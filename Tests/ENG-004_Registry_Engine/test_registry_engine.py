import ast
import sys
import unittest
from pathlib import Path
from types import MappingProxyType

SOURCE = Path(__file__).resolve().parents[2] / "Implementation" / "ENG-004_Registry_Engine" / "Source"
sys.path.insert(0, str(SOURCE))

from taskgraph_registry import (  # noqa: E402
    Availability, EngineRegistration, RegistryContract, RegistryEngine, RegistryPolicy,
    RegistryRequest, RegistryState, ResponseStatus,
)


class LogStub:
    def __init__(self, raises=False):
        self.records = []
        self.raises = raises

    def record(self, record):
        if self.raises:
            raise RuntimeError("unavailable")
        self.records.append(record)


def request(**changes):
    values = dict(request_id="request-1", correlation_id="correlation-1", source_identity="test-boundary", timestamp_context="controlled")
    values.update(changes)
    return RegistryRequest(**values)


def registration(engine_id="ENG-001", **changes):
    values = dict(engine_id=engine_id, display_name=f"{engine_id} Engine", contract_id=f"taskgraph.{engine_id.lower()}", contract_version="1.0.0", capabilities=(f"{engine_id.lower()}.public",), provenance={"source": "test"})
    values.update(changes)
    return EngineRegistration(**values)


def ready_engine(registrations=(), **kwargs):
    engine = RegistryEngine(**kwargs)
    engine.open(request())
    for index, item in enumerate(registrations):
        engine.register(request(request_id=f"register-{index}"), item)
    engine.mark_ready(request(request_id="ready"))
    return engine


class RegistryEngineTests(unittest.TestCase):
    def test_public_contract_is_implemented(self):
        self.assertIsInstance(RegistryEngine(), RegistryContract)

    def test_open_enters_accepting_state(self):
        engine = RegistryEngine()
        response = engine.open(request())
        self.assertEqual(response.status, ResponseStatus.SUCCEEDED)
        self.assertEqual(engine.state, RegistryState.ACCEPTING_REGISTRATIONS)

    def test_register_and_lookup_metadata(self):
        item = registration()
        engine = ready_engine((item,))
        response = engine.lookup(request(), "ENG-001")
        self.assertEqual(response.registration, item)
        self.assertEqual(response.status, ResponseStatus.SUCCEEDED)

    def test_registry_stores_metadata_not_engine_instance(self):
        item = registration(metadata={"adapter": "public-contract"})
        snapshot = ready_engine((item,)).snapshot(request()).snapshot
        self.assertEqual(snapshot.registrations["ENG-001"].metadata["adapter"], "public-contract")
        self.assertFalse(hasattr(snapshot.registrations["ENG-001"], "start"))

    def test_duplicate_registration_is_rejected(self):
        engine = RegistryEngine()
        engine.open(request())
        engine.register(request(request_id="one"), registration())
        response = engine.register(request(request_id="two"), registration())
        self.assertEqual(response.status, ResponseStatus.REJECTED)
        self.assertEqual(response.errors[0].code, "registry.registration.duplicate")

    def test_invalid_registration_fields_are_rejected(self):
        engine = RegistryEngine()
        engine.open(request())
        response = engine.register(request(), registration(engine_id="bad", capabilities=()))
        codes = {error.code for error in response.errors}
        self.assertIn("registry.registration.engine_identity", codes)
        self.assertIn("registry.registration.capabilities", codes)

    def test_duplicate_capabilities_are_rejected(self):
        engine = RegistryEngine()
        engine.open(request())
        response = engine.register(request(), registration(capabilities=("one", "one")))
        self.assertIn("registry.registration.duplicate_capability", {error.code for error in response.errors})

    def test_required_metadata_policy_is_enforced(self):
        engine = RegistryEngine(policy=RegistryPolicy(required_metadata_keys=("owner",)))
        engine.open(request())
        response = engine.register(request(), registration())
        self.assertEqual(response.errors[0].code, "registry.registration.required_metadata")

    def test_capacity_policy_is_enforced(self):
        engine = RegistryEngine(policy=RegistryPolicy(maximum_registrations=1))
        engine.open(request())
        engine.register(request(request_id="one"), registration())
        response = engine.register(request(request_id="two"), registration("ENG-002"))
        self.assertEqual(response.errors[0].code, "registry.registration.capacity")

    def test_invalid_policy_fails_open(self):
        response = RegistryEngine(policy=RegistryPolicy(maximum_registrations=-1)).open(request())
        self.assertEqual(response.status, ResponseStatus.FAILED)

    def test_discovery_is_filtered_and_deterministic(self):
        first = registration("ENG-002", capabilities=("runtime",))
        second = registration("ENG-001", capabilities=("runtime",))
        response = ready_engine((first, second)).discover(request(), "runtime")
        self.assertEqual(tuple(item.engine_id for item in response.registrations), ("ENG-001", "ENG-002"))

    def test_discovery_filters_availability(self):
        engine = ready_engine((registration(),))
        engine.set_availability(request(), "ENG-001", Availability.UNAVAILABLE)
        response = engine.discover(request(), availability=Availability.AVAILABLE)
        self.assertEqual(response.registrations, ())

    def test_lookup_unknown_is_explicit(self):
        response = ready_engine().lookup(request(), "ENG-999")
        self.assertEqual(response.status, ResponseStatus.REJECTED)
        self.assertEqual(response.errors[0].code, "registry.lookup.not_found")

    def test_set_availability_replaces_immutable_registration(self):
        engine = ready_engine((registration(),))
        before = engine.lookup(request(), "ENG-001").registration
        updated = engine.set_availability(request(request_id="availability"), "ENG-001", Availability.DEGRADED).registration
        self.assertEqual(before.availability, Availability.AVAILABLE)
        self.assertEqual(updated.availability, Availability.DEGRADED)

    def test_deregister_removes_registration(self):
        engine = ready_engine((registration(),))
        response = engine.deregister(request(), "ENG-001")
        self.assertEqual(response.status, ResponseStatus.SUCCEEDED)
        self.assertEqual(engine.lookup(request(request_id="lookup"), "ENG-001").status, ResponseStatus.REJECTED)

    def test_deregister_unknown_is_explicit(self):
        response = ready_engine().deregister(request(), "ENG-999")
        self.assertEqual(response.errors[0].code, "registry.deregistration.not_found")

    def test_snapshot_is_immutable_and_generation_changes(self):
        engine = RegistryEngine()
        engine.open(request())
        first = engine.snapshot(request()).snapshot
        engine.register(request(request_id="register"), registration())
        second = engine.snapshot(request(request_id="snapshot-two")).snapshot
        self.assertIsInstance(second.registrations, MappingProxyType)
        self.assertGreater(second.generation, first.generation)
        self.assertEqual(first.registrations, {})

    def test_exact_identity_dependency_resolution(self):
        engine = ready_engine((registration("ENG-001"), registration("ENG-003")))
        response = engine.resolve(request(), ("ENG-003", "ENG-001"))
        self.assertEqual(response.status, ResponseStatus.SUCCEEDED)
        self.assertEqual(tuple(response.resolution.resolved), ("ENG-003", "ENG-001"))
        self.assertEqual(engine.state, RegistryState.READY)

    def test_unavailable_dependency_degrades_registry(self):
        engine = ready_engine((registration(),))
        engine.set_availability(request(), "ENG-001", Availability.UNAVAILABLE)
        response = engine.resolve(request(request_id="resolve"), ("ENG-001",))
        self.assertEqual(response.status, ResponseStatus.FAILED)
        self.assertEqual(engine.state, RegistryState.DEGRADED)
        self.assertEqual(response.errors[0].code, "registry.resolution.unavailable")

    def test_invalid_resolution_requirements_are_rejected(self):
        response = ready_engine().resolve(request(), ())
        self.assertEqual(response.status, ResponseStatus.REJECTED)

    def test_operations_before_ready_are_rejected(self):
        engine = RegistryEngine()
        engine.open(request())
        self.assertEqual(engine.lookup(request(), "ENG-001").status, ResponseStatus.REJECTED)

    def test_close_clears_registry_and_is_terminal(self):
        engine = ready_engine((registration(),))
        response = engine.close(request())
        self.assertEqual(response.status, ResponseStatus.SUCCEEDED)
        self.assertEqual(engine.state, RegistryState.CLOSED)
        self.assertEqual(engine.lookup(request(), "ENG-001").status, ResponseStatus.REJECTED)

    def test_invalid_request_version_is_rejected(self):
        response = RegistryEngine().open(request(request_id="", contract_version="2.0.0"))
        self.assertEqual(response.status, ResponseStatus.REJECTED)
        self.assertEqual(len(response.errors), 2)

    def test_logging_and_explanations_are_emitted(self):
        log = LogStub()
        engine = ready_engine(log_sink=log)
        self.assertTrue(log.records)
        self.assertTrue(engine.explanations)

    def test_logging_failure_is_explicit(self):
        response = RegistryEngine(log_sink=LogStub(raises=True)).open(request())
        self.assertEqual(response.status, ResponseStatus.FAILED)
        self.assertIn("registry.logging.delivery_failed", {error.code for error in response.errors})

    def test_controlled_inputs_are_deterministic(self):
        one = RegistryEngine().open(request())
        two = RegistryEngine().open(request())
        self.assertEqual(one.response_id, two.response_id)

    def test_public_metadata_accepts_prior_engine_identities(self):
        items = (registration("ENG-001"), registration("ENG-002"), registration("ENG-003"))
        response = ready_engine(items).discover(request())
        self.assertEqual(tuple(item.engine_id for item in response.registrations), ("ENG-001", "ENG-002", "ENG-003"))

    def test_rule_40_has_no_concrete_engine_imports(self):
        for path in SOURCE.rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            imports = " ".join(ast.unparse(node) for node in ast.walk(tree) if isinstance(node, (ast.Import, ast.ImportFrom)))
            for forbidden in ("taskgraph_bootstrap", "taskgraph_kernel", "taskgraph_configuration", "Implementation"):
                self.assertNotIn(forbidden, imports)


if __name__ == "__main__":
    unittest.main()
