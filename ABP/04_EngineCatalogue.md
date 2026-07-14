# Engine Catalogue

---

# Document Information

| Field | Value |
|-------|-------|
| Document ID | ABP-04 |
| Document Name | Engine Catalogue |
| Package | Architecture Blueprint Package (ABP) |
| Version | 1.0 |
| Status | Draft |
| Author | Systems Architect |
| Project | TaskGraph – Semantic Robotic Manipulation Platform |
| Depends On | ABP-00, ABP-01, ABP-02, ABP-03 |
| Used By | GBP, Repository Generation, Engine Specifications |

---

# Revision History

| Version | Description |
|----------|-------------|
| 1.0 | Initial Engine Catalogue |

---

# Purpose

This document defines every Engine that exists within TaskGraph Version 1.

The Engine Catalogue serves as the architectural inventory of the platform.

Every functional capability of the system shall belong to exactly one Engine.

No Engine may exist outside this catalogue.

Future Engines require an approved Engineering Decision Record (EDR).

---

# Engine Philosophy

An Engine is the smallest independently developable architectural unit within TaskGraph.

Every Engine shall:

- Own one primary responsibility.
- Expose one public contract.
- Be independently testable.
- Be independently replaceable.
- Be independently documented.
- Be implemented only after its specification is approved.

The Engine is the fundamental unit of implementation throughout the project.

---

# Engine Classification

The platform organizes Engines into six architectural domains.

```text
Core Platform

↓

Perception

↓

Semantic Intelligence

↓

Planning & Execution

↓

User Interaction

↓

Infrastructure
```

Each domain groups Engines with related responsibilities.

---

# Core Platform Domain

---

## ENG-001 — Bootstrap Engine

### Purpose

Initialize the TaskGraph platform.

### Responsibilities

- Start the platform.
- Verify startup conditions.
- Load runtime environment.
- Initialize system lifecycle.

### Input

Application startup.

### Output

Initialized runtime.

### Priority

Critical.

---

## ENG-002 — Kernel Engine

### Purpose

Coordinate the overall runtime.

### Responsibilities

- Manage Engine lifecycle.
- Coordinate execution.
- Maintain runtime state.

### Input

Platform services.

### Output

Runtime coordination.

### Priority

Critical.

---

## ENG-003 — Configuration Engine

### Purpose

Manage system configuration.

### Responsibilities

- Load configuration.
- Validate configuration.
- Provide runtime settings.

### Input

Configuration files.

### Output

Configuration services.

### Priority

High.

---

## ENG-004 — Registry Engine

### Purpose

Maintain Engine registration.

### Responsibilities

- Register Engines.
- Discover Engines.
- Resolve dependencies.

### Input

Engine metadata.

### Output

Runtime registry.

### Priority

High.

---

## ENG-005 — Event Bus Engine

### Purpose

Coordinate platform events.

### Responsibilities

- Publish events.
- Deliver events.
- Route notifications.

### Input

Platform events.

### Output

Event distribution.

### Priority

High.

---

## ENG-006 — Memory Engine

### Purpose

Manage runtime memory ownership.

### Responsibilities

- Store temporary state.
- Manage shared context.
- Handle lifecycle cleanup.

### Input

Runtime data.

### Output

Managed memory.

### Priority

High.

---

## ENG-007 — Logging Engine

### Purpose

Provide centralized logging.

### Responsibilities

- Record events.
- Record errors.
- Record diagnostics.

### Priority

Medium.

---

# Perception Domain

---

## ENG-008 — Camera Engine

Purpose

Acquire observations from the webcam.

Responsibilities

- Capture frames.
- Manage camera lifecycle.
- Provide observations.

---

## ENG-009 — Vision Engine

Purpose

Detect objects and estimate their properties.

Responsibilities

- Object detection.
- Object localization.
- Confidence estimation.

---

## ENG-010 — Scene Engine

Purpose

Construct a consistent representation of the environment.

Responsibilities

- Track objects.
- Maintain scene consistency.
- Handle object updates.

---

## ENG-011 — Semantic Inventory Engine

Purpose

Transform scene information into semantic entities.

Responsibilities

- Build semantic inventory.
- Maintain object identities.
- Represent relationships.

---

# Semantic Intelligence Domain

---

## ENG-012 — Knowledge Engine

Purpose

Represent reusable semantic knowledge.

Responsibilities

- Store concepts.
- Maintain relationships.
- Provide reasoning context.

---

## ENG-013 — Affordance Engine

Purpose

Infer capabilities of objects.

Responsibilities

- Determine possible actions.
- Apply contextual reasoning.
- Produce capability descriptions.

---

## ENG-014 — TaskIR Compiler Engine

Purpose

Transform validated plans into TaskIR.

Responsibilities

- Generate TaskIR.
- Validate representation.
- Produce executable task description.

---

## ENG-015 — Planner Engine

Purpose

Generate semantic task plans.

Responsibilities

- Interpret goals.
- Build execution plans.
- Explain planning decisions.

---

## ENG-016 — Explainability Engine

Purpose

Expose reasoning to the user.

Responsibilities

- Explain decisions.
- Display reasoning chain.
- Produce human-readable descriptions.

---

# Planning & Execution Domain

---

## ENG-017 — Execution Engine

Purpose

Execute validated TaskIR.

Responsibilities

- Schedule execution.
- Coordinate execution lifecycle.
- Monitor execution progress.

---

## ENG-018 — Simulation Connector Engine

Purpose

Communicate with the robotic arm simulation.

Responsibilities

- Connect to simulation.
- Exchange execution data.
- Maintain communication state.

---

## ENG-019 — Replay Engine

Purpose

Replay completed executions.

Responsibilities

- Record execution history.
- Replay execution.
- Support demonstration review.

---

# User Interaction Domain

---

## ENG-020 — Dashboard Engine

Purpose

Provide the primary user interface.

Responsibilities

- Display platform state.
- Display reasoning.
- Display execution.

---

## ENG-021 — Demonstration Engine

Purpose

Manage human demonstrations.

Responsibilities

- Coordinate demonstrations.
- Validate demonstration workflow.
- Deliver demonstration data.

---

## ENG-022 — Feedback Engine

Purpose

Capture user feedback.

Responsibilities

- Record corrections.
- Record validation.
- Improve semantic knowledge.

---

# Infrastructure Domain

---

## ENG-023 — Report Engine

Purpose

Generate engineering and execution reports.

Responsibilities

- Produce implementation reports.
- Produce execution summaries.
- Produce analysis reports.

---

## ENG-024 — Export Engine

Purpose

Export project artifacts.

Responsibilities

- Export reports.
- Export TaskIR.
- Export project data.

---

# Engine Interaction Principles

All Engine communication shall satisfy:

- Interface-based interaction.
- Independent ownership.
- No concrete dependencies.
- Deterministic communication.
- Traceable execution.

No Engine shall bypass another Engine's architectural responsibility.

---

# Engine Development Order

The implementation order follows architectural dependency.

```text
Core Platform

↓

Perception

↓

Semantic Intelligence

↓

Planning

↓

Execution

↓

User Interaction

↓

Infrastructure
```

This order shall be used when generating the implementation roadmap.

---

# Definition of an Engine

An Engine is considered architecturally complete when:

- Its purpose is defined.
- Its responsibilities are defined.
- Its public contract is specified.
- Its dependencies are identified.
- Its specification is approved.
- Its implementation is completed.
- Its implementation report is approved.

---

# Expected Outcome

The Engine Catalogue defines the complete functional decomposition of TaskGraph Version 1.

Every implementation artifact, engineering specification, repository folder, framework prompt, and implementation report shall trace back to one Engine defined within this catalogue.

No additional Engine may be introduced without architectural approval.

---

# Engine Catalogue Summary

TaskGraph Version 1 consists of twenty-four independent Engines organized into six architectural domains.

This catalogue defines the permanent architectural inventory of the platform and serves as the foundation for all subsequent engineering specifications and implementation activities.

---

# Freeze Statement

This Engine Catalogue defines the official Engine inventory of TaskGraph Version 1.

Changes require an approved Engineering Decision Record (EDR).

End of Document.