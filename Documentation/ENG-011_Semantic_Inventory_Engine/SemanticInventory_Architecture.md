# Semantic Inventory Architecture

ENG-011 is a replaceable perception Engine between learned object metadata and future semantic intelligence. Its source and storage are protocols; the Composition Root binds `ObjectLibrarySemanticSource` and `JsonInventoryStorage`. The Engine owns immutable semantic snapshots and indexes only. Object Library retains object mutation/persistence ownership, ENG-012 retains reusable reasoning knowledge, and ENG-013 retains affordances.

```text
Integration/CompositionRoot
  ├─ ObjectLibrarySemanticSource ─┐
  ├─ JsonInventoryStorage ────────┼─> SemanticInventoryEngine
  └─ constructs/registers ────────┘       ├─ contract records
                                          ├─ search/statistics
                                          └─ owned snapshot
WebAPI reads public contract responses; React renders projections only.
```

The Engine is independently replaceable, thread-safe, local-first, robot-independent, and contains no imports of other Engine implementations.
