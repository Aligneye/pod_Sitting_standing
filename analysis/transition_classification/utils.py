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


def ensure_output_dirs() -> None:
    for path in [REPORTS_DIR, PLOTS_DIR, MODELS_DIR, DATASET_DIR]:
        path.mkdir(parents=True, exist_ok=True)


def find_csvs(participant: Optional[str] = None, session: Optional[int] = None, file_path: Optional[str] = None) -> List[Path]:
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
    seg = seg.copy()
    seg["time_s"] = (seg["timestamp_ms"] - seg["timestamp_ms"].iloc[0]) / 1000.0
    seg["magnitude"] = np.sqrt(seg["acc_x"] ** 2 + seg["acc_y"] ** 2 + seg["acc_z"] ** 2)
    return seg


def normalize_transition(seg: pd.DataFrame, n_samples: int) -> Dict[str, np.ndarray]:
    if len(seg) < 2:
        return {}
    t_orig = np.linspace(0.0, 1.0, len(seg))
    t_new = np.linspace(0.0, 1.0, n_samples)
    out = {"t": t_new}
    for axis in FEATURE_AXES:
        out[axis] = interp1d(t_orig, seg[axis].to_numpy(), kind="linear")(t_new)
    return out


def vectorize_normalized(item: Dict[str, np.ndarray], axes: List[str]) -> np.ndarray:
    return np.concatenate([item[axis] for axis in axes])


def compute_transition_id(source_name: str, label: str, index: int) -> str:
    return f"{Path(source_name).stem}_{label}_{index + 1:03d}"
