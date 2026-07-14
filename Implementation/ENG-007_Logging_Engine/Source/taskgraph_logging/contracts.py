"""Public contracts for ENG-007 Logging Engine."""
from __future__ import annotations
from dataclasses import dataclass,field
from enum import Enum
from types import MappingProxyType
from typing import Any,Mapping,Protocol,runtime_checkable
ENGINE_ID="ENG-007";CONTRACT_ID="taskgraph.logging";CONTRACT_VERSION="1.0.0"
def freeze(v):
    if isinstance(v,Mapping):return MappingProxyType({k:freeze(x) for k,x in v.items()})
    if isinstance(v,(list,tuple)):return tuple(freeze(x) for x in v)
    if isinstance(v,(set,frozenset)):return frozenset(freeze(x) for x in v)
    return v
class LoggingState(str,Enum):CREATED="created";CONFIGURING="configuring";READY="ready";RECORDING="recording";FLUSHING="flushing";STOPPED="stopped";DEGRADED="degraded"
class Severity(str,Enum):TRACE="trace";DEBUG="debug";INFO="info";WARNING="warning";ERROR="error";CRITICAL="critical"
SEVERITY_RANK={Severity.TRACE:0,Severity.DEBUG:1,Severity.INFO:2,Severity.WARNING:3,Severity.ERROR:4,Severity.CRITICAL:5}
class ResponseStatus(str,Enum):SUCCEEDED="succeeded";REJECTED="rejected";FAILED="failed"
@dataclass(frozen=True,slots=True)
class LoggingError:
    category:str;code:str;message:str;request_id:str;correlation_id:str;recoverable:bool=False;context:Mapping[str,Any]=field(default_factory=dict)
    def __post_init__(self):object.__setattr__(self,"context",freeze(self.context))
@dataclass(frozen=True,slots=True)
class ExplanationRecord:
    explanation_id:str;engine_id:str;correlation_id:str;subject:str;decision:str;supporting_facts:tuple[str,...];status:str;metadata:Mapping[str,Any]=field(default_factory=dict)
    def __post_init__(self):object.__setattr__(self,"supporting_facts",tuple(self.supporting_facts));object.__setattr__(self,"metadata",freeze(self.metadata))
@dataclass(frozen=True,slots=True)
class LoggingRequest:
    request_id:str;correlation_id:str;source_identity:str;causation_id:str|None=None;timestamp_context:str|None=None;expectation:str="response_required";contract_id:str=CONTRACT_ID;contract_version:str=CONTRACT_VERSION;target_capability:str="logging";metadata:Mapping[str,Any]=field(default_factory=dict)
    def __post_init__(self):object.__setattr__(self,"metadata",freeze(self.metadata))
@dataclass(frozen=True,slots=True)
class LogInput:
    source_identity:str;category:str;severity:Severity|str;correlation_id:str;message:str;timestamp_context:str|None=None;metadata:Mapping[str,Any]=field(default_factory=dict)
    def __post_init__(self):object.__setattr__(self,"metadata",freeze(self.metadata))
@dataclass(frozen=True,slots=True)
class StructuredLogRecord:
    record_id:str;sequence:int;source_identity:str;category:str;severity:Severity;correlation_id:str;message:str;timestamp_context:str|None;metadata:Mapping[str,Any]=field(default_factory=dict);contract_version:str=CONTRACT_VERSION
    def __post_init__(self):object.__setattr__(self,"metadata",freeze(self.metadata))
@dataclass(frozen=True,slots=True)
class SinkResult:
    succeeded:bool;error_summary:str|None=None;metadata:Mapping[str,Any]=field(default_factory=dict)
    def __post_init__(self):object.__setattr__(self,"metadata",freeze(self.metadata))
@runtime_checkable
class RuntimeLogSink(Protocol):
    def write(self,record:StructuredLogRecord)->SinkResult:...
    def flush(self)->SinkResult:...
class NullRuntimeLogSink:
    def write(self,record):del record;return SinkResult(True)
    def flush(self):return SinkResult(True)
@dataclass(frozen=True,slots=True)
class LoggingPolicy:
    minimum_severity:Severity=Severity.INFO;allowed_categories:tuple[str,...]=();maximum_records:int=10000
    def __post_init__(self):object.__setattr__(self,"allowed_categories",tuple(self.allowed_categories))
@dataclass(frozen=True,slots=True)
class LogFilter:
    minimum_severity:Severity|None=None;categories:tuple[str,...]=();source_identities:tuple[str,...]=();correlation_id:str|None=None
    def __post_init__(self):object.__setattr__(self,"categories",tuple(self.categories));object.__setattr__(self,"source_identities",tuple(self.source_identities))
@dataclass(frozen=True,slots=True)
class LoggingSnapshot:
    snapshot_id:str;generation:int;state:LoggingState;records:tuple[StructuredLogRecord,...];accepted_count:int;filtered_count:int;rejected_count:int;correlation_id:str
    def __post_init__(self):object.__setattr__(self,"records",tuple(self.records))
@dataclass(frozen=True,slots=True)
class LoggingResponse:
    response_id:str;request_id:str;correlation_id:str;status:ResponseStatus;state:LoggingState;record:StructuredLogRecord|None=None;snapshot:LoggingSnapshot|None=None;formatted_records:tuple[str,...]=();errors:tuple[LoggingError,...]=();explanations:tuple[ExplanationRecord,...]=();metadata:Mapping[str,Any]=field(default_factory=dict);contract_id:str=CONTRACT_ID;contract_version:str=CONTRACT_VERSION;source_identity:str=ENGINE_ID
    def __post_init__(self):object.__setattr__(self,"formatted_records",tuple(self.formatted_records));object.__setattr__(self,"errors",tuple(self.errors));object.__setattr__(self,"explanations",tuple(self.explanations));object.__setattr__(self,"metadata",freeze(self.metadata))
class LoggingDeliveryError(RuntimeError):pass
@runtime_checkable
class LoggingContract(Protocol):
    @property
    def state(self)->LoggingState:...
    def initialize(self,request:LoggingRequest)->LoggingResponse:...
    def record_log(self,request:LoggingRequest,entry:LogInput)->LoggingResponse:...
    def query(self,request:LoggingRequest,filter:LogFilter|None=None)->LoggingResponse:...
    def format(self,request:LoggingRequest,filter:LogFilter|None=None)->LoggingResponse:...
    def stop(self,request:LoggingRequest)->LoggingResponse:...
