# Specification Generation Report

## Engineering Mode Transition Notice

This document is a preserved historical stage report. Its original review/readiness findings remain unchanged below. The one-time Engineering Mode transition subsequently approved and froze the architecture and Contracts package and marked all Engine specifications and Framework Prompts Implementation Ready; current readiness is governed by Engineering_Mode_Transition_Report.md.

## Document Information

| Field | Value |
|---|---|
| Project | TaskGraph — Semantic Robotic Manipulation Platform |
| Stage | Engineering Specification Generation |
| Status | Complete — Awaiting Specification Review |
| Date | 2026-07-14 |
| Governing Sources | ABP, GBP, and frozen repository navigation documents |

## Scope Completed

- Read the governing ABP, GBP, Repository Manifest, Engine Index, Dependency Map, Engineering Standards, Repository Guide, and Development Workflow.
- Replaced all twenty-four repository-generation specification placeholders with complete implementation-grade Draft specifications.
- Replaced all twenty-four repository-generation prompt placeholders with complete single-Engine Draft Framework Prompts.
- Cross-validated catalogue responsibilities and candidate contract relationships.
- Generated no source code, APIs, algorithms, tests, SDKs, packages, or implementation artifacts.
- Modified no ABP, GBP, repository structure, Engine documentation, report template, or implementation status artifact.

## Specifications Generated

Twenty-four authoritative Draft specifications were generated under `Specifications/`, one for each Engine from ENG-001 through ENG-024.

Each specification now contains:

- purpose, scope, and catalogue responsibilities;
- inputs, outputs, and behavioral public contract;
- internal responsibilities and privacy boundary;
- candidate external contract dependencies;
- explicit non-responsibilities;
- lifecycle and Draft state-transition model;
- error handling, configuration, and logging expectations;
- acceptance criteria and test requirements;
- qualitative performance expectations;
- future extension points, traceability, and open review items.

All specifications remain Draft and explicitly prohibit implementation until their review items and dependency contracts are approved.

## Framework Prompts Generated

Twenty-four authoritative Draft Framework Prompts were generated under `Prompts/`, one for each Engine.

Every prompt:

- requires reading ABP, GBP, repository navigation, the target specification, and dependency specifications;
- authorizes implementation of exactly one Engine;
- enforces Rule 40 and production-quality engineering expectations;
- restricts modification to the target Engine's Source, Tests, Documentation, Implementation Report, and truthful Implementation Status update;
- requires tests, documentation, reporting, and status synchronization;
- defines mandatory stop conditions for missing approval, ambiguity, conflict, undocumented behavior, or unavailable contracts;
- requires Codex to stop after implementing the single Engine.

## Missing Information

The governing architecture does not define the following implementation prerequisites:

1. Concrete public-contract operation names, type signatures, or schemas.
2. Shared envelope conventions for identity, correlation, provenance, validity, errors, and versioning.
3. Exact required and optional Engine dependencies.
4. Startup/shutdown ordering and dependency failure propagation.
5. TaskIR schema, validation rules, versioning, and simulator mapping.
6. Simulation SDK protocol, transport, retry, timeout, and compatibility rules.
7. Configuration keys, defaults, ranges, reload behavior, and secret-handling rules.
8. Persistence policy for semantic knowledge, replay history, reports, and feedback.
9. Quantitative latency, throughput, capacity, retention, and resource limits.
10. User-approval representation and enforcement contract before execution.

These items are flagged in the Draft specifications and were not invented.

## Ambiguities Discovered

### Planner and TaskIR Compiler order

The semantic workflow requires planning before TaskIR generation, but catalogue numbering and roadmap order place ENG-014 TaskIR Compiler before ENG-015 Planner. Operational dependency and implementation order require architecture approval.

### Planning-layer output ownership

ABP-03 describes TaskIR as the Planning Layer output, while ABP-04 separates semantic plan generation (ENG-015) from TaskIR compilation (ENG-014). The boundary must define a validated semantic-plan contract without merging responsibilities.

### Demonstration intent understanding

Project identity requires understanding demonstrated actions, intent, dependencies, and goals. ENG-021 owns demonstration workflow coordination but does not explicitly own temporal action or intent inference. No other catalogue responsibility states this ownership directly.

### User approval enforcement

User validation before execution is mandatory, but the Engine that creates, records, and verifies approval evidence is not explicitly identified.

### Persistence ownership

Memory owns temporary runtime state, Knowledge owns reusable semantic knowledge, Replay records execution history, Feedback records corrections, and Report produces reports. The persistence provider and retention boundaries for each artifact class are unspecified.

## Responsibility Conflicts Requiring Review

No catalogue responsibility is duplicated verbatim, and no Engine was added, merged, or split. The following semantic boundaries nevertheless require clarification:

1. **Kernel versus Execution:** ENG-002 coordinates execution globally; ENG-017 coordinates the execution lifecycle. Kernel must remain runtime coordination while Execution owns TaskIR execution.
2. **Event Bus versus Logging:** ENG-005 publishes/delivers events; ENG-007 records events. Event delivery and event persistence/diagnostics must remain distinct.
3. **Scene versus Semantic Inventory:** ENG-010 tracks objects; ENG-011 maintains semantic object identities. Physical/observational tracking identity must be distinguished from semantic identity.
4. **Knowledge versus Feedback:** ENG-012 stores reusable knowledge; ENG-022 improves semantic knowledge. Feedback should submit approved improvement requests while Knowledge owns storage/mutation, subject to architectural confirmation.
5. **Reasoning Engines versus Explainability:** reasoning Engines must expose explanations, ENG-016 owns explanation production, and ENG-020 displays reasoning. The producer/aggregator/presenter split needs a shared explanation contract.
6. **Replay versus Logging/Memory:** replayable execution history is not the same as diagnostic logs or temporary runtime memory; storage and retention boundaries need approval.
7. **Report Engine versus implementation engineer:** ABP assigns Implementation Report generation to Codex while ENG-023 says it produces implementation reports. Runtime Engine behavior versus engineering workflow ownership requires clarification.

## Dependency Questions and Potential Cycles

Candidate dependencies in the Draft specifications are explicitly non-authoritative. Cross-validation identified potential cycles that must be removed or mediated through contracts/providers:

- Configuration may use Logging while Logging may require Configuration.
- Knowledge may accept Feedback updates while Feedback requires Knowledge to apply improvements.
- Planner may coordinate explanations while Explainability consumes Planner reasoning.
- Dashboard participates in Demonstration and Feedback interaction while those Engines may publish state back to Dashboard.
- Bootstrap, Kernel, Registry, Configuration, and Logging have startup relationships whose direction and minimal bootstrap subset are not specified.

These are dependency-design questions, not circular responsibility ownership. DependencyMap.md must be updated through architecture review before implementation.

## Cross-Validation Result

| Check | Result |
|---|---|
| Engines represented | 24 of 24 |
| One authoritative specification per Engine | Pass |
| One authoritative Framework Prompt per Engine | Pass |
| Catalogue responsibility text assigned once | Pass |
| Engines added, removed, merged, or split | None |
| Duplicate authoritative artifacts | None |
| Confirmed circular responsibility ownership | None |
| Candidate dependency cycles | Present; review required |
| Architectural ambiguities | Present; documented above |
| Source code or tests generated | None |

## Recommendations

1. Resolve the Planner/TaskIR boundary and approve the operational order before reviewing ENG-014 and ENG-015.
2. Define a shared contract vocabulary for request identity, correlation, provenance, validation, outcomes, errors, and contract versioning.
3. Approve a contract-level dependency map, including startup order and failure propagation, beginning with Core Platform Engines.
4. Allocate temporal demonstration action/intent understanding to an existing Engine through clarification or use an EDR if catalogue ownership must change.
5. Define the user-approval evidence and enforcement boundary before ENG-017.
6. Clarify Feedback/Knowledge mutation, explanation production/presentation, replay persistence, and Report Engine boundaries.
7. Establish Engine-specific quantitative performance targets only where evaluation requires them.
8. Review and approve specifications domain-by-domain in the roadmap order; do not approve Framework Prompts before their specifications and dependencies.

## Readiness for Implementation

**Ready for specification review; not yet ready for Engine implementation.**

Every Engine now has a complete Draft specification and Draft Framework Prompt. Implementation remains prohibited until the Systems Architect resolves applicable ambiguities, approves concrete behavioral contracts and dependencies, approves the target specification and prompt, and authorizes the Engine's implementation order.

## Completion Statement

Engineering Specification Generation is complete. Work stops here and awaits specification review.
