# Transition Alignment Analysis

Source CSV: validation_20260626_183159.csv
Generated: 2026-06-29 14:44:31

## Runtime Summary

- CSV load: 0.01s
- Transition extraction and landmark detection: 1.23s
- Plot generation: 0.63s
- Report generation: 0.00s
- Total runtime: 0.00s

## Interpretation

This analysis asks whether Stand Up variability is mostly temporal misalignment or whether the movement pattern itself is materially different.

## SIT_DOWN

- Count: 1
- Average duration: 4.200 s
- Duration std dev: 0.000 s
- Euclidean mean before alignment: nan
- Euclidean median before alignment: nan
- Best Euclidean alignment: start
- Euclidean mean after best alignment: nan
- DTW-to-reference mean: 0.0000
- DTW-to-reference std: 0.0000
- DTW-to-reference min: 0.0000
- DTW-to-reference max: 0.0000
- Reference transition for DTW: cycle 1

### Landmark Timing

- max_z: avg 2.700 s, std 0.000 s, avg fraction 0.643
- min_y: avg 2.480 s, std 0.000 s, avg fraction 0.590
- max_acc_magnitude: avg 2.720 s, std 0.000 s, avg fraction 0.648
- max_first_derivative: avg 2.580 s, std 0.000 s, avg fraction 0.614

### Atypical Transitions by DTW

- Cycle 1: 0.0000

## STAND_UP

- Count: 1
- Average duration: 2.880 s
- Duration std dev: 0.000 s
- Euclidean mean before alignment: nan
- Euclidean median before alignment: nan
- Best Euclidean alignment: start
- Euclidean mean after best alignment: nan
- DTW-to-reference mean: 0.0000
- DTW-to-reference std: 0.0000
- DTW-to-reference min: 0.0000
- DTW-to-reference max: 0.0000
- Reference transition for DTW: cycle 1

### Landmark Timing

- max_z: avg 1.620 s, std 0.000 s, avg fraction 0.563
- min_y: avg 1.920 s, std 0.000 s, avg fraction 0.667
- max_acc_magnitude: avg 1.560 s, std 0.000 s, avg fraction 0.542
- max_first_derivative: avg 1.500 s, std 0.000 s, avg fraction 0.521

### Atypical Transitions by DTW

- Cycle 1: 0.0000

## Answers

- Does peak alignment reduce variability? No clear reduction was observed.
- Are Stand Up transitions truly different or merely shifted in time? Stand Up still varies after alignment, which suggests a stronger biomechanical component.
- Which alignment method produces the most consistent overlays? start
- Is the observed variability primarily temporal or biomechanical? mixed or biomechanical

## Generated Files

- validation_20260626_183159_sit_down_duration_hist.html
- validation_20260626_183159_sit_down_max_acc_magnitude_aligned.html
- validation_20260626_183159_sit_down_max_first_derivative_aligned.html
- validation_20260626_183159_sit_down_max_z_aligned.html
- validation_20260626_183159_sit_down_min_y_aligned.html
- validation_20260626_183159_sit_down_start_aligned.html
- validation_20260626_183159_stand_up_duration_hist.html
- validation_20260626_183159_stand_up_max_acc_magnitude_aligned.html
- validation_20260626_183159_stand_up_max_first_derivative_aligned.html
- validation_20260626_183159_stand_up_max_z_aligned.html
- validation_20260626_183159_stand_up_min_y_aligned.html
- validation_20260626_183159_stand_up_start_aligned.html
- validation_20260626_183159_transition_similarity_heatmap.html