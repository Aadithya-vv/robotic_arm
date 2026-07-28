# Engine 012 Knowledge Engine Engineering Specification

## Purpose

ENG-012 converts ENG-011 Semantic Objects into immutable structured Knowledge Records describing only what is explicitly known. It stores and retrieves reusable knowledge context but performs no AI, inference, reasoning, affordance analysis, planning, intent recognition, TaskIR, or execution.

## Responsibilities

The Engine owns Knowledge Record generation, summaries, validation, integrity checksums, consistency, indexes/cache, lookup, search/filtering, statistics, export, derived persistence, migration, and full rebuild. It never edits Semantic Inventory or Object Library and never invents facts.

## Inputs and outputs

An injected `SemanticInventorySource` returns objects satisfying the structural Semantic Object contract. Required identity/name fields and semantic contract shape are validated. The output `KnowledgeGraph` contains ordered `KnowledgeRecord` values and statistics in versioned, correlated responses with explicit status/errors/explanations.

`KnowledgeRecord` contains KnowledgeID, ObjectID, ObjectName, Category, Summary, Properties, Facts, Attributes, TypicalUses, Materials, Environment, Confidence, KnowledgeSources, Relationships, Metadata, Version, SchemaVersion, EngineVersion, Created, Updated, and SHA-256 Checksum. All nested data is frozen and JSON serializable at boundaries.

## Data flow and architecture

```text
Object Library -> ENG-011 public contract
                       |
                       v
Composition adapter -> SemanticInventorySource protocol
                       |
                       v
ENG-012 validate/normalize/index/checksum
       |                     |
       v                     v
read-only contract       atomic knowledge_graph.json
       |
       v
WebAPI projections -> Knowledge Viewer
```

## Boundaries

ENG-012 imports no ENG-011 implementation. Composition Root alone invokes ENG-011’s public request/response contract and adapts records to ENG-012’s structural source. ENG-012 has no Object Library, UI, WebAPI, Scene, detection, robot, Affordance, Planner, TaskIR, or Execution dependency.

## Storage and migration

`KnowledgeStorage` is injected. Production storage atomically replaces `Assets/ObjectLibrary/knowledge_graph.json`. `objects.json` and `semantic_inventory.json` are read/modified only by their owners. Startup and rebuild derive the complete graph from live Semantic Inventory, automatically replacing missing, stale, legacy, or incompatible derived files.

## Protocols and configuration

- `SemanticInventorySource.get_all()`
- `KnowledgeStorage.load/save()`
- `LogSink.record()`
- `KnowledgeConfiguration(schema_version, maximum_records)`
- `KnowledgeContract`

## Public API

- lifecycle: `initialize`, `rebuild`, `close`
- retrieval: `get_knowledge`, `get_knowledge_by_object`
- search: general, property, fact, category, relationship
- `get_statistics`, `export_knowledge`, `validate_knowledge`

## Thread safety and cache

A re-entrant lock serializes lifecycle transitions, rebuilds, reads, and cache changes. O(1) maps index Knowledge ID and Object ID. Search uses an immutable graph snapshot. States are Empty → Building → Available; Available → Updating → Available/Invalid; Available → Closed.

## Failure modes

Invalid requests/versions/states are Rejected. Invalid semantic records, source/storage exceptions, capacity violations, checksum failures, and logging failures are explicit Failed outcomes with safe errors. No partial or fabricated success is allowed.

## Validation and performance

Required tests cover contract/lifecycle, complete model, no-inference behavior, lookup, all searches, relationships, statistics, summaries, serialization, checksums, migration, atomic storage, rebuild, dependency failure, concurrency, logging, configuration, Rule 40, Composition Root, APIs, UI compilation, and all prior regressions. Target: build 1,000 records within two seconds on the development system.

## Future extensions

ENG-022 may submit validated Knowledge Update Requests through a future backward-compatible contract. Incremental source change sets, pagination, richer explicit schemas, and optimized indexes are permitted extensions. ENG-013 owns affordances; ENG-015 owns planning; none may be absorbed here.
