"""
Configuration for live prediction stabilization.

These settings affect only the post-model decision layer. They do not change
the trained model, preprocessing, interpolation, or feature generation.
"""

CONFIDENCE_THRESHOLD = 0.70
MAJORITY_WINDOW = 5
MIN_CONSECUTIVE = 3

ENABLE_CONFIDENCE_FILTER = True
ENABLE_MAJORITY_FILTER = True
ENABLE_CONSECUTIVE_FILTER = True

# Debug-only mode for validating the trained classifier by itself.
# When True, live inference bypasses every post-processing filter and logs the
# direct model output for each window. Do not use this as the final UX layer.
DEBUG_RAW_MODEL_OUTPUT = False

# Filters run in this order. Supported names:
# "confidence", "majority", "consecutive"
FILTER_ORDER = ["confidence", "majority", "consecutive"]
