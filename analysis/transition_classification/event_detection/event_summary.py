"""
Self-describing summaries for extracted transition events.

This module is intentionally independent from ML. It only looks at the raw
samples inside a completed TransitionWindow.
"""

from __future__ import annotations

from typing import Dict, List

import numpy as np
import pandas as pd

from analysis.transition_classification.event_detection.context_window import TransitionWindow


AXES = ("acc_x", "acc_y", "acc_z")


def transition_window_to_rows(window: TransitionWindow) -> List[dict]:
    """Convert a TransitionWindow to CSV-friendly rows with region labels."""
    rows = []
    samples = window.samples
    if not samples:
        return rows

    for index, sample in enumerate(samples):
        rows.append(
            {
                "event_id": window.event_id,
                "event_sample_index": index,
                "timestamp_ms": int(sample.timestamp_ms),
                "time_from_event_start_ms": int(sample.timestamp_ms - samples[0].timestamp_ms),
                "acc_x": float(sample.acc_x),
                "acc_y": float(sample.acc_y),
                "acc_z": float(sample.acc_z),
                "region": _region_for_index(window, index),
                "is_movement_start": bool(index == window.movement_start_index),
                "is_movement_end": bool(index == window.movement_end_index),
            }
        )
    return rows


def transition_window_to_dataframe(window: TransitionWindow) -> pd.DataFrame:
    """Build a DataFrame with derived magnitude and derivative columns."""
    df = pd.DataFrame(transition_window_to_rows(window))
    if df.empty:
        return df

    df["gravity_magnitude"] = np.sqrt(
        (df["acc_x"] ** 2) + (df["acc_y"] ** 2) + (df["acc_z"] ** 2)
    )
    df["derivative_x"] = df["acc_x"].diff().fillna(0.0)
    df["derivative_y"] = df["acc_y"].diff().fillna(0.0)
    df["derivative_z"] = df["acc_z"].diff().fillna(0.0)
    df["derivative_magnitude"] = np.sqrt(
        (df["derivative_x"] ** 2) + (df["derivative_y"] ** 2) + (df["derivative_z"] ** 2)
    )
    return df


def build_event_summary(window: TransitionWindow, sampling_rate_hz: int) -> dict:
    """Build a human-readable engineering summary for one event."""
    features = compute_statistical_features(window)
    movement_duration_ms = int(window.movement_end_timestamp_ms - window.movement_start_timestamp_ms)

    pre_duration_ms = _region_duration_ms(window.before_context)
    post_duration_ms = _region_duration_ms(window.after_context)
    average_sample_period_ms = _average_sample_period(window)

    return {
        "general": {
            "event_id": window.event_id,
            "timestamp": features["timestamps"]["start_timestamp_ms"],
            "start_timestamp_ms": features["timestamps"]["start_timestamp_ms"],
            "end_timestamp_ms": features["timestamps"]["end_timestamp_ms"],
            "duration_ms": window.duration_ms,
            "total_samples": window.total_samples,
            "sampling_rate_hz": sampling_rate_hz,
            "average_sample_period_ms": average_sample_period_ms,
        },
        "context": {
            "pre_context_samples": window.pre_context_samples,
            "transition_samples": len(window.movement_samples),
            "post_context_samples": window.post_context_samples,
        },
        "timing": {
            "duration_ms": window.duration_ms,
            "sample_count": window.total_samples,
            "sampling_rate_hz": sampling_rate_hz,
            "average_sample_period_ms": average_sample_period_ms,
            "transition_duration_ms": movement_duration_ms,
            "pre_context_duration_ms": pre_duration_ms,
            "post_context_duration_ms": post_duration_ms,
            "debounce_merges": window.debounce_merges,
        },
        "movement": {
            "movement_start_index": window.movement_start_index,
            "movement_end_index": window.movement_end_index,
            "movement_start_sample_index": window.movement_start_sample_index,
            "movement_end_sample_index": window.movement_end_sample_index,
            "movement_start_timestamp_ms": window.movement_start_timestamp_ms,
            "movement_end_timestamp_ms": window.movement_end_timestamp_ms,
            "movement_duration_ms": movement_duration_ms,
            "debounce_merges": window.debounce_merges,
        },
        "pre_context": features["regions"]["pre_context"],
        "transition": features["regions"]["transition"],
        "post_context": features["regions"]["post_context"],
        "delta_features": features["delta_features"],
        "statistical_features": features["statistical_features"],
        "combined_std": features["combined_std"],
        "relative_std_metrics": features["relative_std_metrics"],
        "legacy_orientation_features": features["legacy_orientation_features"],
        "debug_interpretation": {
            "detector_view": "pre_context -> transition -> post_context",
            "summary_purpose": "Investigate simple physical features before classifier integration.",
        },
    }


def compute_statistical_features(window: TransitionWindow) -> dict:
    """Compute simple physical features for validation and investigation."""
    df = transition_window_to_dataframe(window)
    transition_df = _region(df, "transition")
    pre_df = _region(df, "pre_context")
    post_df = _region(df, "post_context")
    first_ts = int(df["timestamp_ms"].iloc[0]) if not df.empty else None
    last_ts = int(df["timestamp_ms"].iloc[-1]) if not df.empty else None

    pre_stats = _simple_region_statistics(pre_df)
    transition_stats = _simple_region_statistics(transition_df)
    post_stats = _simple_region_statistics(post_df)
    combined_std = _combined_std_by_region(pre_stats, transition_stats, post_stats)

    return {
        "timestamps": {
            "start_timestamp_ms": first_ts,
            "end_timestamp_ms": last_ts,
        },
        "regions": {
            "pre_context": pre_stats,
            "transition": transition_stats,
            "post_context": post_stats,
        },
        "delta_features": _delta_features(pre_stats, post_stats),
        "statistical_features": {
            "event_duration_ms": window.duration_ms,
            "movement_duration_ms": int(window.movement_end_timestamp_ms - window.movement_start_timestamp_ms),
            "movement_energy": _safe_sum(transition_df["derivative_magnitude"] ** 2),
            "transition_std_larger_than_context": _transition_std_larger_than_context(
                pre_stats,
                transition_stats,
                post_stats,
            ),
        },
        "combined_std": combined_std,
        "relative_std_metrics": _relative_std_metrics(combined_std),
        "legacy_orientation_features": _legacy_orientation_features(pre_df, post_df),
    }


def _region_for_index(window: TransitionWindow, index: int) -> str:
    if index < window.movement_start_index:
        return "pre_context"
    if index <= window.movement_end_index:
        return "transition"
    return "post_context"


def _region(df: pd.DataFrame, name: str) -> pd.DataFrame:
    if df.empty:
        return df
    return df[df["region"] == name]


def _simple_region_statistics(df: pd.DataFrame) -> dict:
    return {
        "samples": int(len(df)),
        "duration_ms": _duration_ms(df),
        "mean": {axis: _safe_mean(df[axis]) for axis in AXES},
        "standard_deviation": {axis: _safe_std(df[axis]) for axis in AXES},
        "variance": {axis: _safe_var(df[axis]) for axis in AXES},
        "range": {axis: _safe_range(df[axis]) for axis in AXES},
        "minimum": {axis: _safe_min(df[axis]) for axis in AXES},
        "maximum": {axis: _safe_max(df[axis]) for axis in AXES},
    }


def _delta_features(pre_stats: dict, post_stats: dict) -> dict:
    return {
        "delta_mean_x": _safe_delta(pre_stats["mean"]["acc_x"], post_stats["mean"]["acc_x"]),
        "delta_mean_y": _safe_delta(pre_stats["mean"]["acc_y"], post_stats["mean"]["acc_y"]),
        "delta_mean_z": _safe_delta(pre_stats["mean"]["acc_z"], post_stats["mean"]["acc_z"]),
    }


def _combined_std_by_region(pre_stats: dict, transition_stats: dict, post_stats: dict) -> dict:
    return {
        "pre": _combined_std(pre_stats["standard_deviation"]),
        "transition": _combined_std(transition_stats["standard_deviation"]),
        "post": _combined_std(post_stats["standard_deviation"]),
    }


def _combined_std(axis_std: dict) -> float | None:
    values = [axis_std[axis] for axis in AXES]
    if any(value is None for value in values):
        return None
    return float(np.sqrt(sum(float(value) ** 2 for value in values)))


def _relative_std_metrics(combined_std: dict) -> dict:
    pre = combined_std["pre"]
    transition = combined_std["transition"]
    post = combined_std["post"]
    stable_avg = None
    if pre is not None and post is not None:
        stable_avg = (pre + post) / 2.0
    return {
        "transition_vs_pre": _safe_ratio(transition, pre),
        "transition_vs_post": _safe_ratio(transition, post),
        "transition_vs_average_stable": _safe_ratio(transition, stable_avg),
        "stable_average_std": stable_avg,
    }


def _transition_std_larger_than_context(pre_stats: dict, transition_stats: dict, post_stats: dict) -> dict:
    result = {}
    for axis in AXES:
        transition_std = transition_stats["standard_deviation"][axis]
        pre_std = pre_stats["standard_deviation"][axis]
        post_std = post_stats["standard_deviation"][axis]
        context_max = _safe_max_value([pre_std, post_std])
        ratio = None
        if transition_std is not None and context_max not in (None, 0.0):
            ratio = float(transition_std / context_max)
        result[axis] = {
            "transition_std": transition_std,
            "pre_std": pre_std,
            "post_std": post_std,
            "context_max_std": context_max,
            "ratio_to_context": ratio,
        }
    return result


def _legacy_orientation_features(pre_df: pd.DataFrame, post_df: pd.DataFrame) -> dict:
    # Intentionally disabled — overly sensitive during experimentation.
    # Angle-derived orientation features are still recorded for later analysis,
    # but they are not used by the current validation decision.
    before = _mean_vector_df(pre_df)
    after = _mean_vector_df(post_df)
    return {
        "disabled_reason": "Intentionally disabled — overly sensitive during experimentation.",
        "mean_gravity_vector_before_transition": before,
        "mean_gravity_vector_after_transition": after,
        "gravity_vector_delta_after_minus_before": _vector_delta(pre_df, post_df),
    }


def _mean_vector_df(df: pd.DataFrame) -> Dict[str, float | None]:
    return {axis: _safe_mean(df[axis]) for axis in AXES}


def _vector_delta(pre_df: pd.DataFrame, post_df: pd.DataFrame) -> Dict[str, float | None]:
    before = _mean_vector_df(pre_df)
    after = _mean_vector_df(post_df)
    return {axis: _safe_delta(before[axis], after[axis]) for axis in AXES}


def _duration_ms(df: pd.DataFrame) -> int:
    if len(df) < 2:
        return 0
    return int(df["timestamp_ms"].iloc[-1] - df["timestamp_ms"].iloc[0])


def _safe_mean(series: pd.Series) -> float | None:
    if series.empty:
        return None
    return float(series.mean())


def _safe_min(series: pd.Series) -> float | None:
    if series.empty:
        return None
    return float(series.min())


def _safe_max(series: pd.Series) -> float | None:
    if series.empty:
        return None
    return float(series.max())


def _safe_std(series: pd.Series) -> float | None:
    if series.empty:
        return None
    return float(series.std(ddof=0))


def _safe_var(series: pd.Series) -> float | None:
    if series.empty:
        return None
    return float(series.var(ddof=0))


def _safe_sum(series: pd.Series) -> float | None:
    if series.empty:
        return None
    return float(series.sum())


def _safe_range(series: pd.Series) -> float | None:
    minimum = _safe_min(series)
    maximum = _safe_max(series)
    return _safe_delta(minimum, maximum)


def _safe_delta(before: float | None, after: float | None) -> float | None:
    if before is None or after is None:
        return None
    return float(after - before)


def _safe_ratio(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator in (None, 0.0):
        return None
    return float(numerator / denominator)


def _safe_max_value(values: list[float | None]) -> float | None:
    clean = [v for v in values if v is not None]
    if not clean:
        return None
    return float(max(clean))


def _region_duration_ms(samples) -> int:
    if not samples or len(samples) < 2:
        return 0
    return int(samples[-1].timestamp_ms - samples[0].timestamp_ms)


def _average_sample_period(window: TransitionWindow) -> float | None:
    all_samples = window.samples
    if len(all_samples) < 2:
        return None
    total_time = all_samples[-1].timestamp_ms - all_samples[0].timestamp_ms
    return round(float(total_time) / (len(all_samples) - 1), 2)
