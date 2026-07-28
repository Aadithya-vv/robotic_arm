# ENG-016 Explainability Engine Specification

## Purpose and responsibilities

ENG-016 deterministically aggregates, links, formats, stores, validates, and exposes explanation facts derived exclusively from validated semantic artifacts. It owns Explanation Records, Decision Traces, Dependency Traces, provenance, rule/validation/compilation summaries, search, statistics, import/export, integrity, and rebuilding. It never performs AI, inference, planning, compilation, execution, simulation, control, or upstream mutation.

## Inputs and outputs

Inputs are public, read-only projections from ENG-011 Semantic Inventory, ENG-012 Knowledge, ENG-013 Affordance, ENG-015 Semantic Plans, and ENG-014 TaskIR, including validation, compilation, checksum, and version facts. Output is an immutable validated Explanation Record or explicit Shared-Contract failure.

## Architecture and protocols

```text
ENG-011/012/013/015/014 public projections
                 -> injected ArtifactSource
                 -> [ENG-016 deterministic formatter/linker/validator]
                 -> injected ExplanationStorage -> Assets/Explainability/explanations.json
                 -> REST/read-only viewer
```

Public operations are GenerateExplanation, GetExplanation, Search, Export, Import, Validate, GetStatistics, Rebuild, TraceArtifact, TraceDecision, and TraceDependency. Dependencies are injected ArtifactSource, ExplanationStorage, configuration, and logging contracts. No concrete upstream implementation is imported by ENG-016.

## Storage, validation, and thread safety

Storage contains Explanation Records only and uses same-directory atomic replacement. Validation covers identity, supported schema major, source validation state, references, and canonical SHA-256 integrity. Invalid inputs/imports are Rejected; accepted processing/storage failures are Failed. A re-entrant lock protects owned records, rebuilding, imports, generation, indexes, and persistence.

## Failure modes and future extensions

Unsupported versions, missing identities, invalid sources, checksum tampering, corrupt storage, unavailable providers, capacity, missing traces, and invalid lifecycle states fail explicitly. Future compatible extensions may add optional trace views, source adapters, storage providers, and presentation formats without generating or changing source reasoning.
