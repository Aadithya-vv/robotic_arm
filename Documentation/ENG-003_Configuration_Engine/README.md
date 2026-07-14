# ENG-003 — Configuration Engine

## Public Behavior

ENG-003 owns loading, validation, and immutable publication of TaskGraph runtime settings. It consumes an injected `ConfigurationSource`, validates the returned settings against an explicit `ConfigurationSchema`, and exposes only a validated `RuntimeConfiguration` snapshot.

The public contract provides:

- `load(request)`: perform the initial source load and validation.
- `reload(request)`: replace an available snapshot through the approved reload lifecycle.
- `get(request)`: retrieve the current validated snapshot.
- `shutdown(request)`: release the owned in-memory snapshot and stop the Engine.

Every operation returns a versioned, correlated response with an explicit succeeded, rejected, or failed status. Important decisions and transitions produce Configuration-owned Explanation Records.

## Lifecycle

Initial load follows:

`Unloaded → Loading → Validating → Available | Invalid`

Reload follows:

`Available → Reloading → Validating → Available | Invalid`

Shutdown follows:

`Unloaded | Available | Invalid → Stopping → Stopped`

Invalid operations are rejected. An initialization or reload failure never exposes a false successful result. Recovery from `Invalid` requires coordinated shutdown and reconstruction because no safe in-place recovery contract is approved.

## Validation

`ConfigurationSchema` maps setting names to `SettingRule` values. A rule declares whether a key is required, whether `None` is allowed, and its value kind: any supported value, string, integer, number, Boolean, mapping, or sequence. Unknown keys are rejected unless explicitly allowed by the schema.

Top-level keys must be non-empty strings. Nested configuration is accepted only when it can be converted into an immutable representation. Arbitrary mutable/custom implementation objects are rejected.

## Immutability

Validated mappings become read-only mapping proxies; sequences become tuples; sets become frozen sets; nested structures are frozen recursively. Reload creates a new revision and does not mutate previously returned snapshots.

## Provider Integration

Configuration sources implement `ConfigurationSource.load(SourceLoadRequest)` and return `SourceLoadResult`. This permits future file, environment, or other local providers without embedding any filesystem or environment assumption in ENG-003.

Logging is injected through `LogSink`; a `NullLogSink` is supplied for compositions where ENG-007 is unavailable. Provider exceptions and invalid provider results become explicit structured errors. No concrete ENG-001, ENG-002, ENG-007, or future-Engine package is imported.

## Responsibilities and Boundaries

ENG-003 loads configuration, validates configuration, and provides runtime settings. It does not own application startup, dependency resolution, consumer-specific interpretation, Registry, Logging persistence, Memory, Event Bus transport, secret acquisition, or configuration-source policy.

## Limitations

- No concrete source provider is selected by architecture; composition supplies one.
- Values supported for immutable publication are scalars, mappings with string keys, sequences, and sets composed recursively from supported values.
- No quantitative performance targets, retries, timeouts, or secret-handling mechanism are approved.
- Configuration is in-memory only; persistence is a source/provider responsibility outside ENG-003.

## Verification

The isolated unittest suite covers loading, validation boundaries, immutable snapshots, lifecycle and invalid transitions, reload, shutdown, dependency failures, logging, deterministic behavior, contract substitutes, and Rule 40.
