"""Contract types owned or consumed by ENG-001.

These types implement the architectural meanings in Contracts/SharedContracts.md.
They deliberately contain no references to concrete future Engine implementations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Any, Mapping, Protocol, Sequence, runtime_checkable


CONTRACT_ID = "taskgraph.bootstrap"
CONTRACT_VERSION = "1.0.0"
ENGINE_ID = "ENG-001"


class BootstrapState(str, Enum):
    """Approved Bootstrap lifecycle states."""

    CREATED = "created"
    VALIDATING = "validating"
    LOADING = "loading"
    INITIALIZING = "initializing"
    READY = "ready"
    FAILED = "failed"
    STOPPING = "stopping"
    STOPPED = "stopped"


class ResponseStatus(str, Enum):
    """Terminal shared-status values used by synchronous Bootstrap operations."""

    SUCCEEDED = "succeeded"
    REJECTED = "rejected"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class BootstrapError:
    """Structured error conforming to the shared architectural error model."""

    category: str
    code: str
    message: str
    recoverable: bool = False
    context: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "context", MappingProxyType(dict(self.context)))


@dataclass(frozen=True, slots=True)
class ExplanationRecord:
    """ENG-001-owned explanation for a decision or lifecycle transition."""

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
    """Structured record sent through an injected logging contract."""

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
    """Minimal logging capability; not a concrete Logging Engine dependency."""

    def record(self, record: LogRecord) -> None:
        """Accept one structured log record or raise on delivery failure."""


class NullLogSink:
    """Contract-conforming no-op sink for staged Engineering Mode composition."""

    def record(self, record: LogRecord) -> None:
        del record


@runtime_checkable
class StartupCapability(Protocol):
    """A future capability exposed to Bootstrap through an abstract provider."""

    @property
    def capability_id(self) -> str:
        """Return the stable capability identity."""

    def validate_startup(
        self, environment: Mapping[str, Any]
    ) -> Sequence[BootstrapError]:
        """Validate availability without performing the future Engine's work."""


@dataclass(frozen=True, slots=True)
class BootstrapConfiguration:
    """Bootstrap-owned settings; future Engine configuration is out of scope."""

    required_capabilities: tuple[str, ...] = ()
    supported_contract_major: int = 1
    allow_empty_environment: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(self, "required_capabilities", tuple(self.required_capabilities))


@dataclass(frozen=True, slots=True)
class BootstrapRequest:
    """Versioned request envelope for runtime startup."""

    request_id: str
    correlation_id: str
    source_identity: str
    environment: Mapping[str, Any]
    contract_version: str = CONTRACT_VERSION
    metadata: Mapping[str, Any] = field(default_factory=dict)
    required_capabilities: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "environment", MappingProxyType(dict(self.environment)))
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))
        object.__setattr__(self, "required_capabilities", tuple(self.required_capabilities))


@dataclass(frozen=True, slots=True)
class ShutdownRequest:
    """Versioned request envelope for graceful Bootstrap shutdown."""

    request_id: str
    correlation_id: str
    source_identity: str
    contract_version: str = CONTRACT_VERSION
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class RuntimeSnapshot:
    """Immutable description of the initial runtime prepared by ENG-001."""

    state: BootstrapState
    environment: Mapping[str, Any]
    capability_ids: tuple[str, ...]
    contract_version: str = CONTRACT_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(self, "environment", MappingProxyType(dict(self.environment)))
        object.__setattr__(self, "capability_ids", tuple(self.capability_ids))


@dataclass(frozen=True, slots=True)
class BootstrapResponse:
    """Terminal response envelope for a Bootstrap lifecycle operation."""

    response_id: str
    request_id: str
    correlation_id: str
    status: ResponseStatus
    state: BootstrapState
    runtime: RuntimeSnapshot | None = None
    errors: tuple[BootstrapError, ...] = ()
    explanations: tuple[ExplanationRecord, ...] = ()
    contract_id: str = CONTRACT_ID
    contract_version: str = CONTRACT_VERSION
    source_identity: str = ENGINE_ID

    def __post_init__(self) -> None:
        object.__setattr__(self, "errors", tuple(self.errors))
        object.__setattr__(self, "explanations", tuple(self.explanations))


@runtime_checkable
class BootstrapContract(Protocol):
    """Stable public behavior exposed by ENG-001."""

    @property
    def state(self) -> BootstrapState:
        """Return the current Bootstrap lifecycle state."""

    @property
    def runtime(self) -> RuntimeSnapshot | None:
        """Return the immutable runtime snapshot after successful startup."""

    def start(self, request: BootstrapRequest) -> BootstrapResponse:
        """Validate and establish the initial TaskGraph runtime lifecycle."""

    def stop(self, request: ShutdownRequest) -> BootstrapResponse:
        """Stop the Bootstrap-owned lifecycle without stopping future Engines."""
