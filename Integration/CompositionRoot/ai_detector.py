"""Optional official Ultralytics detector provider."""
from dataclasses import dataclass
from time import perf_counter
import traceback


@dataclass(frozen=True, slots=True)
class AIDetection:
    x: int; y: int; width: int; height: int; confidence: float; class_id: int; class_name: str; kind: str


class YOLORuntimeError(RuntimeError):
    def __init__(self, model, frame_number, exception, stack_summary):
        self.model = model; self.frame_number = frame_number; self.exception = exception; self.stack_summary = stack_summary
        super().__init__(f"YOLO Runtime Failed: model={model}; frame={frame_number}; {exception}")


class UltralyticsDetector:
    def __init__(self, model_manager, model_id="yolo11n"):
        self.manager = model_manager; self.model_id = model_id; self._model = None; self._error = None; self._stack_summary = None; self._inference_ms = None; self._device = "CPU"; self._frame_number = 0; self._failed = False

    @property
    def available(self):
        status = self.manager.status(self.model_id)
        return status.checksum_valid and status.runtime_available

    def _ensure_model(self):
        if self._model is not None:
            return
        from ultralytics import YOLO
        self._model = YOLO(self.manager.status(self.model_id).path)
        from gpu_runtime import accelerator_diagnostics
        accelerator = accelerator_diagnostics()
        if accelerator["device"] == "CUDA Initialization Failed":
            raise RuntimeError(f"CUDA Initialization Failed: {accelerator['cuda_error']}")
        self._device_target = 0 if accelerator["cuda_available"] else "cpu"
        self._model.to(self._device_target)

    def warm_up(self):
        """Load weights once and run one synthetic inference before the frame queue."""
        if not self.available:
            raise YOLORuntimeError(self.model_id, 0, "model weights or Ultralytics runtime unavailable", "warm-up availability check failed")
        try:
            import numpy as np
            self._ensure_model()
            self._model.predict(np.zeros((640, 640, 3), dtype=np.uint8), verbose=False, conf=0.2, imgsz=640, device=self._device_target)
        except YOLORuntimeError:
            raise
        except Exception as exc:
            self._error = f"{type(exc).__name__}: {exc}"; self._failed = True
            self._stack_summary = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__, limit=4))
            raise YOLORuntimeError(self.model_id, 0, self._error, self._stack_summary) from exc

    def detect(self, image):
        self._frame_number += 1
        if self._failed: raise YOLORuntimeError(self.model_id, self._frame_number, self._error, "runtime remains failed until detector is reselected")
        if not self.available:
            self._failed = True; self._error = "model weights or Ultralytics runtime unavailable"
            raise YOLORuntimeError(self.model_id, self._frame_number, self._error, "availability check failed")
        try:
            self._ensure_model()
            height, width = image.shape[:2]
            started = perf_counter(); results = self._model.predict(image, verbose=False, conf=0.2, imgsz=640, device=self._device_target); self._inference_ms = (perf_counter()-started)*1000
            try:
                import torch
                self._device = "GPU" if torch.cuda.is_available() else "CPU"
            except ImportError: self._device = "CPU"
            values = []
            for result in results:
                for box in result.boxes:
                    raw = box.xyxy[0].tolist()
                    x1, y1, x2, y2 = (int(raw[0]), int(raw[1]), int(raw[2]), int(raw[3]))
                    x1,y1,x2,y2=max(0,x1),max(0,y1),min(width,x2),min(height,y2); class_id = int(box.cls[0]); name = result.names[class_id]
                    if x2<=x1 or y2<=y1 or (x2-x1)>=width*.95 and (y2-y1)>=height*.95: continue
                    if name.casefold() in {"person", "face", "hand", "arm", "body"}: continue
                    kind = "object_candidate"
                    values.append(AIDetection(x1, y1, x2 - x1, y2 - y1, float(box.conf[0]), class_id, name, kind))
            return tuple(values)
        except YOLORuntimeError:
            raise
        except Exception as exc:
            self._error = f"{type(exc).__name__}: {exc}"; self._failed = True
            self._stack_summary = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__, limit=4))
            raise YOLORuntimeError(self.model_id, self._frame_number, self._error, self._stack_summary) from exc

    def diagnostics(self):
        status = self.manager.status(self.model_id)
        return {"model": self.model_id, "weights_valid": status.checksum_valid, "runtime_available": status.runtime_available, "size_bytes": status.size_bytes, "inference_ms": self._inference_ms, "device": self._device, "model_path": status.path, "frame_number": self._frame_number, "failed": self._failed, "last_error": self._error, "stack_summary": self._stack_summary}
