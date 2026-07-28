"""Isolated ENG-010 Scene Engine tests."""
from __future__ import annotations

import inspect
import threading
import unittest
from dataclasses import dataclass, FrozenInstanceError

from taskgraph_scene import (
    BoundingRegion, DefaultSceneTracker, GeometricRelationshipBuilder,
    MockSceneTracker, MotionState, RelationshipType, ResponseStatus,
    SceneConfiguration, SceneContract, SceneEngine, SceneRequest, SceneState,
    SceneTrackerCatalog, TrackingResult, VisionObservationContract,
)


@dataclass(frozen=True)
class Region:
    x: int
    y: int
    width: int
    height: int


@dataclass(frozen=True)
class Candidate:
    candidate_id: str
    region: Region
    confidence: float = 0.8


@dataclass(frozen=True)
class Observation:
    observation_id: str = "vision-1"
    frame_id: str = "frame-1"
    correlation_id: str = "corr-1"
    timestamp_context: str | None = "t-1"
    objects: tuple = (Candidate("candidate-1", Region(0, 0, 10, 10)),)
    image_width: int = 100
    image_height: int = 100


def request(**changes):
    values = {"request_id": "req-1", "correlation_id": "corr-1", "source_identity": "test"}
    values.update(changes)
    return SceneRequest(**values)


def ready(tracker=None, **configuration):
    tracker = tracker or MockSceneTracker()
    engine = SceneEngine([tracker], clock=iter((1.0, 1.001) * 200).__next__)
    response = engine.initialize(request(), SceneConfiguration(tracker_id=tracker.tracker_id, **configuration))
    if response.status is not ResponseStatus.SUCCEEDED:
        raise AssertionError(response)
    return engine


class Records:
    def __init__(self): self.items = []
    def record(self, item): self.items.append(item)


class BadLogger:
    def record(self, item): raise RuntimeError("unavailable")


class InvalidTracker:
    tracker_id = "invalid"


class RaisingTracker(MockSceneTracker):
    tracker_id = "raising"
    def update(self, observation): raise RuntimeError("controlled")


class BadResultTracker(MockSceneTracker):
    tracker_id = "bad-result"
    def update(self, observation): return object()


class SceneTests(unittest.TestCase):
    def test_01_public_contract(self):
        self.assertIsInstance(SceneEngine(), SceneContract)

    def test_02_vision_contract_is_structural(self):
        self.assertIsInstance(Observation(), VisionObservationContract)

    def test_03_initial_state(self):
        self.assertEqual(SceneEngine().state, SceneState.EMPTY)

    def test_04_default_catalog(self):
        self.assertEqual(SceneTrackerCatalog.default().tracker_ids, ("default", "mock"))

    def test_05_initialize_default_tracker(self):
        response = SceneEngine().initialize(request(), SceneConfiguration())
        self.assertEqual((response.status, response.state), (ResponseStatus.SUCCEEDED, SceneState.ACTIVE))

    def test_06_initialize_mock_tracker(self):
        self.assertEqual(ready().state, SceneState.ACTIVE)

    def test_07_unknown_tracker(self):
        response = SceneEngine().initialize(request(), SceneConfiguration("missing"))
        self.assertEqual(response.errors[0].code, "scene.tracker.not_found")

    def test_08_invalid_tracker_contract(self):
        response = SceneEngine([InvalidTracker()]).initialize(request(), SceneConfiguration("invalid"))
        self.assertEqual(response.errors[0].code, "scene.tracker.catalog_invalid")

    def test_09_duplicate_tracker(self):
        self.assertIn("duplicate tracker_id", SceneTrackerCatalog([MockSceneTracker(), MockSceneTracker()]).errors[0])

    def test_10_tracker_initialization_failure(self):
        response = SceneEngine([MockSceneTracker(fail_initialize=True)]).initialize(request(), SceneConfiguration("mock"))
        self.assertEqual((response.status, response.state), (ResponseStatus.FAILED, SceneState.DEGRADED))

    def test_11_invalid_configuration_type(self):
        self.assertEqual(SceneEngine().initialize(request(), object()).errors[0].code, "scene.configuration.invalid_type")

    def test_12_invalid_iou_range(self):
        response = SceneEngine().initialize(request(), SceneConfiguration(association_iou_threshold=1.1))
        self.assertEqual(response.errors[0].code, "scene.configuration.invalid_range")

    def test_13_invalid_missing_limit(self):
        response = SceneEngine().initialize(request(), SceneConfiguration(maximum_missing_updates=-1))
        self.assertEqual(response.errors[0].code, "scene.configuration.invalid_missing_limit")

    def test_14_repeated_initialization(self):
        self.assertEqual(ready().initialize(request(), SceneConfiguration("mock")).status, ResponseStatus.REJECTED)

    def test_15_update_before_initialization(self):
        self.assertEqual(SceneEngine().update(request(), Observation()).errors[0].category, "invalid_state")

    def test_16_invalid_observation_contract(self):
        self.assertEqual(ready().update(request(), object()).errors[0].code, "scene.observation.invalid_contract")

    def test_17_missing_observation_identity(self):
        response = ready().update(request(), Observation(observation_id=""))
        self.assertEqual(response.errors[0].code, "scene.observation.missing_field")

    def test_18_invalid_image_dimensions(self):
        response = ready().update(request(), Observation(image_width=0))
        self.assertEqual(response.errors[0].code, "scene.observation.invalid_dimensions")

    def test_19_invalid_candidate_region(self):
        response = ready().update(request(), Observation(objects=(Candidate("x", Region(95, 0, 10, 10)),)))
        self.assertEqual(response.errors[0].code, "scene.observation.invalid_region")

    def test_20_invalid_confidence(self):
        response = ready().update(request(), Observation(objects=(Candidate("x", Region(0, 0, 2, 2), 2.0),)))
        self.assertEqual(response.errors[0].code, "scene.observation.invalid_confidence")

    def test_21_duplicate_candidates(self):
        candidate = Candidate("x", Region(0, 0, 2, 2))
        response = ready().update(request(), Observation(objects=(candidate, candidate)))
        self.assertEqual(response.errors[0].code, "scene.observation.invalid_candidate")

    def test_22_correlation_mismatch(self):
        response = ready().update(request(), Observation(correlation_id="other"))
        self.assertEqual(response.errors[0].code, "scene.observation.correlation_mismatch")

    def test_23_object_creation(self):
        snapshot = ready().update(request(), Observation()).snapshot
        self.assertEqual((len(snapshot.objects), snapshot.objects[0].scene_object_id), (1, "scene-object-000001"))

    def test_24_stable_object_association(self):
        engine = ready()
        first = engine.update(request(), Observation()).snapshot.objects[0]
        moved = Observation("vision-2", "frame-2", objects=(Candidate("different-candidate", Region(1, 0, 10, 10)),))
        second = engine.update(request(request_id="r2"), moved).snapshot.objects[0]
        self.assertEqual(first.scene_object_id, second.scene_object_id)

    def test_25_object_update_count(self):
        engine = ready()
        engine.update(request(), Observation())
        item = engine.update(request(request_id="r2"), Observation("v2", "f2")).snapshot.objects[0]
        self.assertEqual(item.update_count, 2)

    def test_26_motion_detection(self):
        engine = ready(motion_threshold=0.5)
        engine.update(request(), Observation())
        item = engine.update(request(request_id="r2"), Observation("v2", "f2", objects=(Candidate("x", Region(1, 0, 10, 10)),))).snapshot.objects[0]
        self.assertEqual(item.motion_state, MotionState.MOVING)

    def test_27_stationary_detection(self):
        engine = ready()
        engine.update(request(), Observation())
        item = engine.update(request(request_id="r2"), Observation("v2", "f2")).snapshot.objects[0]
        self.assertEqual(item.motion_state, MotionState.STATIONARY)

    def test_28_disappearance_marks_missing(self):
        engine = ready(maximum_missing_updates=1)
        engine.update(request(), Observation())
        item = engine.update(request(request_id="r2"), Observation("v2", "f2", objects=())).snapshot.objects[0]
        self.assertEqual(item.status, "missing")

    def test_29_disappearance_removes_object(self):
        engine = ready(maximum_missing_updates=0)
        engine.update(request(), Observation())
        snapshot = engine.update(request(request_id="r2"), Observation("v2", "f2", objects=())).snapshot
        self.assertEqual((snapshot.objects, snapshot.diagnostics.removed_objects), ((), 1))

    def test_30_repeated_observation_consistency(self):
        engine = ready()
        identifiers = [engine.update(request(request_id=f"r{i}"), Observation(f"v{i}", f"f{i}")).snapshot.objects[0].scene_object_id for i in range(3)]
        self.assertEqual(len(set(identifiers)), 1)

    def test_31_left_right_relationships(self):
        objects = (Candidate("a", Region(0, 0, 10, 10)), Candidate("b", Region(20, 0, 10, 10)))
        kinds = {item.relationship_type for item in ready().update(request(), Observation(objects=objects)).snapshot.relationships}
        self.assertTrue({RelationshipType.LEFT_OF, RelationshipType.RIGHT_OF}.issubset(kinds))

    def test_32_above_below_relationships(self):
        objects = (Candidate("a", Region(0, 0, 10, 10)), Candidate("b", Region(0, 20, 10, 10)))
        kinds = {item.relationship_type for item in ready().update(request(), Observation(objects=objects)).snapshot.relationships}
        self.assertTrue({RelationshipType.ABOVE, RelationshipType.BELOW}.issubset(kinds))

    def test_33_near_relationship(self):
        objects = (Candidate("a", Region(0, 0, 10, 10)), Candidate("b", Region(12, 0, 10, 10)))
        kinds = {item.relationship_type for item in ready(near_distance=20).update(request(), Observation(objects=objects)).snapshot.relationships}
        self.assertIn(RelationshipType.NEAR, kinds)

    def test_34_overlap_relationship(self):
        objects = (Candidate("a", Region(0, 0, 20, 20)), Candidate("b", Region(10, 10, 20, 20)))
        kinds = {item.relationship_type for item in ready().update(request(), Observation(objects=objects)).snapshot.relationships}
        self.assertIn(RelationshipType.OVERLAP, kinds)

    def test_35_contained_relationship(self):
        objects = (Candidate("outer", Region(0, 0, 30, 30)), Candidate("inner", Region(5, 5, 5, 5)))
        kinds = {item.relationship_type for item in ready().update(request(), Observation(objects=objects)).snapshot.relationships}
        self.assertIn(RelationshipType.CONTAINED, kinds)

    def test_36_snapshot_is_immutable(self):
        snapshot = ready().update(request(), Observation()).snapshot
        with self.assertRaises(FrozenInstanceError): snapshot.frame_id = "changed"

    def test_37_snapshot_after_update(self):
        engine = ready(); engine.update(request(), Observation())
        self.assertEqual(engine.snapshot(request(request_id="snapshot")).snapshot.frame_id, "frame-1")

    def test_38_reset(self):
        engine = ready(); engine.update(request(), Observation()); engine.reset(request(request_id="reset"))
        self.assertEqual(engine.snapshot(request(request_id="snapshot")).snapshot.objects, ())

    def test_39_diagnostics(self):
        engine = ready(); engine.update(request(), Observation())
        diagnostics = engine.diagnostics(request(request_id="diagnostics")).diagnostics
        self.assertEqual((diagnostics.tracked_object_count, diagnostics.added_objects, diagnostics.tracking_health), (1, 1, "healthy"))

    def test_40_tracker_controlled_failure(self):
        response = ready(MockSceneTracker(fail_update_at=1)).update(request(), Observation())
        self.assertEqual((response.status, response.state), (ResponseStatus.FAILED, SceneState.DEGRADED))

    def test_41_tracker_exception_is_structured(self):
        response = ready(RaisingTracker()).update(request(), Observation())
        self.assertEqual(response.errors[0].code, "scene.tracker.exception")

    def test_42_invalid_tracker_result(self):
        response = ready(BadResultTracker()).update(request(), Observation())
        self.assertEqual(response.errors[0].code, "scene.tracker.invalid_result")

    def test_43_structured_logging(self):
        records = Records(); engine = SceneEngine([MockSceneTracker()], log_sink=records)
        engine.initialize(request(), SceneConfiguration("mock"))
        self.assertEqual(records.items[0].engine_id, "ENG-010")

    def test_44_logging_failure_is_explicit(self):
        response = SceneEngine([MockSceneTracker()], log_sink=BadLogger()).initialize(request(), SceneConfiguration("mock"))
        self.assertEqual(response.errors[0].code, "scene.logging.failed")

    def test_45_explanation_record(self):
        response = ready().update(request(), Observation())
        self.assertEqual((response.explanations[0].engine_id, response.snapshot.explanation.engine_id), ("ENG-010", "ENG-010"))

    def test_46_close(self):
        response = ready().close(request())
        self.assertEqual((response.status, response.state), (ResponseStatus.SUCCEEDED, SceneState.CLOSED))

    def test_47_close_before_initialization(self):
        self.assertEqual(SceneEngine().close(request()).status, ResponseStatus.REJECTED)

    def test_48_thread_safe_concurrent_updates(self):
        engine = ready(); outputs = []; lock = threading.Lock()
        def update(index):
            response = engine.update(request(request_id=f"r{index}"), Observation(f"v{index}", f"f{index}"))
            with lock: outputs.append(response)
        threads = [threading.Thread(target=update, args=(index,)) for index in range(12)]
        for thread in threads: thread.start()
        for thread in threads: thread.join()
        self.assertEqual((len(outputs), engine.diagnostics(request(request_id="d")).diagnostics.updates_processed), (12, 12))

    def test_49_deterministic_execution(self):
        first = ready().update(request(), Observation()).snapshot
        second = ready().update(request(), Observation()).snapshot
        self.assertEqual((first.objects, first.relationships), (second.objects, second.relationships))

    def test_50_performance_boundary(self):
        duration = ready().update(request(), Observation()).snapshot.diagnostics.processing_time_ms
        self.assertAlmostEqual(duration, 1.0)

    def test_51_mock_tracker(self):
        tracker = MockSceneTracker(); tracker.initialize(SceneConfiguration("mock"))
        self.assertTrue(tracker.update(Observation()).succeeded)

    def test_52_default_tracker(self):
        tracker = DefaultSceneTracker(); tracker.initialize(SceneConfiguration())
        self.assertEqual(tracker.update(Observation()).added, 1)

    def test_53_rule_40_import_boundary(self):
        import taskgraph_scene.engine as module
        source = inspect.getsource(module)
        forbidden = ("taskgraph_vision.engine", "taskgraph_camera", "taskgraph_semantic", "taskgraph_planner", "TaskIR", "Simulation")
        self.assertFalse(any(item in source for item in forbidden))


if __name__ == "__main__":
    unittest.main()
