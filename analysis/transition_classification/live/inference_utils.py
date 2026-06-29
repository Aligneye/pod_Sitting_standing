"""
Model loading and prediction helpers for live transition inference.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import joblib
import numpy as np


def load_model(model_path: str | Path) -> Any:
    """Load a trained sklearn/joblib model from disk."""
    return joblib.load(Path(model_path))


def predict_with_confidence(model: Any, features: np.ndarray) -> Tuple[str, Optional[float]]:
    """Predict one label and return an optional confidence score."""
    x = features.reshape(1, -1)
    prediction = model.predict(x)[0]

    confidence: Optional[float] = None
    if hasattr(model, "predict_proba"):
        proba = model.predict_proba(x)[0]
        confidence = float(np.max(proba))

    return str(prediction), confidence
