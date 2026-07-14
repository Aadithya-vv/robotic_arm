# ENG-004 — Registry Engine

## Public Behavior

ENG-004 is the authoritative in-memory registry of Engine registration metadata. It stores identities, public contract descriptors, capabilities, availability, provenance, and safe metadata. It never stores, constructs, starts, stops, or coordinates Engine instances.

The public contract supports:

- `open`: enter registration acceptance.
- `register` and `deregister`: add or remove validated Engine metadata.
- `mark_ready`: enable discovery, lookup, and dependency resolution.
- `lookup`: retrieve one registration by exact Engine identity.
- `discover`: list registrations deterministically, optionally filtered by capability and availability.
- `resolve`: resolve an explicit set of exact Engine identities when all are registered and available.
- `set_availability`: replace a registration with an immutable availability update.
- `snapshot`: return an immutable authoritative registry view.
- `close`: clear runtime registry state and reject further work.

Every operation returns a correlated, versioned response with explicit status, structured errors, and Registry-owned Explanation Records where a decision or transition occurs.

## Lifecycle

`Empty → Accepting Registrations → Ready`

Resolution temporarily follows `Ready → Resolving → Ready | Degraded`. Missing or unavailable required registrations produce `Degraded`; that instance may then be inspected and closed but not silently recovered. Any non-resolving active state may close. `Closed` is terminal.

Registration, deregistration, availability updates, and snapshots are allowed while accepting registrations or ready. Lookup, discovery, and resolution require ready state.

## Registration Validation

Registrations require an approved `ENG-` identity, display name, public contract identity/version, at least one unique non-empty capability, valid availability, and immutable provenance/metadata. Duplicate Engine identities are conflicts. Optional `RegistryPolicy` can require metadata keys or impose a registration capacity supplied by composition.

## Dependency Resolution

Resolution accepts exact Engine identities and returns their registration metadata only when every requested Engine is available. ENG-004 does not select implementations, instantiate dependencies, or coordinate lifecycle. Exact identities avoid introducing an undocumented construction or candidate-preference policy.

## Integration Boundaries

- Bootstrap may publish ENG-001 metadata through `register` after composition establishes Registry access.
- Kernel may use `lookup`, `discover`, `resolve`, or `snapshot` through a Registry contract adapter.
- Configuration may publish ENG-003 configuration capability metadata through `register`.

These integrations exchange only Registry contract values. ENG-004 imports no Bootstrap, Kernel, Configuration, Logging, or other Engine package.

Logging is injected through `LogSink`; `NullLogSink` supports staged composition until ENG-007 is implemented. Registry policy values may be constructed from validated Configuration output by the composition root; ENG-004 does not import Configuration or interpret its internals.

## Concurrency and Immutability

Public operations are serialized with a reentrant lock. Registrations are frozen values; updates replace them. Snapshots copy the authoritative index into a read-only mapping and remain unchanged after later registry mutations. Discovery order is lexical by Engine identity.

## Limitations

- Registry state is local and in-memory; persistence and distributed registries are outside Version 1.
- Capability discovery reports candidates but does not select or instantiate them.
- Degraded recovery is not defined by the approved lifecycle; close and reconstruct the Registry.
- Quantitative capacity and performance targets are not architecturally defined.

## Verification

The isolated unittest suite covers lifecycle, registration validation, duplicates, policy limits, lookup, discovery, availability, deregistration, dependency resolution, immutable snapshots, degraded behavior, observability, deterministic operation, integration-ready metadata, and Rule 40.
