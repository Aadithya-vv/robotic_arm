# TaskGraph v0.4 Refinement Report

## M2 FINAL stabilization

The Detection Workspace now operates exclusively on extracted image frames. The application-owned immutable `ExtractedFrame` value satisfies the existing structural Vision boundary without importing or constructing ENG-008 Camera observations. The Camera Engine remains composed and unchanged for future milestones.

Every extracted frame is attempted in sequence on a background worker. Errors are captured as structured per-frame monitor events, surfaced in review, included in exports, and do not terminate the batch.

Original images remain in `Workspace/Frames`. Green-box annotated images containing class labels and confidence are written to `Workspace/Frames/Detected`; accepted and rejected review results are copied to their corresponding directories. Native YOLO coordinates are used directly, with no box enlargement or multi-scale remapping. Human classes are discarded immediately after inference.

The review panel now shows frame number, status, detected objects, and confidence, and supports selecting a detection, creating an object, deleting a detection, and moving to the next frame. Controls use padded centered captions and minimum widths. The persistent status area exposes task, percent, processed frames, device, model, FPS, inference time, elapsed time, ETA, memory, and last completed operation.

## Architecture assurance

ENG-001 through ENG-010, ABP, GBP, shared contracts, specifications, framework prompts, Engine responsibilities, Rule 40, engine count, and repository structure remain unchanged.

## Freeze recommendation

The 316 ENG-001 through ENG-010 regressions, the v0.4 integration workflow, compilation checks, and headless startup/validation/reverse-shutdown checks pass. GUI construction remains blocked on this host by the existing Python/Tcl installation issue (`init.tcl` unavailable), not by an application exception.

TaskGraph v0.4 Milestone M2 is stabilized and ready for freeze after the GUI smoke test is repeated on a host with a working Tk/Tcl installation.
