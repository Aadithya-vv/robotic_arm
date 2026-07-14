# Role Catalogue

---

# Document Information

| Field | Value |
|---|---|
| Document ID | GBP-05 |
| Document Name | Role Catalogue |
| Package | Generated Blueprint Package (GBP) |
| Version | 1.0 |
| Status | Generated for Architecture Review |
| Project | TaskGraph – Semantic Robotic Manipulation Platform |
| Derived From | ABP-00, ABP-01, ABP-02, ABP-03, ABP-04, ABP-09 |
| Used By | Repository Generation, Specifications, Prompts, Reviews |

---

# Purpose

This document expands the responsibilities and authority already assigned by the Architecture Blueprint Package. It does not introduce organizational positions or transfer architectural authority. A role describes accountability in the TaskGraph lifecycle; one person or tool may perform a role only within the authority stated here.

# Authority Model

```text
Architecture Blueprint Package
        ↓
Generated Blueprint Package
        ↓
Repository
        ↓
Engine Specification
        ↓
Framework Prompt
        ↓
Implementation
```

Higher artifacts govern lower artifacts. A lower-level role may report an inconsistency but may not resolve it by changing architecture.

# Engineering Roles

## Systems Architect

**Purpose:** Own architectural intent and integrity.

**Accountabilities:**

- Author and approve ABP documents.
- Review the GBP and generated repository for conformance.
- Define and approve Engine specifications and Framework Prompts.
- Review Engine implementations and Implementation Reports.
- Approve freezes and Engineering Decision Records.
- Resolve architectural ambiguity and ownership conflicts.

**Authority:** May approve architectural artifacts and formally authorize architectural change through an EDR.

**Restrictions:** Shall preserve the project identity, Version 1 scope, and documented research contribution unless an approved EDR changes them.

## Implementation Engineer (Codex)

**Purpose:** Convert approved specifications into maintainable, production-quality implementation.

**Accountabilities:**

- Read the repository before acting.
- Implement only the requested, fully specified Engine.
- Depend on public contracts rather than concrete Engine internals.
- Create appropriate tests and synchronized documentation.
- Generate an accurate Implementation Report after each Engine.
- Stop and report missing specifications, ambiguity, conflicts, or inconsistency.

**Authority:** May create or modify implementation artifacts expressly authorized by an approved specification and Framework Prompt.

**Restrictions:** May not redesign architecture, rename Engines, change ownership, reorganize the repository, invent behavior, bypass specifications, or modify unrelated stable Engines.

## Architecture Reviewer

The ABP assigns review and approval to architectural authority. This catalogue therefore treats architecture review as a responsibility of the Systems Architect rather than as a new independent authority.

**Accountabilities:**

- Verify traceability from ABP through GBP, specifications, prompts, implementation, tests, and reports.
- Confirm interface-based dependencies and single responsibility.
- Accept, reject, or return an artifact for correction.
- Confirm that review is complete before an artifact is frozen.

## Repository Maintainer

Repository maintenance is an activity governed by the Systems Architect's repository design, not a separate architectural authority.

**Accountabilities:**

- Preserve the prescribed top-level structure.
- Maintain one authoritative location for each artifact.
- Prevent orphaned, duplicated, conflicting, or unreferenced artifacts.
- Preserve stable names and document identifiers.
- Ensure repository content remains the permanent engineering record.

# System Interaction Roles

## TaskGraph User

**Purpose:** Teach, validate, and review robotic tasks through human-centered interaction.

**Capabilities:**

- Provide a webcam-based demonstration.
- Observe live input and the system's progressively enriched understanding.
- Validate detected objects, semantic interpretations, and task plans.
- Approve execution.
- Review simulation execution and replay.
- Provide corrections and feedback.

The user is an active participant. Version 1 does not require the user to program robot motion or inspect internal algorithms.

## Simulation System

**Purpose:** Execute validated TaskIR-derived operations in PyBullet on the separate simulation machine.

**Boundary:** The simulation is independent of the platform and communicates through the stable Simulation Connector/SDK boundary. It has no authority over semantic reasoning, planning, or architectural state.

# Artifact Ownership Matrix

| Artifact | Responsible Producer | Approval/Review Authority | Governing Source |
|---|---|---|---|
| ABP documents | Systems Architect | Systems Architect | Project identity and standards |
| GBP documents | Codex as directed generator | Systems Architect | Complete ABP |
| Repository structure/manifest | Codex as directed generator | Systems Architect | ABP-02 and approved GBP |
| Engine specification | Architecture | Systems Architect | ABP and approved GBP |
| Framework Prompt | Architecture | Systems Architect | Approved Engine specification |
| Engine implementation | Implementation Engineer | Systems Architect | Specification and Framework Prompt |
| Engine tests | Implementation Engineer | Systems Architect | Engine contract and specification |
| Implementation Report | Implementation Engineer | Systems Architect | Completed implementation and tests |
| EDR | Architectural authority | Systems Architect | ABP-01 change process |
| User/developer documentation | Assigned producer | Systems Architect | Approved repository artifacts |
| Research artifacts | Assigned research contributor | Systems Architect | Project identity and demonstrated behavior |

# Engine Ownership Rule

Each of the twenty-four Engines owns exactly one primary responsibility, one public contract, one specification, one Framework Prompt, one implementation directory, one corresponding test suite, and one Implementation Report. Ownership does not permit an Engine to bypass another Engine's architectural responsibility.

# Escalation and Stop Rules

An artifact producer shall stop and report when:

- a required governing artifact is missing or unapproved;
- two documents assign conflicting responsibility;
- an implementation would require a concrete dependency;
- requested behavior is not documented;
- a repository change would violate the prescribed organization;
- a Version 1 requirement crosses an excluded boundary.

Only architectural authority may resolve such conditions. Resolution that changes approved architecture requires an EDR.

# Completion Criteria

A role has completed an assigned lifecycle activity only when its artifact exists in the authoritative location, conforms to its governing artifacts, is traceable, has been reviewed, and has received the approval required for the next stage.

---

End of Document.
