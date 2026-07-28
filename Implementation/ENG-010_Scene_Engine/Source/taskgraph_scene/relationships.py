"""Pure geometric relationship generation and scene validation."""
from __future__ import annotations

from math import hypot

from .contracts import RelationshipType, SceneObject, SpatialRelationship


def _contained(inner, outer) -> bool:
    return (
        inner.x >= outer.x and inner.y >= outer.y
        and inner.x + inner.width <= outer.x + outer.width
        and inner.y + inner.height <= outer.y + outer.height
    )


def _overlap(first, second) -> bool:
    return not (
        first.x + first.width <= second.x or second.x + second.width <= first.x
        or first.y + first.height <= second.y or second.y + second.height <= first.y
    )


class GeometricRelationshipBuilder:
    def build(self, objects: tuple[SceneObject, ...], near_distance: float) -> tuple[SpatialRelationship, ...]:
        relationships: list[SpatialRelationship] = []
        ordered = sorted(objects, key=lambda item: item.scene_object_id)
        for subject in ordered:
            for target in ordered:
                if subject.scene_object_id == target.scene_object_id:
                    continue
                kinds = []
                if subject.spatial_position.center_x < target.spatial_position.center_x:
                    kinds.append(RelationshipType.LEFT_OF)
                elif subject.spatial_position.center_x > target.spatial_position.center_x:
                    kinds.append(RelationshipType.RIGHT_OF)
                if subject.spatial_position.center_y < target.spatial_position.center_y:
                    kinds.append(RelationshipType.ABOVE)
                elif subject.spatial_position.center_y > target.spatial_position.center_y:
                    kinds.append(RelationshipType.BELOW)
                distance = hypot(subject.spatial_position.center_x - target.spatial_position.center_x, subject.spatial_position.center_y - target.spatial_position.center_y)
                if distance <= near_distance:
                    kinds.append(RelationshipType.NEAR)
                if _overlap(subject.region, target.region):
                    kinds.append(RelationshipType.OVERLAP)
                if _contained(subject.region, target.region):
                    kinds.append(RelationshipType.CONTAINED)
                for kind in kinds:
                    relationships.append(SpatialRelationship(
                        f"{subject.scene_object_id}:{kind.value}:{target.scene_object_id}",
                        subject.scene_object_id, target.scene_object_id, kind,
                    ))
        return tuple(relationships)


class SceneValidator:
    def validate(self, objects: tuple[SceneObject, ...], relationships: tuple[SpatialRelationship, ...], width: int, height: int) -> tuple[str, ...]:
        errors: list[str] = []
        identifiers = [item.scene_object_id for item in objects]
        if len(identifiers) != len(set(identifiers)):
            errors.append("scene object identities must be unique")
        known = set(identifiers)
        for item in objects:
            region = item.region
            if region.x < 0 or region.y < 0 or region.width <= 0 or region.height <= 0 or region.x + region.width > width or region.y + region.height > height:
                errors.append(f"object outside image: {item.scene_object_id}")
            if not 0 <= item.confidence <= 1:
                errors.append(f"invalid confidence: {item.scene_object_id}")
        for relation in relationships:
            if relation.subject_id not in known or relation.object_id not in known or relation.subject_id == relation.object_id:
                errors.append(f"invalid relationship: {relation.relationship_id}")
        return tuple(errors)
