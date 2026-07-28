# ENG-014 TaskIR Compiler Engine Specification

## Purpose and responsibilities

ENG-014 deterministically compiles a validated ENG-015 Semantic Plan into canonical, immutable TaskIR. It owns the TaskIR schema, serialization, validation, compilation, storage, import/export, version checks, integrity checksums, statistics, indexing, migration validation, diagnostics, and rebuilding. It never plans, infers, optimizes, reorders, adds, deletes, or edits semantic actions.

## Inputs and outputs

Input is one validated, checksum-correct Semantic Plan compatible with schema major version 1. Output is a validated TaskIR or an explicit Shared Contracts rejection/failure response. TaskIR preserves the plan identity, correlation, goal, resources, node identity/order, edges, conditions, constraints, timestamps, provenance, rule references, and explanation references.

## Compilation pipeline

```text
Validated Semantic Plan -> structural/integrity validation -> node compilation
 -> edge/condition/constraint compilation -> metadata -> checksums -> TaskIR validation
 -> atomic storage -> export projection
```

Every stage is deterministic. Compilation reads but never mutates its source. No external lookup participates in compilation.

## Protocols and dependencies

The public contract provides `Compile`, `Validate`, `GetTaskIR`, `SearchTaskIR`, `ExportTaskIR`, `ImportTaskIR`, `GetStatistics`, and `Rebuild`, with Pythonic aliases. Dependencies are injected `TaskIRStorage`, logging, and configuration contracts. ENG-015 is an upstream provider only; ENG-014 never imports its concrete implementation. ENG-011/012/013, execution, simulation, robot SDKs, motion planning, UI, and transport are non-dependencies.

## Thread safety

Owned documents and indexes are protected by a re-entrant lock. Storage mutations are atomic. Concurrent identical compilations converge on one content-addressed TaskIR identity and checksum.

## Validation and failure modes

Validation covers request identity/correlation, source validation evidence, supported major version, required fields, unique node IDs, resolved edge endpoints, source and output checksums, provenance, and storage integrity. Invalid input is Rejected; accepted processing/storage failure is Failed; only validated output is Succeeded. Unsupported versions, tampering, capacity, missing documents, invalid lifecycle, malformed import, and corrupt storage fail explicitly.

## Storage and versioning

`Assets/TaskIR/task_ir.json` is authoritative only for compiled TaskIR. Writes use a same-directory temporary file plus atomic replacement. Incompatible major versions are rejected without silent migration. Compatible future migrations may be registered at the serialization boundary.

## Architecture

```text
ENG-015 -- validated Semantic Plan --> [ENG-014 pure compiler]
                                           |-- immutable TaskIR contracts
                                           |-- validator/checksums/index
                                           `-- TaskIRStorage provider
                                                    |
                                             Assets/TaskIR/task_ir.json
```

## Future extensions

Backward-compatible optional schema fields, explicit migration providers, alternate storage providers, streaming export, and downstream execution consumers may be added without introducing planning or simulator-specific meaning.
