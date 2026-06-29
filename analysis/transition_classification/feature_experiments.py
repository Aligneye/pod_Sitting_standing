"""
Feature-set experiments for transition classification baselines.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Dict, List, Sequence

import sys

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score
from sklearn.model_selection import StratifiedKFold, cross_val_predict, cross_val_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from analysis.transition_classification.dataset_builder import build_dataset
from analysis.transition_classification.utils import METADATA_COLUMNS, REPORTS_DIR, ensure_output_dirs, find_csvs


EXPERIMENTS = {
    "acc_xyz": ["acc_x", "acc_y", "acc_z"],
    "acc_yz": ["acc_y", "acc_z"],
    "acc_z": ["acc_z"],
    "acc_x": ["acc_x"],
    "acc_xy": ["acc_x", "acc_y"],
    "acc_xz": ["acc_x", "acc_z"],
}


def feature_columns(n_samples: int, axes: Sequence[str]) -> List[str]:
    """Select the flattened feature columns that belong to a subset of axes.

    The dataset stores all features as `feature_000 ... feature_299` so the
    experiment code maps each requested axis back to its slice of the vector.
    """
    axis_order = ["acc_x", "acc_y", "acc_z"]
    selected: List[str] = []
    for axis in axes:
        axis_index = axis_order.index(axis)
        start = axis_index * n_samples
        end = start + n_samples
        selected.extend([f"feature_{i:03d}" for i in range(start, end)])
    return selected


def extract_validation_keys(dataset: pd.DataFrame) -> Dict[str, pd.Series]:
    """Expose metadata columns for future grouped validation experiments."""
    return {
        "participant_ids": dataset["participant_id"].copy() if "participant_id" in dataset else pd.Series(dtype=object),
        "session_ids": dataset["session_id"].copy() if "session_id" in dataset else pd.Series(dtype=object),
        "source_files": dataset["source_file"].copy() if "source_file" in dataset else pd.Series(dtype=object),
    }


def run_benchmark(X: np.ndarray, y: np.ndarray) -> Dict[str, float]:
    """Evaluate a simple logistic regression benchmark for one feature set."""
    model = Pipeline([
        ("scaler", StandardScaler()),
        ("model", LogisticRegression(max_iter=2000, class_weight="balanced")),
    ])
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    scores = cross_val_score(model, X, y, cv=cv, scoring="accuracy")
    preds = cross_val_predict(model, X, y, cv=cv)
    return {
        "accuracy": accuracy_score(y, preds),
        "precision": precision_score(y, preds, pos_label="STAND_UP"),
        "recall": recall_score(y, preds, pos_label="STAND_UP"),
        "f1": f1_score(y, preds, pos_label="STAND_UP"),
        "cv_mean": float(scores.mean()),
        "cv_std": float(scores.std()),
    }


def main() -> None:
    """Run the feature-sweep experiment across several axis combinations."""
    parser = argparse.ArgumentParser(description="Transition feature experiments")
    parser.add_argument("--dataset", default=None, help="Path to a prebuilt dataset CSV")
    parser.add_argument("--file", "-f", default=None, help="Path to raw CSV")
    parser.add_argument("--participant", "-p", default=None, help="Participant ID")
    parser.add_argument("--session", "-s", type=int, default=None, help="Session number")
    parser.add_argument("--samples", type=int, default=100, help="Normalized samples per transition")
    args = parser.parse_args()

    ensure_output_dirs()
    if args.dataset:
        dataset = pd.read_csv(args.dataset)
    else:
        csvs = find_csvs(args.participant, args.session, args.file)
        dataset = build_dataset(csvs, n_samples=args.samples)

    validation_keys = extract_validation_keys(dataset)
    rows = []
    for experiment_name, axes in EXPERIMENTS.items():
        feature_cols = feature_columns(args.samples, axes)
        X = dataset[feature_cols].to_numpy(dtype=float)
        y = dataset["label"].to_numpy()
        metrics = run_benchmark(X, y)
        rows.append({"experiment": experiment_name, "axes": "+".join(axes), **metrics})

    out_csv = REPORTS_DIR / "feature_comparison.csv"
    pd.DataFrame(rows).to_csv(out_csv, index=False)
    print(f"Saved feature comparison to {out_csv}")


if __name__ == "__main__":
    main()
