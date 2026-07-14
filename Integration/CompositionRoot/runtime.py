"""Composed Core Platform runtime container."""
from __future__ import annotations
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any,Mapping

@dataclass(frozen=True,slots=True)
class RuntimeComponents:
    bootstrap:Any;kernel:Any;configuration:Any;registry:Any;event_bus:Any;memory:Any;logging:Any
    startup_results:Mapping[str,Any];activities:tuple[str,...]
    def __post_init__(self):
        object.__setattr__(self,"startup_results",MappingProxyType(dict(self.startup_results)));object.__setattr__(self,"activities",tuple(self.activities))
    @property
    def engines(self):
        return MappingProxyType({"Bootstrap":self.bootstrap,"Kernel":self.kernel,"Configuration":self.configuration,"Registry":self.registry,"Event Bus":self.event_bus,"Memory":self.memory,"Logging":self.logging})
