"""
Build a transition-level dataset for classical ML baselines.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, List, Optional

import sys

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from analysis.transition_classification.utils import (
    DATASET_DIR,
    FEATURE_AXES,
    METADATA_COLUMNS,
    TARGET_LABELS,
    add_time_columns,
    compute_transition_id,
    ensure_output_dirs,
    extract_transitions,
    find_csvs,
    parse_transition_metadata,
    normalize_transition,
)


def build_dataset(csv_files: List[Path], n_samples: int = 100) -> pd.DataFrame:
    """Convert raw recordings into one row per transition.

    Each row is like a single flashcard: it contains the label, the source
    recording, the duration, and the flattened normalized sensor trace.
    """
    rows: List[Dict[str, object]] = []

    for csv_path in csv_files:
        df = pd.read_csv(csv_path)
        source_meta = parse_transition_metadata(csv_path)
        # We process SIT_DOWN and STAND_UP separately so each transition type
        # becomes its own supervised learning example.
        for label in TARGET_LABELS:
            transitions = [add_time_columns(seg) for seg in extract_transitions(df, label)]
            for idx, seg in enumerate(transitions):
                # Normalize now, before any model training, so every sample has
                # the same shape regardless of how long the person took.
                norm = normalize_transition(seg, n_samples=n_samples)
                if not norm:
                    continue
                row: Dict[str, object] = {
                    "transition_id": compute_transition_id(csv_path.name, label, idx),
                    "participant_id": source_meta.get("participant_id", "unknown"),
                    "session_id": source_meta.get("session_id", "unknown"),
                    "source_file": csv_path.name,
                    "recording_timestamp": source_meta.get("recording_timestamp", "unknown"),
                    "cycle_number": idx + 1,
                    "transition_index": idx + 1,
                    "transition_duration_seconds": (seg["timestamp_ms"].iloc[-1] - seg["timestamp_ms"].iloc[0]) / 1000.0,
                    "label": label,
                }
                feature_values: List[float] = []
                for axis in FEATURE_AXES:
                    feature_values.extend(float(v) for v in norm[axis])
                for i, value in enumerate(feature_values):
                    row[f"feature_{i:03d}"] = value
                rows.append(row)

    dataset = pd.DataFrame(rows)
    if not dataset.empty:
        ordered_cols = METADATA_COLUMNS + [c for c in dataset.columns if c.startswith("feature_")]
        dataset = dataset[ordered_cols]
        dataset = dataset.sort_values(["source_file", "label", "transition_id"]).reset_index(drop=True)
    return dataset


def main() -> None:
    """Build and save the transition dataset from raw CSV files."""
    parser = argparse.ArgumentParser(description="Build transition classification dataset")
    parser.add_argument("--file", "-f", default=None, help="Path to a specific CSV")
    parser.add_argument("--participant", "-p", default=None, help="Participant ID")
    parser.add_argument("--session", "-s", type=int, default=None, help="Session number")
    parser.add_argument("--samples", type=int, default=100, help="Normalized samples per transition")
    args = parser.parse_args()

    ensure_output_dirs()
    csvs = find_csvs(args.participant, args.session, args.file)
    if not csvs:
        raise SystemExit("No CSV files found.")

    dataset = build_dataset(csvs, n_samples=args.samples)
    if dataset.empty:
        raise SystemExit("No transitions found.")

    out_csv = DATASET_DIR / f"transition_dataset_{args.samples}.csv"
    dataset.to_csv(out_csv, index=False)

    meta = {
        "source_files": [p.name for p in csvs],
        "rows": int(len(dataset)),
        "samples_per_transition": args.samples,
        "labels": list(TARGET_LABELS),
        "metadata_columns": METADATA_COLUMNS,
    }
    (DATASET_DIR / f"transition_dataset_{args.samples}.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(f"Saved dataset: {out_csv}")


if __name__ == "__main__":
    main()
