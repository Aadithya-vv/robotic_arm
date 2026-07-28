"""Reverse-order TaskGraph v0.4 shutdown through public contracts."""
from taskgraph_bootstrap import ShutdownRequest
from taskgraph_camera import CameraRequest
from taskgraph_configuration import ConfigurationRequest
from taskgraph_event_bus import EventBusRequest
from taskgraph_kernel import KernelStopRequest
from taskgraph_logging import LoggingRequest
from taskgraph_memory import MemoryRequest
from taskgraph_registry import RegistryRequest
from taskgraph_scene import SceneRequest
from taskgraph_vision import VisionRequest
from taskgraph_semantic_inventory import SemanticRequest
from taskgraph_knowledge import KnowledgeRequest
from taskgraph_affordance import AffordanceRequest
from taskgraph_planner import PlannerRequest
from taskgraph_taskir import TaskIRRequest
from taskgraph_explainability import ExplainabilityRequest


def shutdown_runtime(runtime, correlation_id="m2-shutdown"):
    results = {}
    runtime.monitor.stop()
    results["explainability"] = runtime.explainability.close(ExplainabilityRequest("stop-explainability", correlation_id, "composition-root"))
    results["taskir"] = runtime.taskir.close(TaskIRRequest("stop-taskir", correlation_id, "composition-root"))
    results["planner"] = runtime.planner.close(PlannerRequest("stop-planner", correlation_id, "composition-root"))
    results["affordance"] = runtime.affordance.close(AffordanceRequest("stop-affordance", correlation_id, "composition-root"))
    results["knowledge"] = runtime.knowledge.close(KnowledgeRequest("stop-knowledge", correlation_id, "composition-root"))
    results["semantic_inventory"] = runtime.semantic_inventory.close(SemanticRequest("stop-semantic", correlation_id, "composition-root"))
    results["scene"] = runtime.scene.close(SceneRequest("stop-scene", correlation_id, "composition-root"))
    results["vision"] = runtime.vision.shutdown(VisionRequest("stop-vision", correlation_id, "composition-root"))
    results["camera"] = runtime.camera.shutdown(CameraRequest("stop-camera", correlation_id, "composition-root"))
    runtime.log_bridge.detach()
    results["logging"] = runtime.logging.stop(LoggingRequest("stop-logging", correlation_id, "composition-root"))
    results["memory"] = runtime.memory.dispose(MemoryRequest("stop-memory", correlation_id, "composition-root"))
    results["event_bus"] = runtime.event_bus.stop(EventBusRequest("stop-event-bus", correlation_id, "composition-root"))
    results["registry"] = runtime.registry.close(RegistryRequest("stop-registry", correlation_id, "composition-root"))
    results["configuration"] = runtime.configuration.shutdown(ConfigurationRequest("stop-configuration", correlation_id, "composition-root"))
    results["kernel"] = runtime.kernel.stop(KernelStopRequest("stop-kernel", correlation_id, "composition-root"))
    results["bootstrap"] = runtime.bootstrap.stop(ShutdownRequest("stop-bootstrap", correlation_id, "composition-root"))
    return results
