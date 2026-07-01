"""
Movement detection boundary for the event-based pipeline.

Responsibility:
    Decide whether meaningful movement is occurring.

Non-responsibilities:
    No ML, no posture labels, no transition classification, and no voting.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import sqrt
from typing import Optional

from analysis.transition_classification.event_detection.config import DEFAULT_CONFIG, EventDetectionConfig
from analysis.transition_classification.live.serial_stream import Sample


class MovementState(str, Enum):
    """Discrete movement state emitted for each sample."""

    NO_MOVEMENT = "NO_MOVEMENT"
    MOVEMENT_STARTED = "MOVEMENT_STARTED"
    MOVEMENT_CONTINUES = "MOVEMENT_CONTINUES"
    MOVEMENT_STOPPED = "MOVEMENT_STOPPED"


@dataclass(frozen=True)
class MovementDecision:
    """Result of checking one sample for movement."""

    state: MovementState
    is_moving: bool
    timestamp_ms: int
    sample_index: int
    movement_score: float
    movement_start_sample_index: Optional[int] = None
    movement_end_sample_index: Optional[int] = None
    movement_end_timestamp_ms: Optional[int] = None
    reason: str = ""


class MovementDetector:
    """Simple threshold detector based on raw accelerometer deltas.

    This is intentionally simple: no ML, no labels, no filtering, and no
    adaptive thresholds. Movement score is the Euclidean delta from the
    previous sample across x/y/z.
    """

    def __init__(self, config: EventDetectionConfig = DEFAULT_CONFIG) -> None:
        self.config = config
        self._previous_sample: Optional[Sample] = None
        self._sample_index = -1
        self._is_moving = False
        self._moving_count = 0
        self._quiet_count = 0
        self._movement_start_sample_index: Optional[int] = None
        self._last_active_sample_index: Optional[int] = None
        self._last_active_timestamp_ms: Optional[int] = None

    def update(self, sample: Sample) -> MovementDecision:
        """Inspect one sample and emit a movement state."""
        self._sample_index += 1
        score = self._movement_score(sample)
        above_threshold = score >= self.config.movement_threshold

        if above_threshold:
            self._moving_count += 1
            self._quiet_count = 0
            self._last_active_sample_index = self._sample_index
            self._last_active_timestamp_ms = sample.timestamp_ms
        else:
            self._quiet_count += 1
            self._moving_count = 0

        if not self._is_moving and self._moving_count >= self.config.movement_start_consecutive_samples:
            start_index = self._sample_index
            self._is_moving = True
            self._movement_start_sample_index = start_index
            decision = MovementDecision(
                state=MovementState.MOVEMENT_STARTED,
                is_moving=True,
                timestamp_ms=sample.timestamp_ms,
                sample_index=self._sample_index,
                movement_score=score,
                movement_start_sample_index=start_index,
                reason="movement score crossed threshold",
            )
        elif self._is_moving and self._quiet_count >= self.config.movement_stop_consecutive_samples:
            end_index = self._last_active_sample_index
            end_timestamp_ms = self._last_active_timestamp_ms
            self._is_moving = False
            self._moving_count = 0
            self._movement_start_sample_index = None
            self._last_active_sample_index = None
            self._last_active_timestamp_ms = None
            decision = MovementDecision(
                state=MovementState.MOVEMENT_STOPPED,
                is_moving=False,
                timestamp_ms=sample.timestamp_ms,
                sample_index=self._sample_index,
                movement_score=score,
                movement_end_sample_index=end_index,
                movement_end_timestamp_ms=end_timestamp_ms,
                reason="movement score stayed below threshold",
            )
        elif self._is_moving:
            decision = MovementDecision(
                state=MovementState.MOVEMENT_CONTINUES,
                is_moving=True,
                timestamp_ms=sample.timestamp_ms,
                sample_index=self._sample_index,
                movement_score=score,
                movement_start_sample_index=self._movement_start_sample_index,
                reason="movement active",
            )
        else:
            decision = MovementDecision(
                state=MovementState.NO_MOVEMENT,
                is_moving=False,
                timestamp_ms=sample.timestamp_ms,
                sample_index=self._sample_index,
                movement_score=score,
                reason="movement score below threshold",
            )

        self._previous_sample = sample
        return decision

    def _movement_score(self, sample: Sample) -> float:
        if self._previous_sample is None:
            return 0.0
        dx = sample.acc_x - self._previous_sample.acc_x
        dy = sample.acc_y - self._previous_sample.acc_y
        dz = sample.acc_z - self._previous_sample.acc_z
        return float(sqrt((dx * dx) + (dy * dy) + (dz * dz)))
