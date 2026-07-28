# TaskIR Compiler Architecture

ENG-014 is a pure compiler positioned strictly after ENG-015. Its public engine coordinates immutable contracts, a canonical serializer/checksum function, validation, an in-memory identity/index projection, and an injected atomic storage provider. The composition root constructs the provider and engine; no global is used.

The compiler consumes only the Semantic Plan contract shape. It deliberately performs no calls to Knowledge or Affordance engines, so compilation cannot reinterpret a plan. Content-derived TaskIR identity, preserved source timestamps, canonical JSON key ordering, immutable tuples/mappings, and SHA-256 checksums make repeated compilation verifiable and deterministic.

Rule 40 is maintained: ENG-014 imports no concrete upstream engine. Web API and Viewer are presentation adapters over its public contract and contain no compiler logic.
