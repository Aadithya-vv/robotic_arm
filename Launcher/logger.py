from __future__ import annotations
import logging
from datetime import datetime
from pathlib import Path

def configure(root:Path)->logging.Logger:
    folder=root/"Logs";folder.mkdir(parents=True,exist_ok=True)
    log=logging.getLogger("taskgraph.launcher");log.setLevel(logging.INFO)
    if not log.handlers:
        handler=logging.FileHandler(folder/"launcher.log",encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"));log.addHandler(handler)
    stamp=datetime.now().isoformat(timespec="seconds")
    for name in ("startup.log","shutdown.log","backend.log","frontend.log"):(folder/name).touch()
    log.info("startup requested %s",stamp);return log

def append(root:Path,name:str,message:str)->None:
    with (root/"Logs"/name).open("a",encoding="utf-8") as stream:stream.write(f"{datetime.now().isoformat(timespec='seconds')} {message}\n")
