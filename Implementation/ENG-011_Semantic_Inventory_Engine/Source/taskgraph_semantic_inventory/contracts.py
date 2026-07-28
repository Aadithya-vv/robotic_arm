"""Public contracts and immutable records for ENG-011."""
from __future__ import annotations
from dataclasses import dataclass,field,fields
from enum import Enum
from types import MappingProxyType
from typing import Any,Mapping,Protocol,runtime_checkable

ENGINE_ID="ENG-011";CONTRACT_ID="taskgraph.semantic-inventory";CONTRACT_VERSION="1.0.0";SCHEMA_VERSION="1.0"

def freeze(value:Any)->Any:
    if isinstance(value,Mapping):return MappingProxyType({str(k):freeze(v) for k,v in value.items()})
    if isinstance(value,(list,tuple)):return tuple(freeze(v) for v in value)
    if isinstance(value,(set,frozenset)):return frozenset(freeze(v) for v in value)
    return value

def plain(value:Any)->Any:
    if hasattr(value,"__dataclass_fields__"):return {item.name:plain(getattr(value,item.name)) for item in fields(value)}
    if isinstance(value,Mapping):return {str(k):plain(v) for k,v in value.items()}
    if isinstance(value,(tuple,list,set,frozenset)):return [plain(v) for v in value]
    if isinstance(value,Enum):return value.value
    return value

class InventoryState(str,Enum):EMPTY="empty";BUILDING="building";AVAILABLE="available";UPDATING="updating";INVALID="invalid";CLOSED="closed"
class ResponseStatus(str,Enum):SUCCEEDED="succeeded";REJECTED="rejected";FAILED="failed"

@dataclass(frozen=True,slots=True)
class SemanticRequest:
    request_id:str;correlation_id:str;source_identity:str;contract_id:str=CONTRACT_ID;contract_version:str=CONTRACT_VERSION;target_capability:str="semantic_inventory";metadata:Mapping[str,Any]=field(default_factory=dict)
    def __post_init__(self):object.__setattr__(self,"metadata",freeze(self.metadata))

@dataclass(frozen=True,slots=True)
class SemanticObject:
    object_id:str;object_name:str;category:str;description:str;aliases:tuple[str,...];visual_descriptors:tuple[Any,...];instance_frames:tuple[str,...];instance_images:tuple[str,...];recognition_history:tuple[Any,...];average_confidence:float;learning_date:str;last_updated:str;source_videos:tuple[str,...];source_frames:tuple[str,...];tags:tuple[str,...];relationships:tuple[Any,...]=();affordances:tuple[Any,...]=();semantic_score:float=0.0;version:str=SCHEMA_VERSION;metadata:Mapping[str,Any]=field(default_factory=dict)
    def __post_init__(self):
        for name in ("aliases","visual_descriptors","instance_frames","instance_images","recognition_history","source_videos","source_frames","tags","relationships","affordances"):object.__setattr__(self,name,tuple(freeze(getattr(self,name))))
        object.__setattr__(self,"metadata",freeze(self.metadata))

@dataclass(frozen=True,slots=True)
class InventoryStatistics:
    total_objects:int;categories:Mapping[str,int];tags:Mapping[str,int];average_semantic_score:float
    def __post_init__(self):object.__setattr__(self,"categories",freeze(self.categories));object.__setattr__(self,"tags",freeze(self.tags))

@dataclass(frozen=True,slots=True)
class SemanticInventory:
    version:str;generated_at:str;objects:tuple[SemanticObject,...];statistics:InventoryStatistics

@dataclass(frozen=True,slots=True)
class SemanticError:category:str;code:str;message:str;request_id:str;correlation_id:str;recoverable:bool=False
@dataclass(frozen=True,slots=True)
class ExplanationRecord:explanation_id:str;engine_id:str;correlation_id:str;subject:str;decision:str;supporting_facts:tuple[str,...];status:str
@dataclass(frozen=True,slots=True)
class LogRecord:engine_id:str;category:str;severity:str;correlation_id:str;message:str;metadata:Mapping[str,Any]=field(default_factory=dict)
@runtime_checkable
class LogSink(Protocol):
    def record(self,item:LogRecord)->Any:...
class NullLogSink:
    def record(self,item:LogRecord)->None:return None
@dataclass(frozen=True,slots=True)
class SemanticResponse:
    response_id:str;request_id:str;correlation_id:str;status:ResponseStatus;state:InventoryState;inventory:SemanticInventory|None=None;object:SemanticObject|None=None;statistics:InventoryStatistics|None=None;export:Mapping[str,Any]|None=None;errors:tuple[SemanticError,...]=();explanations:tuple[ExplanationRecord,...]=()

@runtime_checkable
class ObjectSource(Protocol):
    def get_all(self)->tuple[Mapping[str,Any],...]:...
@runtime_checkable
class InventoryStorage(Protocol):
    def load(self)->Mapping[str,Any]|None:...
    def save(self,payload:Mapping[str,Any])->None:...
@runtime_checkable
class SemanticInventoryContract(Protocol):
    @property
    def state(self)->InventoryState:...
    def initialize(self,request:SemanticRequest)->SemanticResponse:...
    def refresh(self,request:SemanticRequest)->SemanticResponse:...
    def get_object(self,request:SemanticRequest,object_id:str)->SemanticResponse:...
    def get_all_objects(self,request:SemanticRequest)->SemanticResponse:...
    def search(self,request:SemanticRequest,query:str="",category:str="",alias:str="",tag:str="")->SemanticResponse:...
    def get_statistics(self,request:SemanticRequest)->SemanticResponse:...
    def export_inventory(self,request:SemanticRequest)->SemanticResponse:...
    def close(self,request:SemanticRequest)->SemanticResponse:...
