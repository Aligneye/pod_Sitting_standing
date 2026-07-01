"""
Configuration for event extraction and staged validation.

All thresholds for movement detection, validation stages, and context sizing
live here so the event pipeline has no hidden magic numbers.

Validation pipeline: movement_orientation_v2
    Stage 1 - Movement (rolling combined STD)
    Stage 2 - Orientation (delta Y/Z)
    Stability is diagnostic only — it never rejects events.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class EventDetectionConfig:
    """Threshold and config values for event extraction and validation."""

    # --- Sampling ---
    sampling_rate_hz: int = 50

    # --- Movement detection (raw delta threshold) ---
    movement_threshold: float = 0.12
    movement_start_consecutive_samples: int = 2
    movement_stop_consecutive_samples: int = 5
    minimum_event_duration_ms: int = 300
    maximum_event_duration_ms: int = 5000

    # --- Context window sizing ---
    pre_context_ms: int = 500
    post_context_ms: int = 500

    # --- Debug output paths ---
    debug_events_dir: Path = Path("debug/events")
    debug_rejected_events_dir: Path = Path("debug/rejected_events")

    # --- Rolling combined STD (primary movement indicator) ---
    rolling_std_window_samples: int = 10
    rolling_combined_std_threshold: float = 0.20

    # --- Stage 1: Movement validation ---
    # The rolling combined STD must exceed the threshold for at least this many
    # consecutive samples during the transition region to confirm movement.
    stage1_rolling_std_threshold: float = 0.20
    stage1_min_consecutive_above: int = 3

    # --- Stage 2: Orientation change ---
    # Minimum absolute delta between PRE and POST mean values.
    # At least one axis (Y or Z) must exceed its threshold.
    stage2_delta_y_threshold: float = 0.15
    stage2_delta_z_threshold: float = 0.15

    # --- Transition end debounce ---
    # When movement stops mid-transition, wait this many milliseconds before
    # finalizing the event. If movement resumes within the debounce window,
    # the event continues as a single segment instead of being split into two.
    # Humans naturally produce brief pauses during sit/stand transitions as
    # they shift weight or adjust posture.
    transition_end_debounce_ms: int = 200

    # --- Event cooldown (refractory period) ---
    # After a VALID_TRANSITION is emitted, suppress new event detection for
    # this many milliseconds. Prevents duplicate detections caused by body
    # settling immediately after a valid sit/stand transition.
    event_cooldown_ms: int = 500

    # --- Stability diagnostics (does NOT reject events) ---
    # These are recorded for analysis but have no effect on validation.
    # Real users do not become perfectly stationary immediately after a
    # transition — small body adjustments and natural settling mean POST
    # context is often noisy. Stability may be re-evaluated as a validation
    # stage in the future once we have enough accepted events to study
    # settling patterns.
    stability_reference_max_std: float = 0.15
    stability_reference_ratio: float = 1.5

    # --- Intentionally disabled during feature investigation ---
    # Angle-based orientation thresholds are preserved for future experiments
    # but do NOT drive validation decisions. They are overly sensitive during
    # experimentation and will be re-evaluated after threshold tuning.
    orientation_angle_threshold_deg: float = 15.0
    orientation_delta_y_threshold: float = 0.12
    orientation_delta_z_threshold: float = 0.12
    orientation_stability_threshold: float = 0.08

    @property
    def pre_context_samples(self) -> int:
        return max(0, int(round(self.sampling_rate_hz * self.pre_context_ms / 1000.0)))

    @property
    def post_context_samples(self) -> int:
        return max(0, int(round(self.sampling_rate_hz * self.post_context_ms / 1000.0)))


DEFAULT_CONFIG = EventDetectionConfig()
