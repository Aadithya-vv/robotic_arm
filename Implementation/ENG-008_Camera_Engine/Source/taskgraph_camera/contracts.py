"""Public contracts for ENG-008 Camera Engine."""
from __future__ import annotations
from dataclasses import dataclass,field
from enum import Enum
from types import MappingProxyType
from typing import Any,Mapping,Protocol,runtime_checkable
ENGINE_ID="ENG-008";CONTRACT_ID="taskgraph.camera";CONTRACT_VERSION="1.0.0"
def freeze(v):
    if isinstance(v,Mapping):return MappingProxyType({k:freeze(x) for k,x in v.items()})
    if isinstance(v,(list,tuple)):return tuple(freeze(x) for x in v)
    if isinstance(v,(set,frozenset)):return frozenset(freeze(x) for x in v)
    return v
class CameraState(str,Enum):CLOSED="closed";OPENING="opening";READY="ready";CAPTURING="capturing";CLOSING="closing";FAILED="failed"
class ResponseStatus(str,Enum):SUCCEEDED="succeeded";REJECTED="rejected";FAILED="failed"
@dataclass(frozen=True,slots=True)
class CameraError:
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
class CameraRequest:
    request_id:str;correlation_id:str;source_identity:str;causation_id:str|None=None;timestamp_context:str|None=None;expectation:str="response_required";contract_id:str=CONTRACT_ID;contract_version:str=CONTRACT_VERSION;target_capability:str="camera";metadata:Mapping[str,Any]=field(default_factory=dict)
    def __post_init__(self):object.__setattr__(self,"metadata",freeze(self.metadata))
@dataclass(frozen=True,slots=True)
class CameraDevice:
    device_id:str;display_name:str;provider_id:str;available:bool=True;metadata:Mapping[str,Any]=field(default_factory=dict)
    def __post_init__(self):object.__setattr__(self,"metadata",freeze(self.metadata))
@dataclass(frozen=True,slots=True)
class CameraConfiguration:
    provider_id:str;device_id:str;width:int=640;height:int=480;frames_per_second:int=30;pixel_format:str="bgr8";provider_settings:Mapping[str,Any]=field(default_factory=dict)
    def __post_init__(self):object.__setattr__(self,"provider_settings",freeze(self.provider_settings))
@dataclass(frozen=True,slots=True)
class ProviderResult:
    succeeded:bool;error_code:str|None=None;error_summary:str|None=None;metadata:Mapping[str,Any]=field(default_factory=dict)
    def __post_init__(self):object.__setattr__(self,"metadata",freeze(self.metadata))
@dataclass(frozen=True,slots=True)
class ProviderDiscovery:
    succeeded:bool;devices:tuple[CameraDevice,...]=();error_code:str|None=None;error_summary:str|None=None
    def __post_init__(self):object.__setattr__(self,"devices",tuple(self.devices))
@dataclass(frozen=True,slots=True)
class ProviderFrame:
    succeeded:bool;data:bytes=b"";width:int=0;height:int=0;channels:int=0;pixel_format:str="";timestamp_context:str|None=None;metadata:Mapping[str,Any]=field(default_factory=dict);error_code:str|None=None;error_summary:str|None=None
    def __post_init__(self):object.__setattr__(self,"data",bytes(self.data));object.__setattr__(self,"metadata",freeze(self.metadata))
@runtime_checkable
class CameraProvider(Protocol):
    @property
    def provider_id(self)->str:...
    def discover(self)->ProviderDiscovery:...
    def open(self,configuration:CameraConfiguration)->ProviderResult:...
    def acquire(self)->ProviderFrame:...
    def diagnostics(self)->Mapping[str,Any]:...
    def close(self)->ProviderResult:...
@dataclass(frozen=True,slots=True)
class CameraObservation:
    observation_id:str;sequence:int;device_id:str;provider_id:str;correlation_id:str;data:bytes;width:int;height:int;channels:int;pixel_format:str;timestamp_context:str|None;metadata:Mapping[str,Any]=field(default_factory=dict);contract_version:str=CONTRACT_VERSION
    def __post_init__(self):object.__setattr__(self,"data",bytes(self.data));object.__setattr__(self,"metadata",freeze(self.metadata))
@dataclass(frozen=True,slots=True)
class CameraDiagnostics:
    state:CameraState;provider_id:str|None;device_id:str|None;frames_acquired:int;provider_diagnostics:Mapping[str,Any];last_error_code:str|None=None
    def __post_init__(self):object.__setattr__(self,"provider_diagnostics",freeze(self.provider_diagnostics))
@dataclass(frozen=True,slots=True)
class CameraResponse:
    response_id:str;request_id:str;correlation_id:str;status:ResponseStatus;state:CameraState;devices:tuple[CameraDevice,...]=();observation:CameraObservation|None=None;diagnostics:CameraDiagnostics|None=None;errors:tuple[CameraError,...]=();explanations:tuple[ExplanationRecord,...]=();metadata:Mapping[str,Any]=field(default_factory=dict);contract_id:str=CONTRACT_ID;contract_version:str=CONTRACT_VERSION;source_identity:str=ENGINE_ID
    def __post_init__(self):object.__setattr__(self,"devices",tuple(self.devices));object.__setattr__(self,"errors",tuple(self.errors));object.__setattr__(self,"explanations",tuple(self.explanations));object.__setattr__(self,"metadata",freeze(self.metadata))
@runtime_checkable
class CameraContract(Protocol):
    @property
    def state(self)->CameraState:...
    def discover(self,request:CameraRequest)->CameraResponse:...
    def initialize(self,request:CameraRequest,configuration:CameraConfiguration)->CameraResponse:...
    def acquire(self,request:CameraRequest)->CameraResponse:...
    def diagnostics(self,request:CameraRequest)->CameraResponse:...
    def shutdown(self,request:CameraRequest)->CameraResponse:...
