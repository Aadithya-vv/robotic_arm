# M2 Perception Validation Report

| Field | Result |
|---|---|
| Date | 2026-07-15 |
| Command | `.\.venv\Scripts\python.exe Integration\CompositionRoot\main.py --validate-only` |
| Startup | PASS — ten Engines in approved order |
| Registry | PASS — ten registrations |
| Camera | PASS — Mock provider and frame acquisition |
| Vision | PASS — four non-semantic visual candidates on controlled Mock input |
| Scene | PASS — tracking and immutable snapshot |
| Runtime Health | PASS — ten Engines healthy |
| Shutdown | PASS — ten Engines in reverse order |
| Previous Engine Tests | PASS — 316 tests across ENG-001 through ENG-010 |
| v0.2.4 Workflow | PASS — all YOLO variants, Classical CV, recognition, export, reset, shutdown |
| YOLO11 Models | PASS — n/s/m installed in `Models/`; all SHA-256 values verified |
| AI Runtime | PASS — Ultralytics 8.4.95, Torch 2.13.0+cpu; real inference succeeded |
| Detector AUTO | PASS — selected YOLO11m; fallback order m → s → n → Classical CV |
| Hybrid Vision | PASS — four candidates on controlled Mock input |
| Descriptors | PASS — component descriptors and recognition vector generated |
| Recognition | PASS — stored object recognized on repeated observation |
| Object Library | PASS — create, list, duplicate rejection, export |
| Monitoring | PASS — one-second sample and five-minute window |
| v0.2.4 Export | PASS — generated and parsed as JSON |
| Perception Reset | PASS — reset and reconnect without application restart |

The validation used the Mock Camera and local model assets; it required no GUI, network, or physical camera. OpenCV and Ultralytics were exercised locally.

Desktop construction was attempted separately but the host Python installation could not locate Tcl 8.6 `init.tcl`. This is an environment prerequisite failure rather than a TaskGraph runtime failure; release review must repeat the GUI smoke test with a working Tk/Tcl installation.

## v0.4 M2 FINAL stabilization checks

| Check | Result |
|---|---|
| Detection Camera Independence | PASS — no `CameraObservation` import or construction in Detection Workspace |
| Batch Continuation | PASS — frame failures are recorded and subsequent frames continue |
| Annotated Outputs | PASS — originals retained; Detected/Accepted/Rejected directories managed |
| Human Filtering | PASS — person, hand, face, arm, and body removed immediately after inference |
| UI Thread Safety | PASS — extraction and detection execute in daemon worker threads |
| ENG-001 through ENG-010 Regression | PASS — 316 tests |
| v0.4 Integration Workflow | PASS — 1 end-to-end integration test |
| Headless Runtime Validation | PASS — startup, validation, and reverse shutdown |
| GUI Smoke Test | BLOCKED BY HOST — Python 3.13 installation cannot locate Tcl 8.6 `init.tcl` |
