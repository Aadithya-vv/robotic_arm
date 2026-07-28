# TaskGraph v1.2 — ENG-016 Explainability Report

## Architecture and dependency verification

Frozen contracts, ABP/GBP/Rule 40, ENG-011/012/013/015/014 specifications, prompts, reports, public contracts, storage, composition, launcher, and session lifecycle were reviewed. ENG-016 observes the semantic pipeline through injected public adapters and never mutates it. Rule and explanation facts are mapped directly from validated artifacts.

## Implementation and files

Added `taskgraph_explainability` immutable contracts, deterministic engine, atomic storage, focused tests, specification/framework prompt, seven documents, and this report. Added `Assets/Explainability/explanations.json` and a narrow composition adapter. Extended composition registration/lifecycle/validation, Web API, and the read-only Explainability Viewer without changing upstream ownership.

## Public and Web APIs

Public operations cover generation, retrieval/search, artifact/decision/dependency traces, validation, import/export, statistics, and rebuilding. Required `/explain` endpoints expose these read-only projections. The viewer shows explanation trees, artifact chains, validation/compilation state, checksums, rules, and versions; it has no editing behavior.

## Tests, validation, and performance

Six focused test groups covering model immutability, deterministic generation, trace integrity, versions, checksums, serialization, import/export, validation, statistics, source immutability, threading, and persistence passed through a dependency-light harness because pytest is not installed. Python compilation, launcher/session compilation, the live 16-Engine composition lifecycle, TypeScript production build, and frozen-file audit passed. ESLint completed with no errors and one existing Fast Refresh warning. Generation is linear in artifact/trace size and bounded by configuration.

## Limitations and freeze recommendation

ENG-016 formats declared facts only; it does not generate narrative rationale or fill missing provenance. Schema-major migration is fail-closed. Recommend freeze only after validation gates pass and architecture review confirms the read-only boundary.
