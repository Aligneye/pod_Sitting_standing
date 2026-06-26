"""
config.py — Shared constants and paths for the data collection pipeline.
"""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

DATASETS_RAW = PROJECT_ROOT / "datasets" / "raw"
DATASETS_PROCESSED = PROJECT_ROOT / "datasets" / "processed"
DATASETS_WINDOWS = PROJECT_ROOT / "datasets" / "windows"
DATASETS_METADATA = PROJECT_ROOT / "datasets" / "metadata"
PLOTS_DIR = PROJECT_ROOT / "plots"

RTT_PORT = 9090

SAMPLING_RATE_HZ = 50

WINDOW_SIZE_SECONDS = 2.0
WINDOW_OVERLAP = 0.5

# Protocol phases in order (one cycle)
PHASE_ORDER = ["STANDING", "SIT_DOWN", "SITTING", "STAND_UP"]

# Timed phases: participant holds still for this many seconds
HOLD_DURATION_SEC = 5

# Untimed phases: these are transitions, participant moves at own pace
# We wait for user confirmation (ENTER key) instead of a timer
TRANSITION_PHASES = {"SIT_DOWN", "STAND_UP"}

DEFAULT_CYCLES = 25

FIRMWARE_VERSION = "research_v1_50hz"

CSV_COLUMNS = [
    "timestamp_ms",
    "acc_x",
    "acc_y",
    "acc_z",
    "activity_label",
]
