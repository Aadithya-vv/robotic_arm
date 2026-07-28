# Engine 012 Framework Prompt

Implement and extend only ENG-012 Knowledge Engine.

ENG-012 owns immutable structured Knowledge Records, knowledge persistence, integrity, validation, consistency, rebuild, indexes/cache, lookup/search/filtering, summaries, statistics, and export. It may provide structured reasoning context but must never reason, infer missing facts, plan, identify intent, infer affordances, compile TaskIR, execute, control robots, edit Semantic Inventory, or access Object Library.

Follow ABP → GBP → repository → authoritative ENG-012 specification → concrete specification → this prompt. Preserve Rule 40: depend only on structural/public contracts. ENG-012 receives Semantic Objects through `SemanticInventorySource`; it must never import ENG-011’s implementation/package or any earlier/later concrete Engine. Composition Root alone binds implementations.

Knowledge persistence belongs to ENG-012 and is a rebuildable derived database. Write only through injected `KnowledgeStorage`; never modify `objects.json` or `semantic_inventory.json`. Store only facts supplied by Semantic Inventory or future validated Knowledge Update Requests. Empty knowledge is correct when the source contains no fact; guessing is prohibited.

Keep public records recursively immutable, deterministic, versioned, correlated, checksummed, and serializable. Validate lifecycle, configuration, contract versions, semantic source shape, capacity, checksum integrity, and dependency outcomes. Return explicit Succeeded, Rejected, or Failed responses and ENG-012-owned Explanation Records.

Protect all mutable state and caches with the Engine lock. Require unit, integration, serialization, migration, lookup, property/fact/category/relationship search, statistics, performance, regression, thread-safety, logging, Composition Root, API, and Rule 40 tests. Synchronize documentation and reports. Do not modify ENG-001–011. Freeze authority belongs to architecture review.
