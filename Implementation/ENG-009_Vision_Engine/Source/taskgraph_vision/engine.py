"""Thread-safe ENG-009 Vision Engine."""
from __future__ import annotations

from threading import RLock
from time import perf_counter
from typing import Callable, Mapping, Any

from .contracts import (
    CONTRACT_ID, CONTRACT_VERSION, ENGINE_ID, CameraObservationContract,
    ExplanationRecord, LogRecord, NullLogSink, ProcessorResult, ResponseStatus,
    VisionConfiguration, VisionContract, VisionDiagnostics, VisionError,
    VisionObservation, VisionRequest, VisionResponse, VisionState,
)
from .processors import VisionProcessorCatalog


class VisionEngine:
    """Validate Camera observations and produce non-semantic visual candidates."""

    def __init__(self, processors=None, *, log_sink=None, clock: Callable[[], float] = perf_counter) -> None:
        self._catalog = (
            processors if isinstance(processors, VisionProcessorCatalog)
            else VisionProcessorCatalog.default() if processors is None
            else VisionProcessorCatalog(processors)
        )
        self._log = log_sink or NullLogSink()
        self._clock = clock
        self._state = VisionState.CREATED
        self._processor = None
        self._configuration = None
        self._processed = 0
        self._failures = 0
        self._last_duration = None
        self._last_error = None
        self._sequence = 0
        self._lock = RLock()

    @property
    def state(self) -> VisionState:
        with self._lock:
            return self._state

    def initialize(self, request: VisionRequest, configuration: VisionConfiguration) -> VisionResponse:
        with self._lock:
            errors = self._request_errors(request) + self._configuration_errors(request, configuration)
            if errors:
                return self._response(request, ResponseStatus.REJECTED, errors=errors)
            if self._state is not VisionState.CREATED:
                return self._invalid_state(request, "initialize")
            if self._catalog.errors:
                return self._fail(request, "validation", "vision.processor.catalog_invalid", "; ".join(self._catalog.errors))
            processor = self._catalog.get(configuration.processor_id)
            if processor is None:
                return self._reject(request, "dependency_unavailable", "vision.processor.not_found", f"processor unavailable: {configuration.processor_id}")
            try:
                processor.initialize(configuration)
            except Exception as exc:
                return self._fail(request, "dependency_unavailable", "vision.processor.initialize_failed", "processor initialization failed", {"exception_type": type(exc).__name__})
            self._processor = processor
            self._configuration = configuration
            self._state = VisionState.READY
            explanation = self._explain(request, "Vision initialization", f"selected processor {processor.processor_id}", ("configuration validated",), "succeeded")
            return self._response(request, ResponseStatus.SUCCEEDED, explanations=(explanation,))

    def process(self, request: VisionRequest, observation: CameraObservationContract) -> VisionResponse:
        with self._lock:
            errors = self._request_errors(request) + self._observation_errors(request, observation)
            if errors:
                return self._response(request, ResponseStatus.REJECTED, errors=errors)
            if self._state is not VisionState.READY:
                return self._invalid_state(request, "process")
            self._state = VisionState.VALIDATING
            if observation.correlation_id != request.correlation_id:
                self._state = VisionState.READY
                return self._reject(request, "validation", "vision.observation.correlation_mismatch", "camera observation correlation does not match request")
            self._state = VisionState.PROCESSING
            started = self._clock()
            try:
                result = self._processor.process(observation)
            except Exception as exc:
                return self._fail(request, "processing_failure", "vision.processor.exception", "processor raised during processing", {"exception_type": type(exc).__name__})
            ended = self._clock()
            duration = max(0.0, (ended - started) * 1000.0)
            self._last_duration = duration
            if not isinstance(result, ProcessorResult):
                return self._fail(request, "internal_invariant_failure", "vision.processor.invalid_result", "processor returned an invalid result")
            if not result.succeeded:
                return self._fail(request, "processing_failure", result.error_code or "vision.processing.failed", result.error_summary or "vision processing failed")
            result_error = self._validate_result(request, result, observation)
            if result_error:
                return self._fail(request, result_error.category, result_error.code, result_error.message)
            self._sequence += 1
            self._processed += 1
            explanation = self._explain(
                request, "Visual observation", f"produced {len(result.objects)} visual candidates",
                (f"frame={observation.observation_id}", f"processor={self._processor.processor_id}"), "succeeded",
            )
            output = VisionObservation(
                observation_id=f"{request.correlation_id}:vision-observation:{self._sequence}",
                frame_id=observation.observation_id,
                correlation_id=request.correlation_id,
                timestamp_context=observation.timestamp_context,
                objects=result.objects,
                features=result.features,
                processing_time_ms=duration,
                image_width=observation.width,
                image_height=observation.height,
                pixel_format=observation.pixel_format,
                diagnostics={**dict(result.diagnostics), "processor_id": self._processor.processor_id},
                explanation=explanation,
            )
            self._state = VisionState.READY
            return self._response(request, ResponseStatus.SUCCEEDED, observation=output, explanations=(explanation,))

    def diagnostics(self, request: VisionRequest) -> VisionResponse:
        with self._lock:
            errors = self._request_errors(request)
            if errors:
                return self._response(request, ResponseStatus.REJECTED, errors=errors)
            processor_diagnostics: Mapping[str, Any] = {}
            if self._processor is not None:
                try:
                    processor_diagnostics = self._processor.diagnostics()
                except Exception as exc:
                    return self._fail(request, "dependency_unavailable", "vision.diagnostics.processor_failed", "processor diagnostics failed", {"exception_type": type(exc).__name__})
            value = VisionDiagnostics(
                self._state,
                None if self._processor is None else self._processor.processor_id,
                self._processed,
                self._failures,
                self._last_duration,
                self._last_error,
                processor_diagnostics,
            )
            return self._response(request, ResponseStatus.SUCCEEDED, diagnostics=value)

    def shutdown(self, request: VisionRequest) -> VisionResponse:
        with self._lock:
            errors = self._request_errors(request)
            if errors:
                return self._response(request, ResponseStatus.REJECTED, errors=errors)
            if self._state not in (VisionState.READY, VisionState.FAILED):
                return self._invalid_state(request, "shutdown")
            try:
                if self._processor is not None:
                    self._processor.shutdown()
            except Exception as exc:
                return self._fail(request, "dependency_unavailable", "vision.processor.shutdown_failed", "processor shutdown failed", {"exception_type": type(exc).__name__})
            self._processor = None
            self._configuration = None
            self._state = VisionState.SHUTDOWN
            explanation = self._explain(request, "Vision shutdown", "released processor resources", (), "succeeded")
            return self._response(request, ResponseStatus.SUCCEEDED, explanations=(explanation,))

    def _request_errors(self, request) -> tuple[VisionError, ...]:
        if not isinstance(request, VisionRequest):
            return (VisionError("validation", "vision.request.invalid_type", "request must be VisionRequest", "unknown", "unknown"),)
        missing = [name for name in ("request_id", "correlation_id", "source_identity", "target_capability") if not getattr(request, name)]
        if missing:
            return (self._error(request, "validation", "vision.request.missing_field", "required request fields are missing", {"fields": tuple(missing)}),)
        if request.contract_id != CONTRACT_ID or request.contract_version.split(".")[0] != CONTRACT_VERSION.split(".")[0]:
            return (self._error(request, "unsupported_version", "vision.request.unsupported_contract", "unsupported Vision contract identity or major version"),)
        return ()

    def _configuration_errors(self, request, configuration) -> tuple[VisionError, ...]:
        if not isinstance(configuration, VisionConfiguration):
            return (self._error(request, "validation", "vision.configuration.invalid_type", "configuration must be VisionConfiguration"),)
        if not configuration.processor_id:
            return (self._error(request, "validation", "vision.configuration.processor_required", "processor_id is required"),)
        if isinstance(configuration.confidence_threshold, bool) or not isinstance(configuration.confidence_threshold, (int, float)) or not 0 <= configuration.confidence_threshold <= 1:
            return (self._error(request, "validation", "vision.configuration.invalid_threshold", "confidence_threshold must be between zero and one"),)
        if isinstance(configuration.maximum_candidates, bool) or not isinstance(configuration.maximum_candidates, int) or configuration.maximum_candidates <= 0:
            return (self._error(request, "validation", "vision.configuration.invalid_limit", "maximum_candidates must be a positive integer"),)
        return ()

    def _observation_errors(self, request, observation) -> tuple[VisionError, ...]:
        if not isinstance(observation, CameraObservationContract):
            return (self._error(request, "validation", "vision.observation.invalid_contract", "input does not satisfy Camera observation contract"),)
        if not observation.observation_id or not observation.correlation_id or not observation.pixel_format:
            return (self._error(request, "validation", "vision.observation.missing_field", "camera observation identity, correlation, and pixel format are required"),)
        dimensions = (observation.width, observation.height, observation.channels)
        if any(isinstance(value, bool) or not isinstance(value, int) or value <= 0 for value in dimensions):
            return (self._error(request, "validation", "vision.observation.invalid_dimensions", "camera observation dimensions must be positive integers"),)
        if not isinstance(observation.data, bytes) or not observation.data:
            return (self._error(request, "validation", "vision.observation.invalid_data", "camera observation data must be non-empty bytes"),)
        if len(observation.data) != observation.width * observation.height * observation.channels:
            return (self._error(request, "validation", "vision.observation.size_mismatch", "camera observation byte length does not match dimensions"),)
        return ()

    def _validate_result(self, request, result, observation) -> VisionError | None:
        if len(result.objects) > self._configuration.maximum_candidates:
            return self._error(request, "internal_invariant_failure", "vision.result.candidate_limit", "processor exceeded candidate limit")
        for candidate in result.objects:
            if not 0 <= candidate.confidence <= 1:
                return self._error(request, "internal_invariant_failure", "vision.result.invalid_confidence", "candidate confidence must be between zero and one")
            region = candidate.region
            if region.x < 0 or region.y < 0 or region.width <= 0 or region.height <= 0 or region.x + region.width > observation.width or region.y + region.height > observation.height:
                return self._error(request, "internal_invariant_failure", "vision.result.invalid_region", "candidate region is outside the image")
        return None

    def _invalid_state(self, request, operation):
        return self._reject(request, "invalid_state", "vision.lifecycle.invalid_state", f"cannot {operation} while state is {self._state.value}")

    def _reject(self, request, category, code, message):
        return self._response(request, ResponseStatus.REJECTED, errors=(self._error(request, category, code, message),))

    def _fail(self, request, category, code, message, context=None):
        self._state = VisionState.FAILED
        self._failures += 1
        self._last_error = code
        return self._response(request, ResponseStatus.FAILED, errors=(self._error(request, category, code, message, context),))

    def _error(self, request, category, code, message, context=None):
        return VisionError(category, code, message, getattr(request, "request_id", "unknown"), getattr(request, "correlation_id", "unknown"), False, context or {})

    def _explain(self, request, subject, decision, facts, status):
        self._sequence += 1
        return ExplanationRecord(f"{request.correlation_id}:vision-explanation:{self._sequence}", ENGINE_ID, request.correlation_id, subject, decision, tuple(facts), status)

    def _response(self, request, status, *, observation=None, diagnostics=None, errors=(), explanations=()):
        request_id = getattr(request, "request_id", "unknown")
        correlation_id = getattr(request, "correlation_id", "unknown")
        severity = "error" if status is ResponseStatus.FAILED else "warning" if status is ResponseStatus.REJECTED else "info"
        try:
            self._log.record(LogRecord(ENGINE_ID, "vision.operation", severity, correlation_id, status.value, {"state": self._state.value}))
        except Exception as exc:
            if status is not ResponseStatus.FAILED:
                self._state = VisionState.FAILED
                self._failures += 1
                error = self._error(request, "dependency_unavailable", "vision.logging.failed", "logging contract failed", {"exception_type": type(exc).__name__})
                errors = tuple(errors) + (error,)
                status = ResponseStatus.FAILED
        return VisionResponse(f"{request_id}:vision-response", request_id, correlation_id, status, self._state, observation, diagnostics, tuple(errors), tuple(explanations))
