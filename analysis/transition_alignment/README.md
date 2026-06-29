# Transition Alignment Analysis

This directory contains a standalone research experiment for understanding why `STAND_UP` transitions are more variable than `SIT_DOWN` transitions.

## Scope

- No ML models
- No classification features
- No changes to the capture pipeline
- No changes to existing analysis scripts

## What it does

- Computes transition durations
- Detects landmark peaks
- Aligns overlays by transition start and by landmark timing
- Compares pairwise similarity with Euclidean distance and DTW
- Writes a markdown report with the findings

## Run

```bash
python analysis/transition_alignment/transition_alignment_analysis.py
```

Optional arguments:

- `--file path/to/session.csv`
- `--participant harshit`
- `--participant harshit --session 1`
