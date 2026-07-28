# Architecture

`SemanticPlannerEngine` receives narrow Knowledge, Affordance, storage, configuration, clock, and logging dependencies. Composition Root adapters translate only public ENG-012/013 responses. The engine owns its plan collection and serialized representation; it never writes upstream projections.

