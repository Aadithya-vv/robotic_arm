from __future__ import annotations
from dataclasses import dataclass,field
from pathlib import Path
from threading import Event
from typing import Any
from datetime import datetime

@dataclass
class RuntimeState:
    root:Path
    version:str="v1.1.5"
    backend:Any=None
    frontend:Any=None
    browser:Any=None
    diagnostics:dict[str,Any]=field(default_factory=dict)
    stopping:Event=field(default_factory=Event)
    backend_restarts:int=0
    frontend_restarts:int=0
    processes:dict[str,dict[str,Any]]=field(default_factory=dict)
    def track(self,name:str,process:Any,state:str="running")->None:
        self.processes[name]={"pid":process.pid,"start_time":datetime.now().isoformat(timespec="seconds"),"health":"starting","restart_count":self.processes.get(name,{}).get("restart_count",0),"state":state}
    def mark(self,name:str,**values:Any)->None:
        if name in self.processes:self.processes[name].update(values)
    @property
    def python(self)->Path:return self.root/".venv"/"Scripts"/"python.exe"
    @property
    def webapp(self)->Path:return self.root/"WebApp"
