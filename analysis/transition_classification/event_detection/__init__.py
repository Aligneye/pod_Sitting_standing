"""
Event-detection architecture for sitting/standing transitions.

This package extracts complete sitting/standing transition events from a
continuous accelerometer stream and validates them using a staged pipeline:

    Stage 1 - Movement: Rolling combined STD confirms real movement.
    Stage 2 - Orientation: PRE-to-POST delta Y/Z confirms posture change.

Stability metrics are computed as diagnostics but do not reject events.
Classifier integration is deliberately outside Phase 1/2.
"""

from analysis.transition_classification.event_detection.classifier import ClassificationResult, TransitionClassifier
from analysis.transition_classification.event_detection.config import DEFAULT_CONFIG, EventDetectionConfig
from analysis.transition_classification.event_detection.context_window import ContextWindowBuilder, TransitionWindow
from analysis.transition_classification.event_detection.event_summary import build_event_summary, compute_statistical_features, transition_window_to_dataframe, transition_window_to_rows
from analysis.transition_classification.event_detection.movement_detector import MovementDecision, MovementDetector, MovementState
from analysis.transition_classification.event_detection.orientation_validator import (
    OrientationMetrics,
    OrientationValidationResult,
    OrientationValidationStatus,
    OrientationValidator,
    StabilityDiagnostics,
    StageResult,
    ValidationStage,
    VALIDATION_PIPELINE_VERSION,
    compute_orientation_metrics,
)
from analysis.transition_classification.event_detection.pipeline import EventDebugWriter, EventDetectionPipeline
from analysis.transition_classification.event_detection.transition_extractor import ExtractorState, MovementSegment, TransitionExtractor

__all__ = [
    "ClassificationResult",
    "ContextWindowBuilder",
    "DEFAULT_CONFIG",
    "EventDebugWriter",
    "EventDetectionConfig",
    "EventDetectionPipeline",
    "ExtractorState",
    "MovementDecision",
    "MovementDetector",
    "MovementSegment",
    "MovementState",
    "OrientationMetrics",
    "OrientationValidationResult",
    "OrientationValidationStatus",
    "OrientationValidator",
    "StabilityDiagnostics",
    "StageResult",
    "TransitionClassifier",
    "TransitionExtractor",
    "TransitionWindow",
    "VALIDATION_PIPELINE_VERSION",
    "ValidationStage",
    "build_event_summary",
    "compute_statistical_features",
    "compute_orientation_metrics",
    "transition_window_to_dataframe",
    "transition_window_to_rows",
]
