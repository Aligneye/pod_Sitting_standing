"""
Transition window extraction boundary for the event-based pipeline.

Responsibility:
    Receive continuous samples and return one complete transition window.

Non-responsibilities:
    No ML, no feature extraction, no confidence thresholds, and no voting.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from analysis.transition_classification.live.serial_stream import Sample


@dataclass(frozen=True)
class TransitionWindow:
    """A completed movement event before feature extraction."""

    window_id: int
    samples: Sequence[Sample]
    start_timestamp_ms: int
    end_timestamp_ms: int


class TransitionExtractor:
    """Placeholder boundary for future transition capture logic."""

    def update(self, sample: Sample, is_moving: bool) -> TransitionWindow | None:
        """Consume one sample and maybe emit a completed transition.

        The extraction algorithm is intentionally left for the next phase.
        """
        raise NotImplementedError("Transition extraction logic is intentionally not implemented yet.")
