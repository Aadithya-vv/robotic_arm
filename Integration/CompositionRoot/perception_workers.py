"""Bounded staged workers that keep camera, inference, and UI independent."""
from dataclasses import dataclass
from queue import Empty, Full, Queue
from threading import Event, Lock, Thread
from time import monotonic, perf_counter, sleep

from taskgraph_camera import CameraRequest
from taskgraph_scene import SceneRequest
from taskgraph_vision import VisionRequest


@dataclass(frozen=True, slots=True)
class WorkerRun:
    succeeded: bool; camera_response: object; vision_response: object | None; scene_response: object | None; elapsed_ms: float; error_stage: str | None = None


class PerceptionWorkers:
    def __init__(self, camera, vision, scene, detector_status, monitor, publish, fps=30):
        self.camera, self.vision, self.scene = camera, vision, scene
        self.detector_status, self.monitor, self.publish = detector_status, monitor, publish
        self.interval = 1.0 / max(1, fps); self.stop_event = Event(); self.queues = tuple(Queue(maxsize=1) for _ in range(3))
        self.threads = (); self.sequence = 0; self.dropped = 0; self.error = None; self._lock = Lock()

    def start(self):
        if self.threads and all(thread.is_alive() for thread in self.threads): return
        self.stop_event.clear(); self.error = None
        targets = (("taskgraph-camera", self._capture), ("taskgraph-inference", self._infer), ("taskgraph-recognition", self._recognize), ("taskgraph-scene", self._scene))
        self.threads = tuple(Thread(name=name, target=target, daemon=True) for name, target in targets)
        for thread in self.threads: thread.start()
        self.monitor.record("workers", "started", "succeeded", workers=[thread.name for thread in self.threads])

    def stop(self):
        self.stop_event.set()
        for thread in self.threads: thread.join(timeout=5)
        alive = [thread.name for thread in self.threads if thread.is_alive()]
        self._clear_queues(); self.threads = ()
        self.monitor.record("workers", "stopped", "failed" if alive else "succeeded", alive=alive, dropped_frames=self.dropped)
        if alive: raise RuntimeError(f"workers did not stop: {alive}")

    def diagnostics(self):
        return {"running": bool(self.threads), "threads": {thread.name: thread.is_alive() for thread in self.threads}, "queue_depths": [queue.qsize() for queue in self.queues], "dropped_frames": self.dropped, "error": self.error}

    def _capture(self):
        next_frame = monotonic()
        while not self.stop_event.is_set():
            self.sequence += 1; started = perf_counter()
            response = self.camera.acquire(CameraRequest(f"worker-camera-{self.sequence}", "m2-live", "perception-workers"))
            if response.status.value != "succeeded": return self._fail("Camera", response)
            self._put_latest(self.queues[0], (self.sequence, started, response))
            next_frame += self.interval; sleep(max(0, next_frame-monotonic()))

    def _infer(self):
        while not self.stop_event.is_set():
            item = self._get(self.queues[0])
            if item is None: continue
            sequence, started, camera = item
            vision = self.vision.process(VisionRequest(f"worker-vision-{sequence}", "m2-live", "perception-workers"), camera.observation)
            if vision.status.value != "succeeded": return self._fail("Vision", vision, camera=camera, started=started)
            self._put_latest(self.queues[1], (sequence, started, camera, vision))

    def _recognize(self):
        while not self.stop_event.is_set():
            item = self._get(self.queues[1])
            if item is None: continue
            sequence, started, camera, vision = item
            recognized = sum(bool(obj.properties.get("known")) for obj in vision.observation.objects)
            self.monitor.record("recognition", "frame", "succeeded", frame=sequence, recognized=recognized)
            self._put_latest(self.queues[2], (sequence, started, camera, vision, recognized))

    def _scene(self):
        while not self.stop_event.is_set():
            item = self._get(self.queues[2])
            if item is None: continue
            sequence, started, camera, vision, recognized = item; scene_started = perf_counter()
            scene = self.scene.update(SceneRequest(f"worker-scene-{sequence}", "m2-live", "perception-workers"), vision.observation)
            scene_ms = (perf_counter()-scene_started)*1000; succeeded = scene.status.value == "succeeded"
            status = self.detector_status(); self.monitor.verify_detector(sequence, status.get("current"), status.get("inference_ms"), recognized, succeeded)
            run = WorkerRun(succeeded, camera, vision, scene, (perf_counter()-started)*1000, None if succeeded else "Scene")
            self.publish(run); self.monitor.record("scene", "worker_update", "succeeded" if succeeded else "failed", frame=sequence, latency_ms=scene_ms, pipeline_latency_ms=run.elapsed_ms)
            if not succeeded: return self._fail("Scene", scene)

    def _put_latest(self, queue, value):
        try: queue.put_nowait(value)
        except Full:
            try: queue.get_nowait()
            except Empty: pass
            queue.put_nowait(value); self.dropped += 1
            self.monitor.record("workers", "frame_dropped", "succeeded", dropped_frames=self.dropped, queue_depth=queue.qsize())

    def _get(self, queue):
        try: return queue.get(timeout=0.1)
        except Empty: return None

    def _fail(self, stage, response, camera=None, started=None):
        errors = getattr(response, "errors", ()); self.error = f"{stage}: {errors[0].message if errors else 'worker failed'}"
        self.monitor.record("workers", "worker_failed", "failed", stage=stage, error=self.error); self.stop_event.set()
        if camera is not None: self.publish(WorkerRun(False, camera, response if stage == "Vision" else None, None, (perf_counter()-started)*1000, stage))

    def _clear_queues(self):
        for queue in self.queues:
            while True:
                try: queue.get_nowait()
                except Empty: break
