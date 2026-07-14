"""Milestone M1 Core Platform validation through public contracts."""
from dataclasses import dataclass
from taskgraph_event_bus import DeliveryResult,EventBusRequest,PlatformEvent,PublisherRegistration,Subscription
from taskgraph_logging import LoggingRequest
from taskgraph_memory import MemoryRequest
from taskgraph_registry import RegistryRequest
from health import collect_health
@dataclass(frozen=True,slots=True)
class ValidationCheck:name:str;passed:bool;detail:str
def validate_runtime(runtime,correlation_id="m1-validation"):
    health=collect_health(runtime);checks=[]
    for name,value in health.items():checks.append(ValidationCheck(name,value.healthy,f"state={value.state}"))
    checks.append(ValidationCheck("Startup order",tuple(runtime.startup_results)[:6]==("bootstrap","logging","configuration","registry_open","event_bus","memory"),"Bootstrap -> Logging -> Configuration -> Registry -> Event Bus -> Memory"))
    checks.append(ValidationCheck("Configuration loaded",runtime.configuration.runtime_configuration is not None,"validated runtime settings available"))
    registry=runtime.registry.snapshot(RegistryRequest("validate-registry",correlation_id,"validation"));checks.append(ValidationCheck("Registry populated",registry.snapshot is not None and len(registry.snapshot.registrations)==7,"seven Engine registrations"))
    lookup=runtime.registry.lookup(RegistryRequest("validate-registry-lookup",correlation_id,"validation"),"ENG-007");checks.append(ValidationCheck("Registry lookup",lookup.status.value=="succeeded" and lookup.registration.contract_id=="taskgraph.logging","ENG-007 metadata resolved"))
    memory=runtime.memory.snapshot(MemoryRequest("validate-memory",correlation_id,"validation"));checks.append(ValidationCheck("Memory initialized",memory.status.value=="succeeded","memory snapshot available"))
    runtime.memory.create_session(MemoryRequest("validate-memory-session",correlation_id,"validation"),"m1-validation-session","validation")
    stored=runtime.memory.put(MemoryRequest("validate-memory-put",correlation_id,"validation"),"m1-validation-session","health",{"status":"green"});loaded=runtime.memory.get(MemoryRequest("validate-memory-get",correlation_id,"validation"),"m1-validation-session","health");runtime.memory.close_session(MemoryRequest("validate-memory-close",correlation_id,"validation"),"m1-validation-session")
    checks.append(ValidationCheck("Memory operations",stored.status.value=="succeeded" and loaded.record.value["status"]=="green","temporary context round trip"))
    logs=runtime.logging.query(LoggingRequest("validate-logging",correlation_id,"validation"));checks.append(ValidationCheck("Logging initialized",logs.status.value=="succeeded" and logs.snapshot.accepted_count>0,f"accepted_records={logs.snapshot.accepted_count}"))
    bus=runtime.event_bus.snapshot(EventBusRequest("validate-event-bus",correlation_id,"validation"));checks.append(ValidationCheck("Event Bus operational",bus.status.value=="succeeded","event bus snapshot available"))
    class ValidationHandler:
        def __init__(self):self.received=[]
        def deliver(self,event):self.received.append(event);return DeliveryResult(True)
    handler=ValidationHandler();publisher=PublisherRegistration("m1.validation",("m1.health",));subscription=Subscription("m1-validation-subscription","m1.validation","m1.health")
    runtime.event_bus.register_publisher(EventBusRequest("validate-publisher",correlation_id,"validation"),publisher);runtime.event_bus.subscribe(EventBusRequest("validate-subscription",correlation_id,"validation"),subscription,handler)
    delivery=runtime.event_bus.publish(EventBusRequest("validate-publish",correlation_id,"validation"),PlatformEvent("m1-validation-event","m1.health","m1.validation",correlation_id,{"status":"green"}))
    runtime.event_bus.unsubscribe(EventBusRequest("validate-unsubscribe",correlation_id,"validation"),subscription.subscription_id);runtime.event_bus.unregister_publisher(EventBusRequest("validate-unregister",correlation_id,"validation"),publisher.publisher_id)
    checks.append(ValidationCheck("Event delivery",delivery.status.value=="succeeded" and len(handler.received)==1,"one contract delivery completed"))
    checks.append(ValidationCheck("Runtime health",all(x.healthy for x in health.values()),"all seven Engines green"))
    return tuple(checks)
def validation_passed(checks):return all(item.passed for item in checks)
