# TaskGraph v1.0.3 Session Lifecycle Cleanup Report

## 1. Objective achieved

TaskGraph now has an explicit filesystem lifecycle boundary between temporary session artifacts and permanent learned-object knowledge. The standard `python run_taskgraph.py` launch path clears the temporary session before backend startup and again after process shutdown.

## 2. Permanent vs temporary data separation

Permanent storage is limited to `Assets/ObjectLibrary/`. The cleanup service explicitly protects that directory and never traverses or deletes it.

Session-owned storage is allowlisted as:

- All contents of `Workspace/`, including imported-video artifacts, extracted frames, overlays, accepted/rejected review copies, preview images, logs, caches, and transient references.
- All contents of `.taskgraph-session/`, when present.
- `Assets/TaskGraph_Runtime_Report.json`, the current session report.

Repository source files, models, documentation, screenshots, historical engineering reports, and the Object Library are outside the cleanup allowlist.

## 3. Startup behavior

Before dependency verification or runtime startup, the launcher calls `clear_temporary_session(ROOT)`. The workspace directory is recreated empty. The Composition Root then constructs a fresh runtime with empty in-memory video metadata, frames, results, errors, progress, Scene snapshot, detection state, and monitoring timeline. The existing Object Library startup behavior loads its persistent JSON data unchanged.

The frontend no longer invents fallback frames. Frame count is derived exclusively from the current runtime workspace, so a restarted application presents an empty Frame Gallery, Detection Workspace dataset, cluster collection, and Scene projection.

## 4. New-session behavior

Choosing a new video immediately resets the import component's running flag and extraction progress before storing the new file selection. Existing `VideoWorkspace._extract` behavior already clears prior extracted and detected frame files when a new extraction begins; it was not modified. React cluster and review state is session-memory-only and is recreated with the application.

## 5. Shutdown behavior

The launcher first gracefully terminates and waits for frontend and backend processes. It then calls the same guarded cleanup routine in its `finally` block. This applies on normal child-process exit and Ctrl+C. Temporary workspace and current-session report artifacts are removed; permanent Object Library content is untouched.

If the Python launcher is forcibly killed at the operating-system level, shutdown code cannot run. The next startup cleanup still guarantees a clean session before TaskGraph becomes available.

## 6. Files modified

- `run_taskgraph.py`: startup and shutdown lifecycle hooks.
- `WebApp/src/lib.ts`: removed artificial 61-frame fallback.
- `WebApp/src/pages.tsx`: reset import progress when a replacement video is selected.

## 7. Files added

- `session_lifecycle.py`: allowlisted, containment-checked cleanup service.
- `Tests/test_session_lifecycle.py`: isolated temporary-directory lifecycle test.
- `TaskGraph_v1.0.3_Session_Lifecycle_Cleanup_Report.md`.

## 8. Architecture verification

No Engine, ABP, GBP, contract, specification, Composition Root, Rule 40 implementation, API, backend architecture, YOLO pipeline, Object Library implementation, Scene behavior, detection workflow, or UI layout was modified. Lifecycle cleanup is launcher-level infrastructure outside engine ownership.

## 9. Validation results

| Validation | Result | Evidence |
|---|---|---|
| Temporary frames removed | PASS | Isolated lifecycle unit test |
| Session report removed | PASS | Isolated lifecycle unit test |
| Object Library preserved | PASS | `objects.json` remains after cleanup |
| Cleanup path containment | PASS | Targets must resolve beneath repository root |
| Permanent-path exclusion | PASS | Explicit Object Library equality guard |
| Python syntax | PASS | `py_compile` for launcher and lifecycle module |
| Frontend lint | PASS with one existing warning | Zero errors; Fast Refresh organization warning only |
| TypeScript/Vite production build | PASS | 2,800 modules transformed |
| Real workspace destructive test | NOT RUN | Existing user session files were intentionally not deleted during validation |

## 10. Remaining limitations

- Cleanup is guaranteed when TaskGraph is started through `run_taskgraph.py`, which is the supported one-command launcher. Directly starting individual backend/frontend processes bypasses launcher lifecycle hooks.
- No process can run shutdown cleanup after an uncatchable termination or power loss; startup cleanup provides recovery on the next launch.
- Browser-selected `File` objects and object URLs are browser-memory state and naturally disappear when the tab/application closes; browsers do not expose them for filesystem cleanup.
