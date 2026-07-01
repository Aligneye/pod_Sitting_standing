"""
Transition window extraction boundary for the event-based pipeline.

Responsibility:
    Receive continuous samples and return one complete transition window.

States:
    IDLE         — No movement detected, waiting for MOVEMENT_STARTED.
    TRACKING     — Active movement, appending samples to current event.
    POSSIBLE_END — Movement stopped but debounce window has not expired.
                   If movement resumes, return to TRACKING (same event).
                   If debounce expires, finalize the segment.

Non-responsibilities:
    No ML, no feature extraction, no confidence thresholds, and no voting.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Sequence

from analysis.transition_classification.event_detection.config import DEFAULT_CONFIG, EventDetectionConfig
from analysis.transition_classification.event_detection.movement_detector import MovementDecision, MovementState
from analysis.transition_classification.live.serial_stream import Sample


class ExtractorState(Enum):
    IDLE = "idle"
    TRACKING = "tracking"
    POSSIBLE_END = "possible_end"


@dataclass(frozen=True)
class MovementSegment:
    """The raw movement-only portion of one detected transition."""

    event_id: int
    samples: Sequence[Sample]
    movement_start_sample_index: int
    movement_end_sample_index: int
    movement_start_timestamp_ms: int
    movement_end_timestamp_ms: int
    duration_ms: int
    start_reason: str
    end_reason: str
    debounce_merges: int


class TransitionExtractor:
    """Capture raw movement segments from movement-state decisions.

    Uses a debounce window to prevent a single physical transition from being
    split into multiple events when movement briefly pauses mid-transition.
    """

    def __init__(self, config: EventDetectionConfig = DEFAULT_CONFIG) -> None:
        self.config = config
        self._state = ExtractorState.IDLE
        self._samples: List[Sample] = []
        self._event_id = 0
        self._start_sample_index: Optional[int] = None
        self._start_timestamp_ms: Optional[int] = None
        self._start_reason = ""
        self._debounce_start_ms: Optional[int] = None
        self._debounce_merges = 0
        self._last_movement = MovementDecision(
            state=MovementState.NO_MOVEMENT,
            is_moving=False,
            timestamp_ms=0,
            sample_index=0,
            movement_score=0.0,
            reason="init",
        )

    def update(self, sample: Sample, movement: MovementDecision) -> MovementSegment | None:
        """Consume one sample and maybe emit a completed movement segment."""

        # --- IDLE: waiting for movement to begin ---
        if self._state == ExtractorState.IDLE:
            if movement.state == MovementState.MOVEMENT_STARTED:
                self._begin(sample, movement)
            return None

        # --- TRACKING: active movement, appending samples ---
        if self._state == ExtractorState.TRACKING:
            self._samples.append(sample)

            if movement.state == MovementState.MOVEMENT_STOPPED:
                self._last_movement = movement
                self._enter_possible_end(sample)
                return None

            if self._exceeded_max_duration(sample):
                self._reset()
                return None

            return None

        # --- POSSIBLE_END: debounce window, waiting to see if movement resumes ---
        if self._state == ExtractorState.POSSIBLE_END:
            self._samples.append(sample)

            if movement.state in (MovementState.MOVEMENT_STARTED, MovementState.MOVEMENT_CONTINUES):
                self._resume_tracking()
                return None

            if self._debounce_expired(sample):
                return self._finish(sample, self._last_movement)

            if self._exceeded_max_duration(sample):
                self._reset()
                return None

            return None

        return None

    def _begin(self, sample: Sample, movement: MovementDecision) -> None:
        self._state = ExtractorState.TRACKING
        self._samples = []
        self._start_sample_index = movement.movement_start_sample_index or movement.sample_index
        self._start_timestamp_ms = sample.timestamp_ms
        self._start_reason = movement.reason
        self._debounce_start_ms = None
        self._debounce_merges = 0
        self._last_movement = movement

    def _enter_possible_end(self, sample: Sample) -> None:
        self._state = ExtractorState.POSSIBLE_END
        self._debounce_start_ms = sample.timestamp_ms

    def _resume_tracking(self) -> None:
        self._state = ExtractorState.TRACKING
        self._debounce_merges += 1
        self._debounce_start_ms = None

    def _debounce_expired(self, sample: Sample) -> bool:
        if self._debounce_start_ms is None:
            return False
        elapsed = sample.timestamp_ms - self._debounce_start_ms
        return elapsed >= self.config.transition_end_debounce_ms

    def _exceeded_max_duration(self, sample: Sample) -> bool:
        if self._start_timestamp_ms is None:
            return False
        duration_ms = sample.timestamp_ms - self._start_timestamp_ms
        return duration_ms > self.config.maximum_event_duration_ms

    def _finish(self, sample: Sample, movement: MovementDecision) -> MovementSegment | None:
        if self._start_sample_index is None or self._start_timestamp_ms is None:
            self._reset()
            return None

        duration_ms = int(sample.timestamp_ms - self._start_timestamp_ms)
        if duration_ms < self.config.minimum_event_duration_ms:
            self._reset()
            return None

        self._event_id += 1
        segment = MovementSegment(
            event_id=self._event_id,
            samples=list(self._samples),
            movement_start_sample_index=self._start_sample_index,
            movement_end_sample_index=movement.movement_end_sample_index or movement.sample_index,
            movement_start_timestamp_ms=self._start_timestamp_ms,
            movement_end_timestamp_ms=movement.movement_end_timestamp_ms or sample.timestamp_ms,
            duration_ms=duration_ms,
            start_reason=self._start_reason,
            end_reason=movement.reason,
            debounce_merges=self._debounce_merges,
        )
        self._reset()
        return segment

    def _reset(self) -> None:
        self._state = ExtractorState.IDLE
        self._samples = []
        self._start_sample_index = None
        self._start_timestamp_ms = None
        self._start_reason = ""
        self._debounce_start_ms = None
        self._debounce_merges = 0
