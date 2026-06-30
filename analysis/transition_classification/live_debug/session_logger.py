"""
Session logging helpers for live transition debugging.

The recorder writes a complete, replayable session bundle:

- raw sensor samples
- sliding window boundaries
- exact feature vectors
- model predictions and timing
- session metadata
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence

import numpy as np
import pandas as pd


RAW_SAMPLE_FILE = "raw_samples.csv"
WINDOW_FILE = "windows.csv"
PREDICTION_FILE = "predictions.csv"
FEATURE_FILE = "features.csv"
METADATA_FILE = "metadata.json"
GROUND_TRUTH_FILE = "ground_truth.csv"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _git_commit() -> Optional[str]:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
            cwd=Path(__file__).resolve().parents[3],
        )
    except Exception:
        return None
    commit = result.stdout.strip()
    return commit or None


def _feature_column_name(index: int) -> str:
    return f"feature_{index:03d}"


@dataclass
class SessionMetadata:
    participant: str
    session: str
    sampling_rate: int
    window_size: float
    overlap: float
    model_used: str
    timestamp: str
    git_commit: Optional[str]


class DebugSessionRecorder:
    """Collect live inference artifacts and write them to disk."""

    def __init__(
        self,
        output_dir: Path,
        participant: str = "unknown",
        session: str = "unknown",
        sampling_rate: int = 50,
        window_size: float = 2.0,
        overlap: float = 0.5,
        model_used: str = "unknown",
        git_commit: Optional[str] = None,
    ) -> None:
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.metadata = SessionMetadata(
            participant=participant,
            session=session,
            sampling_rate=sampling_rate,
            window_size=window_size,
            overlap=overlap,
            model_used=model_used,
            timestamp=_now_iso(),
            git_commit=git_commit if git_commit is not None else _git_commit(),
        )

        self._raw_samples: List[Dict[str, object]] = []
        self._windows: List[Dict[str, object]] = []
        self._predictions: List[Dict[str, object]] = []
        self._features: List[Dict[str, object]] = []
        self._feature_names: Optional[List[str]] = None

    @property
    def feature_names(self) -> Optional[List[str]]:
        return self._feature_names

    def record_sample(self, sample_index: int, sample: object) -> None:
        self._raw_samples.append(
            {
                "sample_index": sample_index,
                "timestamp_ms": int(getattr(sample, "timestamp_ms")),
                "acc_x": float(getattr(sample, "acc_x")),
                "acc_y": float(getattr(sample, "acc_y")),
                "acc_z": float(getattr(sample, "acc_z")),
            }
        )

    def record_window(
        self,
        window_id: int,
        start_sample: int,
        end_sample: int,
        start_timestamp: int,
        end_timestamp: int,
        window_size: float,
        overlap: float,
        window_size_seconds: Optional[float] = None,
        window_size_samples: Optional[int] = None,
        step_samples: Optional[int] = None,
    ) -> None:
        row: Dict[str, object] = {
            "window_id": window_id,
            "start_sample": start_sample,
            "end_sample": end_sample,
            "start_timestamp": start_timestamp,
            "end_timestamp": end_timestamp,
            "window_size": window_size,
            "overlap": overlap,
        }
        if window_size_seconds is not None:
            row["window_size_seconds"] = window_size_seconds
        if window_size_samples is not None:
            row["window_size_samples"] = window_size_samples
        if step_samples is not None:
            row["step_samples"] = step_samples
        self._windows.append(row)

    def record_features(
        self,
        window_id: int,
        start_timestamp: int,
        end_timestamp: int,
        features: Sequence[float],
    ) -> None:
        values = [float(v) for v in features]
        if self._feature_names is None:
            self._feature_names = [_feature_column_name(i) for i in range(len(values))]

        row: Dict[str, object] = {
            "window_id": window_id,
            "timestamp_ms": end_timestamp,
            "start_timestamp_ms": start_timestamp,
            "end_timestamp_ms": end_timestamp,
        }
        for name, value in zip(self._feature_names, values):
            row[name] = value
        self._features.append(row)

    def record_prediction(
        self,
        window_id: int,
        prediction: str,
        confidence: Optional[float],
        inference_time_ms: float,
        preprocessing_time_ms: float,
        total_latency_ms: float,
        decision_time_ms: Optional[float] = None,
        filtered_prediction: Optional[str] = None,
        stable_state: Optional[str] = None,
        decision: Optional[str] = None,
        decision_reason: Optional[str] = None,
    ) -> None:
        row: Dict[str, object] = {
            "window_id": window_id,
            "prediction": prediction,
            "confidence": confidence,
            "inference_time_ms": inference_time_ms,
            "preprocessing_time_ms": preprocessing_time_ms,
            "total_latency_ms": total_latency_ms,
        }
        if decision_time_ms is not None:
            row["decision_time_ms"] = decision_time_ms
        if filtered_prediction is not None:
            row["filtered_prediction"] = filtered_prediction
        if stable_state is not None:
            row["stable_state"] = stable_state
        if decision is not None:
            row["decision"] = decision
        if decision_reason is not None:
            row["decision_reason"] = decision_reason
        self._predictions.append(row)

    def write_ground_truth(self, rows: Iterable[Dict[str, object]]) -> Path:
        path = self.output_dir / GROUND_TRUTH_FILE
        pd.DataFrame(list(rows)).to_csv(path, index=False)
        return path

    def finalize(self) -> None:
        raw_columns = ["sample_index", "timestamp_ms", "acc_x", "acc_y", "acc_z"]
        raw_df = pd.DataFrame(self._raw_samples, columns=raw_columns)
        window_df = pd.DataFrame(self._windows)
        prediction_df = pd.DataFrame(self._predictions)
        feature_df = pd.DataFrame(self._features)

        if feature_df.empty and self._feature_names is not None:
            feature_df = pd.DataFrame(columns=["window_id", *self._feature_names])
        elif feature_df.empty:
            feature_df = pd.DataFrame(columns=["window_id"])

        raw_df.to_csv(self.output_dir / RAW_SAMPLE_FILE, index=False)
        window_df.to_csv(self.output_dir / WINDOW_FILE, index=False)
        prediction_df.to_csv(self.output_dir / PREDICTION_FILE, index=False)
        feature_df.to_csv(self.output_dir / FEATURE_FILE, index=False)
        (self.output_dir / METADATA_FILE).write_text(
            json.dumps(asdict(self.metadata), indent=2),
            encoding="utf-8",
        )


@dataclass
class RecordedSession:
    session_dir: Path
    metadata: Dict[str, object]
    raw_samples: pd.DataFrame
    windows: pd.DataFrame
    predictions: pd.DataFrame
    features: pd.DataFrame
    ground_truth: Optional[pd.DataFrame] = None


def load_recorded_session(session_dir: Path) -> RecordedSession:
    """Load a recorded debug session from disk."""
    session_dir = Path(session_dir)
    required_files = [METADATA_FILE, RAW_SAMPLE_FILE, WINDOW_FILE, PREDICTION_FILE, FEATURE_FILE]
    missing = [name for name in required_files if not (session_dir / name).exists()]
    if missing:
        raise FileNotFoundError(
            "Recorded session is incomplete. "
            f"Missing file(s): {', '.join(missing)}. "
            f"Expected a session bundle in {session_dir} containing: {', '.join(required_files)}."
        )

    metadata = json.loads((session_dir / METADATA_FILE).read_text(encoding="utf-8"))

    raw_samples = pd.read_csv(session_dir / RAW_SAMPLE_FILE)
    windows = pd.read_csv(session_dir / WINDOW_FILE)
    predictions = pd.read_csv(session_dir / PREDICTION_FILE)
    features = pd.read_csv(session_dir / FEATURE_FILE)

    ground_truth_path = session_dir / GROUND_TRUTH_FILE
    ground_truth = pd.read_csv(ground_truth_path) if ground_truth_path.exists() else None

    return RecordedSession(
        session_dir=session_dir,
        metadata=metadata,
        raw_samples=raw_samples,
        windows=windows,
        predictions=predictions,
        features=features,
        ground_truth=ground_truth,
    )
