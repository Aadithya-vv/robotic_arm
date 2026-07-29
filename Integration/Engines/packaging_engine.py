"""Packaging Engine and replaceable ROBOT ORam transport boundary."""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import base64
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from uuid import uuid4


DEFAULT_ROBOT = {
    "robot_id": "robot_001",
    "robot_name": "Desktop Arm V1 (Proxy)",
    "robot_model": "6DOF_V1",
    "robot_version": "1.0",
    "number_of_joints": 6,
    "joint_names": ["Base", "Shoulder", "Elbow", "Wrist1", "Wrist2", "Gripper"],
    "joint_types": ["Revolute", "Revolute", "Revolute", "Revolute", "Revolute", "Revolute"],
    "workspace_origin": {"x": 0, "y": 0, "z": 0},
    "workspace_bounds": {"x": [-400, 400], "y": [-400, 400], "z": [0, 500]},
    "coordinate_system": "World",
    "units": {"distance": "mm", "angle": "degrees", "time": "seconds"},
    "end_effector": {"name": "Gripper", "type": "Gripper"},
    "supported_operations": ["Move", "Pick", "Place", "Wait"],
    "speed_profiles": [{"id": "slow", "name": "Slow", "scale": 0.35}, {"id": "normal", "name": "Normal", "scale": 0.65}, {"id": "fast", "name": "Fast", "scale": 0.9}],
    "accuracy_profiles": [{"id": "high_precision", "name": "High Precision", "tolerance_mm": 1}, {"id": "balanced", "name": "Balanced", "tolerance_mm": 3}, {"id": "high_speed", "name": "High Speed", "tolerance_mm": 6}],
    "home_poses": [{"id": "home", "name": "HOME", "pose": [0, -30, 65, 0, 55, 0]}],
    "object_vocabulary": ["Cup", "Bottle", "Plate", "Spoon", "Fork"],
    "connection": {"status": "Offline (Proxy)", "service": "_robot-oram._tcp.local", "transport": "WiFi", "host": "proxy.local", "port": 7421, "proxy": True},
}

_TRANSPARENT_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVQIHWP4z8DwHwAFgAI/ScL+WQAAAABJRU5ErkJggg=="
)


class ExecutionTaskStore:
    """Packaging-owned persistence boundary shared with Compiler Engine."""
    def __init__(self, root: Path):
        self.directory = root / "Assets" / "Execution Tasks"
        self._lock = RLock()

    def save(self, action, task_ir, preview_source):
        with self._lock:
            name = self._safe_name(action["name"])
            target = self.directory / f"{name}.task"
            staging = self.directory / f".{name}.task.tmp"
            if staging.exists(): shutil.rmtree(staging)
            staging.mkdir(parents=True, exist_ok=False)
            suffix = preview_source.suffix.lower() if preview_source.suffix.lower() in {".mp4", ".webm"} else ".webm"
            preview_name = f"preview{suffix}"
            shutil.copy2(preview_source, staging / preview_name)
            timeline = task_ir.get("timeline", action.get("keyframes", []))
            operations = task_ir.get("operations", [])
            metadata = {
                "execution_task_id": name, "name": action["name"], "action_id": action["id"],
                "created_at": datetime.now(timezone.utc).isoformat(),
                "duration": task_ir.get("metadata", {}).get("duration", action.get("estimatedDuration", 0)),
                "compiler_status": "Compiled",
                "compiler_version": task_ir.get("metadata", {}).get("compiler_version", "1.0.0"),
                "preview": preview_name, "folder": f"{name}.task",
            }
            documents = {
                "timeline.json": timeline, "keyframes.json": action.get("keyframes", []),
                "objects.json": action.get("referencedObjects", []),
                "coordinates.json": [point for operation in operations for point in operation.get("coordinates", [])],
                "inference.json": task_ir.get("semantic_segments", []),
                "taskir.json": task_ir, "metadata.json": metadata,
            }
            for filename, value in documents.items():
                (staging / filename).write_text(json.dumps(value, indent=2), encoding="utf-8")
            (staging / "thumbnail.png").write_bytes(_TRANSPARENT_PNG)
            if target.exists(): shutil.rmtree(target)
            staging.replace(target)
            return self.get(name)

    def list(self):
        if not self.directory.is_dir(): return []
        tasks = [self._load(path) for path in self.directory.glob("*.task") if path.is_dir()]
        return sorted(tasks, key=lambda item: item["metadata"]["created_at"], reverse=True)

    def get(self, execution_task_id):
        path = self.directory / f"{self._safe_id(execution_task_id)}.task"
        if not path.is_dir(): raise KeyError(execution_task_id)
        return self._load(path)

    def asset_path(self, execution_task_id, filename):
        path = self.directory / f"{self._safe_id(execution_task_id)}.task" / filename
        if filename not in {"preview.mp4", "preview.webm", "thumbnail.png"} or not path.is_file(): raise KeyError(filename)
        return path

    @staticmethod
    def _safe_name(value):
        name = re.sub(r'[<>:"/\\|?*]+', "", str(value)).strip().rstrip(".")
        return name or "Untitled Execution Task"

    @classmethod
    def _safe_id(cls, value):
        value = str(value)
        if value != cls._safe_name(value): raise KeyError(value)
        return value

    @staticmethod
    def _load(path):
        read = lambda filename: json.loads((path / filename).read_text(encoding="utf-8"))
        metadata = read("metadata.json")
        return {
            "execution_task_id": metadata["execution_task_id"], "metadata": metadata,
            "preview_video": f"/execution/tasks/{metadata['execution_task_id']}/{metadata['preview']}",
            "thumbnail": f"/execution/tasks/{metadata['execution_task_id']}/thumbnail.png",
            "timeline": read("timeline.json"), "keyframes": read("keyframes.json"),
            "objects": read("objects.json"), "coordinates": read("coordinates.json"),
            "inference": read("inference.json"), "task_ir": read("taskir.json"),
        }


class RobotProfileStore:
    """Packaging-owned, persistent source of truth for Robot Profiles."""
    def __init__(self, root: Path):
        self.directory = root / "Assets" / "RobotProfiles"
        self._lock = RLock()
        self.ensure_proxy()

    def ensure_proxy(self):
        with self._lock:
            self.directory.mkdir(parents=True, exist_ok=True)
            path = self.directory / f'{DEFAULT_ROBOT["robot_id"]}.json'
            if not path.is_file(): path.write_text(json.dumps(DEFAULT_ROBOT, indent=2), encoding="utf-8")
            return self.get(DEFAULT_ROBOT["robot_id"])

    def list(self):
        self.ensure_proxy()
        profiles = [json.loads(path.read_text(encoding="utf-8")) for path in self.directory.glob("*.json")]
        return sorted(profiles, key=lambda item: (item["robot_id"] != DEFAULT_ROBOT["robot_id"], item["robot_name"]))

    def get(self, robot_id):
        path = self.directory / f"{self._safe_id(robot_id)}.json"
        if not path.is_file(): raise KeyError(robot_id)
        return json.loads(path.read_text(encoding="utf-8"))

    def save(self, profile):
        robot_id = self._safe_id(profile.get("robot_id", ""))
        with self._lock:
            self.directory.mkdir(parents=True, exist_ok=True)
            (self.directory / f"{robot_id}.json").write_text(json.dumps(profile, indent=2), encoding="utf-8")
        return profile

    @staticmethod
    def _safe_id(value):
        value = str(value)
        if not value or any(char not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_" for char in value): raise ValueError("Invalid Robot Profile")
        return value


class RobotOramConnection:
    """Simulation with the same discovery/profile contract as future WiFi transport."""
    def __init__(self, profile): self._profile, self._connected = deepcopy(profile), False
    @property
    def connected(self): return self._connected
    def discover(self): return [{"service": self._profile["connection"]["service"], "robot_id": self._profile["robot_id"], "simulated": True}]
    def connect(self): self._connected = True; return deepcopy(self._profile)
    def disconnect(self): self._connected = False
    def transfer(self, _package_path):
        if not self._connected: raise ConnectionError("ROBOT ORam is disconnected")
        return {"status": "transferred", "transferred_at": datetime.now(timezone.utc).isoformat()}


class PackagingEngine:
    def __init__(self, root: Path, execution_tasks: ExecutionTaskStore, robot_profiles: RobotProfileStore):
        self.root, self.execution_tasks, self.robot_profiles = root, execution_tasks, robot_profiles
        self.package_dir = root / "Assets" / "ExecutionPackages"
        self._lock = RLock()
        self.connection = RobotOramConnection(self.robot_profiles.ensure_proxy())

    def list_robots(self): return self.robot_profiles.list()
    def list_execution_tasks(self): return self.execution_tasks.list()
    def get_execution_task(self, execution_task_id): return self.execution_tasks.get(execution_task_id)
    def execution_task_asset(self, execution_task_id, filename): return self.execution_tasks.asset_path(execution_task_id, filename)
    def get_robot(self, robot_id):
        return self.robot_profiles.get(robot_id)

    def store_robot(self, profile):
        return self.robot_profiles.save(profile)

    def validate_configuration(self, robot, task_ir, configuration):
        errors = []
        if configuration.get("speed_profile") not in {x["id"] for x in robot["speed_profiles"]}: errors.append("Unsupported speed profile")
        if configuration.get("accuracy_profile") not in {x["id"] for x in robot["accuracy_profiles"]}: errors.append("Unsupported accuracy profile")
        if configuration.get("home_pose") not in {x["id"] for x in robot["home_poses"]}: errors.append("Unsupported home pose")
        if not task_ir.get("validation", {}).get("valid"): errors.append("TaskIR is not valid")
        aliases = {"TRANSPORT": "MOVE", "IDLE": "WAIT"}
        supported = {str(value).upper() for value in robot["supported_operations"]}
        unsupported = sorted({value for item in task_ir.get("operations", []) if (value := aliases.get(str(item.get("type", "")).upper(), str(item.get("type", "")).upper())) not in supported})
        if unsupported: errors.append(f"Unsupported operations: {', '.join(unsupported)}")
        return {"valid": not errors, "errors": errors, "checks": ["Robot Profile resolved", "TaskIR schema valid", "Execution configuration supported", "Package contents complete"] if not errors else []}

    def preview(self, robot_id, execution_task_id, configuration):
        robot, task = self.get_robot(robot_id), self.execution_tasks.get(execution_task_id)
        task_ir = task["task_ir"]
        validation = self.validate_configuration(robot, task_ir, configuration)
        contents = {name: bool(task.get(name)) for name in ("preview_video", "timeline", "keyframes", "objects", "coordinates", "inference", "task_ir")}
        contents.update(robot_profile=True, manifest=True)
        return {"selected_robot": robot["robot_name"], "selected_task": task["metadata"]["name"], "package_size": self._estimate(robot, task, configuration), "status": "Ready" if validation["valid"] else "Invalid", "validation": validation, "contents": contents}

    def build(self, robot_id, execution_task_id, configuration):
        with self._lock:
            robot, task = self.get_robot(robot_id), self.execution_tasks.get(execution_task_id)
            task_ir = task["task_ir"]
            validation = self.validate_configuration(robot, task_ir, configuration)
            if not validation["valid"]: raise ValueError("; ".join(validation["errors"]))
            package_id, built_at = f"package-{uuid4().hex[:12]}", datetime.now(timezone.utc).isoformat()
            compiler_report = {"pipeline": task_ir.get("pipeline", []), "console": task_ir.get("console", []), "metrics": task_ir.get("metrics", {}), "validation": task_ir.get("validation", {})}
            package = {"package_metadata": {"package_id": package_id, "schema_version": "1.0.0", "built_at": built_at, "status": "ready", "transfer_status": "pending"},
                "robot_profile_snapshot": robot,
                "execution_task": {"execution_task_id": task["execution_task_id"], "name": task["metadata"]["name"], "preview_video": task["preview_video"], "timeline": task["timeline"], "keyframes": task["keyframes"], "objects": task["objects"], "coordinates": task["coordinates"], "semantic_inference": task["inference"], "metadata": task["metadata"]},
                "task_ir": task_ir,
                "execution_configuration": deepcopy(configuration), "compiler_report": compiler_report}
            manifest = {"package_id": package_id, "contents": sorted(package), "checksum_algorithm": "sha256"}
            package["manifest"] = manifest
            encoded = json.dumps(package, sort_keys=True, separators=(",", ":")).encode()
            manifest["checksum"] = hashlib.sha256(encoded).hexdigest()
            self.package_dir.mkdir(parents=True, exist_ok=True)
            target = self.package_dir / f"{package_id}.json"
            target.write_text(json.dumps(package, indent=2), encoding="utf-8")
            if self.connection.connected:
                transfer = self.connection.transfer(target)
                package["package_metadata"]["transfer_status"] = transfer["status"]
                package["package_metadata"]["transferred_at"] = transfer["transferred_at"]
                target.write_text(json.dumps(package, indent=2), encoding="utf-8")
            return self._summary(package, target.stat().st_size)

    def list_packages(self):
        if not self.package_dir.is_dir(): return []
        values = [self._read(path) for path in self.package_dir.glob("*.json")]
        return sorted((self._summary(value, path.stat().st_size) for value, path in values), key=lambda x: x["build_time"], reverse=True)

    def get_package(self, package_id):
        path = self._package_path(package_id)
        if not path.is_file(): raise KeyError(package_id)
        return json.loads(path.read_text(encoding="utf-8"))

    def send_execution_package(self, package_id):
        """Transfer an existing package without invoking package generation."""
        if not self.connection.connected:
            raise ConnectionError("ROBOT ORam is not connected. Please connect first.")
        with self._lock:
            path = self._package_path(package_id)
            if not path.is_file(): raise KeyError(package_id)
            package = json.loads(path.read_text(encoding="utf-8"))
            package["package_metadata"]["transfer_status"] = "sending"
            path.write_text(json.dumps(package, indent=2), encoding="utf-8")
            try:
                acknowledgement = self.connection.transfer(path)
                package["package_metadata"]["transfer_status"] = acknowledgement["status"]
                package["package_metadata"]["transferred_at"] = acknowledgement["transferred_at"]
            except Exception:
                package["package_metadata"]["transfer_status"] = "failed"
                path.write_text(json.dumps(package, indent=2), encoding="utf-8")
                raise
            path.write_text(json.dumps(package, indent=2), encoding="utf-8")
            return self._summary(package, path.stat().st_size)

    def _package_path(self, package_id):
        package_id = str(package_id)
        if not package_id.startswith("package-") or any(char not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_" for char in package_id):
            raise KeyError(package_id)
        return self.package_dir / f"{package_id}.json"

    def _read(self, path): return json.loads(path.read_text(encoding="utf-8")), path
    def _estimate(self, robot, task_ir, configuration): return len(json.dumps([robot, task_ir, configuration]).encode()) + 2048
    @staticmethod
    def _summary(package, size):
        metadata, robot = package["package_metadata"], package["robot_profile_snapshot"]
        task = package.get("execution_task") or package.get("action_asset", {})
        task_id = task.get("execution_task_id") or task.get("id", "")
        return {"package_id": metadata["package_id"], "build_time": metadata["built_at"], "task": task.get("name", task_id), "task_id": task_id, "robot": robot["robot_name"], "robot_id": robot["robot_id"], "status": metadata["status"], "transfer_status": metadata["transfer_status"], "package_size": size}
