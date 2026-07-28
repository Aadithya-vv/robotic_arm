# Semantic Inventory Test Plan

The isolated suite validates contract conformance, lifecycle, invalid transitions, complete data model, deterministic normalization, missing records, name/description/category/alias/tag queries, statistics, JSON export, legacy snapshot migration, atomic storage round-trip, source refresh, explicit malformed-record failure, concurrent reads, 1,000-object performance, legacy Object Library shapes, and Rule 40 imports.

Integration validation starts the real Composition Root, confirms eleven healthy registrations, exercises all four HTTP projections, compiles the backend and TypeScript frontend, and runs launcher/session regression tests. Full prior-engine suites are run with each Engine’s source directory on `PYTHONPATH`. Production data is never mutated by isolated tests.
