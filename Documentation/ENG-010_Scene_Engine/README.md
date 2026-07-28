# ENG-010 — Scene Engine

ENG-010 maintains the authoritative runtime scene model from independent Vision observations. It owns stable visual-object tracking, appearance/update/disappearance handling, geometric relationships, consistency validation, snapshots, diagnostics, and its own explanations.

## Public behavior

`SceneContract` supports initialization, update, snapshot, reset, diagnostics, close, and lifecycle inspection. Calls return versioned, correlated `SceneResponse` outcomes with explicit succeeded, rejected, or failed status.

`SceneSnapshot` is immutable and contains scene/frame identity, timestamp context, tracked visual objects, geometric relationships, diagnostics, statistics, and an ENG-010 Explanation Record.

## Tracking architecture

`VisionObservation -> Association -> SceneObject Tracking -> Relationship Builder -> Scene Validator -> SceneSnapshot`

`SceneTracker` is the replaceable association boundary. `DefaultSceneTracker` deterministically associates candidates using intersection-over-union with stable tie-breaking. `MockSceneTracker` provides controlled deterministic behavior. `SceneTrackerCatalog` validates providers and rejects duplicate identifiers.

Objects retain stable Scene Object IDs across associated frames. Missing objects are retained for the configured update tolerance and then removed. Motion is derived geometrically from center displacement.

## Relationships

`GeometricRelationshipBuilder` derives only `left_of`, `right_of`, `above`, `below`, `near`, `overlap`, and `contained`. Relationships contain stable object references and no semantic meaning. `SceneValidator` verifies identities, bounds, confidence values, and relationship referential consistency.

## Configuration and lifecycle

Configuration selects the tracker and controls association IoU threshold, missing-update tolerance, near distance, and motion threshold. The lifecycle is `Empty -> Initializing -> Active`; updates transition through `Updating` and return to `Active`. Owned/dependency failure enters `Degraded`. Close releases resources and enters `Closed`; reset clears the current model while remaining active.

## Diagnostics and observability

Diagnostics expose tracked count, objects added/removed/updated during the last update, relationship count, tracking health, processing duration, total updates, last error, and tracker details. Structured logging uses only the injected `LogSink`; observation payloads are not logged.

## Thread safety and determinism

A reentrant lock serializes lifecycle and world-model mutation. Association ordering, identity allocation, relationship ordering, and snapshots are deterministic for controlled observations and configuration.

## Boundaries and limitations

Scene Objects contain only visual/runtime information. ENG-010 performs no detection, naming, semantic identity, affordance inference, persistent Knowledge, planning, robot control, TaskIR processing, or simulation behavior. The default tracker is a replaceable deterministic IoU tracker and does not predict through long occlusions. No quantitative performance SLA is architecturally approved.

## Locations

- Source: `Implementation/ENG-010_Scene_Engine/Source/taskgraph_scene/`
- Tests: `Tests/ENG-010_Scene_Engine/`
- Specification: `Specifications/ENG-010_Scene_Engine/Specification.md`
- Reports: `Reports/ENG-010_Scene_Engine/`
