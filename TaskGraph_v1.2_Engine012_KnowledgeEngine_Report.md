# TaskGraph v1.2 Engine 012 Knowledge Engine Report

## Architecture review

ABP/GBP, Rule 40, Shared Contracts, Dependency Map, authoritative ENG-012 artifacts, frozen ENG-011 specification/prompt/report/source contract, Composition Root, Object Library, semantic/knowledge storage, WebAPI, UI, launcher, and session lifecycle were reviewed before implementation.

The approved “reasoning context” responsibility is implemented only as structured retrievable data. ENG-012 performs no reasoning or inference. Facts, properties, materials, uses, environment, and relationships are copied only when declared by ENG-011. Missing knowledge stays empty. The pipeline is strictly Object Library → ENG-011 public contract → Composition adapter → ENG-012.

## Responsibilities and knowledge model

ENG-012 owns generation, summaries, persistence, lookup, Object-ID lookup, indexes/cache, general/property/fact/category/relationship search, export, statistics, validation, checksums, migration, consistency, rebuild, lifecycle, errors, and explanations.

Each immutable record includes KnowledgeID, ObjectID, ObjectName, Category, Summary, Properties, Facts, Attributes, TypicalUses, Materials, Environment, Confidence, KnowledgeSources, Relationships, Metadata, Version, SchemaVersion, EngineVersion, Created, Updated, and canonical SHA-256 Checksum.

It does not own Semantic Inventory, Object Library, affordances, planning, intent, Scene, TaskIR, robot skills, execution, UI logic, or AI.

## Storage and migration

Added `Assets/ObjectLibrary/knowledge_graph.json`. It is an atomic, derived, rebuildable database. ENG-012 never opens or modifies `objects.json` or `semantic_inventory.json`. Startup and explicit rebuild replace missing, stale, and legacy graph formats from the current ENG-011 public snapshot. Checksums validate record integrity independently of storage location.

## Composition Root integration

Added `SemanticInventoryKnowledgeSource`, which calls ENG-011’s public `get_all_objects` request/response contract and exposes only the structural source protocol required by ENG-012. The Root injects that adapter, `JsonKnowledgeStorage`, `KnowledgeConfiguration`, and the existing structural logger. It registers `ENG-012 / taskgraph.knowledge / 1.0.0`, initializes after ENG-011, exposes it in `RuntimeComponents.engines`, validates graph integrity, reports health, and closes ENG-012 before ENG-011.

Registry, Bootstrap capability probes, startup results, health, validation, and shutdown now cover twelve Engines without changing prior Engine code or ownership.

## Read-only API summary

| Method | Route | Purpose |
|---|---|---|
| GET | `/knowledge` | Complete Knowledge Graph |
| GET | `/knowledge/{id}` | One Knowledge Record |
| GET | `/knowledge/search` | General/property/fact/category/relationship filters |
| GET | `/knowledge/statistics` | Counts and confidence |
| GET | `/knowledge/categories` | Category index |
| GET | `/knowledge/properties` | Property index |
| GET | `/knowledge/relationships` | Declared relationship projection |

There are no Knowledge mutation routes. Object mutation refreshes ENG-011 first, then rebuilds ENG-012 through public contracts.

## Minimal Knowledge Viewer

The existing UI gained one navigation entry and read-only page with Knowledge Count, categories, properties, relationships, search, cards, and detail dialog. It polls the read-only projection and contains no editing or domain logic. Existing layout was not redesigned.

## Tests added

The 30-test ENG-012 suite covers contract, lifecycle, invalid transitions, close, complete immutable model, configuration rejection, no inference, complete graph and both ID lookups, missing lookup, all five search modes, relationship preservation, statistics, summaries, serialization, checksum stability/integrity, legacy migration, atomic JSON storage, source rebuild, invalid upstream contracts, 20-thread reads, 1,000-record performance, structured logging/failure, and Rule 40 imports.

## Validation results

| Area | Result | Evidence |
|---|---|---|
| ENG-012 isolated tests | PASS | 30/30 |
| All Engines | PASS | ENG-001–012, 369 tests |
| Launcher/session regression | PASS | 5/5 |
| Python compilation | PASS | Implementation, Integration, Launcher |
| TypeScript | PASS | Project build |
| ESLint | PASS | 0 errors; one pre-existing Fast Refresh warning |
| Frontend production build | PASS | Vite, 2,215 modules |
| Composition Root | PASS | Twelve healthy Engines |
| Registry | PASS | Twelve contract registrations |
| ENG-011 dependency | PASS | Public contract adapter only |
| Object Library | PASS | No direct dependency or behavior change |
| Knowledge APIs | PASS | Collection/search/index routes return 200; detail covered by lookup tests |
| Storage/migration | PASS | Schema 1.0 atomic file generated |
| Integrity | PASS | Canonical checksum validation |
| Thread safety | PASS | 20 concurrent reads |
| Session lifecycle | PASS | Permanent library retained |
| Launcher | PASS | Frozen launcher unchanged |

## Performance

Rebuild is O(records + properties + facts + relationships). ID and Object-ID lookup are O(1); deterministic searches are O(records). The controlled 1,000-record build, summary, checksum, index, and snapshot test completes within the two-second development target. Source images and descriptors are not duplicated.

## Files added

- `Engine012_KnowledgeEngine_Specification.md`
- `Engine012_FrameworkPrompt.md`
- `Implementation/ENG-012_Knowledge_Engine/Source/taskgraph_knowledge/{__init__,contracts,engine,storage}.py`
- `Integration/CompositionRoot/knowledge.py`
- `Tests/ENG-012_Knowledge_Engine/test_knowledge_engine.py`
- `Documentation/ENG-012_Knowledge_Engine/KnowledgeEngine_{Architecture,DataFlow,API,TestPlan}.md`
- `Assets/ObjectLibrary/knowledge_graph.json` (runtime-generated derived database)
- `TaskGraph_v1.2_Engine012_KnowledgeEngine_Report.md`

## Files modified

- `Integration/CompositionRoot/{runtime,startup,shutdown,health,validation}.py`
- `Integration/WebAPI/api.py`
- `WebApp/src/{App,components,lib,pages}.tsx`/`.ts`
- `WebApp/vite.config.ts`
- `Documentation/ENG-012_Knowledge_Engine/README.md`
- `Reports/ENG-012_Knowledge_Engine/ImplementationReport.md`
- `ImplementationStatus.md`

No ENG-001–011 source, Launcher, ABP, GBP, Contracts, Object Library implementation, detection/YOLO, or session lifecycle file was modified.

## Known limitations

- v1.2 deliberately does not infer cup/container/material/use facts from names or natural-language descriptions.
- Search is deterministic JSON/field filtering rather than AI, ontology reasoning, or vector retrieval.
- Rebuild processes the complete local graph; incremental ENG-011 change events are a future compatible optimization.
- Knowledge Update Requests from ENG-022 are architecturally reserved but not implemented before ENG-022 exists.
- The viewer polls once per second; a future read-only projection event may reduce requests.

## Future dependencies

ENG-013 consumes ENG-012’s public Knowledge contract to infer affordances but must not access storage/internal caches. ENG-015 may consume structured context through approved contracts but retains all planning. ENG-022 may later propose validated Knowledge Update Requests; ENG-012 alone validates/applies or rejects them. No later Engine may bypass ENG-011/012 to access Object Library.

## Freeze recommendation

ENG-012 satisfies implementation, architecture, persistence, contract, testing, documentation, integration, and regression gates. Freeze at contract 1.0.0/schema 1.0 is recommended after architecture review. Repository status remains truthfully “Awaiting Architecture Review” until that authority acts.
