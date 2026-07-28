# TaskIR Compilation Pipeline

1. Confirm available lifecycle and valid Shared Contract request.
2. Normalize the Semantic Plan contract into a read-only plain projection.
3. Verify schema compatibility, validation evidence, identities, references, and source checksums.
4. Compile every node one-to-one without changing order or action meaning.
5. Compile edges, conditions, and constraints one-to-one.
6. Preserve goal, resources, timestamps, provenance, correlation, and planning-rule references.
7. Generate canonical node and document checksums.
8. Validate complete TaskIR integrity.
9. Atomically persist and rebuild the in-memory index.
10. Return immutable TaskIR, diagnostics, and validation evidence.

Any validation failure rejects compilation before storage. Any accepted processing or storage exception fails explicitly.
