# Known Issues

## Open Issues

### ISSUE-001: Low window count from short sessions

- **Title:** Window extraction produces very few windows from short test sessions
- **Description:** The test capture (participant "1") contained only ~250 samples (5s of STANDING). With a 100-sample window and 50-sample step, only 1 window was extracted. This is expected behavior for short sessions but should be noted.
- **Priority:** Low
- **Status:** EXPECTED BEHAVIOR
- **Date Discovered:** 2026-06-26
- **Possible Cause:** Test session was only 1 partial cycle. Full 25-cycle sessions will produce hundreds of windows.
- **Resolution:** Not a bug. Full protocol sessions will yield sufficient windows.

---

### ISSUE-002: RTT address range may need adjustment per firmware build

- **Title:** RTT control block address (0x20000000) may not match all builds
- **Description:** OpenOCD searches for the SEGGER RTT control block starting at 0x20000000 with a 0x10000 range. If the firmware linker places the RTT block outside this range, connection will fail silently (no data received).
- **Priority:** Medium
- **Status:** OPEN
- **Date Discovered:** 2026-06-26
- **Possible Cause:** Different compiler optimizations or firmware size changes could shift RAM layout.
- **Resolution:** If no data appears, inspect the .map file for `_SEGGER_RTT` symbol address and adjust the `rtt setup` command in `utils.py`.

---

### ISSUE-003: No validation that firmware is running before capture starts

- **Title:** capture.py does not verify firmware is streaming before starting protocol
- **Description:** If the device is not powered, not flashed, or sensor init failed, the capture script will run the full protocol with zero samples and save an empty CSV.
- **Priority:** Medium
- **Status:** OPEN
- **Date Discovered:** 2026-06-26
- **Possible Cause:** No handshake between host and firmware. RTT connection succeeds (to OpenOCD) even if firmware isn't producing data.
- **Resolution:** Add a pre-flight check after RTT connect — wait for at least 10 samples in 2 seconds before starting the protocol. Warn and abort if no data arrives.

---

## Resolved Issues

(None yet)
