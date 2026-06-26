# Research Log — Sitting vs Standing Detection

## Project Objective

Build a reliable sitting/standing detection system using filtered accelerometer data from the AlignEye Pod V5 (nRF52832 + LIS3DH). The system should eventually support OTA model updates on the production device.

## Current Phase

**Phase 1: Data Collection Infrastructure**

Building a professional-quality, repeatable data collection and visualization pipeline before any ML work begins.

## Current Architecture

```
┌─────────────────────────────────────────────────────────┐
│  nRF52832 + LIS3DH (Research Firmware)                  │
│  - Polls accelerometer at 100 Hz                        │
│  - Applies IIR LPF (alpha=0.1) identical to production  │
│  - Outputs filtered CSV at 50 Hz via SEGGER RTT         │
└───────────────────────┬─────────────────────────────────┘
                        │ RTT over CMSIS-DAP
                        ▼
┌─────────────────────────────────────────────────────────┐
│  OpenOCD (RTT TCP Server on port 9090)                  │
└───────────────────────┬─────────────────────────────────┘
                        │ TCP socket
                        ▼
┌─────────────────────────────────────────────────────────┐
│  Python Pipeline (capture.py)                           │
│  - Interactive protocol-guided session                  │
│  - Automatic activity labeling per phase                │
│  - Saves raw CSV + metadata JSON + events              │
└───────────────────────┬─────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────┐
│  Post-processing                                        │
│  - plot.py: Plotly HTML visualizations                  │
│  - window.py: 2s overlapping window extraction          │
└─────────────────────────────────────────────────────────┘
```

## Important Design Decisions

| Date | Decision | Reason |
|------|----------|--------|
| 2026-06-26 | Use RTT instead of UART/BLE for data streaming | nRF52832 has no USB serial. RTT via debug probe is zero-latency and doesn't require additional hardware. |
| 2026-06-26 | LPF alpha=0.1, sensor at 100Hz, output at 50Hz | Matches production firmware exactly. Ensures research data is representative of what the production model will see. |
| 2026-06-26 | Transitions are untimed (user presses ENTER) | Natural movement speed varies per person. Forcing a timer would create artificial transition data. |
| 2026-06-26 | Labels assigned by protocol phase, not by algorithm | Ground truth must come from the experimental protocol, not from a classifier we haven't built yet. |
| 2026-06-26 | platformio.ini at project root | PlatformIO VS Code extension requires .ini in the workspace root. Keeps firmware + Python in one VS Code window. |
| 2026-06-26 | One participant per capture run | Simpler workflow. Re-run for next participant. No complex multi-person state. |
| 2026-06-26 | Window extraction skips mixed-label boundaries | A 2s window spanning STANDING->SIT_DOWN would corrupt the label. Only pure-label windows are saved. |
| 2026-06-26 | No posture angle in Experiment 1 | Goal is to test if raw acc alone separates sit/stand before adding derived features. |
| 2026-06-26 | Plotly for visualization (not matplotlib) | Interactive zoom/pan/hover is essential for inspecting transition dynamics in 50Hz data. |

## Completed Milestones

### 2026-06-26 — Initial Pipeline Setup

- Created research firmware: LIS3DH init, LPF, CSV streaming at 50Hz over RTT
- Created modular Python pipeline: config.py, utils.py, capture.py, plot.py, window.py
- Established data collection protocol (STANDING → SIT_DOWN → SITTING → STAND_UP)
- Generated first test recording and validated end-to-end pipeline
- Generated first Plotly visualizations (acc_x, acc_y, acc_z, combined, magnitude)
- Extracted first windows from test data

## Current Experiment

**Experiment 1: Raw Accelerometer Separability**

- Question: Can filtered acc_x, acc_y, acc_z alone distinguish sitting from standing?
- Method: Collect 25-30 sit/stand cycles per participant, visualize, inspect separability
- Metrics: Visual inspection of axis distributions during STANDING vs SITTING phases
- Status: Pipeline built, first test capture completed

## Observations

### From first test capture (participant "1", 1 cycle)

- Data flows correctly at ~50 Hz
- STANDING phase shows stable readings around X≈7.5, Y≈5.6, Z≈-2.9 m/s²
- Only STANDING data was captured in this test (session was cut short)
- LPF is working — values are smooth, no visible noise spikes

## Lessons Learned

1. PlatformIO extension is strict about folder layout — .ini must be at workspace root
2. RTT requires OpenOCD running as intermediary — cannot connect directly from Python
3. First-order IIR at alpha=0.1 with 100Hz input provides good smoothing for 50Hz output

## Next Milestone

- Collect a full 25-cycle session with one participant
- Verify all four phases (STANDING, SIT_DOWN, SITTING, STAND_UP) appear in the data
- Visually confirm that STANDING and SITTING produce distinct acceleration signatures
- Determine which axis/axes carry the most discriminative signal
