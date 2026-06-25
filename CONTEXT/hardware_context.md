# AlignEye Pod V5 — Hardware & Firmware Context Document

---

## 1. Device Overview

| Field | Value |
|-------|-------|
| MCU | Nordic nRF52832 (NRF52832_XXAA) |
| Board Configuration | `adafruit_feather_nrf52832` (custom PCB, pin mapping in `include/config.h`) |
| Framework | Arduino (Adafruit nRF52 BSP with Bluefruit library) |
| Device Name | `ALIGN_POD` |
| Device Model | `ALIGN_POD_V5` |
| Hardware Version | `POD_V5` |
| Firmware Version | `1.0.0` |
| PlatformIO Environment | `nrf52832_custom` |

**Source:** `platformio.ini`, `include/version.h`, `include/config.h`

---

## 2. Build Configuration

### platformio.ini (complete)

```ini
[env:nrf52832_custom]
platform = nordicnrf52
board = adafruit_feather_nrf52832
framework = arduino

; Upload via CMSIS-DAP / DAPLink / J-Link OB DAPLink
upload_protocol = custom
extra_scripts = upload_hooks.py

debug_tool = cmsis-dap

monitor_speed = 115200

build_flags =
  -I include
  -DNRF52832_XXAA
  -DDEBUG_LOGGING
  -g3

lib_deps =
  koendv/RTT Stream@^1.3.0
  adafruit/Adafruit LIS3DH
  adafruit/Adafruit Unified Sensor
  mathertel/OneButton@^2.5.0
```

### Build Flags

| Flag | Purpose |
|------|---------|
| `-I include` | Adds `include/` directory to include path |
| `-DNRF52832_XXAA` | Defines the MCU variant for Nordic SDK headers |
| `-DDEBUG_LOGGING` | Enables debug print macros (RTT logging) |
| `-g3` | Maximum debug information for GDB |

### Upload Configuration

- **Protocol:** Custom (via `upload_hooks.py`)
- **Tool:** OpenOCD with CMSIS-DAP interface
- **Firmware load address:** `0x26000` (Adafruit bootloader offset)
- **Signature load address:** `0x7F000`
- **Target config:** `target/nrf52.cfg`
- **Interface config:** `interface/cmsis-dap.cfg`

### Debug Configuration

- **Tool:** `cmsis-dap`
- **Monitor baud:** 115200

### Custom Scripts

- `upload_hooks.py` — Custom upload script that uses OpenOCD to flash firmware.bin at 0x26000 and firmware_signature.bin at 0x7F000 via CMSIS-DAP.

### Compile Definitions (conditional, set in `config.h`)

| Define | Default | Purpose |
|--------|---------|---------|
| `ALIGN_RTT_JSON_LOG` | 0 | Log JSON packets to RTT |
| `ALIGN_RTT_BLE_RX_LOG` | 0 | Log BLE RX packets to RTT |
| `ALIGN_RTT_STATUS_LOG` | 0 | Periodic status output to RTT |
| `ALIGN_RTT_STATUS_INTERVAL_MS` | 1000 | Status log interval |
| `ALIGN_RTT_SENSOR_LOG` | 0 | Log sensor data to RTT |
| `RESEARCH_CAPTURE` | 0 | Enable CSV research capture mode (50Hz raw+angle to RTT) |
| `ALIGN_RTT_CALIB_VERBOSE` | 0 | Verbose calibration debug output |
| `ALIGN_RTT_THERAPY_VERBOSE` | 0 | Verbose therapy debug output |
| `ALIGN_RTT_SESSION_VERBOSE` | 0 | Verbose session debug output |

**Source:** `platformio.ini`, `upload_hooks.py`, `include/config.h`

---

## 3. External Dependencies

| Library | Version | Purpose | Used In | Configuration |
|---------|---------|---------|---------|---------------|
| `RTT Stream` (koendv) | ^1.3.0 | SEGGER RTT output stream (replaces Serial over USB) | All files via `RTTStream rtt` global | Default RTT channel 0 |
| `Adafruit LIS3DH` | Latest | LIS3DH accelerometer driver over I2C | `src/training.cpp` | Address: 0x18 or 0x19, Range: ±2G, ODR: 100Hz |
| `Adafruit Unified Sensor` | Latest | Sensor abstraction layer (dependency of LIS3DH) | `src/training.cpp` | N/A |
| `OneButton` (mathertel) | ^2.5.0 | Button debouncing and multi-click detection | `src/button.cpp` | Debounce: 50ms, Click gap: 400ms, Hold: 1000ms |
| `Bluefruit` (Adafruit nRF52 BSP) | Built-in | BLE stack (GAP, GATT, advertising, bonding) | `src/bluetooth.cpp` | Peripheral mode, BANDWIDTH_MAX, TX power: +4 dBm |
| `Adafruit LittleFS / InternalFileSystem` | Built-in | Internal flash filesystem | `src/storage.cpp`, `src/bluetooth.cpp`, `src/session_stats.cpp`, `src/device_time.cpp`, `src/session_log.cpp` | Used for profile store, session logs, device time persistence |

**Source:** `platformio.ini`, `src/training.cpp`, `src/bluetooth.cpp`, `src/button.cpp`

---

## 4. Hardware Pin Mapping

| GPIO | Symbolic Name | Purpose |
|------|---------------|---------|
| P0.11 | `PIN_BUTTON` | Tactile push button (active LOW, internal pull-up) |
| P0.13 | `PIN_LED_RED` | RGB LED — Red channel (active-LOW / common-anode) |
| P0.14 | `PIN_LED_GREEN` | RGB LED — Green channel (active-LOW / common-anode) |
| P0.15 | `PIN_LED_BLUE` | RGB LED — Blue channel (active-LOW / common-anode) |
| P0.17 | `PIN_MOTOR` | Vibration motor PWM output |
| P0.26 | `PIN_I2C_SDA` | I2C SDA — LIS3DH accelerometer |
| P0.27 | `PIN_I2C_SCL` | I2C SCL — LIS3DH accelerometer |
| P0.02 (AIN0) | `PIN_BATTERY_ADC` | Battery voltage sense (ADC input via voltage divider) |
| P0.21 | — | Hardware reset (not used in firmware) |

### Additional Peripherals

- **BLE Radio:** Internal nRF52832 radio, no external BLE hardware
- **Interrupt Pins:** Not Found (LIS3DH interrupts not wired/used; sensor is polled)
- **Crystal:** 32.768 kHz LFXO used for RTC2 timekeeping

**Source:** `include/config.h`, `src/training.cpp` (I2C init), `src/bluetooth.cpp` (LED init)

---

## 5. Accelerometer System

| Parameter | Value |
|-----------|-------|
| Sensor Model | ST LIS3DH (3-axis MEMS accelerometer) |
| Interface | I2C (address 0x18 primary, 0x19 fallback) |
| Range | ±2G (`LIS3DH_RANGE_2_G`) |
| Output Data Rate | 100 Hz (`LIS3DH_DATARATE_100_HZ`) |
| Sensitivity | ~1 mg/digit at ±2G (library-configured, output in m/s²) |
| Filtering | First-order IIR low-pass filter, alpha = 0.1 |
| Sampling Frequency | 100 Hz (10ms interval enforced in software) |
| Data Units | m/s² (from `Adafruit_Sensor` unified event) |

### Initialization Code

Located in `src/training.cpp:366-390` (`initPostureSensor()`):

1. I2C bus recovery (toggle SCL to unstick SDA)
2. `Wire.setPins(PIN_I2C_SDA, PIN_I2C_SCL)` + `Wire.begin()`
3. Try `lis.begin(0x18)` then `lis.begin(0x19)`
4. Up to 5 attempts with 200ms retry delay
5. Set range to ±2G, data rate to 100Hz
6. Load stored calibration

### Power Management

- `sleepPostureSensor()` → sets data rate to `LIS3DH_DATARATE_POWERDOWN`
- `wakePostureSensor()` → sets data rate back to `LIS3DH_DATARATE_100_HZ`

### Sensor Failure Detection

If all three axes read exactly 0.0, the sensor is considered disconnected. The firmware marks `sensorInitialized = false` and will attempt re-initialization every 5 seconds.

**Source:** `src/training.cpp`

---

## 6. Signal Processing Pipeline

```
Raw LIS3DH Event (m/s²)
    │
    ├── Step Count Processing (magnitude-based, high-pass filter)
    │
    ▼
Low-Pass Filter (IIR, α=0.1)
    │   g_fx = 0.1 * rawX + 0.9 * g_fx
    │   g_fy = 0.1 * rawY + 0.9 * g_fy
    │   g_fz = 0.1 * rawZ + 0.9 * g_fz
    │
    ▼
Motion Detection (delta-based)
    │   motionStrength = sqrt(dx² + dy² + dz²)
    │   _moving = (motionStrength > 2.0)
    │
    ▼
Posture Angle Calculation (computePostureAngle)
    │   Uses active calibration profile reference vector
    │
    ▼
Direction Classification
    │   FORWARD (angle > 20°) | BACKWARD (< -20°) | STRAIGHT
    │
    ▼
Bad Posture Detection
    │   BAD if angle > kBadPostureDeg (default 30°)
    │   GOOD after 100ms stable below threshold
    │
    ▼
Motor Feedback (if training mode active)
```

### Filter Equations

**Low-Pass Filter (IIR first-order):**
```
filtered[n] = α * raw[n] + (1 - α) * filtered[n-1]
α = 0.1 (kLpfAlpha)
```

**Seeding:** On first sample (or after re-init), filter is seeded with raw value directly.

### Constants

| Constant | Value | Purpose |
|----------|-------|---------|
| `kLpfAlpha` | 0.1 | Low-pass filter smoothing factor |
| `kMotionThreshold` | 2.0 m/s² | Motion detection threshold |
| `kDirectionDeg` | 20.0° | Direction classification threshold |
| `kBadPostureDeg` | 30.0° (configurable via BLE) | Bad posture angle threshold |
| `kAngleClampDeg` | 90.0° | Maximum angle clamp |
| `kDefaultOriginY` | 6.75 m/s² | Default calibration Y reference |
| `kDefaultOriginZ` | 6.75 m/s² | Default calibration Z reference |
| `kNearZero` | 0.1 | Minimum valid calibration magnitude |
| `kGoodDebounceMs` | 100 ms | Good posture debounce time |

### Posture Angle Calculation Logic

Located in `src/training.cpp:268-328` (`computePostureAngle()`):

1. **Get reference vector (R)** from active calibration profile (refX, refY, refZ)
2. **Normalize R:** `V = R / |R|`
3. **Normalize current filtered vector (C):** `A = C / |C|`
4. **Dot product:** `D = A · V` (cosine similarity)
5. **Perpendicular depth:** `pz = az - D * vz`
6. **Sagittal plane isolation:** `a_d = pz / sqrt(1 - vz²)` (handles non-vertical reference)
7. **Angle:** `atan2(a_d, D) * 180/π`
8. **Clamp** to ±90°

### Relevant Source Files

| File | Role |
|------|------|
| `src/training.cpp` | Sensor init, sampling, filtering, angle calculation, motor feedback |
| `include/training.h` | Public API and extern declarations |
| `src/calibration.cpp` | Calibration sampling and validation |
| `src/orientation_profiles.cpp` | Profile management and origin setting |

---

## 7. Orientation / Calibration System

### Profile Structure

```c
struct CalibrationProfile {     // aka OrientationProfile
    uint32_t id;                // Unique profile ID (auto-incrementing)
    char name[24];              // Human-readable name
    float refX;                 // Reference X acceleration (m/s²)
    float refY;                 // Reference Y acceleration (m/s²)
    float refZ;                 // Reference Z acceleration (m/s²)
    uint32_t createdAtEpoch;    // Creation timestamp (epoch seconds)
    uint16_t sampleCount;       // Number of samples used
    float stabilityScore;       // Quality/stability metric (0-100)
    uint8_t valid;              // 1 = valid profile
    uint8_t reserved[3];        // Padding
};
```

### Storage Format

**Primary:** LittleFS file (`/profiles.dat`) via `ProfileStore` struct:
```c
struct ProfileStore {
    uint32_t magic;              // 0x50524631 ("PRF1")
    uint8_t  profileCount;
    int8_t   activeProfileIndex;
    uint8_t  reserved[2];
    OrientationProfile profiles[8];
};
```

**Fallback:** Raw flash page at `0x00073000` via `PersistedSettings` struct (NVMC direct write).

**Maximum profiles:** 8

### Active Profile Selection

- Stored as index in `reserved2[0]` of PersistedSettings (1-indexed, 0 = no active)
- Runtime: tracked by `s_activeProfileId` (uint32_t ID)
- Selection applies reference vector via `setPostureOrigin3D(refX, refY, refZ)`

### Default Profile

- Stored as `defaultProfileId` in settings
- Selected when no active profile is set or active is deleted
- Falls back to `Y_ORIGIN=6.75, Z_ORIGIN=6.75` if no profiles exist

### Calibration Workflow

1. **Pre-checks** (`startCalibration()` in `src/calibration.cpp:456-506`):
   - Device must be BLE-connected
   - Sensor must be initialized
   - Battery must be >= 10%
   - Motor must not be active
   - Device must not be moving
2. **GET_READY phase** (3 seconds): User gets into position, haptic start pulse (150 duty, 150ms)
3. **HOLD_STILL phase** (5 seconds): Sampling at 50ms intervals (20 Hz calibration rate)
   - Samples stored in `samplesX[200]`, `samplesY[200]`, `samplesZ[200]`
   - Early failure check at 40+ samples: if stdDev > 1.75 on any axis → fail
4. **Final validation:**
   - Compute mean and stdDev for all samples
   - Reject if stdDev > 1.0 on any axis
   - Outlier rejection: discard samples outside mean ± 2σ
   - Require >= 70 valid samples
   - Compute quality score (0-100)
   - Reject if quality < 50
5. **Post-calibration validation** (5-10 seconds): Monitor angle; if > ±5° → delete profile
6. **Success:** Profile saved, haptic pulse (150 duty, 125ms)
7. **Failure:** Haptic pulse (150 duty, 500ms)

### Calibration Timing Constants

| Constant | Value |
|----------|-------|
| `CALIB_GET_READY_MS` | 3000 ms |
| `CALIB_HOLD_MS` | 5000 ms |
| `CALIB_TOTAL_MS` | 8000 ms |
| `kSampleIntervalMs` | 50 ms |
| `kMaxCalibrationSamples` | 200 |
| `MIN_VALID_SAMPLES` | 70 |
| `kEarlyFailMinSamples` | 40 |
| `kFinalStdDevLimit` | 1.0 |
| `kEarlyFailStdDevLimit` | 1.75 |

### Default Calibration Values

- `Y_ORIGIN = 6.75` m/s² (approximately gravity projected on Y axis at ~45° tilt)
- `Z_ORIGIN = 6.75` m/s²

### Commands Related to Calibration (BLE)

| Command | Action |
|---------|--------|
| `CALIBRATE=START` | Request calibration start |
| `CALIBRATE=CANCEL` | Cancel in-progress calibration |
| `ACTION=CALIBRATE` | Start calibration (alternative) |
| `ACTION=CALIBRATE_CANCEL` | Cancel (alternative) |
| `{"cmd":"CALIBRATE_START","slot":"auto","name":"..."}` | JSON: start calibration with name |
| `{"cmd":"CALIBRATE_CANCEL"}` | JSON: cancel calibration |
| Button long press (1s hold) | Start calibration |

**Source:** `src/calibration.cpp`, `src/orientation_profiles.cpp`, `src/storage.cpp`, `include/calibration.h`

---

## 8. BLE Architecture

### Device Configuration

| Parameter | Value |
|-----------|-------|
| Device Name | `"align pod"` (`BLE_DEVICE_NAME`) |
| TX Power | +4 dBm |
| Bandwidth | `BANDWIDTH_MAX` |
| Advertising Interval | 32-244 (20ms fast / 152.5ms slow) |
| Fast Timeout | 30 seconds |
| Advertising Duration | Forever (0) |
| Security | Encrypted, no MITM (`SECMODE_ENC_NO_MITM`) |
| Max Characteristic Length | 512 bytes |
| Pairing | Persistent bond stored in `/ble_pair.dat` |

### Services & Characteristics

| UUID | Type | Properties |
|------|------|------------|
| `4fafc201-1fb5-459e-8fcc-c5c9c331914b` | Service | Primary |
| `beb5483e-36e1-4688-b7f5-ea07361b26a8` | Characteristic | NOTIFY, READ, WRITE, WRITE_WO_RESP |

### Telemetry Packets (Device → App)

| Type (`t`) | Description | Frequency |
|------------|-------------|-----------|
| `"T"` | Telemetry: mode, sub_mode, profile_id, profile name, battery | Every 5s or on change |
| `"L"` | Live posture: profile_id, angle, posture string | Every 150ms when connected |
| `"C"` | Calibration status: phase, result, elapsed/total | During calibration events |
| `"P"` | Profile list (JSON array) | On request |
| `"D"` | DFU status | On DFU arm |
| `"V"` | Device version info | On request |
| `"INFO"` | Device info (fw, hw, serial, protocol, max_profiles) | On request |
| `"ACK"` | Command acknowledgement (seq, cmd, ok, error) | After JSON commands |
| `"S"` | RTT status (mode, profile, angle, posture, battery, steps) | RTT only (1s interval) |

### BLE Commands (App → Device)

#### Key=Value Format (semicolon-separated)

| Key | Values | Action |
|-----|--------|--------|
| `MODE` | `TRACKING`, `TRAINING`, `POSTURE`, `THERAPY` | Switch device mode |
| `POSTURE_TIMING` | `INSTANT`, `DELAYED`, `AUTOMATIC` | Set training alert style |
| `THERAPY_DURATION_MIN` | `10`, `20`, `30` | Set therapy duration |
| `THERAPY_INTENSITY` | `1`, `2`, `3` | Set therapy motor intensity |
| `DIFFICULTY_DEG` | `5`-`60` | Set bad posture threshold angle |
| `PROFILE` | index (1-based), name, `CLEAR`, `RESET`, `DEFAULT` | Select/manage profile |
| `CALIBRATE` / `CALIBRATION` | `START`, `CANCEL` | Calibration control |
| `ACTION` | `CALIBRATE`, `CALIBRATE_CANCEL`, `ENTER_DFU`, `OTA_DFU`, `DFU`, `DEVICE_INFO`, `GET_VERSION`, `VERSION`, `GET_DEVICE_INFO`, `PROFILE_CLEAR`, `CLEAR_PROFILES`, `FACTORY_RESET` | Device actions |
| `TIME` | epoch seconds | Time sync |
| `TZ` | offset seconds | Timezone offset |
| `CMD` | `GET_PROFILES`, `CALIBRATE_CANCEL`, `CALIBRATE_START` | Named commands |

#### JSON Format

| Command (`cmd`) | Parameters | Response |
|-----------------|------------|----------|
| `GET_PROFILES` | — | Profile list packet |
| `CALIBRATE_START` | `slot:"auto"`, `name:"..."` | ACK + calibration status |
| `CALIBRATE_CANCEL` | — | ACK |
| `PROFILE_SELECT` | `id:<uint32>` | ACK |
| `PROFILE_SET_DEFAULT` | `id:<uint32>` | ACK |
| `PROFILE_RENAME` | `id:<uint32>`, `name:"..."` | ACK |
| `PROFILE_DELETE` | `id:<uint32>` | ACK |
| `PROFILE_CLEAR_ALL` | — | ACK |
| `GET_DEVICE_INFO` | — | ACK + INFO packet |
| `FACTORY_RESET` | — | ACK + device reset |

**Source:** `src/bluetooth.cpp`, `include/config.h`

---

## 9. Battery Monitoring System

### ADC Configuration

| Parameter | Value |
|-----------|-------|
| ADC Pin | `PIN_BATTERY_ADC` = A0 (P0.02 / AIN0) |
| Reference | Internal 3.0V (`AR_INTERNAL_3_0`) |
| Resolution | 12-bit (4096 levels) |
| Averaging | 16 samples per reading |
| Inter-sample delay | 2ms |
| Read frequency | Every 5 seconds (in `bluetoothLoop`) |

### Voltage Divider

- **Divider ratio:** 2:1 (battery voltage = sense voltage × 2)
- **Formula:** `senseMillivolts = rawAdc * 3000 / 4095`
- **Battery voltage:** `batteryMillivolts = senseMillivolts * 2`

### Conversion Formula

```
rawAdc (12-bit) → senseMillivolts = rawAdc * 3000 / 4095
                → batteryMillivolts = senseMillivolts * 2
                → voltage (float) = batteryMillivolts / 1000.0
```

### Battery Percentage Calculation (Lookup Table)

```
>= 4.15V → 100%
>= 4.05V →  90%
>= 3.95V →  80%
>= 3.87V →  70%
>= 3.80V →  60%
>= 3.74V →  50%
>= 3.68V →  40%
>= 3.60V →  30%
>= 3.50V →  20%
>= 3.40V →  10%
<  3.40V →   0%
```

### Update Frequency

- Battery ADC read: every 5000ms (guarded in `updateBatteryReading()`)
- Percentage reported in BLE telemetry: every 5s or on change

**Source:** `src/BatteryMonitor.cpp`, `include/BatteryMonitor.h`, `src/bluetooth.cpp`

---

## 10. RGB LED System

### Pin Assignments

| Pin | GPIO | Function |
|-----|------|----------|
| `PIN_LED_RED` | P0.13 | Red channel |
| `PIN_LED_GREEN` | P0.14 | Green channel |
| `PIN_LED_BLUE` | P0.15 | Blue channel |

### Active-Low Behavior (Common Anode)

The LEDs are driven **active-LOW** (common anode configuration):
```c
analogWrite(PIN_LED_RED, 255 - red);     // 255 = OFF, 0 = full ON
analogWrite(PIN_LED_GREEN, 255 - green);
analogWrite(PIN_LED_BLUE, 255 - blue);
```

### Status Indications

| Condition | LED Behavior |
|-----------|--------------|
| Battery >= 67% | Green (solid or pulse) |
| Battery 34-66% | Yellow (Red + Green) |
| Battery < 34% | Red |
| BLE Connected | LED turned off |
| Battery status blink | 5 pulses at 1Hz, brightness ramps up/down per cycle |

### Battery Indication Logic

- Triggered by `bluetoothRequestBatteryStatusBlink()` (on mode transitions, button events)
- 5 blink cycles, 1000ms period each
- Brightness follows triangle wave (ramp up first half, ramp down second half)
- Color determined by battery percentage thresholds (67%/34%)

**Source:** `src/bluetooth.cpp:128-228`

---

## 11. Button System

### Library

`OneButton` by Mathertel (v2.5.0+)

### Configuration

| Parameter | Value |
|-----------|-------|
| Pin | `PIN_BUTTON` (P0.11) |
| Active Level | LOW |
| Internal Pull-up | Enabled |
| Debounce | 50ms (`DEBOUNCE_MS`) |
| Click Gap | 400ms (`DOUBLE_CLICK_GAP_MS`) |
| Long Press | 1000ms (`HOLD_MS`) |

### Actions

| Gesture | Action |
|---------|--------|
| **Single Press** | Haptic feedback (130 duty, 70ms) |
| **Single Click** | Cycle modes: Training → Therapy → OFF → Training |
| **Double Click (Training)** | Cycle training sub-mode: Instant → Delayed → No Alerts |
| **Double Click (Therapy)** | Stop current therapy + cycle duration: 10min → 20min → 30min |
| **Double Click (OFF)** | Enter OTA DFU bootloader |
| **Triple Click (OFF)** | Unlock BLE for re-pairing (clear bonds) |
| **Long Press (1s)** | Start calibration (if not in OFF mode) |

### Calibration Interaction

All button clicks during active calibration cancel the calibration and return to Training mode.

**Source:** `src/button.cpp`, `include/button.h`, `include/config.h`

---

## 12. Timing Architecture

### Main Loop Frequency

The main `loop()` runs as fast as possible (no explicit delay). Effective rate depends on BLE stack and sensor polling.

### Update Frequencies

| Subsystem | Frequency / Interval | Source |
|-----------|---------------------|--------|
| Sensor sampling (accelerometer) | 100 Hz (10ms) | `src/training.cpp:137` |
| Low-pass filter update | 100 Hz (with each sample) | `src/training.cpp:177-186` |
| Posture angle update | 100 Hz (with each sample) | `src/training.cpp:392-457` |
| BLE Live packet (`"L"`) | ~6.7 Hz (every 150ms) | `src/bluetooth.cpp:947` |
| BLE Telemetry packet (`"T"`) | Every 5000ms or on change | `src/bluetooth.cpp:975` |
| Battery ADC reading | Every 5000ms | `src/bluetooth.cpp:182` |
| Calibration sampling | 20 Hz (50ms intervals) | `src/calibration.cpp:23` |
| Research CSV capture | 50 Hz (20ms intervals) | `src/training.cpp:462` |
| Step count processing | 100 Hz (with each accel sample) | `src/training.cpp:164-165` |
| Device time auto-persist | Every 5 minutes | `src/device_time.cpp:26-27` |
| Session stats promotion | After 30 seconds | `src/session_stats.cpp:33` |
| Motor update | Every loop iteration | `src/main.cpp:47` |
| Button tick | Every loop iteration | `src/main.cpp:45` |
| RTT status log | Every 1000ms (if enabled) | `src/bluetooth.cpp:1033` |
| RTT sensor log | Every 1000ms (if enabled) | `src/training.cpp:485` |

### Therapy Timing Logic

| Parameter | Value |
|-----------|-------|
| Available durations | 10min, 20min, 30min |
| Pattern duration | 120000ms (2 minutes per pattern) |
| Pattern count | duration / 2min (e.g., 5 patterns for 10min) |
| Session promotion | 30 seconds minimum to be saved |
| Tick logging | Every 1000ms |

### Training Motor Feedback Timing

| Alert Style | Delay Before Motor | Motor Pattern |
|-------------|-------------------|---------------|
| Instant | 200ms sustained bad posture | 500ms on/off toggle at VIB_INTENSITY_MAX |
| Delayed | 5000ms sustained bad posture | 500ms on/off toggle at VIB_INTENSITY_MAX |
| No Alerts | N/A | Motor always off |
| Grace period | 1000ms after training start | Motor suppressed |

**Source:** `src/main.cpp`, `src/training.cpp`, `src/bluetooth.cpp`, `src/calibration.cpp`, `src/therapy.cpp`, `src/session_stats.cpp`

---

## 13. File Dependency Map

```
main.cpp
├── config.h ─────────── Pin definitions, timing constants, BLE UUIDs, enums
├── storage.h ────────── Flash persistence (NVMC + LittleFS)
│   └── calibration.h ── Profile struct definitions
├── button.h ─────────── Mode management, state machine
│   └── (uses motor.h, bluetooth.h, calibration.h, therapy.h, training.h)
├── therapy.h ────────── Vibration therapy patterns + session
│   └── (uses motor.h, button.h, calibration.h, session_stats.h)
├── training.h ───────── Accelerometer, filtering, posture angle
│   └── (uses Adafruit_LIS3DH, calibration.h, motor.h, step_count.h, storage.h)
├── calibration.h ────── Calibration state machine + profile operations
│   └── (uses training.h, motor.h, bluetooth.h, storage.h)
├── bluetooth.h ──────── BLE stack, telemetry, command parsing
│   └── (uses calibration.h, therapy.h, button.h, training.h, motor.h,
│         storage.h, device_time.h, session_stats.h, BatteryMonitor.h, version.h)
├── device_time.h ────── RTC2-based epoch timekeeping
├── motor.h ──────────── PWM motor control with override system
├── session_stats.h ──── Training/therapy session tracking
│   └── (uses device_time.h, therapy.h, session_log.h, bluetooth.h)
├── monitor_log.h ────── RTT logging helpers (logPacket, logEvent)
└── (implicit)
    ├── step_count.h ─── Pedometer algorithm
    ├── session_log.h ── Session persistence to LittleFS
    ├── BatteryMonitor.h ── Battery ADC driver
    └── version.h ────── FW/HW version strings
```

### Module Interaction Summary

```
                    ┌──────────────┐
                    │   main.cpp   │
                    └──────┬───────┘
         ┌─────────────────┼─────────────────┐
         │                 │                 │
    ┌────▼────┐     ┌─────▼─────┐     ┌────▼────┐
    │ button  │     │ training  │     │bluetooth│
    └────┬────┘     └─────┬─────┘     └────┬────┘
         │                │                 │
         │         ┌──────┼──────┐          │
         │         │      │      │          │
    ┌────▼────┐ ┌──▼──┐ ┌▼────┐ │    ┌─────▼─────┐
    │ therapy │ │motor│ │step │ │    │  battery  │
    └─────────┘ └─────┘ │count│ │    │  monitor  │
                         └─────┘ │    └───────────┘
                                 │
                    ┌────────────▼────────────┐
                    │      calibration        │
                    │  + orientation_profiles  │
                    └────────────┬────────────┘
                                │
                    ┌───────────▼───────────┐
                    │       storage         │
                    │  (NVMC + LittleFS)    │
                    └──────────────────────┘
```

**Source:** All `#include` directives across the project

---

## 14. Experimental ML Reuse

### Components Useful For Sitting/Standing ML Prototype

---

#### 1. Accelerometer Acquisition

| Item | Detail |
|------|--------|
| Source File | `src/training.cpp` |
| Functions | `initPostureSensor()`, `trainingIngestAccelSample()`, `wakePostureSensor()`, `sleepPostureSensor()`, `recoverI2CBus()` |
| Dependencies | `Adafruit_LIS3DH`, `Adafruit_Sensor`, `Wire.h`, `config.h` (I2C pins) |
| Output | Raw acceleration in m/s² via `rawX`, `rawY`, `rawZ` globals |
| Rate | 100 Hz |
| Notes | Includes I2C bus recovery, sensor failure detection, auto-retry |

---

#### 2. Filtering

| Item | Detail |
|------|--------|
| Source File | `src/training.cpp` |
| Functions | Inline within `trainingIngestAccelSample()` (lines 177-186) |
| Dependencies | None (pure math) |
| Output | Filtered values `g_fx`, `g_fy`, `g_fz` |
| Parameters | `kLpfAlpha = 0.1` |
| Notes | First-order IIR low-pass; seeded on first sample |

---

#### 3. Calibration

| Item | Detail |
|------|--------|
| Source File | `src/calibration.cpp`, `src/orientation_profiles.cpp` |
| Functions | `startCalibration()`, `handleCalibration()`, `calibrationSuccess()`, `calibrationFail()`, `calculateCalibrationStats()`, `addCalibrationProfile()`, `selectCalibrationProfileById()`, `setPostureOrigin3D()` |
| Dependencies | `motor.h` (haptic feedback), `storage.h` (persistence), `training.h` (sensor access), `bluetooth.h` (BLE notifications) |
| Output | Reference vector (refX, refY, refZ) stored in profile |
| Notes | For ML prototype, the statistical validation (mean, stdDev, outlier rejection) is reusable for reference pose capture |

---

#### 4. Angle Calculation

| Item | Detail |
|------|--------|
| Source File | `src/training.cpp` |
| Functions | `computePostureAngle()` (lines 268-328), `updatePostureAngle()` |
| Dependencies | Active profile reference vector, `math.h` (`atan2f`, `sqrtf`) |
| Output | `currentAngle` (float, degrees, signed) |
| Notes | The algorithm handles arbitrary reference orientations via dot-product + sagittal-plane projection. Directly applicable to sitting/standing posture classification as a feature input. |

---

#### 5. BLE Streaming

| Item | Detail |
|------|--------|
| Source File | `src/bluetooth.cpp` |
| Functions | `bluetoothSetup()`, `bluetoothLoop()`, `sendBlePacket()` |
| Dependencies | Bluefruit library (Adafruit nRF52 BSP), `config.h` (UUIDs) |
| Output | JSON packets over single GATT characteristic |
| Notes | For ML prototype, reuse the BLE setup + `sendBlePacket()` infrastructure to stream raw/processed sensor data to a phone or laptop for model training data collection |

---

#### 6. Timing Utilities

| Item | Detail |
|------|--------|
| Source File | `src/device_time.cpp` |
| Functions | `initDeviceTime()`, `setDeviceTime()`, `getDeviceTime()`, `getDeviceUptimeSeconds()`, `maintainDeviceTime()`, `formatEpochISO()` |
| Dependencies | nRF52 RTC2 peripheral, LittleFS (for persistence) |
| Output | Epoch timestamps, uptime tracking |
| Notes | Essential for timestamping ML training data captures |

---

#### 7. Research Capture Mode (Ready-Made Data Logger)

| Item | Detail |
|------|--------|
| Source File | `src/training.cpp` |
| Functions | `researchCaptureCsvLog()` (lines 459-481) |
| Dependencies | RTT Stream, `RESEARCH_CAPTURE` build flag |
| Output | CSV over RTT: `timestamp_ms, rawX, rawY, rawZ, angle` at 50Hz |
| Notes | Already built for ML data capture. Enable with `-DRESEARCH_CAPTURE=1` in build_flags. Output via SEGGER RTT to host. |

---

#### 8. Step Count (Motion Feature)

| Item | Detail |
|------|--------|
| Source File | `src/step_count.cpp` |
| Functions | `stepCountInit()`, `stepCountProcessSample()`, `stepCountGetTotal()` |
| Dependencies | `device_time.h` (for daily reset), `math.h` |
| Output | Step count (walking detection) |
| Notes | Useful as supplementary feature for sitting vs. standing classification (standing-and-walking vs. sitting-still) |

---

### Minimal Reuse Set for ML Prototype

To create a minimal experimental firmware that streams labeled accelerometer data:

1. Copy `config.h` (pin definitions only)
2. Copy accelerometer init from `training.cpp`
3. Copy LPF logic (3 lines of math)
4. Copy `computePostureAngle()` function
5. Copy BLE setup from `bluetooth.cpp` (service + characteristic + sendBlePacket)
6. Enable `RESEARCH_CAPTURE` mode for CSV data collection via RTT
7. Add BLE streaming of raw + filtered + angle at desired rate

**Estimated code needed:** ~300 lines for acquisition + streaming prototype.
