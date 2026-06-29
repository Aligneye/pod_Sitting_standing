"""
Live preprocessing for transition classification.

The goal is to use the exact same interpolation logic as training. We reuse
the shared normalization helper so live inference and dataset building stay in
lockstep.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Deque, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from analysis.transition_classification.utils import FEATURE_AXES, add_time_columns, normalize_transition
from analysis.transition_classification.live.serial_stream import Sample


@dataclass
class WindowResult:
    """A single sliding window ready for inference."""

    window_id: int
    start_timestamp_ms: int
    end_timestamp_ms: int
    duration_seconds: float
    features: np.ndarray
    preprocessing_seconds: float


class SlidingWindowPreprocessor:
    """Collect samples and emit normalized windows when enough data is ready."""

    def __init__(self, window_size_seconds: float = 2.0, overlap: float = 0.5, samples_per_second: int = 50, normalized_samples: int = 100):
        self.window_size_seconds = window_size_seconds
        self.overlap = overlap
        self.samples_per_second = samples_per_second
        self.normalized_samples = normalized_samples
        self.window_size_samples = max(2, int(round(window_size_seconds * samples_per_second)))
        self.step_samples = max(1, int(round(self.window_size_samples * (1.0 - overlap))))
        self.buffer: Deque[Sample] = deque()
        self.window_id = 0
        self._last_emitted_end_ts: Optional[int] = None

    def add_sample(self, sample: Sample) -> List[WindowResult]:
        """Add one sample and return any newly completed windows."""
        self.buffer.append(sample)
        emitted: List[WindowResult] = []

        while len(self.buffer) >= self.window_size_samples:
            emitted.append(self._make_window())
            for _ in range(self.step_samples):
                if self.buffer:
                    self.buffer.popleft()
        return emitted

    def _make_window(self) -> WindowResult:
        import time

        t0 = time.perf_counter()
        rows = list(self.buffer)[: self.window_size_samples]
        df = pd.DataFrame(
            {
                "timestamp_ms": [s.timestamp_ms for s in rows],
                "acc_x": [s.acc_x for s in rows],
                "acc_y": [s.acc_y for s in rows],
                "acc_z": [s.acc_z for s in rows],
            }
        )
        df = add_time_columns(df)
        norm = normalize_transition(df, n_samples=self.normalized_samples)
        features = np.concatenate([norm[axis] for axis in FEATURE_AXES]).astype(float)
        self.window_id += 1
        return WindowResult(
            window_id=self.window_id,
            start_timestamp_ms=int(df["timestamp_ms"].iloc[0]),
            end_timestamp_ms=int(df["timestamp_ms"].iloc[-1]),
            duration_seconds=float((df["timestamp_ms"].iloc[-1] - df["timestamp_ms"].iloc[0]) / 1000.0),
            features=features,
            preprocessing_seconds=float(time.perf_counter() - t0),
        )
