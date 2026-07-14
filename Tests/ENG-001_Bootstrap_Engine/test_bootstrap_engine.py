"""Behavioral tests for ENG-001 using contract-conforming substitutes."""

from __future__ import annotations

import ast
import unittest
from pathlib import Path
from typing import Any, Mapping, Sequence

from taskgraph_bootstrap import (
    BootstrapConfiguration,
    BootstrapContract,
    BootstrapEngine,
    BootstrapError,
    BootstrapRequest,
    BootstrapState,
    LogRecord,
    ResponseStatus,
    ShutdownRequest,
)


class StubCapability:
    def __init__(
        self,
        capability_id: str,
        errors: Sequence[BootstrapError] = (),
        *,
        raises: bool = False,
    ) -> None:
        self._capability_id = capability_id
        self.errors = tuple(errors)
        self.raises = raises
        self.environments: list[Mapping[str, Any]] = []

    @property
    def capability_id(self) -> str:
        return self._capability_id

    def validate_startup(
        self, environment: Mapping[str, Any]
    ) -> Sequence[BootstrapError]:
        self.environments.append(environment)
        if self.raises:
            raise RuntimeError("provider unavailable")
        return self.errors


class RecordingLogSink:
    def __init__(self, fail_after: int | None = None) -> None:
        self.records: list[LogRecord] = []
        self.fail_after = fail_after

    def record(self, record: LogRecord) -> None:
        if self.fail_after is not None and len(self.records) >= self.fail_after:
            raise RuntimeError("log sink unavailable")
        self.records.append(record)


def startup_request(**overrides: Any) -> BootstrapRequest:
    values: dict[str, Any] = {
        "request_id": "request-1",
        "correlation_id": "workflow-1",
        "source_identity": "test-harness",
        "environment": {"mode": "test"},
    }
    values.update(overrides)
    return BootstrapRequest(**values)


def shutdown_request(**overrides: Any) -> ShutdownRequest:
    values: dict[str, Any] = {
        "request_id": "shutdown-1",
        "correlation_id": "workflow-1",
        "source_identity": "test-harness",
    }
    values.update(overrides)
    return ShutdownRequest(**values)


class BootstrapStartupTests(unittest.TestCase):
    def test_successful_start_establishes_ready_runtime(self) -> None:
        provider = StubCapability("configuration")
        logs = RecordingLogSink()
        engine = BootstrapEngine(
            [provider],
            configuration=BootstrapConfiguration(
                required_capabilities=("configuration",)
            ),
            log_sink=logs,
        )

        response = engine.start(startup_request())

        self.assertEqual(ResponseStatus.SUCCEEDED, response.status)
        self.assertEqual(BootstrapState.READY, response.state)
        self.assertEqual(BootstrapState.READY, engine.state)
        self.assertIsNotNone(response.runtime)
        self.assertEqual(("configuration",), response.runtime.capability_ids)
        self.assertEqual("test", response.runtime.environment["mode"])
        self.assertEqual(1, len(provider.environments))
        self.assertGreaterEqual(len(logs.records), 5)
        self.assertTrue(all(record.engine_id == "ENG-001" for record in logs.records))

    def test_runtime_environment_is_immutable_snapshot(self) -> None:
        original = {"mode": "test"}
        engine = BootstrapEngine()
        response = engine.start(startup_request(environment=original))
        original["mode"] = "changed"

        self.assertEqual("test", response.runtime.environment["mode"])
        with self.assertRaises(TypeError):
            response.runtime.environment["mode"] = "forbidden"

    def test_response_and_explanation_identity_are_deterministic(self) -> None:
        first = BootstrapEngine().start(startup_request())
        second = BootstrapEngine().start(startup_request())

        self.assertEqual(first.response_id, second.response_id)
        self.assertEqual(
            [item.explanation_id for item in first.explanations],
            [item.explanation_id for item in second.explanations],
        )

    def test_second_start_is_rejected_without_changing_ready_state(self) -> None:
        engine = BootstrapEngine()
        engine.start(startup_request())

        response = engine.start(startup_request(request_id="request-2"))

        self.assertEqual(ResponseStatus.REJECTED, response.status)
        self.assertEqual(BootstrapState.READY, response.state)
        self.assertEqual("bootstrap.start.invalid_state", response.errors[0].code)


class BootstrapValidationTests(unittest.TestCase):
    def test_invalid_envelope_fails_startup_explicitly(self) -> None:
        engine = BootstrapEngine()

        response = engine.start(startup_request(correlation_id=""))

        self.assertEqual(ResponseStatus.FAILED, response.status)
        self.assertEqual(BootstrapState.FAILED, response.state)
        self.assertIn(
            "bootstrap.envelope.correlation_id",
            {error.code for error in response.errors},
        )

    def test_unsupported_contract_major_is_rejected(self) -> None:
        response = BootstrapEngine().start(
            startup_request(contract_version="2.0.0")
        )

        self.assertEqual(ResponseStatus.FAILED, response.status)
        self.assertIn(
            "bootstrap.contract.unsupported_version",
            {error.code for error in response.errors},
        )

    def test_empty_environment_can_be_forbidden_by_configuration(self) -> None:
        engine = BootstrapEngine(
            configuration=BootstrapConfiguration(allow_empty_environment=False)
        )

        response = engine.start(startup_request(environment={}))

        self.assertEqual(ResponseStatus.FAILED, response.status)
        self.assertIn(
            "bootstrap.environment.empty", {error.code for error in response.errors}
        )

    def test_missing_required_capability_fails_explicitly(self) -> None:
        engine = BootstrapEngine(
            configuration=BootstrapConfiguration(
                required_capabilities=("configuration",)
            )
        )

        response = engine.start(startup_request())

        self.assertEqual(ResponseStatus.FAILED, response.status)
        self.assertIn(
            "bootstrap.capability.required_missing",
            {error.code for error in response.errors},
        )

    def test_duplicate_capability_provider_is_a_composition_failure(self) -> None:
        engine = BootstrapEngine(
            [StubCapability("configuration"), StubCapability("configuration")]
        )

        response = engine.start(startup_request())

        self.assertEqual(ResponseStatus.FAILED, response.status)
        self.assertIn(
            "bootstrap.capability.duplicate", {error.code for error in response.errors}
        )


class BootstrapFailureTests(unittest.TestCase):
    def test_provider_contract_error_propagates(self) -> None:
        provider_error = BootstrapError(
            category="validation",
            code="stub.not_ready",
            message="stub is not ready",
        )
        engine = BootstrapEngine([StubCapability("stub", (provider_error,))])

        response = engine.start(startup_request())

        self.assertEqual(ResponseStatus.FAILED, response.status)
        self.assertIn("stub.not_ready", {error.code for error in response.errors})

    def test_provider_exception_is_converted_to_dependency_error(self) -> None:
        engine = BootstrapEngine([StubCapability("stub", raises=True)])

        response = engine.start(startup_request())

        self.assertEqual(ResponseStatus.FAILED, response.status)
        self.assertIn(
            "bootstrap.capability.validation_failed",
            {error.code for error in response.errors},
        )

    def test_logging_failure_is_explicit_and_terminal(self) -> None:
        engine = BootstrapEngine(log_sink=RecordingLogSink(fail_after=0))

        response = engine.start(startup_request())

        self.assertEqual(ResponseStatus.FAILED, response.status)
        self.assertEqual(BootstrapState.FAILED, response.state)
        self.assertIn(
            "bootstrap.logging.delivery_failed",
            {error.code for error in response.errors},
        )


class BootstrapLifecycleTests(unittest.TestCase):
    def test_stop_transitions_ready_runtime_to_stopped(self) -> None:
        provider = StubCapability("stub")
        engine = BootstrapEngine([provider])
        engine.start(startup_request())

        response = engine.stop(shutdown_request())

        self.assertEqual(ResponseStatus.SUCCEEDED, response.status)
        self.assertEqual(BootstrapState.STOPPED, response.state)
        self.assertIsNone(engine.runtime)
        self.assertEqual(1, len(provider.environments))

    def test_stop_before_ready_is_rejected(self) -> None:
        engine = BootstrapEngine()

        response = engine.stop(shutdown_request())

        self.assertEqual(ResponseStatus.REJECTED, response.status)
        self.assertEqual(BootstrapState.CREATED, response.state)
        self.assertEqual("bootstrap.stop.invalid_state", response.errors[0].code)

    def test_explanations_cover_lifecycle_transitions(self) -> None:
        engine = BootstrapEngine()
        start = engine.start(startup_request())
        stop = engine.stop(shutdown_request())

        decisions = [record.decision for record in engine.explanations]
        self.assertTrue(any("created to validating" in item for item in decisions))
        self.assertTrue(any("initializing to ready" in item for item in decisions))
        self.assertTrue(any("stopping to stopped" in item for item in decisions))
        self.assertTrue(start.explanations)
        self.assertTrue(stop.explanations)


class BootstrapContractAndRule40Tests(unittest.TestCase):
    def test_engine_satisfies_runtime_checkable_public_contract(self) -> None:
        self.assertIsInstance(BootstrapEngine(), BootstrapContract)

    def test_source_has_no_cross_engine_or_implementation_imports(self) -> None:
        source_root = (
            Path(__file__).resolve().parents[2]
            / "Implementation"
            / "ENG-001_Bootstrap_Engine"
            / "Source"
            / "taskgraph_bootstrap"
        )
        imported_roots: set[str] = set()
        source_text = ""
        for path in source_root.glob("*.py"):
            text = path.read_text(encoding="utf-8")
            source_text += text
            tree = ast.parse(text, filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imported_roots.update(alias.name.split(".")[0] for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                    imported_roots.add(node.module.split(".")[0])

        self.assertNotIn("Implementation", imported_roots)
        self.assertNotRegex(source_text, r"ENG-00[2-9]|ENG-0[1-2][0-9]")


if __name__ == "__main__":
    unittest.main()
