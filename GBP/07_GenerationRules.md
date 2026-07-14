# Generation Rules

---

# Document Information

| Field | Value |
|---|---|
| Document ID | GBP-07 |
| Document Name | Generation Rules |
| Package | Generated Blueprint Package (GBP) |
| Version | 1.0 |
| Status | Generated for Architecture Review |
| Project | TaskGraph – Semantic Robotic Manipulation Platform |
| Derived From | ABP-00, ABP-01, ABP-02, ABP-03, ABP-04, ABP-09 |
| Used By | Repository Generation and All Subsequent Artifact Generation |

---

# Purpose

This document converts ABP governance into deterministic generation rules. These rules govern repository generation, specifications, Framework Prompts, implementation artifacts, tests, reports, documentation, and research artifacts after the GBP is approved.

# Precedence

Generation shall follow this authority order:

```text
ABP → approved GBP → Repository Manifest → Engine Specification
    → Framework Prompt → Implementation and Tests → Implementation Report
```

When artifacts conflict, generation shall stop. A lower-level artifact shall never override a higher-level artifact.

# Universal Generation Rules

1. Read all governing repository artifacts before generation.
2. Generate only the artifact type and scope explicitly authorized.
3. Preserve project identity, Version 1 scope, and research contribution.
4. Preserve all approved document IDs, Engine IDs, Engine names, domains, layers, and responsibilities.
5. Never introduce an Engine, architectural layer, or top-level directory without an approved EDR.
6. Assign every functional behavior to exactly one Engine.
7. Depend on public contracts or providers, never concrete implementations.
8. Keep each generated artifact in one authoritative location.
9. Include source traceability, status, and review information.
10. Record an unresolved item and stop when required detail cannot be derived without architectural invention.

# Repository Generation Rules

Repository generation may occur only after architecture review approves the ABP and GBP.

The generated repository shall contain exactly these top-level directories:

```text
ABP/
GBP/
Specifications/
Prompts/
Implementation/
Reports/
Documentation/
Research/
Assets/
Tests/
```

Repository generation shall:

- preserve ABP and approved GBP documents;
- create a Repository Manifest mapping all authoritative artifacts;
- prepare one owned location per Engine for specifications, prompts, implementation, reports, and tests;
- use stable, descriptive, human-readable names consistently;
- avoid source code, undocumented behavior, duplicate artifacts, and unreferenced Engines unless that generation stage explicitly authorizes them.

# Specification Generation Rules

Specifications shall be generated and reviewed before their corresponding Framework Prompts or implementations.

For each Engine:

- begin with the exact catalogue purpose and responsibilities;
- define one stable public contract;
- identify contract-level dependencies explicitly;
- define inputs, outputs, lifecycle, invariants, validation, failure behavior, observability, tests, and acceptance criteria;
- preserve the progressive semantic data flow and validation points;
- expose human-readable reasoning where required by the architecture;
- state Version 1 exclusions;
- avoid selecting algorithms, libraries, protocols, or formats unless approved architectural material supplies them.

Specification generation shall pause when architectural ownership is ambiguous or a required cross-Engine contract cannot be defined consistently.

# Framework Prompt Generation Rules

A Framework Prompt may be generated only from an approved Engine specification. It shall:

- authorize implementation of one Engine only;
- list every governing artifact to read;
- identify allowed repository locations;
- restate contract, testing, documentation, reporting, and stop obligations;
- prohibit unrelated modifications and architectural decisions;
- end with the requirement to report completion and stop.

# Implementation Generation Rules

Implementation begins only after the repository, target specification, Framework Prompt, implementation order, and dependency specifications are approved.

Implementation shall:

- remain inside the target Engine's responsibility;
- implement contracts exactly as specified;
- keep internal implementation private and replaceable;
- provide meaningful diagnostics and never silently ignore failures;
- prioritize correctness, readability, maintainability, modularity, testability, and deterministic behavior;
- optimize only where justified;
- create corresponding tests and synchronized documentation;
- generate an Implementation Report;
- stop for architectural review before the next Engine.

# Test Generation Rules

Tests shall remain separate from production implementation and shall verify:

- expected behavior;
- failure behavior;
- public contract compliance;
- lifecycle and cleanup where relevant;
- deterministic and traceable interaction;
- integration readiness through contracts rather than concrete internals;
- acceptance criteria stated in the approved specification.

# Reporting Rules

Implementation Reports shall describe actual completed work. They shall enumerate created and modified files, interfaces, tests and results, limitations, and recommendations. Reports shall not conceal deviations or retroactively redefine requirements.

# Data-Flow Rules

Generated artifacts shall preserve the primary flow:

```text
Observation → Perception → Semantics → Knowledge
→ Planning → Execution → Feedback
```

Each transition shall preserve or enrich semantic meaning. Engines shall not bypass layers or perform responsibilities owned elsewhere. Important transitions shall support inspection and validation before execution.

# User and Simulation Boundary Rules

- The user shall be able to observe understanding, validate interpretations and plans, approve execution, review replay, and provide feedback.
- The UI shall expose platform understanding, not unnecessary implementation detail.
- Simulation shall remain independent and communicate through a stable connector/SDK contract.
- Version 1 generation shall not add physical hardware control, ROS, cloud services, distributed processing, autonomous navigation, voice interaction, mobile applications, multi-robot coordination, or industrial deployment/control.

# Quality Gates

An artifact may advance only when it is complete, traceable, internally consistent, reviewed, and approved. An Engine may be frozen only after its specification and Framework Prompt are approved, implementation is complete, tests pass, its report exists, and review is complete.

# Prohibited Generation

Generation shall never:

- invent requirements or undocumented behavior;
- duplicate ownership;
- couple to concrete Engine implementations;
- modify stable artifacts without authorization;
- place knowledge only in conversation history;
- use implementation convenience to replace scientific correctness;
- claim research behavior that is not demonstrable.

# Conflict Handling

On ambiguity, missing prerequisites, ownership overlap, repository inconsistency, or architectural conflict:

1. Stop the affected generation activity.
2. Identify the governing documents and conflicting statements.
3. Record the impact and required architectural decision.
4. Await clarification or an approved EDR.
5. Resume only from approved repository truth.

---

End of Document.
