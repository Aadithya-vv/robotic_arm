# TaskGraph Release Notes

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
