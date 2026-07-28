from __future__ import annotations
import os,shutil,subprocess,sys
from pathlib import Path
from .windows import hidden_process_kwargs
URL="http://127.0.0.1:5173"

def find_browser()->Path|None:
    candidates=[]
    for variable in ("PROGRAMFILES(X86)","PROGRAMFILES","LOCALAPPDATA"):
        base=os.environ.get(variable)
        if base:
            candidates.extend((Path(base)/"Microsoft/Edge/Application/msedge.exe",Path(base)/"Google/Chrome/Application/chrome.exe"))
    for name in ("msedge.exe","chrome.exe"):
        found=shutil.which(name)
        if found:candidates.append(Path(found))
    return next((item for item in candidates if item.is_file()),None)

class BrowserManager:
    def __init__(self,root:Path,log):self.root,self.log,self.process=root,log,None
    def open(self):
        executable=find_browser()
        if executable is None:raise RuntimeError("Microsoft Edge or Google Chrome was not found for an owned browser session")
        profile=self.root/".taskgraph-session"/"browser-profile";profile.mkdir(parents=True,exist_ok=True)
        self.process=subprocess.Popen([str(executable),f"--app={URL}",f"--user-data-dir={profile}","--no-first-run","--disable-session-crashed-bubble"],**hidden_process_kwargs(True))
        self.log.info("browser opened pid=%s executable=%s",self.process.pid,executable);return self.process
    def closed(self)->bool:return bool(self.process and self.process.poll() is not None)
    def stop(self):
        if self.process and self.process.poll() is None:
            self.process.terminate()
            try:self.process.wait(timeout=8)
            except subprocess.TimeoutExpired:
                if sys.platform=="win32":subprocess.run(["taskkill","/PID",str(self.process.pid),"/T","/F"],capture_output=True,timeout=10,**hidden_process_kwargs())
                else:self.process.kill()
