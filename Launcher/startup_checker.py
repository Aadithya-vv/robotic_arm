from __future__ import annotations
import json,shutil,subprocess
from pathlib import Path
from .runtime_state import RuntimeState
from .windows import hidden_process_kwargs

PROBE="""import json,sys
result={'python':sys.version.split()[0]}
for name in ('fastapi','uvicorn','torch','ultralytics'):
 try:
  module=__import__(name);result[name]=getattr(module,'__version__','installed')
 except Exception as exc:result[name]=None;result[name+'_error']=str(exc)
try:
 import torch;result['cuda']=torch.cuda.is_available();result['gpu']=torch.cuda.get_device_name(0) if result['cuda'] else 'CPU'
except Exception:result['cuda']=False;result['gpu']='Unavailable'
print(json.dumps(result))"""

class StartupError(RuntimeError):
    def __init__(self,reason:str,solution:str):super().__init__(reason);self.reason=reason;self.solution=solution

def verify(state:RuntimeState,progress=lambda *_:None)->dict:
    root=state.root
    checks=[("Project Found",root.is_dir(),"Restore the TaskGraph project folder."),("Virtual Environment",state.python.is_file(),"Create .venv and install project requirements."),("Node",bool(shutil.which('node')),"Install Node.js LTS."),("npm",bool(shutil.which('npm.cmd') or shutil.which('npm')),"Install npm with Node.js."),("YOLO Models",any((root/'Models').glob('*.pt')),"Add a verified YOLO model under Models/."),("Frontend Dependencies",(state.webapp/'node_modules'/'react').is_dir(),"Run npm install in WebApp once."),("Workspace",(root/'Workspace').is_dir(),"Allow TaskGraph to create Workspace/."),("Object Library",(root/'Assets'/'ObjectLibrary').is_dir(),"Restore Assets/ObjectLibrary/." )]
    for label,passed,solution in checks:
        progress(label,passed)
        if not passed:raise StartupError(label,solution)
    try:result=subprocess.run([str(state.python),"-c",PROBE],cwd=root,capture_output=True,text=True,timeout=45,check=True,**hidden_process_kwargs())
    except Exception as exc:raise StartupError(f"Virtual environment diagnostic failed: {exc}","Repair .venv or reinstall backend requirements.") from exc
    try:diagnostics=json.loads(result.stdout.strip().splitlines()[-1])
    except Exception as exc:raise StartupError("Invalid environment diagnostic response","Repair the project virtual environment.") from exc
    for dependency in ("fastapi","uvicorn","torch","ultralytics"):
        passed=bool(diagnostics.get(dependency));progress(dependency.title(),passed)
        if not passed:raise StartupError(f"Missing {dependency} in project .venv",f"Install {dependency} using .venv\\Scripts\\python.exe -m pip.")
    progress("CUDA",bool(diagnostics.get("cuda")));state.diagnostics=diagnostics;return diagnostics
