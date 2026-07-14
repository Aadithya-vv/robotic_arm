"""Provider adapters used exclusively by the repository Composition Root."""
from __future__ import annotations
from threading import RLock
from typing import Any, Mapping
from taskgraph_bootstrap import BootstrapError
from taskgraph_configuration import SourceLoadResult

class StaticConfigurationSource:
    def __init__(self, settings: Mapping[str, Any]): self._settings=dict(settings)
    def load(self, request):
        del request
        return SourceLoadResult(True,self._settings,{"provider":"composition.static","local":True})

class StartupCapabilityProbe:
    def __init__(self, capability_id: str, available=True): self._id=capability_id;self._available=available
    @property
    def capability_id(self): return self._id
    def validate_startup(self, environment):
        del environment
        return () if self._available else (BootstrapError("dependency_unavailable","composition.capability.unavailable",f"provider unavailable: {self._id}"),)

class BootstrapReadinessAdapter:
    def __init__(self, bootstrap): self._bootstrap=bootstrap
    def is_ready(self): return self._bootstrap.state.value=="ready" and self._bootstrap.runtime is not None
    def runtime_metadata(self):
        value=self._bootstrap.runtime
        return {} if value is None else {"state":value.state.value,"capability_ids":value.capability_ids,"contract_version":value.contract_version}

class DeferredLogSink:
    """Buffer bootstrap diagnostics until ENG-007 is ready, then forward structurally."""
    def __init__(self): self._target=None;self._buffer=[];self._lock=RLock()
    def record(self, record):
        with self._lock:
            if self._target is None:self._buffer.append(record)
            else:self._target.record(record)
    def attach(self, target):
        with self._lock:
            self._target=target
            pending=tuple(self._buffer);self._buffer.clear()
            for record in pending:target.record(record)
    @property
    def pending_count(self):
        with self._lock:return len(self._buffer)

class UnavailableCapabilityStub:
    def __init__(self, capability_id):self._id=capability_id
    @property
    def capability_id(self):return self._id
    def validate_startup(self, environment):
        del environment
        return (BootstrapError("dependency_unavailable","composition.future.unavailable",f"future provider unavailable: {self._id}"),)
