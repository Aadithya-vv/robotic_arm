import ast,sys,unittest
from pathlib import Path
from types import MappingProxyType
SOURCE=Path(__file__).resolve().parents[2]/"Implementation"/"ENG-006_Memory_Engine"/"Source";sys.path.insert(0,str(SOURCE))
from taskgraph_memory import *  # noqa: E402,F403
class Log:
    def __init__(self,raises=False):self.records=[];self.raises=raises
    def record(self,record):
        if self.raises:raise RuntimeError("log failure")
        self.records.append(record)
def req(source="ENG-002",**changes):
    values=dict(request_id="request-1",correlation_id="correlation-1",source_identity=source,timestamp_context="controlled");values.update(changes);return MemoryRequest(**values)
def ready(**kwargs):
    engine=MemoryEngine(**kwargs);engine.initialize(req());return engine
def session(engine,owner="ENG-002",sid="session-1"):engine.create_session(req(owner),sid,owner);return engine
class MemoryTests(unittest.TestCase):
    def test_contract(self):self.assertIsInstance(MemoryEngine(),MemoryContract)
    def test_initialize(self):
        engine=MemoryEngine();response=engine.initialize(req());self.assertEqual(response.status,ResponseStatus.SUCCEEDED);self.assertEqual(engine.state,MemoryState.READY)
    def test_invalid_policy(self):self.assertEqual(MemoryEngine(policy=MemoryPolicy(-1,None)).initialize(req()).state,MemoryState.FAILED)
    def test_create_session(self):self.assertEqual(ready().create_session(req(),"session-1","ENG-002").session.owner_id,"ENG-002")
    def test_owner_must_match_requester(self):self.assertEqual(ready().create_session(req(),"s","other").errors[0].code,"memory.session.owner_mismatch")
    def test_duplicate_session(self):
        engine=session(ready());self.assertEqual(engine.create_session(req(),"session-1","ENG-002").errors[0].code,"memory.session.duplicate")
    def test_session_capacity(self):
        engine=ready(policy=MemoryPolicy(maximum_sessions=0));self.assertEqual(engine.create_session(req(),"s","ENG-002").errors[0].code,"memory.session.capacity")
    def test_put_and_get(self):
        engine=session(ready());stored=engine.put(req(),"session-1","plan",{"steps":[1,2]});fetched=engine.get(req(),"session-1","plan");self.assertEqual(stored.record,fetched.record)
    def test_value_is_deeply_immutable(self):
        record=session(ready()).put(req(),"session-1","x",{"nested":{"items":[1]}}).record;self.assertIsInstance(record.value,MappingProxyType);self.assertEqual(record.value["nested"]["items"],(1,))
    def test_custom_object_rejected(self):self.assertEqual(session(ready()).put(req(),"session-1","x",object()).errors[0].code,"memory.record.unsupported_value")
    def test_revision_increments_on_replace(self):
        engine=session(ready());engine.put(req(),"session-1","x",1);self.assertEqual(engine.put(req(),"session-1","x",2).record.revision,2)
    def test_entry_capacity_allows_replace_not_new(self):
        engine=session(ready(policy=MemoryPolicy(maximum_entries_per_session=1)));engine.put(req(),"session-1","x",1);self.assertEqual(engine.put(req(),"session-1","x",2).status,ResponseStatus.SUCCEEDED);self.assertEqual(engine.put(req(),"session-1","y",2).errors[0].code,"memory.record.capacity")
    def test_owner_only_record_rejects_other(self):
        engine=session(ready());engine.put(req(),"session-1","x",1);self.assertEqual(engine.get(req("ENG-003"),"session-1","x").errors[0].code,"memory.record.not_accessible")
    def test_shared_record_allows_other(self):
        engine=session(ready());engine.put(req(),"session-1","x",1,Visibility.SHARED);self.assertEqual(engine.get(req("ENG-003"),"session-1","x").status,ResponseStatus.SUCCEEDED)
    def test_non_owner_cannot_mutate(self):
        engine=session(ready());self.assertEqual(engine.put(req("ENG-003"),"session-1","x",1).errors[0].code,"memory.session.not_owner")
    def test_missing_session(self):self.assertEqual(ready().get(req(),"none","x").errors[0].code,"memory.session.not_found")
    def test_missing_record(self):self.assertEqual(session(ready()).get(req(),"session-1","x").errors[0].code,"memory.record.not_found")
    def test_delete(self):
        engine=session(ready());engine.put(req(),"session-1","x",1);self.assertEqual(engine.delete(req(),"session-1","x").status,ResponseStatus.SUCCEEDED);self.assertEqual(engine.get(req(),"session-1","x").status,ResponseStatus.REJECTED)
    def test_cleanup_clears_session(self):
        engine=session(ready());engine.put(req(),"session-1","x",1);self.assertEqual(engine.cleanup_session(req(),"session-1").status,ResponseStatus.SUCCEEDED);self.assertEqual(engine.snapshot(req(),"session-1").session.records,{})
    def test_close_session_removes_it(self):
        engine=session(ready());response=engine.close_session(req(),"session-1");self.assertEqual(response.session.state,SessionState.CLOSED);self.assertEqual(engine.snapshot(req(),"session-1").status,ResponseStatus.REJECTED)
    def test_session_snapshot_immutable(self):
        engine=session(ready());engine.put(req(),"session-1","x",1);snap=engine.snapshot(req(),"session-1").session;self.assertIsInstance(snap.records,MappingProxyType);engine.put(req(),"session-1","y",2);self.assertNotIn("y",snap.records)
    def test_global_snapshot_owner_scoped(self):
        engine=ready();engine.create_session(req("ENG-002"),"one","ENG-002");engine.create_session(req("ENG-003"),"two","ENG-003");snap=engine.snapshot(req("ENG-002")).snapshot;self.assertEqual(tuple(snap.sessions),("one",))
    def test_dispose_clears_and_is_terminal(self):
        engine=session(ready());response=engine.dispose(req());self.assertEqual(response.status,ResponseStatus.SUCCEEDED);self.assertEqual(engine.state,MemoryState.DISPOSED);self.assertEqual(engine.get(req(),"session-1","x").status,ResponseStatus.REJECTED)
    def test_operations_before_initialize_rejected(self):self.assertEqual(MemoryEngine().create_session(req(),"s","ENG-002").status,ResponseStatus.REJECTED)
    def test_invalid_envelope_and_version(self):self.assertEqual(len(MemoryEngine().initialize(req(request_id="",contract_version="2.0.0")).errors),2)
    def test_logging_explanations(self):
        log=Log();engine=MemoryEngine(log_sink=log);engine.initialize(req());self.assertTrue(log.records);self.assertTrue(engine.explanations)
    def test_logging_failure_explicit(self):self.assertEqual(MemoryEngine(log_sink=Log(True)).initialize(req()).status,ResponseStatus.FAILED)
    def test_determinism(self):self.assertEqual(MemoryEngine().initialize(req()).response_id,MemoryEngine().initialize(req()).response_id)
    def test_integration_identities_use_public_contract(self):
        engine=ready();engine.create_session(req("ENG-002"),"kernel","ENG-002");engine.create_session(req("ENG-005"),"events","ENG-005");self.assertEqual(set(engine.snapshot(req("ENG-002")).snapshot.sessions),{"kernel"})
    def test_rule_40(self):
        for path in SOURCE.rglob("*.py"):
            tree=ast.parse(path.read_text(encoding="utf-8"));imports=" ".join(ast.unparse(n) for n in ast.walk(tree) if isinstance(n,(ast.Import,ast.ImportFrom)))
            for forbidden in ("taskgraph_bootstrap","taskgraph_kernel","taskgraph_configuration","taskgraph_registry","taskgraph_event_bus","Implementation"):self.assertNotIn(forbidden,imports)
if __name__=="__main__":unittest.main()
