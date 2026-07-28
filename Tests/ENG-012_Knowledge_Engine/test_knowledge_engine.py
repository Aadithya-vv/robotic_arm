"""ENG-012 unit, serialization, migration, integrity, search, and concurrency tests."""
from __future__ import annotations
import inspect,json,tempfile,threading,time,unittest
from dataclasses import dataclass,field,FrozenInstanceError
from pathlib import Path
from typing import Any,Mapping
from taskgraph_knowledge import *

@dataclass(frozen=True)
class Semantic:
    object_id:str="object-1";object_name:str="Cup";category:str="Container";description:str="A ceramic drinking cup";aliases:tuple[str,...]=("mug",);average_confidence:float=.9;relationships:tuple[Any,...]=({"type":"near","target":"object-2"},);metadata:Mapping[str,Any]=field(default_factory=lambda:{"material":"ceramic","typical_uses":["drink"],"environment":{"location":"kitchen"},"times_seen":3});version:str="1.0";learning_date:str="2026-01-01";last_updated:str="2026-01-02";tags:tuple[str,...]=("portable",)
class Source:
    def __init__(self,items=()):self.items=list(items)
    def get_all(self):return tuple(self.items)
class Storage:
    def __init__(self,payload=None):self.payload=payload;self.saves=0
    def load(self):return self.payload
    def save(self,payload):self.payload=plain(payload);self.saves+=1
class Records:
    def __init__(self):self.items=[]
    def record(self,item):self.items.append(item)
class BadLogger:
    def record(self,item):raise RuntimeError("unavailable")
def request(identifier="request-1"):return KnowledgeRequest(identifier,"correlation-1","test")
def ready(items=None,storage=None,logger=None):
    engine=KnowledgeEngine(Source(items if items is not None else [Semantic()]),storage or Storage(),clock=lambda:"now",log_sink=logger);response=engine.initialize(request());assert response.status is ResponseStatus.SUCCEEDED,response;return engine

class KnowledgeTests(unittest.TestCase):
    def test_public_contract(self):self.assertIsInstance(ready(),KnowledgeContract)
    def test_lifecycle(self):self.assertEqual(ready().state,KnowledgeState.AVAILABLE)
    def test_invalid_reinitialize(self):self.assertEqual(ready().initialize(request()).status,ResponseStatus.REJECTED)
    def test_close(self):self.assertEqual(ready().close(request("close")).state,KnowledgeState.CLOSED)
    def test_complete_record(self):
        record=ready().get_knowledge_by_object(request(),"object-1").record
        for name in ("knowledge_id","properties","facts","attributes","typical_uses","materials","environment","knowledge_sources","checksum"):self.assertTrue(hasattr(record,name))
    def test_record_is_immutable(self):
        record=ready().get_knowledge_by_object(request(),"object-1").record
        with self.assertRaises(FrozenInstanceError):record.object_name="Changed"
    def test_invalid_configuration_rejected(self):
        with self.assertRaises(ValueError):KnowledgeEngine(Source(),Storage(),KnowledgeConfiguration(maximum_records=0))
    def test_no_inference(self):
        record=ready([Semantic(metadata={})]).get_knowledge_by_object(request(),"object-1").record;self.assertEqual((record.materials,record.typical_uses,plain(record.environment)),((),(),{}))
    def test_lookup_by_knowledge_id(self):self.assertEqual(ready().get_knowledge(request(),"knowledge:object-1").record.object_name,"Cup")
    def test_get_all_knowledge(self):self.assertEqual(ready().get_knowledge(request()).graph.statistics.total_records,1)
    def test_summary_uses_declared_semantics(self):self.assertIn("A ceramic drinking cup",ready().get_knowledge_by_object(request(),"object-1").record.summary)
    def test_missing_lookup(self):self.assertEqual(ready().get_knowledge(request(),"missing").status,ResponseStatus.REJECTED)
    def test_general_search(self):self.assertEqual(ready().search(request(),query="ceramic").graph.statistics.total_records,1)
    def test_property_search(self):self.assertEqual(ready().search(request(),property_name="category").graph.statistics.total_records,1)
    def test_fact_search(self):self.assertEqual(ready().search(request(),fact="drinking").graph.statistics.total_records,1)
    def test_category_search(self):self.assertEqual(ready().search(request(),category="container").graph.statistics.total_records,1)
    def test_relationship_search(self):self.assertEqual(ready().search(request(),relationship="near").graph.statistics.total_records,1)
    def test_statistics(self):
        stats=ready([Semantic(),Semantic("object-2","Plate",category="Dish")]).get_statistics(request()).statistics;self.assertEqual((stats.total_records,stats.categories["Container"],stats.relationships),(2,1,2))
    def test_export_serialization(self):json.dumps(plain(ready().export_knowledge(request()).export))
    def test_checksum_validation(self):self.assertTrue(ready().validate_knowledge(request()).valid)
    def test_checksum_stable(self):
        first=ready().get_knowledge_by_object(request(),"object-1").record.checksum;second=ready().get_knowledge_by_object(request(),"object-1").record.checksum;self.assertEqual(first,second)
    def test_migration_rebuilds_legacy(self):
        storage=Storage({"schema_version":"0.1","records":[]});ready(storage=storage);self.assertEqual((storage.payload["schema_version"],storage.saves),("1.0",1))
    def test_json_storage_roundtrip(self):
        with tempfile.TemporaryDirectory() as folder:
            storage=JsonKnowledgeStorage(Path(folder)/"knowledge.json");ready(storage=storage);self.assertEqual(storage.load()["records"][0]["object_id"],"object-1")
    def test_rebuild_tracks_semantic_source(self):
        source=Source([Semantic()]);engine=KnowledgeEngine(source,Storage());engine.initialize(request());source.items.append(Semantic("object-2","Plate"));self.assertEqual(engine.rebuild(request()).graph.statistics.total_records,2)
    def test_invalid_semantic_contract(self):
        engine=KnowledgeEngine(Source([object()]),Storage());self.assertEqual(engine.initialize(request()).status,ResponseStatus.FAILED)
    def test_thread_safe_queries(self):
        engine=ready();outputs=[];threads=[threading.Thread(target=lambda:outputs.append(engine.search(request(),query="cup").status)) for _ in range(20)];[t.start() for t in threads];[t.join() for t in threads];self.assertEqual(outputs.count(ResponseStatus.SUCCEEDED),20)
    def test_performance_1000_records(self):
        values=[Semantic(f"object-{i}",f"Object {i}") for i in range(1000)];started=time.perf_counter();engine=ready(values);self.assertLess(time.perf_counter()-started,2.0);self.assertEqual(engine.get_statistics(request()).statistics.total_records,1000)
    def test_structured_logging(self):
        logs=Records();ready(logger=logs);self.assertEqual(logs.items[0].engine_id,"ENG-012")
    def test_logging_failure_explicit(self):
        response=KnowledgeEngine(Source([Semantic()]),Storage(),log_sink=BadLogger()).initialize(request());self.assertEqual((response.status,response.errors[-1].code),(ResponseStatus.FAILED,"knowledge.logging.failed"))
    def test_rule_40_boundary(self):
        import taskgraph_knowledge.engine as module
        source=inspect.getsource(module);forbidden=("taskgraph_semantic_inventory","object_library","taskgraph_affordance","taskgraph_planner");self.assertFalse(any(value in source for value in forbidden))

if __name__=="__main__":unittest.main()
