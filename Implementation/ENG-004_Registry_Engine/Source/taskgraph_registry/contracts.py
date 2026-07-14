"""Public metadata-only contracts for ENG-004 Registry Engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Any, Mapping, Protocol, runtime_checkable

ENGINE_ID = "ENG-004"
CONTRACT_ID = "taskgraph.registry"
CONTRACT_VERSION = "1.0.0"


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    if isinstance(value, (set, frozenset)):
        return frozenset(_freeze(item) for item in value)
    return value


class RegistryState(str, Enum):
    EMPTY = "empty"
    ACCEPTING_REGISTRATIONS = "accepting_registrations"
    READY = "ready"
    RESOLVING = "resolving"
    DEGRADED = "degraded"
    CLOSED = "closed"


class Availability(str, Enum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    DEGRADED = "degraded"


class ResponseStatus(str, Enum):
    SUCCEEDED = "succeeded"
    REJECTED = "rejected"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class RegistryError:
    category: str
    code: str
    message: str
    request_id: str
    correlation_id: str
    recoverable: bool = False
    context: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "context", _freeze(self.context))


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
        object.__setattr__(self, "metadata", _freeze(self.metadata))


@dataclass(frozen=True, slots=True)
class LogRecord:
    engine_id: str
    category: str
    severity: str
    correlation_id: str
    message: str
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "metadata", _freeze(self.metadata))


@runtime_checkable
class LogSink(Protocol):
    def record(self, record: LogRecord) -> None: ...


class NullLogSink:
    def record(self, record: LogRecord) -> None:
        del record


@dataclass(frozen=True, slots=True)
class EngineRegistration:
    engine_id: str
    display_name: str
    contract_id: str
    contract_version: str
    capabilities: tuple[str, ...]
    availability: Availability = Availability.AVAILABLE
    provenance: Mapping[str, Any] = field(default_factory=dict)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "capabilities", tuple(self.capabilities))
        object.__setattr__(self, "provenance", _freeze(self.provenance))
        object.__setattr__(self, "metadata", _freeze(self.metadata))


@dataclass(frozen=True, slots=True)
class RegistryRequest:
    request_id: str
    correlation_id: str
    source_identity: str
    causation_id: str | None = None
    timestamp_context: str | None = None
    expectation: str = "response_required"
    contract_id: str = CONTRACT_ID
    contract_version: str = CONTRACT_VERSION
    target_capability: str = "registry"
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "metadata", _freeze(self.metadata))


@dataclass(frozen=True, slots=True)
class RegistrySnapshot:
    snapshot_id: str
    generation: int
    state: RegistryState
    registrations: Mapping[str, EngineRegistration]
    correlation_id: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "registrations", MappingProxyType(dict(self.registrations)))


@dataclass(frozen=True, slots=True)
class DependencyResolution:
    resolution_id: str
    requested_engine_ids: tuple[str, ...]
    resolved: Mapping[str, EngineRegistration]
    correlation_id: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "requested_engine_ids", tuple(self.requested_engine_ids))
        object.__setattr__(self, "resolved", MappingProxyType(dict(self.resolved)))


@dataclass(frozen=True, slots=True)
class RegistryResponse:
    response_id: str
    request_id: str
    correlation_id: str
    status: ResponseStatus
    state: RegistryState
    registration: EngineRegistration | None = None
    registrations: tuple[EngineRegistration, ...] = ()
    snapshot: RegistrySnapshot | None = None
    resolution: DependencyResolution | None = None
    errors: tuple[RegistryError, ...] = ()
    explanations: tuple[ExplanationRecord, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)
    contract_id: str = CONTRACT_ID
    contract_version: str = CONTRACT_VERSION
    source_identity: str = ENGINE_ID

    def __post_init__(self) -> None:
        object.__setattr__(self, "registrations", tuple(self.registrations))
        object.__setattr__(self, "errors", tuple(self.errors))
        object.__setattr__(self, "explanations", tuple(self.explanations))
        object.__setattr__(self, "metadata", _freeze(self.metadata))


@dataclass(frozen=True, slots=True)
class RegistryPolicy:
    maximum_registrations: int | None = None
    required_metadata_keys: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "required_metadata_keys", tuple(self.required_metadata_keys))


@runtime_checkable
class RegistryContract(Protocol):
    @property
    def state(self) -> RegistryState: ...
    def open(self, request: RegistryRequest) -> RegistryResponse: ...
    def register(self, request: RegistryRequest, registration: EngineRegistration) -> RegistryResponse: ...
    def mark_ready(self, request: RegistryRequest) -> RegistryResponse: ...
    def lookup(self, request: RegistryRequest, engine_id: str) -> RegistryResponse: ...
    def discover(self, request: RegistryRequest, capability: str | None = None, availability: Availability | None = None) -> RegistryResponse: ...
    def resolve(self, request: RegistryRequest, engine_ids: tuple[str, ...]) -> RegistryResponse: ...
    def set_availability(self, request: RegistryRequest, engine_id: str, availability: Availability) -> RegistryResponse: ...
    def deregister(self, request: RegistryRequest, engine_id: str) -> RegistryResponse: ...
    def snapshot(self, request: RegistryRequest) -> RegistryResponse: ...
    def close(self, request: RegistryRequest) -> RegistryResponse: ...
