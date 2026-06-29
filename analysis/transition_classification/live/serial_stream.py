"""
Serial stream helpers for live inference.

This module is responsible only for getting samples off the wire. It does not
do any preprocessing or prediction.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Generator, List, Optional

import sys

import pandas as pd
import serial
import serial.tools.list_ports

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "python"))
from config import SERIAL_BAUD


@dataclass
class Sample:
    """One accelerometer reading from either serial or a replay CSV."""

    timestamp_ms: int
    acc_x: float
    acc_y: float
    acc_z: float


def find_port(port: Optional[str] = None) -> str:
    """Return the requested port or auto-detect a likely device port."""
    if port:
        return port

    for p in serial.tools.list_ports.comports():
        desc = (p.description or "").lower()
        if p.vid == 0x239A or "nrf" in desc or "xiao" in desc:
            return p.device

    raise RuntimeError("No serial port found.")


def available_ports() -> List[str]:
    """Return a readable list of serial ports currently visible to Windows."""
    ports = []
    for p in serial.tools.list_ports.comports():
        desc = p.description or "Unknown device"
        ports.append(f"{p.device} - {desc}")
    return ports


def format_available_ports() -> str:
    ports = available_ports()
    if not ports:
        return "No serial ports detected."
    return "\n".join(f"  {item}" for item in ports)


def iter_serial_samples(port: Optional[str] = None, baud: int = SERIAL_BAUD) -> Generator[Sample, None, None]:
    """Yield samples continuously from the live device."""
    device = find_port(port)
    try:
        ser = serial.Serial(device, baud, timeout=1)
    except serial.SerialException as exc:
        raise RuntimeError(
            f"Could not open serial port {device!r}.\n\n"
            f"Available ports:\n{format_available_ports()}\n\n"
            "Check that the board is plugged in, not already open in Serial Monitor, "
            "and that you passed the correct --port value."
        ) from exc

    with ser:
        while True:
            raw = ser.readline().decode("utf-8", errors="ignore").strip()
            if not raw or raw.startswith("#") or raw.startswith("timestamp"):
                continue
            parts = raw.split(",")
            if len(parts) < 4:
                continue
            try:
                yield Sample(
                    timestamp_ms=int(parts[0]),
                    acc_x=float(parts[1]),
                    acc_y=float(parts[2]),
                    acc_z=float(parts[3]),
                )
            except ValueError:
                continue


def iter_csv_samples(csv_path: Path, realtime: bool = True) -> Generator[Sample, None, None]:
    """Replay a recorded CSV at approximately real-time speed."""
    df = pd.read_csv(csv_path)
    if df.empty:
        return

    first_ts = int(df["timestamp_ms"].iloc[0])
    wall_start = time.perf_counter()
    for _, row in df.iterrows():
        if realtime and len(df) > 1:
            target_elapsed = (int(row["timestamp_ms"]) - first_ts) / 1000.0
            while (time.perf_counter() - wall_start) < target_elapsed:
                time.sleep(0.001)
        yield Sample(
            timestamp_ms=int(row["timestamp_ms"]),
            acc_x=float(row["acc_x"]),
            acc_y=float(row["acc_y"]),
            acc_z=float(row["acc_z"]),
        )
