"""
Context-window construction for event-based transition classification.

Responsibility:
    Preserve before-context + transition + after-context as one window.

Non-responsibilities:
    No movement detection, no ML inference, and no feature engineering.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Deque, List, Optional, Sequence

from analysis.transition_classification.event_detection.config import DEFAULT_CONFIG, EventDetectionConfig
from analysis.transition_classification.event_detection.movement_detector import MovementDecision, MovementState
from analysis.transition_classification.event_detection.transition_extractor import MovementSegment
from analysis.transition_classification.live.serial_stream import Sample


@dataclass(frozen=True)
class TransitionWindow:
    """A complete event window with before, movement, and after context."""

    event_id: int
    before_context: Sequence[Sample]
    movement_samples: Sequence[Sample]
    after_context: Sequence[Sample]
    movement_start_index: int
    movement_end_index: int
    movement_start_sample_index: int
    movement_end_sample_index: int
    movement_start_timestamp_ms: int
    movement_end_timestamp_ms: int
    pre_context_samples: int
    post_context_samples: int
    total_samples: int
    duration_ms: int
    debounce_merges: int = 0

    @property
    def samples(self) -> Sequence[Sample]:
        """Return the complete before + transition + after sample sequence."""
        return [*self.before_context, *self.movement_samples, *self.after_context]


class ContextWindowBuilder:
    """Maintain pre-context and append post-context for completed movements."""

    def __init__(self, config: EventDetectionConfig = DEFAULT_CONFIG) -> None:
        self.config = config
        self._pre_buffer: Deque[Sample] = deque(maxlen=config.pre_context_samples)
        self._pending_pre_context: List[Sample] = []
        self._pending_segment: Optional[MovementSegment] = None
        self._post_context: List[Sample] = []

    def update(
        self,
        sample: Sample,
        movement: MovementDecision,
        completed_segment: MovementSegment | None,
    ) -> TransitionWindow | None:
        """Update context state and maybe emit one completed TransitionWindow."""
        if movement.state == MovementState.MOVEMENT_STARTED:
            self._pending_pre_context = list(self._pre_buffer)

        if completed_segment is not None:
            self._pending_segment = completed_segment
            self._post_context = []
            if self.config.post_context_samples == 0:
                window = self._build_window()
                self._pre_buffer.append(sample)
                return window

        elif self._pending_segment is not None:
            self._post_context.append(sample)
            if len(self._post_context) >= self.config.post_context_samples:
                window = self._build_window()
                self._pre_buffer.append(sample)
                return window

        self._pre_buffer.append(sample)
        return None

    def _build_window(self) -> TransitionWindow:
        if self._pending_segment is None:
            raise RuntimeError("Cannot build a context window without a completed movement segment.")

        segment = self._pending_segment
        before = list(self._pending_pre_context)
        movement_samples = list(segment.samples)
        after = list(self._post_context)
        movement_start_index = len(before)
        movement_end_index = movement_start_index + max(0, len(movement_samples) - 1)
        total_samples = len(before) + len(movement_samples) + len(after)
        duration_ms = 0
        all_samples = [*before, *movement_samples, *after]
        if all_samples:
            duration_ms = int(all_samples[-1].timestamp_ms - all_samples[0].timestamp_ms)

        window = TransitionWindow(
            event_id=segment.event_id,
            before_context=before,
            movement_samples=movement_samples,
            after_context=after,
            movement_start_index=movement_start_index,
            movement_end_index=movement_end_index,
            movement_start_sample_index=segment.movement_start_sample_index,
            movement_end_sample_index=segment.movement_end_sample_index,
            movement_start_timestamp_ms=segment.movement_start_timestamp_ms,
            movement_end_timestamp_ms=segment.movement_end_timestamp_ms,
            pre_context_samples=len(before),
            post_context_samples=len(after),
            total_samples=total_samples,
            duration_ms=duration_ms,
            debounce_merges=segment.debounce_merges,
        )

        self._pending_segment = None
        self._pending_pre_context = []
        self._post_context = []
        return window
