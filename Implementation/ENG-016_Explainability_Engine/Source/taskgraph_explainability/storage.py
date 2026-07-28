import json,os,tempfile
from pathlib import Path
class JsonExplanationStorage:
    def __init__(self,path):self.path=Path(path)
    def load(self):
        if not self.path.exists():return None
        with self.path.open("r",encoding="utf-8") as stream:return json.load(stream)
    def save(self,payload):
        self.path.parent.mkdir(parents=True,exist_ok=True);fd,name=tempfile.mkstemp(prefix=self.path.name+".",suffix=".tmp",dir=self.path.parent)
        try:
            with os.fdopen(fd,"w",encoding="utf-8") as stream:json.dump(payload,stream,indent=2,sort_keys=True,ensure_ascii=False);stream.flush();os.fsync(stream.fileno())
            os.replace(name,self.path)
        finally:
            if os.path.exists(name):os.unlink(name)
