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
        self._categories = {}

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
            "version": 1,
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
            "frames_seen": len(crop.get("source_frames", ())) or 1, "videos": tuple(filter(None, (fields.get("video"),))), "frames": tuple(filter(None, (crop.get("frame_id"),))),
            "relationships": tuple(scene_context or ()), "recognition_statistics": MappingProxyType({"matches": 0, "misses": 0}),
            "updated": datetime.now().isoformat(timespec="seconds"),
        }
        response = self._memory.put(MemoryRequest(f"store-{object_id}", "m2-object-library", "perception-integration"), SESSION_ID, object_id, value, provenance={"source": "user-capture", "release": "v0.2.1"})
        if response.status.value == "succeeded":
            self._items[object_id] = value
            self._ensure_category(value.get("category", ""))
            self._save()
        self._monitor.record("object", "created", response.status.value, object_id=object_id, name=value["name"])
        return response

    def list(self):
        return tuple(self._items[key] for key in sorted(self._items))

    def categories(self):
        return tuple(self._categories[key] for key in sorted(self._categories, key=lambda item: self._categories[item]["name"].casefold()))

    def create_category(self, name):
        value = str(name or "").strip()
        if not value: raise ValueError("Category name is required")
        if any(item["name"].casefold() == value.casefold() for item in self.categories()):
            raise ValueError("A category with this name already exists")
        category_id = f"category-{uuid4().hex[:12]}"
        now = datetime.now().isoformat(timespec="seconds")
        self._categories[category_id] = {"category_id": category_id, "name": value, "created": now, "updated": now}
        self._save()
        return self._categories[category_id]

    def rename_category(self, category_id, name):
        if category_id not in self._categories: raise KeyError(category_id)
        value = str(name or "").strip()
        if not value: raise ValueError("Category name is required")
        if any(key != category_id and item["name"].casefold() == value.casefold() for key, item in self._categories.items()):
            raise ValueError("A category with this name already exists")
        previous = self._categories[category_id]["name"]
        now = datetime.now().isoformat(timespec="seconds")
        self._categories[category_id] = {**self._categories[category_id], "name": value, "updated": now}
        for object_id, current in tuple(self._items.items()):
            if str(current.get("category", "")).casefold() == previous.casefold():
                self._items[object_id] = {**dict(current), "category": value, "version": int(current.get("version", 1)) + 1, "updated": now}
        self._save()
        return self._categories[category_id]

    def delete_category(self, category_id, replacement=""):
        if category_id not in self._categories: raise KeyError(category_id)
        current = self._categories[category_id]
        members = [item for item in self.list() if str(item.get("category", "")).casefold() == current["name"].casefold()]
        target = str(replacement or "").strip()
        if members and not target: raise ValueError("Move category objects before deleting this category")
        if target and not any(item["name"].casefold() == target.casefold() for item in self.categories()):
            raise ValueError("Replacement category does not exist")
        now = datetime.now().isoformat(timespec="seconds")
        for item in members:
            self._items[item["object_id"]] = {**dict(item), "category": target, "version": int(item.get("version", 1)) + 1, "updated": now}
        self._categories.pop(category_id)
        self._save()

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
        value["version"] = int(current.get("version", 1)) + 1
        response = self._memory.put(MemoryRequest(f"update-{object_id}", "m2-object-library", "perception-integration"), SESSION_ID, object_id, value, provenance={"source": "user-edit", "release": "v0.4"})
        if response.status.value == "succeeded":
            self._items[object_id] = value
            self._ensure_category(value.get("category", ""))
            self._save()
        return response

    def replace_capture(self, object_id, crop, confidence=0.0, fields=None):
        current = next((item for item in self.list() if item["object_id"] == object_id), None)
        if current is None: raise KeyError(object_id)
        frozen_crop = MappingProxyType(dict(crop)); now = datetime.now().isoformat(timespec="seconds")
        fields = fields or {}
        editable = {key: fields[key] for key in ("name", "category", "description", "material", "color", "notes", "properties", "metadata") if key in fields}
        value = {**dict(current), **editable, "thumbnail": frozen_crop, "gallery": (frozen_crop,), "original_image": frozen_crop, "crop": frozen_crop,
                 "average_confidence": float(confidence or 0.0), "frames": (crop.get("frame_id"),), "version": int(current.get("version", 1)) + 1,
                 "frames_seen": len(crop.get("source_frames", ())) or 1, "updated": now, "last_seen": now}
        if "tags" in fields: value["tags"] = self._strings(fields["tags"])
        if "aliases" in fields: value["aliases"] = self._strings(fields["aliases"])
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
        try:
            payload = json.loads(self._storage_path.read_text(encoding="utf-8"))
            objects = payload.get("objects", ())
            if not isinstance(objects, list): raise ValueError("Object manifest objects must be an array")
            loaded = {}
            for item in objects:
                if not isinstance(item, dict) or not str(item.get("object_id", "")).strip(): continue
                value = {**item, "version": max(1, int(item.get("version", 1) or 1))}
                loaded[value["object_id"]] = self._freeze(value)
            self._items = loaded
            categories = payload.get("categories", ())
            if isinstance(categories, list):
                self._categories = {item["category_id"]: item for item in categories if isinstance(item, dict) and item.get("category_id") and item.get("name")}
            for item in self._items.values(): self._ensure_category(item.get("category", ""))
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            self._items = {}
            self._categories = {}

    def _save(self):
        self._storage_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"version": "TaskGraph v1", "categories": [self._plain(item) for item in self.categories()], "objects": [self._plain(item) for item in self.list()]}
        temporary = self._storage_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        temporary.replace(self._storage_path)

    def _ensure_category(self, name):
        value = str(name or "").strip()
        if not value or any(item["name"].casefold() == value.casefold() for item in self._categories.values()): return
        category_id = f"category-{uuid4().hex[:12]}"
        now = datetime.now().isoformat(timespec="seconds")
        self._categories[category_id] = {"category_id": category_id, "name": value, "created": now, "updated": now}

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
