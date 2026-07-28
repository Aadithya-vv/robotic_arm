# TaskGraph v0.2.6 Runtime Stability Report

## Implementation Summary

The final M2 refinement fixes representation consistency, enables verified CUDA execution, moves continuous perception off the UI thread, bounds all staged queues, and makes camera teardown/reconnection deterministic. Frozen architecture and Engine interfaces remain unchanged.

The Vision/Fusion path now carries immutable `VisualObject` instances throughout and accesses `confidence`, `region`, `properties`, and other fields through attributes. Temporary subscripted proposal dictionaries were removed.

## Performance Improvements

- Camera, Inference, Recognition, and Scene run as independent named workers.
- Three size-one queues bound memory and discard stale frames instead of blocking capture or the UI.
- Tk polls published immutable results every 33 ms and performs no inference.
- Rolling five-minute averages cover camera/inference/recognition FPS, pipeline/inference/Scene latency, CPU, RAM, GPU memory, queue depth, and dropped frames.
- Files remain below the approximate 500-line refactoring threshold; worker and GPU responsibilities are isolated in focused modules.

## GPU Verification

| Field | Verified value |
|---|---|
| PyTorch | 2.11.0+cu128 |
| CUDA runtime | 12.8 |
| `torch.cuda.is_available()` | True |
| GPU | NVIDIA GeForce RTX 3050 Laptop GPU |
| AUTO detector | YOLO11m |
| Device placement | CUDA |
| Real inference | PASS |

Startup validation reported `device=NVIDIA GeForce RTX 3050 Laptop GPU CUDA`. The first validation inference, including model/device initialization, took approximately 4.89 seconds. The integrated rolling evidence recorded warm inference around 617 ms for the exercised multi-model/multi-scale workload. Throughput remains workload-dependent.

If CUDA initialization fails, TaskGraph reports `CUDA Initialization Failed` with the exception rather than claiming the GPU is unavailable or silently changing detectors.

## Camera Lifecycle Verification

The threaded lifecycle was exercised as follows: open Mock Camera, start all four workers, publish three Scene results, disconnect, join every worker, empty all queues, close the Camera Engine/provider, reconnect, restart all workers, and publish another result. Camera state changed to `closed` on disconnect and `ready` after reconnect. Final reverse shutdown passed.

## Thread Verification

All four workers reported alive during operation:

- `taskgraph-camera`
- `taskgraph-inference`
- `taskgraph-recognition`
- `taskgraph-scene`

Queue depth never exceeded one. Under deliberate producer overload, 92 stale frames were discarded while three results completed; this is intentional bounded-latency behavior. After disconnect, no worker remained alive and every queue depth was zero. Worker failure is recorded and raised to the UI rather than silently ignored.

## Validation Results

| Check | Result |
|---|---|
| Engine regression suite | PASS — 316 tests |
| Integrated detector/library/export workflow | PASS |
| Headless ten-Engine validation | PASS |
| AUTO CUDA selection | PASS — YOLO11m |
| CUDA model inference | PASS |
| VisualObject representation audit | PASS — attribute access throughout fusion |
| Detector consistency | PASS |
| Bounded queue depth | PASS — maximum 1 |
| Worker liveness | PASS |
| Disconnect/reconnect | PASS |
| Reverse shutdown | PASS |
| Frozen architecture integrity | PASS |

## Export Evidence

`Assets/TaskGraph_Runtime_Report.json` includes the previous five minutes, Engine health, Camera, Vision, Recognition, Scene, detector/model/CUDA diagnostics, FPS and latency averages, CPU/RAM/GPU metrics, objects, relationships, errors, warnings, exceptions, logs, validation, worker health, queues, dropped frames, recognition statistics, Scene statistics, and startup diagnostics.

## Known Limitations

- This Python 3.13 installation still cannot locate Tcl 8.6 `init.tcl`, so the Tk window cannot be constructed on the current host. Headless runtime, CUDA, workers, Camera lifecycle, export, and shutdown remain verifiable.
- The deterministic Mock Camera validates stability rather than real-world detection accuracy.
- Initial CUDA/model compilation is substantially slower than warm inference.
- Anti-aliased rounded overlays depend on Tk Canvas smoothing and are less sophisticated than GPU-rendered UI overlays.

## Final M2 Freeze Recommendation

The runtime implementation is suitable for M2 freeze review: architecture is unchanged, all 316 Engine tests pass, CUDA and AUTO selection are verified, perception no longer blocks the UI, resources are bounded, disconnect/reconnect succeeds, failures are explicit, and the export contains reproducible runtime evidence. The freeze review should record the host Tcl prerequisite and perform a final visual smoke test after Tk/Tcl is repaired.
