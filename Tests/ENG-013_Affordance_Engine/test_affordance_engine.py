from __future__ import annotations
import inspect,json,tempfile,threading,time,unittest
from dataclasses import dataclass,field,FrozenInstanceError
from pathlib import Path
from typing import Any,Mapping
from taskgraph_affordance import *
@dataclass(frozen=True)
class Knowledge:
    knowledge_id:str="knowledge:cup";object_id:str="cup";object_name:str="Cup";category:str="Container";properties:Mapping[str,Any]=field(default_factory=dict);facts:tuple[Any,...]=();relationships:tuple[Any,...]=();confidence:float=.9;knowledge_sources:tuple[str,...]=("semantic_inventory",);created:str="2026-01-01";updated:str="2026-01-02"
class Source:
    def __init__(self,items=()):self.items=list(items)
    def get_all(self):return tuple(self.items)
class Storage:
    def __init__(self,p=None):self.payload=p;self.saves=0
    def load(self):return self.payload
    def save(self,p):self.payload=plain(p);self.saves+=1
class Logs:
    def __init__(self):self.items=[]
    def record(self,x):self.items.append(x)
def req(i="r1"):return AffordanceRequest(i,"corr","test")
def ready(items=None,storage=None,logs=None):
    e=AffordanceEngine(Source(items if items is not None else [Knowledge()]),storage or Storage(),clock=lambda:"now",log_sink=logs);assert e.initialize(req()).status is ResponseStatus.SUCCEEDED;return e
class Tests(unittest.TestCase):
    def test_contract(self):self.assertIsInstance(ready(),AffordanceContract)
    def test_lifecycle(self):self.assertEqual(ready().state,AffordanceState.AVAILABLE)
    def test_invalid_reinit(self):self.assertEqual(ready().initialize(req()).status,ResponseStatus.REJECTED)
    def test_close(self):self.assertEqual(ready().close(req()).state,AffordanceState.CLOSED)
    def test_record_complete(self):
        x=ready().get_affordance_by_object(req(),"cup").record
        for n in ("affordance_id","preconditions","postconditions","constraints","safety_notes","generation_rule","checksum"):self.assertTrue(hasattr(x,n))
    def test_immutable(self):
        x=ready().get_affordance_by_object(req(),"cup").record
        with self.assertRaises(FrozenInstanceError):x.object_name="x"
    def test_container_and_cup_rules_union(self):self.assertEqual(ready().get_affordance_by_object(req(),"cup").record.affordances,("carry","fill","hold","pick","place","pour"))
    def test_spoon_rule(self):self.assertIn("stir",ready([Knowledge("knowledge:spoon","spoon","Spoon","Utensil")]).get_affordance_by_object(req(),"spoon").record.affordances)
    def test_bottle_rule(self):self.assertIn("open",ready([Knowledge("knowledge:b","b","Bottle","Container")]).get_affordance_by_object(req(),"b").record.affordances)
    def test_unknown_has_no_guessed_actions(self):self.assertEqual(ready([Knowledge("knowledge:x","x","Mystery","Unknown")]).get_affordance_by_object(req(),"x").record.affordances,())
    def test_rule_version(self):self.assertEqual(ready().get_affordance(req()).graph.rule_version,"1.0.0")
    def test_lookup_id(self):self.assertEqual(ready().get_affordance(req(),"affordance:cup").record.object_id,"cup")
    def test_missing(self):self.assertEqual(ready().get_affordance(req(),"missing").status,ResponseStatus.REJECTED)
    def test_search_object(self):self.assertEqual(ready().search(req(),query="cup").graph.statistics.total_records,1)
    def test_search_capability(self):self.assertEqual(ready().search(req(),capability="fill").graph.statistics.total_records,1)
    def test_search_action(self):self.assertEqual(ready().search(req(),action="pour").graph.statistics.total_records,1)
    def test_statistics(self):self.assertEqual(ready().get_statistics(req()).statistics.total_capabilities,6)
    def test_export_serializes(self):json.dumps(plain(ready().export_affordances(req()).export))
    def test_integrity(self):self.assertTrue(ready().validate_affordances(req()).valid)
    def test_migration(self):
        s=Storage({"schema_version":"0"});ready(storage=s);self.assertEqual((s.payload["schema_version"],s.saves),("1.0",1))
    def test_json_storage(self):
        with tempfile.TemporaryDirectory() as f:
            s=JsonAffordanceStorage(Path(f)/"a.json");ready(storage=s);self.assertEqual(s.load()["records"][0]["object_id"],"cup")
    def test_rebuild(self):
        s=Source([Knowledge()]);e=AffordanceEngine(s,Storage());e.initialize(req());s.items.append(Knowledge("knowledge:s","s","Spoon","Utensil"));self.assertEqual(e.rebuild(req()).graph.statistics.total_records,2)
    def test_thread_safety(self):
        e=ready();out=[];ts=[threading.Thread(target=lambda:out.append(e.search(req(),action="pick").status)) for _ in range(20)];[t.start() for t in ts];[t.join() for t in ts];self.assertEqual(out.count(ResponseStatus.SUCCEEDED),20)
    def test_performance(self):
        values=[Knowledge(f"knowledge:{i}",str(i),"Cup","Container") for i in range(1000)];t=time.perf_counter();e=ready(values);self.assertLess(time.perf_counter()-t,2);self.assertEqual(e.get_statistics(req()).statistics.total_records,1000)
    def test_logging(self):l=Logs();ready(logs=l);self.assertEqual(l.items[0].engine_id,"ENG-013")
    def test_bad_configuration(self):
        with self.assertRaises(ValueError):AffordanceEngine(Source(),Storage(),AffordanceConfiguration(rule_version="2"))
    def test_rule40(self):
        import taskgraph_affordance.engine as m
        src=inspect.getsource(m);self.assertFalse(any(x in src for x in ("taskgraph_knowledge","taskgraph_semantic","object_library","taskgraph_planner")))
if __name__=="__main__":unittest.main()
