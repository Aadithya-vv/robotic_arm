# Engine 011 Semantic Inventory Engineering Specification

## Purpose and authority

ENG-011 converts permanent learned-object metadata supplied through a contract into an immutable, searchable semantic inventory. This implementation refinement is governed by ABP-00–04/09, GBP-05–08, `Contracts/SharedContracts.md`, and the authoritative ENG-011 behavioral specification. It does not reason, plan, detect, recognize, infer affordances, edit objects, or own ENG-012 knowledge.

## Responsibilities and boundaries

The Engine normalizes object metadata, preserves permanent identity, builds serializable semantic records, calculates transparent completeness/confidence scores, creates category/tag/name/alias indexes, filters records, reports statistics, exports a snapshot, persists its derived snapshot, and emits its own lifecycle explanations. Relationships are copied when already present; affordances remain empty placeholders. It never changes its source.

## Inputs

`ObjectSource.get_all()` supplies immutable mapping-shaped learned-object records through an injected provider. Each valid record requires an opaque non-empty Object ID and name. Optional metadata includes category, description, aliases, descriptors, instance paths, history, confidence, dates, videos, frames, tags, relationships, and recognition statistics.

## Outputs and data model

`SemanticInventory` contains schema version, generation time, ordered `SemanticObject` records, and statistics. Each semantic object contains ObjectID, ObjectName, Category, Description, Aliases, VisualDescriptors, InstanceFrames, InstanceImages, RecognitionHistory, AverageConfidence, LearningDate, LastUpdated, SourceVideos, SourceFrames, Tags, Relationships, Affordances, SemanticScore, Version, and Metadata. Frozen records use only recursively serializable values at export/storage boundaries.

## Data flow

```text
Object Library --ObjectSource contract--> ENG-011 normalization/index
                                             |
                                             +--> immutable read service
                                             +--> atomic semantic_inventory.json
                                             +--> WebAPI read-only projection --> viewer
```

## Lifecycle and thread safety

Approved states are Empty → Building → Available; Available → Updating → Available/Invalid; Available → Closed. A re-entrant lock serializes state transitions, rebuilds, and reads. Invalid requests/transitions are rejected; processing/storage failures produce explicit Failed responses and Invalid state. No fabricated partial success is allowed.

## Storage and migration

Storage is injected through `InventoryStorage`. The production JSON provider atomically replaces `Assets/ObjectLibrary/semantic_inventory.json` using a temporary sibling. `objects.json` remains authoritative and unchanged. Initialization deterministically rebuilds the derived snapshot from the current source, automatically replacing missing, legacy, or stale semantic snapshots without destructive migration.

## Public API

- `initialize(request)` / `refresh(request)` / `close(request)`
- `get_object(request, object_id)` / `get_all_objects(request)`
- `search(request, query, category, alias, tag)`
- `get_statistics(request)` / `export_inventory(request)`

All operations return a versioned, correlated `SemanticResponse` with explicit status, errors, state, and owned explanations.

## Dependencies and non-dependencies

Required injected contracts: `ObjectSource`, `InventoryStorage`. The Composition Root supplies adapters. ENG-011 imports no Object Library implementation, Scene implementation, Knowledge Engine, Affordance Engine, Planner, WebAPI, UI, YOLO, or robot/simulation dependency.

## Failure cases

Invalid contract/version, missing identities, invalid lifecycle state, missing object, malformed source record, unavailable source, and storage/serialization failure are explicit. Error messages expose safe exception types, never concrete dependency internals.

## Performance goals

Build and index cost is linear in objects plus tags/aliases. Reads are bounded in memory and deterministic. The validation target is a 1,000-object build in under two seconds on the development environment; this is an engineering target, not an architectural SLA.

## Validation strategy

Unit, lifecycle, contract, serialization, query, category, alias, tag, statistics, migration, JSON atomic storage, refresh, failure, concurrency, 1,000-object performance, Rule 40, Object Library compatibility, Composition Root startup, WebAPI, TypeScript, launcher, and session cleanup tests are required.

## Future extensions

Backward-compatible additions may include tokenized/full-text indexes, configurable normalization, relationship projections, pagination, and incremental source change sets. Affordance inference belongs to ENG-013; reusable reasoning knowledge belongs to ENG-012.
