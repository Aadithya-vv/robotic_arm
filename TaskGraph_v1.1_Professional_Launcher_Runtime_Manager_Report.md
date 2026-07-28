# TaskGraph v1.1 Professional Launcher & Runtime Manager Report

## 1. Objective achieved

`run_taskgraph.py` is now a minimal entry point into a dedicated professional launcher package. The launcher owns verification, splash/status UX, backend and frontend processes, readiness checks, browser automation, monitoring, logging, shutdown, session cleanup, and shortcut creation.

## 2. Launcher architecture

`Launcher/launcher.py` orchestrates focused modules: runtime state, startup checker, process manager, health monitor, browser manager, splash, desktop shortcut, and logging. Engines and application pipelines are not imported into this layer.

## 3. Virtual environment verification

The backend command always begins with the resolved `<project>/.venv/Scripts/python.exe`. It never uses `sys.executable`, `python`, `py`, or PATH Python. Heavy diagnostics are executed in a child project-venv process that returns JSON. The launcher interpreter never imports Torch or Ultralytics.

Validated environment: Python 3.13.7, Torch 2.11.0+cu128, CUDA available, NVIDIA GeForce RTX 3050 Laptop GPU, Ultralytics 8.4.95.

## 4. Startup pipeline

The launcher configures logs, cleans the temporary session, verifies project/venv/Node/npm/models/frontend/workspace/Object Library, runs venv diagnostics, attempts shortcut creation, starts FastAPI, waits for `/health`, starts Vite, waits for HTTP readiness, starts monitoring, and opens the workstation URL.

Failures are translated into a reason and suggested solution, logged with traceback, and shut down cleanly.

## 5. Splash screen

A dark Tk splash displays TaskGraph Robotics Workstation v1.1, progress, current phase, GPU details, CUDA state, and ready PIDs. It remains as a compact runtime manager; closing it asks for shutdown confirmation. Headless environments fall back to log-driven operation.

## 6. Backend supervisor

FastAPI starts exclusively through `.venv/Scripts/python.exe -m uvicorn`. Output is appended to `Logs/backend.log`. Startup waits for the health endpoint. The monitor restarts only the backend when its process exits or health becomes unavailable.

## 7. Frontend supervisor

Vite starts with the resolved npm executable in `WebApp/`. Output is appended to `Logs/frontend.log`. Startup waits for port 5173. The monitor restarts only the frontend when its process or HTTP readiness fails.

## 8. Browser automation

After both services are ready, the default browser opens `http://127.0.0.1:5173` with reuse semantics (`new=0`). Browser startup does not own or terminate application processes.

## 9. Health monitor

A daemon monitor checks backend health and frontend reachability every five seconds. Failures are isolated and restart counters are stored in runtime state. Backend health covers the registered runtime/worker health projection; CUDA diagnostics are verified before startup.

## 10. Logging

The launcher creates/appends:

- `Logs/launcher.log`
- `Logs/backend.log`
- `Logs/frontend.log`
- `Logs/startup.log`
- `Logs/shutdown.log`

Unexpected failures include full tracebacks in the launcher log.

## 11. Shutdown workflow

Closing the launcher window displays “TaskGraph is still running” with Shutdown/Cancel behavior. Confirmation terminates frontend, then backend, waits up to eight seconds, force-stops only if required, cleans session artifacts, appends shutdown evidence, and exits. Closing only the browser leaves TaskGraph running.

## 12. Desktop shortcut

On Windows the launcher creates `TaskGraph Robotics Workstation.cmd` on the current user's Desktop. It changes to the project directory and starts the entry point with project `.venv/Scripts/pythonw.exe`. Shortcut permission failures are logged and do not prevent startup.

## 13. Files added

- `Launcher/__init__.py`
- `Launcher/launcher.py`
- `Launcher/process_manager.py`
- `Launcher/health_monitor.py`
- `Launcher/startup_checker.py`
- `Launcher/browser_manager.py`
- `Launcher/logger.py`
- `Launcher/splash.py`
- `Launcher/desktop_shortcut.py`
- `Launcher/runtime_state.py`
- `Tests/test_launcher.py`
- This report

## 14. Files modified

- `run_taskgraph.py`, reduced to a four-line entry point.

## 15. Validation results

| Check | Result |
|---|---|
| Project venv path selection | PASS |
| Global Python ignored for backend | PASS |
| Heavy diagnostics isolated in venv child | PASS |
| Torch/CUDA/Ultralytics/FastAPI verification | PASS |
| CUDA/GPU detection | PASS |
| Friendly missing-venv behavior | PASS |
| Health reachability failure handling | PASS |
| Session cleanup/Object Library preservation | PASS |
| Launcher module syntax | PASS |
| Launcher and lifecycle unit tests | PASS — 4 tests |
| Required log creation | PASS |
| Full graphical startup/browser | NOT RUN — would open GUI and long-running services |
| Crash recovery | VERIFIED BY CODE; destructive process-crash test not run |
| Desktop shortcut creation | VERIFIED BY CODE; Desktop write occurs on real launch |

## 16. Remaining limitations

- Browsers do not provide a portable standard callback when a particular tab closes. Closing the browser therefore leaves TaskGraph running as required; shutdown confirmation is provided by closing the launcher runtime window.
- WebSocket health is represented by backend health and frontend reachability. A protocol-level authenticated WebSocket probe was not added because current sockets have no dedicated health contract.
- Node/npm still resolve from PATH, as the project contains no bundled Node runtime. The no-global-runtime rule is enforced for Python and AI dependencies.
- A hard power loss or forced launcher kill cannot execute shutdown handlers; retained v1.0.3 startup cleanup recovers on the next launch.

## 17. Freeze recommendation

Freeze the launcher/runtime layer after one manual desktop acceptance pass covering splash rendering, port-conflict dialog, shortcut creation, browser reuse, individual process restart, and confirmed shutdown. The modular boundaries and automated checks are suitable for later packaging into an executable without changing TaskGraph engines.
