"""Isolated ENG-009 contract, lifecycle, pipeline, and boundary tests."""
from __future__ import annotations

import inspect
import threading
import unittest
from dataclasses import dataclass, FrozenInstanceError
from types import MappingProxyType
from unittest.mock import patch

from taskgraph_vision import (
    BoundingRegion, BytePreprocessor, CameraObservationContract,
    DefaultVisionProcessor, FeatureDescriptor, ImageFrame, LogRecord,
    MockVisionProcessor, OpenCVVisionProcessor, ProcessorResult,
    ResponseStatus, VisionConfiguration, VisionContract, VisionEngine,
    VisionProcessorCatalog, VisionRequest, VisionState, VisualObject,
)


@dataclass(frozen=True)
class Frame:
    observation_id: str = "frame-1"
    correlation_id: str = "corr-1"
    data: bytes = bytes((0, 64, 128, 255))
    width: int = 2
    height: int = 2
    channels: int = 1
    pixel_format: str = "gray8"
    timestamp_context: str | None = "t-1"
    metadata: dict = None

    def __post_init__(self):
        object.__setattr__(self, "metadata", {} if self.metadata is None else self.metadata)


def request(**changes):
    values = {"request_id": "req-1", "correlation_id": "corr-1", "source_identity": "test"}
    values.update(changes)
    return VisionRequest(**values)


def ready(processor=None, **configuration):
    processors = [processor] if processor else [MockVisionProcessor()]
    engine = VisionEngine(processors, clock=iter((1.0, 1.001) * 100).__next__)
    response = engine.initialize(request(), VisionConfiguration(processor_id=processors[0].processor_id, **configuration))
    if response.status is not ResponseStatus.SUCCEEDED:
        raise AssertionError(response)
    return engine


class Records:
    def __init__(self): self.items = []
    def record(self, item): self.items.append(item)


class BadLogger:
    def record(self, item): raise RuntimeError("log unavailable")


class InvalidProcessor:
    processor_id = "invalid"


class RaisingProcessor(MockVisionProcessor):
    processor_id = "raising"
    def process(self, observation): raise RuntimeError("controlled")


class BadResultProcessor(MockVisionProcessor):
    processor_id = "bad-result"
    def process(self, observation): return object()


class BadConfidenceProcessor(MockVisionProcessor):
    processor_id = "bad-confidence"
    def process(self, observation):
        return ProcessorResult(True, (VisualObject("x", BoundingRegion(0, 0, 1, 1), 1.1),))


class BadRegionProcessor(MockVisionProcessor):
    processor_id = "bad-region"
    def process(self, observation):
        return ProcessorResult(True, (VisualObject("x", BoundingRegion(2, 2, 2, 2), 0.8),))


class VisionTests(unittest.TestCase):
    def test_01_public_contract(self):
        self.assertIsInstance(VisionEngine(), VisionContract)

    def test_02_camera_observation_contract(self):
        self.assertIsInstance(Frame(), CameraObservationContract)

    def test_04_default_catalog_is_hardware_independent(self):
        self.assertEqual(VisionProcessorCatalog.default().processor_ids, ("default", "mock"))

    def test_06_initialize_default(self):
        response = VisionEngine().initialize(request(), VisionConfiguration())
        self.assertEqual((response.status, response.state), (ResponseStatus.SUCCEEDED, VisionState.READY))

    def test_07_initialize_mock(self):
        response = VisionEngine([MockVisionProcessor()]).initialize(request(), VisionConfiguration("mock"))
        self.assertEqual(response.status, ResponseStatus.SUCCEEDED)

    def test_08_unknown_processor(self):
        response = VisionEngine().initialize(request(), VisionConfiguration("missing"))
        self.assertEqual(response.errors[0].code, "vision.processor.not_found")

    def test_09_invalid_processor_contract(self):
        response = VisionEngine([InvalidProcessor()]).initialize(request(), VisionConfiguration("invalid"))
        self.assertEqual(response.errors[0].code, "vision.processor.catalog_invalid")

    def test_10_duplicate_processor(self):
        catalog = VisionProcessorCatalog([MockVisionProcessor(), MockVisionProcessor()])
        self.assertIn("duplicate processor_id", catalog.errors[0])

    def test_11_processor_initialization_failure(self):
        response = VisionEngine([MockVisionProcessor(fail_initialize=True)]).initialize(request(), VisionConfiguration("mock"))
        self.assertEqual((response.status, response.state), (ResponseStatus.FAILED, VisionState.FAILED))

    def test_12_configuration_type(self):
        response = VisionEngine().initialize(request(), object())
        self.assertEqual(response.errors[0].code, "vision.configuration.invalid_type")

    def test_13_configuration_threshold(self):
        response = VisionEngine().initialize(request(), VisionConfiguration(confidence_threshold=1.1))
        self.assertEqual(response.errors[0].code, "vision.configuration.invalid_threshold")

    def test_15_configuration_candidate_limit(self):
        response = VisionEngine().initialize(request(), VisionConfiguration(maximum_candidates=0))
        self.assertEqual(response.errors[0].code, "vision.configuration.invalid_limit")

    def test_16_repeated_initialize_rejected(self):
        engine = ready()
        self.assertEqual(engine.initialize(request(), VisionConfiguration("mock")).status, ResponseStatus.REJECTED)

    def test_17_process_before_initialize(self):
        self.assertEqual(VisionEngine().process(request(), Frame()).errors[0].category, "invalid_state")

    def test_18_invalid_frame_contract(self):
        response = ready().process(request(), object())
        self.assertEqual(response.errors[0].code, "vision.observation.invalid_contract")

    def test_19_empty_frame(self):
        response = ready().process(request(), Frame(data=b""))
        self.assertEqual(response.errors[0].code, "vision.observation.invalid_data")

    def test_20_invalid_dimensions(self):
        response = ready().process(request(), Frame(width=0))
        self.assertEqual(response.errors[0].code, "vision.observation.invalid_dimensions")

    def test_21_frame_size_mismatch(self):
        response = ready().process(request(), Frame(data=b"x"))
        self.assertEqual(response.errors[0].code, "vision.observation.size_mismatch")

    def test_22_correlation_mismatch(self):
        response = ready().process(request(), Frame(correlation_id="other"))
        self.assertEqual(response.errors[0].code, "vision.observation.correlation_mismatch")

    def test_23_preprocessing_normalizes(self):
        output = BytePreprocessor().preprocess(ImageFrame(bytes((10, 20)), 2, 1, 1, "gray8"), True)
        self.assertEqual(output.data, bytes((0, 255)))

    def test_25_observation_generation(self):
        output = ready(confidence_threshold=0).process(request(), Frame()).observation
        self.assertEqual((output.frame_id, output.image_width, output.image_height), ("frame-1", 2, 2))

    def test_26_feature_extraction(self):
        output = ready(confidence_threshold=0).process(request(), Frame()).observation
        self.assertEqual({feature.name for feature in output.features}, {"intensity", "shape"})

    def test_27_confidence_is_bounded(self):
        output = ready(confidence_threshold=0).process(request(), Frame()).observation
        self.assertTrue(all(0 <= item.confidence <= 1 for item in output.objects))

    def test_29_observation_is_immutable(self):
        output = ready(confidence_threshold=0).process(request(), Frame()).observation
        with self.assertRaises(FrozenInstanceError): output.image_width = 4

    def test_31_processor_controlled_failure(self):
        response = ready(MockVisionProcessor(fail_process_at=1)).process(request(), Frame())
        self.assertEqual((response.status, response.state), (ResponseStatus.FAILED, VisionState.FAILED))

    def test_32_processor_exception_is_structured(self):
        response = ready(RaisingProcessor()).process(request(), Frame())
        self.assertEqual(response.errors[0].code, "vision.processor.exception")

    def test_33_invalid_processor_result(self):
        response = ready(BadResultProcessor()).process(request(), Frame())
        self.assertEqual(response.errors[0].code, "vision.processor.invalid_result")

    def test_34_invalid_confidence_rejected(self):
        response = ready(BadConfidenceProcessor()).process(request(), Frame())
        self.assertEqual(response.errors[0].code, "vision.result.invalid_confidence")

    def test_35_invalid_region_rejected(self):
        response = ready(BadRegionProcessor()).process(request(), Frame())
        self.assertEqual(response.errors[0].code, "vision.result.invalid_region")

    def test_36_diagnostics(self):
        engine = ready(confidence_threshold=0)
        engine.process(request(), Frame())
        diagnostics = engine.diagnostics(request()).diagnostics
        self.assertEqual((diagnostics.frames_processed, diagnostics.processor_id), (1, "mock"))

    def test_37_shutdown(self):
        response = ready().shutdown(request())
        self.assertEqual((response.status, response.state), (ResponseStatus.SUCCEEDED, VisionState.SHUTDOWN))

    def test_38_shutdown_before_initialize_rejected(self):
        self.assertEqual(VisionEngine().shutdown(request()).status, ResponseStatus.REJECTED)

    def test_39_explanation_records(self):
        response = ready(confidence_threshold=0).process(request(), Frame())
        self.assertEqual((response.explanations[0].engine_id, response.explanations[0].correlation_id), ("ENG-009", "corr-1"))

    def test_40_structured_logging(self):
        records = Records()
        engine = VisionEngine([MockVisionProcessor()], log_sink=records)
        engine.initialize(request(), VisionConfiguration("mock"))
        self.assertIsInstance(records.items[0], LogRecord)

    def test_41_logging_failure_is_explicit(self):
        response = VisionEngine([MockVisionProcessor()], log_sink=BadLogger()).initialize(request(), VisionConfiguration("mock"))
        self.assertEqual(response.errors[0].code, "vision.logging.failed")

    def test_42_thread_safe_concurrent_processing(self):
        engine = ready(confidence_threshold=0)
        outputs = []
        threads = [threading.Thread(target=lambda: outputs.append(engine.process(request(request_id=f"r-{len(outputs)}"), Frame()).observation)) for _ in range(12)]
        for thread in threads: thread.start()
        for thread in threads: thread.join()
        self.assertEqual(len({output.observation_id for output in outputs}), 12)

    def test_43_deterministic_repeated_execution(self):
        first = ready(confidence_threshold=0).process(request(), Frame()).observation
        second = ready(confidence_threshold=0).process(request(), Frame()).observation
        self.assertEqual((first.objects, first.features), (second.objects, second.features))

    def test_44_performance_boundary_is_recorded(self):
        output = ready(confidence_threshold=0).process(request(), Frame()).observation
        self.assertAlmostEqual(output.processing_time_ms, 1.0)

    def test_45_optional_opencv_unavailable(self):
        processor = OpenCVVisionProcessor()
        with patch("taskgraph_vision.processors.import_module", side_effect=ImportError):
            with self.assertRaisesRegex(RuntimeError, "OpenCV is unavailable"):
                processor.initialize(VisionConfiguration("opencv"))

    def test_46_rule_40_import_boundary(self):
        import taskgraph_vision.engine as module
        source = inspect.getsource(module)
        forbidden = ("taskgraph_camera.engine", "taskgraph_planner", "taskgraph_execution", "taskgraph_semantic", "cv2")
        self.assertFalse(any(name in source for name in forbidden))


if __name__ == "__main__":
    unittest.main()
