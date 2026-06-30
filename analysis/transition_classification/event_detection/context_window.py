"""
Context-window construction for event-based transition classification.

Responsibility:
    Preserve before-context + transition + after-context as one window.

Non-responsibilities:
    No movement detection, no ML inference, and no feature engineering.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from analysis.transition_classification.live.serial_stream import Sample
from analysis.transition_classification.event_detection.transition_extractor import TransitionWindow


@dataclass(frozen=True)
class ContextWindow:
    """A transition plus its surrounding accelerometer context."""

    transition_window: TransitionWindow
    before_context: Sequence[Sample]
    transition_samples: Sequence[Sample]
    after_context: Sequence[Sample]

    @property
    def samples(self) -> Sequence[Sample]:
        """Return the complete before + transition + after sample sequence."""
        return [*self.before_context, *self.transition_samples, *self.after_context]


class ContextWindowBuilder:
    """Placeholder boundary for future before/after context assembly."""

    def build(self, transition_window: TransitionWindow) -> ContextWindow:
        """Build a context-preserving window around one transition.

        The context selection rule is intentionally left for the next phase.
        """
        raise NotImplementedError("Context window construction is intentionally not implemented yet.")
