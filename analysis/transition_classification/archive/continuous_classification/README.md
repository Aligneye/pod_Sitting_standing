# Archived Continuous-Classification Logic

This folder preserves the old live decision-layer architecture for reference.

The old active flow was:

```text
Sliding Window
-> Feature Extraction
-> Classifier
-> Confidence Threshold
-> Majority Voting
-> Stable State
```

Why archived:

- Sitting down and standing up are now treated as discrete events, not
  continuous states.
- Majority voting, confidence thresholds, stable-state filtering, and
  consecutive prediction logic belong to the old continuous-state formulation.
- The new active architecture lives in
  `analysis/transition_classification/event_detection/`.

Preserved files:

- `decision_config.py`
- `decision_layer.py`
- `README_legacy_live.md`

Nothing in this archive should be imported by the new event-detection pipeline.
Keep it only for comparison, debugging history, or rollback reference.
