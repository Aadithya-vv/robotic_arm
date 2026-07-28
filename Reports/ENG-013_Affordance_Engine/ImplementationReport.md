# ENG-013 Affordance Engine Implementation Report

| Status | Implemented — Awaiting Architecture Review |
|---|---|
| Contract | `taskgraph.affordance` 1.0.0 |
| Rule catalog | 1.0.0 |

ENG-013 implements immutable, checksummed, robot-independent Affordance Records through seven explicit exact-match rules. It consumes ENG-012 only through a Composition Root adapter/public contract, owns atomic `affordance_graph.json`, and provides read-only lookup/search/actions/statistics/export/integrity services. No ML, LLM, heuristic, intent, planning, motion, or upstream storage access exists.

Validation: 27/27 ENG-013 tests, 396 ENG-001–013 tests, and 5/5 launcher/session tests pass. Thirteen Engines report healthy; Affordance routes return 200; Python/TypeScript, ESLint (zero errors, one pre-existing warning), and Vite production build pass. Freeze is recommended after architecture review.

See [complete milestone report](../../TaskGraph_v1.2_Engine013_AffordanceEngine_Report.md).
