"""
Movement detection boundary for the event-based pipeline.

Responsibility:
    Decide whether meaningful movement is occurring.

Non-responsibilities:
    No ML, no posture labels, no transition classification, and no voting.
"""

from __future__ import annotations

from dataclasses import dataclass

from analysis.transition_classification.live.serial_stream import Sample


@dataclass(frozen=True)
class MovementDecision:
    """Result of checking one sample for movement."""

    is_moving: bool
    timestamp_ms: int
    reason: str = "movement detector not implemented"


class MovementDetector:
    """Placeholder boundary for future non-ML movement detection logic."""

    def update(self, sample: Sample) -> MovementDecision:
        """Inspect one sample and report whether movement is active.

        The actual movement rule is intentionally left for the next phase.
        This migration only creates the seam where that rule will live.
        """
        raise NotImplementedError("Movement detection logic is intentionally not implemented yet.")
