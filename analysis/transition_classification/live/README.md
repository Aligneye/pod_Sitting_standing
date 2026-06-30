# Live Inference

This folder contains the real-time transition inference pipeline.

## Architecture

```text
Serial device or CSV replay
        ↓
Sample stream
        ↓
Sliding window
        ↓
Interpolation using the same helper as training
        ↓
Flattened feature vector
        ↓
Loaded sklearn/joblib model
        ↓
Raw prediction and confidence
        ↓
Decision layer
        ↓
Printed result
```

## Files

- `serial_stream.py`
  - Connects to a serial device or replays a recorded CSV
  - Yields accelerometer samples one by one

- `preprocessing.py`
  - Maintains the sliding window
  - Reuses the exact same interpolation helper as training
  - Converts each window into a feature vector

- `inference_utils.py`
  - Loads a trained model
  - Runs prediction
  - Extracts probability confidence if the model supports it

- `live_predict.py`
  - Main entry point for live inference
  - Prints raw prediction, filtered prediction, stable state, reason, timings, and latency
  - Can also record a full debug session with `--debug-session`

- `decision_config.py`
  - Stores all decision-layer settings in one place

- `decision_layer.py`
  - Applies configurable post-model smoothing
  - Does not modify or retrain the ML model

- `../live_debug/`
  - Records raw samples, windows, features, and predictions
  - Replays a recorded session and generates visual diagnostics

## Important design rule

The live pipeline does not reimplement interpolation.
It calls the same normalization helper used by the dataset builder, so the training and inference preprocessing stay identical.

## Decision layer

The model still produces raw predictions exactly as before. The decision layer sits after the model and decides whether the displayed state should change.

### Confidence threshold

Only accepts a prediction when confidence is at least `CONFIDENCE_THRESHOLD`.

This is useful when the model is uncertain and you would rather keep the current state than display a shaky change.

### Majority vote

Keeps a rolling history of recent predictions and chooses the most common label.

This is useful when predictions bounce briefly between states.

### Consecutive prediction filter

Requires the same candidate state to appear `MIN_CONSECUTIVE` times before changing the stable state.

This is useful when you want the displayed state to change only after the model has repeated itself several times.

### Combined mode

Filters can be enabled independently in `decision_config.py`.

Default order:

```text
confidence -> majority -> consecutive
```

Supported experiments:

- Raw model only
- Confidence only
- Majority only
- Consecutive only
- Confidence + Majority
- Confidence + Consecutive
- Majority + Consecutive
- All filters

To run raw model only, set all three `ENABLE_*` options in `decision_config.py` to `False`.

## Example commands

Live serial:

```bash
python analysis/transition_classification/live/live_predict.py --model analysis/transition_classification/models/logistic_regression.joblib --port COM5
```

CSV replay:

```bash
python analysis/transition_classification/live/live_predict.py --model analysis/transition_classification/models/logistic_regression.joblib --csv datasets/raw/harshit/harshit_session_001_20260626_184217.csv
```

## Notes

- Run `baseline_classifier.py` first. It exports `.joblib` files into `analysis/transition_classification/models/`.
- CSV replay is useful for testing the live pipeline before using hardware.
- The preprocessing here is intentionally the same as training: same interpolation path, same feature layout, same normalization behavior.
- Confidence thresholding works best with models that support `predict_proba`, such as Logistic Regression and Random Forest.
- For debugging, record a session with `--debug-session` and inspect the outputs in `analysis/transition_classification/live_debug/`.
- For short captures, add `--duration 60` to stop automatically after about a minute; `Ctrl+C` still works as an emergency stop.
