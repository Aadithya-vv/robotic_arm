from __future__ import annotations
import os,traceback
from pathlib import Path
from session_lifecycle import clear_temporary_session
from .browser_manager import BrowserManager
from .desktop_shortcut import ensure_shortcut
from .health_monitor import HealthMonitor
from .logger import append,configure
from .process_manager import ProcessManager
from .runtime_state import RuntimeState
from .splash import Splash
from .startup_checker import StartupError,verify
from .startup_recovery import InstanceLock

ROOT=Path(__file__).resolve().parents[1]

def main()->int:
    state=RuntimeState(ROOT);log=configure(ROOT);manager=ProcessManager(state,log);browser=BrowserManager(ROOT,log);lock=InstanceLock(ROOT,log)
    state.processes["launcher"]={"pid":os.getpid(),"start_time":"current","health":"healthy","restart_count":0,"state":"running"}
    try:splash=Splash(state.version,ROOT)
    except Exception:
        log.exception("splash initialization failed");splash=None
    def status(label:str,value:int,detail:str=""):
        log.info("startup: %s %s",label,detail)
        if splash:splash.update(label,value,detail)
    try:
        status("Recovering previous runtime",2);lock.recover()
        status("Cleaning temporary session",5);removed=clear_temporary_session(ROOT);append(ROOT,"startup.log",f"session cleanup removed {len(removed)} artifacts")
        status("Checking Object Library",7);library=ROOT/"Assets"/"ObjectLibrary";library.mkdir(parents=True,exist_ok=True)
        completed=0
        def checked(label:str,passed:bool):
            nonlocal completed;completed+=1;status(f"{'✓' if passed else '!' } {label}",min(55,8+completed*4))
        diagnostics=verify(state,checked);state.diagnostics=diagnostics;status("Environment verified",58,f"{diagnostics.get('gpu')} · CUDA {'Ready' if diagnostics.get('cuda') else 'Unavailable'}")
        if splash:splash.telemetry(GPU=diagnostics.get("gpu") or "Unavailable",CUDA="Ready" if diagnostics.get("cuda") else "Unavailable",Logs="Append-only · Ready")
        try:shortcut=ensure_shortcut(ROOT,log);log.info("desktop shortcut: %s",shortcut)
        except OSError:log.exception("desktop shortcut could not be created; continuing")
        status("Starting backend",65);manager.start_backend();
        if splash:splash.telemetry(Backend="Starting")
        manager.wait_ready(state.backend,"http://127.0.0.1:8000/health","Backend",pump=splash.pump if splash else None);status("✓ Backend ready",76,f"PID {state.backend.pid}")
        if splash:splash.telemetry(Backend=f"Ready · PID {state.backend.pid}")
        status("Starting frontend",80);manager.start_frontend();
        if splash:splash.telemetry(Frontend="Starting")
        manager.wait_ready(state.frontend,"http://127.0.0.1:5173","Frontend",pump=splash.pump if splash else None);status("✓ Frontend ready",90,f"PID {state.frontend.pid}")
        if splash:splash.telemetry(Frontend=f"Ready · PID {state.frontend.pid}")
        monitor=HealthMonitor(manager);monitor.start();state.processes["monitor"]={"pid":os.getpid(),"start_time":"current","health":"healthy","restart_count":0,"state":"running"};status("Opening browser",95)
        state.browser=browser.open();lock.save(backend_pid=state.backend.pid,frontend_pid=state.frontend.pid,browser_pid=state.browser.pid)
        state.track("browser",state.browser);state.mark("browser",health="healthy",state="ready")
        if splash:splash.telemetry(Browser=f"Open · PID {state.browser.pid}")
        status("Ready",100,f"GPU: {diagnostics.get('gpu')} · Backend {state.backend.pid} · Frontend {state.frontend.pid}")
        append(ROOT,"startup.log","TaskGraph ready")
        if splash:
            def close():
                if splash.confirm_shutdown():splash.root.quit()
            def watch_browser():
                if browser.closed():
                    log.info("browser closed pid=%s; automatic shutdown",state.browser.pid);splash.root.quit();return
                splash.root.after(750,watch_browser)
            splash.root.protocol("WM_DELETE_WINDOW",close);splash.root.after(750,watch_browser);splash.root.mainloop()
        else:
            while not browser.closed() and state.backend.poll() is None and state.frontend.poll() is None:state.stopping.wait(1)
            if browser.closed():log.info("browser closed pid=%s; automatic shutdown",state.browser.pid)
        return 0
    except StartupError as exc:
        log.exception("startup verification failed");append(ROOT,"startup.log",f"FAILED {exc.reason}")
        if splash:splash.error("Unable to start TaskGraph",exc.reason,exc.solution)
        return 2
    except (OSError,RuntimeError,TimeoutError) as exc:
        raw=str(exc);lower=raw.casefold()
        if "backend" in lower:reason="The TaskGraph backend could not start.";solution="Check Logs/backend.log and verify port 8000 is available."
        elif "frontend" in lower or "node" in lower:reason="The TaskGraph frontend could not start.";solution="Install Node.js LTS, run npm install in WebApp once, and verify port 5173 is available."
        elif "browser" in lower or "chrome" in lower or "edge" in lower:reason="A supported browser could not be opened.";solution="Install Microsoft Edge or Google Chrome and retry."
        elif "address" in lower or "port" in lower:reason="A required TaskGraph port is occupied.";solution="Close the application using ports 8000 or 5173, then retry."
        else:reason="TaskGraph could not complete startup.";solution="Review Logs/launcher.log for details, correct the reported environment issue, and retry."
        log.exception("runtime startup failed: %s",raw);append(ROOT,"startup.log",f"FAILED {reason}")
        if splash:splash.error("Unable to start TaskGraph",reason,solution)
        return 3
    except KeyboardInterrupt:return 0
    except Exception as exc:
        log.error("unexpected launcher failure\n%s",traceback.format_exc())
        if splash:splash.error("TaskGraph Launcher Error",str(exc),"Review Logs/launcher.log, repair the reported dependency, and retry.")
        return 4
    finally:
        append(ROOT,"shutdown.log","shutdown started");log.info("shutdown started");browser.stop();manager.stop();lock.recover_ports()
        try:
            removed=clear_temporary_session(ROOT);append(ROOT,"shutdown.log",f"session cleanup removed {len(removed)} artifacts")
        except Exception:log.exception("shutdown session cleanup failed")
        lock.release();append(ROOT,"shutdown.log","shutdown complete");log.info("shutdown completed")
        if splash:
            try:splash.destroy()
            except Exception:pass
