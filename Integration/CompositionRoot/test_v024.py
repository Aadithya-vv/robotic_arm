"""Headless TaskGraph v0.4 final M2 refinement verification."""
import json
from pathlib import Path
import time
import unittest
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "App"))

from startup import create_runtime
from shutdown import shutdown_runtime
from validation import validate_runtime
from desktop import TaskGraphApp


class ProviderChoice:
    def get(self): return "mock"


class RefinementTests(unittest.TestCase):
    def setUp(self): self.runtime = create_runtime(correlation_id="v024-test")
    def tearDown(self):
        if self.runtime.bootstrap.state.value == "ready": shutdown_runtime(self.runtime, "v024-test-shutdown")

    def test_complete_refinement_workflow(self):
        models = self.runtime.model_manager.installed_models()
        self.assertEqual({item.model_id for item in models}, {"yolo11n", "yolo11s", "yolo11m"})
        self.assertTrue(all(item.installed and item.checksum_valid for item in models))
        self.assertEqual(self.runtime.perception.detector_status()["current"], "YOLO11M")
        self.runtime.perception.select_detector("Classical CV")
        first = self.runtime.perception.capture_pipeline("v024-first")
        self.assertTrue(first.succeeded); self.assertGreaterEqual(len(first.vision_response.observation.objects), 2)
        descriptor_names = {feature.name for item in first.vision_response.observation.objects for feature in item.features}
        self.assertTrue({"geometry", "appearance", "scores"}.issubset(descriptor_names))
        selected = first.vision_response.observation.objects[0]
        fields = {"name":"Verification Object","category":"test","type":"capture","material":"","color":"","weight":"","description":"v0.2.3","tags":"verification","aliases":"test object","notes":"","created":"2026-07-15"}
        descriptors = tuple((item.name, tuple(item.values)) for item in selected.features)
        crop = {"x":0,"y":0,"width":4,"height":4,"channels":3,"pixel_format":"bgr8","pixels_hex":"00","frame_id":first.camera_response.observation.observation_id}
        stored = self.runtime.object_library.create(fields, crop, descriptors); self.assertEqual(stored.status.value, "succeeded")
        with self.assertRaises(ValueError): self.runtime.object_library.create(fields, crop, descriptors)
        second = self.runtime.perception.capture_pipeline("v04-second")
        self.assertFalse(any(item.properties.get("known") for item in second.vision_response.observation.objects))
        self.assertTrue((ROOT / "Assets" / "ObjectLibrary" / "objects.json").is_file())
        restarted = create_runtime(correlation_id="v04-restart")
        try:
            self.assertTrue(any(item["name"] == "Verification Object" for item in restarted.object_library.list()))
        finally:
            shutdown_runtime(restarted, "v04-restart-shutdown")
        time.sleep(1.1); self.assertTrue(any(item["action"] == "sample" for item in self.runtime.monitor.snapshot()))
        for mode in ("YOLO11n", "YOLO11s", "YOLO11m"):
            self.runtime.perception.select_detector(mode)
            result = self.runtime.perception.capture_pipeline(f"v024-{mode.lower()}")
            self.assertTrue(result.succeeded)
            status = self.runtime.perception.detector_status()
            self.assertEqual(status["current"], mode.upper())
            self.assertIsNotNone(status["inference_ms"])
        self.runtime.perception.select_detector("Classical CV")
        self.assertTrue(self.runtime.perception.capture_pipeline("v024-classical").succeeded)
        self.assertEqual(self.runtime.perception.detector_status()["current"], "Classical CV")
        checks = validate_runtime(self.runtime, "v024-validation")
        app = object.__new__(TaskGraphApp); app.runtime=self.runtime; app.video=self.runtime.video_workspace; app.checks=checks; app.root_path=ROOT; app.provider=ProviderChoice(); app._started=time.monotonic()-2
        app.export_report(show_dialog=False)
        export = ROOT / "Assets" / "TaskGraph_Runtime_Report.json"
        payload = json.loads(export.read_text(encoding="utf-8"))
        for key in ("application_version","engine_health","frames","detections","scene","objects","relationships","validation","last_five_minutes","logs","performance","gpu","recognition","memory","errors","warnings","timeline"):
            self.assertIn(key, payload)
        camera, scene = self.runtime.perception.reset("v04-reset")
        self.assertEqual(scene.status.value, "succeeded"); self.assertEqual(self.runtime.camera.state.value, "ready")
        self.runtime.object_library.delete(stored.record.key)


if __name__ == "__main__": unittest.main()
