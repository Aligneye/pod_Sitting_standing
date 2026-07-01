# Event Detection Pipeline

This package extracts complete sitting/standing transition events from a
continuous accelerometer stream and validates them using a staged pipeline.

It does not classify events. It only detects movement, captures the event,
adds context, validates using staged physical evidence, and writes debug
artifacts for visual inspection.

## Validation Philosophy (movement_orientation_v2)

The rolling combined standard deviation is the PRIMARY movement indicator.
Validation uses two mandatory stages:

```text
Stage 1: Movement    — Did rolling combined STD exceed threshold long enough?
Stage 2: Orientation — Did PRE-to-POST mean shift on Y or Z confirm change?
```

Each stage is mandatory. Failure at any stage rejects immediately without
evaluating later stages.

Stability metrics (PRE/POST combined STD, transition-to-stable ratio) are
computed and recorded as diagnostics but do NOT reject events. Real users do
not become perfectly stationary immediately after a transition — small body
adjustments and natural settling mean POST context is often noisy.

## Flow

```text
Sample
-> MovementDetector.update()
-> TransitionExtractor.update()
-> ContextWindowBuilder.update()
-> TransitionWindow
-> OrientationValidator.validate()
    -> Stage 1: Movement validation (rolling combined STD)
    -> Stage 2: Orientation change (delta_y, delta_z)
    -> Stability diagnostics (recorded, never rejects)
-> debug/events/event_XXXX/ or debug/rejected_events/event_XXXX/
```

## Stage 1: Movement Validation

The rolling combined STD is computed as:

```text
sqrt(rolling_std_x² + rolling_std_y² + rolling_std_z²)
```

This must exceed `stage1_rolling_std_threshold` for at least
`stage1_min_consecutive_above` consecutive samples during the transition
region.

If movement never exceeds threshold long enough: reject immediately. No
orientation or stability evaluation needed.

## Stage 2: Orientation Change

If Stage 1 passes, verify that orientation actually changed.

Uses only lightweight metrics:

- `|delta_mean_y|` >= `stage2_delta_y_threshold`
- `|delta_mean_z|` >= `stage2_delta_z_threshold`

At least one axis must show meaningful shift.

Angle-based validation is intentionally disabled — it is overly sensitive
during experimentation. The angle code is preserved for future experiments
but does not drive any decision.

## Event Cooldown (Refractory Period)

After a VALID_TRANSITION is emitted, the pipeline enters a cooldown period
(`event_cooldown_ms`, default 500ms). During cooldown:

- Samples are still consumed normally
- No new events are started
- Movement detection is suppressed
- The cooldown prevents duplicate detections caused by body settling

This exists because after a real sit/stand transition, the body often makes
small adjustments (shifting weight, adjusting posture) that can trigger the
movement detector again. Without cooldown, these settling movements would
produce false duplicate events immediately after a valid transition.

The cooldown is purely a state-management mechanism — no new heuristics,
thresholds, or statistical checks are involved.

The event plot shades the debounce period in light purple at the tail of the
TRANSITION region, labeled "POSSIBLE END / DEBOUNCE". This shows where the
extractor waited before finalizing, allowing visual verification of whether
movement resumed or the event was correctly merged.

The cooldown period is shaded in light yellow after POST CONTEXT, labeled
"COOLDOWN", making it visually obvious which time window was intentionally
ignored for new event detection.

## Stability Diagnostics (does NOT reject)

Stability metrics are computed for every event but do not participate in
the accept/reject decision:

- Combined STD for PRE, TRANSITION, POST
- Stable average = (PRE + POST) / 2
- Transition-to-stable ratio

These are recorded in `event_summary.json` and `stability_diagnostics` for
future analysis. They may be re-evaluated as a validation stage once we have
enough accepted events to study natural settling patterns after transitions.

## Validation Outcomes

```text
Movement not detected          → REJECT_EVENT (at stage: movement)
Movement OK, orientation failed → REJECT_EVENT (at stage: orientation)
Movement OK, orientation OK    → VALID_TRANSITION
```

## Movement Detection

`movement_detector.py` uses a simple raw accelerometer delta:

```text
sqrt(dx² + dy² + dz²)
```

If this score is greater than or equal to `movement_threshold`, the sample is
considered active. A configurable number of active samples starts movement. A
configurable number of quiet samples stops movement.

Emitted states:

- `NO_MOVEMENT`
- `MOVEMENT_STARTED`
- `MOVEMENT_CONTINUES`
- `MOVEMENT_STOPPED`

## Transition Extraction

The `TransitionExtractor` uses a three-state machine:

```text
IDLE → TRACKING → POSSIBLE_END → finalize or resume TRACKING
```

- **IDLE**: Waiting for `MOVEMENT_STARTED`.
- **TRACKING**: Active movement, appending samples.
- **POSSIBLE_END**: Movement stopped but debounce window has not expired.

### Transition End Debounce

When movement stops, the extractor does NOT immediately finalize the event.
Instead it enters `POSSIBLE_END` and waits for `transition_end_debounce_ms`
(default 200ms).

If movement resumes within the debounce window, the extractor returns to
`TRACKING` and continues appending samples to the same event. If the debounce
expires without movement resuming, the segment is finalized normally.

**Why this exists**: Humans naturally produce brief pauses during sit/stand
transitions. When standing up, a person may pause momentarily while shifting
weight from the seat to their legs. When sitting down, there is often a brief
deceleration as the body approaches the seat before final settling. These
pauses cause the movement detector to emit `MOVEMENT_STOPPED` even though the
physical transition is not complete.

Without the debounce, a single real-world transition gets split into multiple
events — creating duplicate detections that the cooldown mechanism cannot
prevent (because the second event begins before the first officially ends).

The debounce is purely a state-management mechanism. It does not add scoring,
statistical features, or validation logic. It only delays the finalization
decision by a short configurable window.

The number of times movement resumed during a single event is tracked as
`debounce_merges` in the event summary.

### Duration Guards

Events shorter than `minimum_event_duration_ms` are discarded. Events longer
than `maximum_event_duration_ms` are reset (including during POSSIBLE_END).

## Context

`context_window.py` keeps a circular pre-context buffer. When movement starts,
the current pre-context is attached. After movement stops, post-context samples
are appended before finalizing.

## Debug Output

Accepted events:

```text
debug/events/event_XXXX/
  raw_samples.csv
  metadata.json
  event_summary.json
  event_plot.html
  mean_comparison.html
  std_comparison.html
  variance_comparison.html
  delta_mean.html
  stage_breakdown.html
  combined_std_analysis.html
```

Rejected events (same artifact set):

```text
debug/rejected_events/event_XXXX/
```

## event_summary.json

Contains:

- Event ID, timestamps, duration, total samples, sampling rate
- Context counts (pre, transition, post)
- Movement boundaries and duration
- Per-region statistics (mean, std, variance, range, min, max)
- Delta features (post - pre mean shift per axis)
- Combined STD per region
- Relative STD metrics (transition vs pre, post, stable average)
- Validation result with pipeline version, per-stage pass/fail, reason, metrics
- Rolling STD metrics (peak, mean, duration above threshold)
- Stability diagnostics (pre/post/transition std, stable avg, ratio — never rejects)
- Legacy orientation metrics (disabled)

## Plot Titles

Plot titles now show the validation decision at a glance:

```text
VALID_TRANSITION | Event 3 | Movement ✓ | Orientation ✓ | Stability ✓
REJECT_EVENT | Event 7 | Movement ✓ | Orientation ✗ | Stability — not evaluated
```

The event plot also clearly marks:

- Movement start/end vertical lines
- Rolling STD threshold horizontal line
- Orange regions where rolling STD exceeds threshold

## Configuration

All thresholds live in `config.py`:

### Sampling

- `sampling_rate_hz`

### Movement Detection

- `movement_threshold`
- `movement_start_consecutive_samples`
- `movement_stop_consecutive_samples`
- `minimum_event_duration_ms`
- `maximum_event_duration_ms`

### Context

- `pre_context_ms`
- `post_context_ms`

### Rolling STD

- `rolling_std_window_samples`
- `rolling_combined_std_threshold`

### Stage 1: Movement

- `stage1_rolling_std_threshold`
- `stage1_min_consecutive_above`

### Stage 2: Orientation

- `stage2_delta_y_threshold`
- `stage2_delta_z_threshold`

### Transition End Debounce

- `transition_end_debounce_ms`

### Cooldown

- `event_cooldown_ms`

### Stability Diagnostics (reference only, does not reject)

- `stability_reference_max_std`
- `stability_reference_ratio`

### Disabled (preserved for future experiments)

- `orientation_angle_threshold_deg`
- `orientation_delta_y_threshold`
- `orientation_delta_z_threshold`
- `orientation_stability_threshold`

## Event Analysis

```bash
python analysis/event_analysis/analyze_events.py
```

## Known Limitations

- The movement detector is simple threshold-based.
- Thresholds are configurable defaults and need tuning against real data.
- Angle-based validation is intentionally disabled during experimentation.
- Stability is diagnostic only — may be re-evaluated as a stage in the future.
- Classifier integration is not part of Phase 1/2.
- Feature extraction is not part of Phase 1/2.

## Future Work

1. Analyze accepted events to identify false positives.
2. Tune orientation thresholds using accepted/rejected event statistics.
3. Replay old datasets through the event detector.
4. Decide if stability should become a validation stage again (after studying settling patterns).
5. Re-evaluate angle-based metrics after threshold tuning.
6. Design transition-aware feature engineering.
7. Integrate the classifier.
8. Compare with the old sliding-window pipeline.
