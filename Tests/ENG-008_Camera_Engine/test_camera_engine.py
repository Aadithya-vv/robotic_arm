import ast,sys,threading,unittest
from pathlib import Path
from unittest.mock import patch
SOURCE=Path(__file__).resolve().parents[2]/"Implementation"/"ENG-008_Camera_Engine"/"Source";sys.path.insert(0,str(SOURCE))
from taskgraph_camera import *  # noqa:E402,F403
class Log:
    def __init__(self,raises=False):self.records=[];self.raises=raises
    def record(self,record):
        if self.raises:raise RuntimeError("logging down")
        self.records.append(record)
def req(**changes):
    values=dict(request_id="request-1",correlation_id="corr-1",source_identity="test",timestamp_context="controlled");values.update(changes);return CameraRequest(**values)
def config(**changes):
    values=dict(provider_id="mock",device_id="mock-camera-0",width=2,height=2,frames_per_second=30,pixel_format="bgr8");values.update(changes);return CameraConfiguration(**values)
def engine_with(provider=None,**kwargs):return CameraEngine((provider or MockCameraProvider(frames=(b"one",b"two")),),**kwargs)
def ready(provider=None,**kwargs):
    engine=engine_with(provider,**kwargs);engine.initialize(req(),config(provider_id=(provider.provider_id if provider else "mock"),device_id=(provider._device_id if provider and hasattr(provider,"_device_id") else "mock-camera-0")));return engine
class CameraTests(unittest.TestCase):
    def test_public_contract(self):self.assertIsInstance(CameraEngine(),CameraContract)
    def test_default_catalog_is_hardware_independent(self):self.assertEqual(CameraProviderCatalog.default().provider_ids,("mock",))
    def test_opencv_catalog_is_opt_in(self):self.assertEqual(CameraProviderCatalog.default(include_opencv=True).provider_ids,("mock","opencv"))
    def test_discovery_finds_mock_without_webcam(self):
        response=CameraEngine().discover(req());self.assertEqual(response.status,ResponseStatus.SUCCEEDED);self.assertIn("mock-camera-0",{x.device_id for x in response.devices})
    def test_mock_discovery_metadata(self):self.assertTrue(MockCameraProvider().discover().devices[0].metadata["virtual"])
    def test_initialize_mock(self):
        engine=engine_with();response=engine.initialize(req(),config());self.assertEqual(response.status,ResponseStatus.SUCCEEDED);self.assertEqual(engine.state,CameraState.READY)
    def test_provider_selection(self):
        a=MockCameraProvider(provider_id="a",device_id="a0");b=MockCameraProvider(provider_id="b",device_id="b0");engine=CameraEngine((a,b));response=engine.initialize(req(),config(provider_id="b",device_id="b0"));self.assertEqual(response.status,ResponseStatus.SUCCEEDED);self.assertEqual(engine.diagnostics(req()).diagnostics.provider_id,"b")
    def test_unknown_provider_rejected(self):self.assertEqual(engine_with().initialize(req(),config(provider_id="missing")).errors[0].code,"camera.provider.not_found")
    def test_invalid_provider_contract(self):
        class Bad:
            provider_id="bad"
        response=CameraEngine((Bad(),)).discover(req());self.assertEqual(response.errors[0].code,"camera.provider.catalog_invalid")
    def test_duplicate_provider_rejected(self):self.assertEqual(CameraEngine((MockCameraProvider(),MockCameraProvider())).discover(req()).errors[0].code,"camera.provider.catalog_invalid")
    def test_connection_failure(self):
        provider=MockCameraProvider(fail_open=True);response=engine_with(provider).initialize(req(),config());self.assertEqual(response.status,ResponseStatus.FAILED);self.assertEqual(response.state,CameraState.FAILED)
    def test_wrong_device_connection_failure(self):self.assertEqual(engine_with().initialize(req(),config(device_id="wrong")).state,CameraState.FAILED)
    def test_configuration_type_validation(self):self.assertEqual(engine_with().initialize(req(),object()).errors[0].code,"camera.configuration.invalid_contract")
    def test_configuration_dimension_validation(self):self.assertEqual(engine_with().initialize(req(),config(width=0)).status,ResponseStatus.REJECTED)
    def test_configuration_bool_not_integer(self):self.assertEqual(engine_with().initialize(req(),config(width=True)).status,ResponseStatus.REJECTED)
    def test_acquire_frame(self):
        response=ready().acquire(req());self.assertEqual(response.status,ResponseStatus.SUCCEEDED);self.assertEqual(response.observation.data,b"one");self.assertEqual(response.observation.sequence,1)
    def test_repeated_acquisition(self):
        engine=ready();values=[engine.acquire(req(request_id=f"r-{i}")).observation for i in range(3)];self.assertEqual([x.sequence for x in values],[1,2,3]);self.assertEqual([x.data for x in values],[b"one",b"two",b"one"])
    def test_observation_is_immutable_bytes(self):
        source=bytearray(b"abc");record=ready(MockCameraProvider(frames=(source,))).acquire(req()).observation;source[0]=0;self.assertEqual(record.data,b"abc")
    def test_acquire_before_initialize_rejected(self):self.assertEqual(engine_with().acquire(req()).status,ResponseStatus.REJECTED)
    def test_capture_failure_enters_failed(self):
        engine=ready(MockCameraProvider(fail_acquire_at=0));response=engine.acquire(req());self.assertEqual(response.state,CameraState.FAILED);self.assertEqual(response.errors[0].code,"mock.capture.failed")
    def test_exhausted_mock_frames_fail(self):
        engine=ready(MockCameraProvider(frames=(b"one",),repeat=False));engine.acquire(req());self.assertEqual(engine.acquire(req(request_id="two")).state,CameraState.FAILED)
    def test_empty_provider_frame_rejected(self):
        class Empty(MockCameraProvider):
            def acquire(self):return ProviderFrame(True,b"",1,1,3,"bgr8")
        self.assertEqual(ready(Empty()).acquire(req()).errors[0].code,"camera.capture.invalid_frame")
    def test_provider_acquire_exception_structured(self):
        class Raising(MockCameraProvider):
            def acquire(self):raise RuntimeError("device")
        self.assertEqual(ready(Raising()).acquire(req()).errors[0].code,"camera.capture.provider_exception")
    def test_diagnostics_closed(self):
        value=engine_with().diagnostics(req()).diagnostics;self.assertEqual(value.state,CameraState.CLOSED);self.assertEqual(value.frames_acquired,0)
    def test_diagnostics_ready_and_count(self):
        engine=ready();engine.acquire(req());value=engine.diagnostics(req()).diagnostics;self.assertEqual(value.frames_acquired,1);self.assertTrue(value.provider_diagnostics["open"])
    def test_shutdown(self):
        engine=ready();response=engine.shutdown(req());self.assertEqual(response.status,ResponseStatus.SUCCEEDED);self.assertEqual(engine.state,CameraState.CLOSED)
    def test_shutdown_after_failure_cleans_provider(self):
        provider=MockCameraProvider(fail_acquire_at=0);engine=ready(provider);engine.acquire(req());self.assertEqual(engine.shutdown(req()).state,CameraState.CLOSED)
    def test_shutdown_before_initialize_rejected(self):self.assertEqual(engine_with().shutdown(req()).status,ResponseStatus.REJECTED)
    def test_reinitialize_after_shutdown(self):
        engine=ready();engine.shutdown(req());self.assertEqual(engine.initialize(req(request_id="again"),config()).status,ResponseStatus.SUCCEEDED)
    def test_discovery_while_ready_rejected(self):self.assertEqual(ready().discover(req()).status,ResponseStatus.REJECTED)
    def test_invalid_request_and_version(self):self.assertEqual(len(engine_with().discover(req(request_id="",contract_version="2.0.0")).errors),2)
    def test_logging_and_explanations(self):
        log=Log();engine=engine_with(log_sink=log);engine.initialize(req(),config());self.assertTrue(log.records);self.assertTrue(engine.explanations)
    def test_logging_failure_is_explicit(self):self.assertEqual(engine_with(log_sink=Log(True)).initialize(req(),config()).status,ResponseStatus.FAILED)
    def test_thread_safe_acquisition_sequences(self):
        engine=ready(MockCameraProvider(frames=(b"x",)));sequences=[];lock=threading.Lock()
        def capture(i):
            response=engine.acquire(req(request_id=f"thread-{i}"))
            with lock:sequences.append(response.observation.sequence)
        threads=[threading.Thread(target=capture,args=(i,)) for i in range(20)]
        for thread in threads:thread.start()
        for thread in threads:thread.join()
        self.assertEqual(sorted(sequences),list(range(1,21)))
    def test_deterministic_controlled_run(self):
        one=ready().acquire(req()).observation;two=ready().acquire(req()).observation;self.assertEqual((one.observation_id,one.data),(two.observation_id,two.data))
    def test_opencv_unavailable_is_explicit(self):
        provider=OpenCVCameraProvider()
        with patch("taskgraph_camera.providers.import_module",side_effect=ImportError):
            result=provider.discover();opened=provider.open(config(provider_id="opencv",device_id="0"))
        self.assertFalse(result.succeeded);self.assertEqual(result.error_code,"opencv.unavailable");self.assertFalse(opened.succeeded)
    def test_rule_40_no_core_or_cv2_import(self):
        for path in SOURCE.rglob("*.py"):
            tree=ast.parse(path.read_text(encoding="utf-8"));imports=" ".join(ast.unparse(n) for n in ast.walk(tree) if isinstance(n,(ast.Import,ast.ImportFrom)))
            for forbidden in ("taskgraph_bootstrap","taskgraph_kernel","taskgraph_configuration","taskgraph_registry","taskgraph_event_bus","taskgraph_memory","taskgraph_logging","cv2","Implementation"):self.assertNotIn(forbidden,imports)
if __name__=="__main__":unittest.main()
