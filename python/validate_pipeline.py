"""
validate_pipeline.py — Single-cycle validation experiment.

Captures exactly ONE sit/stand cycle, validates the data, generates
interactive Plotly visualizations, and prints a transition report.

Protocol:
    STANDING (5s) → SIT_DOWN (untimed) → SITTING (5s) → STAND_UP (untimed) → STANDING (5s)

Usage:
    python validate_pipeline.py
    python validate_pipeline.py --port COM5
    python validate_pipeline.py --participant VAL01
"""

import argparse
import csv
import math
import sys
import time
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

sys.path.insert(0, str(Path(__file__).parent))
from config import DATASETS_RAW, PLOTS_DIR, SAMPLING_RATE_HZ, SERIAL_BAUD
from utils import connect_serial, parse_csv_line, read_serial_lines

# Validation protocol: 5 phases, 1 cycle
VALIDATION_PHASES = [
    ("STANDING", 5),
    ("SIT_DOWN", None),   # untimed
    ("SITTING", 5),
    ("STAND_UP", None),   # untimed
    ("STANDING", 5),
]

PHASE_COLORS = {
    "STANDING": "rgba(46, 204, 113, 0.2)",
    "SIT_DOWN": "rgba(230, 126, 34, 0.3)",
    "SITTING": "rgba(52, 152, 219, 0.2)",
    "STAND_UP": "rgba(155, 89, 182, 0.3)",
}

CSV_COLUMNS = [
    "participant_id",
    "timestamp_ms",
    "acc_x",
    "acc_y",
    "acc_z",
    "activity_label",
    "cycle_number",
]


def beep():
    print("\a", end="", flush=True)


def drain(ser, writer, participant_id, label, count_ref):
    """Read all pending serial data and write rows."""
    lines = read_serial_lines(ser)
    for line in lines:
        parsed = parse_csv_line(line)
        if parsed is None:
            continue
        ts, ax, ay, az = parsed
        writer.writerow([participant_id, ts, ax, ay, az, label, 1])
        count_ref[0] += 1


def run_timed_phase(ser, writer, participant_id, label, duration, count_ref):
    """Timed hold — collects for exactly `duration` seconds."""
    start = time.time()
    while (time.time() - start) < duration:
        drain(ser, writer, participant_id, label, count_ref)
        remaining = duration - (time.time() - start)
        print(f"\r     {remaining:.0f}s remaining | {count_ref[0]} samples", end="")
        time.sleep(0.01)
    print()


def run_untimed_phase(ser, writer, participant_id, label, count_ref):
    """Untimed transition — collects until ENTER."""
    print("     Move naturally. Press ENTER when done.")
    if sys.platform == "win32":
        import msvcrt
        while True:
            drain(ser, writer, participant_id, label, count_ref)
            print(f"\r     Recording... {count_ref[0]} samples | Press ENTER when done", end="")
            if msvcrt.kbhit():
                key = msvcrt.getwch()
                if key in ("\r", "\n"):
                    break
            time.sleep(0.01)
    else:
        import select
        while True:
            drain(ser, writer, participant_id, label, count_ref)
            print(f"\r     Recording... {count_ref[0]} samples | Press ENTER when done", end="")
            ready, _, _ = select.select([sys.stdin], [], [], 0.01)
            if ready:
                sys.stdin.readline()
                break
    print()


# ─── CAPTURE ────────────────────────────────────────────────────────────────────

def capture(ser, participant_id, output_path):
    """Run one validation cycle. Returns the CSV path."""
    sample_count = [0]

    with open(output_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(CSV_COLUMNS)

        for label, duration in VALIDATION_PHASES:
            beep()
            if duration is not None:
                print(f"\n  >> {label} — Hold still ({duration}s)")
                run_timed_phase(ser, writer, participant_id, label, duration, sample_count)
            else:
                action = "Sit down" if label == "SIT_DOWN" else "Stand up"
                print(f"\n  >> {label} — {action} at your own pace")
                run_untimed_phase(ser, writer, participant_id, label, sample_count)

    print(f"\n  Capture complete: {sample_count[0]} samples → {output_path.name}")
    return output_path


# ─── VALIDATION ─────────────────────────────────────────────────────────────────

def validate(csv_path):
    """Run data quality checks. Returns (df, report_dict, issues_list)."""
    df = pd.read_csv(csv_path)
    issues = []

    total_samples = len(df)
    duration_ms = df["timestamp_ms"].iloc[-1] - df["timestamp_ms"].iloc[0]
    duration_s = duration_ms / 1000.0

    expected_samples = int(duration_s * SAMPLING_RATE_HZ)

    intervals = df["timestamp_ms"].diff().dropna()
    mean_interval = intervals.mean()
    actual_freq = 1000.0 / mean_interval if mean_interval > 0 else 0

    duplicates = (intervals == 0).sum()
    nan_count = df[["acc_x", "acc_y", "acc_z"]].isna().sum().sum()

    # Gaps: intervals > 3x expected (60ms for 50Hz)
    expected_interval = 1000.0 / SAMPLING_RATE_HZ
    gap_threshold = expected_interval * 3
    gaps = intervals[intervals > gap_threshold]
    missing_count = len(gaps)

    # Check sample count within tolerance
    sample_ratio = total_samples / expected_samples if expected_samples > 0 else 0
    if sample_ratio < 0.9:
        issues.append(f"Low sample count: got {total_samples}, expected ~{expected_samples} ({sample_ratio:.1%})")
    if sample_ratio > 1.1:
        issues.append(f"High sample count: got {total_samples}, expected ~{expected_samples} ({sample_ratio:.1%})")

    if duplicates > 0:
        issues.append(f"{duplicates} duplicate timestamps detected")
    if nan_count > 0:
        issues.append(f"{nan_count} NaN values in acceleration columns")
    if missing_count > 0:
        issues.append(f"{missing_count} timestamp gaps > {gap_threshold:.0f}ms")

    # Frequency check
    if abs(actual_freq - SAMPLING_RATE_HZ) > 5:
        issues.append(f"Sampling frequency {actual_freq:.1f} Hz deviates from expected {SAMPLING_RATE_HZ} Hz")

    report = {
        "total_samples": total_samples,
        "expected_samples": expected_samples,
        "duration_s": round(duration_s, 2),
        "mean_interval_ms": round(mean_interval, 2),
        "std_interval_ms": round(intervals.std(), 2),
        "min_interval_ms": round(intervals.min(), 2),
        "max_interval_ms": round(intervals.max(), 2),
        "actual_frequency_hz": round(actual_freq, 2),
        "duplicate_timestamps": int(duplicates),
        "nan_values": int(nan_count),
        "timestamp_gaps": int(missing_count),
    }

    return df, report, issues


def print_validation_report(report, issues):
    """Print the validation report to console."""
    print("\n" + "=" * 60)
    print("  VALIDATION REPORT")
    print("=" * 60)
    print(f"  Total Samples:         {report['total_samples']}")
    print(f"  Expected Samples:      ~{report['expected_samples']}")
    print(f"  Duration:              {report['duration_s']}s")
    print(f"  Mean Interval:         {report['mean_interval_ms']} ms")
    print(f"  Std Interval:          {report['std_interval_ms']} ms")
    print(f"  Min Interval:          {report['min_interval_ms']} ms")
    print(f"  Max Interval:          {report['max_interval_ms']} ms")
    print(f"  Actual Frequency:      {report['actual_frequency_hz']} Hz")
    print(f"  Duplicate Timestamps:  {report['duplicate_timestamps']}")
    print(f"  NaN Values:            {report['nan_values']}")
    print(f"  Timestamp Gaps:        {report['timestamp_gaps']}")
    print()

    if issues:
        print("  ⚠ ISSUES DETECTED:")
        for issue in issues:
            print(f"    - {issue}")
    else:
        print("  ✓ ALL CHECKS PASSED")
    print("=" * 60)


# ─── VISUALIZATION ──────────────────────────────────────────────────────────────

def get_phase_regions(df):
    """Extract contiguous phase regions as (label, t_start, t_end)."""
    regions = []
    prev_label = None
    start_t = 0

    for i, label in enumerate(df["activity_label"]):
        if label != prev_label:
            if prev_label is not None:
                regions.append((prev_label, start_t, df["time_s"].iloc[i - 1]))
            start_t = df["time_s"].iloc[i]
            prev_label = label
    if prev_label is not None:
        regions.append((prev_label, start_t, df["time_s"].iloc[-1]))
    return regions


def get_transition_boundaries(df):
    """Get the time of each phase start for vertical markers."""
    boundaries = []
    prev_label = None
    for i, label in enumerate(df["activity_label"]):
        if label != prev_label:
            boundaries.append((label, df["time_s"].iloc[i]))
            prev_label = label
    return boundaries


def add_phase_backgrounds(fig, regions, row=None):
    for label, t_start, t_end in regions:
        color = PHASE_COLORS.get(label, "rgba(200,200,200,0.1)")
        fig.add_vrect(
            x0=t_start, x1=t_end,
            fillcolor=color, layer="below", line_width=0,
            row=row, col=1,
        )


def add_transition_markers(fig, boundaries, row=None):
    for label, t in boundaries:
        fig.add_vline(
            x=t, line_dash="dash", line_color="gray", line_width=1,
            annotation_text=label, annotation_position="top",
            row=row, col=1,
        )


def generate_plots(df, output_dir):
    """Generate all 5 required plots."""
    output_dir.mkdir(parents=True, exist_ok=True)
    regions = get_phase_regions(df)
    boundaries = get_transition_boundaries(df)

    # 1-3: Individual axis plots
    for axis in ["acc_x", "acc_y", "acc_z"]:
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=df["time_s"], y=df[axis],
            mode="lines", line=dict(width=0.8, color="black"),
            name=axis,
        ))
        add_phase_backgrounds(fig, regions)
        add_transition_markers(fig, boundaries)
        fig.update_layout(
            title=f"Validation — {axis.upper()} vs Time",
            xaxis_title="Time (s)",
            yaxis_title="Acceleration (m/s²)",
            hovermode="x unified",
        )
        fig.write_html(str(output_dir / f"{axis}.html"))

    # 4: Combined XYZ
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True,
                        subplot_titles=("acc_x", "acc_y", "acc_z"),
                        vertical_spacing=0.06)
    colors = ["#e74c3c", "#27ae60", "#2980b9"]
    for i, axis in enumerate(["acc_x", "acc_y", "acc_z"], 1):
        fig.add_trace(go.Scatter(
            x=df["time_s"], y=df[axis],
            mode="lines", line=dict(width=0.7, color=colors[i - 1]),
            name=axis,
        ), row=i, col=1)
        add_phase_backgrounds(fig, regions, row=i)
        add_transition_markers(fig, boundaries, row=i)
        fig.update_yaxes(title_text="m/s²", row=i, col=1)

    fig.update_layout(
        title="Validation — Combined XYZ",
        height=900,
        hovermode="x unified",
    )
    fig.update_xaxes(title_text="Time (s)", row=3, col=1)
    fig.write_html(str(output_dir / "combined_xyz.html"))

    # 5: Magnitude
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["time_s"], y=df["magnitude"],
        mode="lines", line=dict(width=0.8, color="darkred"),
        name="magnitude",
    ))
    add_phase_backgrounds(fig, regions)
    add_transition_markers(fig, boundaries)
    fig.update_layout(
        title="Validation — Acceleration Magnitude",
        xaxis_title="Time (s)",
        yaxis_title="|a| (m/s²)",
        hovermode="x unified",
    )
    fig.write_html(str(output_dir / "magnitude.html"))

    print(f"\n  Plots saved to: {output_dir}/")
    print(f"    - acc_x.html")
    print(f"    - acc_y.html")
    print(f"    - acc_z.html")
    print(f"    - combined_xyz.html")
    print(f"    - magnitude.html")


# ─── TRANSITION REPORT ──────────────────────────────────────────────────────────

def compute_transition_report(df):
    """Compute transition durations and peak accelerations."""
    duration_s = df["time_s"].iloc[-1] - df["time_s"].iloc[0]
    total_samples = len(df)

    # Extract phase segments
    sit_down = df[df["activity_label"] == "SIT_DOWN"]
    stand_up = df[df["activity_label"] == "STAND_UP"]

    sit_down_duration = 0
    sit_down_peak = 0
    if len(sit_down) > 0:
        sit_down_duration = sit_down["time_s"].iloc[-1] - sit_down["time_s"].iloc[0]
        sit_down_peak = sit_down["magnitude"].max()

    stand_up_duration = 0
    stand_up_peak = 0
    if len(stand_up) > 0:
        stand_up_duration = stand_up["time_s"].iloc[-1] - stand_up["time_s"].iloc[0]
        stand_up_peak = stand_up["magnitude"].max()

    return {
        "total_duration_s": round(duration_s, 2),
        "total_samples": total_samples,
        "sit_down_duration_s": round(sit_down_duration, 2),
        "stand_up_duration_s": round(stand_up_duration, 2),
        "sit_down_peak_magnitude": round(sit_down_peak, 4),
        "stand_up_peak_magnitude": round(stand_up_peak, 4),
    }


def print_transition_report(tr):
    print("\n" + "=" * 60)
    print("  TRANSITION REPORT")
    print("=" * 60)
    print(f"  Total Duration:              {tr['total_duration_s']}s")
    print(f"  Samples Collected:           {tr['total_samples']}")
    print(f"  Sit-Down Transition:         {tr['sit_down_duration_s']}s")
    print(f"  Stand-Up Transition:         {tr['stand_up_duration_s']}s")
    print(f"  Peak |a| during Sit-Down:    {tr['sit_down_peak_magnitude']} m/s²")
    print(f"  Peak |a| during Stand-Up:    {tr['stand_up_peak_magnitude']} m/s²")
    print("=" * 60)


# ─── MAIN ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Single-cycle validation experiment")
    parser.add_argument("--port", default=None, help="Serial port (e.g. COM5)")
    parser.add_argument("--participant", default="VALIDATION", help="Participant ID")
    args = parser.parse_args()

    participant_id = args.participant
    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")

    output_dir = DATASETS_RAW / participant_id
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / f"validation_{timestamp_str}.csv"

    plots_dir = PLOTS_DIR / f"validation_{timestamp_str}"

    # ─── BANNER ─────────────────────────────────────────────────────
    print()
    print("=" * 60)
    print("  PIPELINE VALIDATION EXPERIMENT")
    print("=" * 60)
    print()
    print("  This will record exactly ONE sit/stand cycle.")
    print()
    print("  Protocol:")
    print("    1. Stand still (5s)")
    print("    2. Sit down (your pace, press ENTER when done)")
    print("    3. Sit still (5s)")
    print("    4. Stand up (your pace, press ENTER when done)")
    print("    5. Stand still (5s)")
    print()
    print(f"  Participant: {participant_id}")
    print(f"  Output:      {csv_path.name}")
    print(f"  Rate:        {SAMPLING_RATE_HZ} Hz")
    print()
    input("  Press ENTER to begin...")

    # ─── CONNECT ────────────────────────────────────────────────────
    ser = connect_serial(port=args.port, baud=SERIAL_BAUD)

    # Flush any boot messages
    time.sleep(1)
    while ser.in_waiting:
        ser.readline()

    # ─── CAPTURE ────────────────────────────────────────────────────
    try:
        capture(ser, participant_id, csv_path)
    except KeyboardInterrupt:
        print("\n\n  Capture interrupted.")
        ser.close()
        sys.exit(1)
    finally:
        ser.close()

    # ─── VALIDATE ───────────────────────────────────────────────────
    df, report, issues = validate(csv_path)
    print_validation_report(report, issues)

    # ─── DERIVED COLUMNS ────────────────────────────────────────────
    df["time_s"] = (df["timestamp_ms"] - df["timestamp_ms"].iloc[0]) / 1000.0
    df["magnitude"] = np.sqrt(df["acc_x"]**2 + df["acc_y"]**2 + df["acc_z"]**2)

    # ─── VISUALIZE ──────────────────────────────────────────────────
    generate_plots(df, plots_dir)

    # ─── TRANSITION REPORT ──────────────────────────────────────────
    tr = compute_transition_report(df)
    print_transition_report(tr)

    # ─── FINAL STATUS ───────────────────────────────────────────────
    print()
    if issues:
        print("  STATUS: ISSUES DETECTED — review plots before proceeding.")
    else:
        print("  STATUS: PIPELINE VALIDATED — ready for multi-participant collection.")
    print()


if __name__ == "__main__":
    main()
