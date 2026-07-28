# ENG-015 Semantic Planner Engine Specification

## Authority and position

ENG-015 is the sole owner of validated Semantic Plans. It consumes only public ENG-012 Knowledge and ENG-013 Affordance projections plus explicit goals, constraints, configuration, and versioned planning rules. Its output is the validated Semantic Plan consumed by ENG-014.

## Responsibilities

- Validate supported goals and declared constraints.
- Select current Knowledge/Affordance resources without mutating them.
- Apply exact, versioned, deterministic planning rules.
- Create ordered semantic nodes and dependency edges.
- Validate identities, references, action support, ordering, and checksums.
- Persist, index, search, import, export, rebuild, and report statistics for Semantic Plans.

## Non-responsibilities

ENG-015 does not create TaskIR, trajectories, motion commands, inverse kinematics, simulator commands, servo output, detections, object-library records, Knowledge, or Affordances. It contains no AI, LLM, probabilistic, or heuristic planning path.

## Public operations

`create_plan`, `validate_plan`, `get_plan`, `search_plans`, `search_goals`, `export_plan`, `import_plan`, `get_statistics`, `rebuild`, and lifecycle operations.

## Persistence

The sole authoritative store is `Assets/SemanticPlans/semantic_plans.json`. Writes are atomic. Upstream stores are read-only. Schema, engine, and rule versions plus SHA-256 checksums make compatibility and integrity explicit.

## Determinism and failure

Normalized goals require exact rule matches. Resources are sorted by stable Affordance ID. Unsupported goals, missing capabilities, stale Knowledge references, invalid graphs, incompatible schemas, and checksum failures are rejected explicitly.

