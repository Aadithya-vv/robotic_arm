"""Replaceable deterministic trackers for ENG-010."""
from __future__ import annotations

from dataclasses import replace
from math import hypot
from threading import RLock
from typing import Any, Iterable, Mapping

from .contracts import (
    BoundingRegion, MotionState, SceneConfiguration, SceneObject, SceneTracker,
    SpatialPosition, TrackingResult, TrackingState,
)


def _region(source) -> BoundingRegion:
    return BoundingRegion(source.x, source.y, source.width, source.height)


def _center(region: BoundingRegion) -> SpatialPosition:
    return SpatialPosition(region.x + region.width / 2.0, region.y + region.height / 2.0)


def intersection_over_union(first: BoundingRegion, second: BoundingRegion) -> float:
    left, top = max(first.x, second.x), max(first.y, second.y)
    right = min(first.x + first.width, second.x + second.width)
    bottom = min(first.y + first.height, second.y + second.height)
    intersection = max(0, right - left) * max(0, bottom - top)
    union = first.width * first.height + second.width * second.height - intersection
    return 0.0 if union <= 0 else intersection / union


class DefaultSceneTracker:
    """Associate candidates by best IoU with deterministic tie breaking."""

    tracker_id = "default"

    def __init__(self) -> None:
        self._configuration: SceneConfiguration | None = None
        self._objects: dict[str, SceneObject] = {}
        self._next_id = 1
        self._updates = 0
        self._lock = RLock()

    def initialize(self, configuration: SceneConfiguration) -> None:
        with self._lock:
            self._configuration = configuration
            self.reset()

    def update(self, observation) -> TrackingResult:
        with self._lock:
            if self._configuration is None:
                return TrackingResult(False, error_code="scene.tracker.not_initialized", error_summary="tracker is not initialized")
            candidates = sorted(observation.objects, key=lambda item: item.candidate_id)
            unmatched = set(self._objects)
            next_objects: dict[str, SceneObject] = {}
            added = updated = removed = 0
            for candidate in candidates:
                region = _region(candidate.region)
                scored = sorted(
                    ((intersection_over_union(self._objects[key].region, region), key) for key in unmatched),
                    key=lambda item: (-item[0], item[1]),
                )
                match = scored[0][1] if scored and scored[0][0] >= self._configuration.association_iou_threshold else None
                if match is None:
                    object_id = f"scene-object-{self._next_id:06d}"
                    self._next_id += 1
                    item = SceneObject(
                        object_id, observation.observation_id, observation.frame_id,
                        candidate.candidate_id, region, MotionState.UNKNOWN,
                        TrackingState.ACTIVE, candidate.confidence,
                        observation.timestamp_context, observation.timestamp_context,
                        _center(region), 1,
                    )
                    added += 1
                else:
                    previous = self._objects[match]
                    unmatched.remove(match)
                    center = _center(region)
                    distance = hypot(center.center_x - previous.spatial_position.center_x, center.center_y - previous.spatial_position.center_y)
                    motion = MotionState.MOVING if distance >= self._configuration.motion_threshold else MotionState.STATIONARY
                    item = SceneObject(
                        previous.scene_object_id, observation.observation_id, observation.frame_id,
                        candidate.candidate_id, region, motion, TrackingState.ACTIVE,
                        candidate.confidence, previous.first_seen, observation.timestamp_context,
                        center, previous.update_count + 1,
                    )
                    updated += 1
                next_objects[item.scene_object_id] = item
            for object_id in sorted(unmatched):
                previous = self._objects[object_id]
                missed = previous.missed_updates + 1
                if missed > self._configuration.maximum_missing_updates:
                    removed += 1
                else:
                    next_objects[object_id] = replace(
                        previous, tracking_state=TrackingState.MISSING,
                        missed_updates=missed, status="missing",
                    )
            self._objects = next_objects
            self._updates += 1
            return TrackingResult(
                True, tuple(self._objects[key] for key in sorted(self._objects)),
                added, updated, removed,
                {"associations": updated, "unmatched_candidates": added, "update_number": self._updates},
            )

    def reset(self) -> None:
        with self._lock:
            self._objects = {}
            self._next_id = 1
            self._updates = 0

    def diagnostics(self) -> Mapping[str, Any]:
        with self._lock:
            return {"objects": len(self._objects), "updates": self._updates, "initialized": self._configuration is not None}

    def close(self) -> None:
        with self._lock:
            self.reset()
            self._configuration = None


class MockSceneTracker(DefaultSceneTracker):
    tracker_id = "mock"

    def __init__(self, *, fail_initialize: bool = False, fail_update_at: int | None = None) -> None:
        super().__init__()
        self._fail_initialize = fail_initialize
        self._fail_update_at = fail_update_at
        self._attempts = 0

    def initialize(self, configuration: SceneConfiguration) -> None:
        if self._fail_initialize:
            raise RuntimeError("controlled initialization failure")
        super().initialize(configuration)

    def update(self, observation) -> TrackingResult:
        self._attempts += 1
        if self._fail_update_at == self._attempts:
            return TrackingResult(False, error_code="scene.mock.controlled_failure", error_summary="controlled tracking failure")
        return super().update(observation)


class SceneTrackerCatalog:
    def __init__(self, trackers: Iterable[SceneTracker]) -> None:
        self._trackers: dict[str, SceneTracker] = {}
        errors: list[str] = []
        for tracker in trackers:
            if not isinstance(tracker, SceneTracker):
                errors.append("tracker does not satisfy SceneTracker")
                continue
            if not tracker.tracker_id:
                errors.append("tracker_id must not be empty")
            elif tracker.tracker_id in self._trackers:
                errors.append(f"duplicate tracker_id: {tracker.tracker_id}")
            else:
                self._trackers[tracker.tracker_id] = tracker
        self.errors = tuple(errors)

    @classmethod
    def default(cls) -> "SceneTrackerCatalog":
        return cls((DefaultSceneTracker(), MockSceneTracker()))

    @property
    def tracker_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._trackers))

    def get(self, tracker_id: str) -> SceneTracker | None:
        return self._trackers.get(tracker_id)
