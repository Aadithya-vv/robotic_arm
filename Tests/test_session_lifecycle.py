import tempfile
import unittest
from pathlib import Path

from session_lifecycle import clear_temporary_session


class SessionLifecycleTests(unittest.TestCase):
    def test_cleanup_removes_session_and_preserves_object_library(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            workspace = root / "Workspace" / "Frames" / "Detected"
            workspace.mkdir(parents=True)
            (workspace / "frame0001.png").write_bytes(b"temporary")
            library = root / "Assets" / "ObjectLibrary"
            library.mkdir(parents=True)
            (library / "objects.json").write_text('{"objects": []}', encoding="utf-8")
            report = root / "Assets" / "TaskGraph_Runtime_Report.json"
            report.write_text("{}", encoding="utf-8")

            clear_temporary_session(root)

            self.assertFalse((root / "Workspace" / "Frames").exists())
            self.assertFalse(report.exists())
            self.assertTrue((library / "objects.json").is_file())


if __name__ == "__main__":
    unittest.main()
