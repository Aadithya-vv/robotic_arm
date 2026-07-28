import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "Integration" / "CompositionRoot"))

from action_builder_store import ActionBuilderStore, ActionLibraryStore


class ActionBuilderStoreTests(unittest.TestCase):
    def test_scene_timeline_and_playhead_round_trip_atomically(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "builder_state.json"
            store = ActionBuilderStore(path)
            state = {"scene_objects": [{"id": "scene-cup", "objectId": "cup", "position": [1, 2], "rotationAngle": 30}],
                     "timeline": [{"objectId": "cup", "positionX": 1, "positionY": 2, "rotationAngle": 30, "timestamp": .75}], "playhead": 0.75, "snap": False}
            saved = store.save(state)
            self.assertEqual(store.load(), saved)
            self.assertEqual(store.load()["scene_objects"][0]["position"], [1.0, 2.0])
            self.assertEqual(set(store.load()["timeline"][0]), {"objectId", "positionX", "positionY", "rotationAngle", "timestamp"})
            self.assertFalse(path.with_suffix(".tmp").exists())
            json.loads(path.read_text(encoding="utf-8"))

    def test_invalid_state_is_rejected_without_overwriting(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "builder_state.json"; store = ActionBuilderStore(path)
            store.save({"scene_objects": [], "timeline": []})
            before = path.read_text(encoding="utf-8")
            with self.assertRaises(ValueError): store.save({"scene_objects": "invalid", "timeline": []})
            self.assertEqual(path.read_text(encoding="utf-8"), before)

    def test_saved_action_is_a_durable_asset_with_preview_video(self):
        with tempfile.TemporaryDirectory() as folder:
            store = ActionLibraryStore(Path(folder) / "Actions")
            scene = [{"id": "scene-cup", "objectId": "cup", "position": [1, 2], "rotationAngle": 30}]
            frames = [{"objectId": "cup", "positionX": 1, "positionY": 2, "rotationAngle": 30, "timestamp": 1.5}]
            action = store.create({"name": "Place Cup", "description": "Place the cup", "category": "Assembly", "estimatedDuration": 4, "tags": ["cup"]}, scene, frames, b"generated-video-content", ".webm")
            self.assertEqual(store.list()[0], action)
            self.assertEqual(action["keyframes"][0], frames[0])
            self.assertNotIn("interpolation", action["keyframes"][0])
            self.assertEqual(set(action), {"id", "name", "description", "category", "estimatedDuration", "tags", "previewVideo", "createdAt", "updatedAt", "referencedObjects", "scene_objects", "keyframes"})
            self.assertEqual(action["scene_objects"], scene)
            self.assertEqual(store.get(action["id"]), action)
            self.assertTrue((Path(folder) / "Actions" / f"{action['id']}.action").is_file())
            preview = store.preview_path(action["id"])
            self.assertEqual(preview.read_bytes(), b"generated-video-content")
            self.assertEqual(action["previewVideo"], f"/action-assets/{action['id']}/preview.webm")
            restarted = ActionLibraryStore(Path(folder) / "Actions")
            self.assertEqual(restarted.list(), [action])
            self.assertEqual(restarted.preview_path(action["id"]).read_bytes(), b"generated-video-content")
            self.assertEqual(set(action["keyframes"][0]), {"objectId", "positionX", "positionY", "rotationAngle", "timestamp"})
            edited = restarted.update(action["id"], {"name": "Place Mug", "tags": ["mug"]})
            self.assertEqual(edited["name"], "Place Mug")
            restarted.delete(action["id"])
            self.assertEqual(ActionLibraryStore(Path(folder) / "Actions").list(), [])
            self.assertFalse(preview.parent.exists())

    def test_action_requires_a_generated_preview(self):
        with tempfile.TemporaryDirectory() as folder:
            store = ActionLibraryStore(Path(folder) / "Actions")
            with self.assertRaisesRegex(ValueError, "did not generate a preview"):
                store.create({"name": "No Video"}, [], [])


if __name__ == "__main__": unittest.main()
