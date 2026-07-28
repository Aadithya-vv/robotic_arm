"""Packaging Engine and replaceable ROBOT ORam transport boundary."""
from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from uuid import uuid4


DEFAULT_ROBOT = {
    "robot_id": "desktop-arm-v1",
    "robot_name": "Desktop Arm V1",
    "robot_model": "TG-DA6",
    "robot_version": "1.0.0",
    "number_of_joints": 6,
    "joint_names": ["base", "shoulder", "elbow", "wrist_pitch", "wrist_roll", "tool"],
    "joint_types": ["revolute", "revolute", "revolute", "revolute", "revolute", "fixed"],
    "workspace_origin": {"x": 0, "y": 0, "z": 0},
    "workspace_bounds": {"x": [-450, 450], "y": [-450, 450], "z": [0, 650]},
    "coordinate_system": "right-handed Cartesian",
    "units": {"distance": "mm", "angle": "degrees", "time": "seconds"},
    "end_effector": {"name": "Adaptive Parallel Gripper", "type": "electric_gripper"},
    "supported_operations": ["PICK", "TRANSPORT", "PLACE", "IDLE", "WAIT", "RELEASE"],
    "speed_profiles": [{"id": "precision", "name": "Precision", "scale": 0.35}, {"id": "balanced", "name": "Balanced", "scale": 0.65}, {"id": "rapid", "name": "Rapid", "scale": 0.9}],
    "accuracy_profiles": [{"id": "fine", "name": "Fine", "tolerance_mm": 1}, {"id": "standard", "name": "Standard", "tolerance_mm": 3}],
    "home_poses": [{"id": "ready", "name": "Ready", "pose": [0, -30, 65, 0, 55, 0]}, {"id": "compact", "name": "Compact", "pose": [0, -70, 110, 0, 40, 0]}],
    "object_vocabulary": ["container", "cup", "bottle", "tray", "tool", "surface"],
    "connection": {"service": "_robot-oram._tcp.local", "transport": "WiFi", "host": "simulated.local", "port": 7421},
}


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
    def __init__(self, root: Path, action_assets, compiler):
        self.root, self.actions, self.compiler = root, action_assets, compiler
        self.profile_dir = root / "Assets" / "RobotProfiles"
        self.package_dir = root / "Assets" / "ExecutionPackages"
        self._lock = RLock()
        self._ensure_profile()
        self.connection = RobotOramConnection(self.get_robot(DEFAULT_ROBOT["robot_id"]))

    def _ensure_profile(self):
        self.profile_dir.mkdir(parents=True, exist_ok=True)
        path = self.profile_dir / f'{DEFAULT_ROBOT["robot_id"]}.json'
        if not path.exists(): path.write_text(json.dumps(DEFAULT_ROBOT, indent=2), encoding="utf-8")

    def list_robots(self): return [json.loads(path.read_text(encoding="utf-8")) for path in sorted(self.profile_dir.glob("*.json"))]
    def get_robot(self, robot_id):
        path = self.profile_dir / f"{robot_id}.json"
        if not path.is_file(): raise KeyError(robot_id)
        return json.loads(path.read_text(encoding="utf-8"))

    def store_robot(self, profile):
        robot_id = str(profile.get("robot_id", ""))
        if not robot_id or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_" for c in robot_id): raise ValueError("Invalid Robot Profile")
        self.profile_dir.mkdir(parents=True, exist_ok=True)
        (self.profile_dir / f"{robot_id}.json").write_text(json.dumps(profile, indent=2), encoding="utf-8")
        return profile

    def validate_configuration(self, robot, task_ir, configuration):
        errors = []
        if configuration.get("speed_profile") not in {x["id"] for x in robot["speed_profiles"]}: errors.append("Unsupported speed profile")
        if configuration.get("accuracy_profile") not in {x["id"] for x in robot["accuracy_profiles"]}: errors.append("Unsupported accuracy profile")
        if configuration.get("home_pose") not in {x["id"] for x in robot["home_poses"]}: errors.append("Unsupported home pose")
        if not task_ir.get("validation", {}).get("valid"): errors.append("TaskIR is not valid")
        unsupported = sorted({x.get("type") for x in task_ir.get("operations", [])} - set(robot["supported_operations"]))
        if unsupported: errors.append(f"Unsupported operations: {', '.join(unsupported)}")
        return {"valid": not errors, "errors": errors, "checks": ["Robot Profile resolved", "TaskIR schema valid", "Execution configuration supported", "Package contents complete"] if not errors else []}

    def preview(self, robot_id, action_id, configuration):
        robot, task_ir = self.get_robot(robot_id), self.compiler.get(action_id)
        validation = self.validate_configuration(robot, task_ir, configuration)
        return {"selected_robot": robot["robot_name"], "selected_task": task_ir.get("metadata", {}).get("action_name", action_id), "package_size": self._estimate(robot, task_ir, configuration), "status": "Ready" if validation["valid"] else "Invalid", "validation": validation}

    def build(self, robot_id, action_id, configuration):
        with self._lock:
            robot, action, task_ir = self.get_robot(robot_id), self.actions.get_asset(action_id), self.compiler.get(action_id)
            validation = self.validate_configuration(robot, task_ir, configuration)
            if not validation["valid"]: raise ValueError("; ".join(validation["errors"]))
            package_id, built_at = f"package-{uuid4().hex[:12]}", datetime.now(timezone.utc).isoformat()
            compiler_report = {"pipeline": task_ir.get("pipeline", []), "console": task_ir.get("console", []), "metrics": task_ir.get("metrics", {}), "validation": task_ir.get("validation", {})}
            package = {"package_metadata": {"package_id": package_id, "schema_version": "1.0.0", "built_at": built_at, "status": "ready", "transfer_status": "pending"},
                "robot_profile_snapshot": robot,
                "action_asset": {"id": action["id"], "name": action["name"], "preview_video": action.get("previewVideo"), "frames": action.get("keyframes", []), "timeline": action.get("keyframes", []), "objects": action.get("referencedObjects", []), "metadata": {k: action.get(k) for k in ("description", "category", "tags", "estimatedDuration", "createdAt", "updatedAt")}},
                "task_ir": {"task_ir_id": task_ir.get("task_ir_id"), "operations": task_ir.get("operations", []), "coordinates": [p for op in task_ir.get("operations", []) for p in op.get("coordinates", [])], "semantic_inference": task_ir.get("semantic_segments", [])},
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
        path = self.package_dir / f"{package_id}.json"
        if not path.is_file(): raise KeyError(package_id)
        return json.loads(path.read_text(encoding="utf-8"))

    def _read(self, path): return json.loads(path.read_text(encoding="utf-8")), path
    def _estimate(self, robot, task_ir, configuration): return len(json.dumps([robot, task_ir, configuration]).encode()) + 2048
    @staticmethod
    def _summary(package, size):
        metadata, action, robot = package["package_metadata"], package["action_asset"], package["robot_profile_snapshot"]
        return {"package_id": metadata["package_id"], "build_time": metadata["built_at"], "task": action["name"], "task_id": action["id"], "robot": robot["robot_name"], "robot_id": robot["robot_id"], "status": metadata["status"], "transfer_status": metadata["transfer_status"], "package_size": size}
