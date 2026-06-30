# Transition Classification

This directory contains the sitting/standing transition ML work.

The active architecture target is now event detection:

```text
Continuous Accelerometer Stream
-> Movement Detector
-> Transition Window Extractor
-> Context Window Builder
-> Feature Extraction
-> Transition Classifier
-> Fire One Event
```

The old sliding-window continuous-classification pipeline is preserved for
debugging and comparison, but it is no longer the target live architecture.
See `MIGRATION_EVENT_DETECTION.md` for the migration report.

## Goal

Detect `SIT_DOWN` and `STAND_UP` as discrete movement events, not as continuous
posture states.

The classical ML baseline still exists to understand dataset separability and
to export transition classifiers.

## Scope

- Logistic Regression
- Random Forest
- SVM with RBF kernel
- 5-fold cross validation
- Transition-level samples only
- No neural networks
- Event-detection skeleton only; movement detection and transition extraction
  algorithms are intentionally not implemented yet

## Folder Structure

```text
analysis/transition_classification/
  README.md
  MIGRATION_EVENT_DETECTION.md
  event_detection/
  archive/
  baseline_classifier.py
  dataset_builder.py
  feature_experiments.py
  live_debug/
  live/
  utils.py
  reports/
  plots/
  models/
  dataset/
```

## Event Detection Architecture

New structural modules:

- `event_detection/movement_detector.py`: decides whether meaningful movement
  is occurring. No ML and no labels.
- `event_detection/transition_extractor.py`: receives continuous samples and
  returns one completed transition window.
- `event_detection/context_window.py`: preserves before + transition + after
  context around an event.
- `event_detection/classifier.py`: classifies a completed transition feature
  vector as `SIT_DOWN` or `STAND_UP`.
- `event_detection/pipeline.py`: coordinates the complete flow and fires one
  event.

These modules are intentionally skeletal. They create the architecture for the
next phase without introducing new algorithms or retraining anything.

## Archived Continuous Classification

Old decision-layer concepts are archived in:

```text
analysis/transition_classification/archive/continuous_classification/
```

Archived concepts:

- confidence thresholding
- majority voting
- consecutive prediction filtering
- stable state
- decision layer

The legacy `live/` folder remains available for debugging continuity while the
new event-detection runner is implemented.

## Dataset Building

Each transition becomes one sample.

The dataset builder keeps the transition extraction, interpolation, and normalization exactly as they are. The only change is that each row now carries extra metadata so future validation schemes can be implemented without redesigning the dataset.

### Metadata columns

- `transition_id`
- `participant_id`
- `session_id`
- `source_file`
- `recording_timestamp`
- `cycle_number`
- `transition_index`
- `transition_duration_seconds`
- `label`

### Why these fields exist

- `transition_id`: lets us trace an individual prediction back to one exact transition.
- `participant_id`: enables Leave-One-Participant-Out validation later.
- `session_id`: enables Leave-One-Session-Out validation later.
- `source_file`: lets us group samples from the same recording if needed.
- `recording_timestamp`: helps when comparing repeated captures from the same person.
- `cycle_number`: gives a simple human-readable index inside a recording.
- `transition_index`: helps inspect which transition in the file was misclassified.
- `transition_duration_seconds`: preserves the original timing so we can study duration effects later.
- `label`: the class target, either `SIT_DOWN` or `STAND_UP`.

After the metadata columns, the dataset stores flattened features as `feature_000`, `feature_001`, and so on.

The default normalization uses 100 samples per transition and flattens `acc_x`, `acc_y`, and `acc_z` into a 300-dimensional vector.

This structure makes future validation experiments easier because the model scripts can train on `feature_*` columns while grouping or filtering by the metadata columns without changing the dataset builder.

## How to Run

Build dataset:

```bash
python analysis/transition_classification/dataset_builder.py
```

Run baseline benchmark:

```bash
python analysis/transition_classification/baseline_classifier.py
```

Run feature experiments:

```bash
python analysis/transition_classification/feature_experiments.py
```

Optional arguments:

- `--participant harshit`
- `--session 1`
- `--file path/to/session.csv`
- `--samples 100`

## Outputs

- `reports/classification_report.md`
- `reports/results.csv`
- `reports/predictions.csv`
- `reports/feature_comparison.csv`
- `plots/*confusion_matrix.png`

## Future validation support

The schema now exposes the columns needed for:

- `StratifiedKFold`
- `StratifiedGroupKFold`
- Leave-One-Session-Out
- Leave-One-Participant-Out

That means future validation strategies can be added by changing the splitter, not the dataset format.

## Why classical ML first

We want a lightweight baseline that tells us whether the transition data is already separable with simple models before investing in more complex architectures.

## Current Limitations

- Small dataset size
- Potential participant-specific bias
- Cross-validation may still be optimistic if sessions are not diverse enough
- This is only a baseline, not the final posture detection system

## Live Debugging

Use `analysis/transition_classification/live_debug/` when a live prediction does
not match offline validation. The recorder captures the raw stream, window
boundaries, exact feature vectors, and timing so the session can be replayed
and inspected before any preprocessing or model changes are made.
