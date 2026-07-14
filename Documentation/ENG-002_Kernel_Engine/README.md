# ENG-002 — Kernel Engine

## Public Behavior

The Kernel coordinates the TaskGraph runtime after Bootstrap has established initial readiness. It receives an injected Bootstrap readiness provider and zero or more managed-participant providers. It never imports a concrete Engine implementation.

The public package exposes immutable request, response, error, explanation, configuration, and runtime-snapshot values together with structural provider protocols. `KernelEngine` supports three operations:

- `start`: validates its request and composition, verifies Bootstrap readiness, and starts participants in deterministic order.
- `coordinate`: delegates one named operation to one running participant through its provider contract and updates the runtime generation on success.
- `stop`: stops started participants in reverse startup order.

Responses carry stable request/correlation identity, explicit status and errors, the Kernel state, optional runtime state, and human-readable explanation records.

## Lifecycle

The valid lifecycle is:

`Created → Starting → Running → Stopping → Stopped`

Startup or shutdown failures enter `Failed`. Invalid operations are rejected without silently changing state. A failed participant startup rolls back already-started participants in reverse order. A coordination failure is reported but does not fail the Kernel lifecycle because the runtime may remain usable.

## Responsibilities

- Manage lifecycle calls for injected runtime participants.
- Coordinate participant operations through public provider contracts.
- Maintain an immutable snapshot of Kernel and participant runtime state.
- Emit structured lifecycle logs and explanation records.
- Produce explicit validation, state, dependency, and provider-boundary failures.

The Kernel does not discover Engines, transport events, parse configuration sources, persist logs, perform domain reasoning, or implement Bootstrap or any future Engine.

## Configuration

`KernelConfiguration` accepts:

- `required_participants`: participant identities that must be present at startup.
- `startup_order`: explicit leading startup order; remaining participants start in lexical identity order.
- `supported_contract_major`: accepted Kernel request contract major version, default `1`.

Configuration is supplied by composition. ENG-002 does not read files, environment variables, or secrets.

## Provider Integration

Bootstrap integration uses `BootstrapReadinessProvider` with `is_ready()` and `runtime_metadata()`. Future Engines use `ManagedParticipant` with `participant_id`, `start`, `coordinate`, and `stop`. Until concrete Engines exist, these roles can be fulfilled by contract-compatible providers, mocks, or stubs. This preserves Rule 40 and does not extend ENG-001.

Logging is injected through `LogSink`; `NullLogSink` is the local default. Provider exceptions and invalid result types are converted to structured Kernel errors.

## Limitations

- ENG-002 is an in-process coordination component; transport and distributed execution are outside its scope.
- Runtime state is held in memory and intentionally has no persistence policy.
- Thread safety serializes public lifecycle/coordination operations with a reentrant lock.
- Quantitative performance targets are not defined by the approved specification.
- Integration with concrete future Engines awaits their independent implementation and review.

## Verification

The isolated unittest suite covers startup, validation, lifecycle and state transitions, deterministic ordering, rollback, failure handling, contract behavior, immutability, Bootstrap-provider integration, and Rule 40. See the authoritative [Implementation Report](../../Reports/ENG-002_Kernel_Engine/ImplementationReport.md).
