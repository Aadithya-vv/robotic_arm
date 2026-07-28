"""Persistent scene and timeline state owned by the Action Builder."""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from threading import RLock
from datetime import datetime
from uuid import uuid4


class ActionBuilderStore:
    def __init__(self, path):
        self.path = Path(path)
        self._lock = RLock()

    def load(self):
        with self._lock:
            if not self.path.is_file():
                return {"version": 1, "scene_objects": [], "timeline": [], "playhead": 0, "snap": True}
            value = json.loads(self.path.read_text(encoding="utf-8"))
            return self._validate(value)

    def save(self, value):
        state = self._validate(value)
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.path.with_suffix(".tmp")
            temporary.write_text(json.dumps(state, indent=2), encoding="utf-8")
            temporary.replace(self.path)
        return state

    @staticmethod
    def _validate(value):
        if not isinstance(value, dict): raise ValueError("Action Builder state must be an object")
        scene = value.get("scene_objects", []); timeline = value.get("timeline", [])
        if not isinstance(scene, list) or not isinstance(timeline, list): raise ValueError("Scene and timeline must be arrays")
        scene = [{"id": str(item.get("id", "")), "objectId": str(item.get("objectId", "")),
                  "position": [float((item.get("position") or [0,0])[0]), float((item.get("position") or [0,0])[1])],
                  "rotationAngle": float(item.get("rotationAngle", 0)),
                  **({"label": str(item["label"])} if item.get("label") else {})} for item in scene]
        timeline = [{"objectId": str(item.get("objectId", "")), "positionX": float(item.get("positionX", 0)), "positionY": float(item.get("positionY", 0)),
                     "rotationAngle": float(item.get("rotationAngle", 0)), "timestamp": max(0, float(item.get("timestamp", 0)))} for item in timeline]
        return {"version": 1, "scene_objects": scene, "timeline": timeline,
                "playhead": max(0, float(value.get("playhead", 0))), "snap": bool(value.get("snap", True))}


class ActionLibraryStore:
    """Project action assets, stored as one atomic ``.action`` file per action."""

    def __init__(self, directory):
        self.directory = Path(directory); self._lock = RLock()

    def list(self):
        with self._lock:
            if not self.directory.is_dir(): return []
            actions = [self._read(path) for path in self.directory.glob("*.action")]
            return sorted(actions, key=lambda item: item["updatedAt"], reverse=True)

    def get(self, action_id):
        with self._lock:
            path = self._path(action_id)
            if not path.is_file(): raise KeyError(action_id)
            return self._read(path)

    def create(self, fields, scene, keyframes, preview_data=None, preview_extension=".webm"):
        name = str(fields.get("name", "")).strip()
        if not name: raise ValueError("Action name is required")
        now = datetime.now().isoformat(timespec="seconds")
        clean_keyframes = [{"timestamp": max(0,float(item.get("timestamp",0))), "objectId": str(item.get("objectId","")),
                            "positionX": float(item.get("positionX",0)), "positionY": float(item.get("positionY",0)), "rotationAngle": float(item.get("rotationAngle",0))} for item in keyframes]
        action_id = f"action-{uuid4().hex[:12]}"
        preview_video = self._save_preview(action_id, preview_data, preview_extension)
        value = {"id": action_id, "name": name,
                 "description": str(fields.get("description", "")).strip(), "category": str(fields.get("category", "")).strip(),
                 "estimatedDuration": max(0, float(fields.get("estimatedDuration", 0) or 0)),
                 "previewVideo": preview_video,
                 "tags": [str(item).strip() for item in fields.get("tags", []) if str(item).strip()],
                 "createdAt": now, "updatedAt": now, "referencedObjects": list(dict.fromkeys(str(item.get("objectId","")) for item in scene if item.get("objectId"))),
                 "scene_objects": ActionBuilderStore._validate({"scene_objects": scene, "timeline": []})["scene_objects"], "keyframes": clean_keyframes}
        with self._lock:
            try:
                self._write(value)
            except Exception:
                shutil.rmtree(self._asset_directory(action_id), ignore_errors=True)
                raise
        return value

    def update(self, action_id, fields):
        with self._lock:
            current = self.get(action_id)
            for key in ("name", "description", "category"):
                if key in fields: current[key] = str(fields[key]).strip()
            if not current.get("name"): raise ValueError("Action name is required")
            if "estimatedDuration" in fields: current["estimatedDuration"] = max(0, float(fields["estimatedDuration"] or 0))
            if "tags" in fields: current["tags"] = [str(item).strip() for item in fields["tags"] if str(item).strip()]
            current["updatedAt"] = datetime.now().isoformat(timespec="seconds"); self._write(current); return current

    def delete(self, action_id):
        with self._lock:
            path = self._path(action_id)
            if not path.is_file(): raise KeyError(action_id)
            path.unlink()
            shutil.rmtree(self._asset_directory(action_id), ignore_errors=True)

    def preview_path(self, action_id):
        """Resolve an action-owned preview without accepting arbitrary file paths."""
        action = self.get(action_id)
        if not action.get("previewVideo"):
            raise KeyError(action_id)
        directory = self._asset_directory(action_id)
        previews = sorted(directory.glob("preview.*"))
        if not previews or not previews[0].is_file():
            raise KeyError(action_id)
        return previews[0]

    def _save_preview(self, action_id, preview_data, preview_extension):
        if not isinstance(preview_data, (bytes, bytearray)) or not preview_data:
            raise ValueError("Action Builder did not generate a preview recording")
        suffix = str(preview_extension).lower()
        if suffix not in {".mp4", ".webm"}:
            suffix = ".webm"
        directory = self._asset_directory(action_id)
        directory.mkdir(parents=True, exist_ok=False)
        target = directory / f"preview{suffix}"
        target.write_bytes(preview_data)
        return f"/action-assets/{action_id}/{target.name}"

    def _asset_directory(self, action_id):
        return self.directory / str(action_id)

    def _path(self, action_id):
        if not action_id or any(char not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_" for char in str(action_id)):
            raise KeyError(action_id)
        return self.directory / f"{action_id}.action"

    def _read(self, path):
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict): raise ValueError(f"Invalid action asset: {path.name}")
        return self._normalize(value)

    def _write(self, action):
        self.directory.mkdir(parents=True, exist_ok=True)
        path = self._path(action["id"]); temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps({"version": 1, **action}, indent=2), encoding="utf-8"); temporary.replace(path)

    @staticmethod
    def _normalize(item):
        created = str(item.get("createdAt", item.get("created", "")))
        frames = [{"timestamp": max(0,float(frame.get("timestamp",0))), "objectId": str(frame.get("objectId","")),
                   "positionX": float(frame.get("positionX",(frame.get("position") or [0,0])[0])),
                   "positionY": float(frame.get("positionY",(frame.get("position") or [0,0])[1])),
                   "rotationAngle": float(frame.get("rotationAngle",frame.get("rotationX",0)))} for frame in item.get("keyframes",[])]
        references = item.get("referencedObjects") or list(dict.fromkeys(str(value.get("objectId","")) for value in item.get("scene_objects",[]) if value.get("objectId")))
        scene = ActionBuilderStore._validate({"scene_objects": item.get("scene_objects", []), "timeline": []})["scene_objects"]
        return {"id":str(item.get("id","")),"name":str(item.get("name","")),"description":str(item.get("description","")),"category":str(item.get("category","")),
                "estimatedDuration":float(item.get("estimatedDuration",item.get("estimated_duration",0)) or 0),"tags":list(item.get("tags",[])),"previewVideo":item.get("previewVideo"),
                "createdAt":created,"updatedAt":str(item.get("updatedAt",item.get("updated",created))),"referencedObjects":references,"scene_objects":scene,"keyframes":frames}
