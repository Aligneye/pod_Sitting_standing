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

### ISSUE-004: upload_hooks.py is now unused after board migration

- **Title:** upload_hooks.py remains in repo but is not referenced by platformio.ini
- **Description:** After migrating to XIAO nRF52840 BLE (USB-C upload), the custom OpenOCD upload script is no longer needed. The file remains for reference but could confuse future contributors.
- **Priority:** Low
- **Status:** OPEN
- **Date Discovered:** 2026-06-26
- **Possible Cause:** Board migration removed the `extra_scripts` directive.
- **Resolution:** Can be deleted or moved to `CONTEXT/` if no longer needed. Keeping for now in case V5 board is used again.

---

### ISSUE-005: RTT still requires debug probe despite USB-C availability

- **Title:** Data capture still requires CMSIS-DAP probe for RTT even though board has USB-C
- **Description:** The XIAO nRF52840 has native USB, so Serial output via USB-C is possible. Currently the firmware uses RTT which still requires a separate debug probe for data capture. This adds hardware complexity to the data collection setup.
- **Priority:** Medium
- **Status:** OPEN
- **Date Discovered:** 2026-06-26
- **Possible Cause:** Original design chose RTT because the nRF52832 had no USB. The nRF52840 does have USB.
- **Resolution:** Consider switching from RTT to USB Serial (`Serial.print`) in a future iteration. This would eliminate the need for a debug probe during data collection and simplify capture.py to use pyserial instead of OpenOCD TCP.

---

## Resolved Issues

(None yet)
