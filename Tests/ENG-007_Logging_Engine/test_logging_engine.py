import ast,sys,unittest
from pathlib import Path
from types import MappingProxyType
SOURCE=Path(__file__).resolve().parents[2]/"Implementation"/"ENG-007_Logging_Engine"/"Source";sys.path.insert(0,str(SOURCE))
from taskgraph_logging import *  # noqa:E402,F403
class Sink:
    def __init__(self,write=None,flush=None,raises=None):self.records=[];self.write_result=write or SinkResult(True);self.flush_result=flush or SinkResult(True);self.raises=raises
    def write(self,record):
        if self.raises=="write":raise RuntimeError("write")
        self.records.append(record);return self.write_result
    def flush(self):
        if self.raises=="flush":raise RuntimeError("flush")
        return self.flush_result
class ForeignRecord:
    def __init__(self,severity="info"):
        self.engine_id="ENG-001";self.category="lifecycle";self.severity=severity;self.correlation_id="corr-1";self.message="started";self.metadata={"safe":True}
def req(**changes):
    values=dict(request_id="request-1",correlation_id="corr-1",source_identity="test",timestamp_context="controlled");values.update(changes);return LoggingRequest(**values)
def entry(**changes):
    values=dict(source_identity="ENG-001",category="lifecycle",severity=Severity.INFO,correlation_id="corr-1",message="started",timestamp_context="controlled",metadata={"state":"ready"});values.update(changes);return LogInput(**values)
def ready(**kwargs):
    engine=LoggingEngine(**kwargs);engine.initialize(req());return engine
class LoggingTests(unittest.TestCase):
    def test_contract(self):self.assertIsInstance(LoggingEngine(),LoggingContract)
    def test_initialize(self):
        engine=LoggingEngine();response=engine.initialize(req());self.assertEqual(response.status,ResponseStatus.SUCCEEDED);self.assertEqual(engine.state,LoggingState.READY)
    def test_invalid_policy_capacity(self):self.assertEqual(LoggingEngine(policy=LoggingPolicy(maximum_records=0)).initialize(req()).state,LoggingState.DEGRADED)
    def test_invalid_policy_categories(self):self.assertEqual(LoggingEngine(policy=LoggingPolicy(allowed_categories=("x","x"))).initialize(req()).status,ResponseStatus.FAILED)
    def test_record_structured_event(self):
        response=ready().record_log(req(),entry());self.assertEqual(response.status,ResponseStatus.SUCCEEDED);self.assertEqual(response.record.category,"lifecycle")
    def test_record_error_and_diagnostic_categories(self):
        engine=ready();one=engine.record_log(req(),entry(category="error",severity=Severity.ERROR));two=engine.record_log(req(),entry(category="diagnostic",message="health"));self.assertTrue(one.record);self.assertTrue(two.record)
    def test_record_is_immutable(self):
        record=ready().record_log(req(),entry(metadata={"nested":{"items":[1]}})).record;self.assertIsInstance(record.metadata,MappingProxyType);self.assertEqual(record.metadata["nested"]["items"],(1,))
    def test_severity_normalization(self):self.assertEqual(ready().record_log(req(),entry(severity="warn")).record.severity,Severity.WARNING)
    def test_invalid_severity(self):self.assertEqual(ready().record_log(req(),entry(severity="nope")).errors[0].code,"logging.record.severity")
    def test_invalid_record_fields(self):self.assertEqual(ready().record_log(req(),entry(message="")).status,ResponseStatus.REJECTED)
    def test_correlation_mismatch(self):self.assertEqual(ready().record_log(req(),entry(correlation_id="other")).errors[0].code,"logging.record.correlation")
    def test_minimum_severity_filter(self):
        engine=ready(policy=LoggingPolicy(minimum_severity=Severity.WARNING));response=engine.record_log(req(),entry(severity=Severity.INFO));self.assertEqual(response.status,ResponseStatus.SUCCEEDED);self.assertTrue(response.metadata["filtered"]);self.assertEqual(engine.query(req()).snapshot.records,())
    def test_category_filter(self):
        engine=ready(policy=LoggingPolicy(allowed_categories=("error",)));self.assertTrue(engine.record_log(req(),entry()).metadata["filtered"])
    def test_capacity_rejects_without_eviction(self):
        engine=ready(policy=LoggingPolicy(maximum_records=1));engine.record_log(req(),entry());response=engine.record_log(req(request_id="two"),entry(message="two"));self.assertEqual(response.errors[0].code,"logging.records.capacity");self.assertEqual(len(engine.query(req()).snapshot.records),1)
    def test_sink_receives_canonical_record(self):
        sink=Sink();engine=ready(sink=sink);engine.record_log(req(),entry());self.assertIsInstance(sink.records[0],StructuredLogRecord)
    def test_sink_rejection_degrades(self):
        response=ready(sink=Sink(write=SinkResult(False,"disk unavailable"))).record_log(req(),entry());self.assertEqual(response.status,ResponseStatus.FAILED);self.assertEqual(response.state,LoggingState.DEGRADED)
    def test_sink_exception_degrades(self):self.assertEqual(ready(sink=Sink(raises="write")).record_log(req(),entry()).state,LoggingState.DEGRADED)
    def test_structural_record_adapter(self):
        engine=ready();engine.record(ForeignRecord());self.assertEqual(engine.query(req()).snapshot.records[0].source_identity,"ENG-001")
    def test_structural_adapter_rejects_bad_record(self):
        engine=ready()
        with self.assertRaises(LoggingDeliveryError):engine.record(object())
    def test_structural_adapter_accepts_policy_filtered_record(self):
        engine=ready(policy=LoggingPolicy(minimum_severity=Severity.WARNING))
        engine.record(ForeignRecord("info"));self.assertEqual(engine.query(req()).snapshot.records,())
    def test_query_filters_severity_category_source_and_correlation(self):
        engine=ready();engine.record_log(req(),entry());engine.record_log(req(request_id="two"),entry(source_identity="ENG-002",category="diagnostic",severity=Severity.ERROR,message="bad"));f=LogFilter(Severity.WARNING,("diagnostic",),("ENG-002",),"corr-1");self.assertEqual(len(engine.query(req(),f).snapshot.records),1)
    def test_query_snapshot_counters(self):
        engine=ready(policy=LoggingPolicy(minimum_severity=Severity.WARNING));engine.record_log(req(),entry(severity=Severity.ERROR));engine.record_log(req(request_id="filtered"),entry(severity=Severity.INFO));snapshot=engine.query(req()).snapshot;self.assertEqual((snapshot.accepted_count,snapshot.filtered_count),(1,1))
    def test_snapshot_is_stable(self):
        engine=ready();engine.record_log(req(),entry());first=engine.query(req()).snapshot;engine.record_log(req(request_id="two"),entry(message="two"));self.assertEqual(len(first.records),1)
    def test_format_is_deterministic(self):
        engine=ready();engine.record_log(req(),entry());formatted=engine.format(req()).formatted_records[0];self.assertEqual(formatted,"1|info|lifecycle|ENG-001|corr-1|started")
    def test_stop_flushes(self):
        sink=Sink();engine=ready(sink=sink);response=engine.stop(req());self.assertEqual(response.status,ResponseStatus.SUCCEEDED);self.assertEqual(engine.state,LoggingState.STOPPED)
    def test_flush_failure_degrades(self):self.assertEqual(ready(sink=Sink(flush=SinkResult(False,"no"))).stop(req()).state,LoggingState.DEGRADED)
    def test_query_after_stop_supported(self):
        engine=ready();engine.record_log(req(),entry());engine.stop(req());self.assertEqual(len(engine.query(req()).snapshot.records),1)
    def test_record_after_stop_rejected(self):
        engine=ready();engine.stop(req());self.assertEqual(engine.record_log(req(),entry()).status,ResponseStatus.REJECTED)
    def test_invalid_request_version(self):self.assertEqual(len(LoggingEngine().initialize(req(request_id="",contract_version="2.0.0")).errors),2)
    def test_explanations_generated(self):
        engine=ready();engine.record_log(req(),entry());self.assertTrue(engine.explanations)
    def test_determinism(self):self.assertEqual(LoggingEngine().initialize(req()).response_id,LoggingEngine().initialize(req()).response_id)
    def test_prior_engine_log_shapes_are_structural(self):
        engine=ready()
        for identity in ("ENG-001","ENG-002","ENG-003","ENG-004","ENG-005","ENG-006"):
            record=ForeignRecord();record.engine_id=identity;engine.record(record)
        self.assertEqual(len(engine.query(req()).snapshot.records),6)
    def test_rule_40(self):
        for path in SOURCE.rglob("*.py"):
            tree=ast.parse(path.read_text(encoding="utf-8"));imports=" ".join(ast.unparse(n) for n in ast.walk(tree) if isinstance(n,(ast.Import,ast.ImportFrom)))
            for forbidden in ("taskgraph_bootstrap","taskgraph_kernel","taskgraph_configuration","taskgraph_registry","taskgraph_event_bus","taskgraph_memory","Implementation"):self.assertNotIn(forbidden,imports)
if __name__=="__main__":unittest.main()
