"""Five-minute rolling application diagnostics for TaskGraph v0.4 exports."""
from collections import deque
from datetime import datetime, timedelta, timezone
from threading import RLock
from threading import Event, Thread
from time import process_time, monotonic
import os


class RuntimeMonitor:
    def __init__(self, minutes=5):
        self._window = timedelta(minutes=minutes)
        self._events = deque()
        self._lock = RLock()
        self._stop = Event(); self._thread = None; self._last_cpu = process_time(); self._detector_baseline = None; self._verified_at = monotonic()

    def record(self, category, action, status="succeeded", **details):
        with self._lock:
            now = datetime.now(timezone.utc)
            self._events.append({"timestamp": now.isoformat(), "category": category, "action": action, "status": status, "details": details})
            self._trim(now)

    def snapshot(self):
        with self._lock:
            self._trim(datetime.now(timezone.utc))
            return tuple(dict(item) for item in self._events)

    def rolling_averages(self):
        events = self.snapshot(); processed = [item for item in events if item["category"] == "frame" and item["action"] == "processed"]
        samples = [item for item in events if item["action"] == "sample"]; recognition = [item for item in events if item["category"] == "recognition"]
        scenes = [item for item in events if item["category"] == "scene" and item["action"] == "worker_update"]
        duration = 0.0
        if len(processed) > 1: duration = max(0.001, (datetime.fromisoformat(processed[-1]["timestamp"])-datetime.fromisoformat(processed[0]["timestamp"])).total_seconds())
        average = lambda values: sum(values)/len(values) if values else 0.0
        return {"camera_fps": (len(processed)-1)/duration if duration else 0.0, "inference_fps": 1000.0/max(average([item["details"].get("inference_ms") or 0 for item in processed]), 0.001) if processed else 0.0, "recognition_fps": (len(recognition)-1)/duration if duration and recognition else 0.0, "pipeline_latency_ms": average([item["details"].get("pipeline_latency_ms", 0) for item in scenes]), "inference_latency_ms": average([item["details"].get("inference_ms") or 0 for item in processed]), "scene_latency_ms": average([item["details"].get("latency_ms", 0) for item in scenes]), "cpu_percent": average([item["details"].get("cpu_percent", 0) for item in samples]), "ram_bytes": average([item["details"].get("process_memory_bytes", 0) for item in samples]), "gpu_memory_bytes": average([item["details"].get("gpu_memory_allocated", 0) for item in samples])}

    def clear(self):
        with self._lock: self._events.clear()

    def detector_selected(self, detector):
        with self._lock:
            self._detector_baseline = detector; self._verified_at = monotonic()
            self.record("detector", "selection_baseline", "succeeded", detector=detector)

    def verify_detector(self, frame, detector_used, inference_ms, recognitions, scene_updated):
        with self._lock:
            if self._detector_baseline is None: self._detector_baseline = detector_used
            if detector_used != self._detector_baseline:
                self.record("detector", "consistency_violation", "failed", expected=self._detector_baseline, actual=detector_used, frame=frame)
                raise RuntimeError(f"detector switched without user selection: {self._detector_baseline} -> {detector_used}")
            self.record("frame", "processed", "succeeded", frame=frame, detector_used=detector_used, inference_ms=inference_ms, recognition_count=recognitions, scene_updated=scene_updated)
            if monotonic() - self._verified_at >= 60:
                self.record("detector", "minute_consistency_verified", "succeeded", detector=detector_used, frame=frame)
                self._verified_at = monotonic()

    def start(self):
        if self._thread is not None: return
        self._thread = Thread(target=self._sample_loop, name="taskgraph-monitor", daemon=True); self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread is not None: self._thread.join(timeout=2)

    def _sample_loop(self):
        while not self._stop.wait(1.0):
            current = process_time(); cpu = max(0.0, min(100.0, (current - self._last_cpu) * 100.0)); self._last_cpu = current
            gpu = self._gpu_metrics()
            self.record("monitor", "sample", "succeeded", cpu_percent=cpu, process_memory_bytes=self._process_memory(), **gpu)

    @staticmethod
    def _gpu_metrics():
        try:
            import torch
            if torch.cuda.is_available():
                return {"gpu": torch.cuda.get_device_name(0), "gpu_memory_allocated": int(torch.cuda.memory_allocated(0)), "gpu_memory_reserved": int(torch.cuda.memory_reserved(0))}
        except Exception: pass
        return {"gpu": None, "gpu_memory_allocated": 0, "gpu_memory_reserved": 0}

    @staticmethod
    def _process_memory():
        try:
            import ctypes
            from ctypes import wintypes
            class Counters(ctypes.Structure):
                _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD), ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t)] + [(f"unused{index}", ctypes.c_size_t) for index in range(7)]
            counters = Counters(); counters.cb = ctypes.sizeof(counters)
            ctypes.windll.psapi.GetProcessMemoryInfo(ctypes.windll.kernel32.GetCurrentProcess(), ctypes.byref(counters), counters.cb)
            return int(counters.WorkingSetSize)
        except Exception:
            return 0

    def _trim(self, now):
        cutoff = now - self._window
        while self._events and datetime.fromisoformat(self._events[0]["timestamp"]) < cutoff:
            self._events.popleft()
