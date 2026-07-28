"""M2.1 adaptive visual processor using only ENG-009 public provider contracts."""
from __future__ import annotations

from math import sqrt
from time import perf_counter

from taskgraph_vision import BoundingRegion, FeatureDescriptor, ProcessorResult, VisualObject, VisionConfiguration
from ai_detector import UltralyticsDetector, YOLORuntimeError
from descriptors import component_features, opencv_descriptors
from fusion import non_maximum_suppression
from recognition import ObjectRecognizer
from temporal import TemporalStabilizer


class AdaptiveVisionProcessor:
    """Optional OpenCV enhancement/detection with deterministic dependency-free fallback."""

    processor_id = "adaptive"

    def __init__(self, model_manager=None, object_library=None, detector_mode="AUTO"):
        self._configuration = None
        self._processed = 0
        self._backend = "python"
        self._model_manager = model_manager
        self._detector_mode = "AUTO"
        self._loaded_detector = "classical"
        self._ai = None
        self._runtime_failed = False; self._runtime_error = None
        # Imported videos are always fresh teaching sessions; review never consults the library.
        self._recognizer = None
        self._temporal = TemporalStabilizer()
        self.select_detector(detector_mode)

    def select_detector(self, mode):
        normalized = str(mode).strip().upper()
        valid = {"AUTO", "YOLO11M", "YOLO11S", "YOLO11N", "CLASSICAL CV"}
        if normalized not in valid: raise ValueError(f"unknown detector: {mode}")
        selected = self._model_manager.select_auto() if normalized == "AUTO" and self._model_manager is not None else normalized.lower().replace(" cv", "")
        self._detector_mode = normalized
        self._loaded_detector = selected
        self._ai = None if selected == "classical" or self._model_manager is None else UltralyticsDetector(self._model_manager, selected)
        self._runtime_failed = False; self._runtime_error = None
        self._temporal.reset()
        try:
            import cv2  # noqa: F401
            import numpy  # noqa: F401
            self._backend = "opencv"
        except ImportError:
            self._backend = "python"
        return self.detector_status()

    def detector_status(self):
        ai = {} if self._ai is None else self._ai.diagnostics()
        current = "Classical CV" if self._ai is None else self._loaded_detector.upper()
        return {"requested": self._detector_mode, "current": current, "loaded": self._ai is None or self._ai.available, "loaded_model": None if self._ai is None else self._loaded_detector, "model_size": ai.get("size_bytes", 0), "model_path": ai.get("model_path"), "inference_ms": ai.get("inference_ms"), "device": ai.get("device", "CPU"), "frame_number": ai.get("frame_number", self._processed), "failed": self._runtime_failed or ai.get("failed", False), "last_error": self._runtime_error or ai.get("last_error"), "stack_summary": ai.get("stack_summary"), "runtime_available": ai.get("runtime_available", False)}

    def warm_up_detector(self):
        if self._ai is not None:
            self._ai.warm_up()

    def reset_temporal(self):
        self._temporal.reset()

    def initialize(self, configuration: VisionConfiguration):
        self._configuration = configuration
        try:
            import cv2  # noqa: F401
            import numpy  # noqa: F401
            self._backend = "opencv"
        except ImportError:
            self._backend = "python"

    def process(self, observation):
        if self._configuration is None:
            return ProcessorResult(False, error_code="vision.adaptive.not_initialized", error_summary="adaptive processor is not initialized")
        if self._runtime_failed:
            return ProcessorResult(False, error_code="vision.yolo.runtime_failed", error_summary=self._runtime_error)
        started = perf_counter()
        try:
            objects, global_features = self._opencv(observation) if self._backend == "opencv" else self._fallback(observation)
            if self._ai is None and len(objects) < 2:
                fallback_objects, fallback_features = self._fallback(observation)
                objects = fallback_objects if len(fallback_objects) > len(objects) else objects
                global_features = tuple(global_features) + tuple(fallback_features)
            objects = self._temporal.update(objects)
        except YOLORuntimeError as exc:
            self._runtime_error = str(exc)
            failed = {"backend": self._backend, "yolo_error": str(exc), "model": exc.model, "frame_number": exc.frame_number, "stack_summary": exc.stack_summary}
            # A bad frame must not poison the remaining imported-frame batch.
            self.select_detector(self._detector_mode)
            return ProcessorResult(True, diagnostics=failed)
        except Exception as exc:
            if self._ai is not None:
                self._runtime_error = f"YOLO Runtime Failed: {type(exc).__name__}: {exc}"
                failed = {"backend": self._backend, "yolo_error": self._runtime_error, "model": self._loaded_detector, "frame_number": self._processed + 1}
                self.select_detector(self._detector_mode)
                return ProcessorResult(True, diagnostics=failed)
            self._backend = "python"; objects, global_features = self._fallback(observation)
        self._processed += 1
        return ProcessorResult(True, tuple(objects[:self._configuration.maximum_candidates]), tuple(global_features), {
            "backend": self._backend, "enhancement": "adaptive", "person_object_separation": True,
            "elapsed_ms": (perf_counter() - started) * 1000.0,
        })

    def _opencv(self, observation):
        import cv2
        import numpy as np

        channels = observation.channels
        image = np.frombuffer(observation.data, dtype=np.uint8).reshape(observation.height, observation.width, channels)
        if channels == 1:
            gray = image.reshape(observation.height, observation.width)
            color = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
        else:
            color = image[:, :, :3].copy()
            gray = cv2.cvtColor(color, cv2.COLOR_BGR2GRAY)

        # White balance, adaptive gamma, CLAHE, denoising, shadow compensation and sharpening.
        means = color.reshape(-1, 3).mean(axis=0); target = max(1.0, float(means.mean()))
        balanced = np.clip(color * (target / np.maximum(means, 1.0)), 0, 255).astype(np.uint8)
        luminance = cv2.cvtColor(balanced, cv2.COLOR_BGR2LAB); l, a, b = cv2.split(luminance)
        l = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8)).apply(l)
        mean_light = max(1.0, float(l.mean())); gamma = max(0.55, min(1.8, 0.9 * 128.0 / mean_light))
        table = np.array([((index / 255.0) ** gamma) * 255 for index in range(256)]).astype("uint8")
        l = cv2.LUT(l, table); enhanced = cv2.cvtColor(cv2.merge((l, a, b)), cv2.COLOR_LAB2BGR)
        enhanced = cv2.fastNlMeansDenoisingColored(enhanced, None, 5, 5, 7, 21)
        blurred = cv2.GaussianBlur(enhanced, (0, 0), 1.2); enhanced = cv2.addWeighted(enhanced, 1.7, blurred, -0.7, 0)
        gray = cv2.cvtColor(enhanced, cv2.COLOR_BGR2GRAY)
        threshold = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 21, 4)
        edges = cv2.Canny(gray, 40, 130)
        mask = cv2.morphologyEx(cv2.bitwise_or(threshold, edges), cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8), iterations=2)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        frame_area = observation.width * observation.height
        candidates = []
        ai_regions = []
        for detected in (() if self._ai is None else self._ai.detect(enhanced)):
            x, y, width, height = detected.x, detected.y, detected.width, detected.height
            rectangle = np.array([[[x, y]], [[x + width, y]], [[x + width, y + height]], [[x, y + height]]], dtype=np.int32)
            base = component_features(width * height, 2 * (width + height), width, height, x + width / 2, y + height / 2, 0.0, 0.0, 0, 0.0, detected.confidence)
            features = base + opencv_descriptors(enhanced, gray, rectangle, (x, y, width, height))
            recognition = {} if self._recognizer is None else self._recognizer.recognize(features)
            properties = {"visual_kind": detected.kind, "ai_class": detected.class_name, "ai_class_id": detected.class_id, **recognition}
            candidates.append(VisualObject(f"ai-proposal-{len(ai_regions)+1}", BoundingRegion(x, y, width, height), detected.confidence, features, properties)); ai_regions.append((x, y, width, height))
        person_regions = []
        for contour in (() if self._ai is not None else contours):
            area = cv2.contourArea(contour)
            if area < frame_area * 0.003 or area > frame_area * 0.85:
                continue
            x, y, width, height = cv2.boundingRect(contour)
            if width >= observation.width * 0.95 and height >= observation.height * 0.95:
                continue
            if any(self._box_iou((x, y, width, height), person) > 0.45 for person in person_regions):
                continue
            if any(self._box_iou((x, y, width, height), ai) > 0.45 for ai in ai_regions):
                continue
            perimeter = cv2.arcLength(contour, True); aspect = width / max(height, 1)
            crop = gray[y:y + height, x:x + width]
            texture = min(1.0, float(crop.std()) / 64.0); contrast = min(1.0, float(crop.max() - crop.min()) / 128.0)
            edge_density = float((edges[y:y + height, x:x + width] > 0).mean())
            corners = cv2.goodFeaturesToTrack(crop, 20, 0.04, 3); corner_count = 0 if corners is None else len(corners)
            shape = min(1.0, area / max(width * height, 1)); detection = (shape + texture + contrast + min(1.0, edge_density * 4)) / 4
            confidence = max(0.05, min(0.99, detection))
            features = component_features(area, perimeter, width, height, x + width / 2, y + height / 2, texture, edge_density, corner_count, contrast, confidence) + opencv_descriptors(enhanced, gray, contour, (x, y, width, height))
            recognition = {} if self._recognizer is None else self._recognizer.recognize(features)
            candidates.append(VisualObject(f"proposal-{len(candidates)+1}", BoundingRegion(x, y, width, height), confidence, features, {"visual_kind": "object_candidate", "ai_class": None, **recognition}))
        candidates = list(non_maximum_suppression(candidates))
        return candidates, (FeatureDescriptor("frame_lighting", (float(gray.mean()) / 255.0, float(gray.std()) / 255.0)),)

    def _fallback(self, observation):
        """Create independent regional proposals without ever boxing the full frame."""
        width, height, channels = observation.width, observation.height, observation.channels
        data = observation.data
        objects = []
        regions = ((0, 0, width // 2, height // 2), (width // 2, 0, width - width // 2, height // 2), (0, height // 2, width // 2, height - height // 2), (width // 2, height // 2, width - width // 2, height - height // 2))
        for index, (x, y, w, h) in enumerate(regions, 1):
            values = []
            for row in range(y, y + h):
                start = (row * width + x) * channels; values.extend(data[start:start + w * channels])
            if not values: continue
            mean = sum(values) / len(values); variance = sum((value - mean) ** 2 for value in values) / len(values)
            texture = min(1.0, sqrt(variance) / 64.0); contrast = min(1.0, (max(values) - min(values)) / 128.0)
            detection = (texture + contrast) / 2.0
            if detection < 0.08: continue
            confidence = min(0.95, 0.35 + detection * 0.6)
            area, perimeter, aspect = w * h, 2 * (w + h), w / max(h, 1)
            bins = [0] * 8
            for value in values: bins[min(7, value // 32)] += 1
            histogram = FeatureDescriptor("color_histogram", tuple(count / len(values) for count in bins))
            features = self._features(area, perimeter, aspect, x + w / 2, y + h / 2, texture, texture, 0, 1.0, contrast, detection, confidence) + (histogram,)
            recognition = {} if self._recognizer is None else self._recognizer.recognize(features)
            objects.append(VisualObject(f"proposal-{index}", BoundingRegion(x, y, w, h), confidence, features, {"visual_kind": "object_candidate", "fallback": True, "ai_class": None, **recognition}))
        return objects, (FeatureDescriptor("frame_lighting", (sum(data) / max(len(data), 1) / 255.0,)),)

    @staticmethod
    def _features(area, perimeter, aspect, center_x, center_y, texture, edge_density, corners, shape, contrast, detection, confidence):
        return (
            FeatureDescriptor("geometry", (area, perimeter, aspect, center_x, center_y, 0.0)),
            FeatureDescriptor("appearance", (texture, edge_density, float(corners), shape, contrast)),
            FeatureDescriptor("scores", (shape, texture, contrast, 0.0, detection, confidence)),
            FeatureDescriptor("motion_vector", (0.0, 0.0)),
        )

    @staticmethod
    def _box_iou(first, second):
        x1, y1 = max(first[0], second[0]), max(first[1], second[1])
        x2, y2 = min(first[0] + first[2], second[0] + second[2]), min(first[1] + first[3], second[1] + second[3])
        intersection = max(0, x2 - x1) * max(0, y2 - y1)
        union = first[2] * first[3] + second[2] * second[3] - intersection
        return 0.0 if union <= 0 else intersection / union

    def diagnostics(self):
        return {"backend": self._backend, "processed": self._processed, "initialized": self._configuration is not None, "detector": self.detector_status(), "ai": {} if self._ai is None else self._ai.diagnostics()}

    def shutdown(self):
        self._configuration = None; self._temporal.reset()
