# Dependency Map

## Status

Consolidated Draft reflecting approved architectural ownership decisions. This map defines direction and ownership at the architectural-contract level. It authorizes no concrete imports, bindings, APIs, transport, or implementation dependency.

## Shared Contract Rule

All cross-Engine interactions conform to [SharedContracts.md](Contracts/SharedContracts.md). TaskIR interactions additionally conform to [TaskIRContract.md](Contracts/TaskIRContract.md). Rule 40 remains immutable: Engines depend on approved contracts or providers, never concrete Engine implementations.

## Primary Semantic and Execution Flow

```text
ENG-021 Demonstration
        │ validated demonstration data
        ▼
ENG-015 Planner
        │ Semantic Plan
        ▼
ENG-014 TaskIR Compiler
        │ validated TaskIR
        ├──────────────────────────────┐
        ▼                              │
ENG-020 Dashboard                      │
        │ Approval Token               │
        └──────────────┬───────────────┘
                       ▼
                ENG-017 Execution
                       │ execution exchange
                       ▼
             ENG-018 Simulation Connector
```

### Ownership

- ENG-015 owns demonstrated task-intent understanding and Semantic Plan generation.
- ENG-014 consumes a validated Semantic Plan and produces validated TaskIR.
- ENG-020 owns explicit user approval and issues an Approval Token bound to the exact TaskIR identity/version and correlation context.
- ENG-017 consumes validated TaskIR and the matching Approval Token. It never generates approval.
- ENG-018 owns communication with the independent simulation boundary.

Catalogue identifiers remain unchanged. The operational order is Planner before TaskIR Compiler even though ENG-014 numerically precedes ENG-015.

## Feedback and Knowledge Flow

```text
User feedback
     ▼
ENG-022 Feedback
     │ Knowledge Update Request
     ▼
ENG-012 Knowledge
     │ validated applied/rejected outcome
     ▼
Reusable semantic knowledge
```

- ENG-022 captures and validates feedback and produces Knowledge Update Requests.
- ENG-022 never modifies, stores, or applies Knowledge changes.
- ENG-012 validates each request and alone owns applying or rejecting the update.

## Explanation Flow

```text
Every Engine
     │ owned Explanation Records
     ▼
ENG-016 Explainability
     │ aggregated, linked, formatted, exposed explanations
     ▼
ENG-020 Dashboard
     │ display
     ▼
User
```

- Every Engine owns the facts and reasoning in its Explanation Records.
- ENG-016 aggregates, links, formats, and exposes explanations without changing their owned meaning.
- ENG-020 displays explanations and does not aggregate or become their reasoning owner.

## Runtime Reporting Boundary

ENG-023 is the Runtime Reporting Engine. It consumes approved runtime information and produces runtime operation reports, execution summaries, and runtime analysis reports. Engineering specifications, Framework Prompts, Implementation Reports, architecture reports, and repository workflow reports remain outside runtime architecture. ENG-024 may export completed runtime reports through its own contract.

## Contracts Package

`Contracts/` is a repository-level architectural package, not an Engine. It owns no runtime behavior, lifecycle, state, or implementation. It defines shared semantic boundaries only.

## Engineering Mode Dependency Policy

The approved decisions resolve Planner/TaskIR order, Feedback/Knowledge mutation, explanation ownership, demonstration intent ownership, user approval ownership, and runtime reporting scope.

ENG-001 establishes the initial runtime lifecycle. During incremental engineering, future Engines are unavailable by design and are represented through contracts, interfaces, injected providers, mocks, or stubs. ENG-001 shall never import, instantiate, or depend on their concrete implementations and shall never perform their responsibilities.

For the Core Platform:

- Bootstrap receives the capability providers required for a particular startup composition.
- A missing required capability produces an explicit startup validation failure.
- Optional or not-yet-implemented capabilities may use contract-conforming stubs.
- Configuration and Logging do not form a concrete startup cycle: Bootstrap interacts with their abstract capabilities, and a minimal/no-op diagnostic provider may stand in until Logging is implemented and configured.
- Shutdown occurs through the lifecycle contracts supplied to the active composition; Bootstrap owns initial lifecycle establishment, not another Engine's shutdown behavior.

Persistence strategy, simulation transport details, quantitative timeouts/retries, and exact optional capability sets are engineering choices within the frozen contracts and Engine boundaries. They become blockers only if implementation reveals a genuine architectural ambiguity. No additional Engine dependency is inferred by this map.
