"""Public contracts for ENG-009 Vision Engine."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Any, Mapping, Protocol, runtime_checkable

ENGINE_ID = "ENG-009"
CONTRACT_ID = "taskgraph.vision"
CONTRACT_VERSION = "1.0.0"


def freeze(value: Any) -> Any:
    """Recursively convert common containers to immutable boundary values."""
    if isinstance(value, Mapping):
        return MappingProxyType({key: freeze(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(freeze(item) for item in value)
    if isinstance(value, (set, frozenset)):
        return frozenset(freeze(item) for item in value)
    return value


class VisionState(str, Enum):
    CREATED = "created"
    READY = "ready"
    VALIDATING = "validating"
    PROCESSING = "processing"
    FAILED = "failed"
    SHUTDOWN = "shutdown"


class ResponseStatus(str, Enum):
    SUCCEEDED = "succeeded"
    REJECTED = "rejected"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class VisionRequest:
    request_id: str
    correlation_id: str
    source_identity: str
    causation_id: str | None = None
    timestamp_context: str | None = None
    expectation: str = "response_required"
    contract_id: str = CONTRACT_ID
    contract_version: str = CONTRACT_VERSION
    target_capability: str = "vision"
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "metadata", freeze(self.metadata))


@runtime_checkable
class CameraObservationContract(Protocol):
    """Structural view of the approved ENG-008 observation boundary."""

    observation_id: str
    correlation_id: str
    data: bytes
    width: int
    height: int
    channels: int
    pixel_format: str
    timestamp_context: str | None
    metadata: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class VisionConfiguration:
    processor_id: str = "default"
    confidence_threshold: float = 0.5
    maximum_candidates: int = 100
    normalize: bool = True
    processor_settings: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "processor_settings", freeze(self.processor_settings))


@dataclass(frozen=True, slots=True)
class BoundingRegion:
    x: int
    y: int
    width: int
    height: int


@dataclass(frozen=True, slots=True)
class FeatureDescriptor:
    name: str
    values: tuple[float, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "values", tuple(float(value) for value in self.values))


@dataclass(frozen=True, slots=True)
class VisualObject:
    candidate_id: str
    region: BoundingRegion
    confidence: float
    features: tuple[FeatureDescriptor, ...] = ()
    properties: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "features", tuple(self.features))
        object.__setattr__(self, "properties", freeze(self.properties))


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
        object.__setattr__(self, "metadata", freeze(self.metadata))


@dataclass(frozen=True, slots=True)
class VisionDiagnostics:
    state: VisionState
    processor_id: str | None
    frames_processed: int
    failures: int
    last_processing_time_ms: float | None
    last_error_code: str | None
    processor_diagnostics: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "processor_diagnostics", freeze(self.processor_diagnostics))


@dataclass(frozen=True, slots=True)
class VisionObservation:
    observation_id: str
    frame_id: str
    correlation_id: str
    timestamp_context: str | None
    objects: tuple[VisualObject, ...]
    features: tuple[FeatureDescriptor, ...]
    processing_time_ms: float
    image_width: int
    image_height: int
    pixel_format: str
    diagnostics: Mapping[str, Any]
    explanation: ExplanationRecord
    contract_version: str = CONTRACT_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(self, "objects", tuple(self.objects))
        object.__setattr__(self, "features", tuple(self.features))
        object.__setattr__(self, "diagnostics", freeze(self.diagnostics))


@dataclass(frozen=True, slots=True)
class VisionError:
    category: str
    code: str
    message: str
    request_id: str
    correlation_id: str
    recoverable: bool = False
    context: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "context", freeze(self.context))


@dataclass(frozen=True, slots=True)
class LogRecord:
    engine_id: str
    category: str
    severity: str
    correlation_id: str
    message: str
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "metadata", freeze(self.metadata))


@runtime_checkable
class LogSink(Protocol):
    def record(self, record: LogRecord) -> None: ...


class NullLogSink:
    def record(self, record: LogRecord) -> None:
        del record


@dataclass(frozen=True, slots=True)
class ProcessorResult:
    succeeded: bool
    objects: tuple[VisualObject, ...] = ()
    features: tuple[FeatureDescriptor, ...] = ()
    diagnostics: Mapping[str, Any] = field(default_factory=dict)
    error_code: str | None = None
    error_summary: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "objects", tuple(self.objects))
        object.__setattr__(self, "features", tuple(self.features))
        object.__setattr__(self, "diagnostics", freeze(self.diagnostics))


@runtime_checkable
class VisionProcessor(Protocol):
    @property
    def processor_id(self) -> str: ...
    def initialize(self, configuration: VisionConfiguration) -> None: ...
    def process(self, observation: CameraObservationContract) -> ProcessorResult: ...
    def diagnostics(self) -> Mapping[str, Any]: ...
    def shutdown(self) -> None: ...


@dataclass(frozen=True, slots=True)
class VisionResponse:
    response_id: str
    request_id: str
    correlation_id: str
    status: ResponseStatus
    state: VisionState
    observation: VisionObservation | None = None
    diagnostics: VisionDiagnostics | None = None
    errors: tuple[VisionError, ...] = ()
    explanations: tuple[ExplanationRecord, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)
    contract_id: str = CONTRACT_ID
    contract_version: str = CONTRACT_VERSION
    source_identity: str = ENGINE_ID

    def __post_init__(self) -> None:
        object.__setattr__(self, "errors", tuple(self.errors))
        object.__setattr__(self, "explanations", tuple(self.explanations))
        object.__setattr__(self, "metadata", freeze(self.metadata))


@runtime_checkable
class VisionContract(Protocol):
    @property
    def state(self) -> VisionState: ...
    def initialize(self, request: VisionRequest, configuration: VisionConfiguration) -> VisionResponse: ...
    def process(self, request: VisionRequest, observation: CameraObservationContract) -> VisionResponse: ...
    def diagnostics(self, request: VisionRequest) -> VisionResponse: ...
    def shutdown(self, request: VisionRequest) -> VisionResponse: ...
