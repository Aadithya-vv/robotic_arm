"""Replaceable JSON storage provider for ENG-011."""
from __future__ import annotations
import json
from pathlib import Path
from threading import RLock
from typing import Any,Mapping

class JsonInventoryStorage:
    def __init__(self,path:Path):self.path=Path(path);self._lock=RLock()
    def load(self)->Mapping[str,Any]|None:
        with self._lock:
            if not self.path.is_file():return None
            return json.loads(self.path.read_text(encoding="utf-8"))
    def save(self,payload:Mapping[str,Any])->None:
        with self._lock:
            self.path.parent.mkdir(parents=True,exist_ok=True);temporary=self.path.with_suffix(".tmp")
            temporary.write_text(json.dumps(payload,indent=2,ensure_ascii=False),encoding="utf-8");temporary.replace(self.path)
