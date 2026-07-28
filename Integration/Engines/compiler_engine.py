"""Compiler Engine facade: all Studio Action -> TaskIR orchestration."""
from __future__ import annotations


class CompilerEngine:
    def __init__(self, taskir_engine, action_assets, request_factory):
        self._taskir = taskir_engine
        self._assets = action_assets
        self._request = request_factory

    def list_compiled(self):
        return self._taskir.list_action_task_ir(self._request("list-compiled"))

    def validate(self, action_id):
        return self._taskir.validate_action(self._request("validate-action"), self._assets.get_asset(action_id))

    def compile(self, action_id):
        return self._taskir.compile_action(self._request("compile-action"), self._assets.get_asset(action_id))

    def get(self, action_id):
        return self._taskir.get_action_task_ir(self._request("get-compiled"), action_id)
