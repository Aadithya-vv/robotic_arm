"""Public contracts for ENG-010 Scene Engine."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Any, Mapping, Protocol, runtime_checkable

ENGINE_ID = "ENG-010"
CONTRACT_ID = "taskgraph.scene"
CONTRACT_VERSION = "1.0.0"


def freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({key: freeze(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(freeze(item) for item in value)
    if isinstance(value, (set, frozenset)):
        return frozenset(freeze(item) for item in value)
    return value


class SceneState(str, Enum):
    EMPTY = "empty"
    INITIALIZING = "initializing"
    ACTIVE = "active"
    UPDATING = "updating"
    DEGRADED = "degraded"
    CLOSED = "closed"


class ResponseStatus(str, Enum):
    SUCCEEDED = "succeeded"
    REJECTED = "rejected"
    FAILED = "failed"


class TrackingState(str, Enum):
    ACTIVE = "active"
    MISSING = "missing"


class MotionState(str, Enum):
    STATIONARY = "stationary"
    MOVING = "moving"
    UNKNOWN = "unknown"


class RelationshipType(str, Enum):
    LEFT_OF = "left_of"
    RIGHT_OF = "right_of"
    ABOVE = "above"
    BELOW = "below"
    NEAR = "near"
    OVERLAP = "overlap"
    CONTAINED = "contained"


@dataclass(frozen=True, slots=True)
class SceneRequest:
    request_id: str
    correlation_id: str
    source_identity: str
    causation_id: str | None = None
    timestamp_context: str | None = None
    expectation: str = "response_required"
    contract_id: str = CONTRACT_ID
    contract_version: str = CONTRACT_VERSION
    target_capability: str = "scene"
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "metadata", freeze(self.metadata))


@runtime_checkable
class RegionContract(Protocol):
    x: int
    y: int
    width: int
    height: int


@runtime_checkable
class VisualObjectContract(Protocol):
    candidate_id: str
    region: RegionContract
    confidence: float


@runtime_checkable
class VisionObservationContract(Protocol):
    observation_id: str
    frame_id: str
    correlation_id: str
    timestamp_context: str | None
    objects: tuple[VisualObjectContract, ...]
    image_width: int
    image_height: int


@dataclass(frozen=True, slots=True)
class SceneConfiguration:
    tracker_id: str = "default"
    association_iou_threshold: float = 0.2
    maximum_missing_updates: int = 1
    near_distance: float = 50.0
    motion_threshold: float = 1.0
    tracker_settings: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "tracker_settings", freeze(self.tracker_settings))


@dataclass(frozen=True, slots=True)
class BoundingRegion:
    x: int
    y: int
    width: int
    height: int


@dataclass(frozen=True, slots=True)
class SpatialPosition:
    center_x: float
    center_y: float


@dataclass(frozen=True, slots=True)
class SceneObject:
    scene_object_id: str
    vision_observation_id: str
    frame_id: str
    source_candidate_id: str
    region: BoundingRegion
    motion_state: MotionState
    tracking_state: TrackingState
    confidence: float
    first_seen: str | None
    last_seen: str | None
    spatial_position: SpatialPosition
    update_count: int
    missed_updates: int = 0
    status: str = "active"


@dataclass(frozen=True, slots=True)
class SpatialRelationship:
    relationship_id: str
    subject_id: str
    object_id: str
    relationship_type: RelationshipType


@dataclass(frozen=True, slots=True)
class ExplanationRecord:
    explanation_id: str
    engine_id: str
    correlation_id: str
    subject: str
    decision: str
    supporting_facts: tuple[str, ...]
    status: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "supporting_facts", tuple(self.supporting_facts))


@dataclass(frozen=True, slots=True)
class SceneDiagnostics:
    state: SceneState
    tracker_id: str | None
    tracked_object_count: int
    added_objects: int
    removed_objects: int
    updated_objects: int
    relationship_count: int
    tracking_health: str
    processing_time_ms: float | None
    updates_processed: int
    last_error_code: str | None
    tracker_diagnostics: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "tracker_diagnostics", freeze(self.tracker_diagnostics))


@dataclass(frozen=True, slots=True)
class SceneStatistics:
    total_objects_created: int
    total_objects_removed: int
    total_updates: int


@dataclass(frozen=True, slots=True)
class SceneSnapshot:
    scene_id: str
    timestamp_context: str | None
    frame_id: str | None
    objects: tuple[SceneObject, ...]
    relationships: tuple[SpatialRelationship, ...]
    diagnostics: SceneDiagnostics
    statistics: SceneStatistics
    explanation: ExplanationRecord
    contract_version: str = CONTRACT_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(self, "objects", tuple(self.objects))
        object.__setattr__(self, "relationships", tuple(self.relationships))


@dataclass(frozen=True, slots=True)
class SceneError:
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
class TrackingResult:
    succeeded: bool
    objects: tuple[SceneObject, ...] = ()
    added: int = 0
    updated: int = 0
    removed: int = 0
    diagnostics: Mapping[str, Any] = field(default_factory=dict)
    error_code: str | None = None
    error_summary: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "objects", tuple(self.objects))
        object.__setattr__(self, "diagnostics", freeze(self.diagnostics))


@runtime_checkable
class SceneTracker(Protocol):
    @property
    def tracker_id(self) -> str: ...
    def initialize(self, configuration: SceneConfiguration) -> None: ...
    def update(self, observation: VisionObservationContract) -> TrackingResult: ...
    def reset(self) -> None: ...
    def diagnostics(self) -> Mapping[str, Any]: ...
    def close(self) -> None: ...


@dataclass(frozen=True, slots=True)
class SceneResponse:
    response_id: str
    request_id: str
    correlation_id: str
    status: ResponseStatus
    state: SceneState
    snapshot: SceneSnapshot | None = None
    diagnostics: SceneDiagnostics | None = None
    errors: tuple[SceneError, ...] = ()
    explanations: tuple[ExplanationRecord, ...] = ()
    contract_id: str = CONTRACT_ID
    contract_version: str = CONTRACT_VERSION
    source_identity: str = ENGINE_ID

    def __post_init__(self) -> None:
        object.__setattr__(self, "errors", tuple(self.errors))
        object.__setattr__(self, "explanations", tuple(self.explanations))


@runtime_checkable
class SceneContract(Protocol):
    @property
    def state(self) -> SceneState: ...
    def initialize(self, request: SceneRequest, configuration: SceneConfiguration) -> SceneResponse: ...
    def update(self, request: SceneRequest, observation: VisionObservationContract) -> SceneResponse: ...
    def snapshot(self, request: SceneRequest) -> SceneResponse: ...
    def reset(self, request: SceneRequest) -> SceneResponse: ...
    def diagnostics(self, request: SceneRequest) -> SceneResponse: ...
    def close(self, request: SceneRequest) -> SceneResponse: ...
