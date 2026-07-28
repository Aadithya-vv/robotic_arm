"""Public contracts and immutable records for ENG-012."""
from __future__ import annotations
from dataclasses import dataclass,field,fields
from enum import Enum
from types import MappingProxyType
from typing import Any,Mapping,Protocol,runtime_checkable

ENGINE_ID="ENG-012";CONTRACT_ID="taskgraph.knowledge";CONTRACT_VERSION="1.0.0";SCHEMA_VERSION="1.0";ENGINE_VERSION="1.0.0"
def freeze(value:Any)->Any:
    if isinstance(value,Mapping):return MappingProxyType({str(k):freeze(v) for k,v in value.items()})
    if isinstance(value,(list,tuple)):return tuple(freeze(v) for v in value)
    if isinstance(value,(set,frozenset)):return frozenset(freeze(v) for v in value)
    return value
def plain(value:Any)->Any:
    if hasattr(value,"__dataclass_fields__"):return {f.name:plain(getattr(value,f.name)) for f in fields(value)}
    if isinstance(value,Mapping):return {str(k):plain(v) for k,v in value.items()}
    if isinstance(value,(tuple,list,set,frozenset)):return [plain(v) for v in value]
    if isinstance(value,Enum):return value.value
    return value

class KnowledgeState(str,Enum):EMPTY="empty";BUILDING="building";AVAILABLE="available";UPDATING="updating";INVALID="invalid";CLOSED="closed"
class ResponseStatus(str,Enum):SUCCEEDED="succeeded";REJECTED="rejected";FAILED="failed"
@dataclass(frozen=True,slots=True)
class KnowledgeConfiguration:
    schema_version:str=SCHEMA_VERSION;maximum_records:int=100000
@dataclass(frozen=True,slots=True)
class KnowledgeRequest:
    request_id:str;correlation_id:str;source_identity:str;contract_id:str=CONTRACT_ID;contract_version:str=CONTRACT_VERSION;target_capability:str="knowledge";metadata:Mapping[str,Any]=field(default_factory=dict)
    def __post_init__(self):object.__setattr__(self,"metadata",freeze(self.metadata))
@dataclass(frozen=True,slots=True)
class KnowledgeRecord:
    knowledge_id:str;object_id:str;object_name:str;category:str;summary:str;properties:Mapping[str,Any];facts:tuple[Mapping[str,Any],...];attributes:Mapping[str,Any];typical_uses:tuple[str,...];materials:tuple[str,...];environment:Mapping[str,Any];confidence:float;knowledge_sources:tuple[str,...];relationships:tuple[Any,...];metadata:Mapping[str,Any];version:str;schema_version:str;engine_version:str;created:str;updated:str;checksum:str
    def __post_init__(self):
        for name in ("properties","attributes","environment","metadata"):object.__setattr__(self,name,freeze(getattr(self,name)))
        for name in ("facts","typical_uses","materials","knowledge_sources","relationships"):object.__setattr__(self,name,tuple(freeze(v) for v in getattr(self,name)))
@dataclass(frozen=True,slots=True)
class KnowledgeStatistics:
    total_records:int;categories:Mapping[str,int];properties:Mapping[str,int];facts:int;relationships:int;average_confidence:float
    def __post_init__(self):object.__setattr__(self,"categories",freeze(self.categories));object.__setattr__(self,"properties",freeze(self.properties))
@dataclass(frozen=True,slots=True)
class KnowledgeGraph:version:str;schema_version:str;generated_at:str;records:tuple[KnowledgeRecord,...];statistics:KnowledgeStatistics
@dataclass(frozen=True,slots=True)
class KnowledgeError:category:str;code:str;message:str;request_id:str;correlation_id:str;recoverable:bool=False
@dataclass(frozen=True,slots=True)
class ExplanationRecord:explanation_id:str;engine_id:str;correlation_id:str;subject:str;decision:str;supporting_facts:tuple[str,...];status:str
@dataclass(frozen=True,slots=True)
class LogRecord:engine_id:str;category:str;severity:str;correlation_id:str;message:str;metadata:Mapping[str,Any]=field(default_factory=dict)
@dataclass(frozen=True,slots=True)
class KnowledgeResponse:
    response_id:str;request_id:str;correlation_id:str;status:ResponseStatus;state:KnowledgeState;graph:KnowledgeGraph|None=None;record:KnowledgeRecord|None=None;statistics:KnowledgeStatistics|None=None;export:Mapping[str,Any]|None=None;valid:bool|None=None;errors:tuple[KnowledgeError,...]=();explanations:tuple[ExplanationRecord,...]=()

@runtime_checkable
class SemanticObjectContract(Protocol):
    object_id:str;object_name:str;category:str;description:str;aliases:tuple[str,...];average_confidence:float;relationships:tuple[Any,...];metadata:Mapping[str,Any];version:str;learning_date:str;last_updated:str;tags:tuple[str,...]
@runtime_checkable
class SemanticInventorySource(Protocol):
    def get_all(self)->tuple[SemanticObjectContract,...]:...
@runtime_checkable
class KnowledgeStorage(Protocol):
    def load(self)->Mapping[str,Any]|None:...
    def save(self,payload:Mapping[str,Any])->None:...
@runtime_checkable
class LogSink(Protocol):
    def record(self,item:LogRecord)->Any:...
class NullLogSink:
    def record(self,item):return None
@runtime_checkable
class KnowledgeContract(Protocol):
    @property
    def state(self)->KnowledgeState:...
    def initialize(self,request:KnowledgeRequest)->KnowledgeResponse:...
    def rebuild(self,request:KnowledgeRequest)->KnowledgeResponse:...
    def get_knowledge(self,request:KnowledgeRequest,knowledge_id:str|None=None)->KnowledgeResponse:...
    def get_knowledge_by_object(self,request:KnowledgeRequest,object_id:str)->KnowledgeResponse:...
    def search(self,request:KnowledgeRequest,query:str="",property_name:str="",fact:str="",category:str="",relationship:str="")->KnowledgeResponse:...
    def get_statistics(self,request:KnowledgeRequest)->KnowledgeResponse:...
    def export_knowledge(self,request:KnowledgeRequest)->KnowledgeResponse:...
    def validate_knowledge(self,request:KnowledgeRequest)->KnowledgeResponse:...
    def close(self,request:KnowledgeRequest)->KnowledgeResponse:...
