"""
Baseline classical ML classifiers for transition classification.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

import sys

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)
from sklearn.model_selection import StratifiedKFold, cross_val_predict, cross_val_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from analysis.transition_classification.dataset_builder import build_dataset
from analysis.transition_classification.utils import METADATA_COLUMNS, MODELS_DIR, PLOTS_DIR, REPORTS_DIR, ensure_output_dirs, find_csvs


def feature_columns(dataset: pd.DataFrame) -> List[str]:
    """Select every model input column without hardcoding indices."""
    return [c for c in dataset.columns if c.startswith("feature_")]


def split_dataset_columns(dataset: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Split metadata columns from feature columns.

    This keeps the training code future-proof: anything named `feature_*` is
    treated as model input, and everything else is preserved for analysis and
    later grouped validation experiments.
    """
    metadata = dataset[[c for c in dataset.columns if c in METADATA_COLUMNS]].copy()
    features = dataset[[c for c in dataset.columns if c.startswith("feature_")]].copy()
    return metadata, features


def extract_validation_keys(dataset: pd.DataFrame) -> Dict[str, pd.Series]:
    """Expose grouping columns now so future validation modes can reuse them."""
    return {
        "participant_ids": dataset["participant_id"].copy() if "participant_id" in dataset else pd.Series(dtype=object),
        "session_ids": dataset["session_id"].copy() if "session_id" in dataset else pd.Series(dtype=object),
        "source_files": dataset["source_file"].copy() if "source_file" in dataset else pd.Series(dtype=object),
    }


def make_models() -> Dict[str, object]:
    """Define the baseline models.

    Logistic Regression and SVM use a scaler because they are sensitive to
    feature scale. Random Forest does not need scaling, like a decision-maker
    that only cares about relative thresholds.
    """
    return {
        "Logistic Regression": Pipeline([
            ("scaler", StandardScaler()),
            ("model", LogisticRegression(max_iter=2000, class_weight="balanced")),
        ]),
        "Random Forest": RandomForestClassifier(n_estimators=300, random_state=42, class_weight="balanced"),
        "SVM (RBF)": Pipeline([
            ("scaler", StandardScaler()),
            ("model", SVC(kernel="rbf", class_weight="balanced")),
        ]),
    }


def run_model(name: str, model, X: np.ndarray, y: np.ndarray, transition_ids: Sequence[str], labels: Sequence[str]) -> Tuple[Dict[str, object], pd.DataFrame]:
    """Evaluate one model with cross-validation and keep per-transition predictions.

    This is where we ask, fold by fold, "if the model only saw part of the
    data, how well would it recognize the rest?"
    """
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    scores = cross_val_score(model, X, y, cv=cv, scoring="accuracy")
    preds = cross_val_predict(model, X, y, cv=cv)

    metrics = {
        "model": name,
        "accuracy": accuracy_score(y, preds),
        "precision": precision_score(y, preds, pos_label="STAND_UP"),
        "recall": recall_score(y, preds, pos_label="STAND_UP"),
        "f1": f1_score(y, preds, pos_label="STAND_UP"),
        "cv_mean": float(scores.mean()),
        "cv_std": float(scores.std()),
    }

    cm = confusion_matrix(y, preds, labels=list(labels))
    pred_rows = []
    for tid, true, pred in zip(transition_ids, y, preds):
        pred_rows.append(
            {
                "transition_id": tid,
                "true_label": true,
                "predicted_label": pred,
                "correct": bool(true == pred),
            }
        )
    pred_df = pd.DataFrame(pred_rows)
    metrics["confusion_matrix"] = cm.tolist()
    return metrics, pred_df


def plot_confusion_matrix(cm: np.ndarray, labels: Sequence[str], path: Path, title: str) -> None:
    """Draw a confusion matrix so mistakes are easy to inspect at a glance."""
    fig, ax = plt.subplots(figsize=(5, 4))
    im = ax.imshow(cm, cmap="Blues")
    ax.set_xticks(range(len(labels)))
    ax.set_yticks(range(len(labels)))
    ax.set_xticklabels(labels)
    ax.set_yticklabels(labels)
    ax.set_xlabel("Predicted")
    ax.set_ylabel("True")
    ax.set_title(title)
    for i in range(cm.shape[0]):
        for j in range(cm.shape[1]):
            ax.text(j, i, str(cm[i, j]), ha="center", va="center", color="black")
    fig.colorbar(im, ax=ax)
    fig.tight_layout()
    fig.savefig(path, dpi=200)
    plt.close(fig)


def write_report(rows: List[Dict[str, object]], output_path: Path) -> None:
    """Write a human-readable summary of the benchmark results."""
    lines = [
        "# Baseline Transition Classification Report",
        "",
        "This benchmark uses classical machine learning only.",
        "",
        "## Model Results",
        "",
        "| Model | Accuracy | Precision | Recall | F1 | CV Mean | CV Std |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            f"| {row['model']} | {row['accuracy']:.3f} | {row['precision']:.3f} | {row['recall']:.3f} | {row['f1']:.3f} | {row['cv_mean']:.3f} | {row['cv_std']:.3f} |"
        )
    lines += [
        "",
        "## Notes",
        "",
        "- Predictions preserve transition IDs so failures can be traced back to individual transitions.",
        "- Cross validation uses 5 stratified folds.",
        "- This is a baseline only, not the final deployment model.",
    ]
    output_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    """Run the baseline benchmark from raw CSVs or a prebuilt dataset."""
    parser = argparse.ArgumentParser(description="Baseline transition classifier")
    parser.add_argument("--dataset", default=None, help="Path to a prebuilt dataset CSV")
    parser.add_argument("--file", "-f", default=None, help="Path to a specific raw CSV")
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

    if dataset.empty:
        raise SystemExit("Dataset is empty.")

    labels = list(dict.fromkeys(dataset["label"].tolist()))
    _, feature_df = split_dataset_columns(dataset)
    feature_cols = list(feature_df.columns)
    X = dataset[feature_cols].to_numpy(dtype=float)
    y = dataset["label"].to_numpy()
    transition_ids = dataset["transition_id"].tolist()
    validation_keys = extract_validation_keys(dataset)

    model_rows = []
    prediction_frames = []
    for model_name, model in make_models().items():
        metrics, pred_df = run_model(model_name, model, X, y, transition_ids, labels)
        model_rows.append(metrics)
        prediction_frames.append(pred_df.assign(model=model_name))

        cm = np.asarray(metrics["confusion_matrix"])
        plot_confusion_matrix(cm, labels, PLOTS_DIR / f"{model_name.lower().replace(' ', '_')}_confusion_matrix.png", model_name)

    results_df = pd.DataFrame(model_rows)
    results_df.to_csv(REPORTS_DIR / "results.csv", index=False)
    pd.concat(prediction_frames, ignore_index=True).to_csv(REPORTS_DIR / "predictions.csv", index=False)
    write_report(model_rows, REPORTS_DIR / "classification_report.md")
    print(f"Saved reports to {REPORTS_DIR}")


if __name__ == "__main__":
    main()
