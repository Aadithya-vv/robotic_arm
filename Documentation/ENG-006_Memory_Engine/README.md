# ENG-006 — Memory Engine

## Public Behavior

ENG-006 owns temporary runtime and working memory. It creates owner-scoped sessions, stores immutable context records, retrieves and deletes records, supports explicitly shared records, produces immutable snapshots, cleans or closes sessions, and disposes all temporary state.

Operations use versioned, correlated requests and return explicit succeeded, rejected, or failed responses with structured errors and Memory-owned Explanation Records.

## Lifecycle

Initialization follows `Created → Ready`. Normal operations use `Ready → Active → Ready`. Cleanup and session closure use `Ready → Cleaning → Ready`. Disposal follows `Ready → Disposed`; disposed is terminal. Initialization or transition failures enter `Failed` and never expose false readiness.

## Sessions, Ownership, and Sharing

A session has one owner identity. Only that owner may add, replace, delete, clean, close, or snapshot its session. Records default to owner-only visibility. A record marked `Shared` may be read by another authenticated contract identity, but this does not grant session mutation or snapshot access.

Global snapshots include only sessions owned by the requesting identity, preventing accidental cross-owner disclosure.

## Runtime Values and Immutability

Supported temporary values are scalars, string-keyed mappings, sequences, and sets recursively composed from supported values. Mappings become read-only proxies, sequences become tuples, and sets become frozen sets. Arbitrary implementation objects are rejected because they cannot provide deterministic immutable snapshots.

Each key has a monotonically increasing revision within its session. Session and Engine generations advance on mutations. Previously returned records and snapshots never change.

## Policy and Integration

`MemoryPolicy` optionally limits session count and entries per session. A Composition Root may construct this policy from validated Configuration output without ENG-006 importing Configuration.

Bootstrap may initialize Memory, Kernel may coordinate it, Registry may publish ENG-006 metadata, and Event Bus may carry Memory-related events only through their public contracts. ENG-006 imports none of those Engines and never controls them. Logging is injected through `LogSink`; `NullLogSink` supports staged composition.

## Boundaries and Limitations

- All data is process-local, temporary, and lost on disposal or process termination.
- No TTL, eviction, persistence, retry, or quantitative capacity policy is architecturally defined.
- Persistent semantic knowledge belongs to ENG-012; replay history belongs to ENG-019.
- ENG-006 does not own Configuration, Logging, Registry, Event routing, planning, or execution.

## Verification

The isolated suite covers lifecycle, ownership, shared reads, session and entry capacity, immutable nested values/snapshots, revisions, cleanup, close, disposal, validation, logging, deterministic outcomes, contract integration identities, and Rule 40.
