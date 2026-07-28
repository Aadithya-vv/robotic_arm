# Explainability API

| Operation | Result |
|---|---|
| GenerateExplanation | One deterministic record from one validated artifact |
| GetExplanation / Search | Identity retrieval and deterministic search |
| TraceArtifact | Records containing an artifact in their chain |
| TraceDecision | Declared rule/actions/facts |
| TraceDependency | Ordered artifact chain and explanation nodes |
| Validate | Schema/source/integrity result |
| Import / Export | Validated canonical serialization |
| GetStatistics | Counts by validity, type, and source Engine |
| Rebuild | Read public projections and replace the owned explanation index |

REST endpoints are `GET /explain`, `GET /explain/{id}`, `GET /explain/statistics`, `GET /explain/trace`, `GET /explain/dependencies`, `POST /explain/validate`, `POST /explain/import`, and `GET /explain/export`.
