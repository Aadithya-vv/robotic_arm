import tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from Launcher.process_manager import reachable
from Launcher.runtime_state import RuntimeState
from Launcher.startup_checker import StartupError,verify
from Launcher.desktop_shortcut import ensure_shortcut
from Launcher.health_monitor import HealthMonitor

class LauncherTests(unittest.TestCase):
    def test_runtime_uses_project_venv(self):
        state=RuntimeState(Path("C:/project"));self.assertEqual(state.python,Path("C:/project/.venv/Scripts/python.exe"))
    def test_missing_venv_is_friendly(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/"Workspace").mkdir();(root/"Assets/ObjectLibrary").mkdir(parents=True);(root/"Models").mkdir();(root/"WebApp/node_modules/react").mkdir(parents=True)
            with self.assertRaises(StartupError) as caught:verify(RuntimeState(root))
            self.assertIn("Virtual Environment",caught.exception.reason)
    @patch("urllib.request.urlopen",side_effect=OSError("offline"))
    def test_unreachable_health_is_false(self,_):self.assertFalse(reachable("http://127.0.0.1:1"))
    @patch("Launcher.desktop_shortcut.sys.platform","win32")
    @patch("Launcher.desktop_shortcut.subprocess.run")
    def test_shortcut_uses_project_pythonw(self,run):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)/"project";desktop=Path(folder)/"desktop";root.mkdir();desktop.mkdir();pythonw=root/".venv/Scripts/pythonw.exe";pythonw.parent.mkdir(parents=True);pythonw.touch()
            with patch("Launcher.desktop_shortcut.detect_desktop",return_value=desktop):target=ensure_shortcut(root)
            self.assertEqual(target,desktop/"TaskGraph.lnk");command=run.call_args.args[0][-1]
            self.assertIn(str(pythonw),command);self.assertIn("run_taskgraph.py",command);self.assertNotIn("TaskGraph Robotics Workstation",command)

    @patch("Launcher.health_monitor.reachable",return_value=False)
    def test_health_monitor_ignores_single_transient_timeout(self,_):
        process=unittest.mock.Mock();process.poll.return_value=None
        state=unittest.mock.Mock(backend=process,frontend=None,backend_restarts=0,frontend_restarts=0)
        manager=unittest.mock.Mock(state=state);monitor=HealthMonitor(manager,failure_threshold=3)
        monitor.check_once();manager.stop_process.assert_not_called();manager.start_backend.assert_not_called()

    @patch("Launcher.health_monitor.reachable",return_value=False)
    def test_health_monitor_restarts_after_confirmed_failure_and_waits_ready(self,_):
        process=unittest.mock.Mock();process.poll.return_value=None;replacement=unittest.mock.Mock()
        state=unittest.mock.Mock(backend=process,frontend=None,backend_restarts=0,frontend_restarts=0)
        manager=unittest.mock.Mock(state=state)
        def start():state.backend=replacement
        manager.start_backend.side_effect=start
        monitor=HealthMonitor(manager,failure_threshold=3)
        for _ in range(3):monitor.check_once()
        manager.stop_process.assert_called_once_with(process);manager.start_backend.assert_called_once();manager.wait_ready.assert_called_once_with(replacement,"http://127.0.0.1:8000/health","Backend",timeout=60)

if __name__=="__main__":unittest.main()
