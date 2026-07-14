"""Public contracts for ENG-003 Configuration Engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Any, Mapping, Protocol, runtime_checkable

ENGINE_ID = "ENG-003"
CONTRACT_ID = "taskgraph.configuration"
CONTRACT_VERSION = "1.0.0"


class ConfigurationState(str, Enum):
    UNLOADED = "unloaded"
    LOADING = "loading"
    RELOADING = "reloading"
    VALIDATING = "validating"
    AVAILABLE = "available"
    INVALID = "invalid"
    STOPPING = "stopping"
    STOPPED = "stopped"


class ResponseStatus(str, Enum):
    SUCCEEDED = "succeeded"
    REJECTED = "rejected"
    FAILED = "failed"


class ValueKind(str, Enum):
    ANY = "any"
    STRING = "string"
    INTEGER = "integer"
    NUMBER = "number"
    BOOLEAN = "boolean"
    MAPPING = "mapping"
    SEQUENCE = "sequence"


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    if isinstance(value, (set, frozenset)):
        return frozenset(_freeze(item) for item in value)
    return value


@dataclass(frozen=True, slots=True)
class ConfigurationError:
    category: str
    code: str
    message: str
    request_id: str
    correlation_id: str
    recoverable: bool = False
    retry_guidance: str | None = None
    context: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "context", _freeze(self.context))


@dataclass(frozen=True, slots=True)
class ExplanationRecord:
    explanation_id: str
    engine_id: str
    correlation_id: str
    subject: str
    decision: str
    supporting_facts: tuple[str, ...]
    status: str
    provenance: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "supporting_facts", tuple(self.supporting_facts))
        object.__setattr__(self, "provenance", _freeze(self.provenance))


@dataclass(frozen=True, slots=True)
class LogRecord:
    engine_id: str
    category: str
    severity: str
    correlation_id: str
    message: str
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "metadata", _freeze(self.metadata))


@runtime_checkable
class LogSink(Protocol):
    def record(self, record: LogRecord) -> None: ...


class NullLogSink:
    def record(self, record: LogRecord) -> None:
        del record


@dataclass(frozen=True, slots=True)
class SourceLoadRequest:
    request_id: str
    correlation_id: str
    source_identity: str
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "metadata", _freeze(self.metadata))


@dataclass(frozen=True, slots=True)
class SourceLoadResult:
    succeeded: bool
    settings: Mapping[str, Any] = field(default_factory=dict)
    provenance: Mapping[str, Any] = field(default_factory=dict)
    errors: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "settings", _freeze(self.settings))
        object.__setattr__(self, "provenance", _freeze(self.provenance))
        object.__setattr__(self, "errors", tuple(self.errors))


@runtime_checkable
class ConfigurationSource(Protocol):
    def load(self, request: SourceLoadRequest) -> SourceLoadResult: ...


@dataclass(frozen=True, slots=True)
class SettingRule:
    kind: ValueKind = ValueKind.ANY
    required: bool = False
    allow_none: bool = False


@dataclass(frozen=True, slots=True)
class ConfigurationSchema:
    rules: Mapping[str, SettingRule] = field(default_factory=dict)
    allow_unknown_keys: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "rules", MappingProxyType(dict(self.rules)))


@dataclass(frozen=True, slots=True)
class ConfigurationRequest:
    request_id: str
    correlation_id: str
    source_identity: str
    causation_id: str | None = None
    timestamp_context: str | None = None
    expectation: str = "response_required"
    contract_id: str = CONTRACT_ID
    contract_version: str = CONTRACT_VERSION
    target_capability: str = "configuration"
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "metadata", _freeze(self.metadata))


@dataclass(frozen=True, slots=True)
class RuntimeConfiguration:
    configuration_id: str
    revision: int
    values: Mapping[str, Any]
    provenance: Mapping[str, Any]
    correlation_id: str
    validation_status: str = "validated"
    contract_version: str = CONTRACT_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(self, "values", _freeze(self.values))
        object.__setattr__(self, "provenance", _freeze(self.provenance))


@dataclass(frozen=True, slots=True)
class ConfigurationResponse:
    response_id: str
    request_id: str
    correlation_id: str
    status: ResponseStatus
    state: ConfigurationState
    runtime_configuration: RuntimeConfiguration | None = None
    errors: tuple[ConfigurationError, ...] = ()
    explanations: tuple[ExplanationRecord, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)
    contract_id: str = CONTRACT_ID
    contract_version: str = CONTRACT_VERSION
    source_identity: str = ENGINE_ID

    def __post_init__(self) -> None:
        object.__setattr__(self, "errors", tuple(self.errors))
        object.__setattr__(self, "explanations", tuple(self.explanations))
        object.__setattr__(self, "metadata", _freeze(self.metadata))


@runtime_checkable
class ConfigurationContract(Protocol):
    @property
    def state(self) -> ConfigurationState: ...

    @property
    def runtime_configuration(self) -> RuntimeConfiguration | None: ...

    def load(self, request: ConfigurationRequest) -> ConfigurationResponse: ...

    def reload(self, request: ConfigurationRequest) -> ConfigurationResponse: ...

    def get(self, request: ConfigurationRequest) -> ConfigurationResponse: ...

    def shutdown(self, request: ConfigurationRequest) -> ConfigurationResponse: ...
