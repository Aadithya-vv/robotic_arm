# TaskGraph v1.2 Engine 013 Affordance Engine Report

## Architecture review and responsibilities

ABP/GBP, Rule 40, Contracts, Dependency Map, frozen ENG-011/012 specifications/prompts/reports/public contracts, Composition Root, storage, WebAPI, UI, launcher, and lifecycle were reviewed. ENG-013 alone owns affordance generation, rules, records, storage, index/cache, validation, lookup/search, summaries, export, statistics, migration, and rebuild. It owns no Knowledge, semantics, objects, reasoning, inference, intent, planning, TaskIR, robot skills/motion, Scene, or execution.

Pipeline enforcement: Object Library → ENG-011 → ENG-012 → Composition public-contract adapter → ENG-013. ENG-013 source imports no upstream concrete package.

## Rule system and catalog

Catalog 1.0.0 contains exact category `container` plus exact names cup, bottle, knife, spoon, plate, and bowl. Matching is case-insensitive exact equality; matches union, deduplicate, and lexically sort actions. Output records retain every `rule_id@version`. Unknown objects receive no guessed capability. Actions are explicitly categorized as manipulation, transport, container, access, tool use, or food handling.

## Affordance model and storage

Immutable records contain every required identity, action, condition, constraint, safety, confidence, provenance, rule, metadata, version, checksum, and timestamp field plus a deterministic summary. SHA-256 validates canonical record integrity.

`Assets/ObjectLibrary/affordance_graph.json` is atomically written and fully rebuilt at startup or upstream change. ENG-013 never opens/modifies `knowledge_graph.json`, `semantic_inventory.json`, or `objects.json`; legacy derived graphs migrate by rebuild.

## Composition Root and API

The Root injects `KnowledgeAffordanceSource`, JSON storage, configuration, and logging; registers ENG-013; starts it after ENG-012; includes it in health/validation; and shuts it down first. Upstream object changes refresh/rebuild ENG-011→012→013 in order.

Read-only routes: `GET /affordances`, `/{id}`, `/search`, `/actions`, `/statistics`. The minimal viewer shows objects, capabilities, action categories, search, capability badges, and details without editing.

## Tests and validation

The 27 isolated tests cover contract/lifecycle, immutable complete model, category/name rules and union, spoon/bottle examples, unknown no-guess behavior, version, ID/Object lookup, query/capability/action search, statistics, serialization, checksum integrity, migration, atomic storage, rebuild, concurrency, 1,000-record performance, logging, configuration, and Rule 40.

| Validation | Result |
|---|---|
| ENG-013 | PASS — 27/27 |
| ENG-001–013 | PASS — 396 tests |
| Launcher/session | PASS — 5/5 |
| Thirteen-Engine health/registry | PASS |
| Affordance API projections | PASS — collection/search/actions/statistics 200 |
| Python/TypeScript | PASS |
| ESLint | PASS — zero errors, one pre-existing warning |
| Vite production build | PASS — 2,215 modules |
| Storage/migration/integrity | PASS |
| Thread safety | PASS — 20 readers |
| Performance | PASS — 1,000 records below two seconds |
| Rule 40/upstream isolation | PASS |

## Files added

- `Engine013_AffordanceEngine_Specification.md`, `Engine013_FrameworkPrompt.md`
- `Implementation/ENG-013_Affordance_Engine/Source/taskgraph_affordance/{__init__,contracts,engine,rules,storage}.py`
- `Integration/CompositionRoot/affordance.py`
- `Tests/ENG-013_Affordance_Engine/test_affordance_engine.py`
- Five `Documentation/ENG-013_Affordance_Engine/Affordance*.md` documents including Rule Catalog
- `Assets/ObjectLibrary/affordance_graph.json`
- `TaskGraph_v1.2_Engine013_AffordanceEngine_Report.md`

## Files modified

- Composition Root runtime/startup/shutdown/health/validation
- WebAPI adapter
- WebApp App/components/lib/pages and Vite proxy
- ENG-013 README and standard implementation report
- `ImplementationStatus.md`

No ENG-001–012 source, Launcher, detection, Object Library implementation, session lifecycle, ABP, GBP, or Contracts file changed.

## Performance and limitations

Build is O(records × catalog rules); the fixed seven-rule catalog makes this effectively linear. ID/Object lookup is O(1), search O(records). Rules describe abstract capabilities, not feasibility in a specific scene or robot. Preconditions/postconditions are generic declarative placeholders; execution safety and geometric validation belong downstream. Catalog coverage is intentionally small and unknown objects remain empty.

## Future dependencies and freeze recommendation

Future planning/TaskIR may consume the public Affordance contract but cannot access graph internals. Rule additions require backward-compatible catalog/version review and tests. Robot-specific feasibility belongs execution/simulation Engines.

ENG-013 satisfies architecture, implementation, rules, persistence, testing, documentation, integration, and regression gates. Freeze at contract/rules/schema 1.0 is recommended after architecture review; status remains “Awaiting Architecture Review” until that authority acts.
