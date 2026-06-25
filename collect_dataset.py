import csv
import time
from pathlib import Path

import serial
import serial.tools.list_ports


STANDING_SECONDS = 60
SITTING_SECONDS = 60
BAUD_RATE = 115200
OUT_FILE = Path("standing_sitting_dataset.csv")


def choose_port() -> str:
    ports = list(serial.tools.list_ports.comports())
    if not ports:
        raise RuntimeError("No serial ports found.")
    if len(ports) == 1:
        return ports[0].device

    print("Available ports:")
    for i, port in enumerate(ports, start=1):
        print(f"{i}. {port.device} - {port.description}")

    choice = int(input("Select port number: ").strip())
    return ports[choice - 1].device


def parse_csv_line(line: str):
    parts = line.strip().split(",")
    if len(parts) != 5:
        return None
    try:
        return {
            "timestamp": int(parts[0]),
            "accX": float(parts[1]),
            "accY": float(parts[2]),
            "accZ": float(parts[3]),
            "angle": float(parts[4]),
        }
    except ValueError:
        return None


def main():
    port = choose_port()
    print(f"Using {port}")
    print(f"Capturing {STANDING_SECONDS}s standing + {SITTING_SECONDS}s sitting")
    input("Put the subject in standing posture and press Enter to start...")

    start = time.monotonic()
    rows = 0

    with serial.Serial(port, BAUD_RATE, timeout=1) as ser, OUT_FILE.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["timestamp", "accX", "accY", "accZ", "angle", "label"])
        writer.writeheader()

        while True:
            elapsed = time.monotonic() - start
            if elapsed >= STANDING_SECONDS + SITTING_SECONDS:
                break

            line = ser.readline().decode("utf-8", errors="ignore")
            if not line:
                continue

            row = parse_csv_line(line)
            if row is None:
                continue

            row["label"] = "standing" if elapsed < STANDING_SECONDS else "sitting"
            writer.writerow(row)
            rows += 1
            print(f"{rows:05d} {row['label']} angle={row['angle']:.2f}")

    print(f"Saved {rows} rows to {OUT_FILE.resolve()}")


if __name__ == "__main__":
    main()
