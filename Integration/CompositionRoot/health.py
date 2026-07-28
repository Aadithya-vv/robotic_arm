"""Read-only health projection over ten public Engine lifecycle states."""
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class EngineHealth:
    name: str
    engine_id: str
    state: str
    version: str
    healthy: bool
    detail: str
    runtime_status: str
    last_activity: str


EXPECTED = {
    "Bootstrap": "ready", "Kernel": "running", "Configuration": "available",
    "Registry": "ready", "Event Bus": "accepting_events", "Memory": "ready",
    "Logging": "ready", "Camera": "ready", "Vision": "ready", "Scene": "active", "Semantic Inventory": "available", "Knowledge": "available", "Affordance": "available", "Planner": "available", "TaskIR Compiler": "available", "Explainability": "available",
}
IDS = {name: f"ENG-{index:03d}" for index, name in enumerate(EXPECTED, 1)}
IDS["Planner"] = "ENG-015"
IDS["TaskIR Compiler"] = "ENG-014"
IDS["Explainability"] = "ENG-016"


def collect_health(runtime):
    timestamp = datetime.now().isoformat(timespec="seconds")
    result = {}
    for name, engine in runtime.engines.items():
        state = engine.state.value
        healthy = state == EXPECTED[name]
        result[name] = EngineHealth(
            name, IDS[name], state, "1.0.0", healthy,
            "Operational" if healthy else f"Expected {EXPECTED[name]}",
            "Running" if healthy else "Attention", timestamp,
        )
    return result
