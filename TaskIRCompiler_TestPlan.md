# TaskIR Compiler Test Plan

Tests cover immutable contracts, lifecycle, exact action/order preservation, repeated compilation equality, content checksum determinism, validated-plan enforcement, unsupported schema rejection, source/output tamper detection, missing references, atomic JSON persistence, serialization round trips, import/export, search/indexing, statistics, rebuilding, capacity, malformed/corrupt storage, API composition readiness, and concurrent compilation.

Regression validation includes ENG-011/012/013/015 tests, composition-root validation, Python compilation, frontend TypeScript build, and ESLint. Performance is checked for bounded document/node traversal and concurrent convergence; no unapproved quantitative SLA is asserted.
