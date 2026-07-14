"""Public and provider contracts for ENG-002.

No type in this module imports a concrete Bootstrap or future Engine package.
Integration is structural and provider-based in accordance with Rule 40.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Any, Mapping, Protocol, runtime_checkable


CONTRACT_ID = "taskgraph.kernel"
CONTRACT_VERSION = "1.0.0"
ENGINE_ID = "ENG-002"


class KernelState(str, Enum):
    CREATED = "created"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    FAILED = "failed"


class ParticipantState(str, Enum):
    REGISTERED = "registered"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    FAILED = "failed"


class ResponseStatus(str, Enum):
    SUCCEEDED = "succeeded"
    REJECTED = "rejected"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class KernelError:
    category: str
    code: str
    message: str
    recoverable: bool = False
    context: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "context", MappingProxyType(dict(self.context)))


@dataclass(frozen=True, slots=True)
class ExplanationRecord:
    explanation_id: str
    engine_id: str
    correlation_id: str
    subject: str
    decision: str
    supporting_facts: tuple[str, ...]
    status: str
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "supporting_facts", tuple(self.supporting_facts))
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class LogRecord:
    engine_id: str
    category: str
    severity: str
    correlation_id: str
    message: str
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))


@runtime_checkable
class LogSink(Protocol):
    def record(self, record: LogRecord) -> None:
        """Accept one structured Kernel log record."""


class NullLogSink:
    def record(self, record: LogRecord) -> None:
        del record


@runtime_checkable
class BootstrapReadinessProvider(Protocol):
    """Kernel view of Bootstrap readiness, supplied by composition."""

    def is_ready(self) -> bool:
        """Return whether Bootstrap established the initial runtime."""

    def runtime_metadata(self) -> Mapping[str, Any]:
        """Return safe immutable/copyable metadata for Kernel coordination."""


@dataclass(frozen=True, slots=True)
class ParticipantResult:
    """Contract outcome returned by a managed runtime participant."""

    succeeded: bool
    errors: tuple[KernelError, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "errors", tuple(self.errors))
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))


@runtime_checkable
class ManagedParticipant(Protocol):
    """Lifecycle and coordination capability of a runtime participant."""

    @property
    def participant_id(self) -> str:
        """Return the stable participant identity."""

    def start(self, context: Mapping[str, Any]) -> ParticipantResult:
        """Start through the participant's public lifecycle contract."""

    def coordinate(
        self, operation: str, payload: Mapping[str, Any]
    ) -> ParticipantResult:
        """Handle a runtime-coordination request without event transport."""

    def stop(self, context: Mapping[str, Any]) -> ParticipantResult:
        """Stop through the participant's public lifecycle contract."""


@dataclass(frozen=True, slots=True)
class KernelConfiguration:
    required_participants: tuple[str, ...] = ()
    startup_order: tuple[str, ...] = ()
    supported_contract_major: int = 1

    def __post_init__(self) -> None:
        object.__setattr__(self, "required_participants", tuple(self.required_participants))
        object.__setattr__(self, "startup_order", tuple(self.startup_order))


@dataclass(frozen=True, slots=True)
class KernelStartRequest:
    request_id: str
    correlation_id: str
    source_identity: str
    required_participants: tuple[str, ...] = ()
    contract_version: str = CONTRACT_VERSION
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "required_participants", tuple(self.required_participants))
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class CoordinationRequest:
    request_id: str
    correlation_id: str
    source_identity: str
    participant_id: str
    operation: str
    payload: Mapping[str, Any] = field(default_factory=dict)
    contract_version: str = CONTRACT_VERSION
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "payload", MappingProxyType(dict(self.payload)))
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class KernelStopRequest:
    request_id: str
    correlation_id: str
    source_identity: str
    contract_version: str = CONTRACT_VERSION
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class RuntimeSnapshot:
    kernel_state: KernelState
    generation: int
    bootstrap_metadata: Mapping[str, Any]
    participant_states: Mapping[str, ParticipantState]
    contract_version: str = CONTRACT_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "bootstrap_metadata", MappingProxyType(dict(self.bootstrap_metadata))
        )
        object.__setattr__(
            self, "participant_states", MappingProxyType(dict(self.participant_states))
        )


@dataclass(frozen=True, slots=True)
class KernelResponse:
    response_id: str
    request_id: str
    correlation_id: str
    status: ResponseStatus
    state: KernelState
    runtime: RuntimeSnapshot | None = None
    errors: tuple[KernelError, ...] = ()
    explanations: tuple[ExplanationRecord, ...] = ()
    contract_id: str = CONTRACT_ID
    contract_version: str = CONTRACT_VERSION
    source_identity: str = ENGINE_ID

    def __post_init__(self) -> None:
        object.__setattr__(self, "errors", tuple(self.errors))
        object.__setattr__(self, "explanations", tuple(self.explanations))


@runtime_checkable
class KernelContract(Protocol):
    @property
    def state(self) -> KernelState:
        """Return current Kernel lifecycle state."""

    @property
    def runtime(self) -> RuntimeSnapshot | None:
        """Return the immutable coordinated runtime state."""

    def start(self, request: KernelStartRequest) -> KernelResponse:
        """Start Kernel coordination after Bootstrap readiness."""

    def coordinate(self, request: CoordinationRequest) -> KernelResponse:
        """Coordinate one participant operation."""

    def stop(self, request: KernelStopRequest) -> KernelResponse:
        """Stop managed participant lifecycles in reverse startup order."""
