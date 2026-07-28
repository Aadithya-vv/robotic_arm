"""Application-level Camera -> Vision -> Scene orchestration through public contracts."""
from __future__ import annotations

from dataclasses import dataclass
from threading import RLock
from time import perf_counter

from taskgraph_camera import CameraConfiguration, CameraRequest
from taskgraph_scene import SceneRequest
from taskgraph_vision import VisionRequest
from perception_workers import PerceptionWorkers


@dataclass(frozen=True, slots=True)
class PipelineRun:
    succeeded: bool
    camera_response: object
    vision_response: object | None
    scene_response: object | None
    elapsed_ms: float
    error_stage: str | None = None


class PerceptionController:
    def __init__(self, camera, vision, scene, camera_configuration, monitor=None, detector=None):
        self.camera = camera
        self.vision = vision
        self.scene = scene
        self.camera_configuration = camera_configuration
        self.latest_run = None
        self.total_runs = 0
        self._sequence = 0
        self._lock = RLock()
        self._monitor = monitor
        self._detector = detector
        self._workers = PerceptionWorkers(camera, vision, scene, self.detector_status, monitor, self._publish_worker, camera_configuration.frames_per_second) if monitor is not None else None

    def _publish_worker(self, run):
        with self._lock:
            self.latest_run = run; self.total_runs += 1

    def start_background(self):
        if self._workers is not None: self._workers.start()

    def stop_background(self):
        if self._workers is not None: self._workers.stop()

    def worker_diagnostics(self):
        return {} if self._workers is None else self._workers.diagnostics()

    def connect_camera(self, provider_id="mock", device_id=None, correlation_id="m2-camera-connect"):
        with self._lock:
            if self.camera.state.value == "ready":
                if self.camera_configuration.provider_id == provider_id:
                    return None
                self.disconnect_camera(correlation_id)
            config = CameraConfiguration(
                provider_id=provider_id,
                device_id=device_id or ("mock-camera-0" if provider_id == "mock" else "0"),
                width=640 if provider_id == "mock" else 1280,
                height=480 if provider_id == "mock" else 720,
                frames_per_second=self.camera_configuration.frames_per_second,
                pixel_format=self.camera_configuration.pixel_format,
            )
            response = self.camera.initialize(CameraRequest("ui-camera-connect", correlation_id, "desktop-app"), config)
            if response.status.value == "succeeded":
                self.camera_configuration = config
            self._record("camera", "connect", response.status.value, provider=provider_id)
            return response

    def disconnect_camera(self, correlation_id="m2-camera-disconnect"):
        self.stop_background()
        with self._lock:
            if self.camera.state.value not in ("ready", "failed"):
                return None
            response = self.camera.shutdown(CameraRequest("ui-camera-disconnect", correlation_id, "desktop-app"))
            self._record("camera", "disconnect", response.status.value)
            return response

    def capture_pipeline(self, correlation_id=None):
        with self._lock:
            self._sequence += 1
            correlation = correlation_id or f"m2-pipeline-{self._sequence}"
            started = perf_counter()
            camera = self.camera.acquire(CameraRequest(f"capture-{self._sequence}", correlation, "perception-integration"))
            if camera.status.value != "succeeded":
                return self._finish(False, camera, None, None, started, "Camera")
            vision = self.vision.process(VisionRequest(f"vision-{self._sequence}", correlation, "perception-integration"), camera.observation)
            if vision.status.value != "succeeded":
                return self._finish(False, camera, vision, None, started, "Vision")
            scene = self.scene.update(SceneRequest(f"scene-{self._sequence}", correlation, "perception-integration"), vision.observation)
            if self._monitor is not None:
                detector = self.detector_status(); recognized = sum(bool(item.properties.get("known")) for item in vision.observation.objects)
                self._monitor.verify_detector(self._sequence, detector.get("current"), detector.get("inference_ms"), recognized, scene.status.value == "succeeded")
            return self._finish(scene.status.value == "succeeded", camera, vision, scene, started, None if scene.status.value == "succeeded" else "Scene")

    def _finish(self, succeeded, camera, vision, scene, started, error_stage):
        run = PipelineRun(succeeded, camera, vision, scene, (perf_counter() - started) * 1000.0, error_stage)
        self.latest_run = run
        self.total_runs += 1
        self._record("pipeline", "capture", "succeeded" if succeeded else "failed", elapsed_ms=run.elapsed_ms, error_stage=error_stage, detections=0 if vision is None or vision.observation is None else len(vision.observation.objects), tracked=0 if scene is None or scene.snapshot is None else len(scene.snapshot.objects))
        return run

    def reset(self, correlation_id="m2-perception-reset"):
        """Recover the perception lifecycle without restarting TaskGraph."""
        with self._lock:
            self.disconnect_camera(correlation_id)
            scene_response = self.scene.reset(SceneRequest("reset-scene", correlation_id, "perception-integration"))
            self.latest_run = None
            self.total_runs = 0
            camera_response = self.connect_camera("mock", correlation_id=correlation_id)
            self._record("pipeline", "reset", "succeeded" if scene_response.status.value == "succeeded" else "failed")
            return camera_response, scene_response

    def select_detector(self, mode):
        if self._detector is None: raise RuntimeError("detector control is unavailable")
        status = self._detector.select_detector(mode)
        if self._monitor is not None: self._monitor.detector_selected(status.get("current"))
        self._record("vision", "detector_selected", "succeeded", **status); return status

    def detector_status(self):
        return {} if self._detector is None else self._detector.detector_status()

    def warm_up_detector(self):
        if self._detector is not None:
            self._detector.warm_up_detector()

    def reset_detection_context(self):
        if self._detector is not None:
            self._detector.reset_temporal()

    def _record(self, category, action, status, **details):
        if self._monitor is not None:
            self._monitor.record(category, action, status, **details)
