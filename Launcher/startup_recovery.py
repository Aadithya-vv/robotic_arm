from __future__ import annotations
import json,os,subprocess,sys
from pathlib import Path
from .windows import hidden_process_kwargs

class InstanceLock:
    def __init__(self,root:Path,log):self.root=root.resolve();self.path=root/".taskgraph-instance.json";self.log=log
    def recover(self):
        if self.path.is_file():
            try:data=json.loads(self.path.read_text(encoding="utf-8"))
            except Exception:data={}
            for key in ("launcher_pid","browser_pid","frontend_pid","backend_pid"):
                pid=int(data.get(key) or 0)
                if pid and pid!=os.getpid() and self._belongs_to_taskgraph(pid):self._terminate(pid);self.log.info("startup recovery terminated old %s=%s",key,pid)
            self.path.unlink(missing_ok=True)
        self.recover_ports()
    def recover_ports(self):
        if sys.platform!="win32":return
        result=subprocess.run(["netstat","-ano"],capture_output=True,text=True,timeout=8,**hidden_process_kwargs())
        for line in result.stdout.splitlines():
            columns=line.split()
            if len(columns)>=5 and columns[1] in ("127.0.0.1:8000","127.0.0.1:5173") and columns[3]=="LISTENING":
                pid=int(columns[4])
                if self._belongs_to_taskgraph(pid):self._terminate(pid);self.log.info("startup recovery released %s from TaskGraph pid=%s",columns[1],pid)
    def save(self,**pids):self.path.write_text(json.dumps({"launcher_pid":os.getpid(),**pids},indent=2),encoding="utf-8")
    def release(self):self.path.unlink(missing_ok=True)
    def _belongs_to_taskgraph(self,pid:int)->bool:
        if sys.platform!="win32":return True
        command=f"(Get-CimInstance Win32_Process -Filter \"ProcessId={pid}\").CommandLine"
        result=subprocess.run(["powershell.exe","-NoProfile","-NonInteractive","-WindowStyle","Hidden","-Command",command],capture_output=True,text=True,timeout=5,**hidden_process_kwargs())
        line=result.stdout.casefold();root=str(self.root).casefold()
        return bool(line and (root in line or "taskgraph-session" in line))
    @staticmethod
    def _terminate(pid:int):
        if sys.platform=="win32":subprocess.run(["taskkill","/PID",str(pid),"/T","/F"],capture_output=True,timeout=10,**hidden_process_kwargs())
        else:
            try:os.kill(pid,15)
            except ProcessLookupError:pass
