"""Thread-safe persistent ENG-010 Scene Engine."""
from __future__ import annotations

from threading import RLock
from time import perf_counter
from typing import Callable, Mapping, Any

from .contracts import (
    CONTRACT_ID, CONTRACT_VERSION, ENGINE_ID, ExplanationRecord, LogRecord,
    NullLogSink, ResponseStatus, SceneConfiguration, SceneContract,
    SceneDiagnostics, SceneError, SceneRequest, SceneResponse, SceneSnapshot,
    SceneState, SceneStatistics, TrackingResult, VisionObservationContract,
    VisualObjectContract,
)
from .relationships import GeometricRelationshipBuilder, SceneValidator
from .tracker import SceneTrackerCatalog


class SceneEngine:
    def __init__(self, trackers=None, *, relationship_builder=None, validator=None, log_sink=None, clock: Callable[[], float] = perf_counter) -> None:
        self._catalog = (
            trackers if isinstance(trackers, SceneTrackerCatalog)
            else SceneTrackerCatalog.default() if trackers is None
            else SceneTrackerCatalog(trackers)
        )
        self._builder = relationship_builder or GeometricRelationshipBuilder()
        self._validator = validator or SceneValidator()
        self._log = log_sink or NullLogSink()
        self._clock = clock
        self._lock = RLock()
        self._state = SceneState.EMPTY
        self._tracker = None
        self._configuration = None
        self._scene_id = None
        self._objects = ()
        self._relationships = ()
        self._frame_id = None
        self._timestamp = None
        self._updates = 0
        self._total_created = 0
        self._total_removed = 0
        self._last_added = self._last_updated = self._last_removed = 0
        self._last_duration = None
        self._last_error = None
        self._sequence = 0

    @property
    def state(self) -> SceneState:
        with self._lock:
            return self._state

    def initialize(self, request: SceneRequest, configuration: SceneConfiguration) -> SceneResponse:
        with self._lock:
            errors = self._request_errors(request) + self._configuration_errors(request, configuration)
            if errors:
                return self._response(request, ResponseStatus.REJECTED, errors=errors)
            if self._state is not SceneState.EMPTY:
                return self._invalid_state(request, "initialize")
            if self._catalog.errors:
                return self._fail(request, "validation", "scene.tracker.catalog_invalid", "; ".join(self._catalog.errors))
            tracker = self._catalog.get(configuration.tracker_id)
            if tracker is None:
                return self._reject(request, "dependency_unavailable", "scene.tracker.not_found", f"tracker unavailable: {configuration.tracker_id}")
            self._state = SceneState.INITIALIZING
            try:
                tracker.initialize(configuration)
            except Exception as exc:
                return self._fail(request, "dependency_unavailable", "scene.tracker.initialize_failed", "tracker initialization failed", {"exception_type": type(exc).__name__})
            self._tracker = tracker
            self._configuration = configuration
            self._scene_id = f"{request.correlation_id}:scene"
            self._state = SceneState.ACTIVE
            explanation = self._explain(request, "Scene creation", f"created {self._scene_id}", (f"tracker={tracker.tracker_id}",), "succeeded")
            return self._response(request, ResponseStatus.SUCCEEDED, explanations=(explanation,))

    def update(self, request: SceneRequest, observation: VisionObservationContract) -> SceneResponse:
        with self._lock:
            errors = self._request_errors(request) + self._observation_errors(request, observation)
            if errors:
                return self._response(request, ResponseStatus.REJECTED, errors=errors)
            if self._state is not SceneState.ACTIVE:
                return self._invalid_state(request, "update")
            if observation.correlation_id != request.correlation_id:
                return self._reject(request, "validation", "scene.observation.correlation_mismatch", "Vision observation correlation does not match request")
            self._state = SceneState.UPDATING
            started = self._clock()
            try:
                result = self._tracker.update(observation)
            except Exception as exc:
                return self._fail(request, "processing_failure", "scene.tracker.exception", "tracker raised during update", {"exception_type": type(exc).__name__})
            if not isinstance(result, TrackingResult):
                return self._fail(request, "internal_invariant_failure", "scene.tracker.invalid_result", "tracker returned an invalid result")
            if not result.succeeded:
                return self._fail(request, "processing_failure", result.error_code or "scene.tracking.failed", result.error_summary or "tracking failed")
            try:
                relationships = self._builder.build(result.objects, self._configuration.near_distance)
                consistency_errors = self._validator.validate(result.objects, relationships, observation.image_width, observation.image_height)
            except Exception as exc:
                return self._fail(request, "processing_failure", "scene.consistency.exception", "scene consistency processing failed", {"exception_type": type(exc).__name__})
            if consistency_errors:
                return self._fail(request, "internal_invariant_failure", "scene.consistency.invalid", "; ".join(consistency_errors))
            self._objects = result.objects
            self._relationships = relationships
            self._frame_id = observation.frame_id
            self._timestamp = observation.timestamp_context
            self._updates += 1
            self._total_created += result.added
            self._total_removed += result.removed
            self._last_added, self._last_updated, self._last_removed = result.added, result.updated, result.removed
            self._last_duration = max(0.0, (self._clock() - started) * 1000.0)
            self._state = SceneState.ACTIVE
            explanation = self._explain(
                request, "Scene update",
                f"maintained {len(self._objects)} tracked visual objects",
                (f"added={result.added}", f"updated={result.updated}", f"removed={result.removed}", f"relationships={len(relationships)}"),
                "succeeded",
            )
            snapshot = self._build_snapshot(explanation)
            return self._response(request, ResponseStatus.SUCCEEDED, snapshot=snapshot, explanations=(explanation,))

    def snapshot(self, request: SceneRequest) -> SceneResponse:
        with self._lock:
            errors = self._request_errors(request)
            if errors:
                return self._response(request, ResponseStatus.REJECTED, errors=errors)
            if self._state not in (SceneState.ACTIVE, SceneState.DEGRADED):
                return self._invalid_state(request, "snapshot")
            explanation = self._explain(request, "Scene snapshot", f"captured {len(self._objects)} tracked objects", (f"frame={self._frame_id}",), "succeeded")
            return self._response(request, ResponseStatus.SUCCEEDED, snapshot=self._build_snapshot(explanation), explanations=(explanation,))

    def reset(self, request: SceneRequest) -> SceneResponse:
        with self._lock:
            errors = self._request_errors(request)
            if errors:
                return self._response(request, ResponseStatus.REJECTED, errors=errors)
            if self._state not in (SceneState.ACTIVE, SceneState.DEGRADED):
                return self._invalid_state(request, "reset")
            try:
                self._tracker.reset()
            except Exception as exc:
                return self._fail(request, "dependency_unavailable", "scene.tracker.reset_failed", "tracker reset failed", {"exception_type": type(exc).__name__})
            self._objects = self._relationships = ()
            self._frame_id = self._timestamp = None
            self._last_added = self._last_updated = self._last_removed = 0
            self._last_duration = None
            self._last_error = None
            self._state = SceneState.ACTIVE
            explanation = self._explain(request, "Scene reset", "cleared current runtime world model", (), "succeeded")
            return self._response(request, ResponseStatus.SUCCEEDED, explanations=(explanation,))

    def diagnostics(self, request: SceneRequest) -> SceneResponse:
        with self._lock:
            errors = self._request_errors(request)
            if errors:
                return self._response(request, ResponseStatus.REJECTED, errors=errors)
            details: Mapping[str, Any] = {}
            if self._tracker is not None:
                try:
                    details = self._tracker.diagnostics()
                except Exception as exc:
                    return self._fail(request, "dependency_unavailable", "scene.diagnostics.tracker_failed", "tracker diagnostics failed", {"exception_type": type(exc).__name__})
            return self._response(request, ResponseStatus.SUCCEEDED, diagnostics=self._diagnostics(details))

    def close(self, request: SceneRequest) -> SceneResponse:
        with self._lock:
            errors = self._request_errors(request)
            if errors:
                return self._response(request, ResponseStatus.REJECTED, errors=errors)
            if self._state not in (SceneState.ACTIVE, SceneState.DEGRADED):
                return self._invalid_state(request, "close")
            try:
                self._tracker.close()
            except Exception as exc:
                return self._fail(request, "dependency_unavailable", "scene.tracker.close_failed", "tracker close failed", {"exception_type": type(exc).__name__})
            self._objects = self._relationships = ()
            self._tracker = self._configuration = None
            self._state = SceneState.CLOSED
            explanation = self._explain(request, "Scene close", "released runtime scene resources", (), "succeeded")
            return self._response(request, ResponseStatus.SUCCEEDED, explanations=(explanation,))

    def _build_snapshot(self, explanation):
        return SceneSnapshot(self._scene_id, self._timestamp, self._frame_id, self._objects, self._relationships, self._diagnostics(), SceneStatistics(self._total_created, self._total_removed, self._updates), explanation)

    def _diagnostics(self, tracker_details=None):
        health = "degraded" if self._state is SceneState.DEGRADED else "healthy" if self._state is SceneState.ACTIVE else "inactive"
        return SceneDiagnostics(self._state, None if self._tracker is None else self._tracker.tracker_id, len(self._objects), self._last_added, self._last_removed, self._last_updated, len(self._relationships), health, self._last_duration, self._updates, self._last_error, tracker_details or {})

    def _request_errors(self, request):
        if not isinstance(request, SceneRequest):
            return (SceneError("validation", "scene.request.invalid_type", "request must be SceneRequest", "unknown", "unknown"),)
        missing = [name for name in ("request_id", "correlation_id", "source_identity", "target_capability") if not getattr(request, name)]
        if missing:
            return (self._error(request, "validation", "scene.request.missing_field", "required request fields are missing", {"fields": tuple(missing)}),)
        if request.contract_id != CONTRACT_ID or request.contract_version.split(".")[0] != CONTRACT_VERSION.split(".")[0]:
            return (self._error(request, "unsupported_version", "scene.request.unsupported_contract", "unsupported Scene contract identity or major version"),)
        return ()

    def _configuration_errors(self, request, configuration):
        if not isinstance(configuration, SceneConfiguration):
            return (self._error(request, "validation", "scene.configuration.invalid_type", "configuration must be SceneConfiguration"),)
        if not configuration.tracker_id:
            return (self._error(request, "validation", "scene.configuration.tracker_required", "tracker_id is required"),)
        numeric = (configuration.association_iou_threshold, configuration.near_distance, configuration.motion_threshold)
        if any(isinstance(value, bool) or not isinstance(value, (int, float)) for value in numeric):
            return (self._error(request, "validation", "scene.configuration.invalid_number", "numeric configuration values are invalid"),)
        if not 0 <= configuration.association_iou_threshold <= 1 or configuration.near_distance < 0 or configuration.motion_threshold < 0:
            return (self._error(request, "validation", "scene.configuration.invalid_range", "configuration values are outside valid ranges"),)
        if isinstance(configuration.maximum_missing_updates, bool) or not isinstance(configuration.maximum_missing_updates, int) or configuration.maximum_missing_updates < 0:
            return (self._error(request, "validation", "scene.configuration.invalid_missing_limit", "maximum_missing_updates must be a non-negative integer"),)
        return ()

    def _observation_errors(self, request, observation):
        if not isinstance(observation, VisionObservationContract):
            return (self._error(request, "validation", "scene.observation.invalid_contract", "input does not satisfy Vision observation contract"),)
        if not observation.observation_id or not observation.frame_id or not observation.correlation_id:
            return (self._error(request, "validation", "scene.observation.missing_field", "Vision observation identities and correlation are required"),)
        if any(isinstance(value, bool) or not isinstance(value, int) or value <= 0 for value in (observation.image_width, observation.image_height)):
            return (self._error(request, "validation", "scene.observation.invalid_dimensions", "image dimensions must be positive integers"),)
        identifiers = set()
        for item in observation.objects:
            if not isinstance(item, VisualObjectContract) or not item.candidate_id or item.candidate_id in identifiers:
                return (self._error(request, "validation", "scene.observation.invalid_candidate", "visual candidates must be valid with unique identities"),)
            identifiers.add(item.candidate_id)
            region = item.region
            if region.x < 0 or region.y < 0 or region.width <= 0 or region.height <= 0 or region.x + region.width > observation.image_width or region.y + region.height > observation.image_height:
                return (self._error(request, "validation", "scene.observation.invalid_region", "visual candidate region is outside image"),)
            if isinstance(item.confidence, bool) or not isinstance(item.confidence, (int, float)) or not 0 <= item.confidence <= 1:
                return (self._error(request, "validation", "scene.observation.invalid_confidence", "visual candidate confidence must be between zero and one"),)
        return ()

    def _invalid_state(self, request, operation):
        return self._reject(request, "invalid_state", "scene.lifecycle.invalid_state", f"cannot {operation} while state is {self._state.value}")

    def _reject(self, request, category, code, message):
        return self._response(request, ResponseStatus.REJECTED, errors=(self._error(request, category, code, message),))

    def _fail(self, request, category, code, message, context=None):
        self._state = SceneState.DEGRADED
        self._last_error = code
        return self._response(request, ResponseStatus.FAILED, errors=(self._error(request, category, code, message, context),))

    def _error(self, request, category, code, message, context=None):
        return SceneError(category, code, message, getattr(request, "request_id", "unknown"), getattr(request, "correlation_id", "unknown"), False, context or {})

    def _explain(self, request, subject, decision, facts, status):
        self._sequence += 1
        return ExplanationRecord(f"{request.correlation_id}:scene-explanation:{self._sequence}", ENGINE_ID, request.correlation_id, subject, decision, tuple(facts), status)

    def _response(self, request, status, *, snapshot=None, diagnostics=None, errors=(), explanations=()):
        request_id, correlation = getattr(request, "request_id", "unknown"), getattr(request, "correlation_id", "unknown")
        severity = "error" if status is ResponseStatus.FAILED else "warning" if status is ResponseStatus.REJECTED else "info"
        try:
            self._log.record(LogRecord(ENGINE_ID, "scene.operation", severity, correlation, status.value, {"state": self._state.value}))
        except Exception as exc:
            if status is not ResponseStatus.FAILED:
                self._state = SceneState.DEGRADED
                status = ResponseStatus.FAILED
                errors = tuple(errors) + (self._error(request, "dependency_unavailable", "scene.logging.failed", "logging contract failed", {"exception_type": type(exc).__name__}),)
        return SceneResponse(f"{request_id}:scene-response", request_id, correlation, status, self._state, snapshot, diagnostics, tuple(errors), tuple(explanations))
