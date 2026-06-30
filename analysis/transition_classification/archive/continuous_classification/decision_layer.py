"""
Configurable post-model decision layer for stable live predictions.

The ML model still emits raw predictions exactly as before. This module decides
when the displayed state should actually change.
"""

from __future__ import annotations

import time
from collections import Counter, deque
from dataclasses import dataclass
from typing import Deque, Dict, List, Optional

from analysis.transition_classification.live import decision_config as config


@dataclass
class DecisionResult:
    raw_prediction: str
    confidence: Optional[float]
    filtered_prediction: Optional[str]
    stable_state: Optional[str]
    decision: str
    reason: str
    decision_seconds: float


@dataclass
class DecisionMetrics:
    total_predictions: int = 0
    confidence_sum: float = 0.0
    confidence_count: int = 0
    ignored_predictions: int = 0
    accepted_predictions: int = 0
    state_changes: int = 0
    false_state_flips_prevented: int = 0
    decision_time_sum: float = 0.0

    @property
    def average_confidence(self) -> Optional[float]:
        if self.confidence_count == 0:
            return None
        return self.confidence_sum / self.confidence_count

    @property
    def average_decision_latency(self) -> float:
        if self.total_predictions == 0:
            return 0.0
        return self.decision_time_sum / self.total_predictions


class PredictionDecisionLayer:
    """Smooth raw predictions into a stable displayed state."""

    def __init__(
        self,
        confidence_threshold: float = config.CONFIDENCE_THRESHOLD,
        majority_window: int = config.MAJORITY_WINDOW,
        min_consecutive: int = config.MIN_CONSECUTIVE,
        enable_confidence: bool = config.ENABLE_CONFIDENCE_FILTER,
        enable_majority: bool = config.ENABLE_MAJORITY_FILTER,
        enable_consecutive: bool = config.ENABLE_CONSECUTIVE_FILTER,
        filter_order: Optional[List[str]] = None,
    ) -> None:
        self.confidence_threshold = confidence_threshold
        self.majority_window = majority_window
        self.min_consecutive = min_consecutive
        self.enabled = {
            "confidence": enable_confidence,
            "majority": enable_majority,
            "consecutive": enable_consecutive,
        }
        self.filter_order = filter_order or list(config.FILTER_ORDER)
        self.history: Deque[str] = deque(maxlen=majority_window)
        self.consecutive_candidate: Optional[str] = None
        self.consecutive_count = 0
        self.stable_state: Optional[str] = None
        self.metrics = DecisionMetrics()

    def update(self, raw_prediction: str, confidence: Optional[float]) -> DecisionResult:
        """Apply configured filters to one raw prediction."""
        start = time.perf_counter()
        self.metrics.total_predictions += 1
        if confidence is not None:
            self.metrics.confidence_sum += confidence
            self.metrics.confidence_count += 1

        candidate: Optional[str] = raw_prediction
        reason_parts: List[str] = []

        for filter_name in self.filter_order:
            if not self.enabled.get(filter_name, False):
                continue
            if filter_name == "confidence":
                candidate = self._apply_confidence(candidate, confidence, reason_parts)
            elif filter_name == "majority":
                candidate = self._apply_majority(candidate, reason_parts)
            elif filter_name == "consecutive":
                candidate = self._apply_consecutive(candidate, reason_parts)
            else:
                reason_parts.append(f"unknown filter skipped: {filter_name}")
            if candidate is None:
                break

        previous_state = self.stable_state
        decision = "Ignored"
        if candidate is not None:
            self.stable_state = candidate
            decision = "Accepted"
            self.metrics.accepted_predictions += 1
            if previous_state is not None and previous_state != self.stable_state:
                self.metrics.state_changes += 1
            elif previous_state is None:
                self.metrics.state_changes += 1
        else:
            self.metrics.ignored_predictions += 1
            if self.stable_state is not None and raw_prediction != self.stable_state:
                self.metrics.false_state_flips_prevented += 1

        elapsed = time.perf_counter() - start
        self.metrics.decision_time_sum += elapsed
        reason = "; ".join(reason_parts) if reason_parts else "all enabled filters passed"
        return DecisionResult(
            raw_prediction=raw_prediction,
            confidence=confidence,
            filtered_prediction=candidate,
            stable_state=self.stable_state,
            decision=decision,
            reason=reason,
            decision_seconds=elapsed,
        )

    def _apply_confidence(self, candidate: Optional[str], confidence: Optional[float], reasons: List[str]) -> Optional[str]:
        if candidate is None:
            return None
        if confidence is None:
            reasons.append("confidence unavailable")
            return None
        if confidence < self.confidence_threshold:
            reasons.append(f"confidence below threshold ({confidence:.2f} < {self.confidence_threshold:.2f})")
            return None
        reasons.append("confidence passed")
        return candidate

    def _apply_majority(self, candidate: Optional[str], reasons: List[str]) -> Optional[str]:
        if candidate is None:
            return None
        self.history.append(candidate)
        winner, count = Counter(self.history).most_common(1)[0]
        reasons.append(f"majority vote selected {winner} ({count}/{len(self.history)})")
        return winner

    def _apply_consecutive(self, candidate: Optional[str], reasons: List[str]) -> Optional[str]:
        if candidate is None:
            return None
        if candidate == self.consecutive_candidate:
            self.consecutive_count += 1
        else:
            self.consecutive_candidate = candidate
            self.consecutive_count = 1

        if candidate == self.stable_state:
            reasons.append("prediction matches current stable state")
            return candidate

        if self.consecutive_count < self.min_consecutive:
            reasons.append(f"waiting for consecutive predictions ({self.consecutive_count}/{self.min_consecutive})")
            return None

        reasons.append(f"{self.min_consecutive} consecutive predictions reached")
        return candidate
