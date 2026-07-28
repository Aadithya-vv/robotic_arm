"""Action Asset Engine: sole owner of authored action persistence and CRUD."""
from __future__ import annotations

from pathlib import Path

from action_builder_store import ActionBuilderStore, ActionLibraryStore


class ActionAssetEngine:
    def __init__(self, root: Path):
        directory = root / "Assets" / "Actions"
        self.builder = ActionBuilderStore(directory / "builder_state.json")
        self.library = ActionLibraryStore(directory)

    def load_workspace(self): return self.builder.load()
    def save_workspace(self, value): return self.builder.save(value)
    def list_assets(self): return self.library.list()
    def get_asset(self, action_id): return self.library.get(action_id)
    def create_asset(self, fields, preview, extension=".webm"):
        return self.library.create(fields, fields.get("scene_objects", []), fields.get("keyframes", []), preview, extension)
    def update_asset(self, action_id, fields): return self.library.update(action_id, fields)
    def delete_asset(self, action_id): return self.library.delete(action_id)
    def preview_path(self, action_id): return self.library.preview_path(action_id)
