"""Thread-safe authoritative metadata Registry for ENG-004."""

from __future__ import annotations

from dataclasses import replace
from threading import RLock
from typing import Any, Mapping

from .contracts import (
    CONTRACT_ID, ENGINE_ID, Availability, DependencyResolution, EngineRegistration,
    ExplanationRecord, LogRecord, LogSink, NullLogSink, RegistryError, RegistryPolicy,
    RegistryRequest, RegistryResponse, RegistrySnapshot, RegistryState, ResponseStatus,
)

_ACTIVE = {RegistryState.ACCEPTING_REGISTRATIONS, RegistryState.READY}
_TRANSITIONS = {
    RegistryState.EMPTY: {RegistryState.ACCEPTING_REGISTRATIONS, RegistryState.CLOSED},
    RegistryState.ACCEPTING_REGISTRATIONS: {RegistryState.READY, RegistryState.CLOSED},
    RegistryState.READY: {RegistryState.RESOLVING, RegistryState.CLOSED},
    RegistryState.RESOLVING: {RegistryState.READY, RegistryState.DEGRADED},
    RegistryState.DEGRADED: {RegistryState.CLOSED},
    RegistryState.CLOSED: set(),
}


class RegistryEngine:
    """Maintain immutable registration metadata; never Engine instances."""

    def __init__(self, *, policy: RegistryPolicy | None = None, log_sink: LogSink | None = None) -> None:
        self._policy = policy or RegistryPolicy()
        self._log_sink = log_sink or NullLogSink()
        self._state = RegistryState.EMPTY
        self._registrations: dict[str, EngineRegistration] = {}
        self._generation = 0
        self._sequence = 0
        self._explanations: list[ExplanationRecord] = []
        self._lock = RLock()

    @property
    def state(self) -> RegistryState:
        with self._lock:
            return self._state

    @property
    def explanations(self) -> tuple[ExplanationRecord, ...]:
        with self._lock:
            return tuple(self._explanations)

    def open(self, request: RegistryRequest) -> RegistryResponse:
        with self._lock:
            errors = self._validate_request(request)
            if errors:
                return self._response(request, ResponseStatus.REJECTED, errors)
            if self._state is not RegistryState.EMPTY:
                return self._invalid_state(request, "open")
            if self._policy.maximum_registrations is not None and self._policy.maximum_registrations < 0:
                return self._failure(request, "validation", "registry.policy.invalid_limit", "maximum_registrations must not be negative")
            error = self._transition(RegistryState.ACCEPTING_REGISTRATIONS, request)
            return self._transition_response(request, error, "Registry is accepting registrations")

    def register(self, request: RegistryRequest, registration: EngineRegistration) -> RegistryResponse:
        with self._lock:
            errors = list(self._validate_request(request)) + list(self._validate_registration(request, registration))
            if errors:
                return self._response(request, ResponseStatus.REJECTED, errors)
            if self._state not in _ACTIVE:
                return self._invalid_state(request, "register")
            if registration.engine_id in self._registrations:
                return self._rejection(request, "conflict", "registry.registration.duplicate", f"engine is already registered: {registration.engine_id}")
            limit = self._policy.maximum_registrations
            if limit is not None and len(self._registrations) >= limit:
                return self._rejection(request, "conflict", "registry.registration.capacity", "registry registration limit reached")
            self._registrations[registration.engine_id] = registration
            self._generation += 1
            explanation = self._explain(request, "Engine registration", f"registered metadata for {registration.engine_id}", (f"contract={registration.contract_id}",), "succeeded")
            return self._response(request, ResponseStatus.SUCCEEDED, (), registration=registration, explanations=(explanation,))

    def mark_ready(self, request: RegistryRequest) -> RegistryResponse:
        with self._lock:
            errors = self._validate_request(request)
            if errors:
                return self._response(request, ResponseStatus.REJECTED, errors)
            if self._state is not RegistryState.ACCEPTING_REGISTRATIONS:
                return self._invalid_state(request, "mark_ready")
            error = self._transition(RegistryState.READY, request)
            return self._transition_response(request, error, "Registry is ready for discovery and resolution")

    def lookup(self, request: RegistryRequest, engine_id: str) -> RegistryResponse:
        with self._lock:
            errors = self._validate_request(request)
            if errors:
                return self._response(request, ResponseStatus.REJECTED, errors)
            if self._state is not RegistryState.READY:
                return self._invalid_state(request, "lookup")
            if not isinstance(engine_id, str) or not engine_id.strip():
                return self._rejection(request, "validation", "registry.lookup.invalid_identity", "lookup engine_id must be non-empty")
            registration = self._registrations.get(engine_id)
            if registration is None:
                return self._rejection(request, "dependency_unavailable", "registry.lookup.not_found", f"engine is not registered: {engine_id}")
            return self._response(request, ResponseStatus.SUCCEEDED, (), registration=registration)

    def discover(self, request: RegistryRequest, capability: str | None = None, availability: Availability | None = None) -> RegistryResponse:
        with self._lock:
            errors = self._validate_request(request)
            if errors:
                return self._response(request, ResponseStatus.REJECTED, errors)
            if self._state is not RegistryState.READY:
                return self._invalid_state(request, "discover")
            if capability is not None and (not isinstance(capability, str) or not capability.strip()):
                return self._rejection(request, "validation", "registry.discovery.invalid_capability", "capability filter must be non-empty")
            matches = tuple(reg for _, reg in sorted(self._registrations.items()) if (capability is None or capability in reg.capabilities) and (availability is None or availability is reg.availability))
            return self._response(request, ResponseStatus.SUCCEEDED, (), registrations=matches)

    def resolve(self, request: RegistryRequest, engine_ids: tuple[str, ...]) -> RegistryResponse:
        with self._lock:
            errors = list(self._validate_request(request))
            if not engine_ids or any(not isinstance(item, str) or not item.strip() for item in engine_ids):
                errors.append(self._error(request, "validation", "registry.resolution.invalid_requirements", "resolution requires non-empty Engine identities"))
            if len(engine_ids) != len(set(engine_ids)):
                errors.append(self._error(request, "validation", "registry.resolution.duplicate_requirement", "dependency identities must be unique"))
            if errors:
                return self._response(request, ResponseStatus.REJECTED, errors)
            if self._state is not RegistryState.READY:
                return self._invalid_state(request, "resolve")
            error = self._transition(RegistryState.RESOLVING, request)
            if error is not None:
                return self._response(request, ResponseStatus.FAILED, (error,))
            missing = tuple(item for item in engine_ids if item not in self._registrations or self._registrations[item].availability is not Availability.AVAILABLE)
            if missing:
                transition_error = self._transition(RegistryState.DEGRADED, request)
                collected = [self._error(request, "dependency_unavailable", "registry.resolution.unavailable", "one or more dependencies are unavailable", {"engine_ids": missing})]
                if transition_error is not None:
                    collected.append(transition_error)
                return self._response(request, ResponseStatus.FAILED, collected)
            resolved = {item: self._registrations[item] for item in engine_ids}
            resolution = DependencyResolution(f"{request.correlation_id}:resolution:{self._generation}", tuple(engine_ids), resolved, request.correlation_id)
            error = self._transition(RegistryState.READY, request)
            if error is not None:
                return self._response(request, ResponseStatus.FAILED, (error,))
            explanation = self._explain(request, "Dependency resolution", "resolved exact registered Engine identities", tuple(engine_ids), "succeeded")
            return self._response(request, ResponseStatus.SUCCEEDED, (), resolution=resolution, explanations=(explanation,))

    def set_availability(self, request: RegistryRequest, engine_id: str, availability: Availability) -> RegistryResponse:
        with self._lock:
            errors = self._validate_request(request)
            if errors:
                return self._response(request, ResponseStatus.REJECTED, errors)
            if self._state not in _ACTIVE:
                return self._invalid_state(request, "set_availability")
            registration = self._registrations.get(engine_id)
            if registration is None:
                return self._rejection(request, "dependency_unavailable", "registry.availability.not_found", f"engine is not registered: {engine_id}")
            if not isinstance(availability, Availability):
                return self._rejection(request, "validation", "registry.availability.invalid", "availability must use the Registry contract")
            updated = replace(registration, availability=availability)
            self._registrations[engine_id] = updated
            self._generation += 1
            explanation = self._explain(request, "Engine availability", f"updated availability for {engine_id}", (f"availability={availability.value}",), "succeeded")
            return self._response(request, ResponseStatus.SUCCEEDED, (), registration=updated, explanations=(explanation,))

    def deregister(self, request: RegistryRequest, engine_id: str) -> RegistryResponse:
        with self._lock:
            errors = self._validate_request(request)
            if errors:
                return self._response(request, ResponseStatus.REJECTED, errors)
            if self._state not in _ACTIVE:
                return self._invalid_state(request, "deregister")
            registration = self._registrations.get(engine_id)
            if registration is None:
                return self._rejection(request, "dependency_unavailable", "registry.deregistration.not_found", f"engine is not registered: {engine_id}")
            del self._registrations[engine_id]
            self._generation += 1
            explanation = self._explain(request, "Engine deregistration", f"removed registration metadata for {engine_id}", (), "succeeded")
            return self._response(request, ResponseStatus.SUCCEEDED, (), registration=registration, explanations=(explanation,))

    def snapshot(self, request: RegistryRequest) -> RegistryResponse:
        with self._lock:
            errors = self._validate_request(request)
            if errors:
                return self._response(request, ResponseStatus.REJECTED, errors)
            if self._state not in _ACTIVE | {RegistryState.DEGRADED}:
                return self._invalid_state(request, "snapshot")
            snapshot = RegistrySnapshot(f"{request.correlation_id}:registry-snapshot:{self._generation}", self._generation, self._state, self._registrations, request.correlation_id)
            return self._response(request, ResponseStatus.SUCCEEDED, (), snapshot=snapshot)

    def close(self, request: RegistryRequest) -> RegistryResponse:
        with self._lock:
            errors = self._validate_request(request)
            if errors:
                return self._response(request, ResponseStatus.REJECTED, errors)
            if self._state not in {RegistryState.EMPTY, RegistryState.ACCEPTING_REGISTRATIONS, RegistryState.READY, RegistryState.DEGRADED}:
                return self._invalid_state(request, "close")
            error = self._transition(RegistryState.CLOSED, request)
            if error is not None:
                return self._response(request, ResponseStatus.FAILED, (error,))
            self._registrations.clear()
            self._generation += 1
            return self._response(request, ResponseStatus.SUCCEEDED, ())

    def _validate_request(self, request: RegistryRequest) -> tuple[RegistryError, ...]:
        errors = []
        for name in ("request_id", "correlation_id", "source_identity", "target_capability", "expectation"):
            value = getattr(request, name)
            if not isinstance(value, str) or not value.strip():
                errors.append(self._error(request, "validation", f"registry.envelope.{name}", f"{name} must be a non-empty string"))
        if request.contract_id != CONTRACT_ID:
            errors.append(self._error(request, "validation", "registry.contract.identity", "unsupported Registry contract identity"))
        try:
            major = int(request.contract_version.split(".", 1)[0])
        except (AttributeError, TypeError, ValueError):
            major = -1
        if major != 1:
            errors.append(self._error(request, "unsupported_version", "registry.contract.version", "unsupported Registry contract version"))
        return tuple(errors)

    def _validate_registration(self, request: RegistryRequest, registration: EngineRegistration) -> tuple[RegistryError, ...]:
        if not isinstance(registration, EngineRegistration):
            return (self._error(request, "validation", "registry.registration.invalid_contract", "registration must use the Registry contract"),)
        errors = []
        for name in ("engine_id", "display_name", "contract_id", "contract_version"):
            value = getattr(registration, name)
            if not isinstance(value, str) or not value.strip():
                errors.append(self._error(request, "validation", f"registry.registration.{name}", f"{name} must be a non-empty string"))
        if not registration.engine_id.startswith("ENG-"):
            errors.append(self._error(request, "validation", "registry.registration.engine_identity", "engine_id must use the approved ENG identity form"))
        if not registration.capabilities or any(not isinstance(item, str) or not item.strip() for item in registration.capabilities):
            errors.append(self._error(request, "validation", "registry.registration.capabilities", "at least one non-empty capability is required"))
        if len(registration.capabilities) != len(set(registration.capabilities)):
            errors.append(self._error(request, "validation", "registry.registration.duplicate_capability", "capabilities must be unique"))
        try:
            int(registration.contract_version.split(".", 1)[0])
        except (AttributeError, TypeError, ValueError):
            errors.append(self._error(request, "validation", "registry.registration.contract_version", "Engine contract version must be semantic-major compatible text"))
        for key in self._policy.required_metadata_keys:
            if key not in registration.metadata:
                errors.append(self._error(request, "validation", "registry.registration.required_metadata", f"required registration metadata is missing: {key}", {"key": key}))
        return tuple(errors)

    def _transition(self, target: RegistryState, request: RegistryRequest) -> RegistryError | None:
        source = self._state
        if target not in _TRANSITIONS[source]:
            return self._error(request, "invalid_state", "registry.lifecycle.invalid_transition", f"invalid Registry transition: {source.value} -> {target.value}")
        error = self._log(request, "lifecycle", "info", f"Registry transitioning from {source.value} to {target.value}", {"source": source.value, "target": target.value})
        if error is not None:
            return error
        self._state = target
        self._explain(request, "Registry lifecycle", f"transitioned from {source.value} to {target.value}", (f"source={source.value}", f"target={target.value}"), "in_progress")
        return None

    def _transition_response(self, request: RegistryRequest, error: RegistryError | None, decision: str) -> RegistryResponse:
        if error is not None:
            return self._response(request, ResponseStatus.FAILED, (error,))
        explanation = self._explain(request, "Registry lifecycle", decision, (f"state={self._state.value}",), "succeeded")
        return self._response(request, ResponseStatus.SUCCEEDED, (), explanations=(explanation,))

    def _invalid_state(self, request: RegistryRequest, operation: str) -> RegistryResponse:
        return self._rejection(request, "invalid_state", f"registry.{operation}.invalid_state", f"{operation} is not valid while Registry is {self._state.value}")

    def _rejection(self, request: RegistryRequest, category: str, code: str, message: str) -> RegistryResponse:
        error = self._error(request, category, code, message)
        explanation = self._explain(request, "Registry request", message, (code,), "rejected")
        return self._response(request, ResponseStatus.REJECTED, (error,), explanations=(explanation,))

    def _failure(self, request: RegistryRequest, category: str, code: str, message: str) -> RegistryResponse:
        return self._response(request, ResponseStatus.FAILED, (self._error(request, category, code, message),))

    def _response(self, request: RegistryRequest, status: ResponseStatus, errors: tuple[RegistryError, ...] | list[RegistryError], *, registration: EngineRegistration | None = None, registrations: tuple[EngineRegistration, ...] = (), snapshot: RegistrySnapshot | None = None, resolution: DependencyResolution | None = None, explanations: tuple[ExplanationRecord, ...] = ()) -> RegistryResponse:
        collected = list(errors)
        log_error = self._log(request, "operation_outcome", "info" if status is ResponseStatus.SUCCEEDED else "warning", f"Registry request completed with status {status.value}", {"status": status.value, "state": self._state.value})
        if log_error is not None and not any(item.code == log_error.code for item in collected):
            collected.append(log_error)
            status = ResponseStatus.FAILED
        self._sequence += 1
        return RegistryResponse(f"{request.correlation_id}:registry-response:{self._sequence}", request.request_id, request.correlation_id, status, self._state, registration, registrations, snapshot, resolution, tuple(collected), explanations, {"terminal": True})

    def _explain(self, request: RegistryRequest, subject: str, decision: str, facts: tuple[str, ...], status: str) -> ExplanationRecord:
        self._sequence += 1
        record = ExplanationRecord(f"{request.correlation_id}:registry-explanation:{self._sequence}", ENGINE_ID, request.correlation_id, subject, decision, facts, status, {"request_id": request.request_id})
        self._explanations.append(record)
        return record

    def _log(self, request: RegistryRequest, category: str, severity: str, message: str, metadata: Mapping[str, Any]) -> RegistryError | None:
        try:
            self._log_sink.record(LogRecord(ENGINE_ID, category, severity, request.correlation_id, message, metadata))
        except Exception as exc:
            return self._error(request, "dependency_unavailable", "registry.logging.delivery_failed", "logging capability rejected a Registry record", {"exception_type": type(exc).__name__})
        return None

    @staticmethod
    def _error(request: RegistryRequest, category: str, code: str, message: str, context: Mapping[str, Any] | None = None) -> RegistryError:
        return RegistryError(category, code, message, request.request_id, request.correlation_id, False, context or {})
