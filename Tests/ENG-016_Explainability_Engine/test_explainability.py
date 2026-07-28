import copy,sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/"Implementation"/"ENG-016_Explainability_Engine"/"Source"))
from taskgraph_explainability import *
class MemoryStorage:
    def __init__(self,payload=None):self.payload=payload
    def load(self):return copy.deepcopy(self.payload)
    def save(self,payload):self.payload=copy.deepcopy(plain(payload))
class Source:
    def __init__(self,artifacts=()):self.artifacts=artifacts
    def get_artifacts(self):return self.artifacts
def artifact():return {"task_id":"taskir:one","semantic_plan_id":"plan:one","engine_version":"1.0.0","schema_version":"1.0","checksum":"source-checksum","created":"2026-01-01T00:00:00Z","nodes":[{"action":"pick"},{"action":"place"}],"resources":[{"knowledge_id":"knowledge:cup","affordance_id":"affordance:cup"}],"metadata":{"rule_id":"rule:pick-place","rule_version":"1.0.0","provenance":["knowledge:cup","affordance:cup"]},"validation":{"valid":True,"errors":[],"warnings":[]},"compilation":{"compiler_id":"ENG-014","compiler_version":"1.0.0","source_plan_id":"plan:one","diagnostics":["validated"]}}
def request(name="test"):return ExplainabilityRequest(name,"workflow:one","test")
def ready(source=None,storage=None):
    engine=ExplainabilityEngine(source or Source(),storage or MemoryStorage());assert engine.initialize(request("initialize")).status is ResponseStatus.SUCCEEDED;return engine
def test_lifecycle_immutable_and_deterministic():
    engine=ready();first=engine.generate_explanation(request("one"),"task_ir","ENG-014",artifact()).record;second=engine.generate_explanation(request("two"),"task_ir","ENG-014",artifact()).record
    assert plain(first)==plain(second);assert first.decision_trace.ordered_actions==("pick","place")
    with pytest.raises(Exception):first.artifact_id="changed"
    with pytest.raises(TypeError):first.metadata.attributes["x"]=1
    assert engine.close(request("close")).state is ExplainabilityState.CLOSED
def test_content_is_directly_derived_and_traceable():
    record=ready().generate_explanation(request(),"task_ir","ENG-014",artifact()).record
    assert record.planning_rule_id=="rule:pick-place";assert record.semantic_plan_id=="plan:one";assert record.task_ir_id=="taskir:one";assert record.knowledge_id=="knowledge:cup";assert record.affordance_id=="affordance:cup";assert record.compilation.compiler_id=="ENG-014";assert record.validation.valid
def test_search_traces_statistics_export_import_and_validation():
    engine=ready();record=engine.generate_explanation(request(),"task_ir","ENG-014",artifact()).record
    assert engine.get_explanation(request("get"),record.explanation_id).record==record;assert len(engine.search(request("search"),"pick-place").records)==1;assert engine.trace_artifact(request("artifact"),"knowledge:cup").status is ResponseStatus.SUCCEEDED;assert engine.trace_decision(request("decision"),record.explanation_id).trace.ordered_actions==("pick","place");assert engine.trace_dependency(request("dependency"),record.explanation_id).trace.dependency_chain[-1]=="taskir:one";assert engine.get_statistics(request("stats")).statistics.total_records==1
    payload=plain(engine.export(request("export")).export);target=ready();assert target.import_records(request("import"),payload).status is ResponseStatus.SUCCEEDED;assert target.validate(request("validate"),record.explanation_id).valid
def test_rebuild_is_read_only_repeatable_and_replaces_stale_records():
    original=artifact();snapshot=copy.deepcopy(original);engine=ready(Source((("task_ir","ENG-014",original),)));first=engine.rebuild(request("first"));second=engine.rebuild(request("second"));assert original==snapshot;assert plain(first.records)==plain(second.records);assert len(second.records)==1
def test_tamper_invalid_source_and_schema_are_rejected():
    engine=ready();record=plain(engine.generate_explanation(request(),"task_ir","ENG-014",artifact()).record);record["artifact_id"]="tampered";assert engine.validate(request("tamper"),record).status is ResponseStatus.REJECTED
    invalid=artifact();invalid["validation"]["valid"]=False;assert engine.generate_explanation(request("invalid"),"task_ir","ENG-014",invalid).status is ResponseStatus.REJECTED
    storage=MemoryStorage({"schema_version":"2.0","records":[]});assert ExplainabilityEngine(Source(),storage).initialize(request()).state is ExplainabilityState.INVALID
def test_thread_safety_and_storage_round_trip(tmp_path):
    storage=JsonExplanationStorage(tmp_path/"explanations.json");engine=ready(storage=storage)
    with ThreadPoolExecutor(max_workers=8) as pool:results=list(pool.map(lambda i:engine.generate_explanation(request(str(i)),"task_ir","ENG-014",artifact()),range(32)))
    assert all(x.status is ResponseStatus.SUCCEEDED for x in results);assert engine.get_statistics(request("stats")).statistics.total_records==1;engine.close(request("close"));reloaded=ready(storage=storage);assert reloaded.get_statistics(request("stats2")).statistics.total_records==1
