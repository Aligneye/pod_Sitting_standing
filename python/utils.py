"""
utils.py — Serial connection and parsing helpers.
"""

import sys
import time

import serial
import serial.tools.list_ports


def find_xiao_port():
    """Auto-detect the XIAO nRF52840 serial port."""
    ports = serial.tools.list_ports.comports()
    for p in ports:
        desc = (p.description or "").lower()
        vid = p.vid
        if vid == 0x239A or "nrf" in desc or "xiao" in desc:
            return p.device
    if ports:
        return ports[-1].device
    return None


def connect_serial(port=None, baud=115200, retries=5):
    """Connect to the device over USB serial. Returns a serial.Serial object."""
    if not port:
        port = find_xiao_port()
    if not port:
        print("Error: No serial port found. Connect the XIAO and try again.")
        print("\nAvailable ports:")
        for p in serial.tools.list_ports.comports():
            print(f"  {p.device} — {p.description}")
        sys.exit(1)

    for attempt in range(retries):
        try:
            ser = serial.Serial(port, baud, timeout=0.3)
            print(f"Connected to {port} at {baud} baud")
            return ser
        except serial.SerialException:
            if attempt < retries - 1:
                time.sleep(1)

    print(f"Error: Could not open {port}")
    sys.exit(1)


def read_serial_lines(ser):
    """Read available lines from serial. Returns list of complete lines."""
    lines = []
    while ser.in_waiting:
        try:
            raw = ser.readline()
            line = raw.decode("utf-8", errors="ignore").strip()
            if line:
                lines.append(line)
        except serial.SerialException:
            break
    return lines


def parse_csv_line(line):
    """Parse a firmware CSV line. Returns (timestamp_ms, acc_x, acc_y, acc_z) or None."""
    if not line or line.startswith("#") or line.startswith("timestamp") or line.startswith("BOOT"):
        return None
    parts = line.split(",")
    if len(parts) < 4:
        return None
    try:
        return int(parts[0]), float(parts[1]), float(parts[2]), float(parts[3])
    except ValueError:
        return None
