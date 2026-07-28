"""Discover, verify, and optionally retrieve official integration model assets."""
from dataclasses import dataclass
from hashlib import sha256
from importlib.util import find_spec
import json
from pathlib import Path
from urllib.request import urlopen
import os


@dataclass(frozen=True, slots=True)
class ModelStatus:
    model_id: str
    path: str
    installed: bool
    checksum_valid: bool
    runtime_available: bool
    provider: str
    size_bytes: int


class ModelManager:
    def __init__(self, root: Path):
        self.root = Path(root)
        config = self.root / "Models" / ".ultralytics"; config.mkdir(parents=True, exist_ok=True); os.environ.setdefault("YOLO_CONFIG_DIR", str(config))
        self.manifest_path = self.root / "Models" / "models.json"
        self._manifest = json.loads(self.manifest_path.read_text(encoding="utf-8"))["models"]

    def status(self, model_id="yolo11n"):
        item = self._manifest[model_id]; path = self.root / "Models" / item["file"]
        valid = path.is_file() and self._checksum(path) == item["sha256"]
        return ModelStatus(model_id, str(path), path.is_file(), valid, find_spec("ultralytics") is not None, item["provider"], path.stat().st_size if path.is_file() else 0)

    def installed_models(self):
        return tuple(self.status(model_id) for model_id in sorted(self._manifest))

    def ensure(self, model_id="yolo11n", timeout=60):
        status = self.status(model_id)
        if status.checksum_valid: return status
        item = self._manifest[model_id]; target = Path(status.path); temporary = target.with_suffix(target.suffix + ".download")
        target.parent.mkdir(parents=True, exist_ok=True)
        with urlopen(item["url"], timeout=timeout) as response, temporary.open("wb") as output:
            while chunk := response.read(1024 * 1024): output.write(chunk)
        if self._checksum(temporary) != item["sha256"]:
            temporary.unlink(missing_ok=True); raise ValueError(f"checksum verification failed for {model_id}")
        temporary.replace(target); return self.status(model_id)

    def ensure_all(self):
        return tuple(self.ensure(model_id) for model_id in sorted(self._manifest))

    def select_auto(self):
        from gpu_runtime import accelerator_diagnostics
        preferred = ("yolo11m", "yolo11s", "yolo11n")
        for model_id in preferred:
            status = self.status(model_id)
            if status.checksum_valid and status.runtime_available: return model_id
        return "classical"

    @staticmethod
    def _checksum(path):
        digest = sha256()
        with Path(path).open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""): digest.update(chunk)
        return digest.hexdigest()
