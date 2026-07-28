import copy
import hashlib
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Implementation" / "ENG-014_TaskIR_Compiler_Engine" / "Source"))

from taskgraph_taskir import (CompilerState, JsonTaskIRStorage, ResponseStatus, TaskIRCompilerEngine,
                              TaskIRRequest, plain)


class MemoryStorage:
    def __init__(self, payload=None): self.payload = payload
    def load(self): return copy.deepcopy(self.payload)
    def save(self, payload): self.payload = copy.deepcopy(plain(payload))


def digest(value):
    return hashlib.sha256(json.dumps(plain(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def plan(plan_id="plan:cup"):
    node_base = {"plan_id": plan_id, "node_id": f"{plan_id}:node:001", "action": "grasp", "object_id": "object:cup",
                 "knowledge_id": "knowledge:cup", "affordance_id": "affordance:cup", "goal": "pick cup",
                 "preconditions": ["cup available"], "postconditions": ["cup grasped"], "constraints": ["safe"],
                 "participants": ["object:cup"], "inputs": [], "outputs": ["step:1:complete"],
                 "duration": "semantic-only", "priority": 1, "metadata": {"rule_id": "rule:pick"},
                 "schema_version": "1.0", "engine_version": "1.0.0", "created": "2026-01-01T00:00:00Z",
                 "updated": "2026-01-01T00:00:00Z"}
    node = {**node_base, "checksum": digest(node_base)}
    base = {"plan_id": plan_id, "goal": {"goal_id": "goal:pick", "name": "pick cup", "description": "pick cup",
             "success_conditions": ["cup grasped"]}, "nodes": [node], "edges": [], "constraints": [],
            "resources": [{"resource_id": "resource:cup", "object_id": "object:cup", "knowledge_id": "knowledge:cup",
                           "affordance_id": "affordance:cup", "role": "primary"}],
            "validation": {"valid": True, "errors": [], "warnings": []},
            "metadata": {"rule_id": "rule:pick", "rule_version": "1.0.0", "source_versions": {"knowledge": "1.0"},
                         "provenance": ["knowledge:cup", "affordance:cup"]}, "schema_version": "1.0",
            "engine_version": "1.0.0", "created": "2026-01-01T00:00:00Z", "updated": "2026-01-01T00:00:00Z"}
    return {**base, "checksum": digest(base)}


def request(name="test", correlation="workflow:1"):
    return TaskIRRequest(name, correlation, "test")


def ready(storage=None):
    engine = TaskIRCompilerEngine(storage or MemoryStorage())
    assert engine.initialize(request("initialize")).status is ResponseStatus.SUCCEEDED
    return engine


def test_lifecycle_and_public_contract():
    engine = TaskIRCompilerEngine(MemoryStorage())
    assert engine.compile(request(), plan()).status is ResponseStatus.REJECTED
    assert engine.initialize(request()).state is CompilerState.AVAILABLE
    assert engine.close(request("close")).state is CompilerState.CLOSED


def test_compilation_is_lossless_for_actions_and_order_and_is_deterministic():
    engine = ready()
    first = engine.compile(request("one"), plan()).task_ir
    second = engine.compile(request("two", "another-workflow-context"), plan()).task_ir
    assert plain(first) == plain(second)
    assert [item.action for item in first.nodes] == [item["action"] for item in plan()["nodes"]]
    assert first.nodes[0].node_id == plan()["nodes"][0]["node_id"]
    assert first.created == plan()["created"]


@pytest.mark.parametrize("mutation", [
    lambda value: value["validation"].update(valid=False),
    lambda value: value.update(schema_version="2.0"),
    lambda value: value["nodes"][0].update(action="invented"),
])
def test_rejects_unvalidated_incompatible_or_tampered_plans(mutation):
    source = plan(); mutation(source)
    response = ready().compile(request(), source)
    assert response.status is ResponseStatus.REJECTED
    assert not response.task_ir


def test_validation_detects_taskir_tampering():
    engine = ready(); document = plain(engine.compile(request(), plan()).task_ir)
    document["nodes"][0]["action"] = "tampered"
    response = engine.validate(request("validate"), document)
    assert response.status is ResponseStatus.REJECTED
    assert "checksum mismatch" in " ".join(response.validation.errors)


def test_storage_export_import_statistics_search_and_rebuild(tmp_path):
    path = tmp_path / "task_ir.json"; engine = ready(JsonTaskIRStorage(path))
    compiled = engine.compile(request(), plan()).task_ir
    assert path.exists()
    assert engine.get_task_ir(request("get"), compiled.task_id).task_ir == compiled
    assert len(engine.search_task_ir(request("search"), "grasp").documents) == 1
    exported = plain(engine.export_task_ir(request("export"), compiled.task_id).export)
    target = ready()
    assert target.import_task_ir(request("import"), exported).status is ResponseStatus.SUCCEEDED
    stats = target.get_statistics(request("stats")).statistics
    assert (stats.total_documents, stats.valid_documents, stats.total_nodes, stats.actions["grasp"]) == (1, 1, 1, 1)
    assert target.rebuild(request("rebuild")).status is ResponseStatus.SUCCEEDED


def test_persistence_round_trip(tmp_path):
    storage = JsonTaskIRStorage(tmp_path / "task_ir.json"); first = ready(storage)
    expected = first.compile(request(), plan()).task_ir
    assert first.close(request("close")).status is ResponseStatus.SUCCEEDED
    second = ready(storage)
    assert second.get_task_ir(request("get"), expected.task_id).task_ir == expected


def test_thread_safety_and_repeatability():
    engine = ready()
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda index: engine.compile(request(f"compile-{index}"), plan()), range(32)))
    assert all(item.status is ResponseStatus.SUCCEEDED for item in results)
    assert len({item.task_ir.checksum for item in results}) == 1
    assert engine.get_statistics(request("stats")).statistics.total_documents == 1


def test_immutable_contracts():
    document = ready().compile(request(), plan()).task_ir
    with pytest.raises(Exception): document.task_id = "changed"
    with pytest.raises(TypeError): document.nodes[0].metadata["x"] = 1


def test_action_compiler_preserves_coordinates_and_uses_v1_vocabulary(tmp_path):
    engine = TaskIRCompilerEngine(JsonTaskIRStorage(tmp_path / "task_ir.json"))
    assert engine.initialize(request("action-init")).status is ResponseStatus.SUCCEEDED
    action = {"id": "action-spoon", "name": "Move Spoon", "description": "", "category": "Kitchen",
              "estimatedDuration": 2, "tags": [], "createdAt": "2026-01-01T00:00:00", "updatedAt": "2026-01-01T00:00:00",
              "referencedObjects": ["spoon"], "scene_objects": [],
              "keyframes": [{"objectId": "spoon", "positionX": 0, "positionY": 0, "rotationAngle": 0, "timestamp": 0},
                            {"objectId": "spoon", "positionX": 2, "positionY": 1, "rotationAngle": 15, "timestamp": 1}]}
    compiled = engine.compile_action(request("action-compile"), action)
    assert compiled["original_coordinates"] == action["keyframes"]
    assert {item["type"] for item in compiled["operations"]} <= {"IDLE", "PICK", "TRANSPORT", "PLACE"}
    assert [item["type"] for item in compiled["operations"]] == ["PICK", "TRANSPORT", "PLACE"]
    restarted = TaskIRCompilerEngine(JsonTaskIRStorage(tmp_path / "task_ir.json"))
    restarted.initialize(request("action-restart"))
    assert restarted.get_action_task_ir(request("action-get"), "action-spoon")["checksum"] == compiled["checksum"]


def test_invalid_store_fails_closed():
    storage = MemoryStorage({"schema_version": "2.0", "documents": []})
    response = TaskIRCompilerEngine(storage).initialize(request())
    assert response.status is ResponseStatus.FAILED
    assert response.state is CompilerState.INVALID
