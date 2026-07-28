# TaskGraph v0.2.3 Refinement Report

| Field | Value |
|---|---|
| Release | TaskGraph v0.2.3 |
| Milestone | M2 — Perception Layer refinement |
| Date | 2026-07-15 |
| Architecture | Frozen and unchanged |
| Engine Count | 24 defined; ENG-001 through ENG-010 implemented |
| New Engine | None |
| Status | Ready for refinement review with documented host limitations |

## Repository Integrity

ABP, GBP, repository Contracts, Specifications, Framework Prompts, Engine responsibilities, Engine count, and repository architecture were not changed. Rule 40 remains enforced: the Composition Root injects model, detector, recognition, monitoring, and library providers through existing public boundaries.

All previous Engine suites pass: **316 tests** across ENG-001 through ENG-010. The legacy M1 Composition Root convenience behavior was restored without changing Engine behavior. M2 startup, perception validation, health, and exact reverse shutdown pass.

## Model Management

Added `ModelManager` with manifest-based discovery, automatic download when absent, SHA-256 verification, runtime availability detection, and non-crashing diagnostics.

Official YOLO11n weights:

- Path: `Models/yolo11n.pt`
- Size: 5,613,764 bytes
- SHA-256: `0ebbc80d4a7680d14987a577cd21342b65ecfd94632bd9a8da63ae6417644ee1`
- Source: official Ultralytics assets release

Two official `pip install ultralytics` attempts stalled before installing any package. Consequently, the weights are installed and verified but the Ultralytics/Torch inference runtime is unavailable on this host. `UltralyticsDetector` reports that condition and the pipeline automatically continues through OpenCV/classical providers.

## Vision and Recognition Improvements

- Adaptive white balance, CLAHE, gamma correction, brightness/contrast normalization, histogram treatment, denoising, sharpening, shadow compensation, adaptive thresholding, edges, morphology, contours, corners, texture, gradient, and shape processing.
- Optional YOLO11 AI detections with class, confidence, box, and explicit human/object separation.
- Classical proposal fallback, full-frame rejection, AI/classical overlap suppression, NMS, duplicate removal, and confidence ordering.
- ORB, Hu moments, color histograms, dominant colors, gradients, geometry, circularity, compactness, corners, edges, texture, component scores, and motion-vector descriptors.
- Descriptor matching against user-created Memory records. Matching proposals expose known/unknown state, user name, library identity, AI class, and recognition confidence without modifying Scene or semantic Engine contracts.
- Detector abstractions remain open for future YOLO-World, Grounding DINO, SAM, and custom providers; those models were not installed because v0.2.3 does not require them.

## Object Library and Workflow

- Frozen displayed-frame capture with exact pixel crop data.
- Draggable and reselectable crop; keyboard movement.
- Required name validation and duplicate-name rejection.
- User name, AI name, aliases, category, tags, notes, original/crop/thumbnail data, descriptors, colors, histogram, shape, texture, recognition history/statistics, times seen, confidence, created/last-seen metadata.
- Search, sort, details, edit, delete, and Memory-backed storage.
- Capture-before-connect guidance, idempotent start, disconnect-during-live handling, provider switching, corrupt/failure boundaries, and in-process Perception Reset.

## UI and Monitoring

- Camera occupies 40% of the Perception workspace.
- Overlays show boxes, candidate or recognized labels, confidence, and centers.
- Camera/Vision/Scene state animation plus detection count, recognition count, FPS, latency, CPU, RAM, descriptors, known/unknown objects, motion, age, confidence, and relationships.
- Background monitoring samples every second and retains the exact preceding 300 seconds.

## Export

`Assets/TaskGraph_v0.2.3_RuntimeExport.json` was generated and parsed successfully. It includes runtime/system/configuration, Engine health, validation, Camera, Vision, Scene, tracked objects, relationships, recognition, Object Library assets, descriptors, model status, performance, CPU, RAM, FPS, latency, Memory statistics, current snapshot, five-minute timeline, logs, warnings, errors, exceptions, and recent events.

## Files Added

- `Models/yolo11n.pt`, `Models/models.json`, `Models/README.md`
- `Integration/CompositionRoot/model_manager.py`
- `Integration/CompositionRoot/ai_detector.py`
- `Integration/CompositionRoot/descriptors.py`
- `Integration/CompositionRoot/fusion.py`
- `Integration/CompositionRoot/recognition.py`
- `Integration/CompositionRoot/test_v023.py`
- `TaskGraph_v0.2.3_Refinement_Report.md`

## Files Updated

- Composition Root runtime, startup, shutdown, monitoring, perception, adaptive Vision provider, and Object Library.
- Desktop application, object dialogs, README, release notes, and M2 validation evidence.

## Validation Results

- ENG-001 through ENG-010: **316/316 tests pass**.
- v0.2.3 headless workflow: PASS.
- Model checksum: PASS.
- Mock/OpenCV-safe provider behavior: PASS.
- Multi-object detection: PASS — four controlled candidates.
- Scene: PASS — four tracked objects and 28 geometric relationships.
- Recognition learning: PASS.
- Object creation and duplicate rejection: PASS.
- One-second monitoring: PASS.
- Export generation and JSON parse: PASS.
- Provider switching and Perception Reset: PASS.
- Reverse shutdown: PASS.

## Remaining Limitations

- AI inference cannot execute until a compatible Ultralytics/Torch runtime is installed. Classical OpenCV processing remains operational.
- Generic models cannot guarantee detection of every arbitrary, partially hidden, or domain-specific object.
- The current Python 3.13 installation cannot locate Tcl 8.6 `init.tcl`; desktop window construction and manual GUI verification must be repeated on a host with working Tk/Tcl.
- Scene remains visual/runtime only. User and AI labels are application presentation/library metadata and do not alter semantic architecture.

## Release Readiness

The headless v0.2.3 perception system is ready for refinement review. Desktop release approval remains conditional on resolving the host Tk/Tcl installation and repeating manual UI verification. ENG-011 was not implemented.
