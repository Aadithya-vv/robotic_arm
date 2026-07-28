"""Composed TaskGraph v0.4 runtime container."""
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping


@dataclass(frozen=True, slots=True)
class RuntimeComponents:
    bootstrap: Any
    kernel: Any
    configuration: Any
    registry: Any
    event_bus: Any
    memory: Any
    logging: Any
    camera: Any
    vision: Any
    scene: Any
    semantic_inventory: Any
    knowledge: Any
    affordance: Any
    planner: Any
    taskir: Any
    explainability: Any
    perception: Any
    object_library: Any
    monitor: Any
    model_manager: Any
    video_workspace: Any
    log_bridge: Any
    startup_results: Mapping[str, Any]
    activities: tuple[str, ...]

    def __post_init__(self):
        object.__setattr__(self, "startup_results", MappingProxyType(dict(self.startup_results)))
        object.__setattr__(self, "activities", tuple(self.activities))

    @property
    def engines(self):
        return MappingProxyType({
            "Bootstrap": self.bootstrap, "Kernel": self.kernel,
            "Configuration": self.configuration, "Registry": self.registry,
            "Event Bus": self.event_bus, "Memory": self.memory,
            "Logging": self.logging, "Camera": self.camera,
            "Vision": self.vision, "Scene": self.scene,
            "Semantic Inventory": self.semantic_inventory,
            "Knowledge": self.knowledge,
            "Affordance": self.affordance,
            "Planner": self.planner,
            "TaskIR Compiler": self.taskir,
            "Explainability": self.explainability,
        })

    def stop(self, correlation_id="runtime-stop"):
        """Backward-compatible convenience implemented through public shutdown contracts."""
        from shutdown import shutdown_runtime
        return shutdown_runtime(self, correlation_id)
