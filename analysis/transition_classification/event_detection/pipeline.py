"""
Coordinator for the event-based sitting/standing pipeline.

The intended flow is:

    sample stream
    -> MovementDetector
    -> TransitionExtractor
    -> ContextWindowBuilder
    -> feature extraction seam
    -> TransitionClassifier
    -> one fired event

This module does not implement movement detection, transition extraction, or
feature engineering. It only defines the orchestration boundary for the next
development phase.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence

import numpy as np

from analysis.transition_classification.event_detection.classifier import ClassificationResult, TransitionClassifier
from analysis.transition_classification.event_detection.context_window import ContextWindowBuilder
from analysis.transition_classification.event_detection.movement_detector import MovementDetector
from analysis.transition_classification.event_detection.transition_extractor import TransitionExtractor
from analysis.transition_classification.live.serial_stream import Sample


@dataclass(frozen=True)
class PipelineEvent:
    """One fired sitting/standing event."""

    window_id: int
    timestamp_ms: int
    prediction: str
    confidence: Optional[float]


class EventDetectionPipeline:
    """Structural coordinator for the new event-detection architecture."""

    def __init__(
        self,
        movement_detector: MovementDetector,
        transition_extractor: TransitionExtractor,
        context_window_builder: ContextWindowBuilder,
        classifier: TransitionClassifier,
    ) -> None:
        self.movement_detector = movement_detector
        self.transition_extractor = transition_extractor
        self.context_window_builder = context_window_builder
        self.classifier = classifier

    def process_sample(self, sample: Sample) -> PipelineEvent | None:
        """Process one sample and fire at most one transition event.

        This method intentionally stops at the feature-extraction seam until the
        next phase defines how event windows become model features.
        """
        movement = self.movement_detector.update(sample)
        transition = self.transition_extractor.update(sample, movement.is_moving)
        if transition is None:
            return None

        context_window = self.context_window_builder.build(transition)
        features = self.extract_features(context_window.samples)
        result = self.classifier.classify_features(features)
        return self._make_event(transition.window_id, transition.end_timestamp_ms, result)

    def extract_features(self, samples: Sequence[Sample]) -> np.ndarray:
        """Feature extraction seam for the future event-based model input."""
        raise NotImplementedError("Event-based feature extraction is intentionally not implemented yet.")

    @staticmethod
    def _make_event(window_id: int, timestamp_ms: int, result: ClassificationResult) -> PipelineEvent:
        return PipelineEvent(
            window_id=window_id,
            timestamp_ms=timestamp_ms,
            prediction=result.prediction,
            confidence=result.confidence,
        )
