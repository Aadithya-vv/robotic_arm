"""Public surface for ENG-004 Registry Engine."""

from .contracts import (
    Availability, DependencyResolution, EngineRegistration, ExplanationRecord, LogRecord,
    LogSink, NullLogSink, RegistryContract, RegistryError, RegistryPolicy, RegistryRequest,
    RegistryResponse, RegistrySnapshot, RegistryState, ResponseStatus,
)
from .engine import RegistryEngine

__all__ = [
    "Availability", "DependencyResolution", "EngineRegistration", "ExplanationRecord",
    "LogRecord", "LogSink", "NullLogSink", "RegistryContract", "RegistryEngine",
    "RegistryError", "RegistryPolicy", "RegistryRequest", "RegistryResponse",
    "RegistrySnapshot", "RegistryState", "ResponseStatus",
]
