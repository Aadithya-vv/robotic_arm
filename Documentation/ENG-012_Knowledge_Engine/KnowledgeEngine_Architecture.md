# Knowledge Engine Architecture

ENG-012 is the sole owner of structured reusable knowledge. Its upstream boundary is the frozen ENG-011 public contract, adapted in the Composition Root to `SemanticInventorySource`. Its downstream public contract is read-only for v1.2. Storage and logging are injected protocols; configuration is immutable.

The Engine maintains an immutable graph plus owned Knowledge-ID/Object-ID caches under one lock. Deterministic rebuild makes its JSON database disposable and recoverable. No Object Library or Semantic Inventory file is accessed by ENG-012 code.
