from __future__ import annotations
from dataclasses import dataclass,field,fields
from enum import Enum
from types import MappingProxyType
from typing import Any,Mapping,Protocol,runtime_checkable
ENGINE_ID="ENG-016";CONTRACT_ID="taskgraph.explainability";CONTRACT_VERSION="1.0.0";SCHEMA_VERSION="1.0";ENGINE_VERSION="1.0.0"
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
class ExplainabilityState(str,Enum):EMPTY="empty";AVAILABLE="available";INVALID="invalid";CLOSED="closed"
class ResponseStatus(str,Enum):SUCCEEDED="succeeded";REJECTED="rejected";FAILED="failed"
@dataclass(frozen=True,slots=True)
class ExplainabilityConfiguration:maximum_records:int=50000;supported_schema_major:int=1
@dataclass(frozen=True,slots=True)
class ExplainabilityRequest:
    request_id:str;correlation_id:str;source_identity:str;contract_id:str=CONTRACT_ID;contract_version:str=CONTRACT_VERSION;metadata:Mapping[str,Any]=field(default_factory=dict)
    def __post_init__(self):object.__setattr__(self,"metadata",freeze(self.metadata))
@dataclass(frozen=True,slots=True)
class EngineReference:engine_id:str;version:str
@dataclass(frozen=True,slots=True)
class ArtifactReference:artifact_id:str;artifact_type:str;source_engine:EngineReference;checksum:str;schema_version:str
@dataclass(frozen=True,slots=True)
class ExplanationNode:
    node_id:str;label:str;artifact:ArtifactReference;dependencies:tuple[str,...]=()
    def __post_init__(self):object.__setattr__(self,"dependencies",tuple(self.dependencies))
@dataclass(frozen=True,slots=True)
class DecisionTrace:
    planning_rule_id:str;semantic_plan_id:str;ordered_actions:tuple[str,...];facts:tuple[str,...]
    def __post_init__(self):object.__setattr__(self,"ordered_actions",tuple(self.ordered_actions));object.__setattr__(self,"facts",tuple(self.facts))
@dataclass(frozen=True,slots=True)
class DependencyTrace:
    dependency_chain:tuple[str,...];nodes:tuple[ExplanationNode,...]
    def __post_init__(self):object.__setattr__(self,"dependency_chain",tuple(self.dependency_chain));object.__setattr__(self,"nodes",tuple(self.nodes))
@dataclass(frozen=True,slots=True)
class ProvenanceRecord:artifact_id:str;source_references:tuple[str,...];checksums:Mapping[str,str]
@dataclass(frozen=True,slots=True)
class RuleExplanation:rule_id:str;rule_version:str;declared_actions:tuple[str,...]
@dataclass(frozen=True,slots=True)
class ValidationExplanation:valid:bool;errors:tuple[str,...];warnings:tuple[str,...]=()
@dataclass(frozen=True,slots=True)
class CompilationExplanation:compiler_id:str;compiler_version:str;source_plan_id:str;diagnostics:tuple[str,...]
@dataclass(frozen=True,slots=True)
class Metadata:
    correlation_id:str;source_versions:Mapping[str,str];attributes:Mapping[str,Any]=field(default_factory=dict)
    def __post_init__(self):object.__setattr__(self,"source_versions",freeze(self.source_versions));object.__setattr__(self,"attributes",freeze(self.attributes))
@dataclass(frozen=True,slots=True)
class ExplanationRecord:
    explanation_id:str;artifact_id:str;artifact_type:str;source_engine:EngineReference;source_version:str;planning_rule_id:str;semantic_plan_id:str;task_ir_id:str;knowledge_id:str;affordance_id:str;dependency_trace:DependencyTrace;decision_trace:DecisionTrace;provenance:ProvenanceRecord;rule:RuleExplanation;validation:ValidationExplanation;compilation:CompilationExplanation|None;checksums:Mapping[str,str];creation_time:str;engine_version:str;schema_version:str;metadata:Metadata;checksum:str
    def __post_init__(self):object.__setattr__(self,"checksums",freeze(self.checksums))
@dataclass(frozen=True,slots=True)
class Statistics:
    total_records:int;valid_records:int;artifact_types:Mapping[str,int];source_engines:Mapping[str,int]
    def __post_init__(self):object.__setattr__(self,"artifact_types",freeze(self.artifact_types));object.__setattr__(self,"source_engines",freeze(self.source_engines))
@dataclass(frozen=True,slots=True)
class ExplainabilityError:category:str;code:str;message:str;request_id:str;correlation_id:str
@dataclass(frozen=True,slots=True)
class ExplainabilityResponse:
    response_id:str;request_id:str;correlation_id:str;status:ResponseStatus;state:ExplainabilityState;record:ExplanationRecord|None=None;records:tuple[ExplanationRecord,...]=();trace:Any=None;statistics:Statistics|None=None;export:Mapping[str,Any]|None=None;valid:bool|None=None;errors:tuple[ExplainabilityError,...]=()
@runtime_checkable
class ArtifactSource(Protocol):
    def get_artifacts(self)->tuple[tuple[str,str,Any],...]:...
@runtime_checkable
class ExplanationStorage(Protocol):
    def load(self)->Mapping[str,Any]|None:...
    def save(self,payload:Mapping[str,Any])->None:...
class NullLogSink:
    def record(self,item):return None
