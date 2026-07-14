import ast
import sys
import unittest
from pathlib import Path
from types import MappingProxyType

SOURCE = Path(__file__).resolve().parents[2] / "Implementation" / "ENG-003_Configuration_Engine" / "Source"
sys.path.insert(0, str(SOURCE))

from taskgraph_configuration import (  # noqa: E402
    ConfigurationContract,
    ConfigurationEngine,
    ConfigurationRequest,
    ConfigurationSchema,
    ConfigurationState,
    ResponseStatus,
    SettingRule,
    SourceLoadResult,
    ValueKind,
)


class SourceStub:
    def __init__(self, settings=None, *, succeeded=True, raises=False):
        self.settings = settings if settings is not None else {"mode": "local", "workers": 2}
        self.succeeded = succeeded
        self.raises = raises
        self.requests = []

    def load(self, request):
        self.requests.append(request)
        if self.raises:
            raise RuntimeError("unavailable")
        return SourceLoadResult(self.succeeded, self.settings, {"provider": "stub"}, (() if self.succeeded else ("unavailable",)))


class LogStub:
    def __init__(self, raises=False):
        self.records = []
        self.raises = raises

    def record(self, record):
        if self.raises:
            raise RuntimeError("logging unavailable")
        self.records.append(record)


def schema(**changes):
    values = dict(rules={"mode": SettingRule(ValueKind.STRING, required=True), "workers": SettingRule(ValueKind.INTEGER, required=True)})
    values.update(changes)
    return ConfigurationSchema(**values)


def request(**changes):
    values = dict(request_id="request-1", correlation_id="correlation-1", source_identity="test-boundary", timestamp_context="controlled-time")
    values.update(changes)
    return ConfigurationRequest(**values)


class ConfigurationEngineTests(unittest.TestCase):
    def test_public_contract_is_implemented(self):
        self.assertIsInstance(ConfigurationEngine(SourceStub(), schema()), ConfigurationContract)

    def test_load_validates_and_exposes_runtime_settings(self):
        log = LogStub()
        engine = ConfigurationEngine(SourceStub(), schema(), log_sink=log)
        response = engine.load(request())
        self.assertEqual(response.status, ResponseStatus.SUCCEEDED)
        self.assertEqual(engine.state, ConfigurationState.AVAILABLE)
        self.assertEqual(response.runtime_configuration.values["workers"], 2)
        self.assertEqual(response.runtime_configuration.revision, 1)
        self.assertTrue(response.explanations)
        self.assertTrue(log.records)

    def test_source_receives_contract_request_not_engine_internals(self):
        source = SourceStub()
        ConfigurationEngine(source, schema()).load(request(metadata={"trace": "one"}))
        self.assertEqual(source.requests[0].correlation_id, "correlation-1")
        self.assertEqual(source.requests[0].metadata["trace"], "one")

    def test_get_returns_same_validated_snapshot(self):
        engine = ConfigurationEngine(SourceStub(), schema())
        loaded = engine.load(request())
        fetched = engine.get(request(request_id="get-1"))
        self.assertIs(fetched.runtime_configuration, loaded.runtime_configuration)
        self.assertEqual(fetched.status, ResponseStatus.SUCCEEDED)

    def test_runtime_configuration_is_deeply_immutable(self):
        source = SourceStub({"mode": "local", "workers": 2, "nested": {"items": [1, 2]}})
        flexible = ConfigurationSchema(schema().rules | {"nested": SettingRule(ValueKind.MAPPING)})
        runtime = ConfigurationEngine(source, flexible).load(request()).runtime_configuration
        self.assertIsInstance(runtime.values, MappingProxyType)
        self.assertIsInstance(runtime.values["nested"], MappingProxyType)
        self.assertEqual(runtime.values["nested"]["items"], (1, 2))
        with self.assertRaises(TypeError):
            runtime.values["mode"] = "remote"

    def test_missing_required_setting_is_explicit(self):
        response = ConfigurationEngine(SourceStub({"mode": "local"}), schema()).load(request())
        self.assertEqual(response.status, ResponseStatus.FAILED)
        self.assertEqual(response.state, ConfigurationState.INVALID)
        self.assertIn("configuration.settings.required_missing", {error.code for error in response.errors})

    def test_unknown_setting_is_rejected_by_default(self):
        response = ConfigurationEngine(SourceStub({"mode": "local", "workers": 2, "extra": True}), schema()).load(request())
        self.assertIn("configuration.settings.unknown_key", {error.code for error in response.errors})

    def test_unknown_setting_can_be_allowed_by_schema(self):
        response = ConfigurationEngine(SourceStub({"mode": "local", "workers": 2, "extra": True}), schema(allow_unknown_keys=True)).load(request())
        self.assertEqual(response.status, ResponseStatus.SUCCEEDED)

    def test_wrong_type_rejects_bool_as_integer(self):
        response = ConfigurationEngine(SourceStub({"mode": "local", "workers": True}), schema()).load(request())
        self.assertIn("configuration.settings.invalid_type", {error.code for error in response.errors})

    def test_none_requires_explicit_permission(self):
        optional_schema = ConfigurationSchema({"optional": SettingRule(ValueKind.STRING, allow_none=True)})
        response = ConfigurationEngine(SourceStub({"optional": None}), optional_schema).load(request())
        self.assertEqual(response.status, ResponseStatus.SUCCEEDED)

    def test_custom_mutable_values_are_rejected(self):
        response = ConfigurationEngine(SourceStub({"mode": "local", "workers": 2, "object": object()}), schema(allow_unknown_keys=True)).load(request())
        self.assertIn("configuration.settings.unsupported_value", {error.code for error in response.errors})

    def test_source_failure_is_explicit(self):
        response = ConfigurationEngine(SourceStub(succeeded=False), schema()).load(request())
        self.assertEqual(response.status, ResponseStatus.FAILED)
        self.assertEqual(response.errors[0].code, "configuration.source.failed")

    def test_source_exception_is_explicit(self):
        response = ConfigurationEngine(SourceStub(raises=True), schema()).load(request())
        self.assertEqual(response.errors[0].code, "configuration.source.exception")

    def test_non_contract_source_result_is_rejected(self):
        class BadSource:
            def load(self, request):
                return {"mode": "local"}
        response = ConfigurationEngine(BadSource(), schema()).load(request())
        self.assertEqual(response.errors[0].code, "configuration.source.invalid_result")

    def test_invalid_request_envelope_is_rejected_without_loading(self):
        source = SourceStub()
        response = ConfigurationEngine(source, schema()).load(request(request_id="", contract_version="2.0.0"))
        self.assertEqual(response.status, ResponseStatus.REJECTED)
        self.assertEqual(len(response.errors), 2)
        self.assertFalse(source.requests)

    def test_load_is_invalid_after_configuration_available(self):
        engine = ConfigurationEngine(SourceStub(), schema())
        engine.load(request())
        response = engine.load(request(request_id="again"))
        self.assertEqual(response.status, ResponseStatus.REJECTED)

    def test_get_before_load_is_rejected(self):
        response = ConfigurationEngine(SourceStub(), schema()).get(request())
        self.assertEqual(response.status, ResponseStatus.REJECTED)

    def test_reload_replaces_snapshot_and_increments_revision(self):
        source = SourceStub()
        engine = ConfigurationEngine(source, schema())
        first = engine.load(request()).runtime_configuration
        source.settings = {"mode": "local", "workers": 3}
        second = engine.reload(request(request_id="reload-1")).runtime_configuration
        self.assertEqual(first.values["workers"], 2)
        self.assertEqual(second.values["workers"], 3)
        self.assertEqual(second.revision, 2)

    def test_failed_reload_never_exposes_previous_snapshot_as_success(self):
        source = SourceStub()
        engine = ConfigurationEngine(source, schema())
        engine.load(request())
        source.settings = {"mode": "local"}
        response = engine.reload(request(request_id="reload-1"))
        self.assertEqual(response.status, ResponseStatus.FAILED)
        self.assertIsNone(response.runtime_configuration)
        self.assertEqual(engine.state, ConfigurationState.INVALID)

    def test_shutdown_releases_snapshot(self):
        engine = ConfigurationEngine(SourceStub(), schema())
        engine.load(request())
        response = engine.shutdown(request(request_id="shutdown-1"))
        self.assertEqual(response.status, ResponseStatus.SUCCEEDED)
        self.assertEqual(engine.state, ConfigurationState.STOPPED)
        self.assertIsNone(engine.runtime_configuration)

    def test_shutdown_from_unloaded_is_supported(self):
        engine = ConfigurationEngine(SourceStub(), schema())
        self.assertEqual(engine.shutdown(request()).status, ResponseStatus.SUCCEEDED)

    def test_operations_after_shutdown_are_rejected(self):
        engine = ConfigurationEngine(SourceStub(), schema())
        engine.shutdown(request())
        self.assertEqual(engine.load(request(request_id="later")).status, ResponseStatus.REJECTED)

    def test_logging_failure_is_explicit(self):
        response = ConfigurationEngine(SourceStub(), schema(), log_sink=LogStub(raises=True)).load(request())
        self.assertEqual(response.status, ResponseStatus.FAILED)
        self.assertEqual(response.state, ConfigurationState.INVALID)
        self.assertEqual(response.errors[0].code, "configuration.logging.delivery_failed")

    def test_deterministic_controlled_inputs_produce_same_identity(self):
        first = ConfigurationEngine(SourceStub(), schema()).load(request())
        second = ConfigurationEngine(SourceStub(), schema()).load(request())
        self.assertEqual(first.response_id, second.response_id)
        self.assertEqual(first.runtime_configuration.configuration_id, second.runtime_configuration.configuration_id)

    def test_rule_40_has_no_concrete_engine_import(self):
        for path in SOURCE.rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            rendered = " ".join(ast.unparse(node) for node in ast.walk(tree) if isinstance(node, (ast.Import, ast.ImportFrom)))
            self.assertNotIn("taskgraph_bootstrap", rendered)
            self.assertNotIn("taskgraph_kernel", rendered)
            self.assertNotIn("Implementation", rendered)


if __name__ == "__main__":
    unittest.main()
