# ENG-005 — Event Bus Engine

## Public Behavior

ENG-005 provides deterministic in-process event publication, subscription, routing, and synchronous delivery through public contracts. Publishers register identities and authorized topics. Subscribers register immutable subscription metadata plus an injected `EventHandler` provider. Publishing validates the event, routes exact-topic matches in lexical subscription order, and returns a complete delivery outcome.

Operations include lifecycle start/stop, publisher registration/removal, subscription creation/removal, publish, and immutable runtime snapshot retrieval.

## Event and Delivery Lifecycle

Engine lifecycle follows `Created → Starting → Accepting Events → Draining → Stopped`; startup failures enter `Failed`. Delivery is completed synchronously before its response is returned, so draining has no hidden queue to persist.

A successful event with no subscribers is a valid routed outcome with zero deliveries. Mixed successful and failed subscribers produce explicit `Partial`; total delivery failure produces `Failed`. Failed/partial work is never represented as success.

## Validation and Routing

Requests enforce identity, correlation, target, expectation, contract identity, and major-version compatibility. Events require identity, topic, registered publisher, matching correlation, compatible version, and immutable payload/metadata. Publishers may emit only registered topics. Routing uses exact topic equality and never interprets business semantics.

## Thread Safety and State

A reentrant lock serializes lifecycle, publisher, subscription, publication, and snapshot operations. Snapshots expose immutable publisher/subscription metadata and counters but never handler implementations. Payloads and metadata are recursively frozen.

## Integration

Registry may describe ENG-005 as metadata; it does not route events. Kernel and Configuration may publish or subscribe through Event Bus contracts. Bootstrap does not own Event Bus behavior. Logging is injected through `LogSink`, with `NullLogSink` available until ENG-007 exists. No concrete Engine implementation is imported.

The repository [Composition Root](../../Integration/CompositionRoot/README.md) constructs ENG-005 through its public package and publishes Registry metadata without moving event responsibility out of ENG-005.

## Boundaries and Limitations

- Delivery is local, in-process, synchronous, and non-persistent.
- Exact-topic routing is the approved Version 1 implementation; wildcard policy is not invented.
- No retries, timeouts, prioritization, queue retention, or distributed transport are architecturally approved.
- Event Bus does not own logs, memory, configuration, runtime coordination, Registry, planning, execution, or subscriber business decisions.

## Verification

The suite covers lifecycle, publishers, subscriptions, routing order, validation, partial/failed delivery, handler boundaries, immutability, snapshots, observability, Rule 40, and Composition Root startup/shutdown.
