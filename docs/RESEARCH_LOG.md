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

---

### 2026-06-26 — Hardware Migration: V5 → V3 (Seeed XIAO nRF52840 BLE)

**What was implemented:**
Migrated the research firmware from the custom nRF52832 PCB (Pod V5) to the Seeed XIAO nRF52840 BLE dev board.

**Why:**
The XIAO BLE is physically smaller and easier to attach to a participant during data collection sessions. It connects via USB-C for programming — no debug probe needed for flashing.

**Files modified:**
- `include/config.h` — I2C pin definitions changed
- `platformio.ini` — Board target, upload protocol, and build flags changed
- `upload_hooks.py` — No longer needed (USB-C native upload), file retained but unused

**Design decisions:**
- I2C SDA moved from P0.26 → P0.04 (hardware I2C on XIAO BLE D4 pin)
- I2C SCL moved from P0.27 → P0.05 (hardware I2C on XIAO BLE D5 pin)
- Removed `-DNRF52832_XXAA` build flag (nRF52840 board package handles its own defines)
- Removed `upload_protocol = custom` and `extra_scripts = upload_hooks.py` (XIAO BLE uses built-in USB bootloader)
- Board changed from `adafruit_feather_nrf52832` to `xiaoblenrf52840`

**Assumptions:**
- LIS3DH accelerometer is wired to D4 (SDA) and D5 (SCL) on the XIAO BLE
- RTT Stream library is compatible with nRF52840 (same SEGGER RTT mechanism)
- USB-C connection handles both programming and power

**Observations:**
- The nRF52840 has more RAM (256KB vs 64KB) and flash (1MB vs 512KB) — no constraints on firmware size
- RTT still requires a debug probe for data capture (USB serial could be an alternative in future)

**Remaining verification:**
- Confirm firmware compiles for xiaoblenrf52840 target
- Confirm I2C communication with LIS3DH works on D4/D5
- Confirm RTT data stream still works via CMSIS-DAP probe (needed for capture.py)
- Determine if USB Serial can replace RTT for simpler data capture workflow

---

### 2026-06-26 — RTT → USB Serial Migration

**What was implemented:**
Switched firmware output from SEGGER RTT to native USB Serial. Updated Python pipeline to use pyserial instead of OpenOCD TCP socket.

**Why:**
XIAO nRF52840 has native USB-C. RTT required a separate debug probe for data capture — unnecessary hardware complexity.

**Files modified:**
- `src/main.cpp` — Replaced all `rtt.print()` with `Serial.print()`, added `Serial.begin(115200)`
- `platformio.ini` — Switched to Seeed platform, correct board ID, added TinyUSB
- `python/utils.py` — Replaced RTT/OpenOCD helpers with pyserial-based connection
- `python/capture.py` — Updated to use serial instead of socket
- `python/config.py` — Replaced RTT_PORT with SERIAL_BAUD
- `python/test_serial.py` — New quick-test script for verifying serial output
- `docs/V3.md` — New hardware reference document

**Critical lesson:**
The XIAO nRF52840 requires Seeed's custom PlatformIO platform (GitHub repo), `-DUSE_TINYUSB` flag, and `Adafruit TinyUSB Library`. Without these, USB Serial silently fails.

---

### 2026-06-26 — Transition Consistency Analysis (25 cycles)

**What was implemented:**
Exploratory analysis of transition consistency across 25 sit/stand cycles from participant "harshit".

**Script:** `python/analyze_transitions.py`

**Method:**
1. Extracted all 25 SIT_DOWN and 25 STAND_UP segments from the labeled CSV
2. Normalized each transition to 100 samples via linear interpolation
3. Generated overlay plots, mean±1σ curves, similarity heatmap, and reference curves
4. Computed summary statistics and outlier detection (Euclidean distance from centroid)

**Generated files (analysis/transition_overlays/):**
- `sit_down_overlay_xyz.html` — All 25 sit-down transitions overlaid
- `stand_up_overlay_xyz.html` — All 25 stand-up transitions overlaid
- `sit_down_mean.html` — Mean ± 1σ for sit-down
- `stand_up_mean.html` — Mean ± 1σ for stand-up
- `transition_similarity_heatmap.html` — Pairwise Euclidean distance
- `average_human_transition.html` — Reference mean curves (both transitions)
- `transition_statistics.md` — Full statistics report

**Key findings:**
- Sit-down: 25 transitions, avg 2.76s (range 1.68–3.68s, σ=0.47s)
- Stand-up: 25 transitions, avg 2.73s (range 1.62–3.32s, σ=0.34s)
- Peak magnitude ~11.2 m/s² for both transitions
- Outliers detected: Sit-down cycles 5 and 17 (not removed, only flagged)
- Stand-up transitions are more consistent (lower duration variance, no outliers)

**Observations:**
- Transitions are highly repeatable — overlay plots show tight clustering
- The Y-axis (vertical when worn) carries the strongest transition signal
- Stand-up transitions are slightly more consistent than sit-down
- Cycles 5 and 17 may have had hesitation or unusual movement

---

### 2026-06-29 â€” Transition Alignment Refactor for Timing vs Motion Research

**What was changed:**
- Refactored `analysis/transition_alignment/transition_alignment_analysis.py` to eliminate repeated similarity calculations.
- Kept all existing outputs intact: duration histograms, start-aligned overlays, landmark-aligned overlays, Euclidean heatmaps, summary CSV, and markdown reporting.
- Added stage-level timing logs and a runtime summary to the markdown report.
- Replaced exhaustive pairwise DTW with DTW-to-reference only.

**Why pairwise DTW was replaced:**
- Full NxN DTW was the dominant bottleneck.
- For this experiment, we do not need an all-to-all similarity graph.
- Comparing each transition against a representative reference still answers the research question: whether stand-up variability is mostly timing shift or a genuinely different movement pattern.

**Expected speedup:**
- Euclidean pairwise heatmaps are computed once and reused.
- DTW cost drops from O(N^2) comparisons to O(N) reference comparisons.
- With 25 transitions, this removes most of the expensive dynamic programming work.

**Why scientific validity is preserved:**
- The goal is interpretation, not clustering or classification.
- We only need to know whether alignment reduces variability and whether residual differences remain after timing correction.
- DTW-to-reference is sufficient to measure atypicality relative to a shared motion template for the current question.
