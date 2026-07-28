# Engine 013 Framework Prompt

Implement only ENG-013. It alone owns Affordance Records, explicit rules, graph persistence, validation, indexes/cache, lookup/search, summaries, statistics, export, migration, and rebuild.

Follow ABP, GBP, Rule 40, authoritative specifications, and the versioned rule catalog. Consume Knowledge only through `KnowledgeSource`; never import ENG-012 or earlier/later concrete packages. Composition Root owns binding. Write only the injected Affordance storage; never touch Object Library, Semantic Inventory, or Knowledge files.

Rules must be exact, explicit, deterministic, versioned, reviewable, and tested. Never use ML, LLMs, similarity, heuristics, inferred intent, planning, motion, robot geometry, or unstated facts. Unknown objects receive no actions. Records remain frozen, serializable, correlated, checksummed, and provenance-preserving. Protect state with the Engine lock; fail explicitly. Every rule/API/lifecycle/storage change requires unit, migration, integrity, concurrency, performance, Rule 40, integration, and documentation updates. Do not modify ENG-001–012. Freeze authority remains with architecture review.
