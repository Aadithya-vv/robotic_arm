"""Replaceable stages used by the default vision pipeline."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .contracts import BoundingRegion, FeatureDescriptor, VisualObject


@dataclass(frozen=True, slots=True)
class ImageFrame:
    data: bytes
    width: int
    height: int
    channels: int
    pixel_format: str


class Preprocessor(Protocol):
    def preprocess(self, frame: ImageFrame, normalize: bool) -> ImageFrame: ...


class FeatureExtractor(Protocol):
    def extract(self, frame: ImageFrame) -> tuple[FeatureDescriptor, ...]: ...


class Detector(Protocol):
    def detect(
        self,
        frame: ImageFrame,
        features: tuple[FeatureDescriptor, ...],
        threshold: float,
        limit: int,
    ) -> tuple[VisualObject, ...]: ...


class BytePreprocessor:
    """Validate and optionally normalize byte intensity deterministically."""

    def preprocess(self, frame: ImageFrame, normalize: bool) -> ImageFrame:
        expected = frame.width * frame.height * frame.channels
        if len(frame.data) != expected:
            raise ValueError("frame byte length does not match dimensions")
        if not normalize or not frame.data:
            return frame
        low, high = min(frame.data), max(frame.data)
        if low == high:
            data = bytes(frame.data)
        else:
            scale = 255.0 / (high - low)
            data = bytes(round((value - low) * scale) for value in frame.data)
        return ImageFrame(data, frame.width, frame.height, frame.channels, frame.pixel_format)


class StatisticalFeatureExtractor:
    """Produce algorithm-neutral numerical image descriptors."""

    def extract(self, frame: ImageFrame) -> tuple[FeatureDescriptor, ...]:
        values = frame.data
        mean = sum(values) / len(values)
        variance = sum((value - mean) ** 2 for value in values) / len(values)
        return (
            FeatureDescriptor("intensity", (mean / 255.0, variance / (255.0**2))),
            FeatureDescriptor("shape", (float(frame.width), float(frame.height), float(frame.channels))),
        )


class ContrastDetector:
    """Create a visual candidate when the frame contains measurable contrast."""

    def detect(
        self,
        frame: ImageFrame,
        features: tuple[FeatureDescriptor, ...],
        threshold: float,
        limit: int,
    ) -> tuple[VisualObject, ...]:
        del limit
        intensity = next(feature for feature in features if feature.name == "intensity")
        confidence = min(1.0, max(0.0, intensity.values[1] * 4.0))
        if confidence < threshold:
            return ()
        return (
            VisualObject(
                candidate_id="visual-candidate-1",
                region=BoundingRegion(0, 0, frame.width, frame.height),
                confidence=confidence,
                features=features,
                properties={"visual_kind": "contrast_region"},
            ),
        )


class VisionPipeline:
    """Composable preprocessing, extraction, and detection pipeline."""

    def __init__(self, preprocessor: Preprocessor, extractor: FeatureExtractor, detector: Detector) -> None:
        self._preprocessor = preprocessor
        self._extractor = extractor
        self._detector = detector

    def execute(self, frame: ImageFrame, *, normalize: bool, threshold: float, limit: int):
        prepared = self._preprocessor.preprocess(frame, normalize)
        features = self._extractor.extract(prepared)
        objects = self._detector.detect(prepared, features, threshold, limit)
        return prepared, features, objects
