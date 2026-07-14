# Project Architecture

---

# Document Information

| Field | Value |
|-------|-------|
| Document ID | ABP-03 |
| Document Name | Project Architecture |
| Package | Architecture Blueprint Package (ABP) |
| Version | 1.0 |
| Status | Draft |
| Author | Systems Architect |
| Project | TaskGraph – Semantic Robotic Manipulation Platform |
| Depends On | ABP-00, ABP-01, ABP-02 |
| Used By | ABP-04, GBP, Repository Generation |

---

# Revision History

| Version | Description |
|----------|-------------|
| 1.0 | Initial System Architecture |

---

# Purpose

This document defines the complete architectural design of the TaskGraph platform.

It explains how every major subsystem collaborates to transform a human demonstration into an executable robotic task.

This document intentionally excludes implementation details.

It defines architecture only.

---

# Architectural Vision

TaskGraph is designed as a layered semantic reasoning platform.

Instead of directly converting camera observations into robotic movements, the platform progressively transforms observations into increasingly meaningful representations until a validated executable task is produced.

The architecture prioritizes understanding before execution.

---

# Architectural Principles

The architecture is governed by the following principles.

• Semantic Before Motion

The platform shall understand what a task means before deciding how it should be executed.

---

• Explainability

Every architectural layer shall expose information that can be inspected and validated by the user.

---

• Progressive Intelligence

Understanding shall increase gradually.

Each layer receives structured information from the previous layer and enriches it before passing it forward.

---

• Independent Engines

Each architectural capability belongs to one Engine.

No Engine owns multiple unrelated responsibilities.

---

• Interface-Based Communication

Architectural layers communicate only through public contracts.

Internal implementation remains isolated.

---

# System Overview

The complete platform transforms demonstrations through multiple reasoning stages.

```text
Human Demonstration
        │
        ▼
Camera Observation
        │
        ▼
Vision Understanding
        │
        ▼
Scene Understanding
        │
        ▼
Semantic Inventory
        │
        ▼
Knowledge Representation
        │
        ▼
Affordance Reasoning
        │
        ▼
Task Planning
        │
        ▼
TaskIR Generation
        │
        ▼
Execution
        │
        ▼
Simulation
        │
        ▼
Replay
        │
        ▼
User Feedback
```

Each stage produces information of higher semantic value than the previous stage.

---

# Layered Architecture

TaskGraph consists of seven architectural layers.

---

## Layer 1 — Observation Layer

Purpose

Acquire information from the physical environment.

Responsibilities

- Receive webcam frames.
- Monitor simulation status.
- Capture user interactions.

Output

Raw observations.

---

## Layer 2 — Perception Layer

Purpose

Convert observations into meaningful scene information.

Responsibilities

- Detect objects.
- Estimate object locations.
- Track scene consistency.

Output

Structured scene description.

---

## Layer 3 — Semantic Layer

Purpose

Transform detected objects into semantic entities.

Responsibilities

- Assign identities.
- Build semantic inventory.
- Identify object relationships.

Output

Semantic representation of the environment.

---

## Layer 4 — Knowledge Layer

Purpose

Interpret semantic information using stored knowledge.

Responsibilities

- Apply capability rules.
- Infer affordances.
- Resolve contextual meaning.

Output

Semantic understanding.

---

## Layer 5 — Planning Layer

Purpose

Generate executable plans.

Responsibilities

- Validate goals.
- Build execution strategy.
- Explain planning decisions.

Output

TaskIR.

---

## Layer 6 — Execution Layer

Purpose

Convert TaskIR into simulation commands.

Responsibilities

- Schedule execution.
- Monitor progress.
- Handle execution events.

Output

Simulation actions.

---

## Layer 7 — Feedback Layer

Purpose

Improve future execution through user interaction.

Responsibilities

- Collect feedback.
- Record corrections.
- Update reusable knowledge.

Output

Improved semantic knowledge.

---

# Data Flow Philosophy

Information flows in one primary direction.

```text
Observation

↓

Perception

↓

Semantics

↓

Knowledge

↓

Planning

↓

Execution

↓

Feedback
```

Each layer enriches information.

No layer removes semantic meaning.

---

# Validation Flow

Every important transition shall support validation.

Example

```text
Detected Objects

↓

Validate

↓

Semantic Inventory

↓

Validate

↓

Task Plan

↓

Validate

↓

Execution
```

The user remains informed throughout the workflow.

---

# Explainability Architecture

Every reasoning stage shall generate human-readable explanations.

Examples include:

- detected objects,
- inferred capabilities,
- selected task sequence,
- execution rationale.

Explainability is treated as a core architectural feature rather than an optional utility.

---

# Human Interaction Architecture

The user remains an active participant.

The platform shall allow users to:

- observe system understanding,
- validate interpretations,
- approve execution,
- provide corrections,
- improve future behavior.

The architecture supports collaborative rather than autonomous operation.

---

# Simulation Architecture

Simulation remains independent from the software platform.

The software generates validated execution plans.

The simulation executes those plans.

Communication occurs through a stable SDK.

Neither system directly depends on the other's internal implementation.

---

# User Interface Architecture

The user interface serves as the visual representation of the platform's reasoning.

The interface shall expose:

- live observation,
- detected scene,
- semantic inventory,
- planning output,
- TaskIR,
- execution progress,
- replay,
- feedback.

The interface is designed to answer a single question:

"What does the system currently understand?"

The interface is not intended to expose implementation details.

---

# Engine Collaboration

Every architectural layer is realized through one or more Engines.

Engines collaborate using defined contracts.

Engine interactions remain deterministic and traceable.

No Engine bypasses another architectural layer.

This preserves architectural consistency and explainability.

---

# Architectural Boundaries

The architecture intentionally excludes:

- hardware control,
- real robotic arm integration,
- cloud services,
- distributed processing,
- operating system dependencies,
- implementation-specific frameworks.

These concerns belong outside Version 1.

---

# Scalability

The architecture is designed for extension.

Future versions may introduce additional Engines without modifying the existing architectural layers.

Extensions shall integrate through public contracts.

The core architecture remains stable.

---

# Expected Outcome

The architecture enables the platform to:

- understand demonstrations,
- reason semantically,
- generate explainable plans,
- execute validated tasks,
- improve through feedback,

while preserving modularity, traceability, and maintainability.

---

# Architecture Summary

TaskGraph is organized as a progressive semantic reasoning pipeline.

Each architectural layer contributes additional understanding until the platform possesses sufficient semantic knowledge to safely generate executable robotic tasks.

Execution represents the final outcome of understanding rather than the primary objective.

---

# Freeze Statement

This document defines the official architectural structure of TaskGraph Version 1.

All subsequent specifications, repositories, and implementations shall conform to the architecture described herein.

Architectural modifications require an approved Engineering Decision Record.

End of Document.