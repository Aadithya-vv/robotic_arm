# TaskGraph Release Notes

## TaskGraph v1.0 — Web Edition

- Added a FastAPI presentation adapter with REST and WebSocket projections.
- Added a React + TypeScript + Vite engineering workstation with Tailwind styling.
- Added responsive navigation, workspace, inspector, and runtime status surfaces.
- Added runtime charts, detection tables, object cards, React Flow scene graph, validation, and reporting.
- Added WebSocket-driven React Query cache refresh with no polling.
- Preserved all Python Engines, contracts, module names, runtime logic, workers, CUDA, YOLO, architecture, and Rule 40 boundaries.

## TaskGraph v0.4 — M2 FINAL Stabilization

- Removed the last `CameraObservation` construction from the Detection Workspace and aligned frame/request correlation.
- Processed all extracted frames on a worker thread with per-frame error isolation and structured monitoring.
- Added `Workspace/Frames/Detected`, `Accepted`, and `Rejected`; originals are never overwritten.
- Removed multi-scale/tiled box remapping so rendered boxes use native YOLO coordinates.
- Filtered person, hand, face, arm, and body detections immediately after inference.
- Added annotated-frame review, frame/object/confidence/status rows, Move Next, review persistence, and responsive controls/status telemetry.
- Expanded exported frame results with annotated paths and review status.
- No Engine, contract, specification, prompt, architecture, repository-structure, responsibility, Rule 40, or engine-count change.

## TaskGraph v0.4 — Final M2 Refinement and Freeze

- Replaced the live-camera UI with the video teaching workflow.
- Added progressive cancellable extraction/detection and persistent telemetry.
- Enforced YOLO11m → YOLO11s → YOLO11n → Classical CV AUTO ordering.
- Removed human detections and all automatic library influence during review.
- Added permanent Object Library storage and comprehensive JSON export.
- Marked Milestone M2 FINAL and ready to freeze.

## v0.2.6 — Runtime Stability and GPU Optimization

**Release date:** 2026-07-15

- Fixed mixed dictionary/dataclass proposal handling; fusion now uses immutable `VisualObject` attributes exclusively.
- Added explicit CUDA initialization and device placement. AUTO selects YOLO11m on CUDA and YOLO11n on CPU.
- Added bounded Camera, Inference, Recognition, and Scene workers; the UI polls completed results and never performs inference.
- Added stale-frame dropping, worker/queue health, complete joined teardown, buffer clearing, and reconnect verification.
- Added rolling camera/inference/recognition FPS, pipeline/inference/Scene latency, CPU/RAM/GPU metrics, and dropped-frame counts.
- Expanded startup diagnostics and `TaskGraph_Runtime_Report.json` with PyTorch, CUDA, GPU, model, camera, recognition, Scene, and worker evidence.
- No Engine, contract, interface, responsibility, specification, prompt, repository structure, composition architecture, or Rule 40 change.

## v0.2.5 — Perception Stability and AI Detection Refinement

**Release date:** 2026-07-15

- Made the selected detector the exclusive owner of every frame until explicit reselection or disconnect.
- Removed silent YOLO-to-classical fallback and added a latched failed state with model, frame, exception, and stack context.
- Connect now begins live inference immediately; Capture freezes the current frame; Disconnect stops inference and releases the provider.
- Removed Start/Stop Live View controls and raised Mock Camera operation to 640×480; OpenCV requests 1280×720.
- Added user-facing AI labels, recognition names/confidence, detailed detector/device/model status, GPU metrics, and per-frame consistency audits.
- Standardized the five-minute export as `Assets/TaskGraph_Runtime_Report.json`.
- No Engine, contract, responsibility, specification, prompt, composition architecture, or Rule 40 change.

## v0.2.4 — Advanced Perception Refinement

**Release date:** 2026-07-15

- Added checksum-verified YOLO11n, YOLO11s, and YOLO11m assets under the authoritative `Models/` directory.
- Added AUTO selection (`m → s → n → Classical CV`), manual detector selection, and detector/runtime diagnostics.
- Added adaptive enhancement, multi-scale/tiled inference, classical proposal recovery, fusion/NMS, and temporal stabilization.
- Expanded descriptors, library recognition history, scene presentation, five-minute monitoring, and runtime export.
- Verified real Ultralytics/Torch CPU inference and graceful classical degradation without changing frozen architecture.
- No Engine, contract, responsibility, specification, prompt, or Rule 40 change.

## v0.2.3 — Professional Perception Workstation

**Release date:** 2026-07-15

- Official YOLO11n weights cached and checksum verified by the Model Manager.
- Optional Ultralytics provider with explicit missing-runtime diagnostics and safe OpenCV fallback.
- Hybrid AI/classical proposals with NMS, duplicate removal, person separation, and tight-box filtering.
- ORB, Hu moment, color histogram, dominant-color, texture, shape, corner, edge, and gradient descriptors.
- Descriptor recognition against the Memory-backed Object Library.
- Expanded asset metadata, editing, duplicate-name protection, preview data, recognition history/statistics fields.
- One-second rolling CPU/RAM and perception monitoring retained for exactly five minutes.
- Full v0.2.3 developer/architect JSON export and headless integration verification.
- No new Engine, milestone, contract, responsibility, or architectural change.

## v0.2.1 — Perception Workstation Refinement

**Release date:** 2026-07-15

- Adaptive optional-OpenCV illumination enhancement and classical visual detection.
- Multiple independent proposals with geometry, appearance, and component confidence scores.
- Long-lived Scene tracking configuration.
- Frozen-frame crop selection, metadata entry, and Memory-backed Object Library.
- Five-minute rolling monitoring and comprehensive JSON diagnostics export.
- Larger preview, richer overlays, live statistics, reset, and workflow recovery.
- No new Engine, contract, responsibility, milestone, or architectural change.

## v0.2 — Perception Layer

**Status:** Runnable desktop application
**Release date:** 2026-07-15

### Features

- Ten-Engine Composition Root with approved startup and reverse shutdown.
- Camera→Vision→Scene processing through public contracts.
- Mock Camera and optional OpenCV with safe fallback.
- Vision candidates, confidence, descriptors, regions, and timing.
- Persistent Scene Objects, geometric relationships, snapshots, and diagnostics.
- Overview, Roadmap, Engines, Perception, Validation, and Live Logs pages.
- One-click M2 demo, enriched export, and headless validation.

### Known Limitations

- Visual observations remain non-semantic.
- Scene geometry is image-plane only.
- OpenCV functionality depends on host installation and webcam.
- No packaged installer or industrial real-time guarantee.

### Next Milestone

M3 Semantic Intelligence, beginning only after explicit ENG-011 authorization.

## v0.1 — Core Platform

**Status:** Runnable desktop application  
**Release date:** 2026-07-14

### Features

- Local-first Tkinter desktop dashboard.
- Seven-Engine Composition Root using public contracts only.
- Structured startup and reverse shutdown.
- Live Engine state, health, version, lifecycle, and activity timeline.
- On-demand Core Platform validation.
- JSON runtime report export.
- Structured startup-error display.

### Implemented Engines

ENG-001 Bootstrap, ENG-002 Kernel, ENG-003 Configuration, ENG-004 Registry, ENG-005 Event Bus, ENG-006 Memory, and ENG-007 Logging.

### Architecture Summary

The Composition Root is the only concrete assembly layer. Engine responsibilities remain isolated and Rule 40-compliant. Bootstrap establishes the lifecycle; Logging accepts diagnostics; Configuration supplies validated settings; Registry exposes metadata; Event Bus routes events; Memory owns temporary state; Kernel coordinates runtime.

### Known Limitations

- Core Platform only; no camera, vision, semantics, planning, simulation, or user workflow Engines.
- No packaged installer or executable bundle.
- Runtime logs and Memory are local and non-persistent.
- Screenshot capture awaits desktop release review.

### Next Milestone

Perception engineering beginning with ENG-008 Camera Engine, only after explicit authorization.
