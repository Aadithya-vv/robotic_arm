# Framework Prompt — ENG-020 Dashboard Engine

## Document Control

| Field | Value |
|---|---|
| Engine | ENG-020 — Dashboard Engine |
| Status | Implementation Ready — Engineering Mode |
| Specification | Specifications/ENG-020_Dashboard_Engine/Specification.md |

## Mission

Implement only ENG-020 — Dashboard Engine. Its architectural purpose is: Provide the primary user interface.

## Required Reading

Before any implementation action:

1. Read all documents in ABP/ and GBP/.
2. Read RepositoryManifest.md, EngineIndex.md, DependencyMap.md, RepositoryGuide.md, DevelopmentWorkflow.md, ImplementationStatus.md, and Contracts/SharedContracts.md.
3. Read this Engine's Implementation Ready specification completely, Contracts/TaskIRContract.md, and the Approval Token contract in Contracts/SharedContracts.md.
4. Read relevant dependency specifications and the frozen DependencyMap; use contracts, interfaces, providers, mocks, or stubs for Engines not yet implemented.
5. Inspect existing repository state and preserve unrelated user changes.

## Authorized Responsibility

- Display platform state.
- Display reasoning exposed by ENG-016.
- Display execution.
- Own explicit user approval and issue Approval Tokens bound to exact validated TaskIR identity/version and correlation context; never execute TaskIR.

Implement no other Engine and no behavior listed as a non-responsibility in the specification.

## Engineering Rules

- Follow the authority order ABP → GBP → Repository → Specification → Framework Prompt → Implementation.
- Follow Rule 40: depend only on approved interfaces, contracts, or providers, never concrete Engine internals.
- Produce Dashboard-owned Explanation Records for Dashboard decisions and display explanations exposed by ENG-016; do not aggregate or alter other Engines' reasoning.
- Generate production-quality, readable, maintainable, modular, deterministic, testable, and documented code.
- Preserve the approved lifecycle, state transitions, validation, error behavior, configuration boundary, observability, and acceptance criteria.
- Handle failures explicitly and never fabricate successful behavior.
- Keep implementation details private and independently replaceable.
- Do not redesign architecture, rename/split/merge Engines, add layers, reorganize the repository, or implement undocumented behavior.

## Authorized Locations

- Implementation/ENG-020_Dashboard_Engine/Source/
- Tests/ENG-020_Dashboard_Engine/
- Documentation/ENG-020_Dashboard_Engine/
- Reports/ENG-020_Dashboard_Engine/ImplementationReport.md
- ImplementationStatus.md only for the truthful status update required by the completed implementation workflow.

Do not modify ABP/, GBP/, other Engine workspaces, specifications, prompts, or unrelated artifacts.

## Testing and Documentation

Implement tests for expected behavior, failure behavior, state transitions, contract compliance, Rule 40 compliance, lifecycle cleanup, observability, and integration readiness. Update this Engine's documentation to describe the implemented public contract and operational behavior.

## Reporting and Status

Update the authoritative Implementation Report with files created/modified, public interfaces, dependency contracts, test commands/results, limitations, deviations, and recommendations. Update ImplementationStatus.md truthfully. Do not mark the Engine frozen; freeze authority belongs to architecture review.

## Mandatory Stop Conditions

Stop engineering only if implementation would violate architecture or Rule 40, cross an Engine boundary, encounter repository inconsistency, or expose a genuine architectural ambiguity. An unimplemented future Engine is not by itself a blocker: use its contract, interface, provider, mock, or stub. Report genuine blockers instead of guessing.

## Completion Condition

When this Engine alone is implemented, tested, documented, reported, and its status updated, stop. Wait for implementation review. Do not begin another Engine.