"""ENG-011 unit, integration, compatibility, and performance tests."""
from __future__ import annotations
import inspect,json,tempfile,threading,time,unittest
from pathlib import Path
from taskgraph_semantic_inventory import *

class Source:
    def __init__(self,items=()):self.items=list(items)
    def get_all(self):return tuple(self.items)
class MemoryStorage:
    def __init__(self,payload=None):self.payload=payload;self.saves=0
    def load(self):return self.payload
    def save(self,payload):self.payload=plain(payload);self.saves+=1
class Records:
    def __init__(self):self.items=[]
    def record(self,item):self.items.append(item)
class BadLogger:
    def record(self,item):raise RuntimeError("unavailable")
def record(identifier="object-1",name="Spoon",**changes):
    value={"object_id":identifier,"name":name,"category":"Utensil","description":"A dining spoon","aliases":["teaspoon"],"descriptors":[["geometry",[1,2]]],"thumbnail":{"path":"one.png","instance_images":["one.png","two.png"]},"recognition_history":[{"confidence":.8}],"average_confidence":.8,"created":"2026-01-01","updated":"2026-01-02","videos":["demo.mp4"],"frames":["frame-1"],"tags":["metal"],"relationships":[],"recognition_statistics":{"matches":2,"misses":0}}
    value.update(changes);return value
def request(identifier="request-1"):return SemanticRequest(identifier,"correlation-1","test")
def ready(items=None,storage=None):
    engine=SemanticInventoryEngine(Source(items if items is not None else [record()]),storage or MemoryStorage(),clock=lambda:"now");response=engine.initialize(request());assert response.status is ResponseStatus.SUCCEEDED;return engine

class SemanticInventoryTests(unittest.TestCase):
    def test_public_contract(self):self.assertIsInstance(ready(),SemanticInventoryContract)
    def test_lifecycle(self):
        engine=ready();self.assertEqual(engine.state,InventoryState.AVAILABLE);self.assertEqual(engine.close(request("close")).state,InventoryState.CLOSED)
    def test_invalid_transition(self):self.assertEqual(ready().initialize(request()).status,ResponseStatus.REJECTED)
    def test_normalization(self):
        item=ready().get_object(request(),"object-1").object;self.assertEqual((item.object_name,item.category,item.aliases),("Spoon","Utensil",("teaspoon",)))
    def test_complete_model(self):
        item=ready().get_object(request(),"object-1").object
        for field in ("visual_descriptors","instance_frames","instance_images","recognition_history","relationships","affordances","semantic_score","metadata"):self.assertTrue(hasattr(item,field))
    def test_missing_object(self):self.assertEqual(ready().get_object(request(),"missing").status,ResponseStatus.REJECTED)
    def test_name_search(self):self.assertEqual(ready().search(request(),query="spoo").inventory.statistics.total_objects,1)
    def test_description_search(self):self.assertEqual(ready().search(request(),query="dining").inventory.statistics.total_objects,1)
    def test_category_search(self):self.assertEqual(ready().search(request(),category="utensil").inventory.statistics.total_objects,1)
    def test_alias_search(self):self.assertEqual(ready().search(request(),alias="tea").inventory.statistics.total_objects,1)
    def test_tag_search(self):self.assertEqual(ready().search(request(),tag="metal").inventory.statistics.total_objects,1)
    def test_statistics(self):
        stats=ready([record(),record("object-2","Fork",tags=["metal","table"])]).get_statistics(request()).statistics;self.assertEqual((stats.total_objects,stats.categories["Utensil"],stats.tags["metal"]),(2,2,2))
    def test_export_serializes(self):json.dumps(plain(ready().export_inventory(request()).export))
    def test_automatic_migration_rewrites_legacy_snapshot(self):
        storage=MemoryStorage({"version":"0.1","objects":[]});ready(storage=storage);self.assertEqual((storage.payload["version"],storage.saves),("1.0",1))
    def test_json_storage_atomic_roundtrip(self):
        with tempfile.TemporaryDirectory() as folder:
            storage=JsonInventoryStorage(Path(folder)/"semantic.json");ready(storage=storage);self.assertEqual(storage.load()["objects"][0]["object_id"],"object-1")
    def test_refresh_tracks_source_without_mutating_it(self):
        source=Source([record()]);engine=SemanticInventoryEngine(source,MemoryStorage());engine.initialize(request());source.items.append(record("object-2","Fork"));self.assertEqual(engine.refresh(request()).inventory.statistics.total_objects,2)
    def test_invalid_source_record_is_explicit_failure(self):
        engine=SemanticInventoryEngine(Source([{"name":"bad"}]),MemoryStorage());response=engine.initialize(request());self.assertEqual((response.status,response.state),(ResponseStatus.FAILED,InventoryState.INVALID))
    def test_thread_safe_reads(self):
        engine=ready();outputs=[];threads=[threading.Thread(target=lambda:outputs.append(engine.search(request(),query="spoon").status)) for _ in range(20)]
        [t.start() for t in threads];[t.join() for t in threads];self.assertEqual(outputs.count(ResponseStatus.SUCCEEDED),20)
    def test_performance_1000_objects(self):
        items=[record(f"object-{i}",f"Object {i}") for i in range(1000)];started=time.perf_counter();engine=ready(items);elapsed=time.perf_counter()-started;self.assertEqual(engine.get_statistics(request()).statistics.total_objects,1000);self.assertLess(elapsed,2.0)
    def test_object_library_compatibility_shape(self):self.assertEqual(ready([record(tags=(),aliases=(),videos=(),frames=())]).get_statistics(request()).status,ResponseStatus.SUCCEEDED)
    def test_rule_40_import_boundary(self):
        import taskgraph_semantic_inventory.engine as module
        source=inspect.getsource(module);self.assertNotIn("object_library",source);self.assertNotIn("taskgraph_scene.engine",source);self.assertNotIn("taskgraph_knowledge",source)
    def test_structured_logging(self):
        records=Records();engine=SemanticInventoryEngine(Source([record()]),MemoryStorage(),log_sink=records);engine.initialize(request());self.assertEqual(records.items[0].engine_id,"ENG-011")
    def test_logging_failure_is_explicit(self):
        response=SemanticInventoryEngine(Source([record()]),MemoryStorage(),log_sink=BadLogger()).initialize(request());self.assertEqual((response.status,response.errors[-1].code),(ResponseStatus.FAILED,"semantic.logging.failed"))

if __name__=="__main__":unittest.main()
