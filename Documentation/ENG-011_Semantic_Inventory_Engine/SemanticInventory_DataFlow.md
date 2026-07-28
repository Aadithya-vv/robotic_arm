# Semantic Inventory Data Flow

1. Composition Root initializes the existing Object Library.
2. Its adapter exposes records through `ObjectSource`.
3. ENG-011 validates identities and normalizes optional values.
4. It preserves Object IDs and derives semantic score, references, category/tag counts, and an ordered immutable snapshot.
5. Injected storage atomically writes `Assets/ObjectLibrary/semantic_inventory.json`.
6. Read/search/statistics/export calls return public contract responses.
7. Object create/edit/delete completes through the existing Object Library first, then WebAPI requests an ENG-011 refresh.
8. WebAPI exposes read-only JSON; the viewer polls the projection and never edits it.

On restart, the snapshot is rebuilt from `objects.json`; stale semantic data cannot become authoritative. On session cleanup, both permanent Object Library files remain preserved.
