"""ENG-001 Bootstrap Engine implementation."""

from __future__ import annotations

from collections.abc import Iterable
from threading import RLock
from types import MappingProxyType
from typing import Any, Mapping

from .contracts import (
    CONTRACT_VERSION,
    ENGINE_ID,
    BootstrapConfiguration,
    BootstrapError,
    BootstrapRequest,
    BootstrapResponse,
    BootstrapState,
    ExplanationRecord,
    LogRecord,
    LogSink,
    NullLogSink,
    ResponseStatus,
    RuntimeSnapshot,
    ShutdownRequest,
    StartupCapability,
)


_ALLOWED_TRANSITIONS: Mapping[BootstrapState, frozenset[BootstrapState]] = {
    BootstrapState.CREATED: frozenset({BootstrapState.VALIDATING}),
    BootstrapState.VALIDATING: frozenset(
        {BootstrapState.LOADING, BootstrapState.FAILED}
    ),
    BootstrapState.LOADING: frozenset(
        {BootstrapState.INITIALIZING, BootstrapState.FAILED}
    ),
    BootstrapState.INITIALIZING: frozenset(
        {BootstrapState.READY, BootstrapState.FAILED}
    ),
    BootstrapState.READY: frozenset({BootstrapState.STOPPING}),
    BootstrapState.STOPPING: frozenset({BootstrapState.STOPPED}),
    BootstrapState.FAILED: frozenset(),
    BootstrapState.STOPPED: frozenset(),
}


class BootstrapEngine:
    """Establish the initial runtime lifecycle through injected contracts.

    The engine is intentionally one-shot. A failed or stopped instance is terminal;
    constructing a new instance is the safe restart mechanism.
    """

    def __init__(
        self,
        capabilities: Iterable[StartupCapability] = (),
        *,
        configuration: BootstrapConfiguration | None = None,
        log_sink: LogSink | None = None,
    ) -> None:
        self._configuration = configuration or BootstrapConfiguration()
        self._log_sink = log_sink or NullLogSink()
        self._lock = RLock()
        self._state = BootstrapState.CREATED
        self._runtime: RuntimeSnapshot | None = None
        self._explanations: list[ExplanationRecord] = []
        self._sequence = 0
        self._capabilities: dict[str, StartupCapability] = {}
        self._composition_errors: list[BootstrapError] = []
        self._compose_capabilities(capabilities)

    @property
    def state(self) -> BootstrapState:
        with self._lock:
            return self._state

    @property
    def runtime(self) -> RuntimeSnapshot | None:
        with self._lock:
            return self._runtime

    @property
    def explanations(self) -> tuple[ExplanationRecord, ...]:
        """Return an immutable view of all Bootstrap-owned explanations."""
        with self._lock:
            return tuple(self._explanations)

    def start(self, request: BootstrapRequest) -> BootstrapResponse:
        """Validate startup conditions and establish the initial runtime."""
        with self._lock:
            if self._state is not BootstrapState.CREATED:
                error = self._error(
                    "invalid_state",
                    "bootstrap.start.invalid_state",
                    f"start is not valid while Bootstrap is {self._state.value}",
                )
                explanation = self._explain(
                    request.correlation_id,
                    "startup request",
                    "rejected because Bootstrap is not in created state",
                    (f"current_state={self._state.value}",),
                    ResponseStatus.REJECTED.value,
                )
                return self._response(request, ResponseStatus.REJECTED, (error,), (explanation,))

            transition_error = self._transition(
                BootstrapState.VALIDATING, request.correlation_id
            )
            errors = list(self._validate_request(request))
            errors.extend(self._composition_errors)
            if transition_error is not None:
                errors.append(transition_error)
            if errors:
                return self._fail_start(request, errors, "startup validation failed")

            transition_error = self._transition(
                BootstrapState.LOADING, request.correlation_id
            )
            if transition_error is not None:
                return self._fail_start(request, [transition_error], "runtime loading failed")

            environment = MappingProxyType(dict(request.environment))
            capability_errors = self._validate_capabilities(request, environment)
            if capability_errors:
                return self._fail_start(
                    request, capability_errors, "startup capability validation failed"
                )

            transition_error = self._transition(
                BootstrapState.INITIALIZING, request.correlation_id
            )
            if transition_error is not None:
                return self._fail_start(
                    request, [transition_error], "runtime initialization failed"
                )

            self._runtime = RuntimeSnapshot(
                state=BootstrapState.READY,
                environment=environment,
                capability_ids=tuple(sorted(self._capabilities)),
            )
            transition_error = self._transition(
                BootstrapState.READY, request.correlation_id
            )
            if transition_error is not None:
                return self._fail_start(
                    request, [transition_error], "ready transition failed"
                )

            explanation = self._explain(
                request.correlation_id,
                "initial runtime lifecycle",
                "runtime initialized and ready for future capability registration",
                (
                    f"capabilities={','.join(sorted(self._capabilities)) or 'none'}",
                    f"contract_version={request.contract_version}",
                ),
                ResponseStatus.SUCCEEDED.value,
            )
            log_error = self._log(
                "lifecycle",
                "info",
                request.correlation_id,
                "Bootstrap runtime is ready",
                {"state": self._state.value},
            )
            if log_error is not None:
                return self._fail_start(request, [log_error], "logging contract failed")
            return self._response(
                request, ResponseStatus.SUCCEEDED, (), (explanation,), runtime=self._runtime
            )

    def stop(self, request: ShutdownRequest) -> BootstrapResponse:
        """Stop only the Bootstrap-owned lifecycle."""
        with self._lock:
            request_errors = self._validate_envelope(
                request.request_id,
                request.correlation_id,
                request.source_identity,
                request.contract_version,
            )
            if request_errors:
                explanation = self._explain(
                    request.correlation_id,
                    "shutdown request",
                    "rejected because the request envelope is invalid",
                    tuple(error.code for error in request_errors),
                    ResponseStatus.REJECTED.value,
                )
                return self._response(
                    request, ResponseStatus.REJECTED, request_errors, (explanation,)
                )
            if self._state is not BootstrapState.READY:
                error = self._error(
                    "invalid_state",
                    "bootstrap.stop.invalid_state",
                    f"stop is not valid while Bootstrap is {self._state.value}",
                )
                return self._response(request, ResponseStatus.REJECTED, (error,), ())

            errors: list[BootstrapError] = []
            for target in (BootstrapState.STOPPING, BootstrapState.STOPPED):
                transition_error = self._transition(target, request.correlation_id)
                if transition_error is not None:
                    errors.append(transition_error)
                    break
            if errors:
                return self._response(request, ResponseStatus.FAILED, errors, ())

            self._runtime = None
            explanation = self._explain(
                request.correlation_id,
                "Bootstrap lifecycle",
                "Bootstrap-owned lifecycle stopped without stopping capability providers",
                ("future_engine_responsibilities_untouched=true",),
                ResponseStatus.SUCCEEDED.value,
            )
            return self._response(
                request, ResponseStatus.SUCCEEDED, (), (explanation,), runtime=None
            )

    def _compose_capabilities(
        self, capabilities: Iterable[StartupCapability]
    ) -> None:
        for capability in capabilities:
            try:
                capability_id = capability.capability_id.strip()
            except Exception as exc:  # provider boundary protection
                self._composition_errors.append(
                    self._error(
                        "validation",
                        "bootstrap.capability.invalid_identity",
                        "capability provider did not expose a valid identity",
                        context={"exception_type": type(exc).__name__},
                    )
                )
                continue
            if not capability_id:
                self._composition_errors.append(
                    self._error(
                        "validation",
                        "bootstrap.capability.empty_identity",
                        "capability identity must not be empty",
                    )
                )
            elif capability_id in self._capabilities:
                self._composition_errors.append(
                    self._error(
                        "conflict",
                        "bootstrap.capability.duplicate",
                        f"duplicate capability identity: {capability_id}",
                    )
                )
            else:
                self._capabilities[capability_id] = capability

    def _validate_request(
        self, request: BootstrapRequest
    ) -> tuple[BootstrapError, ...]:
        errors = list(
            self._validate_envelope(
                request.request_id,
                request.correlation_id,
                request.source_identity,
                request.contract_version,
            )
        )
        if not self._configuration.allow_empty_environment and not request.environment:
            errors.append(
                self._error(
                    "validation",
                    "bootstrap.environment.empty",
                    "runtime environment must not be empty",
                )
            )
        required = self._required_capabilities(request)
        if len(required) != len(set(required)):
            errors.append(
                self._error(
                    "validation",
                    "bootstrap.required_capability.duplicate",
                    "required capability identities must be unique",
                )
            )
        return tuple(errors)

    def _validate_envelope(
        self,
        request_id: str,
        correlation_id: str,
        source_identity: str,
        contract_version: str,
    ) -> tuple[BootstrapError, ...]:
        errors: list[BootstrapError] = []
        for field_name, value in (
            ("request_id", request_id),
            ("correlation_id", correlation_id),
            ("source_identity", source_identity),
        ):
            if not isinstance(value, str) or not value.strip():
                errors.append(
                    self._error(
                        "validation",
                        f"bootstrap.envelope.{field_name}",
                        f"{field_name} must be a non-empty string",
                    )
                )
        try:
            major_text = contract_version.split(".", 1)[0]
            major = int(major_text)
        except (AttributeError, TypeError, ValueError):
            major = -1
        if major != self._configuration.supported_contract_major:
            errors.append(
                self._error(
                    "unsupported_version",
                    "bootstrap.contract.unsupported_version",
                    f"unsupported Bootstrap contract version: {contract_version!r}",
                    context={"supported_major": self._configuration.supported_contract_major},
                )
            )
        return tuple(errors)

    def _validate_capabilities(
        self, request: BootstrapRequest, environment: Mapping[str, Any]
    ) -> list[BootstrapError]:
        errors: list[BootstrapError] = []
        for capability_id in self._required_capabilities(request):
            if capability_id not in self._capabilities:
                errors.append(
                    self._error(
                        "dependency_unavailable",
                        "bootstrap.capability.required_missing",
                        f"required capability is unavailable: {capability_id}",
                        context={"capability_id": capability_id},
                    )
                )
        for capability_id in sorted(self._capabilities):
            capability = self._capabilities[capability_id]
            try:
                provider_errors = tuple(capability.validate_startup(environment))
            except Exception as exc:  # provider boundary protection
                errors.append(
                    self._error(
                        "dependency_unavailable",
                        "bootstrap.capability.validation_failed",
                        f"capability validation raised: {capability_id}",
                        context={
                            "capability_id": capability_id,
                            "exception_type": type(exc).__name__,
                        },
                    )
                )
                continue
            for error in provider_errors:
                if not isinstance(error, BootstrapError):
                    errors.append(
                        self._error(
                            "validation",
                            "bootstrap.capability.invalid_error",
                            f"capability returned a non-contract error: {capability_id}",
                        )
                    )
                else:
                    errors.append(error)
        return errors

    def _required_capabilities(self, request: BootstrapRequest) -> tuple[str, ...]:
        return self._configuration.required_capabilities + request.required_capabilities

    def _transition(
        self, target: BootstrapState, correlation_id: str
    ) -> BootstrapError | None:
        source = self._state
        if target not in _ALLOWED_TRANSITIONS[source]:
            return self._error(
                "invalid_state",
                "bootstrap.lifecycle.invalid_transition",
                f"invalid Bootstrap transition: {source.value} -> {target.value}",
            )
        log_error = self._log(
            "lifecycle",
            "info",
            correlation_id,
            f"Bootstrap transitioning from {source.value} to {target.value}",
            {"source": source.value, "target": target.value},
        )
        if log_error is not None:
            return log_error
        self._state = target
        self._explain(
            correlation_id,
            "Bootstrap lifecycle",
            f"transitioned from {source.value} to {target.value}",
            (f"source={source.value}", f"target={target.value}"),
            "in_progress" if target not in {BootstrapState.READY, BootstrapState.STOPPED} else "succeeded",
        )
        return None

    def _fail_start(
        self,
        request: BootstrapRequest,
        errors: Iterable[BootstrapError],
        decision: str,
    ) -> BootstrapResponse:
        collected = list(errors)
        if self._state not in {BootstrapState.FAILED, BootstrapState.READY}:
            transition_error = self._transition(
                BootstrapState.FAILED, request.correlation_id
            )
            if transition_error is not None:
                collected.append(transition_error)
                # Failure is terminal even when the logging dependency prevents
                # the normal transition record from being delivered.
                self._state = BootstrapState.FAILED
        self._runtime = None
        explanation = self._explain(
            request.correlation_id,
            "startup request",
            decision,
            tuple(error.code for error in collected),
            ResponseStatus.FAILED.value,
        )
        return self._response(
            request, ResponseStatus.FAILED, tuple(collected), (explanation,)
        )

    def _response(
        self,
        request: BootstrapRequest | ShutdownRequest,
        status: ResponseStatus,
        errors: Iterable[BootstrapError],
        explanations: Iterable[ExplanationRecord],
        *,
        runtime: RuntimeSnapshot | None = None,
    ) -> BootstrapResponse:
        self._sequence += 1
        return BootstrapResponse(
            response_id=f"{request.correlation_id}:response:{self._sequence}",
            request_id=request.request_id,
            correlation_id=request.correlation_id,
            status=status,
            state=self._state,
            runtime=runtime,
            errors=tuple(errors),
            explanations=tuple(explanations),
        )

    def _explain(
        self,
        correlation_id: str,
        subject: str,
        decision: str,
        facts: tuple[str, ...],
        status: str,
    ) -> ExplanationRecord:
        self._sequence += 1
        explanation = ExplanationRecord(
            explanation_id=f"{correlation_id}:explanation:{self._sequence}",
            engine_id=ENGINE_ID,
            correlation_id=correlation_id,
            subject=subject,
            decision=decision,
            supporting_facts=facts,
            status=status,
            metadata={"sequence": self._sequence},
        )
        self._explanations.append(explanation)
        return explanation

    def _log(
        self,
        category: str,
        severity: str,
        correlation_id: str,
        message: str,
        metadata: Mapping[str, Any],
    ) -> BootstrapError | None:
        try:
            self._log_sink.record(
                LogRecord(
                    engine_id=ENGINE_ID,
                    category=category,
                    severity=severity,
                    correlation_id=correlation_id,
                    message=message,
                    metadata=metadata,
                )
            )
        except Exception as exc:  # logging contract boundary protection
            return self._error(
                "dependency_unavailable",
                "bootstrap.logging.delivery_failed",
                "logging capability rejected a Bootstrap record",
                context={"exception_type": type(exc).__name__},
            )
        return None

    @staticmethod
    def _error(
        category: str,
        code: str,
        message: str,
        *,
        recoverable: bool = False,
        context: Mapping[str, Any] | None = None,
    ) -> BootstrapError:
        return BootstrapError(
            category=category,
            code=code,
            message=message,
            recoverable=recoverable,
            context=context or {},
        )
