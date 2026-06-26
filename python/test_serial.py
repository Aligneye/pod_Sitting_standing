"""
test_serial.py — Quick test to verify firmware is streaming data over USB Serial.

Usage:
    python test_serial.py
    python test_serial.py --port COM5
    python test_serial.py --port COM5 --duration 5

Prints raw lines from the device for the given duration (default 5 seconds).
"""

import argparse
import time
import sys

import serial
import serial.tools.list_ports


def find_xiao_port():
    """Auto-detect the XIAO nRF52840 serial port."""
    ports = serial.tools.list_ports.comports()
    for p in ports:
        desc = (p.description or "").lower()
        vid = p.vid
        # Seeed XIAO nRF52840 shows as USB Serial Device or with VID 0x239A (Adafruit BSP)
        if vid == 0x239A or "nrf" in desc or "xiao" in desc or "serial" in desc:
            return p.device
    # Fallback: return the last port (often the most recently connected)
    if ports:
        return ports[-1].device
    return None


def main():
    parser = argparse.ArgumentParser(description="Test firmware serial output")
    parser.add_argument("--port", "-p", default=None, help="Serial port (e.g. COM5)")
    parser.add_argument("--baud", "-b", type=int, default=115200, help="Baud rate")
    parser.add_argument("--duration", "-d", type=float, default=5.0, help="Seconds to capture")
    args = parser.parse_args()

    port = args.port
    if not port:
        port = find_xiao_port()
        if not port:
            print("Error: No serial port found. Connect the XIAO and try again.")
            print("\nAvailable ports:")
            for p in serial.tools.list_ports.comports():
                print(f"  {p.device} — {p.description} (VID={p.vid}, PID={p.pid})")
            sys.exit(1)

    print(f"Opening {port} at {args.baud} baud...")
    try:
        ser = serial.Serial(port, args.baud, timeout=1)
    except serial.SerialException as e:
        print(f"Error: {e}")
        sys.exit(1)

    print(f"Listening for {args.duration}s...\n")
    start = time.time()
    line_count = 0

    try:
        while time.time() - start < args.duration:
            if ser.in_waiting:
                line = ser.readline().decode("utf-8", errors="ignore").strip()
                if line:
                    print(line)
                    line_count += 1
    except KeyboardInterrupt:
        pass
    finally:
        ser.close()

    elapsed = time.time() - start
    print(f"\n--- {line_count} lines in {elapsed:.1f}s ({line_count/elapsed:.1f} lines/sec) ---")

    if line_count == 0:
        print("\nNo data received. Check:")
        print("  1. Is the LIS3DH wired to D4 (SDA) and D5 (SCL)?")
        print("  2. Is the firmware uploaded? (re-upload after code change)")
        print("  3. Try pressing the reset button on the XIAO.")


if __name__ == "__main__":
    main()
