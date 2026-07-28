# TaskIR Compiler API

The immutable `TaskIRRequest` carries request identity, correlation, source identity, contract/version, and metadata. Every operation returns `TaskIRResponse` with Shared Contracts status and structured errors.

| Operation | Meaning |
|---|---|
| `Compile(request, semantic_plan)` | Validate and compile one plan, then atomically store it |
| `Validate(request, task_ir_or_id)` | Verify schema, references, provenance, and checksums |
| `GetTaskIR(request, id)` | Retrieve one document |
| `SearchTaskIR(request, query)` | Search canonical document projections |
| `ExportTaskIR(request, id=None)` | Export one or all documents |
| `ImportTaskIR(request, payload)` | Validate before atomic persistence |
| `GetStatistics(request)` | Return document/node/edge/action counts |
| `Rebuild(request)` | Revalidate storage and indexes; remove invalid documents |

REST adapters expose `GET /taskir`, `GET /taskir/{id}`, `GET /taskir/statistics`, `POST /taskir/compile`, `POST /taskir/validate`, `POST /taskir/import`, and `GET /taskir/export`. Compile accepts `plan_id` or an embedded validated `semantic_plan`. No endpoint edits TaskIR.
