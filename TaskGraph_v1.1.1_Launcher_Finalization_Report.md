# TaskGraph v1.1.1 Launcher Finalization Report

## 1. Objective achieved

TaskGraph now starts without a terminal from the real Windows Desktop, opens a launcher-owned browser app window, detects that window closing, terminates the complete frontend/backend process trees, releases ports, cleans temporary session data, saves logs, removes its ownership lock, and exits.

## 2. Desktop detection

Desktop discovery uses the Windows `User Shell Folders` registry value first, the Shell `SHGetFolderPathW` API second, and OneDrive/USERPROFILE environment variables only as fallbacks. No Desktop path is hardcoded. On this machine it resolved to `C:\Users\aadit\OneDrive\Desktop`.

## 3. Shortcut generation

`TaskGraph Robotics Workstation.cmd` was created and verified on the detected Desktop. It changes to the project directory and uses `.venv\Scripts\pythonw.exe` with `run_taskgraph.py`; it contains no `python`, `py`, or global PATH launch. Creation, update, existing-file, and detected-Desktop states are logged.

## 4. Icon integration

The splash supports `Assets/Branding/taskgraph.ico` through the native Tk window-icon API. No robotic-arm logo or other branding image was present under `Assets`, `WebApp/src`, the attachment, or the web public assets, so conversion and application to the shortcut, splash artwork, and favicon could not be completed without inventing a replacement. CMD files also do not support native custom icons; a `.lnk` would be required for a Windows icon-bearing shortcut.

## 5. Splash improvements

The splash identifies TaskGraph Robotics Workstation v1.1.1 and progressively displays environment checks, CUDA/GPU details, backend and frontend readiness, browser launch, process IDs, and Ready state. It remains available as the runtime manager until the owned browser closes.

## 6. Browser ownership

The launcher locates Microsoft Edge or Google Chrome and starts a dedicated `--app=http://127.0.0.1:5173` process with a session-only browser profile. The exact browser process is stored in the instance lock and polled every 750 ms. Closing that app window is therefore observable and triggers automatic shutdown. Microsoft Edge was detected and used during acceptance validation.

## 7. Shutdown workflow

Browser close → browser stop → graceful frontend termination → graceful backend termination → timed wait → forced process-tree termination if necessary → verified TaskGraph port-owner sweep → session cleanup → lock removal → shutdown log → launcher exit.

The final sweep fixed an npm/Vite behavior where the Node child could survive after its CMD parent exited. Only processes whose Windows command line resolves beneath the TaskGraph project are eligible for forced recovery or cleanup.

## 8. Startup recovery

`.taskgraph-instance.json` records launcher, backend, frontend, and browser PIDs. A later launch validates recorded PID command lines before terminating stale TaskGraph processes, preventing PID-reuse damage. It also inspects listeners on ports 8000 and 5173 and terminates only verified TaskGraph-owned listeners before startup.

## 9. Logging

`Logs/launcher.log` now records Desktop detection, shortcut state, browser executable/PID, backend and frontend PIDs, browser close, startup recovery, shutdown start/completion, and cleanup results. Backend, frontend, startup, and shutdown logs remain append-only.

## 10. Files modified

- `Launcher/browser_manager.py`
- `Launcher/desktop_shortcut.py`
- `Launcher/launcher.py`
- `Launcher/process_manager.py`
- `Launcher/runtime_state.py`
- `Launcher/splash.py`
- `Tests/test_launcher.py`

## 11. Files added

- `Launcher/startup_recovery.py`
- `TaskGraph_v1.1.1_Launcher_Finalization_Report.md`
- Desktop `TaskGraph Robotics Workstation.cmd`

## 12. Validation results

| Check | Result |
|---|---|
| Real Desktop correctly detected | PASS |
| CMD created/updated | PASS |
| CMD uses project pythonw | PASS |
| No terminal launch command | PASS |
| Edge/Chrome detected | PASS — Microsoft Edge |
| Splash shown | PASS during desktop acceptance |
| Browser automatically opened | PASS |
| Browser close detected | PASS |
| Launcher exited | PASS |
| Backend stopped | PASS |
| Frontend and Vite child stopped | PASS |
| Ports 8000 and 5173 released | PASS |
| Instance lock removed | PASS |
| Workspace cleaned | PASS |
| Second controlled launch | PASS |
| Startup orphan recovery | PASS; verified old TaskGraph listeners removed |
| Object Library preserved | PASS via lifecycle regression test |
| Automated unit tests | PASS — 5 tests |
| Logo/icon applied | BLOCKED — supplied logo asset absent |

Final acceptance output: `Ready=true`, `LauncherExited=true`, `PortsReleased=true`, `LockRemoved=true`, `WorkspaceClean=true`, `ShortcutExists=true`.

## 13. Remaining limitations

- The requested robotic-arm logo file is absent. Add it as `Assets/Branding/taskgraph.ico` (and ideally PNG/SVG variants) to activate the existing splash icon hook and enable favicon/`.lnk` integration.
- Browser ownership uses Edge/Chrome app mode. Systems with neither installed receive a friendly startup error because an arbitrary default-browser tab cannot be reliably monitored.
- OS power loss or forced launcher termination cannot execute shutdown code; startup recovery handles stale TaskGraph locks, listeners, and workspace data on the next launch.

## 14. Freeze recommendation

Freeze launcher process ownership, shutdown, recovery, Desktop detection, and shortcut generation. After the missing official logo is supplied, add the branding files and an icon-bearing `.lnk` without changing runtime behavior, then freeze the full launcher milestone.
