# TaskGraph v0.4 Application

TaskGraph v0.4 — Robotic Teaching Workstation is a video-first Tkinter application for Milestone M2.

Default workflow:

`Import Video → Extract Frames → Frame Gallery → Run Model → Review → Create Objects → Object Library`

The Detection Workspace has no CameraObservation dependency. Immutable application-owned extracted frames are processed on a worker thread, annotated without overwriting originals, and reviewed with frame number, objects, confidence, and status. One frame failure is logged and does not stop the batch. The responsive bottom status bar and Export Report button remain visible throughout the application.

Run `python Integration\CompositionRoot\main.py`, or add `--validate-only` for headless validation.
