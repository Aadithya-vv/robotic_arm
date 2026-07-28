"""Non-blocking extracted-frame workspace orchestration for TaskGraph v0.4."""
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from threading import Event, Thread
from time import monotonic
from types import MappingProxyType
from typing import Mapping

from taskgraph_scene import SceneRequest
from taskgraph_vision import VisionRequest


@dataclass(frozen=True, slots=True)
class VideoMetadata:
    path: str
    name: str
    duration_seconds: float
    width: int
    height: int
    fps: float
    frame_count: int


@dataclass(frozen=True, slots=True)
class ExtractedFrame:
    """Application-owned immutable image frame satisfying the Vision input boundary."""
    observation_id: str
    correlation_id: str
    data: bytes
    width: int
    height: int
    channels: int
    pixel_format: str
    timestamp_context: str
    metadata: Mapping

    def __post_init__(self):
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))


class VideoWorkspace:
    def __init__(self, runtime, root):
        self.runtime, self.root = runtime, Path(root)
        self.workspace = self.root / "Workspace"
        self.frames_dir = self.workspace / "Frames"
        self.detected_dir = self.frames_dir / "Detected"
        self.accepted_dir = self.frames_dir / "Accepted"
        self.rejected_dir = self.frames_dir / "Rejected"
        self.metadata = None
        self.frames, self.results = [], {}
        self.errors = []
        self.current_object, self.current_confidence = None, None
        self._cancel, self._thread = Event(), None

    def inspect(self, path):
        import cv2
        capture = cv2.VideoCapture(str(path))
        if not capture.isOpened():
            raise ValueError("The selected video could not be opened.")
        fps = float(capture.get(cv2.CAP_PROP_FPS) or 0)
        count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        self.metadata = VideoMetadata(str(path), Path(path).name, count / fps if fps else 0.0, int(capture.get(cv2.CAP_PROP_FRAME_WIDTH)), int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT)), fps, count)
        capture.release()
        return self.metadata

    def extract_async(self, rate, progress, done):
        self.cancel()
        self._cancel.clear()
        self._thread = Thread(target=self._extract, args=(max(0.1, float(rate)), progress, done), name="taskgraph-video-extract", daemon=True)
        self._thread.start()

    def detect_async(self, frame_started, progress, frame_done, done):
        self.cancel()
        self._cancel.clear()
        self.errors, self.results = [], {}
        self.current_object, self.current_confidence = None, None
        self._thread = Thread(target=self._detect, args=(frame_started, progress, frame_done, done), name="taskgraph-video-detect", daemon=True)
        self._thread.start()

    def detect_all(self, frame_started, progress, frame_done, done):
        """Run the complete detection queue synchronously for stable batch processing."""
        self._cancel.clear()
        self.errors, self.results = [], {}
        self.current_object, self.current_confidence = None, None
        self._detect(frame_started, progress, frame_done, done)

    def cancel(self):
        self._cancel.set()

    def _extract(self, rate, progress, done):
        import cv2
        capture = cv2.VideoCapture(self.metadata.path)
        interval = max(1, round((self.metadata.fps or 30.0) / rate))
        expected = max(1, (self.metadata.frame_count + interval - 1) // interval)
        for directory in (self.frames_dir, self.detected_dir, self.accepted_dir, self.rejected_dir):
            directory.mkdir(parents=True, exist_ok=True)
        for old in self.frames_dir.glob("frame*.png"):
            old.unlink()
        for old in self.detected_dir.glob("frame*.png"):
            old.unlink()
        self.frames = []
        source_index = output_index = 0
        started = monotonic()
        while not self._cancel.is_set():
            ok, image = capture.read()
            if not ok:
                break
            if source_index % interval == 0:
                output_index += 1
                target = self.frames_dir / f"frame{output_index:04d}.png"
                cv2.imwrite(str(target), image)
                self.frames.append(target)
                elapsed = monotonic() - started
                progress(output_index, expected, elapsed / output_index * max(0, expected-output_index), target.name)
            source_index += 1
        capture.release()
        done(not self._cancel.is_set(), None)

    def _detect(self, frame_started, progress, frame_done, done):
        import cv2
        total, started = len(self.frames), monotonic()
        baseline = self.runtime.perception.detector_status().get("current")
        try:
            self.runtime.perception.warm_up_detector()
        except Exception as exc:
            return done(False, f"YOLO warm-up failed: {exc}")
        for index, path in enumerate(self.frames, 1):
            if self._cancel.is_set():
                return done(False, None)
            correlation = f"m2-video-frame-{index}"
            frame_started(index, path.name)
            inference_started = monotonic()
            try:
                image = cv2.imread(str(path))
                if image is None:
                    raise ValueError("extracted image could not be read")
                height, width = image.shape[:2]
                observation = ExtractedFrame(f"video-frame-{index}", correlation, image.tobytes(), width, height, 3, "bgr8", datetime.now().isoformat(), {"path": str(path), "video": self.metadata.path, "frame_number": index})
                vision = self.runtime.vision.process(VisionRequest(f"video-vision-{index}", correlation, "video-workspace"), observation)
                if vision.status.value != "succeeded":
                    error = vision.errors[0].message if vision.errors else "YOLO processing failed"
                    raise RuntimeError(error)
                if vision.observation.diagnostics.get("yolo_error"):
                    raise RuntimeError(vision.observation.diagnostics["yolo_error"])
                if vision.observation.objects:
                    strongest = max(vision.observation.objects, key=lambda item: item.confidence)
                    self.current_object = strongest.properties.get("ai_class") or "Household object"
                    self.current_confidence = strongest.confidence
                else:
                    self.current_object, self.current_confidence = "None", None
                scene = self.runtime.scene.update(SceneRequest(f"video-scene-{index}", correlation, "video-workspace"), vision.observation)
                if scene.status.value != "succeeded":
                    raise RuntimeError("Scene update failed")
                annotated = self.detected_dir / path.name
                self._save_annotated(image, vision.observation.objects, annotated)
                self.results[index-1] = (observation, vision.observation, scene.snapshot, annotated, "Ready for review")
                self.runtime.monitor.record("video", "frame_processed", "succeeded", frame=index, total=total, detections=len(vision.observation.objects), detector=baseline)
                frame_done(index-1, (monotonic() - inference_started) * 1000)
            except Exception as exc:
                error = {"stage": "YOLO", "frame": index, "path": str(path), "detector": baseline, "message": str(exc)}
                self.errors.append(error)
                self.runtime.monitor.record("video", "frame_failed", "failed", **error)
                frame_done(index-1, (monotonic() - inference_started) * 1000)
            self.runtime.perception.reset_detection_context()
            elapsed = monotonic() - started
            progress(index, total, elapsed / index * max(0, total-index), path.name)
        done(True, None)

    @staticmethod
    def _save_annotated(image, objects, target):
        import cv2
        annotated = image.copy()
        for item in objects:
            region = item.region
            x1, y1 = region.x, region.y
            x2, y2 = region.x + region.width, region.y + region.height
            label = item.properties.get("ai_class") or "Object"
            caption = f"{label} {item.confidence:.2f}"
            cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.putText(annotated, caption, (x1, max(16, y1 - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 0), 2, cv2.LINE_AA)
        if not cv2.imwrite(str(target), annotated):
            raise IOError(f"could not save annotated frame: {target}")

    def set_review_status(self, index, status):
        import shutil
        result = self.results.get(index)
        if result is not None:
            self.results[index] = (*result[:4], status)
            destination = self.accepted_dir if status == "Accepted" else self.rejected_dir if status == "Rejected" else None
            if destination is not None:
                destination.mkdir(parents=True, exist_ok=True)
                shutil.copy2(result[3], destination / Path(result[3]).name)
