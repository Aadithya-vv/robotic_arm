"""Read-only health projection over public Engine lifecycle state."""
from dataclasses import dataclass
@dataclass(frozen=True,slots=True)
class EngineHealth:
    name:str;engine_id:str;state:str;version:str;healthy:bool;detail:str
EXPECTED={"Bootstrap":"ready","Kernel":"running","Configuration":"available","Registry":"ready","Event Bus":"accepting_events","Memory":"ready","Logging":"ready"}
IDS={"Bootstrap":"ENG-001","Kernel":"ENG-002","Configuration":"ENG-003","Registry":"ENG-004","Event Bus":"ENG-005","Memory":"ENG-006","Logging":"ENG-007"}
def collect_health(runtime):
    result={}
    for name,engine in runtime.engines.items():
        state=engine.state.value;healthy=state==EXPECTED[name];result[name]=EngineHealth(name,IDS[name],state,"1.0.0",healthy,"Operational" if healthy else f"Expected {EXPECTED[name]}")
    return result
