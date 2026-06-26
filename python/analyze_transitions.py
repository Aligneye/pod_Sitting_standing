"""
analyze_transitions.py — Transition consistency analysis across cycles.

Extracts individual sit-down and stand-up transitions, normalizes them,
generates overlay plots, mean curves, similarity heatmaps, and a summary report.

Usage:
    python analyze_transitions.py
    python analyze_transitions.py --file path/to/session.csv
    python analyze_transitions.py --participant harshit --session 1
"""

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from scipy.interpolate import interp1d
from scipy.spatial.distance import euclidean

sys.path.insert(0, str(Path(__file__).parent))
from config import DATASETS_RAW, PROJECT_ROOT

ANALYSIS_DIR = PROJECT_ROOT / "analysis" / "transition_overlays"
NORMALIZED_SAMPLES = 100


# ─── EXTRACTION ─────────────────────────────────────────────────────────────────

def extract_transitions(df, label):
    """Extract individual transitions of a given label. Returns list of DataFrames."""
    transitions = []
    in_segment = False
    start_idx = 0

    for i, row_label in enumerate(df["activity_label"]):
        if row_label == label and not in_segment:
            in_segment = True
            start_idx = i
        elif row_label != label and in_segment:
            segment = df.iloc[start_idx:i].copy()
            segment = segment.reset_index(drop=True)
            transitions.append(segment)
            in_segment = False

    if in_segment:
        segment = df.iloc[start_idx:].copy()
        segment = segment.reset_index(drop=True)
        transitions.append(segment)

    return transitions


# ─── NORMALIZATION ──────────────────────────────────────────────────────────────

def normalize_transition(segment, n_samples=NORMALIZED_SAMPLES):
    """Interpolate a transition to a fixed number of samples."""
    n_orig = len(segment)
    if n_orig < 2:
        return None

    t_orig = np.linspace(0, 1, n_orig)
    t_new = np.linspace(0, 1, n_samples)

    result = {"norm_t": t_new}
    for col in ["acc_x", "acc_y", "acc_z"]:
        f = interp1d(t_orig, segment[col].values, kind="linear")
        result[col] = f(t_new)

    result["magnitude"] = np.sqrt(result["acc_x"]**2 + result["acc_y"]**2 + result["acc_z"]**2)
    return result


# ─── OVERLAY PLOTS ──────────────────────────────────────────────────────────────

def plot_overlay(normalized_list, label, output_dir):
    """Overlay all transitions for a given label on one XYZ plot."""
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True,
                        subplot_titles=("acc_x", "acc_y", "acc_z"),
                        vertical_spacing=0.06)

    axis_colors = {
        "acc_x": "rgba(231, 76, 60, 0.25)",
        "acc_y": "rgba(39, 174, 96, 0.25)",
        "acc_z": "rgba(41, 128, 185, 0.25)",
    }

    for i, axis in enumerate(["acc_x", "acc_y", "acc_z"], 1):
        color = axis_colors[axis]
        for j, norm in enumerate(normalized_list):
            fig.add_trace(go.Scatter(
                x=norm["norm_t"],
                y=norm[axis],
                mode="lines",
                line=dict(width=0.8, color=color),
                name=f"cycle {j+1}" if i == 1 else None,
                showlegend=(i == 1 and j == 0),
                legendgroup=axis,
                hovertemplate=f"cycle {j+1}<br>%{{y:.3f}} m/s²<extra></extra>",
            ), row=i, col=1)
        fig.update_yaxes(title_text="m/s²", row=i, col=1)

    action = "Sit Down" if label == "SIT_DOWN" else "Stand Up"
    fig.update_layout(
        title=f"{action} — All {len(normalized_list)} Transitions Overlaid (Normalized Time)",
        height=900,
        hovermode="x unified",
        xaxis3_title="Normalized Time (0→1)",
    )

    filename = f"{label.lower()}_overlay_xyz.html"
    fig.write_html(str(output_dir / filename))
    return filename


# ─── MEAN CURVES ────────────────────────────────────────────────────────────────

def plot_mean_curve(normalized_list, label, output_dir):
    """Plot mean ± 1 std for each axis."""
    axes_data = {}
    for axis in ["acc_x", "acc_y", "acc_z"]:
        matrix = np.array([n[axis] for n in normalized_list])
        axes_data[axis] = {
            "mean": matrix.mean(axis=0),
            "std": matrix.std(axis=0),
        }

    t = normalized_list[0]["norm_t"]

    fig = make_subplots(rows=3, cols=1, shared_xaxes=True,
                        subplot_titles=("acc_x", "acc_y", "acc_z"),
                        vertical_spacing=0.06)

    colors_line = {"acc_x": "#e74c3c", "acc_y": "#27ae60", "acc_z": "#2980b9"}
    colors_fill = {"acc_x": "rgba(231,76,60,0.2)", "acc_y": "rgba(39,174,96,0.2)", "acc_z": "rgba(41,128,185,0.2)"}

    for i, axis in enumerate(["acc_x", "acc_y", "acc_z"], 1):
        mean = axes_data[axis]["mean"]
        std = axes_data[axis]["std"]
        upper = mean + std
        lower = mean - std

        fig.add_trace(go.Scatter(
            x=np.concatenate([t, t[::-1]]),
            y=np.concatenate([upper, lower[::-1]]),
            fill="toself",
            fillcolor=colors_fill[axis],
            line=dict(width=0),
            name=f"±1σ {axis}",
            showlegend=False,
        ), row=i, col=1)

        fig.add_trace(go.Scatter(
            x=t, y=mean,
            mode="lines",
            line=dict(width=2.5, color=colors_line[axis]),
            name=f"mean {axis}",
        ), row=i, col=1)

        fig.update_yaxes(title_text="m/s²", row=i, col=1)

    action = "Sit Down" if label == "SIT_DOWN" else "Stand Up"
    fig.update_layout(
        title=f"{action} — Mean ± 1σ ({len(normalized_list)} transitions)",
        height=900,
        hovermode="x unified",
        xaxis3_title="Normalized Time (0→1)",
    )

    filename = f"{label.lower()}_mean.html"
    fig.write_html(str(output_dir / filename))
    return filename


# ─── SIMILARITY HEATMAP ────────────────────────────────────────────────────────

def compute_similarity_matrix(normalized_list):
    """Compute pairwise normalized Euclidean distance between transitions."""
    n = len(normalized_list)
    dist_matrix = np.zeros((n, n))

    for i in range(n):
        vec_i = np.concatenate([normalized_list[i]["acc_x"],
                                normalized_list[i]["acc_y"],
                                normalized_list[i]["acc_z"]])
        for j in range(i + 1, n):
            vec_j = np.concatenate([normalized_list[j]["acc_x"],
                                    normalized_list[j]["acc_y"],
                                    normalized_list[j]["acc_z"]])
            d = euclidean(vec_i, vec_j) / len(vec_i)
            dist_matrix[i, j] = d
            dist_matrix[j, i] = d

    return dist_matrix


def plot_similarity_heatmap(sit_down_norm, stand_up_norm, output_dir):
    """Generate combined similarity heatmap for both transition types."""
    fig = make_subplots(rows=1, cols=2,
                        subplot_titles=("Sit Down — Pairwise Distance", "Stand Up — Pairwise Distance"),
                        horizontal_spacing=0.1)

    for col, (norm_list, label) in enumerate([(sit_down_norm, "SIT_DOWN"), (stand_up_norm, "STAND_UP")], 1):
        dist = compute_similarity_matrix(norm_list)
        n = len(norm_list)
        labels = [f"C{i+1}" for i in range(n)]

        fig.add_trace(go.Heatmap(
            z=dist,
            x=labels, y=labels,
            colorscale="YlOrRd",
            showscale=(col == 2),
            hovertemplate="Cycle %{x} vs %{y}<br>Distance: %{z:.4f}<extra></extra>",
        ), row=1, col=col)

    fig.update_layout(
        title="Transition Similarity (Normalized Euclidean Distance — lower = more similar)",
        height=550,
        width=1200,
    )

    filename = "transition_similarity_heatmap.html"
    fig.write_html(str(output_dir / filename))
    return filename


# ─── AVERAGE HUMAN TRANSITION ───────────────────────────────────────────────────

def plot_average_human(sit_down_norm, stand_up_norm, output_dir):
    """Reference visualization showing mean of all axes + magnitude for both transitions."""
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                        subplot_titles=("Sit Down — Average Transition", "Stand Up — Average Transition"),
                        vertical_spacing=0.12)

    t = sit_down_norm[0]["norm_t"]
    colors = {"acc_x": "#e74c3c", "acc_y": "#27ae60", "acc_z": "#2980b9", "magnitude": "#8e44ad"}

    for row, (norm_list, label) in enumerate([(sit_down_norm, "Sit Down"), (stand_up_norm, "Stand Up")], 1):
        for axis in ["acc_x", "acc_y", "acc_z", "magnitude"]:
            matrix = np.array([n[axis] for n in norm_list])
            mean = matrix.mean(axis=0)
            fig.add_trace(go.Scatter(
                x=t, y=mean,
                mode="lines",
                line=dict(width=2, color=colors[axis]),
                name=f"{axis}" if row == 1 else None,
                showlegend=(row == 1),
                legendgroup=axis,
            ), row=row, col=1)

        fig.update_yaxes(title_text="m/s²", row=row, col=1)

    fig.update_layout(
        title="Average Human Transition — Reference Curves",
        height=700,
        hovermode="x unified",
        xaxis2_title="Normalized Time (0→1)",
    )

    filename = "average_human_transition.html"
    fig.write_html(str(output_dir / filename))
    return filename


# ─── STATISTICS REPORT ──────────────────────────────────────────────────────────

def compute_statistics(transitions, label):
    """Compute summary statistics for a set of transitions."""
    durations = []
    peak_x, peak_y, peak_z, peak_mag = [], [], [], []

    for seg in transitions:
        dur_ms = seg["timestamp_ms"].iloc[-1] - seg["timestamp_ms"].iloc[0]
        durations.append(dur_ms / 1000.0)

        peak_x.append(seg["acc_x"].abs().max())
        peak_y.append(seg["acc_y"].abs().max())
        peak_z.append(seg["acc_z"].abs().max())

        mag = np.sqrt(seg["acc_x"]**2 + seg["acc_y"]**2 + seg["acc_z"]**2)
        peak_mag.append(mag.max())

    return {
        "label": label,
        "count": len(transitions),
        "avg_duration_s": np.mean(durations),
        "min_duration_s": np.min(durations),
        "max_duration_s": np.max(durations),
        "std_duration_s": np.std(durations),
        "peak_x": np.max(peak_x),
        "peak_y": np.max(peak_y),
        "peak_z": np.max(peak_z),
        "peak_magnitude": np.max(peak_mag),
        "mean_peak_magnitude": np.mean(peak_mag),
    }


def detect_outliers(normalized_list, threshold_factor=2.5):
    """Detect outlier transitions using mean distance from centroid."""
    n = len(normalized_list)
    if n < 3:
        return []

    # Compute centroid
    all_vecs = []
    for norm in normalized_list:
        vec = np.concatenate([norm["acc_x"], norm["acc_y"], norm["acc_z"]])
        all_vecs.append(vec)

    centroid = np.mean(all_vecs, axis=0)
    distances = [euclidean(v, centroid) for v in all_vecs]

    mean_dist = np.mean(distances)
    std_dist = np.std(distances)
    threshold = mean_dist + threshold_factor * std_dist

    outliers = [i for i, d in enumerate(distances) if d > threshold]
    return outliers, distances


def write_report(sit_stats, stand_stats, sit_outliers, stand_outliers, output_dir):
    """Write the markdown statistics report."""
    report_path = output_dir / "transition_statistics.md"

    lines = [
        "# Transition Analysis Report",
        "",
        f"Generated: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "---",
        "",
        "## Sit-Down Transitions",
        "",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Count | {sit_stats['count']} |",
        f"| Average Duration | {sit_stats['avg_duration_s']:.2f} s |",
        f"| Min Duration | {sit_stats['min_duration_s']:.2f} s |",
        f"| Max Duration | {sit_stats['max_duration_s']:.2f} s |",
        f"| Std Duration | {sit_stats['std_duration_s']:.2f} s |",
        f"| Peak X | {sit_stats['peak_x']:.4f} m/s² |",
        f"| Peak Y | {sit_stats['peak_y']:.4f} m/s² |",
        f"| Peak Z | {sit_stats['peak_z']:.4f} m/s² |",
        f"| Peak Magnitude | {sit_stats['peak_magnitude']:.4f} m/s² |",
        f"| Mean Peak Magnitude | {sit_stats['mean_peak_magnitude']:.4f} m/s² |",
        "",
        "## Stand-Up Transitions",
        "",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Count | {stand_stats['count']} |",
        f"| Average Duration | {stand_stats['avg_duration_s']:.2f} s |",
        f"| Min Duration | {stand_stats['min_duration_s']:.2f} s |",
        f"| Max Duration | {stand_stats['max_duration_s']:.2f} s |",
        f"| Std Duration | {stand_stats['std_duration_s']:.2f} s |",
        f"| Peak X | {stand_stats['peak_x']:.4f} m/s² |",
        f"| Peak Y | {stand_stats['peak_y']:.4f} m/s² |",
        f"| Peak Z | {stand_stats['peak_z']:.4f} m/s² |",
        f"| Peak Magnitude | {stand_stats['peak_magnitude']:.4f} m/s² |",
        f"| Mean Peak Magnitude | {stand_stats['mean_peak_magnitude']:.4f} m/s² |",
        "",
        "---",
        "",
        "## Outlier Detection",
        "",
        f"Method: Euclidean distance from centroid > mean + 2.5σ",
        "",
    ]

    if sit_outliers:
        lines.append(f"**Sit-Down outliers:** Cycles {', '.join(str(i+1) for i in sit_outliers)}")
    else:
        lines.append("**Sit-Down outliers:** None detected")

    lines.append("")

    if stand_outliers:
        lines.append(f"**Stand-Up outliers:** Cycles {', '.join(str(i+1) for i in stand_outliers)}")
    else:
        lines.append("**Stand-Up outliers:** None detected")

    lines += [
        "",
        "---",
        "",
        "## Generated Files",
        "",
        "| File | Description |",
        "|------|-------------|",
        "| sit_down_overlay_xyz.html | All sit-down transitions overlaid |",
        "| stand_up_overlay_xyz.html | All stand-up transitions overlaid |",
        "| sit_down_mean.html | Mean ± 1σ for sit-down |",
        "| stand_up_mean.html | Mean ± 1σ for stand-up |",
        "| transition_similarity_heatmap.html | Pairwise distance heatmap |",
        "| average_human_transition.html | Reference mean curves |",
        "| transition_statistics.md | This report |",
    ]

    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path


# ─── MAIN ───────────────────────────────────────────────────────────────────────

def find_session_csv(participant=None, session=None, file_path=None):
    """Locate the session CSV."""
    if file_path:
        p = Path(file_path)
        if not p.exists():
            print(f"Error: {p} not found")
            sys.exit(1)
        return p

    if participant:
        participant_dir = DATASETS_RAW / participant
        if not participant_dir.exists():
            print(f"Error: No data for participant '{participant}'")
            sys.exit(1)
        csvs = sorted(participant_dir.glob("*.csv"))
        if session is not None:
            pattern = f"*session_{session:03d}*"
            csvs = sorted(participant_dir.glob(pattern))
        if not csvs:
            print(f"Error: No CSV files found")
            sys.exit(1)
        return csvs[0]

    # Default: find the largest session file
    all_csvs = sorted(DATASETS_RAW.rglob("*.csv"), key=lambda p: p.stat().st_size, reverse=True)
    if not all_csvs:
        print("Error: No CSV files found in datasets/raw/")
        sys.exit(1)
    return all_csvs[0]


def main():
    parser = argparse.ArgumentParser(description="Transition consistency analysis")
    parser.add_argument("--file", "-f", default=None, help="Path to session CSV")
    parser.add_argument("--participant", "-p", default=None, help="Participant ID")
    parser.add_argument("--session", "-s", type=int, default=None, help="Session number")
    args = parser.parse_args()

    csv_path = find_session_csv(args.participant, args.session, args.file)
    print(f"Analyzing: {csv_path.name}")

    df = pd.read_csv(csv_path)
    print(f"  {len(df)} samples, labels: {df['activity_label'].value_counts().to_dict()}")

    # ─── EXTRACT ────────────────────────────────────────────────────
    sit_down_raw = extract_transitions(df, "SIT_DOWN")
    stand_up_raw = extract_transitions(df, "STAND_UP")
    print(f"  Extracted: {len(sit_down_raw)} sit-down, {len(stand_up_raw)} stand-up transitions")

    # ─── NORMALIZE ──────────────────────────────────────────────────
    sit_down_norm = [normalize_transition(s) for s in sit_down_raw]
    sit_down_norm = [n for n in sit_down_norm if n is not None]

    stand_up_norm = [normalize_transition(s) for s in stand_up_raw]
    stand_up_norm = [n for n in stand_up_norm if n is not None]
    print(f"  Normalized: {len(sit_down_norm)} sit-down, {len(stand_up_norm)} stand-up")

    # ─── OUTPUT DIR ─────────────────────────────────────────────────
    ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)
    print(f"  Output: {ANALYSIS_DIR}/")

    # ─── OVERLAY PLOTS ──────────────────────────────────────────────
    print("\n  Generating overlay plots...")
    f1 = plot_overlay(sit_down_norm, "SIT_DOWN", ANALYSIS_DIR)
    f2 = plot_overlay(stand_up_norm, "STAND_UP", ANALYSIS_DIR)
    print(f"    OK {f1}")
    print(f"    OK {f2}")

    # ─── MEAN CURVES ───────────────────────────────────────────────
    print("  Generating mean curves...")
    f3 = plot_mean_curve(sit_down_norm, "SIT_DOWN", ANALYSIS_DIR)
    f4 = plot_mean_curve(stand_up_norm, "STAND_UP", ANALYSIS_DIR)
    print(f"    OK {f3}")
    print(f"    OK {f4}")

    # ─── SIMILARITY HEATMAP ────────────────────────────────────────
    print("  Computing similarity matrix...")
    f5 = plot_similarity_heatmap(sit_down_norm, stand_up_norm, ANALYSIS_DIR)
    print(f"    OK {f5}")

    # ─── AVERAGE HUMAN TRANSITION ──────────────────────────────────
    print("  Generating average human transition...")
    f6 = plot_average_human(sit_down_norm, stand_up_norm, ANALYSIS_DIR)
    print(f"    OK {f6}")

    # ─── STATISTICS ─────────────────────────────────────────────────
    print("  Computing statistics...")
    sit_stats = compute_statistics(sit_down_raw, "SIT_DOWN")
    stand_stats = compute_statistics(stand_up_raw, "STAND_UP")

    # ─── OUTLIER DETECTION ──────────────────────────────────────────
    sit_outliers, sit_distances = detect_outliers(sit_down_norm)
    stand_outliers, stand_distances = detect_outliers(stand_up_norm)

    if sit_outliers:
        print(f"  WARNING: Sit-down outliers: cycles {[i+1 for i in sit_outliers]}")
    if stand_outliers:
        print(f"  WARNING: Stand-up outliers: cycles {[i+1 for i in stand_outliers]}")

    # ─── REPORT ─────────────────────────────────────────────────────
    report_path = write_report(sit_stats, stand_stats, sit_outliers, stand_outliers, ANALYSIS_DIR)
    print(f"    OK {report_path.name}")

    # ─── SUMMARY ────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("  ANALYSIS COMPLETE")
    print("=" * 60)
    print(f"  Sit-Down: {sit_stats['count']} transitions, avg {sit_stats['avg_duration_s']:.2f}s")
    print(f"  Stand-Up: {stand_stats['count']} transitions, avg {stand_stats['avg_duration_s']:.2f}s")
    print(f"  Output directory: {ANALYSIS_DIR}")
    print("=" * 60)


if __name__ == "__main__":
    main()
