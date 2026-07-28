# Knowledge Engine Data Flow

1. ENG-011 starts and exposes its immutable inventory through its public contract.
2. Composition Root adapter requests all Semantic Objects and validates success.
3. ENG-012 validates structural records and copies only declared metadata.
4. It generates stable `knowledge:<ObjectID>` identities, explicit facts/properties, provenance-only summaries, and SHA-256 integrity checksums.
5. It builds immutable statistics and ID caches.
6. Injected storage atomically writes `knowledge_graph.json`.
7. Public reads/searches return contract responses; WebAPI projects them without mutation.
8. After Object Library mutation, WebAPI refreshes ENG-011 first and then rebuilds ENG-012. Startup always rebuilds in the same order.
