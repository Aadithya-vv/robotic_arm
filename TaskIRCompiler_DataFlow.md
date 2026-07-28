# TaskIR Compiler Data Flow

```text
ENG-015 validated plan
  -> request/major-version/validation-evidence checks
  -> source node and plan checksum checks
  -> one-to-one node, edge, condition, constraint projection
  -> provenance and compilation metadata
  -> canonical node checksums
  -> canonical document checksum
  -> full TaskIR integrity validation
  -> atomic TaskIR storage
  -> API/export/read-only viewer
```

Source order is retained exactly. Inputs, outputs, preconditions, postconditions, constraints, resources, goal, correlation, timestamps, rule references, and provenance remain traceable. A failure before storage produces no TaskIR mutation.
