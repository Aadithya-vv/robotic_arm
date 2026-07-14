# ENG-007 — Logging Engine

## Public Behavior

ENG-007 centralizes structured runtime logs, errors, and diagnostics. It normalizes contract records into one immutable representation, applies severity/category policy, stores a bounded local runtime view, forwards accepted records to an injected local sink, filters/query records, formats deterministic text, exposes immutable snapshots, and flushes during shutdown.

`record_log` accepts the canonical `LogInput`. `record` implements the structural sink boundary already exposed by ENG-001 through ENG-006, allowing their public log-shaped records to be accepted without importing those Engines.

## Structured Model

Each canonical record contains a stable record identity and sequence, source identity, category, severity, correlation ID, message, optional caller-supplied time context, metadata, and contract version. Metadata is recursively immutable.

Severity order is Trace, Debug, Info, Warning, Error, Critical. The adapter also normalizes `warn` to Warning. Categories remain validated non-empty contract text so existing and future Engines retain their owned diagnostic vocabulary.

## Filtering and Formatting

`LoggingPolicy` defines minimum severity, optional allowed categories, and a positive bounded runtime capacity. Policy-filtered records return successful delivery with explicit `filtered=true`; filtering is an intentional Logging result, not a dependency failure.

`LogFilter` queries by minimum severity, categories, source identities, and correlation. Formatting is deterministic:

`sequence|severity|category|source|correlation|message`

## Lifecycle

`Created → Configuring → Ready`

Recording follows `Ready → Recording → Ready`. Shutdown follows `Ready | Degraded → Flushing → Stopped`. Local-sink write/flush failures enter `Degraded` and return explicit dependency errors. Stopped logs remain queryable, but new records are rejected.

## Local Sink and Runtime Snapshots

`RuntimeLogSink` owns only the external/local write and flush effect. `NullRuntimeLogSink` supports staged composition while the Logging Engine's bounded runtime snapshot remains authoritative for accepted records. Snapshots include stable record tuples and accepted, filtered, and rejected counters.

## Integration Boundaries

Bootstrap, Kernel, Configuration, Registry, Event Bus, and Memory integrate through their existing `LogSink.record` structural contract. ENG-007 never imports, coordinates, configures, or controls them. Configuration-derived Logging policies must be translated by composition, not loaded by ENG-007.

## Limitations

- No concrete file/database sink, rotation, retention duration, encryption, or cross-process aggregation is architecturally selected.
- The default runtime capacity is 10,000 records; capacity exhaustion rejects rather than silently evicts.
- Formatting is plain deterministic text and does not constitute report generation.
- Runtime milestone validation and Composition Root wiring are intentionally outside this engineering task.

## Verification

The isolated suite covers lifecycle, structured events/errors/diagnostics, severities, category/minimum filters, capacity, sink failures, formatting, immutable snapshots, structural prior-Engine integration, deterministic behavior, and Rule 40.
