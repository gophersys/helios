# VSM (Vital Signs Monitor) Driver -- Deep Architectural Analysis

**Module:** `_fw_build/vsm_drv/`
**Platform:** Zephyr RTOS on nRF52840 (ARM Cortex-M4F)
**Copyright:** CoreKinect Inc. 2024-2025
**Date of Analysis:** 2026-02-09

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Data Pipeline](#2-data-pipeline)
3. [Sampling Rate Handling](#3-sampling-rate-handling)
4. [PSP Integration](#4-psp-integration)
5. [Thread Model](#5-thread-model)
6. [State Machine](#6-state-machine)
7. [Configuration](#7-configuration)
8. [BLE Output Format](#8-ble-output-format)
9. [Test Coverage](#9-test-coverage)
10. [Potential Issues and Risks](#10-potential-issues-and-risks)

---

## 1. Architecture Overview

The VSM driver is a Zephyr RTOS module that orchestrates three hardware sensors and a proprietary Philips PSP (Philips Sensing Platform) signal processing library to extract vital signs from a wearable wrist device (Alpha prototype). It produces heart rate (BPM), SpO2 (blood oxygen %), and skin temperature (Fahrenheit) readings.

### 1.1 Module Boundaries

```
+------------------------------------------------------------------+
|                        Application Layer                          |
|  (samples/simple/src/main.c -- callback-driven, event-based)     |
+---------+--------------------------------------------------------+
          |  vsm_init() / vsm_deinit() / vsm_activate_monitoring()
          v
+---------+--------------------------------------------------------+
|                         VSM Module (vsm.h)                        |
|  Aggregates vitals thread API + optional Bluetooth thread API     |
+---------+--------------------------+-----------------------------+
          |                          |
          v                          v
+---------+---------+    +-----------+-----------+
|   Vitals Thread   |    |   Bluetooth Thread    |  (optional)
|   (thread.c)      |--->|   (bluetooth/thread.c)|
|   Priority: 3     |    |   Priority: 4         |
+---------+---------+    +-----------+-----------+
          |                          |
    +-----+------+------+           |
    |     |      |      |           |
    v     v      v      v           v
+-----+ +-----+ +----+ +-----+  +-------+
| PPG | | IMU | |Temp| | PSP |  | BLE   |
|8151 | |6DSO | |614 | | Lib |  | Stack |
+-----+ +-----+ +----+ +-----+  +-------+
  I2C     I2C    I2C   ROM-resident  Zephyr BT
```

### 1.2 Hardware Sensors

| Sensor | IC | Interface | Purpose | Sample Rate |
|--------|----|-----------|---------|-------------|
| PPG | PAH8151 (PixArt) | I2C (0x15) | Photoplethysmography -- red, green, IR LED intensities | 32 Hz (batched at ~1 Hz) |
| IMU | LSM6DSO (STMicro) | I2C (0x6A) or SPI | Accelerometer + Gyroscope for motion artifact rejection | 52 Hz (FIFO-buffered) |
| Temperature | MLX90614 (Melexis) | I2C (0x5A) | Infrared skin temperature measurement | 1 Hz (timer-driven) |

### 1.3 File Structure

```
vsm_drv/
  CMakeLists.txt                    # Top-level build: guards on CONFIG_CK_MODULES_VSM
  Kconfig                           # All Kconfig options
  README.md                         # Module readme
  src/
    CMakeLists.txt
    corekinect/module/vsm/
      vsm.h                         # Main module header (aggregator)
      CMakeLists.txt
      threads/
        CMakeLists.txt              # Conditionally adds bluetooth/
        vitals/
          api.h                     # Public API: vsm_init, vsm_deinit, vsm_activate_monitoring, etc.
          types.h                   # All type definitions: vsm_t, vsm_config_t, enums, sample structs
          config.h                  # Compile-time constants: stack size, rates, thresholds
          output.h                  # Output metrics struct: vitals_output_metrics_t, vitals_hw_error_t
          priv.h                    # Internal function declarations
          thread.c                  # Main thread entry, event loop, state machine, ISR handlers
          init.c                    # Sensor init, I2C scan, trigger setup, PSP init, thread creation
          deinit.c                  # Graceful shutdown, sensor deinit, thread join/abort
          monitor.c                 # vsm_activate_monitoring / vsm_deactivate_monitoring
          CMakeLists.txt            # Compiles: init.c, deinit.c, thread.c, monitor.c, psp.c
          utils/
            api.h                   # Internal utility function declarations
            transform.c             # Accel downsampling 52Hz->32Hz, PPG scaling, PSP format conversion
            psp.c                   # PSP library wrapper: init, process, set/get metrics, reset
            ble.c                   # BLE data formatting and queueing
          tests/
            cross_talk.c            # Cross-talk (light leakage) manufacturing test
            snr.c                   # SNR test (stub -- not yet implemented)
            reflectivity.c          # Reflectivity test (stub -- not yet implemented)
          lib/inc/
            psp.h                   # Philips PSP library C header (API declarations)
            psp.c                   # PSP library C shim (function pointer trampolines to ROM)
            psp_map.h               # ROM address map for PSP library functions
            fx_datatypes.h          # Philips fixed-width type definitions (FX_UINT08, etc.)
        bluetooth/
          thread.h                  # Bluetooth thread public API
          types.h                   # BLE data structures, FIFO types, config
          thread.c                  # BLE GATT server, advertising, notification management
  samples/simple/
    src/main.c                      # Sample application demonstrating VSM usage
    prj.conf                        # Zephyr project configuration
```

---

## 2. Data Pipeline

### 2.1 End-to-End Data Flow (ASCII Diagram)

```
     HARDWARE                    ISR CONTEXT                  THREAD CONTEXT               OUTPUT
  +-----------+             +------------------+          +--------------------+        +----------+
  | PAH8151   |--INT------->| _ppg_data_ready_ |          |                    |        |          |
  | PPG Sensor|  (1Hz batch)| handler()        |          | _process_accel_    |        | Callback |
  | 32 samp/s |             | 1. Read IMU FIFO |          | data()             |        | to App:  |
  +-----------+             | 2. Read PPG batch |          | (ACTIVE_MONITORING)|        | HR, SpO2,|
                            | 3. Store samples  |         |   |                |        | Temp     |
  +-----------+             | 4. Signal sem     |          |   v                |        +----------+
  | LSM6DSO   |  (FIFO)    +--------+---------+          | _prepare_sensor_   |             |
  | IMU 52Hz  |---(read in           |                    | samples()          |             |
  | Accel+Gyro|   ISR)               v                    |   |                |             v
  +-----------+             +------------------+          |   +-> _downsample_ |        +----------+
                            | ppg_data_ready_  |          |   |   accel_to_32Hz|        | BLE      |
  +-----------+             | sem signaled     |          |   |                |        | Thread   |
  | MLX90614  |             +--------+---------+          |   +-> _convert_raw_|        | (optional|
  | Temp 1Hz  |---(timer)            |                    |       samples_for_ |        |  32Hz +  |
  | IR thermo |             +--------v---------+          |       psp()        |        |  25Hz +  |
  +-----------+             |  k_poll() wakes  |          |   |                |        |  1Hz)    |
                            |  vitals thread   |          |   v                |        +----------+
                            +--------+---------+          | _send_ble_sensor_  |
                                     |                    | samples() [if BLE] |
                                     v                    |   |                |
                            +------------------+          |   v                |
                            | Event dispatch:  |          | _psp_update_input_ |
                            | - HW_ERROR       |          | metrics()          |
                            | - WATCHDOG       |          |   |                |
                            | - SHUTDOWN       |          |   v                |
                            | - PPG_TOUCH      |          | _psp_process()     |
                            | - TEMP_READY     |          |   |                |
                            | - STATE_CHANGE   |          |   v                |
                            | - PPG_DATA_READY |          | _psp_get_output_   |
                            +------------------+          | metrics()          |
                                                          |   |                |
                                                          |   v                |
                                                          | callback(METRICS_  |
                                                          |   UPDATED)         |
                                                          +--------------------+
```

### 2.2 Detailed Steps

1. **Sensor Interrupt (ISR context in `_ppg_data_ready_handler`):**
   - PPG sensor fires a data-ready interrupt at approximately 1 Hz (one batch of 32 samples).
   - The handler immediately reads the IMU FIFO (`_read_imu_samples`) to get the ~52 accelerometer samples accumulated since the last interrupt.
   - Then reads the PPG batch: for each of the 32 samples, it reads timestamp, red/green/IR intensity, exposure time, DAC values, and LED current.
   - Stores both datasets into the `vsm_t` structure's interrupt sample buffers.
   - Signals `ppg_data_ready_sem` to wake the vitals thread.

2. **Thread Processing (in `_handle_ppg_data_ready_event` / `_process_accel_data`):**
   - Only processed in `VITALS_STATE_ACTIVE_MONITORING`.
   - Calls `_prepare_sensor_samples()` which:
     - Downsamples accelerometer from 52 Hz to 32 Hz using timestamp-weighted interpolation.
     - Copies PPG data directly (already at 32 Hz).
     - Converts raw sensor values to PSP input format (scaling, clamping, unit conversion).
   - If BLE is enabled, sends raw sensor data to the Bluetooth thread.

3. **PSP Algorithm Execution:**
   - `_psp_update_input_metrics()` formats and writes 5 metric buffers to PSP: PPG IR, PPG Red, PPG Green, PPG Ambient, and Acceleration.
   - `_psp_process()` invokes the Philips algorithm.
   - `_psp_get_output_metrics()` reads heart rate and SpO2 results. Also reads back the propagated PPG/accel data for BLE transmission.

4. **Output Delivery:**
   - Application callback invoked with `VITALS_EVENT_METRICS_UPDATED` carrying the latest `vitals_output_metrics_t`.
   - BLE thread (if enabled) transmits data via GATT notifications at 1 Hz (vitals), 25 Hz (raw), and 32 Hz (PSP input/output).

---

## 3. Sampling Rate Handling

### 3.1 Sensor Rates

| Signal | Native Rate | PSP Required Rate | Alignment Method |
|--------|------------|-------------------|------------------|
| PPG (PAH8151) | 32 Hz (batched ~1 Hz) | 32 Hz | Direct copy -- no resampling needed |
| Accelerometer (LSM6DSO) | 52 Hz (FIFO) | 32 Hz | Timestamp-weighted downsampling |
| Temperature (MLX90614) | 1 Hz (timer) | N/A (not fed to PSP) | Read on timer, stored directly |

### 3.2 Accelerometer Downsampling (52 Hz to 32 Hz)

**Implementation:** `_downsample_accel_to_32Hz()` in `transform.c`

The downsampling uses a **timestamp-based weighted average** approach:

```
For each of the 32 PSP output samples:
  1. Determine the PPG timestamp window [ppg_timestamp[i], ppg_timestamp[i+1])
  2. Find all IMU samples that fall within this window
  3. For each matching IMU sample, compute weight = 1.0 - (time_offset / window_duration)
     (Closer samples to the PPG timestamp get higher weight)
  4. Weighted average of X, Y, Z accelerometer values
  5. If no samples found in window:
     a. Search with 2x wider window for nearest neighbor
     b. If still nothing, use the previous output sample (zero-order hold)
```

**Key characteristics:**
- This is a **non-uniform resampling** scheme driven by PPG timestamps.
- The weight function is linear, favoring samples nearer the start of each PPG window.
- The fallback chain (weighted avg -> nearest neighbor -> zero-order hold) provides robustness against timing jitter and missed samples.
- A warning is logged when the timestamp mismatch exceeds half the PPG sample period (~15.6 ms).

### 3.3 PPG Signal Scaling and Calibration

**Implementation:** `_convert_raw_samples_for_psp()` in `transform.c`

The PPG signals undergo dynamic scaling to fit the PSP library's expected 16-bit unsigned input range (0-65535):

1. **Initial Calibration (first 3 seconds = 96 samples at 32 Hz):**
   - Track maximum values for Red, IR, and Green channels.
   - Compute scaling factor: `SF = (65535 / 2) / max_observed_value`.
   - Red and IR share the same scaling factor (required for SpO2 ratio accuracy).
   - Green gets its own independent scaling factor.

2. **Dynamic Gain Adjustment (every 1 second = 32 samples):**
   - If scaled value exceeds 90% of max (58982), halve the scaling factor and decrement the virtual ADC gain.
   - If scaled value falls below 20% of max (13107), double the scaling factor and increment the virtual ADC gain.
   - ADC gain is tracked per-channel in range [1, 3] and reported to PSP via the metric preamble.
   - Red and IR gains are always kept in sync.

3. **Output Clamping:**
   - Final scaled values clamped to [0, 65535] via `CLAMP()` macro.

### 3.4 Accelerometer Unit Conversion

Raw accelerometer data arrives in m/s^2 (converted from mg in the ISR: `val1 * 0.00981`).

For PSP input format:
```
1. Normalize to g-force:     accel_g = accel_ms2 / 9.81
2. Convert to PSP units:     accel_psp = accel_g * 512  (1/512 g per unit)
3. Clamp to 13-bit signed:   [-4096, 4095]
4. Cast to int16_t
```

The PSP accelerometer format byte is `0x6E`: 32 Hz, +/- 8G range, 13-bit signed, 1/512 g/unit resolution.

---

## 4. PSP Integration

### 4.1 Library Architecture

The Philips PSP library is a **pre-compiled binary blob** resident in flash ROM at address range `0xE0000 - 0xF2FD2` (approximately 77 KB). It is accessed through function pointer trampolines defined in `psp.c` / `psp_map.h`. Each API function cast the ROM address to the appropriate function pointer type and calls it.

This is a ROM-resident library pattern common in embedded systems where the algorithm IP is pre-flashed and the application code calls into it via a well-defined ABI.

### 4.2 PSP API Functions Used

| Function | Purpose | When Called |
|----------|---------|-------------|
| `PSP_GetDefaultParams` | Get memory requirements | During `_psp_init` |
| `PSP_Initialise` | Create PSP instance | During `_psp_init` |
| `PSP_EnableMetrics` | Enable HR + SpO2 output | During `_psp_init` |
| `PSP_ListRequiredMetrics` | Query required inputs | During `_psp_init` |
| `PSP_SetMetric` | Feed input data per metric | During `_psp_update_input_metrics` |
| `PSP_Process` | Execute algorithm | During `_psp_process` |
| `PSP_ListUpdatedMetrics` | Check which outputs updated | During `_psp_get_output_metrics` |
| `PSP_GetMetric` | Read output values | During `_psp_get_output_metrics` |
| `PSP_Terminate` | Destroy PSP instance | During `_psp_deinit` |

### 4.3 PSP Memory

- **Heap size:** 27,000 bytes (`CONFIG_PSP_MEMORY_SIZE`), allocated from a dedicated `k_heap`.
- The heap is 8-byte aligned.
- Two allocations from the heap: `pMem` (main instance memory, size determined by `PSP_GetDefaultParams`) and `pSourceID`.

### 4.4 PSP Metric Data Format

Each metric sent to PSP follows this binary format:

**PPG Metric (per channel: IR, Red, Green, Ambient):**
```
Offset  Size  Field
0       1     Metric ID (0x7B=IR, 0x7C=Red, 0x7E=Green, 0x7F=Ambient)
1       2     Data length (little-endian, excludes first 3 bytes)
3       1     Sequence index (incrementing)
4       1     Quality (0 during warmup, 4 after calibration)
5       1     Body Position Index (2 = right wrist)
6       1     PPG Sample Format (0x60)
7       1     Stream Identifier (0x00)
8       1     PPG Offset (0x00)
9       1     PPG Exponent (0x00)
10      4     LED Power (DAC value, repeated 4 bytes)
14      4     ADC Gain (calibration gain, repeated 4 bytes)
18      64    PPG Samples (32 x uint16_t, little-endian)
---
Total:  82 bytes per PPG metric
```

**Accelerometer Metric:**
```
Offset  Size  Field
0       1     Metric ID (0x2B)
1       2     Data length (little-endian)
3       1     Sequence index
4       1     Quality
5       1     Body Position Index (0 = unspecified)
6       1     Accelerometer Format (0x6E: 32Hz, +/-8G, 13-bit, 1/512 g/unit)
7       192   Samples (32 x 3 axes x int16_t = 32 x 6 bytes)
---
Total:  199 bytes
```

**Output Metrics (Heart Rate, SpO2):**
```
Offset  Size  Field
0       1     Metric ID (0x20=HR, 0x41=SpO2)
1       2     Data length
3       1     Sequence index
4       1     Quality (0-4, higher = better)
5       1     Value (HR in BPM, SpO2 in %)
---
Total:  6 bytes per output metric
```

### 4.5 Enabled PSP Outputs

Only two output metrics are enabled:
- `PSP_METRIC_ID_HEARTRATE` (0x20)
- `PSP_METRIC_ID_SPO2` (0x41)

The PSP library is capable of many more (activity type, sleep stages, respiration rate, VO2max, etc.) but they are not enabled.

### 4.6 PSP Reset

When transitioning to `VITALS_STATE_TOUCH_DETECTED` (i.e., a new measurement session), the PSP algorithm is fully reset via `_psp_reset()` which performs a complete deinit/init cycle. This clears all internal algorithm state, forcing it to re-converge from scratch.

---

## 5. Thread Model

### 5.1 Vitals Thread

| Property | Value |
|----------|-------|
| **Entry point** | `_vitals_thread_entry()` in `thread.c` |
| **Stack size** | 8,192 bytes (`CONFIG_VITALS_THREAD_STACK_SIZE = 4096 * 2`) |
| **Priority** | 3 (`CONFIG_VITALS_THREAD_PRIORITY`) |
| **Scheduling** | Preemptive (priority > 0) |
| **Event model** | `k_poll()` on 7 semaphore events |
| **Name** | `"vitals_thread"` |

**Events polled (in priority order of processing):**

| Index | Event | Source | Processing |
|-------|-------|--------|------------|
| 0 | `HW_ERROR` | Any sensor failure | Callback + thread exit |
| 1 | `SHUTDOWN` | `vsm_deinit()` | Thread exit |
| 2 | `WATCHDOG_TIMEOUT` | 2-second timer (active monitoring only) | Callback + thread exit |
| 3 | `PPG_TOUCH` | PPG sensor touch/release interrupt | State machine transition |
| 4 | `TEMP_DATA_READY` | 1-second timer | Skin detection / temperature monitoring |
| 5 | `STATE_CHANGE` | `vsm_activate_monitoring()` / `vsm_deactivate_monitoring()` | State transition |
| 6 | `PPG_DATA_READY` | PPG sensor data interrupt (~1 Hz) | Main data processing pipeline |

**Synchronization primitives:**
- 7 binary semaphores (max count 1) for event signaling
- `k_timer` for temperature polling (1 Hz) and PPG watchdog (2 seconds)
- `k_heap` for PSP memory allocation
- `k_mutex` declared but not actively used in the current implementation

### 5.2 Bluetooth Thread (Optional)

| Property | Value |
|----------|-------|
| **Entry point** | `bluetooth_thread_entry()` in `bluetooth/thread.c` |
| **Stack size** | 4,096 bytes (`CONFIG_VSM_BT_THREAD_STACK_SIZE`) |
| **Priority** | 4 (`CONFIG_VSM_BT_THREAD_PRIORITY`) |
| **Event model** | `k_poll()` on 5 events |
| **Heap size** | 20,480 bytes (`CONFIG_VSM_BT_THREAD_HEAP_SIZE`) |
| **Name** | `"bluetooth"` |

**Events polled:**
- `CONNECTED` -- BLE connection established
- `DISCONNECTED` -- BLE connection lost (triggers system reboot!)
- `TIMER_1HZ` -- Vitals data transmission
- `TIMER_25HZ` -- Raw sensor data transmission
- `TIMER_32HZ` -- PSP-rate data transmission

**Data flow between threads:**
- Vitals thread enqueues data into 5 Zephyr FIFOs: `data_fifo_1hz`, `data_fifo_25hz`, `data_fifo_32hz`, `data_fifo_psp_32hz`, `data_fifo_psp_read_32hz`.
- Each FIFO item is heap-allocated from the Bluetooth thread's dedicated `k_heap`.
- Bluetooth thread dequeues and transmits via `bt_gatt_notify()`.
- Timer intervals are dynamically adjusted to compensate for processing time, maintaining target notification rates.

### 5.3 Thread Timing Diagram

```
Time (ms) 0        250       500       750       1000
          |---------|---------|---------|---------|
Vitals:   [PPG ISR + process..]                   [PPG ISR + process..]
          ^--- ~1Hz interrupt triggers pipeline

Temp:                         [read]              [read]
          |---- 1000ms timer ----|---- 1000ms ----|

BT 32Hz:  [tx][tx][tx][tx]...[tx][tx][tx][tx]...[tx]  (32 notifications/sec)
          |31ms|31ms|31ms|...

BT 1Hz:   [tx]                                    [tx]
          |------------- 1000ms ------------------|
```

---

## 6. State Machine

### 6.1 States

```
  +------+     touch      +-----------+    temp OK     +----------+    user cmd    +--------+
  | IDLE |--------------->| TOUCH_    |  (after skin   | SKIN_    |  activate_    | ACTIVE_ |
  |      |                | DETECTED  |  detection     | CONFIRMED|  monitoring() | MONITOR |
  +------+                +-----------+  period)       +----------+               +--------+
     ^                         |  ^                         |                         |
     |                  touch  |  | touch                   |                         |
     |                  lost   |  | regained                |                         |
     |                         v  |                         |                         |
     |                    +-----------+                     |                         |
     |                    | TOUCH_    |<--------------------+-------------------------+
     |                    | LOST      |     (touch lost from any active state)
     |                    +-----------+
     |                         |
     |                  temp confirms
     |                  deskin (immediate
     |                  in current impl)
     |                         v
     |                    +-----------+
     +--------------------| DESKIN_   |
       user cmd           | CONFIRMED |
       deactivate()       +-----------+
       (commented out)
```

### 6.2 State Transitions Detail

| From | Event | To | Actions |
|------|-------|----|---------|
| `IDLE` | PPG touch detected | `TOUCH_DETECTED` | Start temp timer (1 Hz), reset PSP algorithm |
| `TOUCH_DETECTED` | Temp in range for `skin_detection_period_ms` | `SKIN_CONFIRMED` | Callback: state changed |
| `TOUCH_DETECTED` | Temp verification timeout (2x period) | `IDLE` | Stop temp timer |
| `TOUCH_DETECTED` | Touch released | `TOUCH_LOST` | -- |
| `SKIN_CONFIRMED` | `vsm_activate_monitoring()` | `ACTIVE_MONITORING` | Start watchdog timer (2s) |
| `SKIN_CONFIRMED` | Touch released | `TOUCH_LOST` | -- |
| `ACTIVE_MONITORING` | Touch released | `TOUCH_LOST` | Stop watchdog timer |
| `ACTIVE_MONITORING` | Watchdog timeout (2s no PPG data) | Thread exit | HW error callback |
| `TOUCH_LOST` | Deskin temp confirmed | `DESKIN_CONFIRMED` | Stop temp timer |
| `TOUCH_LOST` | Touch regained | `TOUCH_DETECTED` | Reset PSP, restart skin detection |
| `DESKIN_CONFIRMED` | Touch regained | `TOUCH_DETECTED` | Reset PSP |
| `DESKIN_CONFIRMED` | `vsm_deactivate_monitoring()` | (commented out) | Would return to IDLE |

**Note:** The deskin detection logic in `_handle_temp_data_ready_event` for `VITALS_STATE_TOUCH_LOST` currently forces `temp_below_threshold = true` and the condition `if (true)`, meaning deskin is confirmed immediately upon touch loss without waiting for temperature drop. This appears to be a development shortcut.

### 6.3 Skin Detection Algorithm

Skin detection uses the MLX90614 infrared temperature sensor:
- PPG touch interrupt provides initial touch/release detection.
- Temperature must be within `[skin_temp_min_threshold_f, skin_temp_max_threshold_f]` for at least `skin_detection_period_ms` to confirm skin contact.
- Default thresholds: 70-100 F (sample app), valid range: 65-105 F (config.h).
- Default detection period: 1000 ms (sample app), valid range: 500-10000 ms.

---

## 7. Configuration

### 7.1 Kconfig Options

**Main Module:**

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `CONFIG_CK_MODULES_VSM` | bool | n | Master enable for VSM module |
| `CONFIG_CK_MODULES_VSM_BLE_SERVER` | bool | n | Enable BLE GATT server thread |
| `CONFIG_CK_MODULES_VSM_TESTS_ENABLED` | bool | n | Enable manufacturing test functions |
| `CONFIG_CK_MODULES_VSM_I2C_METRICS_ENABLED` | bool | n | Enable I2C bus performance metrics |

**Thread Configuration:**

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `CONFIG_VITALS_THREAD_PRIORITY` | int | 3 | Vitals thread priority (lower = higher priority) |
| `CONFIG_VSM_SENSOR_PRIORITY` | int | 8 | Sensor thread priority |
| `CONFIG_VSM_BUS_MUTEX` | bool | y | Guard I2C/SPI bus with mutex |
| `CONFIG_VSM_BT_THREAD_PRIORITY` | int | 4 | Bluetooth thread priority |
| `CONFIG_VSM_BT_THREAD_STACK_SIZE` | int | 4096 | Bluetooth thread stack (bytes) |
| `CONFIG_VSM_BT_THREAD_HEAP_SIZE` | int | 20480 | Bluetooth data heap (bytes) |

**Debug:**

| Option | Type | Default | Range | Description |
|--------|------|---------|-------|-------------|
| `CONFIG_CK_MODULES_VSM_THREADS_DEBUG_LEVEL` | int | 3 (INF) | 0-4 | Log level for VSM threads |
| `CONFIG_CK_MODULES_VSM_SENSOR_DEBUG_LEVEL` | int | 3 (INF) | 0-4 | Log level for sensor ops |

**BLE Stack Defaults (when BLE server enabled):**

| Option | Default | Description |
|--------|---------|-------------|
| `BT_DEVICE_NAME` | "Alpha Prototype" | BLE device name |
| `BT_DEVICE_APPEARANCE` | 833 | BLE appearance code |
| `BT_MAX_CONN` | 1 | Max simultaneous connections |
| `BT_PERIPHERAL_PREF_MIN_INT` | 6 (7.5 ms) | Min connection interval |
| `BT_PERIPHERAL_PREF_MAX_INT` | 6 (7.5 ms) | Max connection interval |
| `BT_L2CAP_TX_MTU` | 498 | L2CAP TX MTU |
| `BT_BUF_ACL_RX_SIZE` | 1024 | ACL RX buffer size |
| `BT_BUF_ACL_TX_SIZE` | 1024 | ACL TX buffer size |

### 7.2 Compile-Time Constants (config.h)

| Constant | Value | Description |
|----------|-------|-------------|
| `CONFIG_VITALS_THREAD_STACK_SIZE` | 8192 (4096*2) | Vitals thread stack |
| `CONFIG_PSP_MEMORY_SIZE` | 27000 | PSP heap size |
| `CONFIG_PSP_NUM_INPUT_METRICS` | 15 | Max PSP input metrics |
| `CONFIG_PSP_NUM_OUTPUT_METRICS` | 24 | Max PSP output metrics |
| `CONFIG_PSP_ALGORITHM_SAMPLES_PER_SECOND` | 32 | PSP processing rate |
| `CONFIG_ACCEL_SAMPLES_PER_SECOND` | 52 | IMU sample rate |
| `CONFIG_PPG_SAMPLES_PER_BATCH` | 32 | PPG samples per 1Hz batch |
| `CONFIG_VITALS_WARMUP_PERIOD` | 6000 | Warmup period (ms) |
| `CONFIG_VITALS_SKIN_TEMP_MIN_THRESHOLD_F` | 65.0 | Min valid skin temp |
| `CONFIG_VITALS_SKIN_TEMP_MAX_THRESHOLD_F` | 105.0 | Max valid skin temp |
| `CONFIG_VITALS_SKIN_DETECTION_MIN_PERIOD_MS` | 500 | Min detection period |
| `CONFIG_VITALS_SKIN_DETECTION_MAX_PERIOD_MS` | 10000 | Max detection period |
| `CONFIG_VITALS_DESKIN_DETECTION_MIN_PERIOD_MS` | 500 | Min deskin period |
| `CONFIG_VITALS_DESKIN_DETECTION_MAX_PERIOD_MS` | 10000 | Max deskin period |

### 7.3 Runtime Configuration (vsm_config_t)

| Field | Type | Description |
|-------|------|-------------|
| `p_ppg_dev` | `const struct device*` | PPG sensor device pointer |
| `p_imu_dev` | `const struct device*` | IMU device pointer |
| `p_temp_dev` | `const struct device*` | Temperature sensor device pointer |
| `p_ppg_enable_gpio` | `struct gpio_dt_spec` | GPIO to enable PPG subsystem power |
| `callback` | function pointer | Application callback for events |
| `callback_user_data` | `void*` | User data passed to callback |
| `skin_temp_min_threshold_f` | float | Minimum skin temperature (F) |
| `skin_temp_max_threshold_f` | float | Maximum skin temperature (F) |
| `skin_detection_period_ms` | uint32_t | Time to confirm skin contact |
| `deskin_detection_period_ms` | uint32_t | Time to confirm skin removal |

---

## 8. BLE Output Format

### 8.1 GATT Service

**Service UUID:** `12345678-1234-5678-1234-56789abcdef0`

### 8.2 Characteristics

| Characteristic | UUID Suffix | Rate | Data Type | Content |
|---------------|-------------|------|-----------|---------|
| Vitals 1Hz | `...def1` | 1 Hz | `vitals_data_t` (packed) | HR (int16), HR quality (int8), HR index (int16), SpO2 (int16), SpO2 quality (int8), SpO2 index (int16), Temp F (float) -- 12 bytes packed |
| PPG Intensity 25Hz | `...def2` | 25 Hz | `ppg_intensity_data_t` | Green intensity only (uint32) -- 4 bytes |
| PPG Intensity 32Hz | `...def3` | 32 Hz | `ppg_intensity_data_t` | Green intensity only (uint32) -- 4 bytes |
| Accel 25Hz | `...def4` | 25 Hz | `accelerometer_data_t` | X, Y, Z floats (m/s^2) -- 12 bytes |
| Accel 32Hz | `...def5` | 32 Hz | `accelerometer_data_t` | X, Y, Z floats (m/s^2) -- 12 bytes |
| PSP PPG 32Hz | `...def6` | 32 Hz | `psp_input_ppg_intensity_data_t` | Green intensity (uint16) -- 2 bytes |
| PSP Accel 32Hz | `...def7` | 32 Hz | `psp_input_accelerometer_data_t` | Padding (6 bytes) + X, Y, Z int16 -- 12 bytes |
| PSP Read PPG 32Hz | `...def8` | 32 Hz | (same as PSP PPG) | PSP-propagated green PPG |
| PSP Read Accel 32Hz | `...def9` | 32 Hz | (same as PSP Accel) | PSP-propagated accel |

**Notes:**
- Red and IR PPG channels are commented out in the BLE structs to reduce bandwidth. Only green is transmitted.
- All characteristics support NOTIFY and READ.
- Connection interval is set to 7.5 ms (minimum BLE spec), MTU is 498 bytes, allowing burst of multiple notifications per connection event.
- Each notification requires a CCC (Client Characteristic Configuration) write to enable.

### 8.3 BLE Data Streams Configuration

The Bluetooth thread configuration (`bluetooth_thread_config_t`) allows independently enabling/disabling each stream:
- `vitals_1hz_enabled`
- `sensor_data_25hz_enabled`
- `sensor_data_32hz_enabled`
- `psp_input_data_32hz_enabled`
- `psp_read_input_data_32hz_enabled`

### 8.4 BLE Bandwidth Estimate

At maximum with all streams enabled:
- 1 Hz vitals: 12 bytes/sec
- 25 Hz sensor data (accel + PPG): 25 * 16 = 400 bytes/sec
- 32 Hz sensor data: 32 * 16 = 512 bytes/sec
- 32 Hz PSP input: 32 * 14 = 448 bytes/sec
- 32 Hz PSP read-back: 32 * 14 = 448 bytes/sec
- **Total: ~1,820 bytes/sec** (well within BLE 5.0 throughput with 7.5 ms interval and large MTU)

---

## 9. Test Coverage

### 9.1 Cross-Talk Test (Implemented)

**File:** `tests/cross_talk.c`
**Purpose:** Measures light leakage from LEDs directly to the photodetector, bypassing the intended optical path. The device must be covered with a black rubber patch during this test.

**Procedure:**
1. Initialize PPG I2C communication (NOT the full driver -- uses direct register access).
2. Configure the PAH8151 sensor in factory test mode using vendor-provided register arrays (`pah_815x_verify_light_leakage_array`).
3. Take 5 samples at 60 ms intervals.
4. Average the ADC readings for each channel (Red, Green, IR).
5. Compare against thresholds.

**Pass Criteria (16-bit ADC):**

| Channel | Threshold | Condition |
|---------|-----------|-----------|
| Green | < 690 counts | Must be below |
| Red | < 82 counts | Must be below |
| IR | < 82 counts | Must be below |

**Result structure** provides per-channel pass/fail with raw counts and thresholds.

### 9.2 SNR Test (Stub)

**File:** `tests/snr.c`
**Status:** Not yet implemented (returns `passed = false`).

**Planned functionality (from api.h documentation):**
- Measures PPG sensor SNR at various light levels using a reflector at different positions.
- Uses a step callback to allow fixture adjustment between measurements.
- Reports per-step results: mean signal, standard deviation, SNR in dB.
- Pass criteria: Green > 80 dB, Red/IR > 85 dB at required operating current.

### 9.3 Reflectivity Test (Stub)

**File:** `tests/reflectivity.c`
**Status:** Not yet implemented (returns `passed = false`).

**Planned functionality (from api.h documentation):**
- Measures LED-to-photodiode reflectivity using a calibrated fixture.
- Supports "golden unit" mode (measure reference values) and DUT mode (compare to golden).
- Reports per-channel: ADC PPG level, maximum ADC, photodiode current, LED current, reflectivity ratio.

### 9.4 Test Infrastructure

- Tests are conditionally compiled via `CONFIG_CK_MODULES_VSM_TESTS_ENABLED` (also selects `CK_PAH8151_FACTORY_TEST`).
- The cross-talk test uses low-level PAH8151 register manipulation via `pah_815x_comm_write/read` functions, bypassing the Zephyr sensor API entirely.
- Tests are designed for production validation on the manufacturing line, not unit testing.

---

## 10. Potential Issues and Risks

### 10.1 ISR Duration Concerns

**Severity: High**

The `_ppg_data_ready_handler` runs in ISR context (sensor trigger callback) but performs substantial work:
- Reads the entire IMU FIFO (`sensor_sample_fetch` + multiple `sensor_channel_get` calls) -- this involves I2C transactions.
- Reads ~12 PPG channels for all 32 samples -- also I2C transactions.
- Total I2C bytes transferred in a single ISR: potentially hundreds of bytes at 400 kHz I2C.

At 400 kHz I2C, reading 500+ bytes takes approximately 10-15 ms. During this time, all lower-priority interrupts are blocked. This could cause:
- Missed UART characters.
- BLE connection event timing violations.
- Other sensor interrupt latency.

**Recommendation:** Move sensor reads to the vitals thread context using a deferred work pattern.

### 10.2 Deskin Detection Shortcut

**Severity: Medium**

In `_handle_temp_data_ready_event` for `VITALS_STATE_TOUCH_LOST`, the temperature check is hardcoded:
```c
bool temp_below_threshold = true;  // For now just force deskin
// ...
if (true) {  // immediately confirms deskin
```

This means the device immediately transitions to `DESKIN_CONFIRMED` upon touch loss without waiting for temperature confirmation. The intended behavior (commented out) would verify the temperature drops below the skin threshold for `deskin_detection_period_ms`.

### 10.3 Deactivate Monitoring Not Functional

**Severity: Medium**

The `STATE_REQUEST_DEACTIVATE_MONITORING` handler in `_handle_state_change_event` has its implementation entirely commented out:
```c
case STATE_REQUEST_DEACTIVATE_MONITORING:
    if (p_thread->state == VITALS_STATE_DESKIN_CONFIRMED) {
        // Entire block commented out
    }
```

Once monitoring is activated, the only way to return to IDLE is through hardware error, watchdog timeout, or `vsm_deinit()`.

### 10.4 Static Variable in Transform

**Severity: Medium**

`_convert_raw_samples_for_psp()` uses a static variable `samples_since_last_check` for gain adjustment timing. This persists across PSP resets and could cause incorrect gain adjustment timing after a state transition. The calibration state (`ppg_cal_state.cal_timer`) is only reset when it equals 0, meaning a full PSP reset does not clear the calibration state in the `vsm_t` structure.

### 10.5 BLE Disconnection Causes System Reboot

**Severity: High**

In `process_event_disconnected()`, the very first action is:
```c
LOG_WRN("Disconnected from device, rebooting in 2 seconds");
k_sleep(K_SECONDS(2));
sys_reboot(0);
```

This means any BLE disconnection causes a full system reboot. The reconnection and cleanup code below this `sys_reboot` call is unreachable dead code. This is clearly a development workaround, not production behavior.

### 10.6 Timestamp Domain Mismatch Risk

**Severity: Medium**

The accelerometer downsampling relies on timestamp matching between PPG and IMU samples. PPG timestamps are reconstructed from sensor registers (64-bit combining val1 and val2), while IMU timestamps come from the LSM6DSO hardware FIFO. If these timestamp domains are not synchronized (e.g., different clock sources), the weighted interpolation could produce incorrect results.

The code has fallback mechanisms (nearest neighbor, zero-order hold), but persistent timestamp skew would degrade accelerometer alignment quality throughout the measurement session.

### 10.7 Buffer Overflow Risk in IMU Read

**Severity: Low-Medium**

The IMU sample count check allows up to `CONFIG_ACCEL_SAMPLES_PER_SECOND + 2` (54) samples, but the buffer `accel_interrupt_samples` is sized to `CONFIG_ACCEL_SAMPLES_PER_SECOND` (52). The storage loop uses:
```c
for (int i = 0; i < count && i < p_thread->imu_sample_count; i++)
```
where `imu_sample_count` was set to `count` (which passed the 54 check). This means if 53 or 54 samples arrive, the loop would try to write beyond the 52-element buffer. However, the VLA declarations on the stack (`struct sensor_value timestamp[count]`) would correctly hold all samples, and the channel_get calls fill them. The issue is only in the copy-to-thread-buffer loop which is bounded by `imu_sample_count`.

**Actually:** Looking more carefully, the loop condition `i < count && i < p_thread->imu_sample_count` is equivalent to `i < count` since they are set equal, so the buffer can overflow by up to 2 elements.

### 10.8 PPG Warmup Period Interaction

**Severity: Low**

The 6-second warmup period (`CONFIG_VITALS_WARMUP_PERIOD`) starts from `touch_detection_start_time`, but this timestamp is set during the `TOUCH_DETECTED` state's temperature verification flow. The warmup flag `is_warmup_period` is checked in `_handle_ppg_data_ready_event` but is never explicitly set to `true` in the code -- it would need to be initialized or set somewhere during the touch detection to active monitoring transition.

### 10.9 Memory Leak Risk in BLE Thread

**Severity: Low**

The `bluetooth_send_sensor_data` function allocates from `data_heap` for every data item. If the Bluetooth thread cannot keep up (e.g., FIFO fills faster than BLE can transmit), allocations will fail with a 20 ms timeout. The error path correctly reports the failure but does not implement backpressure. If the vitals thread continues to enqueue data while BLE cannot drain, the heap could become fragmented over time.

### 10.10 Sequence Number Wrapping

**Severity: Low**

The PSP metric sequence number (`p_thread->sequence_number`) is a `uint32_t` that increments each processing cycle (approximately 1 Hz). It would take ~136 years to overflow, so this is not a practical concern. However, the PSP preamble only uses the low 8 bits (`data[3] = p_thread->sequence_number`), so the PSP library sees wrapping every 256 seconds. This should be fine as PSP likely only uses it for ordering/deduplication.

### 10.11 No Gyroscope Data Used

**Severity: Informational**

The IMU read collects both accelerometer and gyroscope data (X/Y/Z for both), but only accelerometer data is used in the processing pipeline. Gyroscope data is read and discarded. The PSP library does support gyroscope input (`PSP_METRIC_ID_GYRO`), but it is not being fed. This represents unused I2C bandwidth and processing time in the ISR.

### 10.12 Sample App Runs Init/Deinit in Loop

**Severity: Informational**

The sample application (`samples/simple/src/main.c`) runs VSM init, sleeps 20 seconds, then deinits, sleeps 5 seconds, and repeats forever. This is useful for testing the init/deinit lifecycle but would not be how a real application operates (it would typically keep VSM running and rely on the state machine).

---

## Appendix A: Memory Budget

| Component | Size | Notes |
|-----------|------|-------|
| Vitals thread stack | 8,192 bytes | `CONFIG_VITALS_THREAD_STACK_SIZE` |
| Vitals thread struct (`vsm_t`) | ~30,000 bytes | Includes PSP heap (27,000), sample buffers, etc. |
| PSP heap | 27,000 bytes | For PSP library instance memory |
| PSP ROM | ~77,000 bytes | Flash ROM at 0xE0000 |
| BLE thread stack | 4,096 bytes | `CONFIG_VSM_BT_THREAD_STACK_SIZE` |
| BLE thread struct | ~21,000 bytes | Includes data heap (20,480) |
| BLE data heap | 20,480 bytes | `CONFIG_VSM_BT_THREAD_HEAP_SIZE` |
| **Total RAM (vitals only)** | **~38 KB** | |
| **Total RAM (with BLE)** | **~63 KB** | |

## Appendix B: Key Source File Cross-References

| Functionality | Primary File | Related Files |
|--------------|-------------|---------------|
| Public API | `api.h` | `types.h`, `output.h` |
| Thread event loop | `thread.c` | `priv.h`, `utils/api.h` |
| Sensor init/deinit | `init.c`, `deinit.c` | `api.h` |
| State control | `monitor.c` | `api.h` |
| Accel downsampling | `utils/transform.c` | `types.h`, `config.h` |
| PPG scaling | `utils/transform.c` | `types.h` |
| PSP interface | `utils/psp.c` | `lib/inc/psp.h`, `lib/inc/psp_map.h` |
| BLE data output | `utils/ble.c` | `bluetooth/types.h`, `bluetooth/thread.h` |
| BLE GATT server | `bluetooth/thread.c` | `bluetooth/types.h` |
| Cross-talk test | `tests/cross_talk.c` | `api.h`, PAH8151 factory test headers |
| Build system | `CMakeLists.txt` (all levels) | `Kconfig` |
| Sample usage | `samples/simple/src/main.c` | `samples/simple/prj.conf` |
