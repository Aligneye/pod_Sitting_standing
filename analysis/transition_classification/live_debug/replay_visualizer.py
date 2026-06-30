"""
Replay and visualize a recorded live transition inference session.

The script can either:

- generate plots from the recorded logs
- replay the session in live timing using the raw samples
- optionally recompute predictions from a model for comparison
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from analysis.transition_classification.live.inference_utils import load_model, predict_with_confidence
from analysis.transition_classification.live.preprocessing import SlidingWindowPreprocessor
from analysis.transition_classification.live.serial_stream import Sample
from analysis.transition_classification.live_debug.session_logger import RecordedSession, load_recorded_session


def _label_to_numeric(values: Sequence[object]) -> Tuple[np.ndarray, Dict[str, int]]:
    labels = [str(v) for v in values if pd.notna(v)]
    unique_labels: List[str] = []
    for label in labels:
        if label not in unique_labels:
            unique_labels.append(label)
    mapping = {label: i for i, label in enumerate(unique_labels)}
    return np.asarray([mapping.get(str(v), np.nan) if pd.notna(v) else np.nan for v in values], dtype=float), mapping


def _prepare_ground_truth(session: RecordedSession) -> Optional[pd.DataFrame]:
    if session.ground_truth is None or session.ground_truth.empty:
        return None
    gt = session.ground_truth.copy()
    if {"timestamp_ms", "label"}.issubset(gt.columns):
        return gt.sort_values("timestamp_ms").reset_index(drop=True)
    if {"start_timestamp", "end_timestamp", "label"}.issubset(gt.columns):
        return gt.sort_values("start_timestamp").reset_index(drop=True)
    return None


def _prediction_changes(predictions: pd.DataFrame) -> pd.DataFrame:
    if predictions.empty or "prediction" not in predictions:
        return pd.DataFrame(columns=predictions.columns)
    changed = predictions["prediction"].ne(predictions["prediction"].shift())
    return predictions.loc[changed.fillna(True)].copy()


def _ensure_output_dir(session_dir: Path, output_dir: Optional[Path]) -> Path:
    if output_dir is not None:
        output_dir.mkdir(parents=True, exist_ok=True)
        return output_dir
    default = session_dir / "visualizations"
    default.mkdir(parents=True, exist_ok=True)
    return default


def _annotate_window_spans(ax: plt.Axes, windows: pd.DataFrame, base_ts: int, y_offset: float = 0.98) -> None:
    """Draw window spans and label each one with its bounds."""
    if windows.empty:
        return

    ymin, ymax = ax.get_ylim()
    label_y = ymax - (ymax - ymin) * (1.0 - y_offset)

    for _, row in windows.iterrows():
        start_ts = int(row["start_timestamp"])
        end_ts = int(row["end_timestamp"])
        window_id = int(row["window_id"])
        ax.axvspan(start_ts, end_ts, color="gray", alpha=0.06)
        ax.axvline(start_ts, color="#1f77b4", alpha=0.2, linewidth=0.8)
        ax.axvline(end_ts, color="#d62728", alpha=0.2, linewidth=0.8)
        ax.text(
            (start_ts + end_ts) / 2.0,
            label_y,
            f"W{window_id}\n{start_ts} - {end_ts}",
            ha="center",
            va="top",
            fontsize=7,
            color="#333333",
            bbox=dict(boxstyle="round,pad=0.2", facecolor="white", alpha=0.7, edgecolor="none"),
        )


def _plot_xyz(session: RecordedSession, output_dir: Path, window_changes: Optional[pd.DataFrame] = None) -> Path:
    df = session.raw_samples.sort_values("sample_index").reset_index(drop=True)
    time_ms = df["timestamp_ms"]
    fig, ax = plt.subplots(figsize=(14, 6))
    for axis, color in [("acc_x", "#1f77b4"), ("acc_y", "#ff7f0e"), ("acc_z", "#2ca02c")]:
        ax.plot(time_ms, df[axis], label=axis, linewidth=1.2, color=color)

    _annotate_window_spans(ax, session.windows, int(df["timestamp_ms"].iloc[0]))

    if window_changes is not None and not window_changes.empty:
        for _, row in window_changes.iterrows():
            t = int(session.windows.loc[session.windows["window_id"] == row["window_id"], "end_timestamp"].iloc[0])
            ax.axvline(t, color="crimson", linestyle="--", alpha=0.45)
            ax.text(t, ax.get_ylim()[1], str(row["prediction"]), rotation=90, va="top", ha="right", fontsize=8, color="crimson")

    ax.set_title("Accelerometer XYZ vs Time")
    ax.set_xlabel("Timestamp (ms)")
    ax.set_ylabel("Acceleration")
    ax.legend(loc="upper right")
    ax.grid(True, alpha=0.2)
    fig.tight_layout()
    path = output_dir / "xyz_vs_time.png"
    fig.savefig(path, dpi=200)
    plt.close(fig)
    return path


def _plot_window_boundaries(session: RecordedSession, output_dir: Path) -> Path:
    df = session.raw_samples.sort_values("sample_index").reset_index(drop=True)
    fig, ax = plt.subplots(figsize=(14, 3.5))
    ax.plot(df["timestamp_ms"], np.zeros(len(df)), alpha=0.0)
    _annotate_window_spans(ax, session.windows, int(df["timestamp_ms"].iloc[0]), y_offset=0.92)
    ax.set_title("Window Boundaries")
    ax.set_xlabel("Timestamp (ms)")
    ax.set_yticks([])
    ax.grid(True, axis="x", alpha=0.2)
    fig.tight_layout()
    path = output_dir / "window_boundaries.png"
    fig.savefig(path, dpi=200)
    plt.close(fig)
    return path


def _plot_prediction_timeline(session: RecordedSession, output_dir: Path) -> Path:
    preds = session.predictions.sort_values("window_id").reset_index(drop=True)
    windows = session.windows.sort_values("window_id").reset_index(drop=True)
    if preds.empty or windows.empty:
        raise ValueError("Session is missing predictions or windows.")

    labels = [str(v) for v in preds["prediction"].dropna().unique().tolist()]
    pred_numeric, mapping = _label_to_numeric(preds["prediction"].tolist())
    change_rows = _prediction_changes(preds)

    timestamps = windows["end_timestamp"].to_numpy(dtype=float)
    fig, ax = plt.subplots(figsize=(14, 4))
    ax.step(timestamps, pred_numeric, where="post", label="prediction", color="#1f77b4")
    ax.scatter(timestamps, pred_numeric, s=18, color="#1f77b4")

    if not change_rows.empty:
        change_ts = windows.loc[windows["window_id"].isin(change_rows["window_id"]), "end_timestamp"].to_numpy(dtype=float)
        ax.vlines(change_ts, np.nanmin(pred_numeric) - 0.5, np.nanmax(pred_numeric) + 0.5, color="crimson", alpha=0.3, linestyle="--")

    ax.set_title("Prediction Timeline")
    ax.set_xlabel("Timestamp (ms)")
    ax.set_ylabel("Prediction")
    ax.set_yticks(list(mapping.values()))
    ax.set_yticklabels(list(mapping.keys()))
    ax.grid(True, alpha=0.2)
    fig.tight_layout()
    path = output_dir / "prediction_timeline.png"
    fig.savefig(path, dpi=200)
    plt.close(fig)
    return path


def _plot_confidence_timeline(session: RecordedSession, output_dir: Path) -> Path:
    preds = session.predictions.sort_values("window_id").reset_index(drop=True)
    windows = session.windows.sort_values("window_id").reset_index(drop=True)
    if preds.empty or windows.empty or "confidence" not in preds:
        raise ValueError("Session is missing confidence values.")

    fig, ax = plt.subplots(figsize=(14, 4))
    ax.plot(windows["end_timestamp"], preds["confidence"], marker="o", linewidth=1.4, color="#9467bd")
    ax.set_ylim(0.0, 1.05)
    ax.set_title("Confidence Timeline")
    ax.set_xlabel("Timestamp (ms)")
    ax.set_ylabel("Confidence")
    ax.grid(True, alpha=0.2)
    fig.tight_layout()
    path = output_dir / "confidence_timeline.png"
    fig.savefig(path, dpi=200)
    plt.close(fig)
    return path


def _plot_ground_truth_timeline(session: RecordedSession, output_dir: Path) -> Optional[Path]:
    gt = _prepare_ground_truth(session)
    if gt is None or gt.empty:
        return None

    fig, ax = plt.subplots(figsize=(14, 4))
    if {"timestamp_ms", "label"}.issubset(gt.columns):
        numeric, mapping = _label_to_numeric(gt["label"].tolist())
        ax.step(gt["timestamp_ms"], numeric, where="post", color="#2ca02c", label="ground truth")
        ax.scatter(gt["timestamp_ms"], numeric, s=14, color="#2ca02c")
        ax.set_yticks(list(mapping.values()))
        ax.set_yticklabels(list(mapping.keys()))
    else:
        labels = [str(v) for v in gt["label"].dropna().unique().tolist()]
        numeric, mapping = _label_to_numeric(gt["label"].tolist())
        ax.step(gt["start_timestamp"], numeric, where="post", color="#2ca02c", label="ground truth")
        ax.set_yticks(list(mapping.values()))
        ax.set_yticklabels(list(mapping.keys()))

    ax.set_title("Ground Truth Timeline")
    ax.set_xlabel("Timestamp (ms)")
    ax.set_ylabel("Label")
    ax.grid(True, alpha=0.2)
    fig.tight_layout()
    path = output_dir / "ground_truth_timeline.png"
    fig.savefig(path, dpi=200)
    plt.close(fig)
    return path


def _plot_overlay(session: RecordedSession, output_dir: Path) -> Path:
    df = session.raw_samples.sort_values("sample_index").reset_index(drop=True)
    windows = session.windows.sort_values("window_id").reset_index(drop=True)
    preds = session.predictions.sort_values("window_id").reset_index(drop=True)
    time_ms = df["timestamp_ms"]

    fig, ax = plt.subplots(figsize=(14, 6))
    ax.plot(time_ms, df["acc_x"], color="#1f77b4", linewidth=1.0, alpha=0.85, label="acc_x")
    ax.plot(time_ms, df["acc_y"], color="#ff7f0e", linewidth=1.0, alpha=0.85, label="acc_y")
    ax.plot(time_ms, df["acc_z"], color="#2ca02c", linewidth=1.0, alpha=0.85, label="acc_z")

    change_rows = _prediction_changes(preds)
    base_ts = int(df["timestamp_ms"].iloc[0])
    _annotate_window_spans(ax, windows, base_ts, y_offset=0.94)

    for _, row in change_rows.iterrows():
        window_ts = int(windows.loc[windows["window_id"] == row["window_id"], "end_timestamp"].iloc[0])
        t = window_ts
        ax.axvline(t, color="crimson", linestyle="--", linewidth=1.2, alpha=0.6)
        idx = min(len(df) - 1, np.searchsorted(time_ms.to_numpy(), t))
        ax.scatter([t], [df["acc_z"].iloc[idx]], color="crimson", s=20, zorder=5)

    ax.set_title("Accelerometer Signals with Prediction Changes")
    ax.set_xlabel("Timestamp (ms)")
    ax.set_ylabel("Acceleration")
    ax.legend(loc="upper right")
    ax.grid(True, alpha=0.2)
    fig.tight_layout()
    path = output_dir / "overlay_prediction_changes.png"
    fig.savefig(path, dpi=200)
    plt.close(fig)
    return path


def generate_plots(session: RecordedSession, output_dir: Optional[Path] = None) -> List[Path]:
    """Generate the debugging plots requested for a recorded session."""
    output_dir = _ensure_output_dir(session.session_dir, output_dir)
    generated = [
        _plot_xyz(session, output_dir, _prediction_changes(session.predictions)),
        _plot_window_boundaries(session, output_dir),
        _plot_prediction_timeline(session, output_dir),
        _plot_confidence_timeline(session, output_dir),
        _plot_overlay(session, output_dir),
    ]
    gt_path = _plot_ground_truth_timeline(session, output_dir)
    if gt_path is not None:
        generated.append(gt_path)
    return generated


def replay_session(session: RecordedSession, model_path: Optional[str] = None, realtime: bool = True) -> None:
    """Replay the session exactly as a live stream would be processed."""
    raw = session.raw_samples.sort_values("sample_index").reset_index(drop=True)
    windows = session.windows.sort_values("window_id").reset_index(drop=True)
    predictions = session.predictions.sort_values("window_id").reset_index(drop=True)
    if raw.empty:
        print("Session contains no raw samples.")
        return

    print(f"Loaded session from: {session.session_dir}")
    print(f"Recorded model: {session.metadata.get('model_used', 'unknown')}")
    if model_path:
        print(f"Recomputed model: {model_path}")

    recorded_by_window = {int(row.window_id): row for row in predictions.itertuples(index=False)}
    model = load_model(model_path) if model_path else None
    preprocessor = SlidingWindowPreprocessor(
        window_size_seconds=float(session.metadata.get("window_size", 2.0)),
        overlap=float(session.metadata.get("overlap", 0.5)),
        samples_per_second=int(session.metadata.get("sampling_rate", 50)),
    )

    wall_start = time.perf_counter()
    base_ts = int(raw["timestamp_ms"].iloc[0])

    for _, row in raw.iterrows():
        target_elapsed = (int(row["timestamp_ms"]) - base_ts) / 1000.0
        if realtime:
            while (time.perf_counter() - wall_start) < target_elapsed:
                time.sleep(0.001)

        sample = Sample(
            timestamp_ms=int(row["timestamp_ms"]),
            acc_x=float(row["acc_x"]),
            acc_y=float(row["acc_y"]),
            acc_z=float(row["acc_z"]),
        )
        emitted_windows = preprocessor.add_sample(sample)
        for window in emitted_windows:
            recorded = recorded_by_window.get(window.window_id)
            if recorded is not None:
                print(
                    f"[replay] window={window.window_id} recorded_pred={recorded.prediction} "
                    f"confidence={getattr(recorded, 'confidence', 'N/A')} "
                    f"latency_ms={getattr(recorded, 'total_latency_ms', 'N/A')}"
                )
            else:
                print(f"[replay] window={window.window_id} recorded_pred=N/A")

            if model is not None:
                prediction, confidence = predict_with_confidence(model, window.features)
                print(
                    f"          recomputed_pred={prediction} "
                    f"confidence={confidence if confidence is not None else 'N/A'} "
                    f"preprocess_ms={window.preprocessing_seconds * 1000.0:.2f}"
                )


def main() -> None:
    parser = argparse.ArgumentParser(description="Visualize or replay a recorded live session")
    parser.add_argument("--session-dir", required=True, help="Path to a recorded live session directory")
    parser.add_argument("--output-dir", default=None, help="Directory for generated plots")
    parser.add_argument("--replay", action="store_true", help="Replay the session using live timing")
    parser.add_argument("--model", default=None, help="Optional model path to recompute predictions during replay")
    parser.add_argument("--no-realtime", action="store_true", help="Disable live timing during replay")
    args = parser.parse_args()

    try:
        session = load_recorded_session(Path(args.session_dir))
    except FileNotFoundError as exc:
        raise SystemExit(
            f"{exc}\n\n"
            "Record a session first by running live_predict.py with --debug-session."
        ) from exc
    if args.replay:
        replay_session(session, model_path=args.model, realtime=not args.no_realtime)

    generated = generate_plots(session, Path(args.output_dir) if args.output_dir else None)
    print("Generated plots:")
    for path in generated:
        print(f"  {path}")


if __name__ == "__main__":
    main()
