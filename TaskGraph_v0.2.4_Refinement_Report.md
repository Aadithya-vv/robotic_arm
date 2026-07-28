# TaskGraph v0.2.4 Refinement Report

## Outcome

TaskGraph v0.2.4 completes the Advanced Perception Refinement without changing the frozen architecture. The ten-Engine M2 runtime remains contract-only and Rule 40 compliant.

## Delivered

- Installed authoritative YOLO11n, YOLO11s, and YOLO11m weights in `Models/`, with manifest SHA-256 verification and automatic discovery.
- Implemented AUTO model selection in the order YOLO11m, YOLO11s, YOLO11n, then Classical CV, plus manual selection and safe failure fallback.
- Added adaptive illumination enhancement, multi-scale/tiled AI inference, classical proposal recovery, fusion/NMS, tight-region rejection, descriptors, recognition, and temporal stabilization.
- Expanded Object Library metadata, duplicate protection, recognition history/statistics, and edit support.
- Expanded workstation detector controls, status, six-stage visualization, camera preview allocation, scene detail, performance monitoring, and five-minute export evidence.
- Preserved deterministic Mock Camera operation when no physical camera is available.

## Model Evidence

| Model | Bytes | SHA-256 |
|---|---:|---|
| YOLO11n | 5,613,764 | `0ebbc80d4a7680d14987a577cd21342b65ecfd94632bd9a8da63ae6417644ee1` |
| YOLO11s | 19,313,732 | `85a76fe86dd8afe384648546b56a7a78580c7cb7b404fc595f97969322d502d5` |
| YOLO11m | 40,684,120 | `d5ffc1a674953a08e11a8d21e022781b1b23a19b730afc309290bd9fb5305b95` |

The verified local AI runtime is Ultralytics 8.4.95 with Torch 2.13.0+cpu. AUTO selected YOLO11m and real inference succeeded. The initial controlled CPU run took approximately 4.19 seconds; this is graceful CPU degradation and does not meet the specified RTX 3050 FPS targets, which require validation on that GPU class.

## Validation

- Ten Engines started in the approved order and reported healthy.
- Camera acquisition, AI inference, hybrid object detection, recognition, Scene update, relationships, Object Library mutation, monitoring, export, and reverse shutdown passed headlessly.
- All three installed model variants and Classical CV are covered by the v0.2.4 integration verification.
- The complete ENG-001 through ENG-010 regression suite passed: **316 tests in 2.24 seconds**.
- The dedicated v0.2.4 workflow test passed across all three YOLO variants, Classical CV, recognition, export, reset, and shutdown.
- Frozen ABP, GBP, Contracts, Specifications, and Framework Prompts were not modified.

## Files Updated

Changes are confined to M2 implementation, tests, documentation, reports, application presentation, composition-root integration, model assets, release evidence, and `ImplementationStatus.md`. No ENG-011 work was started.

## Known Limitations

- Desktop construction cannot be completed on the current host because its Python 3.13 installation cannot locate Tcl 8.6 `init.tcl`; headless runtime validation is unaffected. A GUI smoke test remains required on a host with working Tk/Tcl.
- GPU throughput targets require an RTX 3050-class validation host; only CPU behavior was available here.
- Face/hand separation remains dependent on the available visual providers and model classes; it is not a biometric or pose-analysis subsystem.
- Recognition is visual descriptor matching within M2 and does not introduce M3 semantic ownership.

## Readiness

The v0.2.4 refinement is ready for architecture and release review. The only outstanding host-level check is the GUI smoke test on a working Tk/Tcl installation. ENG-011 remains out of scope.
