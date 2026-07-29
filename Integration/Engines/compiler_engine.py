"""Compiler Engine: compilation and self-contained Execution Task production."""
from __future__ import annotations

from pathlib import Path

class CompilerEngine:
    def __init__(self, root: Path, taskir_engine, action_assets, execution_tasks, request_factory):
        self._root = root
        self._taskir = taskir_engine
        self._assets = action_assets
        self._execution_tasks = execution_tasks
        self._request = request_factory

    def list_compiled(self):
        return self._taskir.list_action_task_ir(self._request("list-compiled"))

    def validate(self, action_id):
        return self._taskir.validate_action(self._request("validate-action"), self._assets.get_asset(action_id))

    def compile(self, action_id):
        return self._taskir.compile_action(self._request("compile-action"), self._assets.get_asset(action_id))

    def get(self, action_id):
        return self._taskir.get_action_task_ir(self._request("get-compiled"), action_id)

    def create_execution_task(self, action_id):
        """Materialize an immutable, portable handoff from Compiler to Packaging."""
        action, task_ir = self._assets.get_asset(action_id), self.get(action_id)
        return self._execution_tasks.save(action, task_ir, self._assets.preview_path(action_id))
