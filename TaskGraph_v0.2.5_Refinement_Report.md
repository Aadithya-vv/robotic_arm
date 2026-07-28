# TaskGraph v0.2.5 Refinement Report

## Implementation Summary

TaskGraph v0.2.5 stabilizes the existing M2 perception integration without changing architecture or Engine ownership.

- The selected YOLO11n/s/m provider now exclusively processes every frame. Classical processing occurs only when Classical CV is explicitly selected.
- YOLO exceptions produce a structured `YOLO Runtime Failed` result containing the model, frame number, exception, and stack summary. Failure remains latched until explicit detector reselection.
- Connect begins live inference automatically. Capture freezes the displayed frame for cropping. Disconnect stops inference and releases the camera. Start/Stop Live View controls were removed.
- Mock Camera now runs at 640×480. OpenCV requests 1280×720 and the UI displays the actual acquired resolution.
- Detector status exposes loaded state, backend, device, model path, inference latency/FPS, frame count, objects, recognitions, tracker, and Scene health.
- Preview labels use AI class or `Unknown Object`, optional user recognition name, confidence, and an object identifier. Proposal IDs remain internal.
- Recognition continues on every produced visual object, and Scene presentation includes stable ID, AI class, recognition name, confidence, age, motion, and relationships.
- Monitoring records CPU, RAM, GPU identity/memory, pipeline events, and a detector-consistency record for every frame. It emits a minute-level consistency attestation and raises immediately on a mismatch.
- Export now writes `Assets/TaskGraph_Runtime_Report.json` with the previous five minutes of health, runtime, detector, performance, objects, recognition, Scene, relationships, library, logs, warnings, exceptions, validation, and recent events.

## Validation Results

| Check | Result |
|---|---|
| Engine regression suite | PASS — 316 tests |
| v0.2.4/v0.2.5 integrated workflow | PASS |
| Continuous selected YOLO | PASS — YOLO11n frames 1, 2, and 3; no switching |
| Warm CPU inference evidence | PASS — approximately 617–622 ms on controlled 640×480 frames |
| Per-frame consistency audit | PASS — detector, inference, recognition, and Scene outcome recorded |
| Forced YOLO exception | PASS — remained `YOLO11N / FAILED`; no Classical CV output |
| Reverse shutdown | PASS |
| Frozen architecture integrity | PASS — no frozen document changes |

## Runtime Verification Evidence

The continuity run recorded three successive `frame/processed` events with `detector_used=YOLO11N`, monotonically increasing frame numbers, non-null inference times, and successful Scene updates. The forced-failure run produced `YOLO Runtime Failed: model=yolo11n; frame=1; RuntimeError: forced provider failure`; a second frame remained failed with the same selected detector.

## Remaining Limitations

- The current Python 3.13 host still lacks a usable Tcl 8.6 installation, so desktop construction cannot be smoke-tested here. Headless application behavior is fully testable.
- CUDA was unavailable on this host. CPU was explicitly reported; RTX 3050 throughput and GPU-memory presentation require validation on CUDA hardware.
- The deterministic Mock Camera image is synthetic and is intended for runtime stability, not household-object accuracy evaluation. Real-world detection quality must be assessed with a physical camera dataset.
- Bounding boxes use a custom rounded Canvas path and remain tightly mapped to detector regions.

## Architecture Compliance

ABP, GBP, Contracts, Specifications, Framework Prompts, repository structure, composition architecture, Engine count, Engine responsibilities, and Rule 40 remain unchanged. No new Engine was created and ENG-011 was not started.
