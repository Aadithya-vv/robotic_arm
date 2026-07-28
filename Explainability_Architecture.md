# Explainability Architecture

ENG-016 is a read-only observer after ENG-014. The composition root adapts upstream public contracts into one `ArtifactSource`; the engine itself knows no concrete Engine. Its deterministic formatter constructs immutable records, canonical checksums, dependency nodes, decision traces, provenance, and validation/compilation summaries. `ExplanationStorage` is independently replaceable and stores no upstream artifact.

Rule 40 is preserved. REST and WebApp code are presentation adapters only and contain no explanation derivation logic.
