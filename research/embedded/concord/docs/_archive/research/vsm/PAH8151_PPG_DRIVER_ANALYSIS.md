# PAH8151 PPG Sensor Driver -- Deep Analysis

**Date:** 2026-02-09
**Sensor:** PixArt PAH8151 Photoplethysmography (PPG) Optical Sensor
**Target Platform:** Alpha Wearable (nRF52840, Zephyr RTOS)
**Driver Location:** `_fw_build/pah8151_drv/drivers/corekinect/sensors/pah8151/`

---

## Table of Contents

1. [Sensor Architecture](#1-sensor-architecture)
2. [Operating Modes](#2-operating-modes)
3. [Sampling Rate Configuration](#3-sampling-rate-configuration)
4. [LED Configuration](#4-led-configuration)
5. [Channel Configuration](#5-channel-configuration)
6. [FIFO Operation](#6-fifo-operation)
7. [Register Defaults](#7-register-defaults)
8. [I2C Interface](#8-i2c-interface)
9. [Data Format](#9-data-format)
10. [Factory Test Thresholds](#10-factory-test-thresholds)
11. [Potential Issues and Tuning Opportunities](#11-potential-issues-and-tuning-opportunities)

---

## 1. Sensor Architecture

The PAH8151 driver is organized in a three-tier architecture:

```
+------------------------------------------------------------+
|  CK Zephyr Driver Wrapper (pah8151.c / pah8151.h)         |
|  - Zephyr sensor API: sample_fetch, channel_get,           |
|    trigger_set, attr_set                                    |
|  - Sensor processing thread (k_thread)                     |
|  - PPG sample buffer (32 samples)                          |
|  - Touch/PPG trigger callbacks                             |
+------------------------------------------------------------+
            |
            v
+------------------------------------------------------------+
|  PixArt SDK Main Layer (pah_815x_main.c / pah_815x_main.h)|
|  - State machine (AUTO_MODE, ALWAYS_PPG, TOUCH_ONLY)      |
|  - DRI (interrupt) and POLLING work modes                  |
|  - PPG enable/disable based on touch detection             |
|  - Global buffer[512] for FIFO reads                       |
|  - ppg_data_out accumulation and reporting                 |
+------------------------------------------------------------+
            |
            v
+------------------------------------------------------------+
|  PixArt SDK Core (pah_815x.c / pah_815x.h)                |
|  - Sensor initialization/start/stop lifecycle              |
|  - FIFO read with chunked transfers                        |
|  - Watermark management                                    |
|  - Touch data reading (IR and capacitive)                  |
|  - Auto-exposure info reading                              |
|  - Timing tuning (rpt_divider adjustment)                  |
|  - PPG auto power saving                                   |
+------------------------------------------------------------+
            |
            v
+------------------------------------------------------------+
|  HAL Layer (pah_815x_hal.c / pah_815x_hal.h)              |
|  - Bank-switched register access (banks 0-9)               |
|  - Power control, soft reset                               |
|  - Register array write sequences                          |
|  - PPG channel value extraction from register arrays       |
|  - AE info reading (exposure time, LED DAC per channel)    |
|  - PPG data extraction from FIFO bytes                     |
|  - Frame rate calculation: 32000 / rpt_divider             |
|  - Timing tuning adjustment algorithm                      |
+------------------------------------------------------------+
            |
            v
+------------------------------------------------------------+
|  Communication Layer (pah_815x_comm.c / pah_815x_comm.h)   |
|  - Zephyr I2C bus operations                               |
|  - Hardcoded address 0x15                                  |
|  - Bank caching (two separate caches: _curr_bank,          |
|    _curr_bank_2)                                           |
|  - Optional bus mutex (CONFIG_CK_PAH8151_BUS_MUTEX)        |
|  - Retry logic: 3 attempts, 5ms delay between retries     |
+------------------------------------------------------------+
```

### Source File Inventory

| File | Layer | Purpose |
|------|-------|---------|
| `pah8151.c` | CK Wrapper | Zephyr sensor API, thread, triggers |
| `pah8151.h` | CK Wrapper | Public API, channel/trigger/attr enums, data structures |
| `pah8151_reg.h` | CK Wrapper | CK-level register and constant definitions |
| `PAH8151/pah_sensor/pah_815x_main.c` | SDK Main | State machine, mode management |
| `PAH8151/pah_sensor/pah_815x_main.h` | SDK Main | State structures, enums, function declarations |
| `PAH8151/pah_sensor/pah_815x.c` | SDK Core | Sensor lifecycle, FIFO, watermark |
| `PAH8151/pah_sensor/pah_815x.h` | SDK Core | Core state/config structures, API declarations |
| `PAH8151/pah_sensor/pah_815x_hal.c` | HAL | Register access, data extraction, timing tuning |
| `PAH8151/pah_sensor/pah_815x_hal.h` | HAL | HAL function declarations |
| `PAH8151/pah_sensor/pah_815x_comm.c` | Comm | Zephyr I2C implementation |
| `PAH8151/pah_sensor/pah_815x_comm.h` | Comm | Comm function declarations |
| `PAH8151/pah_sensor/pah_815x_config.h` | Config | Feature flags, watermarks, compile options |
| `PAH8151/pah_sensor/pah_815x_define.h` | Config | Register addresses, constants, bit fields |
| `PAH8151/pah_sensor/pah_815x_data_types.h` | Config | Additional type definitions |
| `PAH8151/pah_sensor/pah_815x_reg_default.h` | Config | All register initialization arrays (5 presets) |
| `PAH8151/pah_sensor/pah_815x_reg_cap_cal.h` | Config | Capacitive calibration register arrays |
| `PAH8151/pah/pah_plat.h` | Platform | Platform abstraction interfaces |
| `PAH8151/pah/pah_reg.h` | Platform | Register array type and setup macro |
| `PAH8151/pah/pah_ret.h` | Platform | Return code enum |
| `PAH8151/pah/pah_util.h` | Platform | Bit manipulation macros |
| `PAH8151/pah_factory_test/pah_815x_factory_test_v1.c` | Factory | Zephyr-adapted factory test |
| `PAH8151/pah_factory_test/pah_815x_factory_test_v2.c` | Factory | nRF-native factory test |
| `PAH8151/pah_factory_test/pah_815x_factory_test_v1.h` | Factory | Test enums and structures |
| `PAH8151/pah_factory_test/pah_815x_verify_reg_v1.h` | Factory | Register verification declarations |
| `PAH8151/pah_factory_test/demo_factory_v1.c` | Factory | Demo factory test sequence |

### Thread Architecture

The CK wrapper creates a dedicated sensor processing thread:

- **Stack size:** 16,384 bytes (4096 * 4)
- **Thread priority:** Configurable via `CONFIG_CK_PAH8151_THREAD_PRIORITY` (default: 8)
- **Thread name:** `pah8151_thread`
- **Signaling:** Uses `k_poll` with two events:
  - `data_sem` -- signaled by GPIO ISR when sensor interrupt fires
  - `exit_sem` -- signaled by deinit to request thread shutdown
- **Data protection:** `k_mutex data_mutex` protects `ppg_samples[]` buffer

The thread loop calls `pah_sensor_task()` which dispatches to either `demo_data_ready_interrupt()` (DRI mode) or `demo_polling()` (polling mode) in the PixArt SDK layer.

---

## 2. Operating Modes

### Work Modes (Data Acquisition Strategy)

| Work Mode | Enum | Value | Description |
|-----------|------|-------|-------------|
| Idle | `PAH815X_WORK_IDLE` | 0 | No active acquisition |
| DRI | `PAH815X_WORK_DRI` | 1 | Data Ready Interrupt -- interrupt-driven |
| Polling | `PAH815X_WORK_POLLING` | 2 | Periodic polling at `POLLING_PERIOD_MS` (500ms) |

**Current configuration: DRI mode.** The sensor asserts its interrupt pin when the FIFO watermark is reached, the GPIO ISR sets `has_interrupt = true` and signals the processing thread via `data_sem`.

### Operate Modes (Functional Behavior)

| Operate Mode | Enum | Value | Description |
|--------------|------|-------|-------------|
| Idle | `PAH815X_INIT_IDLE` | 0 | No sensing |
| Auto Mode | `PAH815X_INIT_AUTO_MODE` | 1 | Touch detection controls PPG on/off |
| Always PPG | `PAH815X_INIT_ALWAYS_PPG` | 2 | PPG always on, touch also enabled |
| Touch Only | `PAH815X_INIT_TOUCH_ONLY` | 3 | Only touch sensing, no PPG |
| Cap Cal NoTouch | `PAH815X_INIT_CAP_CAL_NOTOUCH` | 4 | Capacitive calibration without touch |
| Cap Cal Touch | `PAH815X_INIT_CAP_CAL_TOUCH` | 5 | Capacitive calibration with touch |

**Current configuration: AUTO_MODE.** Behavior:
1. Sensor starts with only touch detection enabled.
2. `touch_last_is_touched` is initialized to `2` (OFF).
3. When a touch interrupt reports `ON` (1), `enable_ppg_sensor()` is called.
4. When a touch interrupt reports `OFF` (2), `disable_ppg_sensor()` is called.
5. This saves power by only running LEDs when the device is on skin.

### Initialization Call

From `pah8151.c` line 667:

```c
pah_sensor_start(PAH815X_WORK_DRI, PAH815X_INIT_AUTO_MODE,
                 PAH815X_REG_SETTING_5,
                 PPG_WATERMARK_SpO2,
                 1000 / PPG_WATERMARK_SpO2);
```

Parameters:
- Work mode: DRI (interrupt-driven)
- Operate mode: Auto (touch controls PPG)
- Register setting: 5 (3-channel, 32Hz)
- Interrupt report num: 32 (PPG_WATERMARK_SpO2)
- Sample period: 31 (1000/32, in ms)

### PPG LED On Modes

| Mode | Enum | Description |
|------|------|-------------|
| Instantly | `PAH_815X_PPG_LED_ON_INSTANTLY` | LED activates immediately when PPG is enabled |
| Deferred | `PAH_815X_PPG_LED_ON_DEFERRED` | LED activates only after first touch detection |

### PPG Auto Power Saving

When `enable_ppg_auto_power_saving` is set, the SDK enters a low-power state (PPG PS mode) that reduces exposure times and LED DAC to minimum values when no touch is detected, then restores full settings when touch resumes. This is controlled by writing reduced register values for `max_expotime` and `led_dac_max` to all channels.

---

## 3. Sampling Rate Configuration

### Frame Rate Calculation

```
frame_rate_hz = 32000 / rpt_divider
```

Where `32000` is the `MAGIC_NUM` constant and `rpt_divider` is a 13-bit register value in Bank 2 registers `0x73` (low byte) and `0x74` (high 5 bits).

### Register Configuration Presets and Sample Rates

| Preset | Macro | rpt_divider | Sample Rate | Channels |
|--------|-------|-------------|-------------|----------|
| Config 1 | `PAH_815X_REG_PPG_ENABLE_1` | 0x03E8 (1000) | 32 Hz | 1 (Green) |
| Config 2 | `PAH_815X_REG_PPG_ENABLE_2` | 0x0500 (1280) | 25 Hz | 1 (Green) |
| Config 3 | `PAH_815X_REG_PPG_ENABLE_3` | 0x0500 (1280) | 25 Hz | 2 (Green + IR) |
| Config 4 | `PAH_815X_REG_PPG_ENABLE_4` | 0x0500 (1280) | 25 Hz | 2 (IR + Red, SpO2) |
| Config 5 | `PAH_815X_REG_PPG_ENABLE_5` | 0x03E8 (1000) | 32 Hz | 3 (Green + Red + IR) |

**Current configuration: Config 5 (32 Hz, 3-channel).**

### Watermark Presets

Defined in `pah_815x_config.h`:

| Preset | Macro | Value | Use Case |
|--------|-------|-------|----------|
| Default | `PPG_WATERMARK` | 20 | Basic HR |
| SpO2 | `PPG_WATERMARK_SpO2` | 32 | SpO2 measurement (currently used) |
| HRV | `PPG_WATERMARK_HRV` | 25 | Heart Rate Variability |
| RR | `PPG_WATERMARK_RR` | 25 | Respiratory Rate |

**Current configuration: SpO2 watermark (32 samples).**

With 3 channels at 32 Hz and watermark of 32, the interrupt fires every 1 second (32 samples / 32 Hz).

### Maximum Watermark Calculation

```
max_watermark = FIFO_SIZE / (ch_num * data_size)
             = 1584 / (3 * 4)
             = 132 samples
```

### Timing Tuning

Enabled via `#define Timing_Tuning` in `pah_815x_config.h`.

The timing tuning algorithm adjusts the `rpt_divider` register to lock the actual sample rate to the target. It uses a weighted average approach:

```c
time_target_avg = ((_time_target * 3) + (actual_sampling_time)) / 4;
```

Key behavior:
- Skips the first callback to establish a baseline (`time_target_init` flag)
- Applies a deadband of +/- 0.02 of target (e.g., 31.25 +/- 0.02 ms for 32 Hz)
- Rejects adjustments if error exceeds 20% of target (likely a measurement glitch)
- Reads current `rpt_divider`, calculates correction factor, writes new value
- Sets update flag register (`0x7D`) to apply changes immediately

---

## 4. LED Configuration

### LED-to-Channel Assignment

From register defaults in `pah_815x_reg_default.h` (Config 5):

| SDK Channel | Register | Value | LED Color | Wavelength |
|-------------|----------|-------|-----------|------------|
| Channel A | B2:0x4C | 0x12 | Green | ~520 nm |
| Channel B | B2:0x57 | 0x18 | Red | ~660 nm |
| Channel C | B2:0x62 | 0x11 | IR | ~880 nm |
| Channel D | B1:0x0C | (unused) | N/A | N/A |

The LED register value format is:
- Bits [3:0]: `led_bias_sel` -- selects LED bias configuration
- Bits [7:4]: Additional LED driver settings

### LED DAC Maximum Values

| Channel | Register | Default Max | Current (max) |
|---------|----------|-------------|---------------|
| Channel A (Green) | B2:0x4B | 0x3F (63) | 63 * 0.4 = 25.2 mA |
| Channel B (Red) | B2:0x56 | 0x7F (127) | 127 * 0.4 = 50.8 mA |
| Channel C (IR) | B2:0x61 | 0x7F (127) | 127 * 0.4 = 50.8 mA |
| Channel D | B1:0x0B | 0x1F (31) | 31 * 0.4 = 12.4 mA |

**LED current formula:** `current_mA = DAC_value * 0.4`

### Auto-Exposure (AE) Control

Each channel has an AE register at:
- Channel A: B2:0x4D (value 0x03)
- Channel B: B2:0x58 (value 0x03)
- Channel C: B2:0x63 (value 0x03)
- Channel D: B1:0x10 (value 0x03)

The AE value `0x03` means both bits are set:
- Bit 0: `ae_enable` -- automatic exposure adjustment enabled
- Bit 1: `auto_FP_enable` -- automatic frame period adjustment enabled

### Maximum Exposure Times

Per channel, exposure time is configured by three registers (3 bytes, 24-bit value):

| Channel | Max Expo Reg 1 | Max Expo Reg 2 | Max Expo Reg 3 |
|---------|----------------|----------------|----------------|
| A (Green) | B2:0x48 = 0x00 | B2:0x49 = 0x02 | B2:0x4A = 0x00 |
| B (Red) | B2:0x53 = 0x19 | B2:0x54 = 0x00 | B2:0x55 = 0x00 |
| C (IR) | B2:0x5E = 0x19 | B2:0x5F = 0x00 | B2:0x60 = 0x00 |

Exposure time raw value * 0.25 = microseconds.

---

## 5. Channel Configuration

### Channel Enable/Disable

Each channel is controlled by a register with two critical bits:
- Bit 0: `CH_X_ENABLE` -- enables the channel
- Bit 1: `CH_X_FIFO_WRITE` -- enables FIFO data writing for the channel

A channel is considered "active" only when both bits are set (enable=1, fifo_write=1), i.e., register value `0x03`.

### Config 5 Channel Setup (Currently Used)

```
Channel A (Green): B2:0x51 = 0x03 (enabled + FIFO write)
Channel B (Red):   B2:0x5C = 0x03 (enabled + FIFO write)
Channel C (IR):    B2:0x67 = 0x03 (enabled + FIFO write)
Channel D:         B1:0x11 = 0x00 (disabled)
Touch (T):         B2:0x6C = 0x01 (enabled, no FIFO write)
```

### Channel Data Order in FIFO

When multiple channels are enabled, their data is interleaved per sample:

```
Sample 0: [Ch_A data (4 bytes)] [Ch_B data (4 bytes)] [Ch_C data (4 bytes)]
Sample 1: [Ch_A data (4 bytes)] [Ch_B data (4 bytes)] [Ch_C data (4 bytes)]
...
```

With Config 5 (3 channels):
- FIFO index 0 = Channel A (Green)
- FIFO index 1 = Channel B (Red)
- FIFO index 2 = Channel C (IR)

### Channel Mapping in CK Wrapper

From `pah8151.c` line 205-208:

```c
/* Channel mapping: A=Green, B=Red, C=IR */
data->ppg_samples[i].green_intensity = raw_data[i * ppg_data.ch_num + 0];  // Ch A
data->ppg_samples[i].red_intensity   = raw_data[i * ppg_data.ch_num + 1];  // Ch B
data->ppg_samples[i].ir_intensity    = raw_data[i * ppg_data.ch_num + 2];  // Ch C
```

### Custom Zephyr Sensor Channels

Defined in `pah8151.h`:

| Channel Enum | Description |
|--------------|-------------|
| `SENSOR_CHAN_PAH8151_SAMPLE_COUNT` | Number of samples in batch |
| `SENSOR_CHAN_PAH8151_TIMESTAMP` | Per-sample timestamp (ms since boot) |
| `SENSOR_CHAN_PAH8151_RED_INTENSITY` | Red channel raw ADC |
| `SENSOR_CHAN_PAH8151_RED_EXPO_US` | Red exposure time (us) |
| `SENSOR_CHAN_PAH8151_RED_DAC` | Red LED DAC (0-255) |
| `SENSOR_CHAN_PAH8151_RED_CURR_MA` | Red LED current (mA) |
| `SENSOR_CHAN_PAH8151_GREEN_INTENSITY` | Green channel raw ADC |
| `SENSOR_CHAN_PAH8151_GREEN_EXPO_US` | Green exposure time (us) |
| `SENSOR_CHAN_PAH8151_GREEN_DAC` | Green LED DAC (0-255) |
| `SENSOR_CHAN_PAH8151_GREEN_CURR_MA` | Green LED current (mA) |
| `SENSOR_CHAN_PAH8151_IR_INTENSITY` | IR channel raw ADC |
| `SENSOR_CHAN_PAH8151_IR_EXPO_US` | IR exposure time (us) |
| `SENSOR_CHAN_PAH8151_IR_DAC` | IR LED DAC (0-255) |
| `SENSOR_CHAN_PAH8151_IR_CURR_MA` | IR LED current (mA) |
| `SENSOR_CHAN_PAH8151_TOUCH` | Touch detection status |

---

## 6. FIFO Operation

### FIFO Parameters

| Parameter | Value | Source |
|-----------|-------|--------|
| Total FIFO size | 1584 bytes | `PAH_815X_FIFO_SIZE` |
| Data size per channel | 4 bytes | `PAH_815X_DEFAULT_PPG_DATA_SIZE` |
| Max channels | 4 (A, B, C, D) | `PAH_815X_MAX_PPG_CH_NUM` |
| Current channels | 3 (A, B, C) | Config 5 |
| Bytes per sample | 12 (3 * 4) | ch_num * data_size |
| Max samples (3ch) | 132 | 1584 / 12 |
| Current watermark | 32 | `PPG_WATERMARK_SpO2` |

### FIFO Read Sequence

1. Switch to Bank 2
2. Enable manual clock: write `0x03` to `B2:0x40`
3. Enable PPG FIFO chip select: write `0x0E` to `B2:0x3C`
4. Read data in chunks from `B2:0x7B` (FIFO data register)
   - Chunk size limited by `plat->comm.max_length` (252 bytes)
   - Chunks are aligned to `sample_size` boundaries
5. Disable FIFO chip select: write `0x0F` to `B2:0x3C`
6. Disable manual clock: write `0x04` to `B2:0x40`
7. Clear FIFO: write `0x03` to `B2:0x39`

### FIFO Read Buffer

The SDK uses a global `uint8_t buffer[512]` in `pah_815x_main.c`. With 3 channels at 4 bytes each and watermark of 32:

```
Required bytes = 32 * 3 * 4 = 384 bytes
Buffer size    = 512 bytes
Margin         = 128 bytes (sufficient)
```

### Interrupt-Driven Flow

1. Sensor fills FIFO with PPG data samples.
2. When sample count reaches watermark (32), sensor asserts INT pin.
3. Zephyr GPIO callback fires, sets `has_interrupt = true`, gives `data_sem`.
4. Sensor thread wakes from `k_poll`, calls `pah_sensor_task()`.
5. `demo_data_ready_interrupt()` calls `process_interrupt()`:
   - Reads interrupt status register (Bank 2, `0x3A`)
   - If PPG data ready: reads sample count from FIFO num register, reads FIFO data
   - If touch interrupt: reads touch flag and updates touch status
   - If FIFO overflow: logs error, clears FIFO
6. In AUTO_MODE: enables/disables PPG based on touch state change.

### FIFO Overflow Handling

The interrupt status union (`pah_815x_int_status`) has a `ppg_fifo_overflow` bit. The macro `PAH_815X_FIFO_IS_OVERFLOW()` checks `data[1] & 0x07` for any overflow flag (PPG, IR, or CAP). On overflow, the SDK calls `process_flush()` which clears the FIFO.

---

## 7. Register Defaults

### Initialization Sequence

The sensor initialization writes registers across multiple banks in this order:

**`PAH_815X_REG_INIT` array (from `pah_815x_reg_default.h`):**

1. **Bank 4:** GPIO configuration
   - GPIO0 mode: `0x01` (output)
   - GPIO1 mode: `0x00`
   - GPIO2 mode: `0x00`
   - GPIO3 mode: `0x00`
   - GPIO IOEB: `0x01`

2. **Bank 1:** Touch detection thresholds
   - IR touch threshold: `0x00, 0x08, 0x00` (2048 decimal)
   - IR no-touch threshold: `0x00, 0x04, 0x00` (1024 decimal)
   - Touch pixel: `0x80, 0x02` (640 decimal)
   - Touch frame period: `0x00, 0x08` (2048 decimal)
   - Channel T dummy mode enabled

3. **Bank 2:** Core sensor configuration
   - FIFO clear: `0x03` (clear PPG and IR FIFOs)
   - FIFO checksum: `0x0F` (disabled)
   - INT mode: `0x03`
   - INT mask: enables IR touch, IR no-touch, PPG data ready, PPG overflow
   - PPG normalization mode
   - Channel T configuration: enabled, exposure, LED DAC, ADC OSR, rpt_divider
   - WR data turn: `0x13`
   - RPT timer enable: `0x01`

4. **Bank 7:** Analog configuration
   - IPGA control: `0xC1`
   - Bandgap level: `0x02`

### Shutdown Sequence

`PAH_815X_REG_DEINIT`:
1. Bank 4: Global reset `0x00`
2. Bank 4: Power down mode `0x01`

### PPG Enable Register Values (Config 5 -- Current)

Key register writes for 3-channel 32 Hz configuration:

```
Bank 2:
  0x39 = 0x03    # Clear FIFOs

  # Channel A (Green)
  0x48 = 0x00    # Max expo time byte 1
  0x49 = 0x02    # Max expo time byte 2
  0x4B = 0x3F    # DAC max = 63
  0x4C = 0x12    # LED A = Green (bias_sel=1, cfg=2)
  0x4D = 0x03    # AE enabled + auto_FP enabled
  0x4E = 0xE8    # Frame period low
  0x4F = 0x03    # Frame period high → 0x03E8 = 1000
  0x51 = 0x03    # Ch A enabled + FIFO write

  # Channel B (Red)
  0x53 = 0x19    # Max expo time byte 1
  0x54 = 0x00    # Max expo time byte 2
  0x56 = 0x7F    # DAC max = 127
  0x57 = 0x18    # LED B = Red (bias_sel=1, cfg=8)
  0x58 = 0x03    # AE enabled
  0x59 = 0xE8    # Frame period low
  0x5A = 0x03    # Frame period high → 0x03E8 = 1000
  0x5C = 0x03    # Ch B enabled + FIFO write

  # Channel C (IR)
  0x5E = 0x19    # Max expo time byte 1
  0x5F = 0x00    # Max expo time byte 2
  0x61 = 0x7F    # DAC max = 127
  0x62 = 0x11    # LED C = IR (bias_sel=1, cfg=1)
  0x63 = 0x03    # AE enabled
  0x64 = 0xE8    # Frame period low
  0x65 = 0x03    # Frame period high → 0x03E8 = 1000
  0x67 = 0x03    # Ch C enabled + FIFO write

  # Timing
  0x73 = 0xE8    # RPT divider low
  0x74 = 0x03    # RPT divider high → 0x03E8 = 1000 → 32 Hz
  0x75 = 0x13    # WR data turn
  0x76 = 0x01    # ON/OFF = on
  0x7C = 0x01    # RPT timer enable
  0x7D = 0x01    # Update flag
```

### PPG Disable Register Values

```
Bank 2:
  0x51 = 0x00    # Ch A disabled
  0x5C = 0x00    # Ch B disabled
  0x67 = 0x00    # Ch C disabled
  0x39 = 0x01    # Clear PPG FIFO only
```

### Other Configuration Presets Summary

| Preset | rpt_divider | Rate | Ch A (Green) | Ch B (Red) | Ch C (IR) | Ch D |
|--------|-------------|------|--------------|------------|-----------|------|
| Config 1 | 1000 | 32 Hz | 0x03 (on) | 0x00 (off) | 0x00 (off) | 0x00 |
| Config 2 | 1280 | 25 Hz | 0x03 (on) | 0x00 (off) | 0x00 (off) | 0x00 |
| Config 3 | 1280 | 25 Hz | 0x03 (on) | 0x00 (off) | 0x03 (on) | 0x00 |
| Config 4 | 1280 | 25 Hz | 0x00 (off) | 0x03 (on) | 0x03 (on) | 0x00 |
| Config 5 | 1000 | 32 Hz | 0x03 (on) | 0x03 (on) | 0x03 (on) | 0x00 |

---

## 8. I2C Interface

### Bus Configuration

| Parameter | Value | Source |
|-----------|-------|--------|
| I2C address | 0x15 (7-bit) | Hardcoded in `pah_815x_comm.c` and `PAH_815X_DEFAULT_I2C_SLAVE_ADDR` |
| Max transfer size | 252 bytes | `plat->comm.max_length` in `pah_sensor_init()` |
| Product ID | 0x8151 | `PAH_815X_PRODUCT_ID` |
| Communication type | I2C | `PAH_PLAT_COMM_I2C` |

### Register Banking

The PAH8151 uses a bank-switched register architecture accessed via register `0x7F`:

| Bank | Value | Purpose |
|------|-------|---------|
| Bank 0 | 0x00 | (default) |
| Bank 1 | 0x01 | Channel D config, touch thresholds, frame periods |
| Bank 2 | 0x02 | Product ID, interrupt status, channel A/B/C config, FIFO, AE info |
| Bank 4 | 0x04 | GPIO, power control, global reset |
| Bank 7 | 0x07 | Analog (IPGA, bandgap, drives count) |
| Bank 9 | 0x09 | Capacitive sensing (LPF, LLOB, IIR, noise avoidance) |

### Bank Caching

The communication layer maintains **two separate bank caches**:

1. `_curr_bank` -- used by `pah_815x_comm_write()` / `pah_815x_comm_read()` (direct functions)
2. `_curr_bank_2` -- used by `pah_plat_comm_i2c_write()` / `pah_plat_comm_i2c_read()` (platform abstraction)

Both skip the bank switch I2C transaction if the requested bank matches the cached value. This is a potential issue -- see Section 11.

### Retry Logic

Without bus mutex (`CONFIG_CK_PAH8151_BUS_MUTEX` not defined):
- Max retries: 3 (`MAX_I2C_TRIES`)
- Delay between retries: 5 ms (`k_msleep(5)`)
- Logs warning on each retry, error on final failure

With bus mutex:
- Uses `k_mutex_lock(_p_bus_mutex, K_FOREVER)` for thread safety
- No retry logic -- single attempt per operation
- Warning logged on failure

### Read Operations

- Single register: `i2c_burst_read(i2c_dev, 0x15, reg, data, 1)`
- Burst read: `i2c_burst_read(i2c_dev, 0x15, reg, data, num)`
- FIFO read: Chunked burst reads from `B2:0x7B`, each chunk <= 252 bytes, aligned to sample size

### Write Operations

- Single register: `i2c_reg_write_byte(i2c_dev, 0x15, reg, data)`
- Burst write: `i2c_burst_write(i2c_dev, 0x15, reg, data, num)`
- Register arrays: Sequential single-byte writes from `{addr, value}` pairs

---

## 9. Data Format

### PPG Raw Data Format

Each PPG data sample is 4 bytes per channel, stored in the FIFO in little-endian format:

```
Byte 0: bits [7:0]   (LSB)
Byte 1: bits [15:8]
Byte 2: bits [23:16]
Byte 3: bits [31:24] (MSB)
```

Extraction function (`pah_815x_hal.c` line 699):

```c
int32_t value = ((fifo[base + 3] << 24) & 0xFF000000) |
                ((fifo[base + 2] << 16) & 0x00FF0000) |
                ((fifo[base + 1] << 8)  & 0x0000FF00) |
                ((fifo[base + 0] << 0)  & 0x000000FF);
```

The result is a signed 32-bit integer representing the raw ADC value.

### Auto-Exposure Information

AE info is read from Bank 2 registers after each FIFO read:

| Parameter | Register | Size | Description |
|-----------|----------|------|-------------|
| Expo_time_A | B2:0x17 | 3 bytes | Channel A exposure time (raw) |
| Expo_time_B | B2:0x1A | 3 bytes | Channel B exposure time (raw) |
| Expo_time_C | B2:0x1D | 3 bytes | Channel C exposure time (raw) |
| Expo_time_D | B2:0x20 | 3 bytes | Channel D exposure time (raw) |
| LEDDAC_A | B2:0x23 | 1 byte | Channel A LED DAC value |
| LEDDAC_B | B2:0x24 | 1 byte | Channel B LED DAC value |
| LEDDAC_C | B2:0x25 | 1 byte | Channel C LED DAC value |
| LEDDAC_D | B2:0x26 | 1 byte | Channel D LED DAC value |
| Touch data | B2:0x04 | 3 bytes | IR touch sensor value |

**Exposure time conversion:** `exposure_us = raw_value * 0.25`

**LED current conversion:** `current_mA = DAC_value * 0.4`

### PPG Data Output Structure

```c
typedef struct {
    uint64_t end_timestamp;          // End time of measurement batch
    uint64_t start_timestamp;        // Start time of measurement batch
    uint8_t ppg_data_ready;          // Data ready flag (incremented per batch)
    uint32_t duration;               // Measurement duration (ms)
    uint8_t is_touched;              // Touch status during measurement
    uint8_t ch_num;                  // Number of active channels (3)
    uint32_t sample_num_per_ch;      // Samples per channel (up to watermark)
    uint8_t *ppg_raw_data;           // Pointer to raw FIFO data buffer
    pah_ae_info pah_ae_info_data;    // Auto-exposure info for all channels
    pah_815x_touch_data touch_data;  // Touch sensor data
} ppg_data_out;
```

### Processed Sample Structure (CK Wrapper)

```c
typedef struct pah8151_ppg_sample {
    int64_t timestamp;       // Sample timestamp (ms since boot)
    int32_t red_intensity;   // Red channel raw ADC
    int32_t green_intensity; // Green channel raw ADC
    int32_t ir_intensity;    // IR channel raw ADC
    float red_expo_us;       // Red exposure time (us)
    float green_expo_us;     // Green exposure time (us)
    float ir_expo_us;        // IR exposure time (us)
    uint8_t red_dac;         // Red LED DAC (0-255)
    uint8_t green_dac;       // Green LED DAC (0-255)
    uint8_t ir_dac;          // IR LED DAC (0-255)
    uint8_t red_curr_ma;     // Red LED current (mA)
    uint8_t green_curr_ma;   // Green LED current (mA)
    uint8_t ir_curr_ma;      // IR LED current (mA)
} pah8151_ppg_sample_t;
```

### Touch Data Structure

```c
typedef struct {
    pah_815x_touch_status status;  // UNKNOWN=0, ON=1, OFF=2
    uint16_t ir_value;             // IR sensor ADC value
    int16_t cap_value;             // Capacitive sensor value
    int16_t cap_value_ref;         // Capacitive reference
    int16_t cap_value_comp;        // Capacitive compensation
} pah_815x_touch_data;
```

### Timestamp Calculation

The CK wrapper distributes timestamps across samples in a batch:

```c
uint64_t base_timestamp = ppg_data.end_timestamp;
uint32_t total_duration_ms = 1000;
uint32_t actual_interval_ms = total_duration_ms / ppg_data.sample_num_per_ch;
uint32_t remainder_ms = total_duration_ms % ppg_data.sample_num_per_ch;

// Last sample gets base_timestamp directly
// Earlier samples: base - (samples_back * interval) - extra_ms
```

With 32 samples and 1000ms duration, the interval is 31ms per sample. The `remainder_ms` distributes any leftover milliseconds to the most recent samples.

---

## 10. Factory Test Thresholds

### Factory Test Modes

| Test | Enum | Description |
|------|------|-------------|
| Brightness (FPC Only) | `Check_Brightness_FPC_Only` | Tests LED brightness without optical cover |
| INT Pin Test | `INT_TEST` | Verifies interrupt pin assertion |
| Brightness (With Cover) | `Brightness_with_cover` | Tests LED brightness through optical cover |
| Light Leak | `Light_Leak_Test` | Checks for optical light leakage |
| Power Noise | `Power_Noise_Test` | Verifies power supply noise levels |
| Touch Calibration | `touch_calibration` | Calibrates touch detection thresholds |

### FPC Only Brightness Test

| Parameter | Value |
|-----------|-------|
| Channels enabled | A, B, C |
| ADC min (pass) | 400 |
| ADC max (pass) | 3000 |
| Off ADC max | 400 |
| Number of reads | 3 (averaged) |

### Brightness With Cover Test

| Parameter | Value |
|-----------|-------|
| Channels enabled | A, B, C |
| ADC min (pass) | 600 |
| ADC max (pass) | 4090 |
| Off ADC max | 400 |
| Touch ADC min | 1250 |
| Touch ADC max | 4090 |
| Exposure setting | 0x45 |
| Number of reads | 3 (averaged) |

### Light Leak Test

| Parameter | Value |
|-----------|-------|
| Channels enabled | A, B, C |
| ADC difference min | 0 |
| ADC difference max | 50 |
| Off ADC max | 400 |
| Touch ADC min | 0 |
| Touch ADC max | 250 |

Light leak test compares LED-on vs LED-off readings. The difference should be less than 50 ADC counts.

### Touch Calibration

| Parameter | Value |
|-----------|-------|
| Target ADC min | 2250 |
| Target ADC max | 2750 |
| DAC search range | 1 to 127 |
| Algorithm | Binary search for optimal DAC value |

### INT Pin Test Sequence

1. Configures GPIO for INT pin observation
2. Starts sensor in test mode
3. Waits for INT pin assertion (rising edge)
4. Verifies interrupt occurred within timeout
5. Pass/fail based on INT pin state

### Demo Factory Test Sequence

From `demo_factory_v1.c`:

1. Product ID check (expects low byte `0x51` from `0x8151`)
2. INT pin test
3. FPC-only brightness test
4. Light leak test
5. Brightness with cover test (exposure `0x45`)
6. Power noise test
7. Stop sensor

---

## 11. Potential Issues and Tuning Opportunities

### CRITICAL BUG: Channel Mapping Inconsistency in AE Data

**Location:** `pah8151.c` lines 211-229

**Problem:** The intensity data correctly maps FIFO index 0 to Green (Channel A), index 1 to Red (Channel B), index 2 to IR (Channel C). However, the exposure time and LED DAC assignments are **swapped between Red and Green**:

```c
// CORRECT: Intensity mapping (lines 206-208)
data->ppg_samples[i].green_intensity = raw_data[i * ch_num + 0];  // Ch A = Green
data->ppg_samples[i].red_intensity   = raw_data[i * ch_num + 1];  // Ch B = Red
data->ppg_samples[i].ir_intensity    = raw_data[i * ch_num + 2];  // Ch C = IR

// INCORRECT: Exposure time mapping (lines 211-216)
data->ppg_samples[i].red_expo_us   = Expo_time_A * 0.25f;  // BUG: A=Green, not Red!
data->ppg_samples[i].green_expo_us = Expo_time_B * 0.25f;  // BUG: B=Red, not Green!
data->ppg_samples[i].ir_expo_us    = Expo_time_C * 0.25f;  // Correct: C=IR

// INCORRECT: LED DAC mapping (lines 219-221)
data->ppg_samples[i].red_dac   = LEDDAC_A;  // BUG: A=Green, not Red!
data->ppg_samples[i].green_dac = LEDDAC_B;  // BUG: B=Red, not Green!
data->ppg_samples[i].ir_dac    = LEDDAC_C;  // Correct: C=IR

// INCORRECT: LED current mapping (lines 224-229)
data->ppg_samples[i].red_curr_ma   = LEDDAC_A * 0.4f;  // BUG: same swap
data->ppg_samples[i].green_curr_ma = LEDDAC_B * 0.4f;  // BUG: same swap
data->ppg_samples[i].ir_curr_ma    = LEDDAC_C * 0.4f;  // Correct
```

**Impact:** The exposure time, DAC value, and current reported for the Red channel actually belong to the Green channel, and vice versa. The raw intensity data is correct, but the associated metadata (exposure, DAC, current) is swapped. This affects any algorithm or logging that relies on per-channel exposure/DAC correlation.

**Fix:** Swap the assignments so `Expo_time_A` maps to `green_expo_us`, `Expo_time_B` maps to `red_expo_us`, and the same for DAC and current values.

### Dead Code: report_touch_data()

**Location:** `pah_815x_main.c` lines 481-491

```c
void report_touch_data(uint64_t timestamp, pah_815x_touch_status touch_state) {
    if (touch_state == PAH_815X_TOUCH_STATUS__UNKNOWN)
        return;

    return;  // <-- Early return prevents all debug logging below

    if (touch_state == PAH_815X_TOUCH_STATUS__ON)
        DEBUG_PRINT("TOUCH: time = { %lu }, status = { ON } ", timestamp);
    else if (touch_state == PAH_815X_TOUCH_STATUS__OFF)
        DEBUG_PRINT("TOUCH: time = { %lu }, status = { OFF } ", timestamp);
}
```

The unconditional `return;` on line 485 makes all touch debug logging dead code. This appears intentional (to reduce UART noise) but should be handled with a compile-time flag rather than dead code.

### Unsafe ppg_data_ready Decrement

**Location:** `pah_815x_main.c` line 498

```c
void clear_ppg_data_ready(void) {
    _ppg_data_out.ppg_data_ready--;
}
```

This uses decrement instead of clearing to zero. If called when `ppg_data_ready` is already 0, the unsigned underflow would wrap to 255, causing the system to believe data is ready when it is not. The CK wrapper does check `get_ppg_data_ready()` before calling `clear_ppg_data_ready()`, but it is fragile.

### Dual Bank Cache

**Location:** `pah_815x_comm.c` lines 18-19

```c
static uint8_t _curr_bank = 0xFF;
static uint8_t _curr_bank_2 = 0;
```

Two independent bank caches exist because there are two code paths that access registers:
1. Direct functions (`pah_815x_comm_write`/`read`) using `_curr_bank`
2. Platform abstraction functions (`pah_plat_comm_i2c_write`/`read`) using `_curr_bank_2`

If both code paths are used concurrently (e.g., factory test functions vs. normal operation), the caches can become desynchronized, leading to register reads/writes on the wrong bank. The bank caches are initialized to different values (`0xFF` and `0x00`), which means the first operation through each path will always perform the bank switch, but subsequent operations may be incorrect if the other path changed the bank.

### Global Buffer Not Mutex-Protected

**Location:** `pah_815x_main.c` line 23

```c
uint8_t buffer[512];
```

The global 512-byte FIFO read buffer is not protected by a mutex at the SDK level. While the CK wrapper's sensor thread is single-threaded, any direct calls to `pah_sensor_task()` from a different context would create a data race. This is currently safe because only one thread calls into the SDK, but it is fragile for future modifications.

### Unimplemented Sensor Attributes

The `attr_set` handler in the CK wrapper has stubs for:
- `SENSOR_ATTR_PAH8151_SAMPLING_FREQUENCY` -- logs "TODO: implement" and returns 0
- `SENSOR_ATTR_PAH8151_LED_CURRENT` -- logs "TODO: implement" and returns 0
- `SENSOR_ATTR_PAH8151_EXPOSURE_TIME` -- logs "TODO: implement" and returns 0

Only `SENSOR_ATTR_PAH8151_MODE` (touch-only vs active) is implemented.

### Hardcoded I2C Address

The I2C address `0x15` is hardcoded in multiple places in `pah_815x_comm.c` rather than being read from the devicetree configuration (`config->i2c.addr`). While PAH8151 devices always use address `0x15`, this prevents using the standard Zephyr I2C address from the DT spec.

### Timestamp Assumption

The CK wrapper assumes a fixed 1000ms total duration for each batch of samples:

```c
uint32_t total_duration_ms = 1000;
```

This is correct for the current configuration (32 Hz, watermark 32 = 1 second), but would be incorrect if the watermark or sample rate were changed at runtime. A more robust approach would calculate the duration from the actual sample rate and sample count.

### Missing Low Power Mode

The `attr_set` handler for `SENSOR_ATTR_PAH8151_MODE` supports switching to `PAH8151_MODE_TOUCH_ONLY`, but the implementation only stops/starts the sensor. It does not implement a true low-power idle state that could be resumed quickly.

### Capacitive Touch Disabled

The configuration has `ENABLE_CAP_TOUCH_DETECT = 0`, relying solely on IR-based touch detection. IR touch detection is simpler but can be less reliable in certain conditions (e.g., dark skin, dry skin, strong ambient IR). Enabling capacitive touch would provide a more robust touch detection mechanism but requires calibration.

### Tuning Opportunities

1. **Sample rate reduction for power saving:** Config 2 (25 Hz, 1 channel) uses significantly less power than Config 5 (32 Hz, 3 channels). Consider switching to a lower config when only heart rate (not SpO2) is needed.

2. **Watermark optimization:** Increasing the watermark reduces interrupt frequency (less CPU wake-ups) but increases latency. The current value of 32 (1 second of data) is a good balance for SpO2 but could be reduced for lower-latency heart rate monitoring.

3. **LED DAC max reduction:** The Green channel DAC max is 63 (25.2 mA) while Red and IR are 127 (50.8 mA). If the optical path allows, reducing the Red/IR DAC max would save power.

4. **PPG auto power saving:** The `enable_ppg_auto_power_saving` flag is not explicitly set in the current initialization. Enabling it would reduce power when no touch is detected in ALWAYS_PPG mode by reducing exposure times and LED currents to minimum values.

5. **FIFO checksum:** Currently disabled (`pah_815x_ENABLE_FIFO_CHECKSUM` not defined). Enabling it adds data integrity verification at the cost of slightly increased FIFO read time.

---

## Appendix: Build Configuration

### Kconfig Options

| Option | Default | Description |
|--------|---------|-------------|
| `CONFIG_CK_PAH8151` | n | Enable PAH8151 driver |
| `CONFIG_CK_PAH8151_INIT_PRIORITY` | 90 | Device init priority |
| `CONFIG_CK_PAH8151_LOG_LEVEL` | 3 (WRN) | Log level |
| `CONFIG_CK_PAH8151_BUS_MUTEX` | n | Enable I2C bus mutex |
| `CONFIG_CK_PAH8151_THREAD_PRIORITY` | 8 | Sensor thread priority |
| `CONFIG_CK_PAH8151_FACTORY_TEST` | n | Enable factory test support |

### Devicetree Binding

From `pixart,pah8151.yaml`:
- Compatible: `pixart,pah8151`
- Bus: I2C
- Required: `irq-gpios` (interrupt GPIO)
- Optional: `int1-gpios`, `int2-gpios` (factory test GPIOs), `int-pin` (touch interrupt pin number)

### CMake Structure

The build system has CMakeLists.txt files at multiple levels:
1. Top-level: adds `drivers/` subdirectory
2. Drivers: adds `corekinect/` subdirectory
3. CoreKinect: adds `sensors/` subdirectory
4. Sensors: adds `pah8151/` subdirectory
5. PAH8151: compiles all `.c` files, adds include paths for `PAH8151/pah_sensor/`, `PAH8151/pah/`, `PAH8151/pah_factory_test/`

---

## Appendix: Return Codes

| Code | Enum | Value | Meaning |
|------|------|-------|---------|
| Success | `PAH_RET_SUCCESS` | 0 | Operation completed successfully |
| Error | `PAH_RET_ERROR` | -1 | Generic error |
| Pending | `PAH_RET_PENDING` | -2 | Operation in progress |
| Failed | `PAH_RET_FAILED` | -3 | Operation failed |
| Platform Failed | `PAH_RET_PLAT_FAILED` | -4 | Platform-level failure |
| Verify Failed | `PAH_RET_VERIFY_FAILED` | -5 | Verification mismatch |
| Not Implemented | `PAH_RET_NOT_IMPLEMENTED` | -6 | Feature not implemented |
| Invalid Argument | `PAH_RET_INVALID_ARGUMENT` | -7 | Bad parameter |
| Invalid Operation | `PAH_RET_INVALID_OPERATION` | -8 | Operation not allowed in current state |
| FIFO Checksum Failed | `PAH_RET_FIFO_CKS_FAILED` | -9 | FIFO data integrity error |
| FIFO Overflow | `PAH_RET_FIFO_OVERFLOW` | -10 | FIFO buffer overflow |
| Async Pending | `PAH_RET_ASYNC_PENDING` | -11 | Asynchronous operation pending |
| Null Pointer | `PAH_RET_NULL_POINTER` | -12 | Null pointer argument |
