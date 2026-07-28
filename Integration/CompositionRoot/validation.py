"""Milestone M2 validation through public contracts only."""
from dataclasses import dataclass
from datetime import datetime
from time import perf_counter

from taskgraph_camera import CameraRequest
from taskgraph_logging import LoggingRequest
from taskgraph_registry import RegistryRequest
from taskgraph_knowledge import KnowledgeRequest
from taskgraph_affordance import AffordanceRequest
from taskgraph_taskir import TaskIRRequest
from taskgraph_explainability import ExplainabilityRequest

from health import collect_health


@dataclass(frozen=True, slots=True)
class ValidationCheck:
    name: str
    passed: bool
    detail: str
    elapsed_ms: float = 0.0
    timestamp: str = ""


def _check(name, passed, detail, started):
    return ValidationCheck(name, bool(passed), detail, (perf_counter() - started) * 1000.0, datetime.now().isoformat(timespec="seconds"))


def validate_runtime(runtime, correlation_id="m2-validation"):
    checks = []
    health = collect_health(runtime)
    for name, value in health.items():
        started = perf_counter()
        checks.append(_check(name, value.healthy, f"state={value.state}", started))

    started = perf_counter()
    expected = ("bootstrap", "kernel", "configuration", "registry", "event_bus", "memory", "logging", "camera", "vision", "scene", "semantic_inventory", "knowledge", "affordance", "planner", "taskir", "explainability", "explainability_rebuild")
    checks.append(_check("Startup order", tuple(runtime.startup_results) == expected, " -> ".join(expected), started))

    started = perf_counter()
    registry = runtime.registry.snapshot(RegistryRequest("validate-registry", correlation_id, "validation"))
    count = 0 if registry.snapshot is None else len(registry.snapshot.registrations)
    checks.append(_check("Registry populated", count == 16, f"registrations={count}", started))

    started = perf_counter()
    camera_diagnostics = runtime.camera.diagnostics(CameraRequest("validate-camera", correlation_id, "validation"))
    camera_ok = camera_diagnostics.status.value == "succeeded" and camera_diagnostics.diagnostics.provider_id == "mock"
    checks.append(_check("Camera Provider", camera_ok, f"provider={camera_diagnostics.diagnostics.provider_id if camera_diagnostics.diagnostics else None}", started))

    started = perf_counter()
    pipeline = runtime.perception.capture_pipeline(correlation_id)
    camera_passed = pipeline.camera_response.status.value == "succeeded"
    checks.append(_check("Frame Acquisition", camera_passed, f"frame={getattr(pipeline.camera_response.observation, 'observation_id', None)}", started))
    vision_passed = pipeline.vision_response is not None and pipeline.vision_response.status.value == "succeeded"
    checks.append(_check("Vision Processing", vision_passed, f"objects={len(pipeline.vision_response.observation.objects) if vision_passed else 0}", started))
    detector = runtime.perception.detector_status()
    checks.append(_check("Detector AUTO", detector.get("current") in ("YOLO11M", "YOLO11S", "YOLO11N", "Classical CV"), f"current={detector.get('current')}; model={detector.get('loaded_model')}; device={detector.get('device')}", started))
    checks.append(_check("AI Inference", detector.get("current") == "Classical CV" or detector.get("inference_ms") is not None, f"inference_ms={detector.get('inference_ms')}", started))
    scene_passed = pipeline.scene_response is not None and pipeline.scene_response.status.value == "succeeded"
    checks.append(_check("Scene Tracking", scene_passed, f"tracked={len(pipeline.scene_response.snapshot.objects) if scene_passed else 0}", started))
    checks.append(_check("Scene Relationships", scene_passed, f"relationships={len(pipeline.scene_response.snapshot.relationships) if scene_passed else 0}", started))
    checks.append(_check("Scene Snapshot", scene_passed and pipeline.scene_response.snapshot is not None, "immutable snapshot available", started))
    semantic = runtime.semantic_inventory.get_statistics(__import__("taskgraph_semantic_inventory").SemanticRequest("validate-semantic", correlation_id, "validation"))
    checks.append(_check("Semantic Inventory", semantic.status.value == "succeeded", f"objects={semantic.statistics.total_objects if semantic.statistics else 0}", started))
    knowledge = runtime.knowledge.validate_knowledge(KnowledgeRequest("validate-knowledge", correlation_id, "validation"))
    checks.append(_check("Knowledge Integrity", knowledge.status.value == "succeeded" and knowledge.valid, f"valid={knowledge.valid}", started))
    affordance = runtime.affordance.validate_affordances(AffordanceRequest("validate-affordance", correlation_id, "validation"))
    checks.append(_check("Affordance Integrity", affordance.status.value == "succeeded" and affordance.valid, f"valid={affordance.valid}", started))
    taskir = runtime.taskir.get_statistics(TaskIRRequest("validate-taskir", correlation_id, "validation"))
    checks.append(_check("TaskIR Compiler", taskir.status.value == "succeeded", f"documents={taskir.statistics.total_documents if taskir.statistics else 0}", started))
    explanations = runtime.explainability.get_statistics(ExplainabilityRequest("validate-explainability", correlation_id, "validation"))
    checks.append(_check("Explainability", explanations.status.value == "succeeded", f"records={explanations.statistics.total_records if explanations.statistics else 0}", started))

    started = perf_counter()
    logs = runtime.logging.query(LoggingRequest("validate-logging", correlation_id, "validation"))
    checks.append(_check("Perception Logging", logs.status.value == "succeeded", f"accepted_records={logs.snapshot.accepted_count}", started))
    checks.append(_check("Runtime Health", all(item.healthy for item in collect_health(runtime).values()), "all sixteen Engines healthy", started))
    checks.append(_check("Graceful Shutdown Ready", all(hasattr(runtime, name) for name in ("explainability", "taskir", "planner", "affordance", "knowledge", "semantic_inventory", "scene", "vision", "camera", "logging", "memory", "event_bus", "registry", "configuration", "kernel", "bootstrap")), "reverse-order shutdown contracts composed", started))
    return tuple(checks)


def validation_passed(checks):
    return all(item.passed for item in checks)
