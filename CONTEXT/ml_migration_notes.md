# Executive Summary

The minimum reusable subset for a sitting-vs-standing ML prototype is centered on `src/training.cpp`, `src/calibration.cpp`, `src/storage.cpp`, and the small public headers that expose their APIs. In practice, the reusable runtime is: LIS3DH acquisition, a first-order LPF, posture origin handling, posture-angle calculation, and a lightweight logging path. BLE is optional and can be reduced to a thin streaming shim because the posture pipeline already produces the exact scalar signals needed for dataset capture.

Estimated code to carry over is modest: roughly 4 source files plus 4-6 headers, with the real extraction cost coming from dependency cleanup rather than line count. The recommended strategy is to split the posture pipeline into a new sensor/angle module, keep calibration/profile persistence only if you need repeatable labels, and treat BLE and RTT logging as adapters that sit on top of the core sample stream. That keeps the experiment repo independent from production mode/session/motor logic while preserving the exact math and sample behavior already validated in firmware.

# Dependency Graph

## posture angle path

`computePostureAngle()`
->
required structs
->
`OrientationProfile` (`include/calibration.h`)
->
required globals
->
`Y_ORIGIN`, `Z_ORIGIN`, `orientationText`, `currentAngle`, `rawX`, `rawY`, `rawZ`, `kBadPostureDeg` (`src/training.cpp`, `include/training.h`)
->
required headers
->
`training.h`, `calibration.h`, `config.h`, `Arduino.h`, `math.h`, `string.h`, `monitor_log.h`
->
required source files
->
`src/training.cpp`

## accelerometer acquisition path

`trainingIngestAccelSample()` / `trainingSampleAccelForCalibration()`
->
required structs
->
`sensors_event_t` from `Adafruit_Sensor`
->
required globals
->
`lis`, `sensorInitialized`, `rawX`, `rawY`, `rawZ`, `g_fx`, `g_fy`, `g_fz`, `s_lpfSeeded`, `stepCountGetTotal()`, `stepCountProcessSample()`
->
required headers
->
`training.h`, `config.h`, `Adafruit_LIS3DH.h`, `Adafruit_Sensor.h`, `Wire.h`, `step_count.h`, `monitor_log.h`
->
required source files
->
`src/training.cpp`, `src/step_count.cpp`

## filtering path

LPF is implemented inline inside `trainingIngestAccelSample()`
->
required structs
->
none beyond sensor sample data
->
required globals
->
`kLpfAlpha`, `g_fx`, `g_fy`, `g_fz`, `s_lpfSeeded`
->
required headers
->
`training.h`, `config.h`, `math.h`
->
required source files
->
`src/training.cpp`

## calibration path

`initCalibration()`, `handleCalibration()`, `requestCalibrationStart()`, `requestCalibrationCancel()`, `startCalibration()`, `cancelCalibration()`
->
required structs
->
`CalibrationStats`, `OrientationProfile`, `PersistedSettings`, `CalibrationProfile`, `CalibrationSettings`
->
required globals
->
`calibState`, `pendingStart`, `pendingCancel`, `samplesX`, `samplesY`, `samplesZ`, `totalSamples`, `lastCalibrationResult`, `s_lastCalibratedX/Y/Z`, `s_lastCalibrationValid`, `g_settings`, `Y_ORIGIN`, `Z_ORIGIN`, `currentAngle`, `sensorInitialized`
->
required headers
->
`calibration.h`, `training.h`, `storage.h`, `bluetooth.h`, `motor.h`, `therapy.h`, `monitor_log.h`, `config.h`
->
required source files
->
`src/calibration.cpp`, `src/storage.cpp`, `src/training.cpp`

## BLE streaming path

`bluetoothLoop()`, `sendBlePacket()`, `notifyCalibrationStatus()`, `notifyCalibrationComplete()`, live telemetry packet builders
->
required structs
->
`BLEService`, `BLECharacteristic`, `BatteryReading`
->
required globals
->
`connected`, `bleInitialized`, `gService`, `gCharacteristic`, `pCharacteristic`, `currentAngle`, `directionText`, `postureText`, `orientationText`, `batteryPercentage`, `batteryMillivolts`, `blePairingKnownPaired`
->
required headers
->
`bluetooth.h`, `training.h`, `calibration.h`, `storage.h`, `monitor_log.h`, `BatteryMonitor.h`, `bluefruit.h`, `ble_hci.h`
->
required source files
->
`src/bluetooth.cpp`, `src/BatteryMonitor.cpp`

## research capture mode

`researchCaptureCsvLog()`
->
required structs
->
none
->
required globals
->
`RESEARCH_CAPTURE`, `rawX`, `rawY`, `rawZ`, `currentAngle`, `sensorInitialized`
->
required headers
->
`config.h`, `monitor_log.h`
->
required source files
->
`src/training.cpp`

# Exact Files To Copy

## Mandatory

| File | Required? | Reason |
| ---- | --------- | ------ |
| `src/training.cpp` | Yes | Contains accelerometer acquisition, LPF, posture angle computation, posture labels, and research-capture logging. |
| `include/training.h` | Yes | Exposes the posture APIs and the shared posture globals. |
| `src/calibration.cpp` | Yes | Implements calibration collection, stability checks, and save/restore flow. |
| `include/calibration.h` | Yes | Defines `OrientationProfile`, `CalibrationProfile`, `CalibrationSettings`, and calibration APIs. |
| `src/storage.cpp` | Yes | Persists calibration origin and profile data used by posture angle calculation. |
| `include/storage.h` | Yes | Declares storage APIs used by calibration and posture bootstrap. |
| `include/config.h` | Yes | Holds board pins, `RESEARCH_CAPTURE`, RTT flags, and the constants the posture code depends on. |
| `src/step_count.cpp` | Yes for exact reuse | `training.cpp` calls `stepCountInit()`, `stepCountProcessSample()`, and `stepCountGetTotal()`. |
| `include/step_count.h` | Yes for exact reuse | Needed by `training.cpp`. |
| `src/BatteryMonitor.cpp` | Optional if BLE removed | Only needed if the BLE layer reports battery. |
| `include/BatteryMonitor.h` | Optional if BLE removed | Only needed with `bluetooth.cpp`. |

## Recommended

| File | Required? | Reason |
| ---- | --------- | ------ |
| `src/bluetooth.cpp` | Recommended | Useful for live streaming posture samples, calibration status, and device info over BLE. |
| `include/bluetooth.h` | Recommended | Public BLE API wrapper for a standalone stream/export mode. |
| `src/monitor_log.cpp` if added in new repo | Recommended | Current code uses `monitor_log.h` for RTT logging helpers. |
| `include/monitor_log.h` | Recommended | Lightweight logging wrapper used by training, calibration, storage, and BLE. |
| `src/main.cpp` | Recommended | Gives the minimal bootstrap order for init and loop scheduling. |
| `include/button.h` | Recommended only if you want on-device mode switching | `training.cpp` references current mode via button/module globals. |
| `src/session_stats.cpp` | Recommended only if you want session labels in telemetry | `training.cpp` uses session counters when composing `postureText`. |
| `include/session_stats.h` | Recommended only if you want session labels in telemetry | Exposes the session counters used in status strings. |
| `src/orientation_profiles.cpp` | Recommended if profile selection is needed | Calibration/profile selection logic depends on `getActiveProfile()` and profile storage. |

## Not Needed

| File | Required? | Reason |
| ---- | --------- | ------ |
| `src/motor.cpp` / `include/motor.h` | No | Haptics and alerts are not required for dataset collection or classification. |
| `src/therapy.cpp` / `include/therapy.h` | No | Therapy wave generation is unrelated to sitting-vs-standing ML. |
| `src/button.cpp` / `include/button.h` | No | Useful for product UX, not needed in the prototype core. |
| `src/device_time.cpp` / `include/device_time.h` | No | Time sync is not required for a standalone capture prototype. |
| `src/session_log.cpp` / `include/session_log.h` | No | Production session logging is not required unless you want archival metadata. |
| `src/session_stats.cpp` / `include/session_stats.h` | No for pure ML capture | Only useful if you want session-level counters in exported data. |
| `src/BatteryMonitor.cpp` / `include/BatteryMonitor.h` | No for pure ML capture | Battery reporting is optional unless BLE telemetry needs it. |
| OTA / DFU helpers in `bluetooth.cpp` | No | Production maintenance path, not part of ML capture. |
| Factory reset plumbing in `storage.cpp` | No | Not needed for the experimental repository. |

# Exact Functions To Reuse

## accelerometer init

Function Name: `initPostureSensor(bool quick = false)`
Source File: `src/training.cpp`
Purpose: Initialize LIS3DH, set range to `±2G`, set ODR to `100 Hz`, load stored calibration, and seed the filter state.
Dependencies: `recoverI2CBus()`, `Wire`, `Adafruit_LIS3DH`, `storageLoadCalibration()`, `sensorInitialized`, `s_lpfSeeded`, `PIN_I2C_SDA`, `PIN_I2C_SCL`
Can Be Isolated? `Yes`, but it needs a hardware abstraction layer for I2C and the LIS3DH driver.

## accelerometer read

Function Name: `trainingIngestAccelSample()`
Source File: `src/training.cpp`
Purpose: Read one LIS3DH sample, update `rawX/rawY/rawZ`, feed step counting, and advance the LPF.
Dependencies: `sensorInitialized`, `lis.getEvent()`, `rawX`, `rawY`, `rawZ`, `g_fx/g_fy/g_fz`, `s_lpfSeeded`, `stepCountProcessSample()`, `stepCountGetTotal()`
Can Be Isolated? `Yes`, but only if you keep the sensor and step-counter dependencies or stub them out.

## LPF filter

Function Name: `trainingIngestAccelSample()` section using `kLpfAlpha`
Source File: `src/training.cpp`
Purpose: Apply first-order low-pass filtering to the raw accelerometer stream.
Dependencies: `kLpfAlpha`, `g_fx`, `g_fy`, `g_fz`, `s_lpfSeeded`
Can Be Isolated? `Yes`

## posture angle calculation

Function Name: `computePostureAngle(float X, float Y, float Z)`
Source File: `src/training.cpp`
Purpose: Compute relative posture angle between current filtered acceleration vector and the active calibration/profile reference.
Dependencies: `OrientationProfile`, `getActiveProfile()`, `Y_ORIGIN`, `Z_ORIGIN`, `orientationText`, `kAngleClampDeg`, `atan2f()`, `sqrtf()`
Can Be Isolated? `Mostly yes`; it becomes fully standalone once profile lookup and origin storage are replaced with a plain reference vector.

## calibration functions

Function Name: `initCalibration()`
Source File: `src/calibration.cpp`
Purpose: Reset calibration state and initialize profile storage.
Dependencies: `initProfiles()`, `motorSetDuty()`, `cancelPostCalibrationValidation()`
Can Be Isolated? `Partially`

Function Name: `handleCalibration()`
Source File: `src/calibration.cpp`
Purpose: Run the full calibration state machine, sample window, stability checks, and success/failure routing.
Dependencies: `trainingSampleAccelForCalibration()`, `calibrationFail()`, `calibrationSuccess()`, `currentAngle`, `rawX/rawY/rawZ`, `storage`, `bluetooth`, `motor`, `therapy`
Can Be Isolated? `No` without trimming a lot of production callbacks.

Function Name: `requestCalibrationStart()`
Source File: `src/calibration.cpp`
Purpose: Defer calibration start until the main loop processes it.
Dependencies: `pendingStart`
Can Be Isolated? `Yes`

Function Name: `requestCalibrationCancel()`
Source File: `src/calibration.cpp`
Purpose: Defer or force calibration cancellation.
Dependencies: `pendingCancel`, `cancelCalibration()`
Can Be Isolated? `Yes`

Function Name: `startCalibration()`
Source File: `src/calibration.cpp`
Purpose: Validate readiness and enter the GET_READY calibration phase.
Dependencies: `bluetoothIsConnected()`, `sensorInitialized`, `bluetoothGetBatteryPercentage()`, `therapyIsRunning()`, `bluetoothIsMotorActive()`, `isDeviceMoving()`, `wakePostureSensor()`, `motorOverrideDuty()`
Can Be Isolated? `No` unless you remove all device-state gates.

Function Name: `cancelCalibration()`
Source File: `src/calibration.cpp`
Purpose: Cancel calibration and return to training mode.
Dependencies: `goToTrainingMode()`, `motorSetDuty()`, local calibration state
Can Be Isolated? `Mostly yes`

## BLE send functions

Function Name: `sendBlePacket(const char* payload)`
Source File: `src/bluetooth.cpp`
Purpose: Write and notify a JSON payload over BLE.
Dependencies: `pCharacteristic`, `rttPrintBlePacket()`
Can Be Isolated? `Yes`

Function Name: `notifyCalibrationStatus(...)`
Source File: `src/bluetooth.cpp`
Purpose: Stream calibration progress/state to the mobile client.
Dependencies: `isCalibrating()`, `getCalibrationElapsedMs()`, `getCalibrationTotalMs()`, `getCalibrationPhase()`
Can Be Isolated? `Yes`

Function Name: `notifyCalibrationComplete(...)`
Source File: `src/bluetooth.cpp`
Purpose: Send calibration result metadata, including profile id, quality, and sample count.
Dependencies: `sendBlePacket()`
Can Be Isolated? `Yes`

Function Name: `bluetoothLoop()`
Source File: `src/bluetooth.cpp`
Purpose: Maintain BLE connection state, send live telemetry, and service commands.
Dependencies: `training`, `calibration`, `storage`, `battery`, `motor`, `device_time`, `session_stats`
Can Be Isolated? `No` as-is; it is the heaviest production coupling point.

## research capture functions

Function Name: `researchCaptureCsvLog(uint32_t now)`
Source File: `src/training.cpp`
Purpose: Emit CSV rows for raw accelerometer data plus posture angle when `RESEARCH_CAPTURE` is enabled.
Dependencies: `RESEARCH_CAPTURE`, `rawX`, `rawY`, `rawZ`, `currentAngle`, `sensorInitialized`, `rtt`
Can Be Isolated? `Yes`

# Global Variables And Constants

## training pipeline globals

`kLpfAlpha` (`src/training.cpp:35`)
`kMotionThreshold` (`src/training.cpp:36`)
`kDirectionDeg` (`src/training.cpp:37`)
`kAngleClampDeg` (`src/training.cpp:39`)
`kDefaultOriginY` (`src/training.cpp:40`)
`kDefaultOriginZ` (`src/training.cpp:41`)
`kNearZero` (`src/training.cpp:42`)
`kGoodDebounceMs` (`src/training.cpp:43`)
`kInitMaxAttempts` (`src/training.cpp:44`)
`kInitRetryDelayMs` (`src/training.cpp:45`)
`kBadPostureDeg` (`src/training.cpp:38`, non-static global)
`rawX`, `rawY`, `rawZ` (`src/training.cpp:65`)
`Y_ORIGIN`, `Z_ORIGIN` (`src/training.cpp:66`)
`currentAngle` (`src/training.cpp:68`)
`isBadPosture` (`src/training.cpp:69`)
`sensorInitialized` (`src/training.cpp:70`)
`s_bootProfileDetectionDone` (`src/training.cpp:71`)
`orientationText[16]` (`src/training.cpp:73`)
`directionText[16]` (`src/training.cpp:74`)
`postureText[96]` (`src/training.cpp:75`)
`_moving` (`src/training.cpp:78`)
`g_fx`, `g_fy`, `g_fz` (`src/training.cpp:81`)
`s_lpfSeeded` (`src/training.cpp:82`)
`s_motionPrevX`, `s_motionPrevY`, `s_motionPrevZ` (`src/training.cpp:85`)
`s_goodPostureStableStart` (`src/training.cpp:88`)
`s_forwardMotorBad` (`src/training.cpp:217`)
`s_trainingStartMs` (`src/training.cpp:218`)
`lis` (`src/training.cpp:61`)

## calibration globals

`CALIB_GET_READY_MS` (`src/calibration.cpp:18`)
`CALIB_HOLD_MS` (`src/calibration.cpp:19`)
`CALIB_TOTAL_MS` (`src/calibration.cpp:20`)
`CALIB_RESULT_BROADCAST_MS` (`src/calibration.cpp:21`)
`kSafetyTimeoutMs` (`src/calibration.cpp:22`)
`kSampleIntervalMs` (`src/calibration.cpp:23`)
`kMaxCalibrationSamples` (`src/calibration.cpp:24`)
`MIN_VALID_SAMPLES` (`src/calibration.cpp:25`)
`kEarlyFailMinSamples` (`src/calibration.cpp:26`)
`kFinalStdDevLimit` (`src/calibration.cpp:27`)
`kEarlyFailStdDevLimit` (`src/calibration.cpp:28`)
`calibState` (`src/calibration.cpp:16`)
`pendingStart`, `pendingCancel` (`src/calibration.cpp:30-31`)
`stabilityStartTime`, `lastHoldPrintMs` (`src/calibration.cpp:33-34`)
`totalSamples`, `s_lastSampleTime` (`src/calibration.cpp:36-37`)
`samplesX`, `samplesY`, `samplesZ` (`src/calibration.cpp:39-41`)
`lastCalibrationResult[16]` (`src/calibration.cpp:43`)
`calibResultSetAt` (`src/calibration.cpp:44`)
`s_failVibEndMs`, `s_successPulseEndMs` (`src/calibration.cpp:46-47`)
`s_postValidationStartMs`, `s_postValidationProfileId`, `s_postValidationActive`, `s_postValidationFailed` (`src/calibration.cpp:48-51`)
`s_lastCalibratedX`, `s_lastCalibratedY`, `s_lastCalibratedZ`, `s_lastCalibrationValid` (`src/calibration.cpp:54-57`)
`CalibrationStats` (`src/calibration.cpp:59-66`)

## storage globals

`SETTINGS_PAGE_ADDR` (`src/storage.cpp:26`)
`SETTINGS_MAGIC` (`src/storage.cpp:27`)
`SETTINGS_VERSION` (`src/storage.cpp:28`)
`PersistedSettingsV1` / `PersistedSettingsV3` / `PersistedSettings` (`src/storage.cpp:30-47`)
`g_settings` (`src/storage.cpp:49-67`)
`ACTIVE_PROFILE_DEFAULT` (`src/storage.cpp:76`)
`ACTIVE_PROFILE_MAX_STORED` (`src/storage.cpp:77`)
`NEXT_OVERWRITE_DEFAULT` (`src/storage.cpp:78`)
`PROFILE_STORE_MAGIC` (`src/storage.cpp:79`)
`PROFILE_STORE_PATH` (`src/storage.cpp:80`)
`PROFILE_STORE_TMP_PATH` (`src/storage.cpp:81`)
`ProfileStore` (`src/storage.cpp:83-89`)

## BLE globals

`therapyIntensityLevel` (`src/bluetooth.cpp:20`)
`connected`, `bleInitialized`, `currentConnHandle` (`src/bluetooth.cpp:28-30`)
`pairingUnlockActive`, `blePairingKnownPaired`, `clearBondsAfterDisconnect` (`src/bluetooth.cpp:31-33`)
`connectionHapticPending`, `connectionHapticPlayed`, `disconnectionHapticPending` (`src/bluetooth.cpp:34-36`)
`forceTelemetrySync`, `forceLiveSync` (`src/bluetooth.cpp:37-38`)
`gService`, `gCharacteristic`, `pCharacteristic` (`src/bluetooth.cpp:45-47`)
`batteryMonitor`, `batteryVoltage`, `batteryRawAdc`, `batterySenseMillivolts`, `batteryMillivolts`, `batteryPercentage` (`src/bluetooth.cpp:48-53`)
`batteryReadValid`, `batteryBlinkActive`, `batteryBlinkStartMs` (`src/bluetooth.cpp:55-57`)
`BATTERY_BLINK_PERIOD_MS`, `BATTERY_BLINK_COUNT`, `UNPAIRED_RED_BLINK_PERIOD_MS`, `CONNECTION_HAPTIC_DELAY_MS`, `DISCONNECTION_HAPTIC_DUTY`, `DISCONNECTION_HAPTIC_MS` (`src/bluetooth.cpp:59-64`)
`BLE_PAIR_MARKER_PATH` (`src/bluetooth.cpp:65`)

## config and compile-time flags

`PIN_I2C_SDA`, `PIN_I2C_SCL`, `PIN_MOTOR`, `PIN_LED_RED/GREEN/BLUE`, `PIN_BATTERY_ADC` (`include/config.h`)
`ALIGN_RTT_JSON_LOG`, `ALIGN_RTT_BLE_RX_LOG`, `ALIGN_RTT_STATUS_LOG`, `ALIGN_RTT_STATUS_INTERVAL_MS`, `ALIGN_RTT_SENSOR_LOG`, `RESEARCH_CAPTURE`, `ALIGN_RTT_CALIB_VERBOSE` (`include/config.h`)
`BLE_SERVICE_UUID`, `BLE_CHARACTERISTIC_UUID`, `BLE_DEVICE_NAME` (`include/config.h`)
Platform flags from `platformio.ini`: `-I include`, `-DNRF52832_XXAA`, `-DDEBUG_LOGGING`, `-g3`

# Hidden Dependencies

`training.cpp` depends on the global `currentMode`, `deviceOn`, `trainingSubModeIndex`, and `trainingSubModes` that are not declared in `training.h`. In the standalone repo, those should be replaced by a minimal local mode enum or deleted entirely.

`computePostureAngle()` is not actually standalone because it reads the active profile through `getActiveProfile()`, mutates `orientationText`, and falls back to `Y_ORIGIN/Z_ORIGIN` when no profile exists.

`trainingIngestAccelSample()` contains a hidden dependency on `step_count` even though step counting is not part of the ML request. If you want the smallest capture-only repository, remove that call path or stub it.

`calibration.cpp` is tightly coupled to `bluetooth`, `therapy`, and `motor` for readiness checks and feedback pulses. Those are production behaviors, not mathematical requirements, so they should be split out in the prototype.

`storage.cpp` assumes the nRF52 flash layout, `NRF_NVMC`, and optionally `InternalFS`. Blindly copying it into another MCU or board will break persistence.

The BLE path assumes the Nordic Bluefruit stack, `BatteryMonitor`, and board-specific LEDs. That makes the BLE adapter non-portable unless you keep the same target platform or provide an abstraction layer.

`RESEARCH_CAPTURE` logs at runtime through RTT, not through a file writer. On a standalone repo, you will need to redirect those CSV rows to UART, USB CDC, SD card, or a host logger.

Initialization order matters: `storageSetup()` must run before `trainingSetup()` if you want calibration origin restored before the first posture sample, and `bluetoothSetup()` should run only after storage and sensor init if you want valid telemetry immediately.

# Research Capture Analysis

All code related to `RESEARCH_CAPTURE` is in `src/training.cpp` inside `researchCaptureCsvLog(uint32_t now)` at `src/training.cpp:459`.

## Build flags required

`RESEARCH_CAPTURE` must be defined to a non-zero value. In this repository it defaults to `0` in `include/config.h:79-80`, so you must override it in `platformio.ini` or a build profile.

The CSV logger also depends on the RTT stream stack already present in the project:
`RTT Stream@^1.3.0` in `platformio.ini`
`RTTStream.h` in `include/training.h` and `include/monitor_log.h`

## Output format

Current CSV format is:
`now,rawX,rawY,rawZ,currentAngle`

The log is emitted with `rtt.print()` / `rtt.println()` and is rate-limited to one row every `20 ms`, which means an effective maximum of `50 Hz`.

## Sample rate

The sensor itself is configured for `100 Hz` in `initPostureSensor()`, but the research-capture logger only emits every `20 ms`. For a sitting-vs-standing dataset, that is the exact capture rate currently encoded in firmware.

## Dependencies

`sensorInitialized`
`rawX`, `rawY`, `rawZ`
`currentAngle`
`rtt`
`trainingIngestAccelSample()` or `updatePostureAngle()` upstream

## Modifications required to run standalone

Replace RTT output with a transport that exists in the new repo.
Remove the `training.cpp` dependency on session stats if you do not need status text.
Keep or replace the `Adafruit_LIS3DH` and `Wire` setup path.
If you want labels, add an explicit label column because the current capture code only emits features, not class labels.

# Minimal ML Prototype Architecture

The smallest practical standalone layout is:

`main.cpp`
`sensor.cpp`
`sensor.h`
`angle.cpp`
`angle.h`
`calibration.cpp`
`calibration.h`
`logger.cpp`
`logger.h`
`ble.cpp` and `ble.h` only if live streaming is needed

## File roles

`main.cpp`: initialize storage, sensor, and optional BLE; run the capture loop.

`sensor.cpp` / `sensor.h`: LIS3DH init, raw reads, LPF state, and motion detection.

`angle.cpp` / `angle.h`: posture-origin handling and `computePostureAngle()` logic.

`calibration.cpp` / `calibration.h`: capture a stillness window, compute averages and standard deviation, save/update the reference posture.

`logger.cpp` / `logger.h`: emit CSV to UART/RTT/USB/SD without mixing it into the math code.

`ble.cpp` / `ble.h`: optional transport for live samples and calibration status; keep it thin and stateless.

# Dataset Collection Plan

## What to log

At minimum log:
`timestamp_ms`
`rawX`
`rawY`
`rawZ`
`filteredX`
`filteredY`
`filteredZ`
`currentAngle`
`orientationText`
`directionText`
`postureText`
`calibration_label` or `pose_label`
`profile_id` if profile-based labeling is used

The existing firmware already supports the raw stream (`researchCaptureCsvLog()`), posture angle (`currentAngle`), and posture text fields (`orientationText`, `directionText`, `postureText`).

## Recommended sampling frequency

Use the firmware’s native sensor rate of `100 Hz` for acquisition, but if you need a lighter dataset pipeline, keep the current research logger at `50 Hz` and ensure the exported rows are timestamped. For ML, consistency matters more than absolute frequency as long as you do not alias the motion.

## Recommended CSV format

`timestamp_ms,rawX,rawY,rawZ,filteredX,filteredY,filteredZ,currentAngle,label,profile_id`

If you keep only the current firmware behavior, the narrow format is:
`timestamp_ms,rawX,rawY,rawZ,currentAngle`

## How to label data

Label the capture session externally, not implicitly from posture heuristics.
For example: `standing`, `sitting`, `transition`, `unknown`.
If you use calibration-driven labels, store the profile id and map it offline to class labels.

## Existing functions that already help

`trainingIngestAccelSample()`
`trainingGetFilteredAccel()`
`updatePostureAngle()`
`computePostureAngle()`
`researchCaptureCsvLog()`
`storageLoadCalibration()`
`storageSaveCalibration()`
`initPostureSensor()`

# Migration Checklist

Step 1: Create a new standalone repository and keep the same board target if you want zero sensor-driver churn.

Step 2: Copy `src/training.cpp`, `src/calibration.cpp`, `src/storage.cpp`, `include/training.h`, `include/calibration.h`, `include/storage.h`, `include/config.h`, and `include/monitor_log.h`.

Step 3: Add only the minimum driver set: `Adafruit LIS3DH`, `Adafruit Unified Sensor`, `RTT Stream` if you still want RTT output, and `Wire`.

Step 4: Remove production-only dependencies from the copied code, especially `therapy`, `motor`, session tracking, DFU/OTA, and the full BLE command parser.

Step 5: Replace hidden globals such as `currentMode`, `deviceOn`, and `trainingSubModeIndex` with a tiny local experiment state machine.

Step 6: Verify accelerometer init and raw reads on the target board before enabling any filter or calibration logic.

Step 7: Verify the LPF output is stable and that posture angle changes smoothly when the board is tilted.

Step 8: Verify calibration saves and reloads the reference vector correctly.

Step 9: Add a CSV logger and confirm that each row contains a timestamp and either raw or filtered features.

Step 10: Decide whether BLE is needed. If yes, keep only a simple telemetry characteristic and send the same CSV/JSON samples you log locally.

Step 11: Create a labeling workflow, either manual per session or external post-processing, and confirm that sitting and standing sessions produce separable feature distributions.

Step 12: Run a short end-to-end capture session and validate that the exported file can be loaded directly into your ML notebook without firmware-side cleanup.

Estimated effort to create standalone prototype: 10 hours
