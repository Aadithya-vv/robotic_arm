# ENG-015 Framework Prompt

Implement or review ENG-015 only within these invariants:

1. Preserve `DependencyMap.md`, `Contracts/SharedContracts.md`, `Contracts/TaskIRContract.md`, and ENG-014 specifications unchanged.
2. Treat ENG-015 as the sole Semantic Plan owner and ENG-014 as its downstream consumer.
3. Read Knowledge and Affordances only through injected public contracts.
4. Use exact, versioned, deterministic rules; never infer or invent an action.
5. Reject unsupported goals and missing capabilities.
6. Emit semantic actions, conditions, resources, constraints, dependencies, validation, provenance, versions, timestamps, and checksums.
7. Never emit TaskIR, motion, trajectories, IK, simulation, or hardware commands.
8. Persist only to `Assets/SemanticPlans/semantic_plans.json` using atomic replacement.
9. Validate imported and stored plans before accepting them.
10. Wire the engine only through the Composition Root.

