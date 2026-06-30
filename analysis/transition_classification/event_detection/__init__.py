"""
Event-detection architecture for sitting/standing transitions.

This package is intentionally structural right now. It defines the new flow:

continuous accelerometer stream -> movement detector -> transition extractor
-> context window -> classifier -> one fired event

Movement detection and transition extraction algorithms are deliberately not
implemented in this migration.
"""

from analysis.transition_classification.event_detection.classifier import ClassificationResult, TransitionClassifier
from analysis.transition_classification.event_detection.context_window import ContextWindow, ContextWindowBuilder
from analysis.transition_classification.event_detection.movement_detector import MovementDecision, MovementDetector
from analysis.transition_classification.event_detection.pipeline import EventDetectionPipeline, PipelineEvent
from analysis.transition_classification.event_detection.transition_extractor import TransitionExtractor, TransitionWindow

__all__ = [
    "ClassificationResult",
    "ContextWindow",
    "ContextWindowBuilder",
    "EventDetectionPipeline",
    "MovementDecision",
    "MovementDetector",
    "PipelineEvent",
    "TransitionClassifier",
    "TransitionExtractor",
    "TransitionWindow",
]
