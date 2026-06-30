# Live Debugging

This module turns live transition inference into a replayable, fully
instrumented debugging pipeline.

## What gets recorded

Every session writes a standalone directory containing:

- `raw_samples.csv`
- `windows.csv`
- `features.csv`
- `predictions.csv`
- `metadata.json`
- `ground_truth.csv` if you provide labels

## Raw sample log

One row per incoming sensor sample:

- `sample_index`
- `timestamp_ms`
- `acc_x`
- `acc_y`
- `acc_z`

## Window log

One row per sliding window with exact boundaries:

- `window_id`
- `start_sample`
- `end_sample`
- `start_timestamp`
- `end_timestamp`
- `window_size` in seconds
- `overlap`

Extra columns are also stored when available:

- `window_size_seconds`
- `window_size_samples`
- `step_samples`

## Feature log

One row per window with the exact flattened feature vector that was passed to
the model.

The columns are named `feature_000`, `feature_001`, and so on so they can be
compared directly with the offline dataset.

## Prediction log

One row per inference with the live timing breakdown:

- `window_id`
- `prediction`
- `confidence`
- `inference_time_ms`
- `preprocessing_time_ms`
- `total_latency_ms`

Extra decision-layer fields are stored too when available:

- `decision_time_ms`
- `filtered_prediction`
- `stable_state`
- `decision`
- `decision_reason`

## Session metadata

`metadata.json` stores:

- participant
- session
- sampling rate
- window size
- overlap
- model used
- timestamp
- git commit

## How to record a session

Run the live CLI with a debug session directory:

```bash
python analysis/transition_classification/live/live_predict.py --model analysis/transition_classification/models/logistic_regression.joblib --port COM5 --debug-session analysis/transition_classification/live_debug/sessions/session_001
```

## How to replay and visualize

Generate plots from a recorded session:

```bash
python analysis/transition_classification/live_debug/replay_visualizer.py --session-dir analysis/transition_classification/live_debug/sessions/session_001
```

Replay the same session in live timing:

```bash
python analysis/transition_classification/live_debug/replay_visualizer.py --session-dir analysis/transition_classification/live_debug/sessions/session_001 --replay
```

Optionally recompute predictions during replay:

```bash
python analysis/transition_classification/live_debug/replay_visualizer.py --session-dir analysis/transition_classification/live_debug/sessions/session_001 --replay --model analysis/transition_classification/models/logistic_regression.joblib
```

## Generated plots

The visualizer writes:

- `xyz_vs_time.png`
- `window_boundaries.png`
- `prediction_timeline.png`
- `confidence_timeline.png`
- `ground_truth_timeline.png` when labels exist
- `overlay_prediction_changes.png`

## Debugging workflow

1. Record one live session with `--debug-session`.
2. Compare `features.csv` against the offline dataset feature layout.
3. Inspect `windows.csv` to confirm the window boundaries and overlap.
4. Inspect `predictions.csv` to see timing, confidence, and decision behavior.
5. Generate the plots and check whether the prediction changed too early, too
   late, or flickered.
6. If labels are available, compare the prediction timeline to the ground truth
   timeline before changing preprocessing or retraining.

The goal is to explain every wrong live prediction before changing the ML
model or its preprocessing.

## Auto-stop and emergency stop

If you only want a short capture, add `--duration`:

```bash
python analysis/transition_classification/live/live_predict.py --model analysis/transition_classification/models/logistic_regression.joblib --port COM5 --debug-session analysis/transition_classification/live_debug/sessions/session_001 --duration 60
```

That will stop after about 60 seconds and still write the session bundle.
`Ctrl+C` remains available as an emergency stop, and the recorder still tries
to finalize the files before exiting.
