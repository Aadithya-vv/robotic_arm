# Engine 013 Affordance Engine Engineering Specification

ENG-013 converts ENG-012 Knowledge Records into immutable robot-independent Affordance Records by exact-match, explicit, versioned rules. It owns generation, summaries, storage, indexes/cache, validation/checksums, search/lookup, export, statistics, migration, and rebuild. It owns no Knowledge, semantics, objects, reasoning, ML, heuristics, intent, planning, TaskIR, robot motion, skills, or execution.

Input arrives only through `KnowledgeSource`; storage/logging are injected protocols and configuration fixes capacity/rule version. Output records contain AffordanceID, ObjectID, KnowledgeID, ObjectName, Summary, Affordances, Preconditions, Postconditions, Constraints, SafetyNotes, Confidence, KnowledgeSources, GenerationRule, Metadata, SchemaVersion, EngineVersion, Checksum, Created, and Updated.

```text
ENG-012 public contract -> Composition adapter -> KnowledgeSource
 -> exact Rule Catalog -> immutable AffordanceGraph
 -> atomic affordance_graph.json + read-only APIs/viewer
```

Rules match normalized category or object name exactly and union/deduplicate/sort actions. Unknown inputs yield a valid empty capability record. No fallback or similarity matching exists. State transitions are Empty→Building→Available, Available→Updating→Available/Invalid, Available→Closed. One re-entrant lock protects graph and ID/Object caches.

Storage atomically rebuilds `Assets/ObjectLibrary/affordance_graph.json`; upstream files are never opened or modified. Public API: initialize, rebuild, close, get all/one/by object, search object/capability/action, export, validate, statistics. Failures are explicit for invalid request/state/config/source, capacity, storage, checksum, or logging.

Validation covers every catalog rule, exact/no-guess behavior, immutable serialization, migration, integrity, lookup/search, statistics, configuration, concurrency, 1,000 records, Composition Root/APIs/UI, Rule 40, and all prior regressions. Future rule additions require a version bump and tests; robot-specific feasibility belongs downstream.
