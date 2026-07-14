# Development Workflow

Research Idea → ABP → GBP → Repository Generation → Repository Review → Engineering Mode Transition → One Engine Implementation → Tests → Implementation Report → Review → Freeze → Next Engine

## Completion Gate

An Engine completes only after its Implementation Ready specification and prompt are followed, implementation is complete, tests pass, documentation and report are synchronized, architecture review completes, and the Engine is frozen.

## Stop Rules

Stop only when architecture or Rule 40 would be violated, work crosses an Engine boundary, repository inconsistency is detected, or a genuine architectural ambiguity appears. Unavailable future Engines use contracts, interfaces, providers, mocks, or stubs and are not by themselves blockers. Architectural changes require an approved EDR.