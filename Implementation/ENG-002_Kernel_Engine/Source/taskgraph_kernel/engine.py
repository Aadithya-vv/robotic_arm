"""ENG-002 Kernel Engine implementation."""

from __future__ import annotations

from collections.abc import Iterable
from threading import RLock
from typing import Any, Mapping

from .contracts import (
    ENGINE_ID,
    BootstrapReadinessProvider,
    CoordinationRequest,
    ExplanationRecord,
    KernelConfiguration,
    KernelError,
    KernelResponse,
    KernelStartRequest,
    KernelState,
    KernelStopRequest,
    LogRecord,
    LogSink,
    ManagedParticipant,
    NullLogSink,
    ParticipantResult,
    ParticipantState,
    ResponseStatus,
    RuntimeSnapshot,
)


_ALLOWED_TRANSITIONS: Mapping[KernelState, frozenset[KernelState]] = {
    KernelState.CREATED: frozenset({KernelState.STARTING}),
    KernelState.STARTING: frozenset({KernelState.RUNNING, KernelState.FAILED}),
    KernelState.RUNNING: frozenset({KernelState.STOPPING, KernelState.FAILED}),
    KernelState.STOPPING: frozenset({KernelState.STOPPED, KernelState.FAILED}),
    KernelState.STOPPED: frozenset(),
    KernelState.FAILED: frozenset(),
}


class KernelEngine:
    """Coordinate runtime participants through injected public contracts."""

    def __init__(
        self,
        bootstrap: BootstrapReadinessProvider,
        participants: Iterable[ManagedParticipant] = (),
        *,
        configuration: KernelConfiguration | None = None,
        log_sink: LogSink | None = None,
    ) -> None:
        self._bootstrap = bootstrap
        self._configuration = configuration or KernelConfiguration()
        self._log_sink = log_sink or NullLogSink()
        self._lock = RLock()
        self._state = KernelState.CREATED
        self._runtime: RuntimeSnapshot | None = None
        self._generation = 0
        self._sequence = 0
        self._explanations: list[ExplanationRecord] = []
        self._participants: dict[str, ManagedParticipant] = {}
        self._participant_states: dict[str, ParticipantState] = {}
        self._started_order: list[str] = []
        self._composition_errors: list[KernelError] = []
        self._compose(participants)

    @property
    def state(self) -> KernelState:
        with self._lock:
            return self._state

    @property
    def runtime(self) -> RuntimeSnapshot | None:
        with self._lock:
            return self._runtime

    @property
    def explanations(self) -> tuple[ExplanationRecord, ...]:
        with self._lock:
            return tuple(self._explanations)

    def start(self, request: KernelStartRequest) -> KernelResponse:
        with self._lock:
            if self._state is not KernelState.CREATED:
                return self._reject_state(request, "start")

            transition_error = self._transition(KernelState.STARTING, request.correlation_id)
            errors = list(self._validate_envelope(request))
            errors.extend(self._composition_errors)
            errors.extend(self._validate_configuration(request))
            if transition_error is not None:
                errors.append(transition_error)
            if errors:
                return self._fail_start(request, errors, "Kernel startup validation failed")

            try:
                bootstrap_ready = self._bootstrap.is_ready()
                bootstrap_metadata = dict(self._bootstrap.runtime_metadata())
            except Exception as exc:
                error = self._error(
                    "dependency_unavailable",
                    "kernel.bootstrap.provider_failed",
                    "Bootstrap readiness provider failed",
                    context={"exception_type": type(exc).__name__},
                )
                return self._fail_start(request, [error], "Bootstrap readiness failed")
            if not bootstrap_ready:
                error = self._error(
                    "dependency_unavailable",
                    "kernel.bootstrap.not_ready",
                    "Bootstrap has not established the initial runtime",
                )
                return self._fail_start(request, [error], "Bootstrap is not ready")

            context = {
                "correlation_id": request.correlation_id,
                "bootstrap": bootstrap_metadata,
            }
            for participant_id in self._ordered_participants():
                self._participant_states[participant_id] = ParticipantState.STARTING
                result, error = self._call_participant(
                    participant_id, "start", context=context
                )
                if error is not None or result is None or not result.succeeded:
                    errors = [error] if error is not None else list(result.errors)
                    self._participant_states[participant_id] = ParticipantState.FAILED
                    errors.extend(self._rollback_started(context))
                    return self._fail_start(
                        request, errors, f"participant startup failed: {participant_id}"
                    )
                self._participant_states[participant_id] = ParticipantState.RUNNING
                self._started_order.append(participant_id)

            transition_error = self._transition(KernelState.RUNNING, request.correlation_id)
            if transition_error is not None:
                errors = [transition_error]
                errors.extend(self._rollback_started(context))
                return self._fail_start(request, errors, "Kernel running transition failed")

            self._refresh_runtime(bootstrap_metadata)
            explanation = self._explain(
                request.correlation_id,
                "runtime coordination",
                "Kernel is running and coordinating participant lifecycles",
                (f"participants={','.join(self._started_order) or 'none'}",),
                ResponseStatus.SUCCEEDED.value,
            )
            return self._response(
                request, ResponseStatus.SUCCEEDED, (), (explanation,), self._runtime
            )

    def coordinate(self, request: CoordinationRequest) -> KernelResponse:
        with self._lock:
            errors = list(self._validate_envelope(request))
            if not request.participant_id.strip():
                errors.append(
                    self._error(
                        "validation",
                        "kernel.coordination.empty_participant",
                        "participant_id must not be empty",
                    )
                )
            if not request.operation.strip():
                errors.append(
                    self._error(
                        "validation",
                        "kernel.coordination.empty_operation",
                        "operation must not be empty",
                    )
                )
            if errors:
                return self._response(request, ResponseStatus.REJECTED, errors, ())
            if self._state is not KernelState.RUNNING:
                return self._reject_state(request, "coordinate")
            if request.participant_id not in self._participants:
                error = self._error(
                    "dependency_unavailable",
                    "kernel.coordination.unknown_participant",
                    f"participant is not registered with Kernel: {request.participant_id}",
                )
                return self._response(request, ResponseStatus.REJECTED, (error,), ())
            if self._participant_states[request.participant_id] is not ParticipantState.RUNNING:
                error = self._error(
                    "invalid_state",
                    "kernel.coordination.participant_not_running",
                    f"participant is not running: {request.participant_id}",
                )
                return self._response(request, ResponseStatus.REJECTED, (error,), ())

            result, error = self._call_participant(
                request.participant_id,
                "coordinate",
                operation=request.operation,
                payload=request.payload,
            )
            if error is not None:
                explanation = self._explain(
                    request.correlation_id,
                    "runtime coordination",
                    f"coordination failed at provider boundary: {request.participant_id}",
                    (error.code,),
                    ResponseStatus.FAILED.value,
                )
                return self._response(
                    request, ResponseStatus.FAILED, (error,), (explanation,), self._runtime
                )
            if result is None or not result.succeeded:
                result_errors = () if result is None else result.errors
                explanation = self._explain(
                    request.correlation_id,
                    "runtime coordination",
                    f"participant rejected or failed coordination: {request.participant_id}",
                    tuple(item.code for item in result_errors),
                    ResponseStatus.FAILED.value,
                )
                return self._response(
                    request,
                    ResponseStatus.FAILED,
                    result_errors,
                    (explanation,),
                    self._runtime,
                )

            self._generation += 1
            self._refresh_runtime(self._runtime.bootstrap_metadata)
            explanation = self._explain(
                request.correlation_id,
                "runtime coordination",
                f"coordinated operation with participant {request.participant_id}",
                (f"operation={request.operation}",),
                ResponseStatus.SUCCEEDED.value,
            )
            return self._response(
                request, ResponseStatus.SUCCEEDED, (), (explanation,), self._runtime
            )

    def stop(self, request: KernelStopRequest) -> KernelResponse:
        with self._lock:
            errors = list(self._validate_envelope(request))
            if errors:
                return self._response(request, ResponseStatus.REJECTED, errors, ())
            if self._state is not KernelState.RUNNING:
                return self._reject_state(request, "stop")
            transition_error = self._transition(KernelState.STOPPING, request.correlation_id)
            if transition_error is not None:
                self._state = KernelState.FAILED
                return self._response(
                    request, ResponseStatus.FAILED, (transition_error,), ()
                )

            context = {"correlation_id": request.correlation_id}
            stop_errors: list[KernelError] = []
            for participant_id in reversed(self._started_order):
                self._participant_states[participant_id] = ParticipantState.STOPPING
                result, error = self._call_participant(
                    participant_id, "stop", context=context
                )
                if error is not None or result is None or not result.succeeded:
                    self._participant_states[participant_id] = ParticipantState.FAILED
                    stop_errors.extend([error] if error is not None else result.errors)
                else:
                    self._participant_states[participant_id] = ParticipantState.STOPPED
            if stop_errors:
                self._state = KernelState.FAILED
                self._refresh_runtime(self._runtime.bootstrap_metadata)
                return self._response(
                    request, ResponseStatus.FAILED, stop_errors, (), self._runtime
                )

            transition_error = self._transition(KernelState.STOPPED, request.correlation_id)
            if transition_error is not None:
                self._state = KernelState.FAILED
                return self._response(
                    request, ResponseStatus.FAILED, (transition_error,), ()
                )
            self._refresh_runtime(self._runtime.bootstrap_metadata)
            explanation = self._explain(
                request.correlation_id,
                "runtime lifecycle",
                "Kernel stopped managed participants in reverse startup order",
                (f"participants={','.join(reversed(self._started_order)) or 'none'}",),
                ResponseStatus.SUCCEEDED.value,
            )
            return self._response(
                request, ResponseStatus.SUCCEEDED, (), (explanation,), self._runtime
            )

    def _compose(self, participants: Iterable[ManagedParticipant]) -> None:
        for participant in participants:
            try:
                participant_id = participant.participant_id.strip()
            except Exception as exc:
                self._composition_errors.append(
                    self._error(
                        "validation",
                        "kernel.participant.invalid_identity",
                        "participant provider did not expose a valid identity",
                        context={"exception_type": type(exc).__name__},
                    )
                )
                continue
            if not participant_id:
                self._composition_errors.append(
                    self._error(
                        "validation",
                        "kernel.participant.empty_identity",
                        "participant identity must not be empty",
                    )
                )
            elif participant_id in self._participants:
                self._composition_errors.append(
                    self._error(
                        "conflict",
                        "kernel.participant.duplicate",
                        f"duplicate participant identity: {participant_id}",
                    )
                )
            else:
                self._participants[participant_id] = participant
                self._participant_states[participant_id] = ParticipantState.REGISTERED

    def _validate_configuration(self, request: KernelStartRequest) -> list[KernelError]:
        errors: list[KernelError] = []
        required = self._configuration.required_participants + request.required_participants
        if len(required) != len(set(required)):
            errors.append(
                self._error(
                    "validation",
                    "kernel.required_participant.duplicate",
                    "required participant identities must be unique",
                )
            )
        for participant_id in required:
            if participant_id not in self._participants:
                errors.append(
                    self._error(
                        "dependency_unavailable",
                        "kernel.participant.required_missing",
                        f"required participant is unavailable: {participant_id}",
                    )
                )
        order = self._configuration.startup_order
        if len(order) != len(set(order)):
            errors.append(
                self._error(
                    "validation",
                    "kernel.startup_order.duplicate",
                    "startup_order identities must be unique",
                )
            )
        unknown = set(order) - set(self._participants)
        for participant_id in sorted(unknown):
            errors.append(
                self._error(
                    "validation",
                    "kernel.startup_order.unknown_participant",
                    f"startup_order contains an unknown participant: {participant_id}",
                )
            )
        return errors

    def _ordered_participants(self) -> tuple[str, ...]:
        configured = self._configuration.startup_order
        remaining = sorted(set(self._participants) - set(configured))
        return configured + tuple(remaining)

    def _validate_envelope(
        self, request: KernelStartRequest | CoordinationRequest | KernelStopRequest
    ) -> tuple[KernelError, ...]:
        errors: list[KernelError] = []
        for name, value in (
            ("request_id", request.request_id),
            ("correlation_id", request.correlation_id),
            ("source_identity", request.source_identity),
        ):
            if not isinstance(value, str) or not value.strip():
                errors.append(
                    self._error(
                        "validation",
                        f"kernel.envelope.{name}",
                        f"{name} must be a non-empty string",
                    )
                )
        try:
            major = int(request.contract_version.split(".", 1)[0])
        except (AttributeError, TypeError, ValueError):
            major = -1
        if major != self._configuration.supported_contract_major:
            errors.append(
                self._error(
                    "unsupported_version",
                    "kernel.contract.unsupported_version",
                    f"unsupported Kernel contract version: {request.contract_version!r}",
                )
            )
        return tuple(errors)

    def _call_participant(
        self,
        participant_id: str,
        method: str,
        **kwargs: Any,
    ) -> tuple[ParticipantResult | None, KernelError | None]:
        participant = self._participants[participant_id]
        try:
            result = getattr(participant, method)(**kwargs)
        except Exception as exc:
            return None, self._error(
                "dependency_unavailable",
                f"kernel.participant.{method}_exception",
                f"participant {method} raised: {participant_id}",
                context={
                    "participant_id": participant_id,
                    "exception_type": type(exc).__name__,
                },
            )
        if not isinstance(result, ParticipantResult):
            return None, self._error(
                "validation",
                f"kernel.participant.{method}_invalid_result",
                f"participant {method} returned a non-contract result: {participant_id}",
            )
        return result, None

    def _rollback_started(self, context: Mapping[str, Any]) -> list[KernelError]:
        errors: list[KernelError] = []
        for participant_id in reversed(self._started_order):
            result, error = self._call_participant(
                participant_id, "stop", context=context
            )
            if error is not None or result is None or not result.succeeded:
                self._participant_states[participant_id] = ParticipantState.FAILED
                errors.extend([error] if error is not None else result.errors)
            else:
                self._participant_states[participant_id] = ParticipantState.STOPPED
        return errors

    def _transition(
        self, target: KernelState, correlation_id: str
    ) -> KernelError | None:
        source = self._state
        if target not in _ALLOWED_TRANSITIONS[source]:
            return self._error(
                "invalid_state",
                "kernel.lifecycle.invalid_transition",
                f"invalid Kernel transition: {source.value} -> {target.value}",
            )
        log_error = self._log(
            "lifecycle",
            "info",
            correlation_id,
            f"Kernel transitioning from {source.value} to {target.value}",
            {"source": source.value, "target": target.value},
        )
        if log_error is not None:
            return log_error
        self._state = target
        self._explain(
            correlation_id,
            "Kernel lifecycle",
            f"transitioned from {source.value} to {target.value}",
            (f"source={source.value}", f"target={target.value}"),
            "in_progress" if target not in {KernelState.RUNNING, KernelState.STOPPED} else "succeeded",
        )
        return None

    def _fail_start(
        self,
        request: KernelStartRequest,
        errors: Iterable[KernelError | None],
        decision: str,
    ) -> KernelResponse:
        collected = [error for error in errors if error is not None]
        if self._state is KernelState.STARTING:
            transition_error = self._transition(KernelState.FAILED, request.correlation_id)
            if transition_error is not None:
                collected.append(transition_error)
                self._state = KernelState.FAILED
        elif self._state is KernelState.CREATED:
            # A failed lifecycle log can prevent the first transition. Startup
            # has nevertheless failed and must leave an unambiguous terminal state.
            self._state = KernelState.FAILED
        explanation = self._explain(
            request.correlation_id,
            "Kernel startup",
            decision,
            tuple(error.code for error in collected),
            ResponseStatus.FAILED.value,
        )
        return self._response(
            request, ResponseStatus.FAILED, collected, (explanation,), self._runtime
        )

    def _reject_state(
        self,
        request: KernelStartRequest | CoordinationRequest | KernelStopRequest,
        operation: str,
    ) -> KernelResponse:
        error = self._error(
            "invalid_state",
            f"kernel.{operation}.invalid_state",
            f"{operation} is not valid while Kernel is {self._state.value}",
        )
        explanation = self._explain(
            request.correlation_id,
            f"Kernel {operation}",
            "request rejected because Kernel state does not allow the operation",
            (f"state={self._state.value}",),
            ResponseStatus.REJECTED.value,
        )
        return self._response(
            request, ResponseStatus.REJECTED, (error,), (explanation,), self._runtime
        )

    def _refresh_runtime(self, bootstrap_metadata: Mapping[str, Any]) -> None:
        self._runtime = RuntimeSnapshot(
            kernel_state=self._state,
            generation=self._generation,
            bootstrap_metadata=bootstrap_metadata,
            participant_states=self._participant_states,
        )

    def _response(
        self,
        request: KernelStartRequest | CoordinationRequest | KernelStopRequest,
        status: ResponseStatus,
        errors: Iterable[KernelError],
        explanations: Iterable[ExplanationRecord],
        runtime: RuntimeSnapshot | None = None,
    ) -> KernelResponse:
        self._sequence += 1
        return KernelResponse(
            response_id=f"{request.correlation_id}:kernel-response:{self._sequence}",
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
        record = ExplanationRecord(
            explanation_id=f"{correlation_id}:kernel-explanation:{self._sequence}",
            engine_id=ENGINE_ID,
            correlation_id=correlation_id,
            subject=subject,
            decision=decision,
            supporting_facts=facts,
            status=status,
            metadata={"sequence": self._sequence},
        )
        self._explanations.append(record)
        return record

    def _log(
        self,
        category: str,
        severity: str,
        correlation_id: str,
        message: str,
        metadata: Mapping[str, Any],
    ) -> KernelError | None:
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
        except Exception as exc:
            return self._error(
                "dependency_unavailable",
                "kernel.logging.delivery_failed",
                "logging capability rejected a Kernel record",
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
    ) -> KernelError:
        return KernelError(
            category=category,
            code=code,
            message=message,
            recoverable=recoverable,
            context=context or {},
        )
