# Event Detection Migration Report

## Reason For Migration

The previous live inference formulation treated sitting and standing transitions
like continuous states. That produced a pipeline centered on sliding windows,
classifier output smoothing, confidence thresholds, majority voting, and stable
state management.

The new interpretation is that `SIT_DOWN` and `STAND_UP` are events. The
classifier should run only after meaningful movement has been detected and a
complete transition window has been captured.

The first migration was structural only. Phase 1 now adds simple movement and
event extraction while still avoiding feature engineering, retraining, firmware
changes, dataset changes, and classifier integration.

## New Target Flow

```text
Continuous Accelerometer Stream
-> Movement Detector
-> Transition Window Extractor
-> Context Window Builder
-> Orientation Validator
-> Feature Extraction
-> Transition Classifier
-> Fire One Event
```

## Repository Decisions

| Path | Category | Decision |
|---|---|---|
| `analysis/transition_classification/event_detection/` | CREATE | New active architecture skeleton for event-based inference. |
| `analysis/transition_classification/event_detection/config.py` | CREATE | Central threshold/configuration file for Phase 1 event extraction. |
| `analysis/transition_classification/event_detection/movement_detector.py` | CREATE | Simple non-ML movement detector using raw accelerometer deltas. |
| `analysis/transition_classification/event_detection/transition_extractor.py` | CREATE | Captures movement-only segments from movement state transitions. |
| `analysis/transition_classification/event_detection/context_window.py` | CREATE | Builds before + movement + after context windows. |
| `analysis/transition_classification/event_detection/orientation_validator.py` | CREATE | Scores candidate events using simple physical evidence. Angle-based validation is disabled during feature investigation. |
| `analysis/transition_classification/event_detection/classifier.py` | CREATE | Thin classifier boundary that runs inference on a completed feature vector. |
| `analysis/transition_classification/event_detection/pipeline.py` | CREATE | Coordinates Phase 1 extraction and writes debug event artifacts. |
| `analysis/event_analysis/analyze_events.py` | CREATE | Scans accepted/rejected event summaries and writes aggregate CSV/Plotly statistics. |
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
- the old decision layer

Note: The new pipeline has its own transition-end debounce mechanism in
`TransitionExtractor` that prevents a single physical transition from being
split into multiple events. This is unrelated to the old decision layer's
cooldown/debounce logic which operated on classifier predictions.

Those concepts remain archived for reference in
`analysis/transition_classification/archive/continuous_classification/`.

## What Remains Unimplemented

Still intentionally deferred:

- event-based feature extraction
- classifier integration
- live CLI that runs the new event-detection pipeline end-to-end
- validation comparing old sliding-window live output against new event output

## Phase 2 Staged Validation (movement_orientation_v2)

Phase 2 uses a two-stage validation pipeline:

```text
Movement
-> TransitionWindow
-> Stage 1: Movement (rolling combined STD as PRIMARY indicator)
-> Stage 2: Orientation (delta Y/Z confirmation)
-> VALID EVENT (with stability diagnostics recorded)
```

The validator answers only:

```text
Is there enough simple physical evidence to keep this candidate event?
```

It does not classify `SIT_DOWN` or `STAND_UP`.

- Stage 1: Rolling combined STD must exceed threshold for enough consecutive
  samples during the transition region. If this fails, reject immediately.
- Stage 2: At least one axis (Y or Z) must show meaningful PRE-to-POST delta.

Stability metrics (PRE/POST combined STD, transition-to-stable ratio) are
computed and recorded as diagnostics but do NOT reject events. Real users do
not become perfectly stationary immediately after a transition — small body
adjustments and natural settling mean POST context is often noisy. Stability
may be re-evaluated as a validation stage once we have enough accepted events
to study settling patterns.

Angle-based validation is intentionally disabled — it is overly sensitive during
experimentation. The code is preserved for future experiments.

Accepted events are saved under `debug/events/`. Rejected candidate movements
are saved under `debug/rejected_events/` with the same artifact set, rejection
stage, and reason.

## Next Development Stage

1. Analyze accepted events to identify false positives.
2. Tune orientation thresholds using accepted/rejected statistics.
3. Replay old datasets through the event detector.
4. Decide if stability should become a validation stage again.
5. Re-evaluate angle-based metrics after threshold tuning.
6. Design transition-aware feature engineering.
7. Integrate the classifier.
8. Compare with the old sliding-window pipeline.

## Compatibility Notes

- Firmware is unchanged.
- Dataset files are unchanged.
- Model artifacts are unchanged by this migration.
- The legacy sliding-window live runner remains available for debugging and
  comparison while the new event pipeline is implemented.
