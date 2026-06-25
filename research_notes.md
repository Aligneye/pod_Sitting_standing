# Research-only dataset collection

This workspace now contains a standalone prototype for the data collection study.

## Output fields
- `timestamp`
- `accX`
- `accY`
- `accZ`
- `angle`
- `label`

## Capture protocol
- 60 seconds standing
- 60 seconds sitting
- Label is assigned by elapsed capture time

## Assumptions
- The device firmware prints one comma-separated sample per line
- The Python collector is responsible for saving rows to CSV
- The firmware in this workspace is intentionally minimal and independent from the original device project
