"""
Analyze accepted and rejected event summaries.

Run from the project root:

    python analysis/event_analysis/analyze_events.py
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable, List

import pandas as pd
import plotly.express as px


DEFAULT_ACCEPTED_DIR = Path("debug/events")
DEFAULT_REJECTED_DIR = Path("debug/rejected_events")
DEFAULT_OUTPUT_DIR = Path("analysis/event_analysis/reports")


def find_summaries(directory: Path, default_status: str) -> Iterable[dict]:
    """Yield flattened rows from event_summary.json files."""
    if not directory.exists():
        return []

    rows = []
    for path in sorted(directory.glob("event_*/event_summary.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        delta = data.get("delta_features", {})
        stats = data.get("statistical_features", {})
        combined_std = data.get("combined_std", {})
        relative_std = data.get("relative_std_metrics", {})
        validation = data.get("validation", {})
        legacy = validation.get("legacy_orientation_metrics", {})
        movement = data.get("movement", {})
        general = data.get("general", {})
        rolling_std = validation.get("rolling_std_metrics", {})
        stability_diag = validation.get("stability_diagnostics", {})

        timing = data.get("timing", {})

        row = {
            "event_dir": str(path.parent),
            "event_id": general.get("event_id"),
            "validation_pipeline_version": validation.get("validation_pipeline_version"),
            "status": validation.get("status", default_status),
            "is_valid": validation.get("is_valid", default_status == "VALID_TRANSITION"),
            "reason": validation.get("reason", ""),
            "validation_stage_passed": validation.get("validation_stage_passed"),
            "validation_stage_failed": validation.get("validation_stage_failed"),
            "rejection_stage": validation.get("rejection_stage"),
            "duration_ms": general.get("duration_ms"),
            "sample_count": general.get("total_samples"),
            "average_sample_period_ms": timing.get("average_sample_period_ms") or general.get("average_sample_period_ms"),
            "transition_duration_ms": timing.get("transition_duration_ms") or movement.get("movement_duration_ms"),
            "pre_context_duration_ms": timing.get("pre_context_duration_ms"),
            "post_context_duration_ms": timing.get("post_context_duration_ms"),
            "debounce_merges": movement.get("debounce_merges", 0),
            "movement_duration_ms": movement.get("movement_duration_ms"),
            "delta_mean_x": delta.get("delta_mean_x"),
            "delta_mean_y": delta.get("delta_mean_y"),
            "delta_mean_z": delta.get("delta_mean_z"),
            "movement_energy": stats.get("movement_energy"),
            "combined_std_pre": combined_std.get("pre"),
            "combined_std_transition": combined_std.get("transition"),
            "combined_std_post": combined_std.get("post"),
            "stable_average_std": relative_std.get("stable_average_std"),
            "transition_vs_pre_std": relative_std.get("transition_vs_pre"),
            "transition_vs_post_std": relative_std.get("transition_vs_post"),
            "transition_vs_average_stable_std": relative_std.get("transition_vs_average_stable"),
            "rolling_std_peak": rolling_std.get("rolling_std_peak"),
            "rolling_std_mean": rolling_std.get("rolling_std_mean"),
            "rolling_std_duration_above_threshold": rolling_std.get("rolling_std_duration_above_threshold"),
            "stability_diag_pre_std": stability_diag.get("combined_std_pre"),
            "stability_diag_post_std": stability_diag.get("combined_std_post"),
            "stability_diag_transition_std": stability_diag.get("combined_std_transition"),
            "stability_diag_stable_avg": stability_diag.get("stable_average_std"),
            "stability_diag_ratio": stability_diag.get("transition_to_stable_ratio"),
            "legacy_gravity_angle_change_deg": legacy.get("angle_change_deg"),
        }
        rows.append(row)
    return rows


def build_event_statistics(accepted_dir: Path, rejected_dir: Path) -> pd.DataFrame:
    """Load accepted and rejected summaries into one DataFrame."""
    rows: List[dict] = []
    rows.extend(find_summaries(accepted_dir, "VALID_TRANSITION"))
    rows.extend(find_summaries(rejected_dir, "REJECT_EVENT"))
    return pd.DataFrame(rows)


def write_statistics(df: pd.DataFrame, output_dir: Path) -> None:
    """Write CSV, aggregate markdown, and Plotly distribution plots."""
    output_dir.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_dir / "event_statistics.csv", index=False)
    _write_overall_stats(df, output_dir / "overall_statistics.md")
    _write_distribution_plots(df, output_dir)


def _write_overall_stats(df: pd.DataFrame, output_path: Path) -> None:
    lines = ["# Event Statistics", ""]
    if df.empty:
        lines.append("No event summaries found.")
        output_path.write_text("\n".join(lines), encoding="utf-8")
        return

    accepted_count = int(df["is_valid"].fillna(False).sum())
    rejected_count = int((~df["is_valid"].fillna(False)).sum())
    lines.extend(
        [
            f"- Total events: {len(df)}",
            f"- Accepted events: {accepted_count}",
            f"- Rejected events: {rejected_count}",
            "",
        ]
    )

    if rejected_count > 0:
        rejection_breakdown = df[~df["is_valid"].fillna(False)]["rejection_stage"].value_counts()
        lines.append("## Rejection Stage Breakdown")
        lines.append("")
        for stage, count in rejection_breakdown.items():
            lines.append(f"- {stage}: {count}")
        lines.append("")

    lines.extend(["## Numeric Summary", ""])
    numeric_columns = [
        "duration_ms",
        "movement_duration_ms",
        "delta_mean_x",
        "delta_mean_y",
        "delta_mean_z",
        "movement_energy",
        "combined_std_pre",
        "combined_std_transition",
        "combined_std_post",
        "stable_average_std",
        "transition_vs_pre_std",
        "transition_vs_post_std",
        "transition_vs_average_stable_std",
        "rolling_std_peak",
        "rolling_std_mean",
        "rolling_std_duration_above_threshold",
        "legacy_gravity_angle_change_deg",
    ]
    available = [c for c in numeric_columns if c in df.columns]
    summary = df[available].describe().transpose()
    lines.append("| metric | count | mean | std | min | max |")
    lines.append("|---|---:|---:|---:|---:|---:|")
    for metric, row in summary.iterrows():
        lines.append(
            f"| {metric} | {_fmt(row.get('count'))} | {_fmt(row.get('mean'))} | "
            f"{_fmt(row.get('std'))} | {_fmt(row.get('min'))} | {_fmt(row.get('max'))} |"
        )
    output_path.write_text("\n".join(lines), encoding="utf-8")


def _write_distribution_plots(df: pd.DataFrame, output_dir: Path) -> None:
    if df.empty:
        return

    plots = {
        "delta_mean_x_distribution.html": "delta_mean_x",
        "delta_mean_y_distribution.html": "delta_mean_y",
        "delta_mean_z_distribution.html": "delta_mean_z",
        "movement_duration_distribution.html": "movement_duration_ms",
        "movement_energy_distribution.html": "movement_energy",
        "combined_std_pre_distribution.html": "combined_std_pre",
        "combined_std_transition_distribution.html": "combined_std_transition",
        "combined_std_post_distribution.html": "combined_std_post",
        "stable_average_std_distribution.html": "stable_average_std",
        "transition_vs_pre_std_distribution.html": "transition_vs_pre_std",
        "transition_vs_post_std_distribution.html": "transition_vs_post_std",
        "transition_vs_average_stable_std_distribution.html": "transition_vs_average_stable_std",
        "rolling_std_peak_distribution.html": "rolling_std_peak",
        "rolling_std_mean_distribution.html": "rolling_std_mean",
        "rolling_std_duration_distribution.html": "rolling_std_duration_above_threshold",
        "legacy_gravity_angle_change_distribution.html": "legacy_gravity_angle_change_deg",
    }
    for filename, column in plots.items():
        if column in df.columns:
            fig = px.histogram(df, x=column, color="status", marginal="box", title=column)
            fig.write_html(output_dir / filename)

    counts = df.groupby(["status"]).size().reset_index(name="count")
    fig = px.bar(counts, x="status", y="count", title="Accepted vs Rejected Events")
    fig.write_html(output_dir / "accepted_vs_rejected.html")

    if "rejection_stage" in df.columns:
        rejected_df = df[df["rejection_stage"].notna()]
        if not rejected_df.empty:
            stage_counts = rejected_df.groupby("rejection_stage").size().reset_index(name="count")
            fig = px.bar(stage_counts, x="rejection_stage", y="count", title="Rejections by Stage")
            fig.write_html(output_dir / "rejections_by_stage.html")


def _fmt(value: object) -> str:
    if pd.isna(value):
        return "N/A"
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value)


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze event_summary.json files.")
    parser.add_argument("--accepted-dir", default=str(DEFAULT_ACCEPTED_DIR))
    parser.add_argument("--rejected-dir", default=str(DEFAULT_REJECTED_DIR))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    args = parser.parse_args()

    df = build_event_statistics(Path(args.accepted_dir), Path(args.rejected_dir))
    write_statistics(df, Path(args.output_dir))
    print(f"Events analyzed: {len(df)}")
    if not df.empty:
        accepted = int(df["is_valid"].fillna(False).sum())
        rejected = len(df) - accepted
        print(f"  Accepted: {accepted}")
        print(f"  Rejected: {rejected}")
        if "rejection_stage" in df.columns:
            breakdown = df[df["rejection_stage"].notna()]["rejection_stage"].value_counts()
            for stage, count in breakdown.items():
                print(f"    Rejected at {stage}: {count}")
    print(f"Saved: {Path(args.output_dir) / 'event_statistics.csv'}")


if __name__ == "__main__":
    main()
