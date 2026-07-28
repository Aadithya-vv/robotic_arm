# TaskGraph v1.1.5 Launcher Freeze Report

## Architecture review

This refinement is confined to `Launcher/` and this report. ABP, GBP, Rule 40, Engine responsibilities, Composition Root, Web Application, Object Library, detection pipeline, and session lifecycle implementations were not changed. The launcher remains an orchestration shell around those frozen responsibilities.

## Launcher and subprocess audit

| Process | Previous launch method | Console risk | Fix applied |
|---|---|---:|---|
| Launcher | Desktop `.cmd` starts project `pythonw.exe` | Low for Python; `.cmd` compatibility entry can flash when used directly | Branded `.lnk` now targets `pythonw.exe` directly; `.cmd` retained because the milestone explicitly requires it |
| Environment probe | `.venv/python.exe -c` via `subprocess.run` | Yes | Central hidden Windows startup information and `CREATE_NO_WINDOW` |
| Backend | `.venv/python.exe -m uvicorn`, new process group only | Yes | Direct executable launch with `CREATE_NO_WINDOW`, `STARTF_USESHOWWINDOW`, `SW_HIDE`, no shell |
| Frontend | `npm.cmd run dev` | Yes; `.cmd` command processor | Replaced with direct `node.exe node_modules/vite/bin/vite.js`; hidden flags; no shell |
| Browser | Edge/Chrome app process, new process group only | Possible console inheritance | Hidden startup options and owned unique profile retained |
| Port recovery | `netstat` | Yes | Hidden direct execution |
| Process identity recovery | PowerShell CIM query | Yes | Non-interactive hidden PowerShell plus no-window process flags |
| Forced process-tree shutdown | `taskkill` | Yes | Hidden direct execution with captured output |
| `.lnk` generation | Missing | N/A | WScript shortcut creation through non-interactive hidden PowerShell; failure is logged and non-fatal |

No launcher process uses `shell=True` or `cmd /c`. The runtime frontend no longer depends on `npm.cmd` process execution.

## Console window audit

`Launcher/windows.py` is the single Windows background-process policy. It supplies a `STARTUPINFO` with `STARTF_USESHOWWINDOW` and `SW_HIDE`, plus `CREATE_NO_WINDOW`; owned long-running processes also receive `CREATE_NEW_PROCESS_GROUP` for lifecycle control. Static validation on Windows confirmed both the no-window creation flag and hidden show-window value.

## Startup pipeline

The launcher presents and logs these stages: stale-runtime recovery, temporary workspace cleanup, Object Library check, environment/dependency checks, YOLO model check, GPU/CUDA probe, backend start and health check, frontend start and readiness check, browser opening, and Ready. Readiness waits pump Tk events every 150 ms, keeping the splash responsive.

The dark splash now displays version, progress, current stage, GPU, CUDA, backend, frontend, browser, and append-only log status. Expected startup failures are translated into friendly backend, frontend/Node, browser, or occupied-port guidance; raw tracebacks remain in `Logs/launcher.log`, not in the user-facing status.

## Process management

Launcher, backend, frontend, browser, and monitor records track PID, start time, health, restart count, and state. The monitor shares the launcher PID because it is a managed thread. Backend and frontend health recovery terminates the unhealthy owned process before replacement. Shutdown terminates, waits, escalates to hidden process-tree termination if necessary, runs stale-port recovery, clears temporary session data, and releases the instance lock.

The owned browser uses a unique TaskGraph profile. Browser-process exit triggers automatic shutdown of frontend, backend, temporary runtime, and launcher. Browser forced shutdown also waits and escalates to process-tree cleanup.

## Recovery verification

The existing instance lock is recovered automatically. Stored TaskGraph PIDs are identity-checked before termination. TaskGraph-owned listeners on ports 8000 and 5173 are recovered. Interrupted temporary session data is cleared at startup and shutdown. No prompt is used for safe stale-state recovery.

## Logging verification

The following append-only logs are maintained under `Logs/`:

- `launcher.log`
- `backend.log`
- `frontend.log`
- `startup.log`
- `shutdown.log`

They record startup, shutdown, dependency and runtime errors, warnings, recovery, health restarts, GPU/CUDA diagnostics, and backend/frontend PIDs and readiness. Backend/frontend output is redirected into their respective append-mode files.

## Desktop shortcut verification

Verified on the actual Windows Desktop:

- `TaskGraph Robotics Workstation.cmd` — present and points to project `pythonw.exe`
- `TaskGraph Robotics Workstation.lnk` — present, targets project `pythonw.exe`, uses the project working directory, and applies `Assets/Branding/taskgraph.ico` when available

Shortcut creation is idempotent. Missing icon or COM shortcut creation failure is logged and does not prevent startup.

## Files added

- `Launcher/windows.py`
- `TaskGraph_v1.1.5_Launcher_Freeze_Report.md`
- Desktop `TaskGraph Robotics Workstation.lnk`

## Files modified

- `Launcher/browser_manager.py`
- `Launcher/desktop_shortcut.py`
- `Launcher/health_monitor.py`
- `Launcher/launcher.py`
- `Launcher/process_manager.py`
- `Launcher/runtime_state.py`
- `Launcher/splash.py`
- `Launcher/startup_checker.py`
- `Launcher/startup_recovery.py`
- Desktop `TaskGraph Robotics Workstation.cmd`

## Validation results

| Validation | Result | Evidence |
|---|---|---|
| Silent process policy | PASS | Windows flag probe: `CREATE_NO_WINDOW=True`, `SW_HIDE=0` |
| No launcher `cmd /c` or `shell=True` | PASS | Complete `Launcher/` subprocess audit |
| Backend direct silent start | PASS | Python/uvicorn argument list plus central hidden options |
| Frontend direct silent start | PASS | Node/Vite argument list; `npm.cmd` removed from launch path |
| Browser automatic open | PASS | Owned BrowserManager path and existing successful runtime log |
| Browser close detection | PASS | Existing launcher log records browser-close automatic shutdown |
| Backend/frontend shutdown | PASS | Wait, kill fallback, process-tree recovery paths verified |
| Workspace cleanup | PASS | `Tests.test_session_lifecycle` |
| Object Library preserved | PASS | Session lifecycle regression test |
| Launcher recovery | PASS | Instance/PID/port recovery audit |
| Desktop `.cmd` | PASS | Actual file verified on Desktop |
| Desktop branded `.lnk` | PASS | Actual 2,112-byte shortcut and icon verified |
| Launcher unit tests | PASS | 4/4 tests |
| Python compilation | PASS | All Launcher modules compiled |
| No orphan listeners | PASS | No listeners on 127.0.0.1:8000 or :5173 after validation |
| Append-only logging | PASS | File handlers and all runtime streams open in append mode |
| Splash responsiveness | PASS | Readiness loops pump Tk events at 150 ms intervals |

## Known limitations

- Windows decides foreground activation when Edge or Chrome opens. The launcher does not explicitly request focus changes, but the OS/browser may foreground the newly opened application window.
- The milestone requires the compatibility `.cmd` to exist. Directly double-clicking a `.cmd` is controlled by Windows Console Host and may briefly show a console; the production `.lnk` bypasses that file and launches `pythonw.exe` directly with the official icon.
- The monitor is a thread rather than a separate process, so its recorded PID is the launcher PID.

## Freeze recommendation

The production entry point is the branded `TaskGraph Robotics Workstation.lnk`. With direct hidden backend/frontend creation, browser-owned lifecycle, stale-runtime recovery, append-only diagnostics, friendly errors, and verified shutdown/port cleanup, the launcher is suitable for production use and should be frozen after v1.1.5. Future changes should require an exceptional launcher-specific defect or platform requirement.
