"""Public immutable contracts for ENG-013."""
from __future__ import annotations
from dataclasses import dataclass,field,fields
from enum import Enum
from types import MappingProxyType
from typing import Any,Mapping,Protocol,runtime_checkable
ENGINE_ID="ENG-013";CONTRACT_ID="taskgraph.affordance";CONTRACT_VERSION="1.0.0";SCHEMA_VERSION="1.0";ENGINE_VERSION="1.0.0";RULE_VERSION="1.0.0"
def freeze(v):
    if isinstance(v,Mapping):return MappingProxyType({str(k):freeze(x) for k,x in v.items()})
    if isinstance(v,(list,tuple)):return tuple(freeze(x) for x in v)
    if isinstance(v,(set,frozenset)):return frozenset(freeze(x) for x in v)
    return v
def plain(v):
    if hasattr(v,"__dataclass_fields__"):return {f.name:plain(getattr(v,f.name)) for f in fields(v)}
    if isinstance(v,Mapping):return {str(k):plain(x) for k,x in v.items()}
    if isinstance(v,(list,tuple,set,frozenset)):return [plain(x) for x in v]
    if isinstance(v,Enum):return v.value
    return v
class AffordanceState(str,Enum):EMPTY="empty";BUILDING="building";AVAILABLE="available";UPDATING="updating";INVALID="invalid";CLOSED="closed"
class ResponseStatus(str,Enum):SUCCEEDED="succeeded";REJECTED="rejected";FAILED="failed"
@dataclass(frozen=True,slots=True)
class AffordanceConfiguration:maximum_records:int=100000;rule_version:str=RULE_VERSION
@dataclass(frozen=True,slots=True)
class AffordanceRequest:
    request_id:str;correlation_id:str;source_identity:str;contract_id:str=CONTRACT_ID;contract_version:str=CONTRACT_VERSION;metadata:Mapping[str,Any]=field(default_factory=dict)
    def __post_init__(self):object.__setattr__(self,"metadata",freeze(self.metadata))
@dataclass(frozen=True,slots=True)
class AffordanceRecord:
    affordance_id:str;object_id:str;knowledge_id:str;object_name:str;summary:str;affordances:tuple[str,...];preconditions:Mapping[str,tuple[str,...]];postconditions:Mapping[str,tuple[str,...]];constraints:Mapping[str,tuple[str,...]];safety_notes:Mapping[str,tuple[str,...]];confidence:float;knowledge_sources:tuple[str,...];generation_rule:tuple[str,...];metadata:Mapping[str,Any];schema_version:str;engine_version:str;checksum:str;created:str;updated:str
    def __post_init__(self):
        for n in ("affordances","knowledge_sources","generation_rule"):object.__setattr__(self,n,tuple(getattr(self,n)))
        for n in ("preconditions","postconditions","constraints","safety_notes","metadata"):object.__setattr__(self,n,freeze(getattr(self,n)))
@dataclass(frozen=True,slots=True)
class AffordanceStatistics:
    total_records:int;total_capabilities:int;actions:Mapping[str,int];action_categories:Mapping[str,int];average_confidence:float
    def __post_init__(self):object.__setattr__(self,"actions",freeze(self.actions));object.__setattr__(self,"action_categories",freeze(self.action_categories))
@dataclass(frozen=True,slots=True)
class AffordanceGraph:version:str;schema_version:str;rule_version:str;generated_at:str;records:tuple[AffordanceRecord,...];statistics:AffordanceStatistics
@dataclass(frozen=True,slots=True)
class AffordanceError:category:str;code:str;message:str;request_id:str;correlation_id:str
@dataclass(frozen=True,slots=True)
class ExplanationRecord:explanation_id:str;engine_id:str;correlation_id:str;subject:str;decision:str;supporting_facts:tuple[str,...];status:str
@dataclass(frozen=True,slots=True)
class LogRecord:engine_id:str;category:str;severity:str;correlation_id:str;message:str;metadata:Mapping[str,Any]=field(default_factory=dict)
@dataclass(frozen=True,slots=True)
class AffordanceResponse:
    response_id:str;request_id:str;correlation_id:str;status:ResponseStatus;state:AffordanceState;graph:AffordanceGraph|None=None;record:AffordanceRecord|None=None;statistics:AffordanceStatistics|None=None;export:Mapping[str,Any]|None=None;valid:bool|None=None;errors:tuple[AffordanceError,...]=();explanations:tuple[ExplanationRecord,...]=()
@runtime_checkable
class KnowledgeRecordContract(Protocol):
    knowledge_id:str;object_id:str;object_name:str;category:str;properties:Mapping[str,Any];facts:tuple[Any,...];relationships:tuple[Any,...];confidence:float;knowledge_sources:tuple[str,...];created:str;updated:str
@runtime_checkable
class KnowledgeSource(Protocol):
    def get_all(self)->tuple[KnowledgeRecordContract,...]:...
@runtime_checkable
class AffordanceStorage(Protocol):
    def load(self)->Mapping[str,Any]|None:...
    def save(self,payload:Mapping[str,Any])->None:...
@runtime_checkable
class LogSink(Protocol):
    def record(self,item:LogRecord)->Any:...
class NullLogSink:
    def record(self,item):return None
@runtime_checkable
class AffordanceContract(Protocol):
    @property
    def state(self)->AffordanceState:...
    def initialize(self,request:AffordanceRequest)->AffordanceResponse:...
    def rebuild(self,request:AffordanceRequest)->AffordanceResponse:...
    def get_affordance(self,request:AffordanceRequest,affordance_id:str|None=None)->AffordanceResponse:...
    def get_affordance_by_object(self,request:AffordanceRequest,object_id:str)->AffordanceResponse:...
    def search(self,request:AffordanceRequest,query:str="",capability:str="",action:str="")->AffordanceResponse:...
    def export_affordances(self,request:AffordanceRequest)->AffordanceResponse:...
    def validate_affordances(self,request:AffordanceRequest)->AffordanceResponse:...
    def get_statistics(self,request:AffordanceRequest)->AffordanceResponse:...
    def close(self,request:AffordanceRequest)->AffordanceResponse:...
