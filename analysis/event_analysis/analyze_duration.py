"""
Duration analysis for accepted and rejected events.

Generates distribution plots, scatter plots, box plots, summary statistics,
and an outlier report to investigate whether event duration naturally
separates valid transitions from noise.

This script does NOT recommend thresholds or modify acceptance logic.
It only collects evidence.

Run from the project root:

    python analysis/event_analysis/analyze_duration.py
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import List

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

DEFAULT_ACCEPTED_DIR = Path("debug/events")
DEFAULT_REJECTED_DIR = Path("debug/rejected_events")
DEFAULT_OUTPUT_DIR = Path("analysis/event_analysis/reports/duration")


def load_events(directory: Path, label: str) -> List[dict]:
    """Load event summaries from a directory and tag with accepted/rejected."""
    if not directory.exists():
        return []

    rows = []
    for path in sorted(directory.glob("event_*/event_summary.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        general = data.get("general", {})
        context = data.get("context", {})
        movement = data.get("movement", {})
        timing = data.get("timing", {})
        combined_std = data.get("combined_std", {})
        validation = data.get("validation", {})
        stages = validation.get("stages", {})
        movement_stage = stages.get("movement", {})
        movement_metrics = movement_stage.get("metrics", {})
        orientation_stage = stages.get("orientation", {})
        orientation_metrics = orientation_stage.get("metrics", {})
        legacy = validation.get("legacy_orientation_metrics", {})

        row = {
            "event_id": general.get("event_id"),
            "label": label,
            "event_dir": str(path.parent),
            "duration_ms": general.get("duration_ms"),
            "sample_count": general.get("total_samples"),
            "sampling_rate_hz": general.get("sampling_rate_hz"),
            "average_sample_period_ms": (
                timing.get("average_sample_period_ms")
                or general.get("average_sample_period_ms")
            ),
            "transition_duration_ms": (
                timing.get("transition_duration_ms")
                or movement.get("movement_duration_ms")
            ),
            "pre_context_duration_ms": timing.get("pre_context_duration_ms"),
            "post_context_duration_ms": timing.get("post_context_duration_ms"),
            "debounce_merges": movement.get("debounce_merges", 0),
            "combined_std_transition": combined_std.get("transition"),
            "movement_score": movement_metrics.get("rolling_std_peak"),
            "rolling_std_mean": movement_metrics.get("rolling_std_mean"),
            "orientation_delta_y": orientation_metrics.get("delta_y"),
            "orientation_delta_z": orientation_metrics.get("delta_z"),
            "orientation_result": (
                "pass" if orientation_stage.get("passed") else "fail"
            ) if orientation_stage else None,
            "angle_change_deg": legacy.get("angle_change_deg"),
            "status": validation.get("status", label),
            "rejection_stage": validation.get("rejection_stage"),
        }
        rows.append(row)
    return rows


def build_dataframe(accepted_dir: Path, rejected_dir: Path) -> pd.DataFrame:
    rows: List[dict] = []
    rows.extend(load_events(accepted_dir, "accepted"))
    rows.extend(load_events(rejected_dir, "rejected"))
    return pd.DataFrame(rows)


def write_duration_histogram(df: pd.DataFrame, output_dir: Path) -> None:
    fig = go.Figure()
    for label, color in [("accepted", "#2ecc71"), ("rejected", "#e74c3c")]:
        subset = df[df["label"] == label]["duration_ms"].dropna()
        if subset.empty:
            continue
        fig.add_trace(go.Histogram(
            x=subset,
            name=label,
            opacity=0.65,
            marker_color=color,
            nbinsx=30,
        ))
    fig.update_layout(
        title="Event Duration Distribution: Accepted vs Rejected",
        xaxis_title="duration_ms",
        yaxis_title="count",
        barmode="overlay",
        template="plotly_white",
    )
    fig.write_html(output_dir / "duration_histogram.html")


def write_scatter_duration_vs_std(df: pd.DataFrame, output_dir: Path) -> None:
    fig = px.scatter(
        df,
        x="duration_ms",
        y="combined_std_transition",
        color="label",
        color_discrete_map={"accepted": "#2ecc71", "rejected": "#e74c3c"},
        hover_data=["event_id", "sample_count"],
        title="Duration vs Combined Transition STD",
    )
    fig.update_layout(template="plotly_white")
    fig.write_html(output_dir / "scatter_duration_vs_std.html")


def write_scatter_duration_vs_movement(df: pd.DataFrame, output_dir: Path) -> None:
    fig = px.scatter(
        df,
        x="duration_ms",
        y="movement_score",
        color="label",
        color_discrete_map={"accepted": "#2ecc71", "rejected": "#e74c3c"},
        hover_data=["event_id", "sample_count"],
        title="Duration vs Movement Score (Rolling STD Peak)",
    )
    fig.update_layout(template="plotly_white")
    fig.write_html(output_dir / "scatter_duration_vs_movement.html")


def write_scatter_duration_vs_orientation(df: pd.DataFrame, output_dir: Path) -> None:
    y_col = "angle_change_deg"
    y_title = "Orientation Angle Change (deg)"
    if df[y_col].isna().all():
        y_col = "orientation_delta_y"
        y_title = "Orientation Delta Y"

    fig = px.scatter(
        df,
        x="duration_ms",
        y=y_col,
        color="label",
        color_discrete_map={"accepted": "#2ecc71", "rejected": "#e74c3c"},
        hover_data=["event_id", "sample_count"],
        title=f"Duration vs {y_title}",
    )
    fig.update_layout(template="plotly_white")
    fig.write_html(output_dir / "scatter_duration_vs_orientation.html")


def write_box_plot(df: pd.DataFrame, output_dir: Path) -> None:
    fig = px.box(
        df,
        x="label",
        y="duration_ms",
        color="label",
        color_discrete_map={"accepted": "#2ecc71", "rejected": "#e74c3c"},
        points="all",
        title="Duration Distribution: Accepted vs Rejected",
    )
    fig.update_layout(template="plotly_white")
    fig.write_html(output_dir / "duration_box_plot.html")


def write_summary_table(df: pd.DataFrame, output_dir: Path) -> None:
    lines = ["# Duration Summary Statistics", ""]
    lines.append("| metric | accepted | rejected |")
    lines.append("|---|---:|---:|")

    accepted = df[df["label"] == "accepted"]["duration_ms"].dropna()
    rejected = df[df["label"] == "rejected"]["duration_ms"].dropna()

    metrics = [
        ("count", lambda s: len(s)),
        ("mean", lambda s: s.mean()),
        ("median", lambda s: s.median()),
        ("std", lambda s: s.std()),
        ("min", lambda s: s.min()),
        ("max", lambda s: s.max()),
        ("25th percentile", lambda s: s.quantile(0.25) if len(s) else None),
        ("75th percentile", lambda s: s.quantile(0.75) if len(s) else None),
    ]
    for name, fn in metrics:
        a_val = fn(accepted) if len(accepted) else None
        r_val = fn(rejected) if len(rejected) else None
        lines.append(f"| {name} | {_fmt(a_val)} | {_fmt(r_val)} |")

    lines.append("")
    lines.append("## Transition Duration (movement region only)")
    lines.append("")
    lines.append("| metric | accepted | rejected |")
    lines.append("|---|---:|---:|")

    accepted_t = df[df["label"] == "accepted"]["transition_duration_ms"].dropna()
    rejected_t = df[df["label"] == "rejected"]["transition_duration_ms"].dropna()

    for name, fn in metrics:
        a_val = fn(accepted_t) if len(accepted_t) else None
        r_val = fn(rejected_t) if len(rejected_t) else None
        lines.append(f"| {name} | {_fmt(a_val)} | {_fmt(r_val)} |")

    (output_dir / "duration_summary.md").write_text("\n".join(lines), encoding="utf-8")


def write_outlier_report(df: pd.DataFrame, output_dir: Path) -> None:
    lines = ["# Duration Outlier Report", ""]
    lines.append("This report lists the shortest and longest events for investigation.")
    lines.append("It does NOT recommend a threshold. It only presents evidence.")
    lines.append("")

    sorted_df = df.sort_values("duration_ms", ascending=True).reset_index(drop=True)

    lines.append("## Shortest 10 Events")
    lines.append("")
    _append_event_table(lines, sorted_df.head(10))

    lines.append("")
    lines.append("## Longest 10 Events")
    lines.append("")
    _append_event_table(lines, sorted_df.tail(10).iloc[::-1])

    (output_dir / "duration_outliers.md").write_text("\n".join(lines), encoding="utf-8")


def _append_event_table(lines: List[str], subset: pd.DataFrame) -> None:
    lines.append(
        "| event_id | label | duration_ms | sample_count | combined_std | "
        "movement_score | orientation | event_dir |"
    )
    lines.append("|---:|---|---:|---:|---:|---:|---|---|")
    for _, row in subset.iterrows():
        ori = row.get("orientation_result")
        orientation_str = ori if (ori and str(ori) not in ("nan", "None")) else "N/A"
        lines.append(
            f"| {_fmt_int(row['event_id'])} "
            f"| {row['label']} "
            f"| {_fmt(row['duration_ms'])} "
            f"| {_fmt_int(row['sample_count'])} "
            f"| {_fmt(row['combined_std_transition'])} "
            f"| {_fmt(row['movement_score'])} "
            f"| {orientation_str} "
            f"| `{row['event_dir']}` |"
        )


def _fmt(value) -> str:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return "N/A"
    if isinstance(value, float):
        return f"{value:.2f}"
    return str(value)


def _fmt_int(value) -> str:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return "N/A"
    return str(int(value))


def main() -> None:
    parser = argparse.ArgumentParser(description="Duration analysis for event detection.")
    parser.add_argument("--accepted-dir", default=str(DEFAULT_ACCEPTED_DIR))
    parser.add_argument("--rejected-dir", default=str(DEFAULT_REJECTED_DIR))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    df = build_dataframe(Path(args.accepted_dir), Path(args.rejected_dir))

    if df.empty:
        print("No events found.")
        return

    print(f"Loaded {len(df)} events ({(df['label'] == 'accepted').sum()} accepted, "
          f"{(df['label'] == 'rejected').sum()} rejected)")

    df.to_csv(output_dir / "duration_data.csv", index=False)

    write_duration_histogram(df, output_dir)
    write_scatter_duration_vs_std(df, output_dir)
    write_scatter_duration_vs_movement(df, output_dir)
    write_scatter_duration_vs_orientation(df, output_dir)
    write_box_plot(df, output_dir)
    write_summary_table(df, output_dir)
    write_outlier_report(df, output_dir)

    print(f"Reports written to: {output_dir}")
    print(f"  duration_histogram.html")
    print(f"  scatter_duration_vs_std.html")
    print(f"  scatter_duration_vs_movement.html")
    print(f"  scatter_duration_vs_orientation.html")
    print(f"  duration_box_plot.html")
    print(f"  duration_summary.md")
    print(f"  duration_outliers.md")
    print(f"  duration_data.csv")


if __name__ == "__main__":
    main()
