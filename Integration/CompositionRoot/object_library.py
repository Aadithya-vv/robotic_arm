"""Permanent application object library mirrored through the ENG-006 public contract."""
from datetime import datetime
import json
from pathlib import Path
from types import MappingProxyType
from uuid import uuid4

from taskgraph_memory import MemoryRequest


SESSION_ID = "m2-object-library"


class ObjectLibrary:
    def __init__(self, memory, monitor, storage_path=None):
        self._memory = memory
        self._monitor = monitor
        self._storage_path = Path(storage_path or "Assets/ObjectLibrary/objects.json")
        self._items = {}

    def initialize(self):
        response = self._memory.create_session(MemoryRequest("object-library-create", "m2-object-library", "perception-integration"), SESSION_ID, "perception-integration")
        self._load()
        for object_id, value in self._items.items():
            self._memory.put(MemoryRequest(f"restore-{object_id}", "m2-object-library", "perception-integration"), SESSION_ID, object_id, value, provenance={"source": "disk", "release": "v0.4"})
        return response

    def create(self, fields, crop, descriptors=(), scene_context=None):
        if any(str(item.get("name", "")).casefold() == fields["name"].strip().casefold() for item in self.list()):
            raise ValueError("an object with this name already exists")
        object_id = f"user-object-{uuid4().hex[:12]}"
        value = {
            "object_id": object_id,
            "name": fields["name"].strip(), "category": fields.get("category", "").strip(),
            "type": fields.get("type", "").strip(), "material": fields.get("material", "").strip(),
            "color": fields.get("color", "").strip(), "weight": fields.get("weight", "").strip(),
            "description": fields.get("description", "").strip(), "tags": self._strings(fields.get("tags", "")),
            "notes": fields.get("notes", "").strip(), "created": fields.get("created") or datetime.now().isoformat(timespec="seconds"),
            "aliases": self._strings(fields.get("aliases", "")),
            "properties": self._mapping(fields.get("properties", {})), "metadata": self._mapping(fields.get("metadata", {})),
            "user_name": fields["name"].strip(), "ai_name": fields.get("ai_name", "").strip(),
            "thumbnail": MappingProxyType(dict(crop)), "gallery": (MappingProxyType(dict(crop)),), "original_image": MappingProxyType(dict(crop)), "crop": MappingProxyType(dict(crop)),
            "descriptors": tuple(descriptors), "recognition_history": (), "times_seen": 1, "average_confidence": float(fields.get("confidence", 0.0) or 0.0),
            "last_seen": fields.get("created") or datetime.now().isoformat(timespec="seconds"), "colors": fields.get("color", "").strip(),
            "histogram": next((values for name, values in descriptors if name == "color_histogram"), ()),
            "shape": next((values for name, values in descriptors if name == "geometry"), ()),
            "texture": next((values for name, values in descriptors if name == "appearance"), ()),
            "frames_seen": 1, "videos": tuple(filter(None, (fields.get("video"),))), "frames": tuple(filter(None, (crop.get("frame_id"),))),
            "relationships": tuple(scene_context or ()), "recognition_statistics": MappingProxyType({"matches": 0, "misses": 0}),
            "updated": datetime.now().isoformat(timespec="seconds"),
        }
        response = self._memory.put(MemoryRequest(f"store-{object_id}", "m2-object-library", "perception-integration"), SESSION_ID, object_id, value, provenance={"source": "user-capture", "release": "v0.2.1"})
        if response.status.value == "succeeded":
            self._items[object_id] = value; self._save()
        self._monitor.record("object", "created", response.status.value, object_id=object_id, name=value["name"])
        return response

    def list(self):
        return tuple(self._items[key] for key in sorted(self._items))

    def delete(self, object_id):
        response = self._memory.delete(MemoryRequest(f"delete-{object_id}", "m2-object-library", "perception-integration"), SESSION_ID, object_id)
        if response.status.value == "succeeded":
            self._items.pop(object_id, None); self._save()
        self._monitor.record("object", "deleted", response.status.value, object_id=object_id)
        return response

    def update(self, object_id, fields):
        current = next((item for item in self.list() if item["object_id"] == object_id), None)
        if current is None: raise KeyError(object_id)
        value = {**dict(current), **{key: str(fields[key]).strip() for key in ("name", "category", "description", "material", "color", "notes") if key in fields}}
        if not str(value.get("name", "")).strip(): raise ValueError("Object name is required")
        if any(item["object_id"] != object_id and str(item.get("name", "")).casefold() == value["name"].casefold() for item in self.list()):
            raise ValueError("an object with this name already exists")
        value["user_name"] = value["name"]; value["tags"] = tuple(item.strip() for item in fields.get("tags", "").split(",") if item.strip()); value["aliases"] = tuple(item.strip() for item in fields.get("aliases", "").split(",") if item.strip())
        if "tags" not in fields: value["tags"] = current.get("tags", ())
        if "aliases" not in fields: value["aliases"] = current.get("aliases", ())
        if "properties" in fields: value["properties"] = self._mapping(fields["properties"])
        if "metadata" in fields: value["metadata"] = self._mapping(fields["metadata"])
        value["colors"] = value.get("color", "")
        value["updated"] = datetime.now().isoformat(timespec="seconds")
        response = self._memory.put(MemoryRequest(f"update-{object_id}", "m2-object-library", "perception-integration"), SESSION_ID, object_id, value, provenance={"source": "user-edit", "release": "v0.4"})
        if response.status.value == "succeeded":
            self._items[object_id] = value; self._save()
        return response

    def replace_capture(self, object_id, crop, confidence=0.0):
        current = next((item for item in self.list() if item["object_id"] == object_id), None)
        if current is None: raise KeyError(object_id)
        frozen_crop = MappingProxyType(dict(crop)); now = datetime.now().isoformat(timespec="seconds")
        value = {**dict(current), "thumbnail": frozen_crop, "gallery": (frozen_crop,), "original_image": frozen_crop, "crop": frozen_crop,
                 "average_confidence": float(confidence or 0.0), "frames": (crop.get("frame_id"),), "updated": now, "last_seen": now}
        response = self._memory.put(MemoryRequest(f"recapture-{object_id}", "m2-object-library", "perception-integration"), SESSION_ID, object_id, value, provenance={"source": "cluster-regeneration", "release": "v0.4"})
        if response.status.value == "succeeded":
            self._items[object_id] = value; self._save()
        return response

    @classmethod
    def _strings(cls, value):
        values = value if isinstance(value, (tuple, list)) else str(value or "").split(",")
        return tuple(str(item).strip() for item in values if str(item).strip())

    @classmethod
    def _mapping(cls, value):
        if value is None: return MappingProxyType({})
        if not hasattr(value, "items"): raise ValueError("properties and metadata must be objects")
        return MappingProxyType({str(key): cls._freeze(item) for key, item in value.items()})

    def record_recognition(self, object_id, confidence, ai_name=None):
        current = next((item for item in self.list() if item["object_id"] == object_id), None)
        if current is None: return None
        count = int(current.get("times_seen", 1)); average = float(current.get("average_confidence", 0.0)); now = datetime.now().isoformat(timespec="seconds")
        history = tuple(current.get("recognition_history", ())) + ({"timestamp": now, "confidence": confidence, "ai_name": ai_name},)
        value = {**dict(current), "times_seen": count+1, "frames_seen": count+1, "average_confidence": (average*count+confidence)/(count+1), "last_seen": now, "recognition_history": history[-100:], "ai_name": ai_name or current.get("ai_name", ""), "recognition_statistics": {"matches": int(current.get("recognition_statistics", {}).get("matches", 0))+1, "misses": int(current.get("recognition_statistics", {}).get("misses", 0))}}
        response = self._memory.put(MemoryRequest(f"recognize-{object_id}-{count+1}", "m2-object-library", "perception-integration"), SESSION_ID, object_id, value, provenance={"source":"descriptor-recognition","release":"v0.4"})
        if response.status.value == "succeeded":
            self._items[object_id] = value; self._save()
        return response

    def _load(self):
        if not self._storage_path.is_file(): return
        payload = json.loads(self._storage_path.read_text(encoding="utf-8"))
        self._items = {item["object_id"]: self._freeze(item) for item in payload.get("objects", ())}

    def _save(self):
        self._storage_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"version": "TaskGraph v0.4", "objects": [self._plain(item) for item in self.list()]}
        temporary = self._storage_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        temporary.replace(self._storage_path)

    @classmethod
    def _freeze(cls, value):
        if isinstance(value, dict): return MappingProxyType({key: cls._freeze(item) for key, item in value.items()})
        if isinstance(value, list): return tuple(cls._freeze(item) for item in value)
        return value

    @classmethod
    def _plain(cls, value):
        if hasattr(value, "items"): return {str(key): cls._plain(item) for key, item in value.items()}
        if isinstance(value, (tuple, list)): return [cls._plain(item) for item in value]
        return value
