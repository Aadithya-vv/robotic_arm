"""Replaceable processor providers for ENG-009."""
from __future__ import annotations

from importlib import import_module
from threading import RLock
from typing import Any, Iterable, Mapping

from .contracts import ProcessorResult, VisionConfiguration, VisionProcessor
from .pipeline import BytePreprocessor, ContrastDetector, ImageFrame, StatisticalFeatureExtractor, VisionPipeline


class DefaultVisionProcessor:
    processor_id = "default"

    def __init__(self, pipeline: VisionPipeline | None = None) -> None:
        self._pipeline = pipeline or VisionPipeline(BytePreprocessor(), StatisticalFeatureExtractor(), ContrastDetector())
        self._configuration: VisionConfiguration | None = None
        self._processed = 0
        self._lock = RLock()

    def initialize(self, configuration: VisionConfiguration) -> None:
        with self._lock:
            self._configuration = configuration

    def process(self, observation) -> ProcessorResult:
        with self._lock:
            if self._configuration is None:
                return ProcessorResult(False, error_code="vision.processor.not_initialized", error_summary="processor is not initialized")
            frame = ImageFrame(bytes(observation.data), observation.width, observation.height, observation.channels, observation.pixel_format)
            try:
                prepared, features, objects = self._pipeline.execute(
                    frame, normalize=self._configuration.normalize,
                    threshold=self._configuration.confidence_threshold,
                    limit=self._configuration.maximum_candidates,
                )
            except (ValueError, StopIteration) as exc:
                return ProcessorResult(False, error_code="vision.processing.invalid_frame", error_summary=str(exc))
            self._processed += 1
            return ProcessorResult(True, objects[:self._configuration.maximum_candidates], features, {"normalized": self._configuration.normalize, "processed_bytes": len(prepared.data)})

    def diagnostics(self) -> Mapping[str, Any]:
        with self._lock:
            return {"processed": self._processed, "initialized": self._configuration is not None}

    def shutdown(self) -> None:
        with self._lock:
            self._configuration = None


class MockVisionProcessor(DefaultVisionProcessor):
    """Deterministic processor with controllable failures."""
    processor_id = "mock"

    def __init__(self, *, fail_initialize: bool = False, fail_process_at: int | None = None) -> None:
        super().__init__()
        self._fail_initialize = fail_initialize
        self._fail_process_at = fail_process_at
        self._attempts = 0

    def initialize(self, configuration: VisionConfiguration) -> None:
        if self._fail_initialize:
            raise RuntimeError("controlled initialization failure")
        super().initialize(configuration)

    def process(self, observation) -> ProcessorResult:
        self._attempts += 1
        if self._fail_process_at == self._attempts:
            return ProcessorResult(False, error_code="vision.mock.controlled_failure", error_summary="controlled processing failure")
        return super().process(observation)


class OpenCVVisionProcessor(DefaultVisionProcessor):
    """Optional adapter; OpenCV is loaded only when selected."""
    processor_id = "opencv"

    def initialize(self, configuration: VisionConfiguration) -> None:
        try:
            import_module("cv2")
        except ImportError as exc:
            raise RuntimeError("OpenCV is unavailable") from exc
        super().initialize(configuration)


class VisionProcessorCatalog:
    def __init__(self, processors: Iterable[VisionProcessor]) -> None:
        self._processors: dict[str, VisionProcessor] = {}
        errors: list[str] = []
        for processor in processors:
            if not isinstance(processor, VisionProcessor):
                errors.append("processor does not satisfy VisionProcessor")
                continue
            if not processor.processor_id:
                errors.append("processor_id must not be empty")
            elif processor.processor_id in self._processors:
                errors.append(f"duplicate processor_id: {processor.processor_id}")
            else:
                self._processors[processor.processor_id] = processor
        self.errors = tuple(errors)

    @classmethod
    def default(cls, *, include_opencv: bool = False) -> "VisionProcessorCatalog":
        processors: list[VisionProcessor] = [DefaultVisionProcessor(), MockVisionProcessor()]
        if include_opencv:
            processors.append(OpenCVVisionProcessor())
        return cls(processors)

    @property
    def processor_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._processors))

    def get(self, processor_id: str) -> VisionProcessor | None:
        return self._processors.get(processor_id)
