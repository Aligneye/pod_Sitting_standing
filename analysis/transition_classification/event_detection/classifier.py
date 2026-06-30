"""
Transition classifier boundary for the event-based pipeline.

Responsibility:
    Rece transition representation and cive one completedlassify it as
    SIT_DOWN or STAND_UP.

Non-responsibilities:
    No movement detection, no transition extraction, no voting, and no stable
    state management.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Sequence

import numpy as np

from analysis.transition_classification.live.inference_utils import load_model, predict_with_confidence


@dataclass(frozen=True)
class ClassificationResult:
    """Direct classifier output for one completed transition."""

    prediction: str
    confidence: Optional[float]


class TransitionClassifier:
    """Thin wrapper around an existing trained classifier artifact."""

    def __init__(self, model_path: str | Path) -> None:
        self.model_path = Path(model_path)
        self.model = load_model(self.model_path)

    def classify_features(self, features: Sequence[float] | np.ndarray) -> ClassificationResult:
        """Classify an already-built feature vector.

        Feature extraction is intentionally outside this class so the new
        architecture keeps one responsibility per module.
        """
        prediction, confidence = predict_with_confidence(self.model, np.asarray(features, dtype=float))
        return ClassificationResult(prediction=prediction, confidence=confidence)
