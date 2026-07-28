# Explainability Test Plan

Tests cover immutable/serializable models, lifecycle, exact fact derivation, determinism, artifact/decision/dependency traces, version and schema rejection, checksum tampering, invalid-source rejection, serialization, atomic storage, imports/exports, statistics, search, rebuilding without source mutation, capacity/failures, concurrent convergence, composition startup/shutdown, REST readiness, TypeScript build, ESLint, and upstream regression/frozen-file audits.

Performance is linear in artifact and trace size plus canonical serialization. No unapproved quantitative SLA is asserted.
