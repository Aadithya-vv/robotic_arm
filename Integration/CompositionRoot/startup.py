"""Construct TaskGraph v0.4 in the approved ten-Engine startup order."""
from pathlib import Path
import sys

_ROOT = Path(__file__).resolve().parents[2]
for _source in sorted((_ROOT / "Implementation").glob("ENG-*_Engine/Source")):
    if str(_source) not in sys.path:
        sys.path.insert(0, str(_source))
from taskgraph_bootstrap import BootstrapConfiguration, BootstrapEngine, BootstrapRequest
from taskgraph_camera import CameraConfiguration, CameraEngine, CameraProviderCatalog, CameraRequest, MockCameraProvider, OpenCVCameraProvider
from taskgraph_configuration import ConfigurationEngine, ConfigurationRequest, ConfigurationSchema, SettingRule, ValueKind
from taskgraph_event_bus import EventBusEngine, EventBusRequest
from taskgraph_kernel import KernelEngine, KernelStartRequest
from taskgraph_logging import LoggingEngine, LoggingRequest
from taskgraph_memory import MemoryEngine, MemoryRequest
from taskgraph_registry import EngineRegistration, RegistryEngine, RegistryRequest
from taskgraph_scene import MockSceneTracker, SceneConfiguration, SceneEngine, SceneRequest
from taskgraph_vision import VisionConfiguration, VisionEngine, VisionRequest
from taskgraph_semantic_inventory import JsonInventoryStorage, SemanticInventoryEngine, SemanticRequest
from taskgraph_knowledge import JsonKnowledgeStorage, KnowledgeConfiguration, KnowledgeEngine, KnowledgeRequest
from taskgraph_affordance import AffordanceConfiguration, AffordanceEngine, AffordanceRequest, JsonAffordanceStorage
from taskgraph_planner import PlannerConfiguration, PlannerRequest, SemanticPlannerEngine, JsonSemanticPlanStorage
from taskgraph_taskir import JsonTaskIRStorage, TaskIRCompilerEngine, TaskIRConfiguration, TaskIRRequest
from taskgraph_explainability import ExplainabilityConfiguration, ExplainabilityEngine, ExplainabilityRequest, JsonExplanationStorage

from perception import PerceptionController
from monitoring import RuntimeMonitor
from object_library import ObjectLibrary
from model_manager import ModelManager
from providers import BootstrapReadinessAdapter, DeferredLogSink, StartupCapabilityProbe, StaticConfigurationSource
from runtime import RuntimeComponents
from vision_provider import AdaptiveVisionProcessor
from video_workflow import VideoWorkspace
from semantic_inventory import ObjectLibrarySemanticSource
from knowledge import SemanticInventoryKnowledgeSource
from affordance import KnowledgeAffordanceSource
from planner import KnowledgePlannerSource, AffordancePlannerSource
from explainability import SemanticPipelineArtifactSource


class StartupFailure(RuntimeError):
    def __init__(self, stage, response):
        self.stage = stage
        self.response = response
        super().__init__(f"startup failed at {stage}: {getattr(response, 'errors', ())}")


def _require(stage, response, results, activities):
    results[stage] = response
    activities.append(f"{stage}: {response.status.value}")
    if response.status.value != "succeeded":
        raise StartupFailure(stage, response)


def create_runtime(settings=None, correlation_id="m2-startup"):
    settings = dict(settings or {"runtime_mode": "local", "release": "v0.4"})
    results, activities = {}, []
    logs = DeferredLogSink()

    logging = LoggingEngine()
    configuration = ConfigurationEngine(
        StaticConfigurationSource(settings),
        ConfigurationSchema({"runtime_mode": SettingRule(ValueKind.STRING, True), "release": SettingRule(ValueKind.STRING, True)}),
        log_sink=logs,
    )
    registry = RegistryEngine(log_sink=logs)
    event_bus = EventBusEngine(log_sink=logs)
    memory = MemoryEngine(log_sink=logs)
    mock_frame = bytes((index % 256 for index in range(640 * 480 * 3)))
    camera_catalog = CameraProviderCatalog((MockCameraProvider(frames=(mock_frame,)), OpenCVCameraProvider()))
    camera = CameraEngine(camera_catalog, log_sink=logs)
    scene = SceneEngine((MockSceneTracker(),), log_sink=logs)

    capability_ids = ("configuration", "registry", "event_bus", "memory", "logging", "camera", "vision", "scene", "semantic_inventory", "knowledge", "affordance", "planner", "taskir", "explainability")
    probes = tuple(StartupCapabilityProbe(item) for item in capability_ids)
    bootstrap = BootstrapEngine(probes, configuration=BootstrapConfiguration(required_capabilities=capability_ids), log_sink=logs)
    kernel = KernelEngine(BootstrapReadinessAdapter(bootstrap), log_sink=logs)

    _require("bootstrap", bootstrap.start(BootstrapRequest("m2-bootstrap", correlation_id, "composition-root", {"mode": "local"})), results, activities)
    _require("kernel", kernel.start(KernelStartRequest("m2-kernel", correlation_id, "composition-root")), results, activities)
    _require("configuration", configuration.load(ConfigurationRequest("m2-configuration", correlation_id, "composition-root")), results, activities)
    _require("registry", registry.open(RegistryRequest("m2-registry-open", correlation_id, "composition-root")), results, activities)

    registrations = (
        ("ENG-001", "Bootstrap Engine", "taskgraph.bootstrap", "runtime.bootstrap"),
        ("ENG-002", "Kernel Engine", "taskgraph.kernel", "runtime.coordination"),
        ("ENG-003", "Configuration Engine", "taskgraph.configuration", "configuration"),
        ("ENG-004", "Registry Engine", "taskgraph.registry", "registry"),
        ("ENG-005", "Event Bus Engine", "taskgraph.event_bus", "events"),
        ("ENG-006", "Memory Engine", "taskgraph.memory", "memory"),
        ("ENG-007", "Logging Engine", "taskgraph.logging", "logging"),
        ("ENG-008", "Camera Engine", "taskgraph.camera", "camera"),
        ("ENG-009", "Vision Engine", "taskgraph.vision", "vision"),
        ("ENG-010", "Scene Engine", "taskgraph.scene", "scene"),
        ("ENG-011", "Semantic Inventory Engine", "taskgraph.semantic-inventory", "semantic_inventory"),
        ("ENG-012", "Knowledge Engine", "taskgraph.knowledge", "knowledge"),
        ("ENG-013", "Affordance Engine", "taskgraph.affordance", "affordance"),
        ("ENG-015", "Semantic Planner Engine", "taskgraph.semantic-planner", "planner"),
        ("ENG-014", "TaskIR Compiler Engine", "taskgraph.taskir-compiler", "taskir"),
        ("ENG-016", "Explainability Engine", "taskgraph.explainability", "explainability"),
    )
    for engine_id, name, contract, capability in registrations:
        response = registry.register(
            RegistryRequest(f"m2-register-{engine_id}", correlation_id, "composition-root"),
            EngineRegistration(engine_id, name, contract, "1.0.0", (capability,)),
        )
        if response.status.value != "succeeded":
            raise StartupFailure(f"register_{engine_id}", response)
    ready = registry.mark_ready(RegistryRequest("m2-registry-ready", correlation_id, "composition-root"))
    if ready.status.value != "succeeded":
        raise StartupFailure("registry_ready", ready)

    _require("event_bus", event_bus.start(EventBusRequest("m2-event-bus", correlation_id, "composition-root")), results, activities)
    _require("memory", memory.initialize(MemoryRequest("m2-memory", correlation_id, "composition-root")), results, activities)
    _require("logging", logging.initialize(LoggingRequest("m2-logging", correlation_id, "composition-root")), results, activities)
    logs.attach(logging)

    monitor = RuntimeMonitor()
    monitor.start()
    object_library = ObjectLibrary(memory, monitor, _ROOT / "Assets" / "ObjectLibrary" / "objects.json")
    library_response = object_library.initialize()
    if library_response.status.value != "succeeded": raise StartupFailure("object_library", library_response)
    model_manager = ModelManager(_ROOT)
    model_manager.ensure_all()
    adaptive_processor = AdaptiveVisionProcessor(model_manager, object_library, "AUTO")
    vision = VisionEngine((adaptive_processor,), log_sink=logs)

    camera_configuration = CameraConfiguration("mock", "mock-camera-0", 640, 480, 10, "bgr8")
    _require("camera", camera.initialize(CameraRequest("m2-camera", correlation_id, "composition-root"), camera_configuration), results, activities)
    _require("vision", vision.initialize(VisionRequest("m2-vision", correlation_id, "composition-root"), VisionConfiguration("adaptive", confidence_threshold=0.0)), results, activities)
    _require("scene", scene.initialize(SceneRequest("m2-scene", correlation_id, "composition-root"), SceneConfiguration("mock", maximum_missing_updates=300)), results, activities)
    semantic_inventory = SemanticInventoryEngine(ObjectLibrarySemanticSource(object_library), JsonInventoryStorage(_ROOT / "Assets" / "ObjectLibrary" / "semantic_inventory.json"), log_sink=logs)
    _require("semantic_inventory", semantic_inventory.initialize(SemanticRequest("m3-semantic", correlation_id, "composition-root")), results, activities)
    knowledge = KnowledgeEngine(SemanticInventoryKnowledgeSource(semantic_inventory), JsonKnowledgeStorage(_ROOT / "Assets" / "ObjectLibrary" / "knowledge_graph.json"), KnowledgeConfiguration(), log_sink=logs)
    _require("knowledge", knowledge.initialize(KnowledgeRequest("m3-knowledge", correlation_id, "composition-root")), results, activities)
    affordance = AffordanceEngine(KnowledgeAffordanceSource(knowledge), JsonAffordanceStorage(_ROOT / "Assets" / "ObjectLibrary" / "affordance_graph.json"), AffordanceConfiguration(), log_sink=logs)
    _require("affordance", affordance.initialize(AffordanceRequest("m3-affordance", correlation_id, "composition-root")), results, activities)
    planner = SemanticPlannerEngine(KnowledgePlannerSource(knowledge), AffordancePlannerSource(affordance), JsonSemanticPlanStorage(_ROOT / "Assets" / "SemanticPlans" / "semantic_plans.json"), PlannerConfiguration(), log_sink=logs)
    _require("planner", planner.initialize(PlannerRequest("m3-planner", correlation_id, "composition-root")), results, activities)
    taskir = TaskIRCompilerEngine(JsonTaskIRStorage(_ROOT / "Assets" / "TaskIR" / "task_ir.json"), TaskIRConfiguration(), log_sink=logs)
    _require("taskir", taskir.initialize(TaskIRRequest("m3-taskir", correlation_id, "composition-root")), results, activities)
    explainability = ExplainabilityEngine(SemanticPipelineArtifactSource(semantic_inventory,knowledge,affordance,planner,taskir), JsonExplanationStorage(_ROOT / "Assets" / "Explainability" / "explanations.json"), ExplainabilityConfiguration(), log_sink=logs)
    _require("explainability", explainability.initialize(ExplainabilityRequest("m3-explainability", correlation_id, "composition-root")), results, activities)
    _require("explainability_rebuild", explainability.rebuild(ExplainabilityRequest("m3-explainability-rebuild", correlation_id, "composition-root")), results, activities)

    perception = PerceptionController(camera, vision, scene, camera_configuration, monitor=monitor, detector=adaptive_processor)
    runtime = RuntimeComponents(bootstrap, kernel, configuration, registry, event_bus, memory, logging, camera, vision, scene, semantic_inventory, knowledge, affordance, planner, taskir, explainability, perception, object_library, monitor, model_manager, None, logs, results, activities)
    object.__setattr__(runtime, "video_workspace", VideoWorkspace(runtime, _ROOT))
    return runtime
