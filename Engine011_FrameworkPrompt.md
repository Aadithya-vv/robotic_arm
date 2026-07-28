# Engine 011 Framework Prompt

Implement and extend only ENG-011 Semantic Inventory Engine.

ENG-011 owns immutable semantic records, normalization, stable semantic identity projection, consistency, search/filter indexes, statistics, export, derived snapshot persistence, lifecycle, validation, diagnostics, and its own Explanation Records. It never owns detection, recognition, Object Library editing, general knowledge/reasoning, affordance inference, planning, TaskIR, execution, UI behavior, or robot-specific data.

Follow ABP → GBP → repository → authoritative specification → this prompt. Follow Rule 40 without exception: consume only `ObjectSource`, `InventoryStorage`, and other approved structural contracts; never import another Engine’s implementation or the Composition Root. Concrete construction and provider binding belong exclusively to the Composition Root.

Keep all public records frozen, versioned, correlated, serializable, deterministic, and backward compatible. Validate requests, major contract versions, lifecycle states, source identities, and output invariants. Return explicit Succeeded, Rejected, or Failed outcomes. Never hide dependency errors, invent knowledge, mutate source objects, or present partial work as success.

Protect owned mutable state with the Engine lock. Do not hold references to caller-owned mutable collections. Keep persistence atomic and replaceable. Treat `objects.json` as an external authoritative source; ENG-011 may write only its derived semantic snapshot through injected storage.

Every change requires isolated tests for normal behavior, boundaries, invalid state, source/storage failure, deterministic serialization, search/category/alias/tag behavior, migration, performance, thread safety, Rule 40 imports, and compatibility. Synchronize specification, architecture, API, data-flow, test-plan, documentation, implementation report, and truthful status. Freeze authority remains with architecture review.
