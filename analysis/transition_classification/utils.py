"""
Shared helpers for the transition classification baseline.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional

import sys

import numpy as np
import pandas as pd
from scipy.interpolate import interp1d

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "python"))
from config import DATASETS_RAW, PROJECT_ROOT


CLASSIFICATION_ROOT = PROJECT_ROOT / "analysis" / "transition_classification"
REPORTS_DIR = CLASSIFICATION_ROOT / "reports"
PLOTS_DIR = CLASSIFICATION_ROOT / "plots"
MODELS_DIR = CLASSIFICATION_ROOT / "models"
DATASET_DIR = CLASSIFICATION_ROOT / "dataset"

TARGET_LABELS = ("SIT_DOWN", "STAND_UP")
FEATURE_AXES = ("acc_x", "acc_y", "acc_z")
METADATA_COLUMNS = [
    "transition_id",
    "participant_id",
    "session_id",
    "source_file",
    "recording_timestamp",
    "cycle_number",
    "transition_index",
    "transition_duration_seconds",
    "label",
]


def ensure_output_dirs() -> None:
    """Create the folders used by this experiment.

    Think of this like setting out separate trays before sorting parts on a
    workbench: one tray for reports, one for plots, one for saved models, and
    one for datasets.
    """
    for path in [REPORTS_DIR, PLOTS_DIR, MODELS_DIR, DATASET_DIR]:
        path.mkdir(parents=True, exist_ok=True)


def find_csvs(participant: Optional[str] = None, session: Optional[int] = None, file_path: Optional[str] = None) -> List[Path]:
    """Find the raw capture CSVs to use for an experiment.

    This keeps dataset selection in one place so the training scripts do not
    need to know where the raw files live.
    """
    if file_path:
        p = Path(file_path)
        return [p] if p.exists() else []

    if participant:
        base = DATASETS_RAW / participant
        if not base.exists():
            return []
        if session is not None:
            return sorted(base.glob(f"*session_{session:03d}*.csv"))
        return sorted(base.glob("*.csv"))

    return sorted(DATASETS_RAW.rglob("*.csv"))


def extract_transitions(df: pd.DataFrame, label: str) -> List[pd.DataFrame]:
    """Split one recording into contiguous transition segments.

    Example: if a session contains STANDING -> SIT_DOWN -> SITTING ->
    STAND_UP, this returns the full SIT_DOWN block and the full STAND_UP block
    as separate chunks.
    """
    transitions: List[pd.DataFrame] = []
    in_segment = False
    start_idx = 0
    for i, row_label in enumerate(df["activity_label"]):
        if row_label == label and not in_segment:
            in_segment = True
            start_idx = i
        elif row_label != label and in_segment:
            transitions.append(df.iloc[start_idx:i].copy().reset_index(drop=True))
            in_segment = False
    if in_segment:
        transitions.append(df.iloc[start_idx:].copy().reset_index(drop=True))
    return transitions


def add_time_columns(seg: pd.DataFrame) -> pd.DataFrame:
    """Add time-from-start and magnitude columns for one transition.

    This is like putting a ruler next to each transition so every later step
    can compare samples using the same reference frame.
    """
    seg = seg.copy()
    seg["time_s"] = (seg["timestamp_ms"] - seg["timestamp_ms"].iloc[0]) / 1000.0
    seg["magnitude"] = np.sqrt(seg["acc_x"] ** 2 + seg["acc_y"] ** 2 + seg["acc_z"] ** 2)
    return seg


def normalize_transition(seg: pd.DataFrame, n_samples: int) -> Dict[str, np.ndarray]:
    """Resample one transition to a fixed length with interpolation.

    If one person takes 1.8 seconds to sit down and another takes 2.6 seconds,
    interpolation stretches or compresses the signal so both become the same
    length before feature extraction.
    """
    if len(seg) < 2:
        return {}
    t_orig = np.linspace(0.0, 1.0, len(seg))
    t_new = np.linspace(0.0, 1.0, n_samples)
    out = {"t": t_new}
    for axis in FEATURE_AXES:
        out[axis] = interp1d(t_orig, seg[axis].to_numpy(), kind="linear")(t_new)
    return out


def vectorize_normalized(item: Dict[str, np.ndarray], axes: List[str]) -> np.ndarray:
    """Flatten selected axes into a single feature vector."""
    return np.concatenate([item[axis] for axis in axes])


def compute_transition_id(source_name: str, label: str, index: int) -> str:
    """Build a stable ID for each transition sample."""
    return f"{Path(source_name).stem}_{label}_{index + 1:03d}"


def parse_transition_metadata(source_path: Path) -> Dict[str, str]:
    """Extract useful identifiers from a raw CSV filename/path.

    This is intentionally lightweight: we reuse metadata that already exists in
    the file path instead of asking anyone to recollect data.
    """
    participant_id = source_path.parent.name if source_path.parent.name else "unknown"

    stem_parts = source_path.stem.split("_")
    session_id = "unknown"
    recording_timestamp = "unknown"
    if len(stem_parts) >= 3 and stem_parts[1] == "session":
        session_id = f"{stem_parts[1]}_{stem_parts[2]}"
    if len(stem_parts) >= 5:
        recording_timestamp = f"{stem_parts[-2]}_{stem_parts[-1]}"
    elif len(stem_parts) >= 1:
        recording_timestamp = stem_parts[-1]

    return {
        "participant_id": participant_id,
        "session_id": session_id,
        "recording_timestamp": recording_timestamp,
    }
