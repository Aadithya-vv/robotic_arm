from __future__ import annotations

from dataclasses import dataclass, field, fields
from enum import Enum
from types import MappingProxyType
from typing import Any, Mapping, Protocol, runtime_checkable

ENGINE_ID = "ENG-014"
CONTRACT_ID = "taskgraph.taskir-compiler"
CONTRACT_VERSION = "1.0.0"
SCHEMA_VERSION = "1.0"
ENGINE_VERSION = "1.0.0"


def freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({str(key): freeze(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(freeze(item) for item in value)
    return value


def plain(value: Any) -> Any:
    if hasattr(value, "__dataclass_fields__"):
        return {item.name: plain(getattr(value, item.name)) for item in fields(value)}
    if isinstance(value, Mapping):
        return {str(key): plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [plain(item) for item in value]
    if isinstance(value, Enum):
        return value.value
    return value


class CompilerState(str, Enum):
    EMPTY = "empty"
    AVAILABLE = "available"
    CLOSED = "closed"
    INVALID = "invalid"


class ResponseStatus(str, Enum):
    SUCCEEDED = "succeeded"
    REJECTED = "rejected"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class TaskIRConfiguration:
    maximum_documents: int = 10000
    supported_schema_major: int = 1


@dataclass(frozen=True, slots=True)
class TaskIRRequest:
    request_id: str
    correlation_id: str
    source_identity: str
    contract_id: str = CONTRACT_ID
    contract_version: str = CONTRACT_VERSION
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        object.__setattr__(self, "metadata", freeze(self.metadata))


@dataclass(frozen=True, slots=True)
class TaskParameter:
    name: str
    value: Any
    value_type: str
    source: str

    def __post_init__(self):
        object.__setattr__(self, "value", freeze(self.value))


@dataclass(frozen=True, slots=True)
class TaskCondition:
    condition_id: str
    kind: str
    expression: str
    required: bool = True


@dataclass(frozen=True, slots=True)
class TaskConstraint:
    constraint_id: str
    kind: str
    description: str
    required: bool = True


@dataclass(frozen=True, slots=True)
class TaskMetadata:
    correlation_id: str
    source_plan_version: str
    planning_rule_id: str
    planning_rule_version: str
    provenance: tuple[str, ...]
    explanation_references: tuple[str, ...] = ()

    def __post_init__(self):
        object.__setattr__(self, "provenance", tuple(self.provenance))
        object.__setattr__(self, "explanation_references", tuple(self.explanation_references))


@dataclass(frozen=True, slots=True)
class TaskNode:
    task_id: str
    node_id: str
    semantic_plan_id: str
    planning_rule_id: str
    action: str
    object_id: str
    knowledge_id: str
    affordance_id: str
    parameters: tuple[TaskParameter, ...]
    inputs: tuple[str, ...]
    outputs: tuple[str, ...]
    preconditions: tuple[TaskCondition, ...]
    postconditions: tuple[TaskCondition, ...]
    constraints: tuple[TaskConstraint, ...]
    priority: int
    metadata: Mapping[str, Any]
    schema_version: str
    engine_version: str
    checksum: str
    created: str
    updated: str

    def __post_init__(self):
        for name in ("parameters", "inputs", "outputs", "preconditions", "postconditions", "constraints"):
            object.__setattr__(self, name, tuple(getattr(self, name)))
        object.__setattr__(self, "metadata", freeze(self.metadata))


@dataclass(frozen=True, slots=True)
class TaskEdge:
    source_node_id: str
    target_node_id: str
    relation: str


@dataclass(frozen=True, slots=True)
class TaskValidation:
    valid: bool
    errors: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    def __post_init__(self):
        object.__setattr__(self, "errors", tuple(self.errors))
        object.__setattr__(self, "warnings", tuple(self.warnings))


@dataclass(frozen=True, slots=True)
class TaskCompilation:
    source_plan_id: str
    compiler_id: str
    compiler_version: str
    diagnostics: tuple[str, ...]

    def __post_init__(self):
        object.__setattr__(self, "diagnostics", tuple(self.diagnostics))


@dataclass(frozen=True, slots=True)
class TaskStatistics:
    total_documents: int
    valid_documents: int
    total_nodes: int
    total_edges: int
    actions: Mapping[str, int]

    def __post_init__(self):
        object.__setattr__(self, "actions", freeze(self.actions))


@dataclass(frozen=True, slots=True)
class TaskIR:
    task_id: str
    semantic_plan_id: str
    correlation_id: str
    goal: Mapping[str, Any]
    resources: tuple[Mapping[str, Any], ...]
    nodes: tuple[TaskNode, ...]
    edges: tuple[TaskEdge, ...]
    constraints: tuple[TaskConstraint, ...]
    failure_semantics: tuple[str, ...]
    metadata: TaskMetadata
    validation: TaskValidation
    compilation: TaskCompilation
    schema_version: str
    engine_version: str
    checksum: str
    created: str
    updated: str

    def __post_init__(self):
        object.__setattr__(self, "goal", freeze(self.goal))
        object.__setattr__(self, "resources", tuple(freeze(item) for item in self.resources))
        for name in ("nodes", "edges", "constraints", "failure_semantics"):
            object.__setattr__(self, name, tuple(getattr(self, name)))


@dataclass(frozen=True, slots=True)
class TaskCompilationResult:
    task_ir: TaskIR | None
    validation: TaskValidation
    diagnostics: tuple[str, ...]

    def __post_init__(self):
        object.__setattr__(self, "diagnostics", tuple(self.diagnostics))


@dataclass(frozen=True, slots=True)
class TaskIRError:
    category: str
    code: str
    message: str
    request_id: str
    correlation_id: str


@dataclass(frozen=True, slots=True)
class TaskIRResponse:
    response_id: str
    request_id: str
    correlation_id: str
    status: ResponseStatus
    state: CompilerState
    result: TaskCompilationResult | None = None
    task_ir: TaskIR | None = None
    documents: tuple[TaskIR, ...] = ()
    statistics: TaskStatistics | None = None
    export: Mapping[str, Any] | None = None
    validation: TaskValidation | None = None
    errors: tuple[TaskIRError, ...] = ()


@runtime_checkable
class TaskIRStorage(Protocol):
    def load(self) -> Mapping[str, Any] | None: ...
    def save(self, payload: Mapping[str, Any]) -> None: ...


class NullLogSink:
    def record(self, item: Any) -> None:
        return None
