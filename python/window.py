"""
window.py — Extract overlapping windows from raw session CSVs.

Input:  Raw CSV (timestamp_ms, acc_x, acc_y, acc_z, activity_label)
Output: Individual window CSVs organized by label.

No feature engineering — just time-sliced raw data for future training.

Usage:
    python window.py --participant P01
    python window.py --participant P01 --session 1
    python window.py --all
    python window.py --file path/to/specific.csv
    python window.py --participant P01 --window-size 2.0 --overlap 0.5
"""

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from config import DATASETS_RAW, DATASETS_WINDOWS, SAMPLING_RATE_HZ, WINDOW_OVERLAP, WINDOW_SIZE_SECONDS


def extract_windows(csv_path: Path, window_size_sec: float, overlap: float, output_dir: Path):
    """Extract overlapping windows from a single CSV. Returns count."""
    df = pd.read_csv(csv_path)
    session_name = csv_path.stem

    samples_per_window = int(window_size_sec * SAMPLING_RATE_HZ)
    step = int(samples_per_window * (1 - overlap))

    session_dir = output_dir / session_name
    session_dir.mkdir(parents=True, exist_ok=True)

    window_count = 0
    i = 0
    while i + samples_per_window <= len(df):
        window = df.iloc[i:i + samples_per_window]

        # Only save windows with a single label (skip mixed-label windows)
        labels = window["activity_label"].unique()
        if len(labels) == 1:
            label = labels[0]
            label_dir = session_dir / label
            label_dir.mkdir(parents=True, exist_ok=True)

            window_filename = f"window_{window_count:05d}.csv"
            window.to_csv(label_dir / window_filename, index=False)
            window_count += 1

        i += step

    return window_count


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
    parser = argparse.ArgumentParser(description="Extract overlapping windows from raw CSVs")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--participant", "-p", help="Participant ID (e.g. P01)")
    group.add_argument("--all", action="store_true", help="Process all participants")
    group.add_argument("--file", "-f", nargs="+", help="Path to specific CSV file(s)")
    parser.add_argument("--session", "-s", type=int, default=None, help="Session number (e.g. 1)")
    parser.add_argument("--window-size", type=float, default=WINDOW_SIZE_SECONDS, help="Window size in seconds")
    parser.add_argument("--overlap", type=float, default=WINDOW_OVERLAP, help="Overlap fraction (0-1)")
    parser.add_argument("--output-dir", default=None, help="Output directory (default: datasets/windows/)")
    args = parser.parse_args()

    output_dir = Path(args.output_dir) if args.output_dir else DATASETS_WINDOWS
    output_dir.mkdir(parents=True, exist_ok=True)

    if args.file:
        csv_files = [Path(f) for f in args.file]
    else:
        csv_files = find_csvs(
            participant=args.participant,
            session=args.session,
            all_participants=args.all,
        )

    if not csv_files:
        print("No CSV files found.")
        sys.exit(1)

    total_windows = 0
    for csv_path in csv_files:
        if not csv_path.exists():
            print(f"Warning: {csv_path} not found, skipping")
            continue

        count = extract_windows(csv_path, args.window_size, args.overlap, output_dir)
        total_windows += count
        print(f"{csv_path.name}: {count} windows extracted")

    print(f"\nTotal: {total_windows} windows saved to {output_dir}/")


if __name__ == "__main__":
    main()
