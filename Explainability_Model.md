# Explainability Model

Immutable schema 1.0 contracts are `ExplanationRecord`, `ExplanationNode`, `DecisionTrace`, `DependencyTrace`, `ProvenanceRecord`, `RuleExplanation`, `ValidationExplanation`, `CompilationExplanation`, `EngineReference`, `ArtifactReference`, `Statistics`, and `Metadata`.

Every record carries explanation/artifact identities and type; source Engine/version; planning-rule, Semantic Plan, TaskIR, Knowledge, and Affordance references where declared; dependency chain; source and explanation checksums; validation; creation time; Engine/schema versions; metadata; decision, provenance, rule, and optional compilation structures. Missing non-applicable references are empty—not inferred.
