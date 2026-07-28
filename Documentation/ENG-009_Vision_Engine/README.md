# ENG-009 — Vision Engine

ENG-009 consumes an observation conforming to ENG-008's public Camera observation contract and produces an immutable, non-semantic `VisionObservation`. It owns preprocessing, feature extraction, visual candidate detection/localization, confidence estimation, diagnostics, and its own Explanation Records.

## Public behavior

`VisionContract` supports initialization, observation processing, diagnostics, shutdown, and lifecycle inspection. Every call returns a versioned, correlated `VisionResponse` with explicit succeeded, rejected, or failed status. Output contains frame identity, correlation and timestamp context, candidates, bounding regions, confidence, numerical descriptors, duration, image metadata, diagnostics, and an explanation.

## Replaceable pipeline

`Camera frame -> Preprocessor -> Feature Extractor -> Detector -> Vision Observation`

- `BytePreprocessor` validates dimensions and optionally normalizes intensity.
- `StatisticalFeatureExtractor` produces numerical intensity and shape descriptors.
- `ContrastDetector` produces bounded visual candidates without semantic labels.
- `VisionPipeline` composes independently replaceable stage protocols.

Processing is isolated behind `VisionProcessor`. `MockVisionProcessor` is deterministic, `DefaultVisionProcessor` is dependency-free, and `OpenCVVisionProcessor` is optional and lazy-loaded. The default catalog requires no OpenCV installation.

## Configuration and lifecycle

`VisionConfiguration` selects the processor and controls confidence threshold, candidate limit, normalization, and immutable provider settings. The lifecycle is `Created -> Ready -> Validating -> Processing -> Ready`; failure enters `Failed`. Shutdown from `Ready` or `Failed` releases resources and enters `Shutdown`.

## Errors, diagnostics, and logging

Structured errors distinguish validation, version, state, dependency, processing, and invariant failures. Diagnostics expose state, processor, processed/failure counts, duration, last error, and processor details. Logging occurs only through the injected `LogSink`; raw images are never logged.

## Concurrency and boundaries

A reentrant lock protects lifecycle and processing state. Controlled input produces deterministic candidates and descriptors. Candidates are visual only. ENG-009 does not own scene tracking, semantic inventory, Knowledge, affordances, planning, execution, robots, TaskIR, simulation, or demonstration interpretation.

## Limitations

- The default detector creates algorithm-neutral contrast candidates, not semantic recognition.
- OpenCV and physical acceleration are optional and environment-dependent.
- No quantitative latency threshold is approved; duration is diagnostic.
- Reconfiguration requires a new lifecycle.

## Locations

- Source: `Implementation/ENG-009_Vision_Engine/Source/taskgraph_vision/`
- Tests: `Tests/ENG-009_Vision_Engine/`
- Specification: `Specifications/ENG-009_Vision_Engine/Specification.md`
- Reports: `Reports/ENG-009_Vision_Engine/`
