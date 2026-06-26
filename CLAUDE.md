# Sitting vs Standing Detection Research

## Mission

Build a reliable sitting/standing detection system using:

* Accelerometer X/Y/Z
* Existing posture angle calculation

The system should eventually support OTA model updates.

## Existing Assets

The context folder contains:

* Posture angle calculation source
* Calibration source
* Hardware documentation
* Schematic

These files are the source of truth.

## Constraints

* Do not modify production firmware.
* Keep all work inside this research project.
* Keep code simple and easy to debug.
* Data collection is more important than model development.

## Development Roadmap

Phase 1:
Collect labeled accelerometer and angle data.

Phase 2:
Visualize and analyze collected data.

Phase 3:
Create training datasets.

Phase 4:
Train candidate ML models.

Phase 5:
Deploy lightweight model to firmware.

## Current Focus

Do not generate ML models yet.

Do not generate TinyML code.

Do not generate TensorFlow code.

Focus only on building a reliable data collection pipeline.

## Important Context

The existing firmware contains a file named `training` (training.cpp/training.h).

Despite the name, this file DOES NOT perform machine learning training.

It contains the posture angle calculation, orientation calibration logic, and related mathematical functions.

Treat this file as the source of truth for posture angle computation.

## Repository Structure

```
src/               — Research firmware source (nRF52832 + LIS3DH)
include/           — Firmware headers
platformio.ini     — PlatformIO build config (at project root)
python/            — Host-side capture and analysis scripts
  capture.py       — Interactive protocol-guided data collection
  plot.py          — Plotly visualization with activity regions
  window.py        — Extract overlapping windows from raw data
  config.py        — Shared constants and paths
  utils.py         — RTT/OpenOCD connection helpers
datasets/
  raw/             — Raw captured CSV files (per participant)
  processed/       — Cleaned/merged datasets
  windows/         — Extracted time windows for training
  metadata/        — Session metadata JSON files
plots/             — Generated interactive HTML plots
CONTEXT/           — Production firmware reference (read-only)
training/          — Future: ML training scripts
models/            — Future: trained model artifacts
docs/
  RESEARCH_LOG.md  — Engineering journal (append-only)
  KNOWN_ISSUES.md  — Issue tracker (never delete entries)
```

## Experiment 1: Raw Accelerometer Separability

Goal: Determine if filtered acc_x, acc_y, acc_z alone can distinguish sitting vs standing.

Firmware streams: timestamp_ms, acc_x, acc_y, acc_z at 50 Hz via RTT.
LPF: alpha=0.1, sensor polled at 100 Hz, output decimated to 50 Hz.
No posture angle in this experiment.

## Data Collection Protocol

Each session:
- One participant at a time
- 25-30 cycles per session
- Each cycle: STANDING (5s) -> SIT_DOWN (untimed) -> SITTING (5s) -> STAND_UP (untimed)
- Transitions are NOT timed — participant moves naturally
- Labels: STANDING, SIT_DOWN, SITTING, STAND_UP

## CSV Format

timestamp_ms, acc_x, acc_y, acc_z, activity_label

## Window Parameters

- Sampling rate: 50 Hz
- Window size: 2 seconds (100 samples)
- Window overlap: 50%
