"""Construct and start all frozen Core Platform Engines through public contracts."""
from taskgraph_bootstrap import BootstrapConfiguration,BootstrapEngine,BootstrapRequest
from taskgraph_configuration import ConfigurationEngine,ConfigurationRequest,ConfigurationSchema,SettingRule,ValueKind
from taskgraph_event_bus import EventBusEngine,EventBusRequest
from taskgraph_kernel import KernelEngine,KernelStartRequest
from taskgraph_logging import LoggingEngine,LoggingRequest
from taskgraph_memory import MemoryEngine,MemoryRequest
from taskgraph_registry import EngineRegistration,RegistryEngine,RegistryRequest
from providers import BootstrapReadinessAdapter,DeferredLogSink,StartupCapabilityProbe,StaticConfigurationSource
from runtime import RuntimeComponents

class StartupFailure(RuntimeError):
    def __init__(self,stage,response):self.stage=stage;self.response=response;super().__init__(f"startup failed at {stage}: {getattr(response,'errors',())}")
def _require(stage,response,results,activities):
    results[stage]=response;activities.append(f"{stage}: {response.status.value}")
    if response.status.value!="succeeded":raise StartupFailure(stage,response)
def create_runtime(settings=None,correlation_id="m1-startup"):
    settings=dict(settings or {"runtime_mode":"local","release":"v0.1"});results={};activities=[];logs=DeferredLogSink()
    logging=LoggingEngine();configuration=ConfigurationEngine(StaticConfigurationSource(settings),ConfigurationSchema({"runtime_mode":SettingRule(ValueKind.STRING,True),"release":SettingRule(ValueKind.STRING,True)}),log_sink=logs)
    registry=RegistryEngine(log_sink=logs);event_bus=EventBusEngine(log_sink=logs);memory=MemoryEngine(log_sink=logs)
    probes=tuple(StartupCapabilityProbe(x) for x in ("configuration","registry","event_bus","memory","logging"))
    bootstrap=BootstrapEngine(probes,configuration=BootstrapConfiguration(required_capabilities=tuple(x.capability_id for x in probes)),log_sink=logs)
    kernel=KernelEngine(BootstrapReadinessAdapter(bootstrap),log_sink=logs)
    _require("bootstrap",bootstrap.start(BootstrapRequest("m1-bootstrap",correlation_id,"composition-root",{"mode":"local"})),results,activities)
    _require("logging",logging.initialize(LoggingRequest("m1-logging",correlation_id,"composition-root")),results,activities);logs.attach(logging)
    _require("configuration",configuration.load(ConfigurationRequest("m1-configuration",correlation_id,"composition-root")),results,activities)
    _require("registry_open",registry.open(RegistryRequest("m1-registry-open",correlation_id,"composition-root")),results,activities)
    _require("event_bus",event_bus.start(EventBusRequest("m1-event-bus",correlation_id,"composition-root")),results,activities)
    _require("memory",memory.initialize(MemoryRequest("m1-memory",correlation_id,"composition-root")),results,activities)
    registrations=(
        ("ENG-001","Bootstrap Engine","taskgraph.bootstrap","runtime.bootstrap"),("ENG-002","Kernel Engine","taskgraph.kernel","runtime.coordination"),
        ("ENG-003","Configuration Engine","taskgraph.configuration","configuration"),("ENG-004","Registry Engine","taskgraph.registry","registry"),
        ("ENG-005","Event Bus Engine","taskgraph.event_bus","events"),("ENG-006","Memory Engine","taskgraph.memory","memory"),("ENG-007","Logging Engine","taskgraph.logging","logging"),)
    for engine_id,name,contract,capability in registrations:
        _require(f"register_{engine_id}",registry.register(RegistryRequest(f"m1-register-{engine_id}",correlation_id,"composition-root"),EngineRegistration(engine_id,name,contract,"1.0.0",(capability,))),results,activities)
    _require("registry_ready",registry.mark_ready(RegistryRequest("m1-registry-ready",correlation_id,"composition-root")),results,activities)
    _require("kernel",kernel.start(KernelStartRequest("m1-kernel",correlation_id,"composition-root")),results,activities)
    return RuntimeComponents(bootstrap,kernel,configuration,registry,event_bus,memory,logging,results,activities)
