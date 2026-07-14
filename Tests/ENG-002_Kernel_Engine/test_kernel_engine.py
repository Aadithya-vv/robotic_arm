import ast
import sys
import unittest
from pathlib import Path
from types import MappingProxyType


SOURCE = (
    Path(__file__).resolve().parents[2]
    / "Implementation"
    / "ENG-002_Kernel_Engine"
    / "Source"
)
sys.path.insert(0, str(SOURCE))

from taskgraph_kernel import (  # noqa: E402
    CoordinationRequest,
    KernelConfiguration,
    KernelContract,
    KernelEngine,
    KernelError,
    KernelStartRequest,
    KernelState,
    KernelStopRequest,
    ParticipantResult,
    ParticipantState,
    ResponseStatus,
)


class BootstrapStub:
    def __init__(self, ready=True, *, raises=False):
        self.ready = ready
        self.raises = raises

    def is_ready(self):
        if self.raises:
            raise RuntimeError("provider unavailable")
        return self.ready

    def runtime_metadata(self):
        return {"bootstrap_state": "ready"}


class ParticipantStub:
    def __init__(self, participant_id, calls=None):
        self._participant_id = participant_id
        self.calls = calls if calls is not None else []
        self.start_result = ParticipantResult(True)
        self.coordinate_result = ParticipantResult(True)
        self.stop_result = ParticipantResult(True)
        self.raise_on = None

    @property
    def participant_id(self):
        return self._participant_id

    def _result(self, operation, result):
        self.calls.append((operation, self.participant_id))
        if self.raise_on == operation:
            raise RuntimeError(f"{operation} failed")
        return result

    def start(self, context):
        self.last_start_context = context
        return self._result("start", self.start_result)

    def coordinate(self, operation, payload):
        self.last_operation = operation
        self.last_payload = payload
        return self._result("coordinate", self.coordinate_result)

    def stop(self, context):
        self.last_stop_context = context
        return self._result("stop", self.stop_result)


class RecordingLog:
    def __init__(self, raises=False):
        self.records = []
        self.raises = raises

    def record(self, record):
        if self.raises:
            raise RuntimeError("log unavailable")
        self.records.append(record)


def start_request(**changes):
    values = dict(request_id="start-1", correlation_id="corr-1", source_identity="test")
    values.update(changes)
    return KernelStartRequest(**values)


def coordinate_request(**changes):
    values = dict(
        request_id="coordinate-1",
        correlation_id="corr-1",
        source_identity="test",
        participant_id="registry",
        operation="refresh",
    )
    values.update(changes)
    return CoordinationRequest(**values)


def stop_request(**changes):
    values = dict(request_id="stop-1", correlation_id="corr-1", source_identity="test")
    values.update(changes)
    return KernelStopRequest(**values)


class KernelEngineTests(unittest.TestCase):
    def test_public_contract_is_structurally_implemented(self):
        self.assertIsInstance(KernelEngine(BootstrapStub()), KernelContract)

    def test_start_coordinates_participants_and_runtime_state(self):
        participant = ParticipantStub("registry")
        log = RecordingLog()
        kernel = KernelEngine(BootstrapStub(), [participant], log_sink=log)
        response = kernel.start(start_request())
        self.assertEqual(response.status, ResponseStatus.SUCCEEDED)
        self.assertEqual(kernel.state, KernelState.RUNNING)
        self.assertEqual(response.runtime.bootstrap_metadata["bootstrap_state"], "ready")
        self.assertEqual(response.runtime.participant_states["registry"], ParticipantState.RUNNING)
        self.assertTrue(log.records)

    def test_startup_order_is_configured_then_lexical(self):
        calls = []
        participants = [ParticipantStub("zeta", calls), ParticipantStub("alpha", calls), ParticipantStub("middle", calls)]
        kernel = KernelEngine(BootstrapStub(), participants, configuration=KernelConfiguration(startup_order=("middle",)))
        kernel.start(start_request())
        self.assertEqual(calls, [("start", "middle"), ("start", "alpha"), ("start", "zeta")])

    def test_missing_required_participant_fails_start(self):
        kernel = KernelEngine(BootstrapStub(), configuration=KernelConfiguration(required_participants=("registry",)))
        response = kernel.start(start_request())
        self.assertEqual(response.status, ResponseStatus.FAILED)
        self.assertEqual(kernel.state, KernelState.FAILED)
        self.assertEqual(response.errors[0].code, "kernel.participant.required_missing")

    def test_bootstrap_not_ready_fails_start(self):
        response = KernelEngine(BootstrapStub(False)).start(start_request())
        self.assertEqual(response.status, ResponseStatus.FAILED)
        self.assertEqual(response.errors[0].code, "kernel.bootstrap.not_ready")

    def test_bootstrap_provider_exception_is_explicit(self):
        response = KernelEngine(BootstrapStub(raises=True)).start(start_request())
        self.assertEqual(response.errors[0].code, "kernel.bootstrap.provider_failed")

    def test_duplicate_participant_identity_fails_validation(self):
        response = KernelEngine(BootstrapStub(), [ParticipantStub("a"), ParticipantStub("a")]).start(start_request())
        self.assertIn("kernel.participant.duplicate", {error.code for error in response.errors})

    def test_start_failure_rolls_back_in_reverse_order(self):
        calls = []
        first = ParticipantStub("first", calls)
        second = ParticipantStub("second", calls)
        second.start_result = ParticipantResult(False, (KernelError("dependency", "rejected", "no"),))
        response = KernelEngine(BootstrapStub(), [first, second], configuration=KernelConfiguration(startup_order=("first", "second"))).start(start_request())
        self.assertEqual(response.status, ResponseStatus.FAILED)
        self.assertEqual(calls, [("start", "first"), ("start", "second"), ("stop", "first")])

    def test_participant_exception_is_structured(self):
        participant = ParticipantStub("registry")
        participant.raise_on = "start"
        response = KernelEngine(BootstrapStub(), [participant]).start(start_request())
        self.assertEqual(response.errors[0].code, "kernel.participant.start_exception")

    def test_coordinate_success_increments_runtime_generation(self):
        participant = ParticipantStub("registry")
        kernel = KernelEngine(BootstrapStub(), [participant])
        kernel.start(start_request())
        response = kernel.coordinate(coordinate_request(payload={"key": "value"}))
        self.assertEqual(response.status, ResponseStatus.SUCCEEDED)
        self.assertEqual(response.runtime.generation, 1)
        self.assertEqual(participant.last_operation, "refresh")

    def test_coordinate_unknown_participant_is_rejected(self):
        kernel = KernelEngine(BootstrapStub())
        kernel.start(start_request())
        response = kernel.coordinate(coordinate_request(participant_id="unknown"))
        self.assertEqual(response.status, ResponseStatus.REJECTED)

    def test_coordinate_before_running_is_rejected(self):
        response = KernelEngine(BootstrapStub(), [ParticipantStub("registry")]).coordinate(coordinate_request())
        self.assertEqual(response.status, ResponseStatus.REJECTED)
        self.assertEqual(response.errors[0].code, "kernel.coordinate.invalid_state")

    def test_coordination_failure_does_not_fail_kernel_lifecycle(self):
        participant = ParticipantStub("registry")
        participant.coordinate_result = ParticipantResult(False, (KernelError("provider", "provider.rejected", "no"),))
        kernel = KernelEngine(BootstrapStub(), [participant])
        kernel.start(start_request())
        response = kernel.coordinate(coordinate_request())
        self.assertEqual(response.status, ResponseStatus.FAILED)
        self.assertEqual(kernel.state, KernelState.RUNNING)

    def test_stop_uses_reverse_startup_order(self):
        calls = []
        first = ParticipantStub("first", calls)
        second = ParticipantStub("second", calls)
        kernel = KernelEngine(BootstrapStub(), [first, second], configuration=KernelConfiguration(startup_order=("first", "second")))
        kernel.start(start_request())
        calls.clear()
        response = kernel.stop(stop_request())
        self.assertEqual(response.status, ResponseStatus.SUCCEEDED)
        self.assertEqual(kernel.state, KernelState.STOPPED)
        self.assertEqual(calls, [("stop", "second"), ("stop", "first")])

    def test_stop_before_running_is_rejected(self):
        response = KernelEngine(BootstrapStub()).stop(stop_request())
        self.assertEqual(response.status, ResponseStatus.REJECTED)

    def test_stop_failure_moves_kernel_to_failed(self):
        participant = ParticipantStub("registry")
        participant.stop_result = ParticipantResult(False, (KernelError("provider", "stop.rejected", "no"),))
        kernel = KernelEngine(BootstrapStub(), [participant])
        kernel.start(start_request())
        response = kernel.stop(stop_request())
        self.assertEqual(response.status, ResponseStatus.FAILED)
        self.assertEqual(kernel.state, KernelState.FAILED)

    def test_logging_failure_is_explicit_and_terminal(self):
        kernel = KernelEngine(BootstrapStub(), log_sink=RecordingLog(raises=True))
        response = kernel.start(start_request())
        self.assertEqual(response.status, ResponseStatus.FAILED)
        self.assertEqual(kernel.state, KernelState.FAILED)
        self.assertIn("kernel.logging.delivery_failed", {error.code for error in response.errors})

    def test_invalid_envelope_and_contract_version_are_rejected(self):
        response = KernelEngine(BootstrapStub()).start(start_request(request_id="", contract_version="2.0.0"))
        self.assertEqual(response.status, ResponseStatus.FAILED)
        self.assertEqual(len(response.errors), 2)

    def test_response_ids_are_deterministic(self):
        one = KernelEngine(BootstrapStub()).start(start_request())
        two = KernelEngine(BootstrapStub()).start(start_request())
        self.assertEqual(one.response_id, two.response_id)

    def test_runtime_snapshot_is_immutable(self):
        response = KernelEngine(BootstrapStub(), [ParticipantStub("registry")]).start(start_request())
        self.assertIsInstance(response.runtime.participant_states, MappingProxyType)
        with self.assertRaises(TypeError):
            response.runtime.participant_states["registry"] = ParticipantState.FAILED

    def test_rule_40_has_no_concrete_engine_imports(self):
        for path in SOURCE.rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            imports = [node for node in ast.walk(tree) if isinstance(node, (ast.Import, ast.ImportFrom))]
            rendered = " ".join(ast.unparse(node) for node in imports)
            self.assertNotIn("taskgraph_bootstrap", rendered)
            self.assertNotIn("Implementation", rendered)


if __name__ == "__main__":
    unittest.main()
