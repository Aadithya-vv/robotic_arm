"""TaskGraph v1.0.3 temporary-session lifecycle management.

This module owns filesystem hygiene only. It does not import or modify engines,
the Composition Root, APIs, or permanent Object Library knowledge.
"""
from __future__ import annotations

import shutil
from pathlib import Path

SESSION_DIRECTORIES = ("Workspace", ".taskgraph-session")
SESSION_FILES = ("Assets/TaskGraph_Runtime_Report.json",)
PERMANENT_LIBRARY = "Assets/ObjectLibrary"


def _inside(root: Path, target: Path) -> bool:
    try:
        target.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def clear_temporary_session(root: Path) -> tuple[str, ...]:
    """Remove allowlisted session artifacts and preserve permanent knowledge."""
    root = root.resolve()
    permanent = (root / PERMANENT_LIBRARY).resolve()
    removed: list[str] = []
    for relative in SESSION_DIRECTORIES:
        directory = (root / relative).resolve()
        if not _inside(root, directory) or directory == permanent:
            raise RuntimeError(f"unsafe session cleanup target: {directory}")
        if directory.is_dir():
            for child in tuple(directory.iterdir()):
                if child.resolve() == permanent:
                    continue
                if child.is_dir():
                    shutil.rmtree(child)
                else:
                    child.unlink()
                removed.append(str(child.relative_to(root)))
        directory.mkdir(parents=True, exist_ok=True)
    for relative in SESSION_FILES:
        target = (root / relative).resolve()
        if not _inside(root, target) or target == permanent:
            raise RuntimeError(f"unsafe session cleanup target: {target}")
        if target.is_file():
            target.unlink()
            removed.append(relative)
    return tuple(removed)
