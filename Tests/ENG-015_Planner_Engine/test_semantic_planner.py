import json,sys
from pathlib import Path
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/"Implementation"/"ENG-015_Planner_Engine"/"Source"))
from taskgraph_planner import *
class Source:
    def __init__(self,items):self.items=tuple(items)
    def get_all(self):return self.items
class MemoryStorage:
    def __init__(self,payload=None):self.payload=payload
    def load(self):return self.payload
    def save(self,payload):self.payload=json.loads(json.dumps(payload))
def sources(actions=("pick","carry","pour","place")):
    knowledge=SimpleNamespace(knowledge_id="knowledge:obj-1",object_id="obj-1",object_name="Bottle",schema_version="1.0")
    affordance=SimpleNamespace(affordance_id="affordance:obj-1",knowledge_id=knowledge.knowledge_id,object_id="obj-1",object_name="Bottle",affordances=actions,preconditions={a:("available",) for a in actions},postconditions={a:("done",) for a in actions},constraints={a:("semantic",) for a in actions},schema_version="1.0")
    return Source((knowledge,)),Source((affordance,))
def request(name="test"):return PlannerRequest(name,name,"pytest")
def engine(storage=None,actions=("pick","carry","pour","place")):
    k,a=sources(actions);e=SemanticPlannerEngine(k,a,storage or MemoryStorage(),clock=lambda:"2026-07-17T00:00:00+00:00");assert e.initialize(request("init")).status is ResponseStatus.SUCCEEDED;return e
def test_create_deterministic_plan():
    e=engine();p=e.create_plan(request(),"Pour Water").plan
    assert tuple(n.action for n in p.nodes)==("pick","carry","pour","place")
    assert tuple((x.source_node_id,x.target_node_id) for x in p.edges)==tuple((p.nodes[i].node_id,p.nodes[i+1].node_id) for i in range(3))
def test_rejects_unknown_goal():assert engine().create_plan(request(),"make tea").status is ResponseStatus.REJECTED
def test_rejects_missing_affordance():assert engine(actions=("pick","pour","place")).create_plan(request(),"pour water").status is ResponseStatus.REJECTED
def test_get_search_validate_statistics_export():
    e=engine();p=e.create_plan(request(),"pour water").plan
    assert e.get_plan(request(),p.plan_id).plan==p
    assert e.search_plans(request(),"pour").plans==(p,)
    assert e.search_goals(request(),"water").plans==(p,)
    assert e.validate_plan(request(),p.plan_id).valid
    assert e.get_statistics(request()).statistics.total_nodes==4
    assert e.export_plan(request(),p.plan_id).export["plan_id"]==p.plan_id
def test_persistence_reload_and_import():
    storage=MemoryStorage();e=engine(storage);p=e.create_plan(request(),"pour water").plan;e.close(request("close"))
    restored=engine(storage);assert restored.get_plan(request(),p.plan_id).plan.plan_id==p.plan_id
    target=engine();assert target.import_plan(request(),dict(restored.export_plan(request(),p.plan_id).export)).status is ResponseStatus.SUCCEEDED
def test_tamper_detected():
    e=engine();p=e.create_plan(request(),"pour water").plan
    object.__setattr__(p.nodes[0],"action","invented")
    assert e.validate_plan(request(),p.plan_id).status is ResponseStatus.FAILED
def test_lifecycle_and_not_found():
    k,a=sources();e=SemanticPlannerEngine(k,a,MemoryStorage())
    assert e.create_plan(request(),"pour water").status is ResponseStatus.REJECTED
    assert e.initialize(request()).status is ResponseStatus.SUCCEEDED
    assert e.get_plan(request(),"missing").status is ResponseStatus.REJECTED
    assert e.close(request()).status is ResponseStatus.SUCCEEDED
def test_storage_is_planner_only(tmp_path):
    path=tmp_path/"Assets"/"SemanticPlans"/"semantic_plans.json";e=SemanticPlannerEngine(*sources(),JsonSemanticPlanStorage(path));e.initialize(request());e.create_plan(request(),"pour water")
    payload=json.loads(path.read_text());assert set(payload)=={"schema_version","engine_version","plans"}
