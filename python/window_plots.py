"""
window_plots.py - Plot sliding window boundaries for raw training CSVs and live debug sessions.

This produces a timestamp-based visualization showing exactly where each window
starts and ends across the full recording.

Usage:
    # From the project root:
    python python/window_plots.py --live-session analysis/transition_classification/live_debug/sessions/session_001

    # From inside the python/ folder:
    python window_plots.py --live-session ../analysis/transition_classification/live_debug/sessions/session_001

    # Training dataset examples:
    python window_plots.py --participant P01
    python window_plots.py --participant P01 --session 1
    python window_plots.py --all
    python window_plots.py --file path/to/specific.csv
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Iterable, List, Optional

import pandas as pd
import plotly.graph_objects as go

sys.path.insert(0, str(Path(__file__).parent))
from config import DATASETS_RAW, PLOTS_DIR, WINDOW_OVERLAP, WINDOW_SIZE_SECONDS, SAMPLING_RATE_HZ

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from analysis.transition_classification.live_debug.session_logger import load_recorded_session


WINDOW_COLORS = {
    "training": "rgba(52, 152, 219, 0.14)",
    "live": "rgba(155, 89, 182, 0.14)",
}


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


def _annotate_windows(fig, windows: pd.DataFrame, label_prefix: str, y_min: float, y_max: float, label_every: int) -> None:
    if windows.empty:
        return

    band_x = []
    band_y = []
    line_x = []
    line_y = []
    center_x = []
    center_y = []
    hover_text = []

    for _, win in windows.iterrows():
        start_ts = int(win["start_timestamp"])
        end_ts = int(win["end_timestamp"])
        window_id = int(win["window_id"])
        band_x.extend([start_ts, end_ts, end_ts, start_ts, start_ts, None])
        band_y.extend([y_min, y_min, y_max, y_max, y_min, None])
        line_x.extend([start_ts, start_ts, None, end_ts, end_ts, None])
        line_y.extend([y_min, y_max, None, y_min, y_max, None])
        center_x.append((start_ts + end_ts) / 2)
        center_y.append(y_max)
        hover_text.append(f"Window {window_id}<br>{start_ts} - {end_ts}")

        if label_every > 0 and (window_id == 1 or window_id % label_every == 0):
            fig.add_annotation(
                x=(start_ts + end_ts) / 2,
                y=1.02,
                yref="paper",
                text=f"W{window_id}",
                showarrow=False,
                font=dict(size=10, color="#333333"),
                bgcolor="rgba(255,255,255,0.8)",
                bordercolor="rgba(0,0,0,0.08)",
                borderwidth=1,
            )

    fig.add_trace(
        go.Scatter(
            x=band_x,
            y=band_y,
            mode="lines",
            fill="toself",
            fillcolor=WINDOW_COLORS[label_prefix],
            line=dict(width=0),
            hoverinfo="skip",
            name="window span",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=line_x,
            y=line_y,
            mode="lines",
            line=dict(width=1, color="rgba(80,80,80,0.35)"),
            hoverinfo="skip",
            name="window boundary",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=center_x,
            y=center_y,
            mode="markers",
            marker=dict(size=6, color="rgba(0,0,0,0.05)"),
            text=hover_text,
            hovertemplate="%{text}<extra></extra>",
            name="window info",
        )
    )


def _base_figure(df: pd.DataFrame, title: str):
    fig = go.Figure()
    for axis, color in [("acc_x", "#1f77b4"), ("acc_y", "#ff7f0e"), ("acc_z", "#2ca02c")]:
        fig.add_trace(
            go.Scatter(
                x=df["timestamp_ms"],
                y=df[axis],
                mode="lines",
                line=dict(width=1, color=color),
                name=axis,
            )
        )
    fig.update_layout(
        title=title,
        xaxis_title="Timestamp (ms)",
        yaxis_title="Acceleration",
        hovermode="x unified",
        template="plotly_white",
        height=700,
    )
    return fig


def plot_training_session(
    csv_path: Path,
    output_dir: Path,
    window_size: float = WINDOW_SIZE_SECONDS,
    overlap: float = WINDOW_OVERLAP,
    label_every: int = 10,
) -> Path:
    df = pd.read_csv(csv_path)
    if df.empty:
        raise ValueError(f"{csv_path} is empty")

    samples_per_window = max(2, int(round(window_size * SAMPLING_RATE_HZ)))
    step = max(1, int(round(samples_per_window * (1.0 - overlap))))

    windows = []
    window_id = 0
    i = 0
    while i + samples_per_window <= len(df):
        win = df.iloc[i : i + samples_per_window]
        windows.append(
            {
                "window_id": window_id + 1,
                "start_timestamp": int(win["timestamp_ms"].iloc[0]),
                "end_timestamp": int(win["timestamp_ms"].iloc[-1]),
            }
        )
        window_id += 1
        i += step

    windows_df = pd.DataFrame(windows)
    fig = _base_figure(df, f"{csv_path.stem} - Training Windows")
    y_min = float(df[["acc_x", "acc_y", "acc_z"]].min().min())
    y_max = float(df[["acc_x", "acc_y", "acc_z"]].max().max())
    _annotate_windows(fig, windows_df, "training", y_min, y_max, label_every)

    session_dir = output_dir / csv_path.stem
    session_dir.mkdir(parents=True, exist_ok=True)
    out_path = session_dir / "window_boundaries.html"
    fig.write_html(str(out_path))
    return out_path


def plot_live_session(session_dir: Path, output_dir: Path, label_every: int = 1) -> Path:
    session = load_recorded_session(session_dir)
    df = session.raw_samples.sort_values("sample_index").reset_index(drop=True)
    fig = _base_figure(df, f"{session_dir.name} - Live Windows")
    y_min = float(df[["acc_x", "acc_y", "acc_z"]].min().min())
    y_max = float(df[["acc_x", "acc_y", "acc_z"]].max().max())
    _annotate_windows(fig, session.windows, "live", y_min, y_max, label_every)

    out_dir = output_dir / session_dir.name
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "window_boundaries.html"
    fig.write_html(str(out_path))
    return out_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Plot sliding window boundaries for training or live sessions")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--participant", "-p", help="Participant ID (e.g. P01)")
    group.add_argument("--all", action="store_true", help="Plot all training CSVs")
    group.add_argument("--file", "-f", help="Path to a specific raw CSV file")
    group.add_argument("--live-session", help="Path to a recorded live debug session directory")
    parser.add_argument("--session", "-s", type=int, default=None, help="Session number (e.g. 1)")
    parser.add_argument("--window-size", type=float, default=WINDOW_SIZE_SECONDS, help="Window size in seconds")
    parser.add_argument("--overlap", type=float, default=WINDOW_OVERLAP, help="Window overlap fraction")
    parser.add_argument("--label-every", type=int, default=10, help="Label every Nth window; all windows still appear on hover")
    parser.add_argument("--output-dir", default=None, help="Output directory (default: plots/windows/)")
    args = parser.parse_args()

    output_dir = Path(args.output_dir) if args.output_dir else PLOTS_DIR / "windows"
    output_dir.mkdir(parents=True, exist_ok=True)

    if args.live_session:
        session_dir = Path(args.live_session)
        if not session_dir.exists():
            raise SystemExit(f"Live session directory not found: {session_dir}")
        out_path = plot_live_session(session_dir, output_dir, label_every=max(1, args.label_every))
        print(f"Saved: {out_path}")
        return

    if args.file:
        csv_files = find_csvs(file_path=args.file)
    else:
        csv_files = find_csvs(participant=args.participant, session=args.session, file_path=None if not args.file else args.file)

    if args.all:
        csv_files = sorted(DATASETS_RAW.rglob("*.csv"))

    if not csv_files:
        raise SystemExit("No CSV files found.")

    for csv_path in csv_files:
        out_path = plot_training_session(
            csv_path,
            output_dir,
            window_size=args.window_size,
            overlap=args.overlap,
            label_every=max(1, args.label_every),
        )
        print(f"Saved: {out_path}")


if __name__ == "__main__":
    main()
