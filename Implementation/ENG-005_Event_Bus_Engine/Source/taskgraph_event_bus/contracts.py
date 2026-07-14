"""Public contracts for ENG-005 Event Bus Engine."""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Any, Mapping, Protocol, runtime_checkable

ENGINE_ID = "ENG-005"
CONTRACT_ID = "taskgraph.event_bus"
CONTRACT_VERSION = "1.0.0"

def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping): return MappingProxyType({k: _freeze(v) for k, v in value.items()})
    if isinstance(value, (list, tuple)): return tuple(_freeze(v) for v in value)
    if isinstance(value, (set, frozenset)): return frozenset(_freeze(v) for v in value)
    return value

class EventBusState(str, Enum):
    CREATED="created"; STARTING="starting"; ACCEPTING_EVENTS="accepting_events"
    DRAINING="draining"; STOPPED="stopped"; DEGRADED="degraded"; FAILED="failed"

class ResponseStatus(str, Enum):
    SUCCEEDED="succeeded"; PARTIAL="partial"; REJECTED="rejected"; FAILED="failed"

@dataclass(frozen=True, slots=True)
class EventBusError:
    category: str; code: str; message: str; request_id: str; correlation_id: str
    recoverable: bool=False; context: Mapping[str, Any]=field(default_factory=dict)
    def __post_init__(self): object.__setattr__(self, "context", _freeze(self.context))

@dataclass(frozen=True, slots=True)
class ExplanationRecord:
    explanation_id: str; engine_id: str; correlation_id: str; subject: str; decision: str
    supporting_facts: tuple[str, ...]; status: str; metadata: Mapping[str, Any]=field(default_factory=dict)
    def __post_init__(self):
        object.__setattr__(self, "supporting_facts", tuple(self.supporting_facts)); object.__setattr__(self, "metadata", _freeze(self.metadata))

@dataclass(frozen=True, slots=True)
class LogRecord:
    engine_id: str; category: str; severity: str; correlation_id: str; message: str
    metadata: Mapping[str, Any]=field(default_factory=dict)
    def __post_init__(self): object.__setattr__(self, "metadata", _freeze(self.metadata))

@runtime_checkable
class LogSink(Protocol):
    def record(self, record: LogRecord) -> None: ...
class NullLogSink:
    def record(self, record: LogRecord) -> None: del record

@dataclass(frozen=True, slots=True)
class EventBusPolicy:
    maximum_publishers: int | None=None; maximum_subscriptions: int | None=None

@dataclass(frozen=True, slots=True)
class EventBusRequest:
    request_id: str; correlation_id: str; source_identity: str
    causation_id: str | None=None; timestamp_context: str | None=None
    expectation: str="response_required"; contract_id: str=CONTRACT_ID
    contract_version: str=CONTRACT_VERSION; target_capability: str="event_bus"
    metadata: Mapping[str, Any]=field(default_factory=dict)
    def __post_init__(self): object.__setattr__(self, "metadata", _freeze(self.metadata))

@dataclass(frozen=True, slots=True)
class PlatformEvent:
    event_id: str; topic: str; publisher_id: str; correlation_id: str; payload: Mapping[str, Any]
    causation_id: str | None=None; timestamp_context: str | None=None
    event_version: str="1.0.0"; metadata: Mapping[str, Any]=field(default_factory=dict)
    def __post_init__(self):
        object.__setattr__(self, "payload", _freeze(self.payload)); object.__setattr__(self, "metadata", _freeze(self.metadata))

@dataclass(frozen=True, slots=True)
class DeliveryResult:
    succeeded: bool; metadata: Mapping[str, Any]=field(default_factory=dict); error_summary: str | None=None
    def __post_init__(self): object.__setattr__(self, "metadata", _freeze(self.metadata))

@runtime_checkable
class EventHandler(Protocol):
    def deliver(self, event: PlatformEvent) -> DeliveryResult: ...

@dataclass(frozen=True, slots=True)
class PublisherRegistration:
    publisher_id: str; topics: tuple[str, ...]; metadata: Mapping[str, Any]=field(default_factory=dict)
    def __post_init__(self):
        object.__setattr__(self, "topics", tuple(self.topics)); object.__setattr__(self, "metadata", _freeze(self.metadata))

@dataclass(frozen=True, slots=True)
class Subscription:
    subscription_id: str; subscriber_id: str; topic: str; metadata: Mapping[str, Any]=field(default_factory=dict)
    def __post_init__(self): object.__setattr__(self, "metadata", _freeze(self.metadata))

@dataclass(frozen=True, slots=True)
class DeliveryOutcome:
    subscription_id: str; subscriber_id: str; succeeded: bool; error: str | None=None

@dataclass(frozen=True, slots=True)
class EventDelivery:
    delivery_id: str; event_id: str; topic: str; outcomes: tuple[DeliveryOutcome, ...]; correlation_id: str
    def __post_init__(self): object.__setattr__(self, "outcomes", tuple(self.outcomes))

@dataclass(frozen=True, slots=True)
class EventBusSnapshot:
    snapshot_id: str; generation: int; state: EventBusState
    publishers: Mapping[str, PublisherRegistration]; subscriptions: Mapping[str, Subscription]
    delivery_count: int; correlation_id: str
    def __post_init__(self):
        object.__setattr__(self, "publishers", MappingProxyType(dict(self.publishers))); object.__setattr__(self, "subscriptions", MappingProxyType(dict(self.subscriptions)))

@dataclass(frozen=True, slots=True)
class EventBusResponse:
    response_id: str; request_id: str; correlation_id: str; status: ResponseStatus; state: EventBusState
    publisher: PublisherRegistration | None=None; subscription: Subscription | None=None
    delivery: EventDelivery | None=None; snapshot: EventBusSnapshot | None=None
    errors: tuple[EventBusError, ...]=(); explanations: tuple[ExplanationRecord, ...]=()
    metadata: Mapping[str, Any]=field(default_factory=dict); contract_id: str=CONTRACT_ID
    contract_version: str=CONTRACT_VERSION; source_identity: str=ENGINE_ID
    def __post_init__(self):
        object.__setattr__(self, "errors", tuple(self.errors)); object.__setattr__(self, "explanations", tuple(self.explanations)); object.__setattr__(self, "metadata", _freeze(self.metadata))

@runtime_checkable
class EventBusContract(Protocol):
    @property
    def state(self) -> EventBusState: ...
    def start(self, request: EventBusRequest) -> EventBusResponse: ...
    def register_publisher(self, request: EventBusRequest, publisher: PublisherRegistration) -> EventBusResponse: ...
    def unregister_publisher(self, request: EventBusRequest, publisher_id: str) -> EventBusResponse: ...
    def subscribe(self, request: EventBusRequest, subscription: Subscription, handler: EventHandler) -> EventBusResponse: ...
    def unsubscribe(self, request: EventBusRequest, subscription_id: str) -> EventBusResponse: ...
    def publish(self, request: EventBusRequest, event: PlatformEvent) -> EventBusResponse: ...
    def snapshot(self, request: EventBusRequest) -> EventBusResponse: ...
    def stop(self, request: EventBusRequest) -> EventBusResponse: ...
