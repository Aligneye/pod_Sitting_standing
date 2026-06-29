"""
transition_alignment_analysis.py

Scientific transition analysis focused on alignment and timing effects.

Question:
    Is Stand Up variability caused mainly by timing differences or by genuinely
    different motion patterns?

This module keeps the existing plots and report outputs, but refactors the
backend so expensive computations are done once and DTW is computed only
against a reference transition rather than pairwise NxN.
"""

from __future__ import annotations

import argparse
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from scipy.interpolate import interp1d
from scipy.spatial.distance import euclidean

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "python"))
from config import DATASETS_RAW, PROJECT_ROOT


OUTPUT_DIR = PROJECT_ROOT / "analysis" / "transition_alignment"
NORMALIZED_SAMPLES = 200
ALIGNMENT_SAMPLES = 200
LANDMARKS = ["max_z", "min_y", "max_acc_magnitude", "max_first_derivative"]


@dataclass
class PeakEvent:
    name: str
    value: float
    timestamp_ms: int
    time_s: float
    sample_index: int


@dataclass
class SimilarityBundle:
    euclidean_matrix: np.ndarray
    euclidean_mean: float
    euclidean_median: float
    dtw_to_reference: np.ndarray
    dtw_mean: float
    dtw_std: float
    dtw_min: float
    dtw_max: float
    dtw_ranking: List[Tuple[int, float]]
    reference_index: int


def now() -> float:
    return time.perf_counter()


def log_stage(label: str, start: float) -> None:
    print(f"  {label}: {now() - start:.2f}s")


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


def extract_transitions(df: pd.DataFrame, label: str) -> List[pd.DataFrame]:
    transitions: List[pd.DataFrame] = []
    in_segment = False
    start_idx = 0
    for i, row_label in enumerate(df["activity_label"]):
        if row_label == label and not in_segment:
            in_segment = True
            start_idx = i
        elif row_label != label and in_segment:
            transitions.append(df.iloc[start_idx:i].copy().reset_index(drop=True))
            in_segment = False
    if in_segment:
        transitions.append(df.iloc[start_idx:].copy().reset_index(drop=True))
    return transitions


def add_time_columns(seg: pd.DataFrame) -> pd.DataFrame:
    seg = seg.copy()
    seg["time_s"] = (seg["timestamp_ms"] - seg["timestamp_ms"].iloc[0]) / 1000.0
    seg["magnitude"] = np.sqrt(seg["acc_x"] ** 2 + seg["acc_y"] ** 2 + seg["acc_z"] ** 2)
    return seg


def duration_seconds(seg: pd.DataFrame) -> float:
    if len(seg) < 2:
        return 0.0
    return (seg["timestamp_ms"].iloc[-1] - seg["timestamp_ms"].iloc[0]) / 1000.0


def finite_difference(series: np.ndarray, time_s: np.ndarray) -> np.ndarray:
    if len(series) < 2:
        return np.zeros_like(series, dtype=float)
    return np.gradient(series, time_s)


def detect_peaks(seg: pd.DataFrame) -> Dict[str, PeakEvent]:
    time_s = seg["time_s"].to_numpy()
    dmag = np.abs(finite_difference(seg["magnitude"].to_numpy(), time_s))
    specs = {
        "max_z": ("max_z", seg["acc_z"].idxmax(), seg["acc_z"].max()),
        "min_y": ("min_y", seg["acc_y"].idxmin(), seg["acc_y"].min()),
        "max_acc_magnitude": ("max_acc_magnitude", seg["magnitude"].idxmax(), seg["magnitude"].max()),
        "max_first_derivative": ("max_first_derivative", int(np.argmax(dmag)), float(dmag.max())),
    }

    peaks: Dict[str, PeakEvent] = {}
    for key, (name, idx, value) in specs.items():
        row = seg.iloc[idx]
        peaks[key] = PeakEvent(
            name=name,
            value=float(value),
            timestamp_ms=int(row["timestamp_ms"]),
            time_s=float(row["time_s"]),
            sample_index=int(idx),
        )
    return peaks


def normalize_transition(seg: pd.DataFrame, n_samples: int = NORMALIZED_SAMPLES) -> Dict[str, np.ndarray]:
    if len(seg) < 2:
        return {}
    t_orig = np.linspace(0.0, 1.0, len(seg))
    t_new = np.linspace(0.0, 1.0, n_samples)
    out = {"t": t_new}
    for col in ["acc_x", "acc_y", "acc_z", "magnitude"]:
        out[col] = interp1d(t_orig, seg[col].to_numpy(), kind="linear")(t_new)
    return out


def align_by_landmark(seg: pd.DataFrame, landmark_time_s: float, n_samples: int = ALIGNMENT_SAMPLES) -> Dict[str, np.ndarray]:
    rel_t = seg["time_s"].to_numpy() - landmark_time_s
    if len(seg) < 2:
        return {}
    grid = np.linspace(rel_t.min(), rel_t.max(), n_samples)
    out = {"t": grid}
    for col in ["acc_x", "acc_y", "acc_z", "magnitude"]:
        out[col] = interp1d(rel_t, seg[col].to_numpy(), kind="linear", bounds_error=False, fill_value="extrapolate")(grid)
    return out


def vectorize(item: Dict[str, np.ndarray]) -> np.ndarray:
    return np.concatenate([item["acc_x"], item["acc_y"], item["acc_z"]])


def compute_euclidean_matrix(vectors: Sequence[np.ndarray]) -> np.ndarray:
    n = len(vectors)
    matrix = np.zeros((n, n), dtype=float)
    for i in range(n):
        for j in range(i + 1, n):
            d = euclidean(vectors[i], vectors[j]) / max(len(vectors[i]), 1)
            matrix[i, j] = matrix[j, i] = d
    return matrix


def dtw_distance(a: np.ndarray, b: np.ndarray) -> float:
    n, m = len(a), len(b)
    dp = np.full((n + 1, m + 1), np.inf)
    dp[0, 0] = 0.0
    for i in range(1, n + 1):
        ai = a[i - 1]
        for j in range(1, m + 1):
            cost = abs(ai - b[j - 1])
            dp[i, j] = cost + min(dp[i - 1, j], dp[i, j - 1], dp[i - 1, j - 1])
    return float(dp[n, m])


def choose_reference(vectors: Sequence[np.ndarray]) -> int:
    if len(vectors) == 1:
        return 0
    matrix = compute_euclidean_matrix(vectors)
    scores = matrix.mean(axis=1)
    return int(np.argmin(scores))


def summarize_pairwise_matrix(matrix: np.ndarray) -> Dict[str, float]:
    if matrix.size == 0:
        return {"mean": float("nan"), "median": float("nan")}
    values = matrix[np.triu_indices_from(matrix, k=1)]
    if len(values) == 0:
        return {"mean": float("nan"), "median": float("nan")}
    return {"mean": float(values.mean()), "median": float(np.median(values))}


def analyze_similarity(vectors: Sequence[np.ndarray]) -> SimilarityBundle:
    euclidean_matrix = compute_euclidean_matrix(vectors)
    euclidean_stats = summarize_pairwise_matrix(euclidean_matrix)
    ref_idx = choose_reference(vectors)
    ref = vectors[ref_idx]

    dtw_to_reference = np.array([dtw_distance(ref, v) / max(len(ref) + len(v), 1) for v in vectors], dtype=float)
    ranking = sorted([(i, float(d)) for i, d in enumerate(dtw_to_reference)], key=lambda x: x[1], reverse=True)

    return SimilarityBundle(
        euclidean_matrix=euclidean_matrix,
        euclidean_mean=euclidean_stats["mean"],
        euclidean_median=euclidean_stats["median"],
        dtw_to_reference=dtw_to_reference,
        dtw_mean=float(dtw_to_reference.mean()) if len(dtw_to_reference) else float("nan"),
        dtw_std=float(dtw_to_reference.std()) if len(dtw_to_reference) else float("nan"),
        dtw_min=float(dtw_to_reference.min()) if len(dtw_to_reference) else float("nan"),
        dtw_max=float(dtw_to_reference.max()) if len(dtw_to_reference) else float("nan"),
        dtw_ranking=ranking,
        reference_index=ref_idx,
    )


def analyze_euclidean_only(vectors: Sequence[np.ndarray]) -> Tuple[np.ndarray, float, float]:
    matrix = compute_euclidean_matrix(vectors)
    stats = summarize_pairwise_matrix(matrix)
    return matrix, stats["mean"], stats["median"]


def plot_histogram(values: Sequence[float], title: str, filename: str, output_dir: Path) -> None:
    fig = go.Figure()
    fig.add_trace(go.Histogram(x=list(values), nbinsx=min(15, max(5, len(values) // 2)), marker_color="#34495e"))
    fig.update_layout(title=title, xaxis_title="Seconds", yaxis_title="Count", bargap=0.08)
    fig.write_html(str(output_dir / filename))


def plot_overlay(collection: Sequence[Dict[str, np.ndarray]], title: str, filename: str, output_dir: Path) -> None:
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True, subplot_titles=("acc_x", "acc_y", "acc_z"), vertical_spacing=0.06)
    colors = {"acc_x": "rgba(231, 76, 60, 0.22)", "acc_y": "rgba(39, 174, 96, 0.22)", "acc_z": "rgba(41, 128, 185, 0.22)"}
    for row, axis in enumerate(["acc_x", "acc_y", "acc_z"], 1):
        for item in collection:
            fig.add_trace(go.Scatter(x=item["t"], y=item[axis], mode="lines", line=dict(width=0.8, color=colors[axis]), showlegend=False, hoverinfo="skip"), row=row, col=1)
    fig.update_layout(title=title, height=900, hovermode="x unified")
    fig.update_xaxes(title_text="Time (s)", row=3, col=1)
    fig.write_html(str(output_dir / filename))


def plot_similarity_heatmaps(sit_matrix: np.ndarray, stand_matrix: np.ndarray, filename: str, output_dir: Path) -> None:
    fig = make_subplots(rows=1, cols=2, subplot_titles=("SIT_DOWN", "STAND_UP"), horizontal_spacing=0.1)
    for col, matrix in enumerate([sit_matrix, stand_matrix], 1):
        fig.add_trace(
            go.Heatmap(
                z=matrix,
                colorscale="YlOrRd",
                hovertemplate="i=%{x}<br>j=%{y}<br>dist=%{z:.4f}<extra></extra>",
                showscale=(col == 2),
            ),
            row=1,
            col=col,
        )
    fig.update_layout(title="Transition Similarity (Pairwise Euclidean Distance)", height=650, width=1150)
    fig.write_html(str(output_dir / filename))


def summarize_landmarks(peaks: Sequence[Dict[str, PeakEvent]], durations: Sequence[float]) -> Dict[str, Dict[str, float]]:
    report: Dict[str, Dict[str, float]] = {}
    if not peaks:
        return report
    for key in LANDMARKS:
        times = np.array([p[key].time_s for p in peaks], dtype=float)
        report[key] = {
            "avg_time_s": float(times.mean()),
            "std_time_s": float(times.std()),
            "avg_fraction_of_transition": float(np.mean([t / d if d > 0 else np.nan for t, d in zip(times, durations)])),
        }
    return report


def infer_alignment_story(sit: Dict[str, object], stand: Dict[str, object]) -> Dict[str, str]:
    sit_gain = sit["euclidean_before"] - sit["euclidean_best_after"]
    stand_gain = stand["euclidean_before"] - stand["euclidean_best_after"]
    best_gain = max(sit_gain, stand_gain)

    return {
        "peak_alignment": "Yes, if alignment by peaks reduces both Euclidean spread and DTW-to-reference variability." if best_gain > 0 else "No clear reduction was observed.",
        "stand_up_difference": "Stand Up looks more time-shifted than structurally different if landmark alignment materially improves consistency." if stand_gain > 0 else "Stand Up still varies after alignment, which suggests a stronger biomechanical component.",
        "best_method": sit["best_alignment"] if sit["euclidean_best_after"] <= stand["euclidean_best_after"] else stand["best_alignment"],
        "root_cause": "primarily temporal" if best_gain > 0.15 * max(sit["euclidean_before"], stand["euclidean_before"], 1e-9) else "mixed or biomechanical",
    }


def build_label_results(label: str, df: pd.DataFrame) -> Dict[str, object]:
    t0 = now()
    raw = [add_time_columns(seg) for seg in extract_transitions(df, label)]
    valid = [seg for seg in raw if len(seg) >= 2]
    print(f"  [{label}] extracted {len(valid)} transitions")
    log_stage(f"[{label}] extraction", t0)

    t1 = now()
    durations = [duration_seconds(seg) for seg in valid]
    peaks = [detect_peaks(seg) for seg in valid]
    log_stage(f"[{label}] peak detection", t1)

    t2 = now()
    start_aligned = [normalize_transition(seg) for seg in valid]
    start_vectors = [vectorize(item) for item in start_aligned]
    log_stage(f"[{label}] start normalization", t2)

    t3 = now()
    landmark_aligned: Dict[str, List[Dict[str, np.ndarray]]] = {key: [] for key in LANDMARKS}
    for seg, peak in zip(valid, peaks):
        for key in LANDMARKS:
            landmark_aligned[key].append(align_by_landmark(seg, peak[key].time_s))
    log_stage(f"[{label}] landmark alignment", t3)

    t4 = now()
    euclidean_bundle = analyze_similarity(start_vectors)
    log_stage(f"[{label}] Euclidean similarity", t4)

    t5 = now()
    dtw_bundle = euclidean_bundle  # placeholder to preserve structure; overwritten below
    ref_idx = euclidean_bundle.reference_index
    ref = start_vectors[ref_idx] if start_vectors else np.array([])
    dtw_to_reference = np.array([dtw_distance(ref, vec) / max(len(ref) + len(vec), 1) for vec in start_vectors], dtype=float) if len(start_vectors) else np.array([])
    dtw_ranking = sorted([(i, float(d)) for i, d in enumerate(dtw_to_reference)], key=lambda x: x[1], reverse=True)
    dtw_bundle = {
        "mean": float(dtw_to_reference.mean()) if len(dtw_to_reference) else float("nan"),
        "std": float(dtw_to_reference.std()) if len(dtw_to_reference) else float("nan"),
        "min": float(dtw_to_reference.min()) if len(dtw_to_reference) else float("nan"),
        "max": float(dtw_to_reference.max()) if len(dtw_to_reference) else float("nan"),
        "reference_index": ref_idx,
        "values": dtw_to_reference,
        "ranking": dtw_ranking,
    }
    log_stage(f"[{label}] DTW-to-reference", t5)

    t6 = now()
    landmark_similarity: Dict[str, Dict[str, object]] = {}
    for key, items in landmark_aligned.items():
        vecs = [vectorize(item) for item in items if item]
        if len(vecs) < 2:
            continue
        matrix, mean, median = analyze_euclidean_only(vecs)
        landmark_similarity[key] = {
            "euclidean_matrix": matrix,
            "euclidean_mean": mean,
            "euclidean_median": median,
        }
    log_stage(f"[{label}] landmark Euclidean reuse", t6)

    best_alignment = "start"
    best_after = euclidean_bundle.euclidean_mean
    for key, stats in landmark_similarity.items():
        if stats["euclidean_mean"] < best_after:
            best_alignment = key
            best_after = stats["euclidean_mean"]

    landmark_timing = summarize_landmarks(peaks, durations)

    return {
        "durations": durations,
        "peaks": peaks,
        "start_aligned": start_aligned,
        "landmark_aligned": landmark_aligned,
        "euclidean_matrix": euclidean_bundle.euclidean_matrix,
        "euclidean_before": euclidean_bundle.euclidean_mean,
        "euclidean_median_before": euclidean_bundle.euclidean_median,
        "dtw_reference_index": ref_idx,
        "dtw_reference_distance": dtw_bundle["values"],
        "dtw_mean": dtw_bundle["mean"],
        "dtw_std": dtw_bundle["std"],
        "dtw_min": dtw_bundle["min"],
        "dtw_max": dtw_bundle["max"],
        "dtw_ranking": dtw_bundle["ranking"],
        "landmark_similarity": landmark_similarity,
        "best_alignment": best_alignment,
        "euclidean_best_after": best_after,
        "landmark_timing": landmark_timing,
    }


def write_report(csv_name: str, results: Dict[str, Dict[str, object]], runtime: Dict[str, float], output_dir: Path) -> Path:
    sit = results["SIT_DOWN"]
    stand = results["STAND_UP"]
    answers = infer_alignment_story(
        {
            "euclidean_before": sit["euclidean_before"],
            "euclidean_best_after": sit["euclidean_best_after"],
            "best_alignment": sit["best_alignment"],
        },
        {
            "euclidean_before": stand["euclidean_before"],
            "euclidean_best_after": stand["euclidean_best_after"],
            "best_alignment": stand["best_alignment"],
        },
    )

    lines = [
        "# Transition Alignment Analysis",
        "",
        f"Source CSV: {csv_name}",
        f"Generated: {pd.Timestamp.now():%Y-%m-%d %H:%M:%S}",
        "",
        "## Runtime Summary",
        "",
        f"- CSV load: {runtime['load']:.2f}s",
        f"- Transition extraction and landmark detection: {runtime['analysis']:.2f}s",
        f"- Plot generation: {runtime['plots']:.2f}s",
        f"- Report generation: {runtime['report']:.2f}s",
        f"- Total runtime: {runtime['total']:.2f}s",
        "",
        "## Interpretation",
        "",
        "This analysis asks whether Stand Up variability is mostly temporal misalignment or whether the movement pattern itself is materially different.",
        "",
    ]

    for label in ["SIT_DOWN", "STAND_UP"]:
        r = results[label]
        lines += [
            f"## {label}",
            "",
            f"- Count: {len(r['durations'])}",
            f"- Average duration: {np.mean(r['durations']):.3f} s",
            f"- Duration std dev: {np.std(r['durations']):.3f} s",
            f"- Euclidean mean before alignment: {r['euclidean_before']:.4f}",
            f"- Euclidean median before alignment: {r['euclidean_median_before']:.4f}",
            f"- Best Euclidean alignment: {r['best_alignment']}",
            f"- Euclidean mean after best alignment: {r['euclidean_best_after']:.4f}",
            f"- DTW-to-reference mean: {r['dtw_mean']:.4f}",
            f"- DTW-to-reference std: {r['dtw_std']:.4f}",
            f"- DTW-to-reference min: {r['dtw_min']:.4f}",
            f"- DTW-to-reference max: {r['dtw_max']:.4f}",
            f"- Reference transition for DTW: cycle {r['dtw_reference_index'] + 1}",
            "",
            "### Landmark Timing",
            "",
        ]
        for lk, stats in r["landmark_timing"].items():
            lines.append(
                f"- {lk}: avg {stats['avg_time_s']:.3f} s, std {stats['std_time_s']:.3f} s, "
                f"avg fraction {stats['avg_fraction_of_transition']:.3f}"
            )
        lines += ["", "### Atypical Transitions by DTW", ""]
        for idx, dist in r["dtw_ranking"][:5]:
            lines.append(f"- Cycle {idx + 1}: {dist:.4f}")
        lines.append("")

    lines += [
        "## Answers",
        "",
        f"- Does peak alignment reduce variability? {answers['peak_alignment']}",
        f"- Are Stand Up transitions truly different or merely shifted in time? {answers['stand_up_difference']}",
        f"- Which alignment method produces the most consistent overlays? {answers['best_method']}",
        f"- Is the observed variability primarily temporal or biomechanical? {answers['root_cause']}",
        "",
        "## Generated Files",
        "",
    ]

    for rel in sorted(output_dir.glob(f"{Path(csv_name).stem}*")):
        lines.append(f"- {rel.name}")

    path = output_dir / "transition_alignment_report.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def analyze_csv(csv_path: Path) -> Tuple[Dict[str, Dict[str, object]], Dict[str, float]]:
    runtime = {"load": 0.0, "analysis": 0.0, "plots": 0.0, "report": 0.0, "total": 0.0}
    total_t0 = now()

    load_t0 = now()
    df = pd.read_csv(csv_path)
    runtime["load"] = now() - load_t0
    print(f"Loaded CSV: {len(df)} rows in {runtime['load']:.2f}s")

    analysis_t0 = now()
    results = {
        "SIT_DOWN": build_label_results("SIT_DOWN", df),
        "STAND_UP": build_label_results("STAND_UP", df),
    }
    runtime["analysis"] = now() - analysis_t0
    print(f"Analysis complete in {runtime['analysis']:.2f}s")

    plots_t0 = now()
    for label in ["SIT_DOWN", "STAND_UP"]:
        r = results[label]
        print(f"  [{label}] plotting duration histogram")
        plot_histogram(r["durations"], f"{label} Duration Distribution", f"{csv_path.stem}_{label.lower()}_duration_hist.html", OUTPUT_DIR)
        print(f"  [{label}] plotting start-aligned overlay")
        plot_overlay(r["start_aligned"], f"{label} Overlay Aligned by Transition Start", f"{csv_path.stem}_{label.lower()}_start_aligned.html", OUTPUT_DIR)
        for key, items in r["landmark_aligned"].items():
            valid = [item for item in items if item]
            if valid:
                print(f"  [{label}] plotting {key}-aligned overlay")
                plot_overlay(valid, f"{label} Overlay Aligned by {key}", f"{csv_path.stem}_{label.lower()}_{key}_aligned.html", OUTPUT_DIR)
    print("  plotting Euclidean similarity heatmap")
    plot_similarity_heatmaps(
        results["SIT_DOWN"]["euclidean_matrix"],
        results["STAND_UP"]["euclidean_matrix"],
        f"{csv_path.stem}_transition_similarity_heatmap.html",
        OUTPUT_DIR,
    )
    runtime["plots"] = now() - plots_t0
    print(f"Plot generation complete in {runtime['plots']:.2f}s")

    report_t0 = now()
    report_path = write_report(csv_path.name, results, runtime, OUTPUT_DIR)
    runtime["report"] = now() - report_t0
    runtime["total"] = now() - total_t0
    print(f"Report generation complete in {runtime['report']:.2f}s")
    print(f"Total runtime: {runtime['total']:.2f}s")
    print(f"Saved markdown report: {report_path.name}")

    return results, runtime


def main() -> None:
    parser = argparse.ArgumentParser(description="Transition alignment research analysis")
    parser.add_argument("--file", "-f", default=None, help="Path to a specific CSV")
    parser.add_argument("--participant", "-p", default=None, help="Participant ID")
    parser.add_argument("--session", "-s", type=int, default=None, help="Session number")
    args = parser.parse_args()

    csvs = find_csvs(args.participant, args.session, args.file)
    if not csvs:
        print("No CSV files found.")
        sys.exit(1)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    summary_rows = []

    for csv_path in csvs:
        print(f"Analyzing {csv_path.name}")
        results, runtime = analyze_csv(csv_path)

        for label in ["SIT_DOWN", "STAND_UP"]:
            r = results[label]
            summary_rows.append(
                {
                    "file": csv_path.name,
                    "label": label,
                    "count": len(r["durations"]),
                    "avg_duration_s": float(np.mean(r["durations"])),
                    "std_duration_s": float(np.std(r["durations"])),
                    "euclidean_before": r["euclidean_before"],
                    "euclidean_median_before": r["euclidean_median_before"],
                    "best_alignment": r["best_alignment"],
                    "euclidean_best_after": r["euclidean_best_after"],
                    "dtw_mean": r["dtw_mean"],
                    "dtw_std": r["dtw_std"],
                    "dtw_min": r["dtw_min"],
                    "dtw_max": r["dtw_max"],
                    "dtw_reference_index": r["dtw_reference_index"] + 1,
                }
            )

    summary_df = pd.DataFrame(summary_rows)
    summary_df.to_csv(OUTPUT_DIR / "transition_alignment_summary.csv", index=False)
    print(f"Saved summary CSV: transition_alignment_summary.csv")


if __name__ == "__main__":
    main()
