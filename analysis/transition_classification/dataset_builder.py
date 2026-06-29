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
    TARGET_LABELS,
    add_time_columns,
    compute_transition_id,
    ensure_output_dirs,
    extract_transitions,
    find_csvs,
    normalize_transition,
)


def build_dataset(csv_files: List[Path], n_samples: int = 100) -> pd.DataFrame:
    rows: List[Dict[str, object]] = []
    feature_cols = [f"{axis}_{i:03d}" for axis in FEATURE_AXES for i in range(n_samples)]

    for csv_path in csv_files:
        df = pd.read_csv(csv_path)
        for label in TARGET_LABELS:
            transitions = [add_time_columns(seg) for seg in extract_transitions(df, label)]
            for idx, seg in enumerate(transitions):
                norm = normalize_transition(seg, n_samples=n_samples)
                if not norm:
                    continue
                row: Dict[str, object] = {
                    "transition_id": compute_transition_id(csv_path.name, label, idx),
                    "source_file": csv_path.name,
                    "label": label,
                    "duration_s": (seg["timestamp_ms"].iloc[-1] - seg["timestamp_ms"].iloc[0]) / 1000.0,
                    "num_samples": len(seg),
                }
                for axis in FEATURE_AXES:
                    for i, value in enumerate(norm[axis]):
                        row[f"{axis}_{i:03d}"] = float(value)
                rows.append(row)

    dataset = pd.DataFrame(rows)
    if not dataset.empty:
        dataset = dataset.sort_values(["source_file", "label", "transition_id"]).reset_index(drop=True)
    return dataset


def main() -> None:
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
    }
    (DATASET_DIR / f"transition_dataset_{args.samples}.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(f"Saved dataset: {out_csv}")


if __name__ == "__main__":
    main()
