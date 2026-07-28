from __future__ import annotations
import shutil,subprocess,sys,time,urllib.request
from pathlib import Path
from .runtime_state import RuntimeState
from .windows import hidden_process_kwargs

def reachable(url:str,timeout:float=1)->bool:
    try:
        with urllib.request.urlopen(url,timeout=timeout) as response:return response.status<500
    except Exception:return False

class ProcessManager:
    def __init__(self,state:RuntimeState,log):self.state,self.log=state,log
    def _open_log(self,name:str):return (self.state.root/"Logs"/name).open("a",encoding="utf-8")
    def start_backend(self):
        stream=self._open_log("backend.log");self.state.backend=subprocess.Popen([str(self.state.python),"-m","uvicorn","api:app","--app-dir","Integration/WebAPI","--host","127.0.0.1","--port","8000"],cwd=self.state.root,stdout=stream,stderr=subprocess.STDOUT,**hidden_process_kwargs(True));self.state.track("backend",self.state.backend);self.log.info("backend pid=%s",self.state.backend.pid)
    def start_frontend(self):
        node=shutil.which("node.exe") or shutil.which("node");vite=self.state.webapp/"node_modules"/"vite"/"bin"/"vite.js"
        if not node:raise RuntimeError("Node.js is unavailable. Install Node.js LTS and retry.")
        if not vite.is_file():raise RuntimeError("Frontend dependencies are incomplete. Run npm install in WebApp once.")
        stream=self._open_log("frontend.log");self.state.frontend=subprocess.Popen([str(node),str(vite),"--host","127.0.0.1"],cwd=self.state.webapp,stdout=stream,stderr=subprocess.STDOUT,**hidden_process_kwargs(True));self.state.track("frontend",self.state.frontend);self.log.info("frontend pid=%s",self.state.frontend.pid)
    def wait_ready(self,process,url:str,label:str,timeout:int=60,pump=None):
        until=time.monotonic()+timeout
        while time.monotonic()<until:
            if process.poll() is not None:raise RuntimeError(f"{label} exited during startup")
            if reachable(url):self.state.mark(label.casefold(),health="healthy",state="ready");return
            if pump:pump()
            time.sleep(.15)
        raise TimeoutError(f"{label} did not become ready on {url}")
    def stop_process(self,process):
        if not process or process.poll() is not None:return
        process.terminate()
        try:process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            if sys.platform=="win32":subprocess.run(["taskkill","/PID",str(process.pid),"/T","/F"],capture_output=True,timeout=10,**hidden_process_kwargs())
            else:process.kill()
    def stop(self):
        self.state.stopping.set()
        for process in (self.state.frontend,self.state.backend):
            if process and process.poll() is None:process.terminate()
        for process in (self.state.frontend,self.state.backend):
            if process:
                try:process.wait(timeout=8)
                except subprocess.TimeoutExpired:process.kill()
        if sys.platform=="win32":
            for process in (self.state.frontend,self.state.backend):
                if process:subprocess.run(["taskkill","/PID",str(process.pid),"/T","/F"],capture_output=True,timeout=10,**hidden_process_kwargs())
        for name in ("frontend","backend"):self.state.mark(name,health="stopped",state="stopped")
