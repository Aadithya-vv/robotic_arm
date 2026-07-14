# Getting Started

## Current State

Repository Generation is complete. No implementation or tests exist.

## Engineering Sequence

1. Read ABP/ and GBP/ in document order.
2. Review RepositoryManifest.md and DependencyMap.md.
3. Read the target Engine specification and Framework Prompt completely.
4. Inspect repository consistency and relevant dependency contracts.
5. Engineer only the target Engine; use contracts/providers/mocks/stubs for unavailable future Engines.

## Implementation Entry Point

Issue Implement Next Engine for one Engine. Codex must implement only that Engine, create its tests and documentation, update its report, then stop for review.