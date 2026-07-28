import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "Integration" / "CompositionRoot"))
sys.path.insert(0, str(ROOT / "Implementation" / "ENG-006_Memory_Engine" / "Source"))

from object_library import ObjectLibrary
from object_library_service import ObjectLibraryService


class Memory:
    def create_session(self, *args, **kwargs): return SimpleNamespace(status=SimpleNamespace(value="succeeded"))
    def put(self, *args, **kwargs): return SimpleNamespace(status=SimpleNamespace(value="succeeded"))
    def delete(self, *args, **kwargs): return SimpleNamespace(status=SimpleNamespace(value="succeeded"))


class Monitor:
    def record(self, *args, **kwargs): pass


class ObjectLibraryImprovementTests(unittest.TestCase):
    def test_highest_confidence_detection_is_cropped_as_thumbnail(self):
        with tempfile.TemporaryDirectory() as folder:
            import cv2
            import numpy as np
            root = Path(folder)
            frames = root / "Workspace" / "Frames"
            frames.mkdir(parents=True)
            low = np.zeros((20, 20, 3), dtype=np.uint8); low[:] = (255, 0, 0)
            high = np.zeros((20, 20, 3), dtype=np.uint8); high[5:13, 4:10] = (0, 255, 0)
            cv2.imwrite(str(frames / "frame0002.png"), low)
            cv2.imwrite(str(frames / "frame0008.png"), high)
            library = ObjectLibrary(Memory(), Monitor(), root / "Assets" / "ObjectLibrary" / "objects.json")
            cluster = {"name": "Bottle", "frame_count": 2, "confidence": .91, "representative_frames": [8, 2], "instances": [
                {"frame": 8, "confidence": .98, "bounding_box": {"x": 4, "y": 5, "width": 6, "height": 8}},
                {"frame": 2, "confidence": .94, "bounding_box": {"x": 5, "y": 6, "width": 7, "height": 8}},
            ]}
            created = ObjectLibraryService(library).create_from_cluster(cluster, {})
            thumbnail = created["thumbnail"]
            image = cv2.imread(thumbnail["path"])
            self.assertEqual(Path(thumbnail["path"]).name, "thumbnail.png")
            self.assertEqual(thumbnail["frame_id"], "video-frame-8")
            self.assertEqual(thumbnail["confidence"], .98)
            self.assertEqual(image.shape[:2], (8, 6))
            original_id = created["object_id"]
            newer = np.zeros((20, 20, 3), dtype=np.uint8); newer[2:7, 3:7] = (0, 0, 255)
            cv2.imwrite(str(frames / "frame0012.png"), newer)
            regenerated = ObjectLibraryService(library).create_from_cluster({**cluster, "instances": [
                {"frame": 12, "confidence": .99, "bounding_box": {"x": 3, "y": 2, "width": 4, "height": 5}}
            ]}, {})
            self.assertEqual(regenerated["object_id"], original_id)
            self.assertEqual(regenerated["thumbnail"]["frame_id"], "video-frame-12")
            self.assertEqual(cv2.imread(regenerated["thumbnail"]["path"]).shape[:2], (5, 4))

    def test_editable_fields_persist_without_erasing_omitted_values(self):
        with tempfile.TemporaryDirectory() as folder:
            storage = Path(folder) / "Assets" / "ObjectLibrary" / "objects.json"
            library = ObjectLibrary(Memory(), Monitor(), storage)
            library.create({"name": "Cup", "aliases": "mug", "tags": "kitchen", "color": "#112233"}, {"path": ""})
            object_id = library.list()[0]["object_id"]
            library.update(object_id, {"description": "Edited", "properties": {"capacity_ml": 250}, "metadata": {"owner": "lab"}})
            restored = ObjectLibrary(Memory(), Monitor(), storage)
            restored.initialize()
            item = restored.list()[0]
            self.assertEqual(item["aliases"], ("mug",))
            self.assertEqual(item["tags"], ("kitchen",))
            self.assertEqual(item["properties"]["capacity_ml"], 250)
            self.assertEqual(item["metadata"]["owner"], "lab")
            restored.delete(object_id)
            self.assertEqual(restored.list(), ())
            final = ObjectLibrary(Memory(), Monitor(), storage)
            final.initialize()
            self.assertEqual(final.list(), ())


if __name__ == "__main__":
    unittest.main()
