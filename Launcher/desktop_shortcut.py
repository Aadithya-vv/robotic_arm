from __future__ import annotations
import ctypes,os,subprocess,sys
from pathlib import Path
from .windows import hidden_process_kwargs

APP_NAME="TaskGraph"
LEGACY_SHORTCUTS=("TaskGraph Robotics Workstation.lnk","TaskGraph Robotics Workstation.cmd","TaskGraph.cmd")

def detect_desktop()->Path:
    if sys.platform=="win32":
        try:
            import winreg
            key=winreg.OpenKey(winreg.HKEY_CURRENT_USER,r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders")
            value,_=winreg.QueryValueEx(key,"Desktop");desktop=Path(os.path.expandvars(value))
            if desktop.is_dir():return desktop
        except OSError:pass
        buffer=ctypes.create_unicode_buffer(260)
        if ctypes.windll.shell32.SHGetFolderPathW(None,0x10,None,0,buffer)==0:
            desktop=Path(buffer.value)
            if desktop.is_dir():return desktop
        for variable in ("OneDrive","USERPROFILE"):
            base=os.environ.get(variable)
            if base and (Path(base)/"Desktop").is_dir():return Path(base)/"Desktop"
    desktop=Path.home()/"Desktop"
    if not desktop.is_dir():raise OSError("Windows Desktop directory could not be detected")
    return desktop

def ensure_shortcut(root:Path,log=None)->Path:
    """Reconcile the Desktop to one branded TaskGraph.lnk shortcut."""
    desktop=detect_desktop();link=desktop/f"{APP_NAME}.lnk"
    if log:log.info("Desktop detected: %s",desktop)
    for name in LEGACY_SHORTCUTS:
        legacy=desktop/name
        if legacy.is_file():
            legacy.unlink()
            if log:log.info("Removed legacy desktop shortcut: %s",legacy)
    executable=root/"TaskGraph.exe"
    pythonw=root/".venv"/"Scripts"/"pythonw.exe"
    script=root/"run_taskgraph.py"
    icon=root/"Assets"/"Branding"/"taskgraph.ico"
    if sys.platform!="win32":return link
    target=executable if executable.is_file() else pythonw
    arguments="" if executable.is_file() else f'"{script}"'
    if not target.is_file():raise OSError(f"TaskGraph launcher target was not found: {target}")
    escape=lambda value:str(value).replace("'","''")
    command=f"$s=(New-Object -ComObject WScript.Shell).CreateShortcut('{escape(link)}');$s.TargetPath='{escape(target)}';$s.Arguments='{escape(arguments)}';$s.WorkingDirectory='{escape(root)}';$s.Description='{APP_NAME}';"
    if icon.is_file():command+=f"$s.IconLocation='{escape(icon)},0';"
    command+="$s.Save()"
    try:subprocess.run(["powershell.exe","-NoProfile","-NonInteractive","-WindowStyle","Hidden","-Command",command],capture_output=True,text=True,timeout=15,check=True,**hidden_process_kwargs())
    except (OSError,subprocess.SubprocessError) as exc:
        if log:log.warning("Desktop .lnk creation skipped: %s",exc)
        raise OSError("TaskGraph desktop shortcut could not be created") from exc
    if log:log.info("Desktop shortcut ready: %s -> %s",link,target)
    return link
