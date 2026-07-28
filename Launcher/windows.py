"""Windows process options shared by launcher-owned background commands."""
from __future__ import annotations
import subprocess,sys

def hidden_process_kwargs(new_group:bool=False)->dict:
    if sys.platform!="win32":return {}
    startup=subprocess.STARTUPINFO();startup.dwFlags|=subprocess.STARTF_USESHOWWINDOW;startup.wShowWindow=subprocess.SW_HIDE
    flags=subprocess.CREATE_NO_WINDOW
    if new_group:flags|=subprocess.CREATE_NEW_PROCESS_GROUP
    return {"startupinfo":startup,"creationflags":flags}
