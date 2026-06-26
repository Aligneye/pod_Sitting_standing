"""
plot.py — Generate interactive Plotly visualizations for captured sessions.

Creates HTML plots with colored activity regions, zoom/pan/hover.
Optionally exports PNG.

Usage:
    python plot.py --participant P01
    python plot.py --participant P01 --session 1
    python plot.py --all
    python plot.py --file path/to/specific.csv
    python plot.py --participant P01 --png
"""

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

sys.path.insert(0, str(Path(__file__).parent))
from config import DATASETS_RAW, PLOTS_DIR


PHASE_COLORS = {
    "STANDING": "rgba(46, 204, 113, 0.2)",
    "SIT_DOWN": "rgba(230, 126, 34, 0.3)",
    "SITTING": "rgba(52, 152, 219, 0.2)",
    "STAND_UP": "rgba(155, 89, 182, 0.3)",
}


def get_phase_regions(df, time_col="time_s"):
    """Extract contiguous phase regions for background shading."""
    regions = []
    if "activity_label" not in df.columns:
        return regions

    prev_label = None
    start_t = 0
    for i, label in enumerate(df["activity_label"]):
        if label != prev_label:
            if prev_label is not None:
                regions.append((prev_label, start_t, df[time_col].iloc[i - 1]))
            start_t = df[time_col].iloc[i]
            prev_label = label
    if prev_label is not None:
        regions.append((prev_label, start_t, df[time_col].iloc[-1]))
    return regions


def add_phase_backgrounds(fig, regions, row=None):
    """Add colored vrects for each activity phase."""
    for label, t_start, t_end in regions:
        color = PHASE_COLORS.get(label, "rgba(200,200,200,0.1)")
        fig.add_vrect(
            x0=t_start, x1=t_end,
            fillcolor=color, layer="below", line_width=0,
            row=row, col=1,
        )


def plot_session(csv_path: Path, output_dir: Path, export_png=False):
    """Generate all plots for a session."""
    df = pd.read_csv(csv_path)
    df["time_s"] = (df["timestamp_ms"] - df["timestamp_ms"].iloc[0]) / 1000.0
    df["magnitude"] = np.sqrt(df["acc_x"]**2 + df["acc_y"]**2 + df["acc_z"]**2)

    session_name = csv_path.stem
    session_dir = output_dir / session_name
    session_dir.mkdir(parents=True, exist_ok=True)

    regions = get_phase_regions(df)

    # 1. Individual axis plots
    for axis in ["acc_x", "acc_y", "acc_z"]:
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=df["time_s"], y=df[axis],
            mode="lines", line=dict(width=0.8, color="black"),
            name=axis,
        ))
        add_phase_backgrounds(fig, regions)
        fig.update_layout(
            title=f"{session_name} — {axis}",
            xaxis_title="Time (s)",
            yaxis_title="Acceleration (m/s²)",
            hovermode="x unified",
        )
        fig.write_html(str(session_dir / f"{axis}.html"))
        if export_png:
            fig.write_image(str(session_dir / f"{axis}.png"), width=1400, height=400)

    # 2. Combined XYZ
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True,
                        subplot_titles=("X", "Y", "Z"))
    for i, axis in enumerate(["acc_x", "acc_y", "acc_z"], 1):
        fig.add_trace(go.Scatter(
            x=df["time_s"], y=df[axis],
            mode="lines", line=dict(width=0.7),
            name=axis,
        ), row=i, col=1)
        add_phase_backgrounds(fig, regions, row=i)

    fig.update_layout(
        title=f"{session_name} — Combined XYZ",
        height=800,
        hovermode="x unified",
    )
    fig.update_xaxes(title_text="Time (s)", row=3, col=1)
    fig.write_html(str(session_dir / "combined_xyz.html"))
    if export_png:
        fig.write_image(str(session_dir / "combined_xyz.png"), width=1400, height=800)

    # 3. Magnitude
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["time_s"], y=df["magnitude"],
        mode="lines", line=dict(width=0.8, color="darkred"),
        name="magnitude",
    ))
    add_phase_backgrounds(fig, regions)
    fig.update_layout(
        title=f"{session_name} — Acceleration Magnitude",
        xaxis_title="Time (s)",
        yaxis_title="|a| (m/s²)",
        hovermode="x unified",
    )
    fig.write_html(str(session_dir / "magnitude.html"))
    if export_png:
        fig.write_image(str(session_dir / "magnitude.png"), width=1400, height=400)

    print(f"Plots saved to: {session_dir}/")
    return session_dir


def find_csvs(participant=None, session=None, all_participants=False):
    """Locate CSV files from datasets/raw/ by participant/session."""
    if all_participants:
        return sorted(DATASETS_RAW.rglob("*.csv"))

    if participant:
        participant_dir = DATASETS_RAW / participant
        if not participant_dir.exists():
            print(f"Error: No data found for participant '{participant}' in {DATASETS_RAW}")
            sys.exit(1)
        csvs = sorted(participant_dir.glob("*.csv"))
        if session is not None:
            pattern = f"*session_{session:03d}*"
            csvs = sorted(participant_dir.glob(pattern))
        return csvs

    return []


def main():
    parser = argparse.ArgumentParser(description="Generate interactive session plots")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--participant", "-p", help="Participant ID (e.g. P01)")
    group.add_argument("--all", action="store_true", help="Plot all participants")
    group.add_argument("--file", "-f", help="Path to a specific CSV file")
    parser.add_argument("--session", "-s", type=int, default=None, help="Session number (e.g. 1)")
    parser.add_argument("--png", action="store_true", help="Also export PNG images")
    parser.add_argument("--output-dir", default=None, help="Output directory (default: plots/)")
    args = parser.parse_args()

    output_dir = Path(args.output_dir) if args.output_dir else PLOTS_DIR

    if args.file:
        csv_files = [Path(args.file)]
        if not csv_files[0].exists():
            print(f"Error: {csv_files[0]} not found")
            sys.exit(1)
    else:
        csv_files = find_csvs(
            participant=args.participant,
            session=args.session,
            all_participants=args.all,
        )

    if not csv_files:
        print("No CSV files found.")
        sys.exit(1)

    print(f"Plotting {len(csv_files)} session(s)...\n")
    for csv_path in csv_files:
        plot_session(csv_path, output_dir, export_png=args.png)


if __name__ == "__main__":
    main()
