# TaskGraph v1.0 — Web Edition Robotics Workstation

TaskGraph now includes a FastAPI + React presentation layer over the unchanged Python Engine architecture.

```powershell
.\.venv\Scripts\python.exe -m uvicorn api:app --app-dir Integration\WebAPI --host 127.0.0.1 --port 8000
cd WebApp
npm install
npm run dev
```

The existing Tkinter application and all ENG-001 through ENG-010 modules remain available. See `TaskGraph_v1.0_Web_Migration_Report.md`.

## TaskGraph v0.4 — Robotic Teaching Workstation

Milestone M2: **FINAL — READY TO FREEZE**

TaskGraph is a contract-driven robotic teaching workstation composed from the existing ENG-001 through ENG-010 engines. Version 0.4 keeps the architecture, shared contracts, specifications, framework prompts, engine responsibilities, Rule 40, and repository structure unchanged.

## Default workflow

`Import Video → Extract Frames → Frame Gallery → Run Model → Review → Create Objects → Object Library`

- Background frame extraction, default 1 FPS, with progress, ETA, current frame, and cancellation
- Every extracted frame is processed independently; a failed frame is logged and the batch continues
- Original frames remain under `Workspace/Frames`; rendered results are saved under `Detected`, `Accepted`, and `Rejected`
- Tight native YOLO coordinates, rendered labels/confidence, immediate human-class filtering, and explicit user review
- No live-camera UI, human detections, automatic match, merge, or library-influenced review
- Permanent disk-backed editable Object Library
- Non-semantic Scene display
- Permanent last-five-minute JSON export and persistent resource/status bar

Run:

```powershell
python Integration\CompositionRoot\main.py
python Integration\CompositionRoot\main.py --validate-only
```

AUTO detector order is YOLO11m, YOLO11s, YOLO11n, then Classical CV only when YOLO is unavailable before a run. Per-frame runtime failures are recorded without stopping the imported-frame batch.

Library data is stored at `Assets/ObjectLibrary/objects.json`; reports are written to `Assets/TaskGraph_Runtime_Report.json`.

See `TaskGraph_v0.4_Final_Report.md` for freeze evidence.
