from __future__ import annotations
from dataclasses import dataclass,field,fields
from enum import Enum
from types import MappingProxyType
from typing import Any,Mapping,Protocol,runtime_checkable
ENGINE_ID="ENG-015";CONTRACT_ID="taskgraph.semantic-planner";CONTRACT_VERSION="1.0.0";SCHEMA_VERSION="1.0";ENGINE_VERSION="1.0.0";RULE_VERSION="1.0.0"
def freeze(v):
    if isinstance(v,Mapping):return MappingProxyType({str(k):freeze(x) for k,x in v.items()})
    if isinstance(v,(list,tuple)):return tuple(freeze(x) for x in v)
    return v
def plain(v):
    if hasattr(v,"__dataclass_fields__"):return {f.name:plain(getattr(v,f.name)) for f in fields(v)}
    if isinstance(v,Mapping):return {str(k):plain(x) for k,x in v.items()}
    if isinstance(v,(list,tuple)):return [plain(x) for x in v]
    if isinstance(v,Enum):return v.value
    return v
class PlannerState(str,Enum):EMPTY="empty";AVAILABLE="available";INVALID="invalid";CLOSED="closed"
class ResponseStatus(str,Enum):SUCCEEDED="succeeded";REJECTED="rejected";FAILED="failed"
@dataclass(frozen=True,slots=True)
class PlannerConfiguration:maximum_plans:int=10000;rule_version:str=RULE_VERSION
@dataclass(frozen=True,slots=True)
class PlannerRequest:
    request_id:str;correlation_id:str;source_identity:str;contract_id:str=CONTRACT_ID;contract_version:str=CONTRACT_VERSION;metadata:Mapping[str,Any]=field(default_factory=dict)
    def __post_init__(self):object.__setattr__(self,"metadata",freeze(self.metadata))
@dataclass(frozen=True,slots=True)
class SemanticGoal:
    goal_id:str;name:str;description:str;success_conditions:tuple[str,...]
    def __post_init__(self):object.__setattr__(self,"success_conditions",tuple(self.success_conditions))
@dataclass(frozen=True,slots=True)
class SemanticConstraint:constraint_id:str;kind:str;description:str;required:bool=True
@dataclass(frozen=True,slots=True)
class SemanticResource:resource_id:str;object_id:str;knowledge_id:str;affordance_id:str;role:str
@dataclass(frozen=True,slots=True)
class SemanticPlanNode:
    plan_id:str;node_id:str;action:str;object_id:str;knowledge_id:str;affordance_id:str;goal:str;preconditions:tuple[str,...];postconditions:tuple[str,...];constraints:tuple[str,...];participants:tuple[str,...];inputs:tuple[str,...];outputs:tuple[str,...];duration:str;priority:int;metadata:Mapping[str,Any];schema_version:str;engine_version:str;checksum:str;created:str;updated:str
    def __post_init__(self):
        for n in ("preconditions","postconditions","constraints","participants","inputs","outputs"):object.__setattr__(self,n,tuple(getattr(self,n)))
        object.__setattr__(self,"metadata",freeze(self.metadata))
@dataclass(frozen=True,slots=True)
class SemanticPlanEdge:source_node_id:str;target_node_id:str;relation:str="precedes"
@dataclass(frozen=True,slots=True)
class PlanValidation:
    valid:bool;errors:tuple[str,...];warnings:tuple[str,...]=()
    def __post_init__(self):object.__setattr__(self,"errors",tuple(self.errors));object.__setattr__(self,"warnings",tuple(self.warnings))
@dataclass(frozen=True,slots=True)
class PlanMetadata:
    rule_id:str;rule_version:str;source_versions:Mapping[str,str];provenance:tuple[str,...]
    def __post_init__(self):object.__setattr__(self,"source_versions",freeze(self.source_versions));object.__setattr__(self,"provenance",tuple(self.provenance))
@dataclass(frozen=True,slots=True)
class SemanticPlan:
    plan_id:str;goal:SemanticGoal;nodes:tuple[SemanticPlanNode,...];edges:tuple[SemanticPlanEdge,...];constraints:tuple[SemanticConstraint,...];resources:tuple[SemanticResource,...];validation:PlanValidation;metadata:PlanMetadata;schema_version:str;engine_version:str;checksum:str;created:str;updated:str
    def __post_init__(self):
        for n in ("nodes","edges","constraints","resources"):object.__setattr__(self,n,tuple(getattr(self,n)))
@dataclass(frozen=True,slots=True)
class PlannerStatistics:
    total_plans:int;valid_plans:int;total_nodes:int;goals:Mapping[str,int]
    def __post_init__(self):object.__setattr__(self,"goals",freeze(self.goals))
@dataclass(frozen=True,slots=True)
class PlannerError:category:str;code:str;message:str;request_id:str;correlation_id:str
@dataclass(frozen=True,slots=True)
class PlannerResponse:
    response_id:str;request_id:str;correlation_id:str;status:ResponseStatus;state:PlannerState;plan:SemanticPlan|None=None;plans:tuple[SemanticPlan,...]=();statistics:PlannerStatistics|None=None;export:Mapping[str,Any]|None=None;valid:bool|None=None;errors:tuple[PlannerError,...]=()
@runtime_checkable
class KnowledgeSource(Protocol):
    def get_all(self)->tuple[Any,...]:...
@runtime_checkable
class AffordanceSource(Protocol):
    def get_all(self)->tuple[Any,...]:...
@runtime_checkable
class SemanticPlanStorage(Protocol):
    def load(self)->Mapping[str,Any]|None:...
    def save(self,payload:Mapping[str,Any])->None:...
class NullLogSink:
    def record(self,item):return None
