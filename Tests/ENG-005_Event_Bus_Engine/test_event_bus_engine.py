import ast, sys, unittest
from pathlib import Path
from types import MappingProxyType
SOURCE=Path(__file__).resolve().parents[2]/"Implementation"/"ENG-005_Event_Bus_Engine"/"Source";sys.path.insert(0,str(SOURCE))
from taskgraph_event_bus import *  # noqa: E402,F403

class Handler:
    def __init__(self,result=None,raises=False):self.events=[];self.result=result or DeliveryResult(True);self.raises=raises
    def deliver(self,event):
        self.events.append(event)
        if self.raises:raise RuntimeError("handler failure")
        return self.result
class Log:
    def __init__(self,raises=False):self.records=[];self.raises=raises
    def record(self,record):
        if self.raises:raise RuntimeError("log failure")
        self.records.append(record)
def req(**changes):
    values=dict(request_id="request-1",correlation_id="correlation-1",source_identity="test",timestamp_context="controlled");values.update(changes);return EventBusRequest(**values)
def pub(pid="ENG-003",topics=("configuration.changed",)):return PublisherRegistration(pid,topics)
def sub(sid="sub-1",topic="configuration.changed"):return Subscription(sid,"ENG-002",topic)
def event(**changes):
    values=dict(event_id="event-1",topic="configuration.changed",publisher_id="ENG-003",correlation_id="correlation-1",payload={"revision":2});values.update(changes);return PlatformEvent(**values)
def running():
    engine=EventBusEngine();engine.start(req());return engine

class EventBusTests(unittest.TestCase):
    def test_contract(self):self.assertIsInstance(EventBusEngine(),EventBusContract)
    def test_start(self):
        engine=EventBusEngine();response=engine.start(req());self.assertEqual(response.status,ResponseStatus.SUCCEEDED);self.assertEqual(engine.state,EventBusState.ACCEPTING_EVENTS)
    def test_invalid_policy(self):self.assertEqual(EventBusEngine(policy=EventBusPolicy(-1,None)).start(req()).state,EventBusState.FAILED)
    def test_register_publisher(self):self.assertEqual(running().register_publisher(req(),pub()).publisher.publisher_id,"ENG-003")
    def test_duplicate_publisher(self):
        engine=running();engine.register_publisher(req(),pub());self.assertEqual(engine.register_publisher(req(request_id="two"),pub()).errors[0].code,"event_bus.publisher.duplicate")
    def test_publisher_validation(self):self.assertEqual(running().register_publisher(req(),pub("",())).status,ResponseStatus.REJECTED)
    def test_publisher_capacity(self):
        engine=EventBusEngine(policy=EventBusPolicy(maximum_publishers=0));engine.start(req());self.assertEqual(engine.register_publisher(req(),pub()).errors[0].code,"event_bus.publisher.capacity")
    def test_unregister_publisher(self):
        engine=running();engine.register_publisher(req(),pub());self.assertEqual(engine.unregister_publisher(req(),"ENG-003").status,ResponseStatus.SUCCEEDED)
    def test_subscribe(self):self.assertEqual(running().subscribe(req(),sub(),Handler()).status,ResponseStatus.SUCCEEDED)
    def test_duplicate_subscription(self):
        engine=running();engine.subscribe(req(),sub(),Handler());self.assertEqual(engine.subscribe(req(),sub(),Handler()).errors[0].code,"event_bus.subscription.duplicate")
    def test_invalid_handler(self):self.assertEqual(running().subscribe(req(),sub(),object()).errors[0].code,"event_bus.subscription.invalid_handler")
    def test_subscription_capacity(self):
        engine=EventBusEngine(policy=EventBusPolicy(maximum_subscriptions=0));engine.start(req());self.assertEqual(engine.subscribe(req(),sub(),Handler()).errors[0].code,"event_bus.subscription.capacity")
    def test_unsubscribe(self):
        engine=running();engine.subscribe(req(),sub(),Handler());self.assertEqual(engine.unsubscribe(req(),"sub-1").status,ResponseStatus.SUCCEEDED)
    def test_publish_routes_deterministically(self):
        engine=running();engine.register_publisher(req(),pub());calls=[]
        class Ordered(Handler):
            def __init__(self,name):super().__init__();self.name=name
            def deliver(self,event):calls.append(self.name);return super().deliver(event)
        engine.subscribe(req(),sub("z"),Ordered("z"));engine.subscribe(req(),sub("a"),Ordered("a"));response=engine.publish(req(),event())
        self.assertEqual(calls,["a","z"]);self.assertEqual(response.status,ResponseStatus.SUCCEEDED)
    def test_no_subscribers_is_successful_routing(self):
        engine=running();engine.register_publisher(req(),pub());self.assertEqual(engine.publish(req(),event()).delivery.outcomes,())
    def test_unknown_publisher(self):self.assertEqual(running().publish(req(),event()).errors[0].code,"event_bus.publish.publisher_unknown")
    def test_unauthorized_topic(self):
        engine=running();engine.register_publisher(req(),pub(topics=("other",)));self.assertEqual(engine.publish(req(),event()).errors[0].code,"event_bus.publish.topic_not_authorized")
    def test_handler_exception_is_failed(self):
        engine=running();engine.register_publisher(req(),pub());engine.subscribe(req(),sub(),Handler(raises=True));self.assertEqual(engine.publish(req(),event()).status,ResponseStatus.FAILED)
    def test_mixed_delivery_is_partial(self):
        engine=running();engine.register_publisher(req(),pub());engine.subscribe(req(),sub("one"),Handler());engine.subscribe(req(),sub("two"),Handler(DeliveryResult(False,error_summary="no")));self.assertEqual(engine.publish(req(),event()).status,ResponseStatus.PARTIAL)
    def test_invalid_delivery_result(self):
        class Bad:
            def deliver(self,event):return True
        engine=running();engine.register_publisher(req(),pub());engine.subscribe(req(),sub(),Bad());self.assertEqual(engine.publish(req(),event()).errors[0].code,"event_bus.delivery.invalid_result")
    def test_event_correlation_validation(self):
        engine=running();engine.register_publisher(req(),pub());self.assertEqual(engine.publish(req(),event(correlation_id="other")).status,ResponseStatus.REJECTED)
    def test_payload_is_deeply_immutable(self):
        value=event(payload={"nested":{"items":[1,2]}});self.assertIsInstance(value.payload,MappingProxyType);self.assertEqual(value.payload["nested"]["items"],(1,2))
    def test_snapshot_hides_handlers(self):
        engine=running();engine.subscribe(req(),sub(),Handler());snapshot=engine.snapshot(req()).snapshot;self.assertEqual(tuple(snapshot.subscriptions),("sub-1",));self.assertFalse(hasattr(snapshot.subscriptions["sub-1"],"deliver"))
    def test_stop_clears_state(self):
        engine=running();engine.register_publisher(req(),pub());engine.subscribe(req(),sub(),Handler());response=engine.stop(req());self.assertEqual(response.status,ResponseStatus.SUCCEEDED);self.assertEqual(engine.state,EventBusState.STOPPED)
    def test_operations_after_stop_rejected(self):
        engine=running();engine.stop(req());self.assertEqual(engine.publish(req(),event()).status,ResponseStatus.REJECTED)
    def test_bad_request_version(self):self.assertEqual(EventBusEngine().start(req(request_id="",contract_version="2.0.0")).status,ResponseStatus.REJECTED)
    def test_logging_and_explanations(self):
        log=Log();engine=EventBusEngine(log_sink=log);engine.start(req());self.assertTrue(log.records);self.assertTrue(engine.explanations)
    def test_logging_failure(self):self.assertEqual(EventBusEngine(log_sink=Log(True)).start(req()).status,ResponseStatus.FAILED)
    def test_determinism(self):self.assertEqual(EventBusEngine().start(req()).response_id,EventBusEngine().start(req()).response_id)
    def test_rule_40(self):
        for path in SOURCE.rglob("*.py"):
            tree=ast.parse(path.read_text(encoding="utf-8"));imports=" ".join(ast.unparse(n) for n in ast.walk(tree) if isinstance(n,(ast.Import,ast.ImportFrom)))
            for forbidden in ("taskgraph_bootstrap","taskgraph_kernel","taskgraph_configuration","taskgraph_registry","Implementation"):self.assertNotIn(forbidden,imports)

if __name__=="__main__":unittest.main()
