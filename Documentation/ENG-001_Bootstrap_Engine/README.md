# ENG-001 — Bootstrap Engine

ENG-001 establishes the initial TaskGraph runtime lifecycle. It validates a versioned startup request, loads an immutable runtime-environment snapshot, validates injected startup capabilities, transitions to Ready, and exposes the prepared runtime through its public contract.

## Responsibilities

- Start the TaskGraph platform lifecycle.
- Verify request, environment, contract-version, composition, and capability conditions.
- Load the runtime environment into an immutable snapshot.
- Establish and manage Bootstrap-owned lifecycle state.
- Prepare a capability manifest for future Engine registration without implementing Registry behavior.
- Emit structured log records through an injected logging contract.
- Produce Bootstrap-owned Explanation Records for important decisions and transitions.

## Public Package

The package is `taskgraph_bootstrap` under the Engine's `Source/` directory. Its supported public surface is exported from `taskgraph_bootstrap.__init__`.

### Primary contract

`BootstrapContract` defines:

- `state` — current Bootstrap lifecycle state;
- `runtime` — immutable `RuntimeSnapshot` after successful startup;
- `start(BootstrapRequest)` — validate and establish the initial runtime;
- `stop(ShutdownRequest)` — stop only the Bootstrap-owned lifecycle.

`BootstrapEngine` is the production implementation. Responses use `BootstrapResponse`, `ResponseStatus`, structured `BootstrapError` values, and `ExplanationRecord` values aligned with `Contracts/SharedContracts.md`.

## Lifecycle

```text
Created
  → Validating
  → Loading
  → Initializing
  → Ready
  → Stopping
  → Stopped

Validating, Loading, or Initializing → Failed
```

Failed and Stopped are terminal. A safe restart uses a new Bootstrap instance. Calling `start` outside Created or `stop` outside Ready returns an explicit Rejected response without fabricating success.

## Startup Validation

Startup checks:

- non-empty request, correlation, and source identities;
- compatible Bootstrap contract major version;
- environment presence when configured as required;
- unique required capability identities;
- unique composed capability providers;
- availability of every required capability;
- contract-conforming results from every provider;
- logging-contract availability during lifecycle transitions.

Provider exceptions and malformed provider error results are converted into structured boundary errors. They do not escape as unhandled cross-Engine failures.

## Configuration

`BootstrapConfiguration` controls only Bootstrap-owned behavior:

- `required_capabilities` — capabilities that must be present in the composition;
- `supported_contract_major` — accepted Bootstrap contract major version;
- `allow_empty_environment` — whether an empty runtime environment is valid.

This configuration does not parse or own future Configuration Engine settings.

## Future Engine Independence

`StartupCapability` is an abstract provider contract. Future Configuration, Registry, Kernel, Logging, and other Engines are never imported or instantiated by ENG-001. Until those Engines exist, their capabilities can be supplied by contract-conforming providers, mocks, or stubs.

Bootstrap calls only `validate_startup` and records capability identities in the runtime snapshot. It does not start, stop, register, configure, log for, or otherwise perform a future Engine's responsibility.

`LogSink` is similarly abstract. `NullLogSink` is a contract-conforming staged-engineering stub; an actual Logging Engine can later be injected without changing Bootstrap.

## Determinism and Thread Safety

Lifecycle operations are serialized with a re-entrant lock. Equivalent input and equivalent provider behavior produce the same state and deterministic correlation-based response/explanation identities. Environment and metadata snapshots are copied and exposed as immutable mappings.

## Error Handling

Errors use shared categories including validation, unsupported version, invalid state, dependency unavailable, and conflict. Every accepted startup either reaches Ready or returns Failed. Invalid lifecycle requests return Rejected. Logging delivery failures are explicit and terminal during startup.

## Testing

Run with the project virtual environment from the repository root:

```powershell
$env:PYTHONPATH=(Resolve-Path 'Implementation\ENG-001_Bootstrap_Engine\Source')
.\.venv\Scripts\python.exe -m unittest discover -s Tests\ENG-001_Bootstrap_Engine -p 'test_*.py' -v
```

The suite covers startup, validation, lifecycle transitions, failure handling, shared-contract behavior, deterministic output, immutable snapshots, injected mocks/stubs, logging integration, public contract conformance, and Rule 40 source-import compliance.

## Limitations

- Bootstrap is intentionally synchronous and one-shot.
- It validates capability providers but does not run future Engine lifecycles.
- Runtime persistence and restart orchestration belong outside ENG-001.
- Quantitative latency and capacity thresholds are not defined by the frozen architecture.

## Authoritative Artifacts

- [Specification](../../Specifications/ENG-001_Bootstrap_Engine/Specification.md)
- [Framework Prompt](../../Prompts/ENG-001_Bootstrap_Engine/FrameworkPrompt.md)
- [Implementation Report](../../Reports/ENG-001_Bootstrap_Engine/ImplementationReport.md)
- [Shared Contracts](../../Contracts/SharedContracts.md)

