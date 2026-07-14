# Template Definitions

---

# Document Information

| Field | Value |
|---|---|
| Document ID | GBP-06 |
| Document Name | Template Definitions |
| Package | Generated Blueprint Package (GBP) |
| Version | 1.0 |
| Status | Generated for Architecture Review |
| Project | TaskGraph – Semantic Robotic Manipulation Platform |
| Derived From | ABP-00, ABP-01, ABP-02, ABP-03, ABP-04, ABP-09 |
| Used By | Repository Generation, Engine Specifications, Framework Prompts, Reports, EDRs |

---

# Purpose

This document defines consistent content templates for artifacts required by the ABP. It specifies document shape and traceability fields only. It does not generate those artifacts, select technologies, or define Engine behavior.

# General Document Header

Every controlled engineering document shall begin with:

```text
# <Document Name>

## Document Information

Document ID: <stable identifier>
Document Name: <human-readable name>
Package or Artifact Type: <type>
Version: <version>
Status: <Draft | In Review | Approved | Frozen>
Project: TaskGraph – Semantic Robotic Manipulation Platform
Engine: <ENG-NNN and name, when applicable>
Depends On: <authoritative artifacts>
Used By: <downstream artifacts>

## Revision History

<version, description, approval status>
```

Identifiers and Engine names shall match the approved catalogue and remain unchanged after approval.

# Repository Manifest Template

The Repository Manifest shall provide:

1. Purpose and governing documents.
2. Approved top-level directories.
3. Artifact-to-path mapping.
4. Engine-to-specification mapping.
5. Engine-to-prompt mapping.
6. Engine-to-implementation mapping.
7. Engine-to-test mapping.
8. Engine-to-report mapping.
9. Artifact status and approval state.
10. Integrity and traceability checks.

It shall not add top-level directories beyond `ABP`, `GBP`, `Specifications`, `Prompts`, `Implementation`, `Reports`, `Documentation`, `Research`, `Assets`, and `Tests`.

# Engine Specification Template

Each Engine specification shall contain:

1. **Document information** — stable Engine ID/name, dependencies, version, and approval state.
2. **Purpose** — the single responsibility copied from and expanded consistently with ABP-04.
3. **Scope** — included behavior and explicit exclusions.
4. **Architectural placement** — domain, layer participation, and upstream/downstream boundaries.
5. **Responsibilities** — complete owned behaviors without ownership overlap.
6. **Public contract** — operations, inputs, outputs, observable state, and contract invariants.
7. **Data definitions** — required structures, validation constraints, and semantic meaning.
8. **Dependencies** — contracts/providers only, including whether each is required or optional.
9. **Lifecycle** — initialization, normal operation, shutdown, and cleanup where applicable.
10. **Behavioral flows** — deterministic success paths and important alternate paths.
11. **Failure behavior** — meaningful diagnostics, propagation, recovery, and stability expectations.
12. **Events and observability** — externally visible events, logging expectations, and traceability.
13. **Explainability obligations** — human-readable information exposed by the Engine where applicable.
14. **Configuration** — required settings and validation, without embedding implementation choices not architecturally approved.
15. **Security and safety constraints** — validation and execution approval boundaries applicable to the Engine.
16. **Testing requirements** — expected behavior, failure behavior, contract compliance, and integration readiness.
17. **Acceptance criteria** — objective conditions for implementation review.
18. **Known limitations and extension points** — Version 1 boundaries and contract-preserving future growth.
19. **Traceability matrix** — each requirement mapped to ABP/GBP source and planned verification.
20. **Approval and freeze record**.

Unspecified algorithms, frameworks, protocols, schemas, or dependencies shall be marked for architectural resolution rather than invented.

# Framework Prompt Template

Each Framework Prompt shall contain:

1. Engine identity and implementation mission.
2. Governing documents in authority order.
3. Files and artifacts that must be read before work.
4. Authorized scope and explicit exclusions.
5. Required public contract and dependency rules.
6. Required implementation artifacts.
7. Coding, error-handling, documentation, and deterministic-behavior expectations.
8. Required tests and acceptance checks.
9. Repository paths authorized for modification.
10. Implementation Report requirement.
11. Stop conditions for ambiguity, conflict, or missing specifications.
12. Completion condition: implement the one Engine, report, and stop.

A Framework Prompt shall operationalize an approved specification; it shall not supplement it with new requirements.

# Implementation Report Template

```text
# <ENG-NNN — Engine Name> Implementation Report

## Document Information
## Governing Specification and Prompt
## Engine Implemented
## Summary of Work Completed
## Files Created
## Files Modified
## Public Interfaces Implemented
## Dependencies and Contract Compliance
## Tests Completed and Results
## Error and Failure Behavior Verified
## Documentation Updated
## Deviations
## Known Limitations
## Future Recommendations
## Traceability and Acceptance Checklist
## Review and Freeze Status
```

The Deviations section shall state `None` when implementation exactly matches the specification. Any architectural deviation prevents completion and requires review; it may not be normalized after the fact in the report.

# Engineering Decision Record Template

Every post-approval architectural change shall use:

```text
# EDR-<identifier> — <Decision Title>

## Status
<Proposed | Approved | Rejected | Superseded>

## Problem
## Current Architectural Rule
## Proposed Change
## Rationale
## Alternatives Considered
## Impact
## Affected Artifacts and Engines
## Compatibility and Migration Considerations
## Approval
## Implementation Conditions
```

Only an approved EDR authorizes modification of frozen architectural artifacts.

# Documentation Template

User-facing and developer-facing documents shall include audience, purpose, prerequisites, workflow or API description, validation/error guidance, limitations, and links to the authoritative engineering artifacts. Documentation shall explain system behavior without duplicating specifications.

# Research Artifact Template

Research records shall identify the research question, relation to TaskGraph's semantic contribution, method, experiment conditions, evaluation metrics, observations, limitations, and evidence linking claims to demonstrable system behavior.

# Template Compliance Rules

- One authoritative artifact shall occupy one logical location.
- Required sections may be marked not applicable with justification; they shall not be silently omitted.
- Templates may be expanded with implementation-grade detail but may not redefine architecture.
- Approval and freeze status shall be explicit.
- Human-readable explanations and stable traceability shall be maintained.

---

End of Document.
