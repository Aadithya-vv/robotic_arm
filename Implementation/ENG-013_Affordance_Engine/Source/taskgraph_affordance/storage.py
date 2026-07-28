from __future__ import annotations
import json
from pathlib import Path
from threading import RLock
class JsonAffordanceStorage:
    def __init__(self,path:Path):self.path=Path(path);self._lock=RLock()
    def load(self):
        with self._lock:return json.loads(self.path.read_text(encoding="utf-8")) if self.path.is_file() else None
    def save(self,payload):
        with self._lock:
            self.path.parent.mkdir(parents=True,exist_ok=True);tmp=self.path.with_suffix(".tmp");tmp.write_text(json.dumps(payload,indent=2,ensure_ascii=False),encoding="utf-8");tmp.replace(self.path)
