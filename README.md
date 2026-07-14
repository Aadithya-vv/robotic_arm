# TaskGraph

TaskGraph is a semantic robotic manipulation platform designed to transform human demonstrations into explainable, reusable task understanding and simulation execution.

## Current Release

**TaskGraph v0.1 — Core Platform** is the first runnable local desktop release. Milestone M1 composes the seven frozen Core Platform Engines and provides health monitoring, validation, activity diagnostics, export, and graceful shutdown.

## Architecture

The platform uses independent Engines communicating through public contracts under Rule 40. The v0.1 runtime contains Bootstrap, Kernel, Configuration, Registry, Event Bus, Memory, and Logging. `Integration/CompositionRoot/` is the sole concrete wiring layer; `App/` contains presentation only.

## Run

Requirements: Python 3 with Tkinter (included in the standard Windows Python distribution). No third-party package installation is required.

From the repository root:

```powershell
.\.venv\Scripts\python.exe Integration\CompositionRoot\main.py
```

For non-GUI release validation:

```powershell
.\.venv\Scripts\python.exe Integration\CompositionRoot\main.py --validate-only
```

From `Integration\CompositionRoot`, `python main.py` launches the desktop application.

## Repository Structure

- `ABP/`, `GBP/`, `Contracts/`: frozen architecture and shared meanings.
- `Specifications/`, `Prompts/`: Engine engineering authority.
- `Implementation/`: Engine source by artifact owner.
- `Integration/CompositionRoot/`: runtime wiring and executable entry point.
- `App/`: Tkinter desktop presentation.
- `Tests/`: Engine-owned tests, unchanged by M1.
- `Milestones/M1_CorePlatform/`: validation, startup, integration, freeze, and release reports.
- `Assets/`: screenshots placeholder and runtime exports.

## Desktop Layout

The desktop shows Runtime and seven Engine navigation items, a live activity timeline, selected Engine details, runtime health, validation, report export, and shutdown controls.

## Screenshots

Screenshots will be added during target-desktop release review. See `Assets/Screenshots/README.md`.

## Roadmap

- **M1 Core Platform:** complete and release-frozen.
- **Next:** Perception domain, beginning with ENG-008 Camera Engine after authorization.
- Later: semantic intelligence, planning/execution, user interaction, and infrastructure milestones.

Architecture changes continue to require formal review and an approved EDR.
