# TaskIR Compiler Schema

Schema `1.0` uses immutable serializable contracts: `TaskIR`, `TaskNode`, `TaskEdge`, `TaskParameter`, `TaskCondition`, `TaskConstraint`, `TaskMetadata`, `TaskStatistics`, `TaskValidation`, `TaskCompilation`, and `TaskCompilationResult`.

`TaskIR` contains task/source/correlation identities, goal, resources, ordered nodes, dependency edges, task constraints, carried failure semantics, metadata/provenance, validation evidence, compilation report, schema/engine versions, checksum, and timestamps. `TaskNode` contains TaskID, NodeID, SemanticPlanID, PlanningRuleID, Action, ObjectID, KnowledgeID, AffordanceID, Parameters, Inputs, Outputs, Preconditions, Postconditions, Constraints, Priority, Metadata, versions, checksum, and timestamps.

Canonical checksums are SHA-256 over UTF-8 JSON with sorted keys, compact separators, and the checksum field omitted. TaskIR identity is a stable hash-derived identifier of Semantic Plan identity. Major schema incompatibility is rejected.
