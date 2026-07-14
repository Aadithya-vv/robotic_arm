import sys, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
for relative in ("Integration/CompositionRoot","Implementation/ENG-001_Bootstrap_Engine/Source","Implementation/ENG-002_Kernel_Engine/Source","Implementation/ENG-003_Configuration_Engine/Source","Implementation/ENG-004_Registry_Engine/Source","Implementation/ENG-005_Event_Bus_Engine/Source"):
    sys.path.insert(0,str(ROOT/relative))
from startup import create_runtime  # noqa: E402

class CompositionRootTests(unittest.TestCase):
    def test_runtime_composes_public_engines(self):
        runtime=create_runtime()
        self.assertEqual(runtime.bootstrap.state.value,"ready")
        self.assertEqual(runtime.configuration.state.value,"available")
        self.assertEqual(runtime.registry.state.value,"ready")
        self.assertEqual(runtime.event_bus.state.value,"accepting_events")
        self.assertEqual(runtime.kernel.state.value,"running")
    def test_runtime_stops_through_public_contracts(self):
        runtime=create_runtime();results=runtime.stop()
        self.assertTrue(all(result.status.value=="succeeded" for result in results.values()))
        self.assertEqual(runtime.event_bus.state.value,"stopped")

if __name__=="__main__":unittest.main()
