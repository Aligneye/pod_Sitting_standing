"""
capture.py — Interactive protocol-guided data capture via USB Serial.

Guides the participant through sit/stand cycles, labels data automatically,
and saves raw CSV + metadata JSON.

Usage:
    python capture.py
    python capture.py --cycles 30
    python capture.py --participant P02 --cycles 10
    python capture.py --port COM5
"""

import argparse
import csv
import json
import time
from datetime import datetime
from pathlib import Path

from config import (
    CSV_COLUMNS,
    DATASETS_METADATA,
    DATASETS_RAW,
    DEFAULT_CYCLES,
    FIRMWARE_VERSION,
    HOLD_DURATION_SEC,
    PHASE_ORDER,
    SAMPLING_RATE_HZ,
    TRANSITION_PHASES,
    WINDOW_OVERLAP,
    WINDOW_SIZE_SECONDS,
)
from utils import connect_serial, parse_csv_line, read_serial_lines


def beep():
    print("\a", end="", flush=True)


def drain_samples(ser, writer, label, count_ref):
    """Read all available serial data and write to CSV."""
    lines = read_serial_lines(ser)
    for line in lines:
        parsed = parse_csv_line(line)
        if parsed is None:
            continue
        ts, ax, ay, az = parsed
        writer.writerow([ts, ax, ay, az, label])
        count_ref[0] += 1


def run_hold_phase(ser, writer, label, duration, count_ref):
    """Timed hold phase — collect for exactly `duration` seconds."""
    start = time.time()
    while (time.time() - start) < duration:
        drain_samples(ser, writer, label, count_ref)
        remaining = duration - (time.time() - start)
        print(f"\r     {remaining:.0f}s remaining | {count_ref[0]} samples total", end="")
        time.sleep(0.01)
    print()


def run_transition_phase(ser, writer, label, count_ref):
    """Untimed transition — collect until participant presses ENTER."""
    import sys

    print("     Press ENTER when done.")
    if sys.platform == "win32":
        import msvcrt
        while True:
            drain_samples(ser, writer, label, count_ref)
            print(f"\r     Recording... {count_ref[0]} samples | Press ENTER when done", end="")
            if msvcrt.kbhit():
                key = msvcrt.getwch()
                if key in ("\r", "\n"):
                    break
            time.sleep(0.01)
    else:
        import select
        while True:
            drain_samples(ser, writer, label, count_ref)
            print(f"\r     Recording... {count_ref[0]} samples | Press ENTER when done", end="")
            ready, _, _ = select.select([sys.stdin], [], [], 0.01)
            if ready:
                sys.stdin.readline()
                break
    print()


def collect_session(ser, participant_id, session_id, cycles, output_dir, metadata_dir):
    """Run the full protocol and save CSV + metadata."""
    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_filename = f"{session_id}_{timestamp_str}.csv"
    csv_path = output_dir / csv_filename
    events = []

    sample_count = [0]
    session_start = time.time()

    with open(csv_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(CSV_COLUMNS)

        for cycle in range(1, cycles + 1):
            print(f"\n{'='*50}")
            print(f"  CYCLE {cycle} / {cycles}")
            print(f"{'='*50}")

            for phase in PHASE_ORDER:
                beep()

                if phase == "STANDING":
                    print(f"\n  >> STANDING — Stay standing naturally ({HOLD_DURATION_SEC}s)")
                elif phase == "SIT_DOWN":
                    print(f"\n  >> SIT DOWN — Sit down at your own pace")
                elif phase == "SITTING":
                    print(f"\n  >> SITTING — Stay seated naturally ({HOLD_DURATION_SEC}s)")
                elif phase == "STAND_UP":
                    print(f"\n  >> STAND UP — Stand up at your own pace")

                events.append({
                    "cycle": cycle,
                    "event": f"{phase}_START",
                    "wall_time_ms": int(time.time() * 1000),
                    "sample_index": sample_count[0],
                })

                if phase in TRANSITION_PHASES:
                    run_transition_phase(ser, writer, phase, sample_count)
                else:
                    run_hold_phase(ser, writer, phase, HOLD_DURATION_SEC, sample_count)

            print(f"\n  Cycle {cycle}/{cycles} complete. ({sample_count[0]} samples)")

    session_end = time.time()
    duration_sec = session_end - session_start

    metadata = {
        "participant_id": participant_id,
        "session_id": session_id,
        "sampling_rate_hz": SAMPLING_RATE_HZ,
        "window_size_seconds": WINDOW_SIZE_SECONDS,
        "window_overlap": WINDOW_OVERLAP,
        "date": datetime.now().strftime("%Y-%m-%d"),
        "time": datetime.now().strftime("%H:%M:%S"),
        "firmware_version": FIRMWARE_VERSION,
        "cycles": cycles,
        "total_samples": sample_count[0],
        "duration_seconds": round(duration_sec, 1),
        "csv_file": csv_filename,
        "events": events,
    }

    metadata_dir.mkdir(parents=True, exist_ok=True)
    meta_path = metadata_dir / f"{session_id}_{timestamp_str}.json"
    with open(meta_path, "w") as mf:
        json.dump(metadata, mf, indent=2)

    return csv_path, meta_path, sample_count[0], duration_sec


def print_summary(participant_id, cycles, sample_count, duration_sec, csv_path, meta_path):
    print(f"\n{'='*50}")
    print(f"  SESSION COMPLETE")
    print(f"{'='*50}")
    print(f"  Participant:     {participant_id}")
    print(f"  Cycles:          {cycles}")
    print(f"  Duration:        {int(duration_sec//60)}m {int(duration_sec%60)}s")
    print(f"  Samples:         {sample_count}")
    print(f"  Effective Rate:  {sample_count/duration_sec:.1f} Hz")
    print(f"  CSV Saved:       {csv_path}")
    print(f"  Metadata Saved:  {meta_path}")
    print(f"{'='*50}\n")


def main():
    parser = argparse.ArgumentParser(description="Interactive sit/stand data capture")
    parser.add_argument("--participant", default=None, help="Participant ID (e.g. P01)")
    parser.add_argument("--cycles", type=int, default=DEFAULT_CYCLES, help="Number of cycles")
    parser.add_argument("--port", default=None, help="Serial port (e.g. COM5). Auto-detects if omitted.")
    args = parser.parse_args()

    print("=" * 50)
    print("  SITTING / STANDING DATA COLLECTION")
    print("=" * 50)
    print()

    if args.participant:
        participant_id = args.participant
    else:
        participant_id = input("  Participant ID (e.g. P01): ").strip()
        if not participant_id:
            participant_id = "P01"

    participant_dir = DATASETS_RAW / participant_id
    participant_dir.mkdir(parents=True, exist_ok=True)
    existing = list(participant_dir.glob("*.csv"))
    session_num = len(existing) + 1
    session_id = f"{participant_id}_session_{session_num:03d}"

    print()
    print(f"  Session ID:       {session_id}")
    print(f"  Sampling Rate:    {SAMPLING_RATE_HZ} Hz")
    print(f"  Cycles:           {args.cycles}")
    print(f"  Window Length:    {WINDOW_SIZE_SECONDS}s")
    print(f"  Window Overlap:   {int(WINDOW_OVERLAP*100)}%")
    print()
    print("  Protocol per cycle:")
    print(f"    1. Stand still ({HOLD_DURATION_SEC}s)")
    print(f"    2. Sit down (at your pace)")
    print(f"    3. Sit still ({HOLD_DURATION_SEC}s)")
    print(f"    4. Stand up (at your pace)")
    print()
    input("  Press ENTER to begin...")

    ser = connect_serial(port=args.port)

    try:
        csv_path, meta_path, sample_count, duration_sec = collect_session(
            ser, participant_id, session_id, args.cycles, participant_dir, DATASETS_METADATA
        )
        print_summary(participant_id, args.cycles, sample_count, duration_sec, csv_path, meta_path)
    except KeyboardInterrupt:
        print("\n\n  Session interrupted by user.")
    finally:
        ser.close()


if __name__ == "__main__":
    main()
