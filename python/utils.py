"""
utils.py — RTT connection, OpenOCD management, and parsing helpers.
"""

import socket
import subprocess
import sys
import time
from pathlib import Path


def find_openocd():
    pio_home = Path.home() / ".platformio"
    if sys.platform.startswith("win"):
        candidate = pio_home / "packages" / "tool-openocd" / "bin" / "openocd.exe"
    else:
        candidate = pio_home / "packages" / "tool-openocd" / "bin" / "openocd"
    if candidate.exists():
        return str(candidate)
    return "openocd"


def find_openocd_scripts():
    pio_home = Path.home() / ".platformio"
    scripts = pio_home / "packages" / "tool-openocd" / "openocd" / "scripts"
    if scripts.exists():
        return str(scripts)
    return None


def start_openocd(rtt_port=9090):
    openocd = find_openocd()
    scripts_dir = find_openocd_scripts()

    cmd = [openocd]
    if scripts_dir:
        cmd += ["-s", scripts_dir]
    cmd += [
        "-f", "interface/cmsis-dap.cfg",
        "-f", "target/nrf52.cfg",
        "-c", "init",
        "-c", 'rtt setup 0x20000000 0x10000 "SEGGER RTT"',
        "-c", "rtt start",
        "-c", f"rtt server start {rtt_port} 0",
    ]

    print(f"Starting OpenOCD (RTT on port {rtt_port})...")
    kwargs = {}
    if sys.platform == "win32":
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, **kwargs)
    time.sleep(2)

    if proc.poll() is not None:
        stderr = proc.stderr.read().decode(errors="ignore")
        print(f"OpenOCD failed to start:\n{stderr}")
        sys.exit(1)

    return proc


def connect_rtt(port=9090, retries=5):
    for attempt in range(retries):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect(("localhost", port))
            sock.settimeout(0.3)
            print(f"Connected to RTT on port {port}")
            return sock
        except ConnectionRefusedError:
            if attempt < retries - 1:
                time.sleep(1)
    print("Error: Could not connect to RTT server")
    sys.exit(1)


def read_rtt_lines(sock, buffer=""):
    """Read from socket, return (remaining_buffer, list_of_complete_lines)."""
    try:
        data = sock.recv(4096).decode("utf-8", errors="ignore")
    except socket.timeout:
        return buffer, []

    if not data:
        return buffer, []

    buffer += data
    lines = []
    while "\n" in buffer:
        line, buffer = buffer.split("\n", 1)
        lines.append(line.strip())
    return buffer, lines


def parse_csv_line(line):
    """Parse a firmware CSV line. Returns (timestamp_ms, acc_x, acc_y, acc_z) or None."""
    if not line or line.startswith("#") or line.startswith("timestamp"):
        return None
    parts = line.split(",")
    if len(parts) != 4:
        return None
    try:
        return int(parts[0]), float(parts[1]), float(parts[2]), float(parts[3])
    except ValueError:
        return None
