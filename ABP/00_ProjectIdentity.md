# Project Identity

---

# Document Information

| Field | Value |
|-------|-------|
| Document ID | ABP-00 |
| Document Name | Project Identity |
| Package | Architecture Blueprint Package (ABP) |
| Version | 1.0 |
| Status | Draft |
| Author | Systems Architect |
| Project | TaskGraph – Semantic Robotic Manipulation Platform |
| Depends On | None |
| Used By | All ABP Documents |

---

# Revision History

| Version | Description |
|----------|-------------|
| 1.0 | Initial Architecture Definition |

---

# Purpose

This document defines the identity of the project.

It answers the fundamental questions:

- What are we building?
- Why are we building it?
- Who is it for?
- What problems does it solve?
- What is considered success?
- What is intentionally outside the scope?

Every architectural decision made in later documents shall align with the identity defined here.

---

# Project Statement

TaskGraph is a semantic robotic manipulation platform that learns task intent from human demonstrations, transforms those observations into reusable semantic understanding, generates explainable task plans, and executes validated actions within a robotic arm simulation.

The system is designed to bridge the gap between human demonstrations and autonomous robotic task execution through semantic reasoning rather than direct motion programming.

---

# Vision

The long-term vision of TaskGraph is to make robotic task programming intuitive, explainable, and reusable.

Instead of manually programming every robotic action, users should be able to demonstrate a task naturally while the system understands:

- what objects exist,
- what actions are being performed,
- why those actions are performed,
- and how those actions can be reused in future situations.

TaskGraph aims to convert demonstrations into semantic knowledge that can be generalized beyond a single execution.

---

# Problem Statement

Traditional robotic programming often requires explicit motion scripting, predefined sequences, or environment-specific programming.

Such approaches present several limitations:

- Programming robots requires technical expertise.
- Demonstrations are often converted only into motion trajectories rather than task understanding.
- Robot behaviors become difficult to explain.
- Task reuse across different environments is limited.
- Users cannot easily verify what the robot has actually understood.

The absence of semantic understanding creates a disconnect between human intention and robotic execution.

TaskGraph addresses this gap by focusing on task understanding before task execution.

---

# Research Motivation

Human demonstrations contain significantly more information than simple movement.

A demonstration implicitly contains:

- object identities,
- object relationships,
- intentions,
- action sequences,
- dependencies,
- goals,
- constraints.

Rather than copying trajectories, TaskGraph attempts to understand these semantic relationships and transform them into reusable knowledge.

This semantic understanding forms the primary research contribution of the project.

---

# Primary Objective

Design and develop a software platform capable of:

1. Observing a human demonstration.
2. Understanding the demonstrated task.
3. Building a semantic representation of the environment.
4. Inferring object affordances.
5. Generating explainable task plans.
6. Converting plans into TaskIR.
7. Executing TaskIR inside a robotic arm simulation.
8. Learning from user feedback to improve future task execution.

---

# Success Criteria

The project shall be considered successful when the system can demonstrate the following workflow:

Human Demonstration

↓

Environment Observation

↓

Semantic Scene Understanding

↓

Affordance Identification

↓

Task Planning

↓

TaskIR Generation

↓

Simulation Execution

↓

Replay

↓

User Feedback

↓

Knowledge Improvement

Each stage shall be observable and explainable through the user interface.

---

# Scope

## Included

The project includes:

- Semantic scene understanding.
- Object recognition.
- Semantic inventory generation.
- Knowledge representation.
- Affordance reasoning.
- Explainable task planning.
- TaskIR generation.
- Robotic arm simulation.
- User interaction interface.
- Replay and explainability.
- User feedback integration.
- Execution through simulation.

The project focuses primarily on software architecture and semantic reasoning.

---

## Excluded

The following are explicitly outside Version 1:

- Physical robotic arm implementation.
- ROS dependency.
- Cloud computing.
- Distributed processing.
- Multi-robot coordination.
- Voice interaction.
- Mobile applications.
- Autonomous navigation.
- Industrial deployment.
- Real-time industrial control systems.

Future versions may expand these areas.

---

# Target Users

Primary users:

- Robotics researchers.
- Engineering students.
- Academic institutions.
- AI researchers.
- Human-robot interaction researchers.

Secondary users:

- Developers interested in semantic robotic programming.
- Demonstration-based robotic learning researchers.

---

# Demonstration Scenario

A user wishes to teach a robot how to pour water from a bottle into a cup.

The interaction follows these steps:

1. The user performs the demonstration in front of the webcam.
2. The system observes the environment.
3. Objects are detected.
4. The scene is reconstructed semantically.
5. Object capabilities are inferred.
6. The demonstrated intent is identified.
7. A semantic task plan is generated.
8. The plan is displayed for user validation.
9. TaskIR is generated.
10. The robotic arm simulation executes the task.
11. The user reviews execution.
12. Feedback is recorded for future improvement.

This scenario represents the reference workflow for Version 1.

---

# Core Philosophy

TaskGraph follows five core philosophies.

## 1. Understand Before Acting

The system shall understand the task before generating execution.

---

## 2. Explain Every Decision

Every important decision shall be visible to the user.

Nothing should appear as unexplained automation.

---

## 3. Semantic First

Objects are represented by meaning rather than appearance alone.

Understanding object capabilities is more important than object labels.

---

## 4. Human-Centered Teaching

The user teaches the robot naturally through demonstrations rather than traditional programming.

---

## 5. Progressive Intelligence

Understanding develops in stages:

Observation

↓

Objects

↓

Semantic Objects

↓

Capabilities

↓

Intent

↓

Task Plan

↓

TaskIR

↓

Execution

Every stage shall be independently inspectable.

---

# Research Contribution

The primary contribution of TaskGraph is not object detection or robotic control.

The novelty lies in transforming demonstrations into reusable semantic task understanding through:

- Semantic Inventory.
- Capability-based reasoning.
- Affordance inference.
- Explainable planning.
- TaskIR generation.

This contribution differentiates the project from systems focused solely on motion imitation.

---

# System Principles

The platform shall satisfy the following principles:

- Local-first execution.
- Explainable intelligence.
- Modular engine architecture.
- Independent engine development.
- Stable architecture.
- Specification-driven engineering.
- Human-readable reasoning.
- User validation before execution.

---

# Constraints

The project shall operate under the following constraints:

- Python-based software platform.
- Local execution.
- Webcam-based observation.
- Separate simulation machine connected over Wi-Fi.
- Simulation executed in PyBullet.
- No dependence on cloud infrastructure.
- No dependence on ROS.
- Version 1 limited to simulation.

---

# Expected Deliverables

The completed project shall provide:

- Complete software platform.
- Semantic reasoning engine.
- Explainable planner.
- TaskIR compiler.
- Robotic arm simulation integration.
- Interactive user interface.
- Replay capability.
- User feedback mechanism.
- Technical documentation.
- Research paper.

---

# Project Milestones

Milestone 1

Core platform operational.

Milestone 2

Semantic understanding operational.

Milestone 3

Planning operational.

Milestone 4

Simulation execution operational.

Milestone 5

Complete end-to-end demonstration.

Milestone 6

Research paper submission.

---

# Version Definition

Version 1.0 focuses exclusively on validating the proposed semantic robotic manipulation framework within simulation.

The objective is to demonstrate the feasibility, explainability, and modularity of the proposed architecture.

Future versions may extend the framework toward real robotic hardware and additional application domains.

---

# Project Identity Summary

TaskGraph is a software platform that enables robots to understand demonstrations semantically rather than merely reproducing observed motion.

The project prioritizes explainability, semantic reasoning, modular architecture, and user-guided robotic learning.

Every subsequent architectural, engineering, and implementation decision shall preserve this identity.

---

# Freeze Statement

This document defines the identity of the TaskGraph project.

It serves as the highest-level architectural reference for all subsequent Architecture Blueprint Package documents.

Any modification to this document requires an approved Engineering Decision Record (EDR).

End of Document.