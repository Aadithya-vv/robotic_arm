"""Public contracts for ENG-006 Memory Engine."""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Any, Mapping, Protocol, runtime_checkable

ENGINE_ID="ENG-006"; CONTRACT_ID="taskgraph.memory"; CONTRACT_VERSION="1.0.0"
def freeze(value: Any)->Any:
    if isinstance(value,Mapping):return MappingProxyType({k:freeze(v) for k,v in value.items()})
    if isinstance(value,(list,tuple)):return tuple(freeze(v) for v in value)
    if isinstance(value,(set,frozenset)):return frozenset(freeze(v) for v in value)
    return value

class MemoryState(str,Enum):CREATED="created";READY="ready";ACTIVE="active";CLEANING="cleaning";DISPOSED="disposed";FAILED="failed"
class SessionState(str,Enum):OPEN="open";CLOSED="closed"
class Visibility(str,Enum):OWNER="owner";SHARED="shared"
class ResponseStatus(str,Enum):SUCCEEDED="succeeded";REJECTED="rejected";FAILED="failed"

@dataclass(frozen=True,slots=True)
class MemoryError:
    category:str;code:str;message:str;request_id:str;correlation_id:str;recoverable:bool=False;context:Mapping[str,Any]=field(default_factory=dict)
    def __post_init__(self):object.__setattr__(self,"context",freeze(self.context))
@dataclass(frozen=True,slots=True)
class ExplanationRecord:
    explanation_id:str;engine_id:str;correlation_id:str;subject:str;decision:str;supporting_facts:tuple[str,...];status:str;metadata:Mapping[str,Any]=field(default_factory=dict)
    def __post_init__(self):object.__setattr__(self,"supporting_facts",tuple(self.supporting_facts));object.__setattr__(self,"metadata",freeze(self.metadata))
@dataclass(frozen=True,slots=True)
class LogRecord:
    engine_id:str;category:str;severity:str;correlation_id:str;message:str;metadata:Mapping[str,Any]=field(default_factory=dict)
    def __post_init__(self):object.__setattr__(self,"metadata",freeze(self.metadata))
@runtime_checkable
class LogSink(Protocol):
    def record(self,record:LogRecord)->None:...
class NullLogSink:
    def record(self,record):del record

@dataclass(frozen=True,slots=True)
class MemoryPolicy:
    maximum_sessions:int|None=None;maximum_entries_per_session:int|None=None
@dataclass(frozen=True,slots=True)
class MemoryRequest:
    request_id:str;correlation_id:str;source_identity:str;causation_id:str|None=None;timestamp_context:str|None=None
    expectation:str="response_required";contract_id:str=CONTRACT_ID;contract_version:str=CONTRACT_VERSION;target_capability:str="memory"
    metadata:Mapping[str,Any]=field(default_factory=dict)
    def __post_init__(self):object.__setattr__(self,"metadata",freeze(self.metadata))
@dataclass(frozen=True,slots=True)
class MemoryRecord:
    record_id:str;session_id:str;key:str;owner_id:str;value:Any;visibility:Visibility;revision:int;correlation_id:str;provenance:Mapping[str,Any]=field(default_factory=dict)
    def __post_init__(self):object.__setattr__(self,"value",freeze(self.value));object.__setattr__(self,"provenance",freeze(self.provenance))
@dataclass(frozen=True,slots=True)
class SessionSnapshot:
    snapshot_id:str;session_id:str;owner_id:str;state:SessionState;generation:int;records:Mapping[str,MemoryRecord];correlation_id:str
    def __post_init__(self):object.__setattr__(self,"records",MappingProxyType(dict(self.records)))
@dataclass(frozen=True,slots=True)
class MemorySnapshot:
    snapshot_id:str;generation:int;state:MemoryState;sessions:Mapping[str,SessionSnapshot];correlation_id:str
    def __post_init__(self):object.__setattr__(self,"sessions",MappingProxyType(dict(self.sessions)))
@dataclass(frozen=True,slots=True)
class MemoryResponse:
    response_id:str;request_id:str;correlation_id:str;status:ResponseStatus;state:MemoryState
    record:MemoryRecord|None=None;session:SessionSnapshot|None=None;snapshot:MemorySnapshot|None=None
    errors:tuple[MemoryError,...]=();explanations:tuple[ExplanationRecord,...]=();metadata:Mapping[str,Any]=field(default_factory=dict)
    contract_id:str=CONTRACT_ID;contract_version:str=CONTRACT_VERSION;source_identity:str=ENGINE_ID
    def __post_init__(self):object.__setattr__(self,"errors",tuple(self.errors));object.__setattr__(self,"explanations",tuple(self.explanations));object.__setattr__(self,"metadata",freeze(self.metadata))
@runtime_checkable
class MemoryContract(Protocol):
    @property
    def state(self)->MemoryState:...
    def initialize(self,request:MemoryRequest)->MemoryResponse:...
    def create_session(self,request:MemoryRequest,session_id:str,owner_id:str)->MemoryResponse:...
    def put(self,request:MemoryRequest,session_id:str,key:str,value:Any,visibility:Visibility=Visibility.OWNER,provenance:Mapping[str,Any]|None=None)->MemoryResponse:...
    def get(self,request:MemoryRequest,session_id:str,key:str)->MemoryResponse:...
    def delete(self,request:MemoryRequest,session_id:str,key:str)->MemoryResponse:...
    def cleanup_session(self,request:MemoryRequest,session_id:str)->MemoryResponse:...
    def close_session(self,request:MemoryRequest,session_id:str)->MemoryResponse:...
    def snapshot(self,request:MemoryRequest,session_id:str|None=None)->MemoryResponse:...
    def dispose(self,request:MemoryRequest)->MemoryResponse:...
