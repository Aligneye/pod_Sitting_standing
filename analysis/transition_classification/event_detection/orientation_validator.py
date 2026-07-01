"""
Staged validation for candidate transition events.

Validation pipeline (movement_orientation_v2):
    Stage 1 - Movement: Did rolling combined STD exceed threshold long enough?
    Stage 2 - Orientation: Did PRE-to-POST mean shift on Y or Z confirm change?

Stability metrics are computed and recorded as diagnostics but do NOT reject
events. Real users do not become perfectly stationary immediately after a
transition — small body adjustments and natural settling mean POST context is
often noisy. Stability may be re-evaluated as a validation stage in the future
once we have enough accepted events to study settling patterns.

This module does not classify SIT_DOWN vs STAND_UP and does not use ML.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import acos, degrees
from typing import Dict, Sequence

import numpy as np
import pandas as pd

from analysis.transition_classification.event_detection.config import DEFAULT_CONFIG, EventDetectionConfig
from analysis.transition_classification.event_detection.context_window import TransitionWindow
from analysis.transition_classification.event_detection.event_summary import (
    compute_statistical_features,
    transition_window_to_dataframe,
)
from analysis.transition_classification.live.serial_stream import Sample


VALIDATION_PIPELINE_VERSION = "movement_orientation_v2"


class ValidationStage(str, Enum):
    """Names for validation stages."""

    MOVEMENT = "movement"
    ORIENTATION = "orientation"


class OrientationValidationStatus(str, Enum):
    """Possible validation outcomes for one candidate event."""

    VALID_TRANSITION = "VALID_TRANSITION"
    REJECT_EVENT = "REJECT_EVENT"


@dataclass(frozen=True)
class StageResult:
    """Result of one validation stage."""

    stage: ValidationStage
    passed: bool
    reason: str
    metrics: Dict[str, float | None]


@dataclass(frozen=True)
class StabilityDiagnostics:
    """Diagnostic-only stability metrics. These never reject events."""

    pre_std: float | None
    post_std: float | None
    transition_std: float | None
    stable_average_std: float | None
    transition_to_stable_ratio: float | None


@dataclass(frozen=True)
class OrientationMetrics:
    """Disabled angle-derived metrics preserved for future experiments."""

    mean_before: Dict[str, float | None]
    mean_after: Dict[str, float | None]
    delta_x: float | None
    delta_y: float | None
    delta_z: float | None
    gravity_magnitude_before: float | None
    gravity_magnitude_after: float | None
    gravity_magnitude_change: float | None
    angle_change_deg: float | None
    stability_before: float | None
    stability_after: float | None


@dataclass(frozen=True)
class OrientationValidationResult:
    """Decision and evidence for one candidate event."""

    status: OrientationValidationStatus
    is_valid: bool
    reason: str
    validation_pipeline_version: str
    stage_results: Dict[str, StageResult]
    validation_stage_passed: str
    validation_stage_failed: str | None
    rejection_stage: str | None
    rolling_std_metrics: Dict[str, float | None]
    stability_diagnostics: StabilityDiagnostics
    statistical_features: dict
    legacy_orientation_metrics: OrientationMetrics
    thresholds: Dict[str, float | dict]


class OrientationValidator:
    """Two-stage validator: movement -> orientation -> VALID."""

    def __init__(self, config: EventDetectionConfig = DEFAULT_CONFIG) -> None:
        self.config = config

    def validate(self, window: TransitionWindow) -> OrientationValidationResult:
        """Run staged validation on a candidate event."""
        statistical_features = compute_statistical_features(window)
        legacy_metrics = _compute_orientation_metrics(window)
        df = transition_window_to_dataframe(window)
        rolling_std_metrics = self._compute_rolling_std_metrics(df, window)
        stability = self._compute_stability_diagnostics(statistical_features)

        stage_results: Dict[str, StageResult] = {}
        last_passed = ""
        failed_stage = None

        stage1 = self._validate_movement(rolling_std_metrics)
        stage_results[ValidationStage.MOVEMENT.value] = stage1
        if not stage1.passed:
            failed_stage = ValidationStage.MOVEMENT.value
        else:
            last_passed = ValidationStage.MOVEMENT.value

            stage2 = self._validate_orientation(statistical_features)
            stage_results[ValidationStage.ORIENTATION.value] = stage2
            if not stage2.passed:
                failed_stage = ValidationStage.ORIENTATION.value
            else:
                last_passed = ValidationStage.ORIENTATION.value

        is_valid = failed_stage is None
        status = (
            OrientationValidationStatus.VALID_TRANSITION
            if is_valid
            else OrientationValidationStatus.REJECT_EVENT
        )
        reason = _build_reason(stage_results, is_valid, failed_stage)

        return OrientationValidationResult(
            status=status,
            is_valid=is_valid,
            reason=reason,
            validation_pipeline_version=VALIDATION_PIPELINE_VERSION,
            stage_results=stage_results,
            validation_stage_passed=last_passed,
            validation_stage_failed=failed_stage,
            rejection_stage=failed_stage,
            rolling_std_metrics=rolling_std_metrics,
            stability_diagnostics=stability,
            statistical_features=statistical_features,
            legacy_orientation_metrics=legacy_metrics,
            thresholds=self._thresholds(),
        )

    # ------------------------------------------------------------------
    # Stage 1: Movement - rolling combined STD must confirm real movement
    # ------------------------------------------------------------------

    def _validate_movement(self, rolling_metrics: Dict[str, float | None]) -> StageResult:
        """Stage 1: Rolling combined STD must exceed threshold long enough."""
        peak = rolling_metrics.get("rolling_std_peak")
        duration_above = rolling_metrics.get("rolling_std_duration_above_threshold")
        threshold = self.config.stage1_rolling_std_threshold
        min_consecutive = self.config.stage1_min_consecutive_above

        if peak is None or peak < threshold:
            return StageResult(
                stage=ValidationStage.MOVEMENT,
                passed=False,
                reason=f"rolling_std_peak={_fmt(peak)} < threshold={threshold}",
                metrics=rolling_metrics,
            )

        if duration_above is not None and duration_above < min_consecutive:
            return StageResult(
                stage=ValidationStage.MOVEMENT,
                passed=False,
                reason=(
                    f"rolling_std_duration_above={duration_above} "
                    f"< min_consecutive={min_consecutive}"
                ),
                metrics=rolling_metrics,
            )

        return StageResult(
            stage=ValidationStage.MOVEMENT,
            passed=True,
            reason=(
                f"rolling_std_peak={_fmt(peak)} >= threshold={threshold}, "
                f"duration_above={duration_above} >= min={min_consecutive}"
            ),
            metrics=rolling_metrics,
        )

    # ------------------------------------------------------------------
    # Stage 2: Orientation - PRE-to-POST mean shift on Y or Z
    # ------------------------------------------------------------------

    def _validate_orientation(self, features: dict) -> StageResult:
        """Stage 2: At least one axis (Y or Z) must show meaningful delta."""
        delta = features["delta_features"]
        delta_y = _abs_or_none(delta.get("delta_mean_y"))
        delta_z = _abs_or_none(delta.get("delta_mean_z"))
        y_threshold = self.config.stage2_delta_y_threshold
        z_threshold = self.config.stage2_delta_z_threshold

        y_passed = delta_y is not None and delta_y >= y_threshold
        z_passed = delta_z is not None and delta_z >= z_threshold
        passed = y_passed or z_passed

        if passed:
            reason = (
                f"delta_y={_fmt(delta_y)} (threshold={y_threshold}), "
                f"delta_z={_fmt(delta_z)} (threshold={z_threshold})"
            )
        else:
            reason = (
                f"delta_y={_fmt(delta_y)} < {y_threshold} AND "
                f"delta_z={_fmt(delta_z)} < {z_threshold}"
            )

        return StageResult(
            stage=ValidationStage.ORIENTATION,
            passed=passed,
            reason=reason,
            metrics={"delta_y": delta_y, "delta_z": delta_z},
        )

    # ------------------------------------------------------------------
    # Stability diagnostics (never rejects, recorded for analysis)
    # ------------------------------------------------------------------

    def _compute_stability_diagnostics(self, features: dict) -> StabilityDiagnostics:
        """Compute stability metrics as diagnostics only."""
        combined_std = features["combined_std"]
        pre_std = combined_std.get("pre")
        post_std = combined_std.get("post")
        transition_std = combined_std.get("transition")

        stable_avg = None
        ratio = None
        if pre_std is not None and post_std is not None:
            stable_avg = (pre_std + post_std) / 2.0
            if stable_avg > 0 and transition_std is not None:
                ratio = transition_std / stable_avg

        return StabilityDiagnostics(
            pre_std=pre_std,
            post_std=post_std,
            transition_std=transition_std,
            stable_average_std=stable_avg,
            transition_to_stable_ratio=ratio,
        )

    # ------------------------------------------------------------------
    # Rolling STD metrics computed over the transition region
    # ------------------------------------------------------------------

    def _compute_rolling_std_metrics(
        self, df: pd.DataFrame, window: TransitionWindow
    ) -> Dict[str, float | None]:
        """Compute rolling combined STD metrics for the full event window."""
        if df.empty:
            return {
                "rolling_std_peak": None,
                "rolling_std_mean": None,
                "rolling_std_duration_above_threshold": None,
            }

        win_size = max(2, int(self.config.rolling_std_window_samples))
        rolling_x = df["acc_x"].rolling(window=win_size, min_periods=2).std(ddof=0).fillna(0.0)
        rolling_y = df["acc_y"].rolling(window=win_size, min_periods=2).std(ddof=0).fillna(0.0)
        rolling_z = df["acc_z"].rolling(window=win_size, min_periods=2).std(ddof=0).fillna(0.0)
        rolling_combined = ((rolling_x ** 2) + (rolling_y ** 2) + (rolling_z ** 2)).pow(0.5)

        transition_mask = df["region"] == "transition"
        transition_rolling = rolling_combined[transition_mask]

        peak = float(rolling_combined.max()) if not rolling_combined.empty else None
        mean_val = float(transition_rolling.mean()) if not transition_rolling.empty else None

        threshold = self.config.stage1_rolling_std_threshold
        above = transition_rolling > threshold
        duration_above = int(_max_consecutive_true(above))

        return {
            "rolling_std_peak": peak,
            "rolling_std_mean": mean_val,
            "rolling_std_duration_above_threshold": duration_above,
        }

    # ------------------------------------------------------------------
    # Thresholds for serialization
    # ------------------------------------------------------------------

    def _thresholds(self) -> Dict[str, float | dict]:
        return {
            "validation_pipeline_version": VALIDATION_PIPELINE_VERSION,
            "stage1_rolling_std_threshold": self.config.stage1_rolling_std_threshold,
            "stage1_min_consecutive_above": self.config.stage1_min_consecutive_above,
            "stage2_delta_y_threshold": self.config.stage2_delta_y_threshold,
            "stage2_delta_z_threshold": self.config.stage2_delta_z_threshold,
            "rolling_std_window_samples": self.config.rolling_std_window_samples,
            "stability_note": "Diagnostic only — does not reject events.",
            "disabled_angle_metrics_note": "Intentionally disabled — overly sensitive during experimentation.",
        }


# ======================================================================
# Helper functions
# ======================================================================


def _build_reason(
    stage_results: Dict[str, StageResult],
    is_valid: bool,
    failed_stage: str | None,
) -> str:
    if is_valid:
        return "All stages passed: movement -> orientation"
    return f"Rejected at stage: {failed_stage} — {stage_results[failed_stage].reason}"


def _max_consecutive_true(series: pd.Series) -> int:
    """Find the longest consecutive run of True values."""
    if series.empty or not series.any():
        return 0
    groups = (series != series.shift()).cumsum()
    true_groups = groups[series]
    if true_groups.empty:
        return 0
    return int(true_groups.value_counts().max())


def _compute_orientation_metrics(window: TransitionWindow) -> OrientationMetrics:
    """Compute angle-derived metrics without using them for validation.

    Intentionally disabled — these are overly sensitive during experimentation.
    Preserved for future experiments once threshold tuning is complete.
    """
    before = _samples_to_array(window.before_context)
    after = _samples_to_array(window.after_context)
    mean_before = _mean_vector(before)
    mean_after = _mean_vector(after)
    before_vector = _dict_to_vector(mean_before)
    after_vector = _dict_to_vector(mean_after)

    return OrientationMetrics(
        mean_before=mean_before,
        mean_after=mean_after,
        delta_x=_safe_delta(mean_before["x"], mean_after["x"]),
        delta_y=_safe_delta(mean_before["y"], mean_after["y"]),
        delta_z=_safe_delta(mean_before["z"], mean_after["z"]),
        gravity_magnitude_before=_vector_magnitude(before_vector),
        gravity_magnitude_after=_vector_magnitude(after_vector),
        gravity_magnitude_change=_safe_delta(
            _vector_magnitude(before_vector),
            _vector_magnitude(after_vector),
        ),
        angle_change_deg=_angle_between(before_vector, after_vector),
        stability_before=_orientation_stability(before),
        stability_after=_orientation_stability(after),
    )


compute_orientation_metrics = _compute_orientation_metrics


def _abs_or_none(value: float | None) -> float | None:
    if value is None:
        return None
    return abs(float(value))


def _samples_to_array(samples: Sequence[Sample]) -> np.ndarray:
    if not samples:
        return np.empty((0, 3), dtype=float)
    return np.asarray([[s.acc_x, s.acc_y, s.acc_z] for s in samples], dtype=float)


def _mean_vector(values: np.ndarray) -> Dict[str, float | None]:
    if values.size == 0:
        return {"x": None, "y": None, "z": None}
    means = values.mean(axis=0)
    return {"x": float(means[0]), "y": float(means[1]), "z": float(means[2])}


def _dict_to_vector(values: Dict[str, float | None]) -> np.ndarray | None:
    if values["x"] is None or values["y"] is None or values["z"] is None:
        return None
    return np.asarray([values["x"], values["y"], values["z"]], dtype=float)


def _vector_magnitude(vector: np.ndarray | None) -> float | None:
    if vector is None:
        return None
    return float(np.linalg.norm(vector))


def _angle_between(before: np.ndarray | None, after: np.ndarray | None) -> float | None:
    if before is None or after is None:
        return None
    before_norm = np.linalg.norm(before)
    after_norm = np.linalg.norm(after)
    if before_norm == 0.0 or after_norm == 0.0:
        return None
    cosine = float(np.dot(before, after) / (before_norm * after_norm))
    cosine = max(-1.0, min(1.0, cosine))
    return float(degrees(acos(cosine)))


def _orientation_stability(values: np.ndarray) -> float | None:
    if values.size == 0:
        return None
    return float(np.linalg.norm(values.std(axis=0)))


def _safe_delta(before: float | None, after: float | None) -> float | None:
    if before is None or after is None:
        return None
    return float(after - before)


def _fmt(value: float | None) -> str:
    if value is None:
        return "N/A"
    return f"{value:.4f}"
