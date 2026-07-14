"""Deterministic ENG-003 Configuration Engine."""

from __future__ import annotations

from threading import RLock
from typing import Any, Mapping

from .contracts import (
    CONTRACT_ID,
    ENGINE_ID,
    ConfigurationError,
    ConfigurationRequest,
    ConfigurationResponse,
    ConfigurationSchema,
    ConfigurationSource,
    ConfigurationState,
    ExplanationRecord,
    LogRecord,
    LogSink,
    NullLogSink,
    ResponseStatus,
    RuntimeConfiguration,
    SourceLoadRequest,
    SourceLoadResult,
    ValueKind,
)

_TRANSITIONS = {
    ConfigurationState.UNLOADED: {ConfigurationState.LOADING, ConfigurationState.STOPPING},
    ConfigurationState.LOADING: {ConfigurationState.VALIDATING, ConfigurationState.INVALID},
    ConfigurationState.RELOADING: {ConfigurationState.VALIDATING, ConfigurationState.INVALID},
    ConfigurationState.VALIDATING: {ConfigurationState.AVAILABLE, ConfigurationState.INVALID},
    ConfigurationState.AVAILABLE: {ConfigurationState.RELOADING, ConfigurationState.STOPPING},
    ConfigurationState.INVALID: {ConfigurationState.STOPPING},
    ConfigurationState.STOPPING: {ConfigurationState.STOPPED},
    ConfigurationState.STOPPED: set(),
}


class ConfigurationEngine:
    """Load, validate, and expose immutable runtime configuration."""

    def __init__(self, source: ConfigurationSource, schema: ConfigurationSchema, *, log_sink: LogSink | None = None) -> None:
        self._source = source
        self._schema = schema
        self._log_sink = log_sink or NullLogSink()
        self._state = ConfigurationState.UNLOADED
        self._runtime: RuntimeConfiguration | None = None
        self._revision = 0
        self._sequence = 0
        self._explanations: list[ExplanationRecord] = []
        self._lock = RLock()

    @property
    def state(self) -> ConfigurationState:
        with self._lock:
            return self._state

    @property
    def runtime_configuration(self) -> RuntimeConfiguration | None:
        with self._lock:
            return self._runtime

    @property
    def explanations(self) -> tuple[ExplanationRecord, ...]:
        with self._lock:
            return tuple(self._explanations)

    def load(self, request: ConfigurationRequest) -> ConfigurationResponse:
        with self._lock:
            errors = self._validate_request(request)
            if errors:
                return self._response(request, ResponseStatus.REJECTED, errors)
            if self._state is not ConfigurationState.UNLOADED:
                return self._invalid_state(request, "load")
            return self._perform_load(request, ConfigurationState.LOADING)

    def reload(self, request: ConfigurationRequest) -> ConfigurationResponse:
        with self._lock:
            errors = self._validate_request(request)
            if errors:
                return self._response(request, ResponseStatus.REJECTED, errors)
            if self._state is not ConfigurationState.AVAILABLE:
                return self._invalid_state(request, "reload")
            return self._perform_load(request, ConfigurationState.RELOADING)

    def get(self, request: ConfigurationRequest) -> ConfigurationResponse:
        with self._lock:
            errors = self._validate_request(request)
            if errors:
                return self._response(request, ResponseStatus.REJECTED, errors)
            if self._state is not ConfigurationState.AVAILABLE or self._runtime is None:
                return self._invalid_state(request, "get")
            explanation = self._explain(request, "runtime settings", "returned validated immutable runtime configuration", (f"revision={self._runtime.revision}",), "succeeded")
            return self._response(request, ResponseStatus.SUCCEEDED, (), self._runtime, (explanation,))

    def shutdown(self, request: ConfigurationRequest) -> ConfigurationResponse:
        with self._lock:
            errors = self._validate_request(request)
            if errors:
                return self._response(request, ResponseStatus.REJECTED, errors)
            if self._state not in {ConfigurationState.UNLOADED, ConfigurationState.AVAILABLE, ConfigurationState.INVALID}:
                return self._invalid_state(request, "shutdown")
            error = self._transition(ConfigurationState.STOPPING, request)
            if error is None:
                error = self._transition(ConfigurationState.STOPPED, request)
            if error is not None:
                return self._response(request, ResponseStatus.FAILED, (error,))
            self._runtime = None
            explanation = self._explain(request, "configuration lifecycle", "released owned runtime configuration", ("state=stopped",), "succeeded")
            return self._response(request, ResponseStatus.SUCCEEDED, (), None, (explanation,))

    def _perform_load(self, request: ConfigurationRequest, loading_state: ConfigurationState) -> ConfigurationResponse:
        error = self._transition(loading_state, request)
        if error is not None:
            self._state = ConfigurationState.INVALID
            return self._response(request, ResponseStatus.FAILED, (error,))
        try:
            result = self._source.load(SourceLoadRequest(request.request_id, request.correlation_id, request.source_identity, request.metadata))
        except Exception as exc:
            return self._fail(request, "dependency_unavailable", "configuration.source.exception", "configuration source raised during load", {"exception_type": type(exc).__name__})
        if not isinstance(result, SourceLoadResult):
            return self._fail(request, "validation", "configuration.source.invalid_result", "configuration source returned a non-contract result")
        if not result.succeeded:
            return self._fail(request, "dependency_unavailable", "configuration.source.failed", "configuration source did not provide settings", {"source_errors": result.errors})
        error = self._transition(ConfigurationState.VALIDATING, request)
        if error is not None:
            return self._fail_with(request, error)
        validation_errors = self._validate_settings(request, result.settings)
        if validation_errors:
            self._transition(ConfigurationState.INVALID, request)
            explanation = self._explain(request, "configuration validation", "configuration was rejected", tuple(item.code for item in validation_errors), "failed")
            return self._response(request, ResponseStatus.FAILED, validation_errors, None, (explanation,))
        self._revision += 1
        self._runtime = RuntimeConfiguration(
            configuration_id=f"{request.correlation_id}:configuration:{self._revision}",
            revision=self._revision,
            values=result.settings,
            provenance=result.provenance,
            correlation_id=request.correlation_id,
        )
        error = self._transition(ConfigurationState.AVAILABLE, request)
        if error is not None:
            self._runtime = None
            return self._fail_with(request, error)
        explanation = self._explain(request, "configuration validation", "configuration is validated and available", (f"revision={self._revision}", f"keys={len(result.settings)}"), "succeeded")
        return self._response(request, ResponseStatus.SUCCEEDED, (), self._runtime, (explanation,))

    def _validate_request(self, request: ConfigurationRequest) -> tuple[ConfigurationError, ...]:
        errors: list[ConfigurationError] = []
        for field_name in ("request_id", "correlation_id", "source_identity", "target_capability", "expectation"):
            value = getattr(request, field_name)
            if not isinstance(value, str) or not value.strip():
                errors.append(self._error(request, "validation", f"configuration.envelope.{field_name}", f"{field_name} must be a non-empty string"))
        if request.contract_id != CONTRACT_ID:
            errors.append(self._error(request, "validation", "configuration.contract.identity", "unsupported configuration contract identity"))
        try:
            major = int(request.contract_version.split(".", 1)[0])
        except (AttributeError, TypeError, ValueError):
            major = -1
        if major != 1:
            errors.append(self._error(request, "unsupported_version", "configuration.contract.version", "unsupported configuration contract version"))
        return tuple(errors)

    def _validate_settings(self, request: ConfigurationRequest, settings: Mapping[str, Any]) -> tuple[ConfigurationError, ...]:
        errors: list[ConfigurationError] = []
        if not isinstance(settings, Mapping):
            return (self._error(request, "validation", "configuration.settings.not_mapping", "settings must be a mapping"),)
        for key in settings:
            if not isinstance(key, str) or not key.strip():
                errors.append(self._error(request, "validation", "configuration.settings.invalid_key", "setting keys must be non-empty strings"))
        for key, value in settings.items():
            if not self._is_immutable_value(value):
                errors.append(self._error(request, "validation", "configuration.settings.unsupported_value", f"setting cannot be represented immutably: {key}", {"key": str(key), "value_type": type(value).__name__}))
        for key, rule in self._schema.rules.items():
            if rule.required and key not in settings:
                errors.append(self._error(request, "validation", "configuration.settings.required_missing", f"required setting is missing: {key}", {"key": key}))
            elif key in settings and not self._matches(settings[key], rule.kind, rule.allow_none):
                errors.append(self._error(request, "validation", "configuration.settings.invalid_type", f"setting has invalid type: {key}", {"key": key, "expected": rule.kind.value}))
        if not self._schema.allow_unknown_keys:
            for key in sorted(set(settings) - set(self._schema.rules)):
                errors.append(self._error(request, "validation", "configuration.settings.unknown_key", f"setting is not declared by the schema: {key}", {"key": key}))
        return tuple(errors)

    @classmethod
    def _is_immutable_value(cls, value: Any) -> bool:
        if value is None or isinstance(value, (str, int, float, bool, bytes)):
            return True
        if isinstance(value, Mapping):
            return all(isinstance(key, str) and cls._is_immutable_value(item) for key, item in value.items())
        if isinstance(value, (list, tuple, set, frozenset)):
            return all(cls._is_immutable_value(item) for item in value)
        return False

    @staticmethod
    def _matches(value: Any, kind: ValueKind, allow_none: bool) -> bool:
        if value is None:
            return allow_none
        if kind is ValueKind.ANY:
            return True
        if kind is ValueKind.STRING:
            return isinstance(value, str)
        if kind is ValueKind.INTEGER:
            return isinstance(value, int) and not isinstance(value, bool)
        if kind is ValueKind.NUMBER:
            return isinstance(value, (int, float)) and not isinstance(value, bool)
        if kind is ValueKind.BOOLEAN:
            return isinstance(value, bool)
        if kind is ValueKind.MAPPING:
            return isinstance(value, Mapping)
        if kind is ValueKind.SEQUENCE:
            return isinstance(value, (list, tuple))
        return False

    def _transition(self, target: ConfigurationState, request: ConfigurationRequest) -> ConfigurationError | None:
        source = self._state
        if target not in _TRANSITIONS[source]:
            return self._error(request, "invalid_state", "configuration.lifecycle.invalid_transition", f"invalid transition: {source.value} -> {target.value}")
        log_error = self._log(request, "lifecycle", "info", f"Configuration transitioning from {source.value} to {target.value}", {"source": source.value, "target": target.value})
        if log_error is not None:
            return log_error
        self._state = target
        self._explain(request, "configuration lifecycle", f"transitioned from {source.value} to {target.value}", (f"source={source.value}", f"target={target.value}"), "in_progress")
        return None

    def _fail(self, request: ConfigurationRequest, category: str, code: str, message: str, context: Mapping[str, Any] | None = None) -> ConfigurationResponse:
        return self._fail_with(request, self._error(request, category, code, message, context))

    def _fail_with(self, request: ConfigurationRequest, error: ConfigurationError) -> ConfigurationResponse:
        if self._state in {ConfigurationState.LOADING, ConfigurationState.RELOADING, ConfigurationState.VALIDATING}:
            transition_error = self._transition(ConfigurationState.INVALID, request)
            if transition_error is not None:
                self._state = ConfigurationState.INVALID
                return self._response(request, ResponseStatus.FAILED, (error, transition_error))
        explanation = self._explain(request, "configuration operation", "configuration operation failed", (error.code,), "failed")
        return self._response(request, ResponseStatus.FAILED, (error,), None, (explanation,))

    def _invalid_state(self, request: ConfigurationRequest, operation: str) -> ConfigurationResponse:
        error = self._error(request, "invalid_state", f"configuration.{operation}.invalid_state", f"{operation} is not valid while Configuration is {self._state.value}")
        explanation = self._explain(request, f"configuration {operation}", "request rejected by lifecycle state", (f"state={self._state.value}",), "rejected")
        return self._response(request, ResponseStatus.REJECTED, (error,), None, (explanation,))

    def _response(self, request: ConfigurationRequest, status: ResponseStatus, errors: tuple[ConfigurationError, ...] | list[ConfigurationError], runtime: RuntimeConfiguration | None = None, explanations: tuple[ExplanationRecord, ...] = ()) -> ConfigurationResponse:
        collected = list(errors)
        log_error = self._log(
            request,
            "operation_outcome",
            "info" if status is ResponseStatus.SUCCEEDED else "warning",
            f"Configuration request completed with status {status.value}",
            {"status": status.value, "state": self._state.value},
        )
        if log_error is not None and not any(item.code == log_error.code for item in collected):
            collected.append(log_error)
            status = ResponseStatus.FAILED
        self._sequence += 1
        return ConfigurationResponse(
            response_id=f"{request.correlation_id}:configuration-response:{self._sequence}",
            request_id=request.request_id,
            correlation_id=request.correlation_id,
            status=status,
            state=self._state,
            runtime_configuration=runtime,
            errors=tuple(collected),
            explanations=explanations,
            metadata={"terminal": True},
        )

    def _explain(self, request: ConfigurationRequest, subject: str, decision: str, facts: tuple[str, ...], status: str) -> ExplanationRecord:
        self._sequence += 1
        record = ExplanationRecord(f"{request.correlation_id}:configuration-explanation:{self._sequence}", ENGINE_ID, request.correlation_id, subject, decision, facts, status, {"request_id": request.request_id})
        self._explanations.append(record)
        return record

    def _log(self, request: ConfigurationRequest, category: str, severity: str, message: str, metadata: Mapping[str, Any]) -> ConfigurationError | None:
        try:
            self._log_sink.record(LogRecord(ENGINE_ID, category, severity, request.correlation_id, message, metadata))
        except Exception as exc:
            return self._error(request, "dependency_unavailable", "configuration.logging.delivery_failed", "logging capability rejected a record", {"exception_type": type(exc).__name__})
        return None

    @staticmethod
    def _error(request: ConfigurationRequest, category: str, code: str, message: str, context: Mapping[str, Any] | None = None) -> ConfigurationError:
        return ConfigurationError(category, code, message, request.request_id, request.correlation_id, False, None, context or {})
