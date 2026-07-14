"""Reverse-order Core Platform shutdown through public contracts."""
from taskgraph_bootstrap import ShutdownRequest
from taskgraph_configuration import ConfigurationRequest
from taskgraph_event_bus import EventBusRequest
from taskgraph_kernel import KernelStopRequest
from taskgraph_logging import LoggingRequest
from taskgraph_memory import MemoryRequest
from taskgraph_registry import RegistryRequest
def shutdown_runtime(runtime,correlation_id="m1-shutdown"):
    results={}
    results["kernel"]=runtime.kernel.stop(KernelStopRequest("stop-kernel",correlation_id,"composition-root"))
    results["event_bus"]=runtime.event_bus.stop(EventBusRequest("stop-event-bus",correlation_id,"composition-root"))
    results["memory"]=runtime.memory.dispose(MemoryRequest("stop-memory",correlation_id,"composition-root"))
    results["registry"]=runtime.registry.close(RegistryRequest("stop-registry",correlation_id,"composition-root"))
    results["configuration"]=runtime.configuration.shutdown(ConfigurationRequest("stop-configuration",correlation_id,"composition-root"))
    results["bootstrap"]=runtime.bootstrap.stop(ShutdownRequest("stop-bootstrap",correlation_id,"composition-root"))
    results["logging"]=runtime.logging.stop(LoggingRequest("stop-logging",correlation_id,"composition-root"))
    return results
