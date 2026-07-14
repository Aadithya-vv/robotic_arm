# TaskIR Architectural Contract

## Document Control

| Field | Value |
|---|---|
| Package | Repository-level Contracts |
| Version | 1.0 |
| Status | Approved and Frozen — Engineering Mode |
| Producer | ENG-014 — TaskIR Compiler Engine |
| Primary Consumer | ENG-017 — Execution Engine |
| Classification | Architectural representation; no implementation syntax |

## Purpose

TaskIR is the validated, simulator-independent execution representation produced by ENG-014 from a validated Semantic Plan. It preserves semantic intent and supplies the ordered, constrained task description required by execution. It does not perform planning, execution, simulation transport, or motion-control algorithms.

## Ownership Boundary

- ENG-015 interprets task intent and produces a validated Semantic Plan.
- ENG-014 consumes the Semantic Plan, compiles it into TaskIR, and validates the TaskIR representation.
- ENG-020 approves a specific TaskIR identity/version and issues an Approval Token.
- ENG-017 accepts TaskIR only with a valid matching Approval Token and coordinates execution.
- ENG-018 transports approved execution data to the independent simulation boundary.

Engine identifiers remain unchanged. TaskIR compilation never changes the intent or invents missing planning decisions.

## Representation

TaskIR is a versioned semantic document. The architecture does not prescribe JSON, YAML, classes, database form, binary encoding, or any programming-language syntax. Any implementation representation must preserve all required semantic elements and contract invariants.

## Required Semantic Elements

TaskIR contains:

- **TaskIR identity and contract version;**
- **correlation and provenance:** references to the originating workflow and Semantic Plan identity/version;
- **goal:** the validated semantic outcome being executed;
- **entity references:** semantic objects, roles, and relationships required by the task;
- **ordered actions:** semantic actions with explicit order or dependency constraints;
- **action participants and parameters:** semantic actors, objects, targets, and approved values;
- **preconditions:** conditions required before the task and before individual actions;
- **postconditions:** expected semantic conditions after actions and task completion;
- **constraints:** ordering, safety, contextual, and validation constraints carried from the Semantic Plan;
- **failure semantics:** named failure/abort conditions and expected safe termination meaning;
- **explanation/provenance references:** links to the planning and compilation explanation records;
- **validation status:** evidence that structural and semantic TaskIR validation succeeded.

TaskIR does not contain an Approval Token. Approval is a separate contract bound to the completed TaskIR identity and version.

## Validation Principles

ENG-014 shall reject TaskIR unless:

- the source Semantic Plan is valid and version-compatible;
- every required element is present and internally consistent;
- every entity and action reference resolves within the TaskIR context;
- action ordering/dependencies are complete and non-contradictory;
- required preconditions, postconditions, and constraints are represented;
- no planning decision is missing or fabricated during compilation;
- the output preserves goal and semantic intent;
- provenance, correlation, version, and explanation references are traceable;
- unsupported or ambiguous constructs are rejected explicitly.

Successful structural validation does not imply user approval, executability in a particular simulator, or successful execution.

## Versioning

TaskIR follows SharedContracts semantic versioning. A major version changes required meaning or compatibility; a minor version adds backward-compatible optional capability; a patch clarifies without changing compatibility. ENG-014 declares the produced version. ENG-017 and ENG-018 reject unsupported major versions explicitly. TaskIR shall not be silently transformed across incompatible versions.

## Immutability and Approval Binding

After validation, a TaskIR artifact used for approval is immutable. Any semantic or structural change creates a new TaskIR identity or version as approved by the contract and invalidates approval tokens bound to the previous artifact. Execution verifies the token-to-TaskIR binding before scheduling work.

## Status and Errors

Compilation and validation use SharedContracts status and error conventions. Invalid Semantic Plan input is Rejected. A failure after accepted compilation is Failed. Only a fully validated TaskIR is Succeeded and eligible for user approval.

## Extension Principles

Extensions shall preserve semantic-first design, simulator independence, explainability, traceability, and backward compatibility. Simulator commands, physical hardware controls, ROS messages, motion-planning algorithms, and transport-specific syntax are outside this architectural contract.

