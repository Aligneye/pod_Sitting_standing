# Event Detection Migration Report

## Reason For Migration

The previous live inference formulation treated sitting and standing transitions
like continuous states. That produced a pipeline centered on sliding windows,
classifier output smoothing, confidence thresholds, majority voting, and stable
state management.

The new interpretation is that `SIT_DOWN` and `STAND_UP` are events. The
classifier should run only after meaningful movement has been detected and a
complete transition window has been captured.

This migration is structural only. It does not add movement detection logic,
transition extraction algorithms, feature engineering, retraining, firmware
changes, or dataset changes.

## New Target Flow

```text
Continuous Accelerometer Stream
-> Movement Detector
-> Transition Window Extractor
-> Context Window Builder
-> Feature Extraction
-> Transition Classifier
-> Fire One Event
```

## Repository Decisions

| Path | Category | Decision |
|---|---|---|
| `analysis/transition_classification/event_detection/` | CREATE | New active architecture skeleton for event-based inference. |
| `analysis/transition_classification/event_detection/movement_detector.py` | CREATE | Boundary for non-ML movement detection. Logic intentionally not implemented. |
| `analysis/transition_classification/event_detection/transition_extractor.py` | CREATE | Boundary for capturing one complete transition. Logic intentionally not implemented. |
| `analysis/transition_classification/event_detection/context_window.py` | CREATE | Boundary for before + transition + after context assembly. Logic intentionally not implemented. |
| `analysis/transition_classification/event_detection/classifier.py` | CREATE | Thin classifier boundary that runs inference on a completed feature vector. |
| `analysis/transition_classification/event_detection/pipeline.py` | CREATE | Coordinator for the new event-detection flow. Feature extraction seam intentionally unimplemented. |
| `analysis/transition_classification/archive/continuous_classification/` | CREATE | Archive area for old continuous-state decision logic. |
| `analysis/transition_classification/live/decision_layer.py` | ARCHIVE | Majority voting, confidence thresholding, stable-state, and consecutive prediction logic belong to the old architecture. A copy is preserved in the archive. |
| `analysis/transition_classification/live/decision_config.py` | ARCHIVE | Old decision-layer configuration belongs to continuous classification. A copy is preserved in the archive. |
| `analysis/transition_classification/live/live_predict.py` | MODIFY LATER | Legacy sliding-window live runner. Kept available for debug continuity; not the new target architecture. |
| `analysis/transition_classification/live/preprocessing.py` | MODIFY LATER | Sliding-window preprocessing is legacy for live inference but useful as a reference for feature compatibility. |
| `analysis/transition_classification/live/inference_utils.py` | KEEP | General model loading and classifier helper. Reused by the new classifier boundary. |
| `analysis/transition_classification/live/serial_stream.py` | KEEP | Hardware/CSV sample stream helper. No firmware behavior change required. |
| `analysis/transition_classification/live_debug/` | KEEP | Debug/replay instrumentation remains useful for diagnosing live sessions. |
| `analysis/transition_classification/baseline_classifier.py` | KEEP | Offline benchmark/export script. No retraining performed by this migration. |
| `analysis/transition_classification/dataset_builder.py` | KEEP | Dataset builder remains unchanged. No dataset migration performed. |
| `analysis/transition_classification/feature_experiments.py` | KEEP | Offline analysis utility; not part of live decision logic. |
| `analysis/transition_classification/utils.py` | KEEP | Shared dataset/interpolation helpers remain available. |
| `python/capture.py` | KEEP | Raw capture utility; no firmware or capture behavior change. |
| `python/config.py` | KEEP | Shared Python configuration for capture/plotting tools. |
| `python/utils.py` | KEEP | Shared utility helpers for Python scripts. |
| `python/analyze_transitions.py` | KEEP | Offline transition inspection utility. |
| `python/plot.py` | KEEP | Raw signal visualization utility. |
| `python/test_serial.py` | KEEP | Serial connectivity test utility. |
| `python/validate_pipeline.py` | KEEP | Pipeline validation utility; useful for regression checks during migration. |
| `python/window.py` | KEEP | Existing window utility/reference. |
| `python/window_plots.py` | KEEP | Useful for visualizing current live/training window boundaries during migration. |
| `analysis/transition_classification/models/` | KEEP | Existing artifacts preserved. No retraining performed. |
| `analysis/transition_classification/reports/` | KEEP | Existing reports preserved. No benchmark rerun required by this migration. |
| `analysis/transition_classification/plots/` | KEEP | Existing plots preserved. |
| `analysis/transition_classification/live_debug/sessions/` | KEEP | Recorded debug sessions remain useful for replaying old live behavior. |
| `__pycache__/` folders | REMOVE LATER | Generated Python bytecode, not source architecture. Not removed in this migration. |

## Old Logic Removed From New Active Pipeline

The new `event_detection` package does not import or depend on:

- majority voting
- confidence thresholding
- stable-state filtering
- consecutive prediction logic
- cooldown/debounce logic
- the old decision layer

Those concepts remain archived for reference in
`analysis/transition_classification/archive/continuous_classification/`.

## What Remains Unimplemented

Intentionally deferred to the next development phase:

- movement detection rule
- transition start/end extraction
- before/after context sizing
- event-based feature extraction
- live CLI that runs the new event-detection pipeline end-to-end
- validation comparing old sliding-window live output against new event output

## Compatibility Notes

- Firmware is unchanged.
- Dataset files are unchanged.
- Model artifacts are unchanged by this migration.
- The legacy sliding-window live runner remains available for debugging and
  comparison while the new event pipeline is implemented.
