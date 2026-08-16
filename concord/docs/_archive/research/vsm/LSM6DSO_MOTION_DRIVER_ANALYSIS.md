# LSM6DSO Motion Driver Deep Analysis

**Date:** 2026-02-09
**Purpose:** Comprehensive analysis of the LSM6DSO accelerometer/gyroscope driver as used in the Alpha wearable device, with specific focus on how motion data feeds into the Philips PSP library for heart rate computation.

**Files Analyzed:**

| Category | File |
|----------|------|
| CK Wrapper | `_fw_build/lsm6dso_drv/drivers/corekinect/sensors/lsm6dso/lsm6dso.c` |
| CK Header | `_fw_build/lsm6dso_drv/drivers/corekinect/sensors/lsm6dso/lsm6dso.h` |
| ST Vendor Reg | `_fw_build/lsm6dso_drv/drivers/corekinect/sensors/lsm6dso/LSM6DSO/lsm6dso_reg.c` |
| ST Vendor Reg Header | `_fw_build/lsm6dso_drv/drivers/corekinect/sensors/lsm6dso/LSM6DSO/lsm6dso_reg.h` |
| Bus Abstraction | `_fw_build/lsm6dso_drv/drivers/corekinect/sensors/lsm6dso/LSM6DSO/stmemsc.h` |
| I2C Transport | `_fw_build/lsm6dso_drv/drivers/corekinect/sensors/lsm6dso/LSM6DSO/stmemsc_i2c.c` |
| SPI Transport | `_fw_build/lsm6dso_drv/drivers/corekinect/sensors/lsm6dso/LSM6DSO/stmemsc_spi.c` |
| Sample App | `_fw_build/lsm6dso_drv/samples/fifo_motion/src/main.c` |
| Sample Config | `_fw_build/lsm6dso_drv/samples/fifo_motion/prj.conf` |
| DTS Binding | `_fw_build/lsm6dso_drv/dts/bindings/sensor/ck,lsm6dso.yaml` |
| DTS I2C Binding | `_fw_build/lsm6dso_drv/dts/bindings/sensor/ck,lsm6dso-i2c.yaml` |
| DTS SPI Binding | `_fw_build/lsm6dso_drv/dts/bindings/sensor/ck,lsm6dso-spi.yaml` |
| Kconfig | `_fw_build/lsm6dso_drv/Kconfig` |
| Build Files | `_fw_build/lsm6dso_drv/CMakeLists.txt` (+ nested) |

---

## 1. Driver Architecture

### Layer Diagram

```
+----------------------------------------------------------+
|  Application / VSM Module                                 |
|  - sensor_sample_fetch() / sensor_channel_get()           |
|  - sensor_trigger_set(SENSOR_TRIG_MOTION, ...)            |
+----------------------------------------------------------+
                          |
                  Zephyr Sensor API
                          |
+----------------------------------------------------------+
|  CoreKinect Wrapper (lsm6dso.c / lsm6dso.h)             |
|  - lsm6dso_init() / lsm6dso_deinit()                     |
|  - lsm6dso_fifo_read()  [FIFO batch consumer]            |
|  - lsm6dso_trigger_set() [motion interrupt handler]       |
|  - lsm6dso_attr_set()   [runtime ODR/FS config]          |
|  - Two-phase init: boot low-power + explicit full init    |
+----------------------------------------------------------+
                          |
              stmdev_ctx_t function pointers
              (.read_reg / .write_reg / .mdelay)
                          |
+----------------------------------------------------------+
|  ST Vendor Library (lsm6dso_reg.c / lsm6dso_reg.h)       |
|  - Pure register-level helpers (no bus knowledge)          |
|  - All functions take stmdev_ctx_t* context                |
|  - ~6500 lines covering every register in the LSM6DSO     |
+----------------------------------------------------------+
                          |
              stmdev_ctx_t callbacks resolve to:
                          |
+----------------------------------------------------------+
|  Bus Transport (stmemsc_i2c.c / stmemsc_spi.c)           |
|  - stmemsc_i2c_read/write -> Zephyr i2c_burst_read_dt()  |
|  - stmemsc_spi_read/write -> Zephyr spi_transceive_dt()  |
|  - Optional bus mutex (CONFIG_CK_LSM6DSO_BUS_MUTEX)       |
|  - Optional I2C metrics (CONFIG_CK_LSM6DSO_I2C_METRICS)   |
|  - I2C has 3-retry logic on failure (without mutex mode)   |
+----------------------------------------------------------+
                          |
                 Zephyr I2C / SPI drivers
                          |
+----------------------------------------------------------+
|  Hardware: LSM6DSO @ I2C 0x6A/0x6B or SPI up to 10 MHz   |
+----------------------------------------------------------+
```

### Key Design Decisions

1. **Two-phase initialization.** At Zephyr boot, `DEVICE_DT_INST_DEFINE` calls `init_low_power_mode()` which verifies the chip ID, performs a software reset, and sets the sensor into ultra-low power mode with FIFO disabled. The application explicitly calls `lsm6dso_init()` later when it is ready to begin sampling. This keeps the sensor drawing minimal current until the firmware is ready.

2. **CK wrapper owns FIFO and motion logic.** The ST vendor library is used purely for register-level access. All FIFO management (read loop, tag parsing, timestamp synthesis, overflow handling) and all motion detection setup (threshold scaling, duration conversion, interrupt routing, trigger thread) live in the CK wrapper.

3. **Devicetree-driven configuration.** ODR, full-scale range, power mode, interrupt pin selection, and bus type are all configured via devicetree properties. The CK wrapper reads these from the `lsm6dso_config` structure populated by DT macros.

4. **Bus abstraction via `stmemsc.h`.** The `STMEMSC_CTX_I2C` and `STMEMSC_CTX_SPI` macros populate the `stmdev_ctx_t` function pointer structure at compile time, so the ST vendor library never needs to know which bus is being used.

---

## 2. ODR (Output Data Rate) Configuration

### Accelerometer ODR

| ODR Index | Frequency (Hz) |
|-----------|----------------|
| 0         | Off            |
| 1         | 12.5           |
| 2         | 26             |
| 3         | **52**         |
| 4         | 104            |
| 5         | 208            |
| 6         | 417            |
| 7         | 833            |
| 8         | 1667           |
| 9         | 3333           |
| 10        | 6667           |
| 11        | 1.6 (accel only) |

**Configured value:** The driver hardcodes a validation check in `lsm6dso_init()`:

```c
lsm6dso->accel_freq = lsm6dso_odr_to_freq_val(odr);
if (lsm6dso->accel_freq != LSM6DSO_SAMPLE_RATE_HZ) {
    LOG_ERR("accel odr is not 52Hz, max is 52Hz");
    return -EIO;
}
```

Where `LSM6DSO_SAMPLE_RATE_HZ = 52`. This means the driver **enforces 52 Hz as the only acceptable accelerometer ODR** and will fail initialization if the devicetree specifies anything else. The default devicetree configuration (`accel-odr = <3>`) maps to index 3 = 52 Hz.

### Gyroscope ODR

The gyroscope ODR is set from the devicetree `gyro-odr` property using the same index table. The default examples show `gyro-odr = <3>` (52 Hz), but **there is no hard validation** in `lsm6dso_init()` for gyro ODR -- only the accelerometer has the 52 Hz enforcement.

### FIFO Batch Data Rate

In `lsm6dso_init()`:

```c
lsm6dso_fifo_xl_batch_set(ctx, LSM6DSO_XL_BATCHED_AT_52Hz);
```

The accelerometer FIFO batching is hardcoded to 52 Hz regardless of what the devicetree says. Gyroscope batching is **disabled** (commented out):

```c
/*
 * Note: Gyroscope batching is currently disabled to reduce I2C bus load.
 * Enable the following line when gyroscope data is needed:
 * lsm6dso_fifo_gy_batch_set(ctx, LSM6DSO_GY_BATCHED_AT_52Hz);
 */
```

**This means only accelerometer data is stored in the FIFO. Gyroscope samples are not being collected via FIFO.**

---

## 3. Full-Scale Range

### Accelerometer

| Index | Range  | Sensitivity  |
|-------|--------|-------------|
| 0     | +/-2g  | 0.061 mg/LSB |
| 1     | +/-16g | 0.488 mg/LSB |
| 2     | +/-4g  | 0.122 mg/LSB |
| 3     | +/-8g  | 0.244 mg/LSB |

**Configured value:** The devicetree default is `accel-range = <0>` (+/-2g). However, regardless of what the devicetree specifies, `lsm6dso_init()` then **overrides it**:

```c
/* Set fixed full-scale values for FIFO operation */
lsm6dso_xl_full_scale_set(ctx, LSM6DSO_2g);
```

The FIFO conversion in `lsm6dso_fifo_read()` uses a hardcoded sensitivity:

```c
/* Conversion factor: 0.061 mg/LSB at 2g full-scale */
data->data[accel_count].acceleration_mg_x =
    ((float)data->data_raw_acceleration.i16bit[0]) * 0.061f;
```

**The 0.061 mg/LSB sensitivity is correct for +/-2g.** This is the full 16-bit range over +/-2g: (2 * 2000 mg) / 65536 = 0.061 mg/LSB.

### Gyroscope

| Index | Range      | Sensitivity   |
|-------|-----------|---------------|
| 0     | +/-250 dps  | 8.75 mdps/LSB |
| 1     | +/-125 dps  | 4.375 mdps/LSB |
| 2     | +/-500 dps  | 17.50 mdps/LSB |
| 4     | +/-1000 dps | 35 mdps/LSB |
| 6     | +/-2000 dps | 70 mdps/LSB |

**Configured value:** `lsm6dso_init()` overrides the gyroscope full-scale to +/-2000 dps:

```c
lsm6dso_gy_full_scale_set(ctx, LSM6DSO_2000dps);
```

The FIFO conversion uses a hardcoded 70.0 mdps/LSB:

```c
/* Conversion factor: 70 mdps/LSB at 2000dps full-scale */
data->data[gyro_count].angular_rate_mdps_x =
    ((float)data->data_raw_angular_rate.i16bit[0]) * 70.0f;
```

**Note:** Even though gyroscope FIFO batching is disabled, the gyro conversion code is present and would be active if batching were re-enabled.

---

## 4. FIFO Configuration

### FIFO Mode

**Stream Mode (Continuous)** -- `LSM6DSO_STREAM_MODE` (value 6).

In stream mode, the FIFO continuously stores samples. When the FIFO is full, the oldest sample is overwritten by the newest one. This ensures the consumer always gets the most recent data without needing to manage start/stop.

### Watermark

```c
lsm6dso_fifo_watermark_set(ctx, LSM6DSO_SAMPLE_RATE_HZ);  // = 52
```

The watermark is set to 52 samples, which at 52 Hz corresponds to exactly 1 second of data. However, **the watermark interrupt is not routed to any GPIO pin** -- the driver does not set `int1_fifo_th` or `int2_fifo_th`. The watermark is set but unused in the current configuration.

### FIFO Size and Overflow Protection

- Maximum FIFO buffer: `LSM6DSO_MAX_FIFO_SIZE = 512` samples (driver-side buffer for parsed output)
- Hardware FIFO: 512 words (each word = 7 bytes: 1 tag + 6 data)
- Flush threshold: `LSM6DSO_FIFO_FLUSH_SIZE = 60` samples

If the FIFO level reaches 60 or more samples, the driver flushes it:

```c
if (num >= LSM6DSO_FIFO_FLUSH_SIZE) {
    LOG_INF("Flushing LSM6DSO FIFO");
    lsm6dso_fifo_mode_set(ctx, LSM6DSO_BYPASS_MODE);
    lsm6dso_fifo_mode_set(ctx, LSM6DSO_STREAM_MODE);
    return 0;
}
```

At 52 Hz with only accelerometer batching, 60 samples = ~1.15 seconds of data. The sample app polls every 500 ms, yielding ~26 samples per read (confirmed by sample output). This gives comfortable margin before the 60-sample flush threshold.

### Batch Data Rate Summary

| Sensor        | Batched into FIFO | BDR      |
|---------------|-------------------|----------|
| Accelerometer | Yes               | 52 Hz    |
| Gyroscope     | **No** (disabled) | N/A      |
| Temperature   | No                | N/A      |
| Timestamp     | No (not configured) | N/A   |

### Data Ready Mode

```c
lsm6dso_data_ready_mode_set(ctx, LSM6DSO_DRDY_PULSED);
```

Data-ready signals are configured as pulsed (75 us pulse), not latched.

---

## 5. Data Format

### Raw Data

- **Resolution:** 16-bit signed integers (int16_t) per axis
- **Axes:** X, Y, Z in that order (i16bit[0] = X, i16bit[1] = Y, i16bit[2] = Z)
- **Byte order:** Little-endian (matching nRF52840 and all ARM Cortex-M targets)
- **FIFO word format:** 1 byte tag + 6 bytes data (3 x int16_t)

### Converted Units

| Measurement | Raw Unit | Converted Unit | Conversion Factor |
|-------------|---------|----------------|-------------------|
| Acceleration | int16_t LSB | float mg (milli-g) | 0.061 mg/LSB (at 2g FS) |
| Angular Rate | int16_t LSB | float mdps (milli-dps) | 70.0 mdps/LSB (at 2000dps FS) |
| Timestamp | N/A | int32_t ms | Synthesized from k_uptime_get_32() |

### Output Data Structure

```c
typedef struct {
    int32_t timestamp;              // ms (Zephyr uptime)
    float acceleration_mg_x;        // milli-g
    float acceleration_mg_y;        // milli-g
    float acceleration_mg_z;        // milli-g
    float angular_rate_mdps_x;      // milli-degrees/sec
    float angular_rate_mdps_y;      // milli-degrees/sec
    float angular_rate_mdps_z;      // milli-degrees/sec
} lsm6dso_output_data_t;
```

Each FIFO read populates an array of these structures: `data->data[LSM6DSO_MAX_FIFO_SIZE]`.

### Zephyr sensor_channel_get() Format

When reading via the standard Zephyr API (`SENSOR_CHAN_ACCEL_X`, etc.), the driver returns arrays of `sensor_value` structs where `val1` contains the mg or mdps value as a truncated integer and `val2` is set to 0. **This truncates the float to integer precision -- the fractional part is lost.** For VSM usage, the application should access `data->data[i].acceleration_mg_x` directly from the driver data structure for full floating-point precision.

---

## 6. Interrupt Configuration

### Current Interrupt Usage

The driver supports **one interrupt purpose: motion detection (wake-up).**

The interrupt system is **not used for FIFO watermark or data-ready**. FIFO data is consumed exclusively by polling.

### Motion Detection Interrupt Path

```
LSM6DSO WAKE_UP_SRC register
        |
    INT1 or INT2 pin (configurable via DTS "int-pin" property)
        |
    GPIO edge-to-active interrupt
        |
    lsm6dso_gpio_callback() [ISR context]
        |
    k_sem_give(&data->gpio_sem)
        |
    lsm6dso_trigger_thread() [dedicated kernel thread, priority 8]
        |
    Reads WAKE_UP_SRC register to confirm and clear interrupt
        |
    Calls data->handler_motion(dev, trig)
```

### Interrupt Latching

When motion trigger is first enabled, the driver sets:

```c
lsm6dso_int_notification_set(ctx, LSM6DSO_ALL_INT_LATCHED);
```

All interrupts are latched (sticky until read), preventing missed events.

### What is NOT Interrupt-Driven

- FIFO watermark threshold (watermark is set but interrupt not routed)
- FIFO overflow
- Accelerometer data ready
- Gyroscope data ready
- Temperature data ready

---

## 7. Power Mode

### Boot State (init_low_power_mode)

| Component      | Mode               | Typical Current |
|----------------|--------------------|-----------------|
| Accelerometer  | Ultra-Low Power    | ~9 uA           |
| Gyroscope      | Normal             | ~275 uA         |
| FIFO           | Bypass (disabled)  | --               |

### Active State (lsm6dso_init)

The active power mode is configured from devicetree. The default/recommended configuration from all examples:

| Component      | Mode               | Typical Current |
|----------------|--------------------|-----------------|
| Accelerometer  | High Performance   | ~170 uA         |
| Gyroscope      | High Performance   | ~550 uA         |
| FIFO           | Stream Mode        | --               |

**Power mode mapping (accel):**

| DTS accel-pm | Enum | Mode |
|-------------|------|------|
| 0 (default) | `LSM6DSO_HIGH_PERFORMANCE_MD` | Full bandwidth, lowest noise |
| 1 | `LSM6DSO_LOW_NORMAL_POWER_MD` | Reduced bandwidth/noise |
| 2 | `LSM6DSO_ULTRA_LOW_POWER_MD` | Minimum power |

**Power mode mapping (gyro):**

| DTS gyro-pm | Enum | Mode |
|------------|------|------|
| 0 (default) | `LSM6DSO_GY_HIGH_PERFORMANCE` | Full bandwidth |
| 1 | `LSM6DSO_GY_NORMAL` | Reduced bandwidth |

### Deinit State (lsm6dso_deinit)

Returns to the same state as boot: accel ULP, gyro normal, FIFO bypass. Also cleanly shuts down the trigger thread if it was running.

---

## 8. How Data is Read

### FIFO Batch Read (Primary Data Path)

The FIFO read is the only supported `sensor_sample_fetch` path. The full sequence:

```
1. Application calls sensor_sample_fetch(dev)  [or directly lsm6dso_fifo_read()]
2. Driver reads FIFO_STATUS1/STATUS2 to get sample count (lsm6dso_fifo_data_level_get)
3. If count == 0: return immediately
4. If count >= 60: flush FIFO (bypass + stream) and return 0 samples
5. For each sample in FIFO:
   a. Read FIFO_DATA_OUT_TAG (1 byte) to get the sensor tag
   b. Read FIFO_DATA_OUT_X_L through FIFO_DATA_OUT_Z_H (6 bytes)
   c. Based on tag:
      - XL_NC_TAG: Parse as accelerometer, convert with 0.061 mg/LSB
      - GYRO_NC_TAG: Parse as gyroscope, convert with 70.0 mdps/LSB
      - Other tags: Discard (read into dummy buffer to advance FIFO pointer)
6. Store accel_sample_count and gyro_sample_count
7. Application calls sensor_channel_get() to retrieve per-axis arrays
```

### Timestamp Synthesis

**The driver does NOT use the LSM6DSO's hardware timestamp counter.** Instead, timestamps are synthesized from the Zephyr kernel uptime:

```c
int32_t current_time = k_uptime_get_32();
const float sample_period_ms = 1000.0f / 52.0f;  // ~19.23 ms

// Most recent sample gets current_time
// Older samples are back-calculated:
sample_time = current_time - (sample_period_ms * samples_back) - extra_ms;
```

This approach has inherent timing uncertainty:
- The "current_time" is the time of the bus read, not the time of the actual ADC conversion
- Bus read latency (I2C or SPI transfer time for all samples) adds jitter
- The back-calculation assumes perfectly uniform 52 Hz spacing, which is only approximately true

### Per-Sample I2C/SPI Cost

Each FIFO sample requires **two bus transactions:**
1. Read FIFO_DATA_OUT_TAG register (1 byte): tag read
2. Read FIFO_DATA_OUT_X_L through Z_H (6 bytes): data read

For a typical 26-sample batch at 500 ms polling:
- 26 tag reads + 26 data reads = **52 I2C burst transactions**
- Plus 1 transaction for FIFO level read
- Total: **53 transactions per 500 ms poll**

---

## 9. I2C/SPI Interface Details

### I2C Configuration

- **Addresses:** 0x6A (SDO/SA0 = GND) or 0x6B (SDO/SA0 = VDD)
- **Speed:** Standard (100 kHz), Fast (400 kHz), or Fast-Plus (1 MHz) -- determined by Zephyr I2C driver configuration, not by this driver
- **Protocol:** Burst read/write via `i2c_burst_read_dt()` / `i2c_burst_write_dt()`
- **I3C:** Explicitly disabled at init (`lsm6dso_i3c_disable_set`)

### SPI Configuration

- **Max frequency:** 10 MHz (`spi-max-frequency = <10000000>` in DTS examples)
- **Mode:** Master, 8-bit word, MSB-first (`SPI_OP_MODE_MASTER | SPI_WORD_SET(8) | SPI_TRANSFER_MSB`)
- **Read bit:** Bit 7 set for reads (`reg_addr | 0x80`)
- **Write bit:** Bit 7 cleared for writes (`reg_addr & 0x7F`)

### Bus Mutex

When `CONFIG_CK_LSM6DSO_BUS_MUTEX=y`, all I2C/SPI transactions are wrapped with `k_mutex_lock/unlock`. This is needed when the bus is shared with other devices (e.g., another sensor on the same I2C bus). The mutex is obtained via `get_bus_mutex()` from the Zephyr bus_mutex library.

### I2C Retry Logic

When **not** using the bus mutex (and not using I2C metrics), the I2C transport implements a 3-retry loop with 1 ms delay between retries:

```c
int retry_count = 0;
int max_retries = 3;
while (retry_count < max_retries) {
    ret = i2c_burst_read_dt(stmemsc, reg_addr, value, len);
    if (ret == 0) return ret;
    retry_count++;
    k_msleep(1);
}
```

### I2C Metrics

When `CONFIG_CK_LSM6DSO_I2C_METRICS=y`, the driver tracks per-second performance stats for both reads and writes: total operations, average/min/max latency (in microseconds), and total bus utilization time (in milliseconds). Metrics are logged at LOG_ERR level every ~1 second.

---

## 10. Motion Detection

### Wake-on-Motion Configuration

The driver implements the LSM6DSO's hardware wake-up detection feature, which operates independently of the FIFO:

**Threshold (WAKE_UP_THS register, 0x5B):**
- 6-bit field (0-63)
- Resolution depends on accelerometer full-scale: `LSB = FS_XL / 64`
- At 2g FS: 31.25 mg per LSB, range 31.25 mg to 1969 mg
- At 4g FS: 62.5 mg per LSB, range 62.5 mg to 3938 mg
- The driver accepts threshold in milli-g and auto-scales based on current FS

**Duration (WAKE_UP_DUR register, 0x5C):**
- 2-bit field (0-3 ODR cycles)
- The driver accepts duration in milliseconds and converts to ODR cycles
- At 52 Hz: 0=instant, ~19 ms=1 cycle, ~38 ms=2 cycles, ~58 ms=3 cycles (max)

**Default values set by the driver on first trigger_set call:**
- Threshold: 250 mg (maps to register value 8 at 2g FS)
- Duration: 0 ms (instant trigger)

### Activity Recognition / Pedometer

**Not configured.** The LSM6DSO has embedded pedometer, tilt detection, significant motion, and Machine Learning Core (MLC) features, but none of these are configured or exposed by this driver.

---

## 11. Critical VSM Analysis: Accel ODR vs PPG ODR Synchronization

### The Core Problem

The Philips PSP (Photoplethysmography Signal Processing) library requires synchronized accelerometer and PPG data with accurate timestamps to perform motion artifact cancellation for heart rate computation. If the accel timestamps are inaccurate or the ODR is not properly related to the PPG ODR, the PSP library cannot correctly correlate motion artifacts with PPG signal disturbances, leading to degraded HR accuracy.

### Current Configuration Assessment

**Accel ODR: 52 Hz (hardcoded and enforced)**

This is a reasonable choice for wrist-worn PPG applications. Typical PPG ODRs for wearables are 25 Hz, 50 Hz, or 100 Hz. The 52 Hz accel ODR:

- **If PPG ODR is 25 Hz:** Accel is approximately 2x the PPG rate. This is acceptable -- PSP can downsample or interpolate. However, 52/25 = 2.08, not exactly 2.0. This irrational ratio means the samples will slowly drift relative to each other, requiring timestamp-based resampling rather than simple decimation.

- **If PPG ODR is 50 Hz:** Close match (52 vs 50), but the 4% frequency mismatch will cause sample phase to drift by ~1 sample every 25 seconds. PSP must use timestamp interpolation.

- **If PPG ODR is 100 Hz:** Accel is approximately half the PPG rate. The 2:1 ratio is not exact (100/52 = 1.923), again requiring interpolation.

- **If PPG ODR is 52 Hz:** Perfect 1:1 match. This would be ideal if the PPG sensor can be configured to exactly 52 Hz.

### Timestamp Accuracy Concerns

**This is the most significant issue for VSM accuracy.** The driver synthesizes timestamps rather than using the LSM6DSO's hardware timestamp counter:

1. **No hardware timestamp.** The LSM6DSO FIFO supports timestamp tagging (`LSM6DSO_TIMESTAMP_TAG`) at configurable batch rates, but this feature is not enabled. The `odr_ts_batch` field in FIFO_CTRL4 is left at 0 (disabled).

2. **Back-calculated timestamps assume perfect ODR.** The code calculates `sample_period_ms = 1000.0f / 52.0f = 19.23 ms` and spaces samples backward from the current kernel time. But the LSM6DSO's actual ODR has tolerance of +/-1.5% (per datasheet), meaning the real period could be anywhere from 18.94 ms to 19.52 ms.

3. **Bus read latency is not accounted for.** The `current_time = k_uptime_get_32()` is captured before the FIFO read loop begins, but the actual most-recent sample may have been captured by the ADC at any point during the previous ~19.23 ms interval. For a 26-sample batch, the bus reads themselves take significant time (on I2C at 400 kHz: ~26 * 2 * ~200 us = ~10 ms of bus time).

4. **Polling jitter.** The 500 ms polling interval is subject to Zephyr scheduler jitter. If a higher-priority thread delays the FIFO read, the back-calculated timestamps will all shift together while the actual ADC sample times did not.

### Quantified Timing Error Estimate

Assuming:
- Actual ODR: 52 Hz +/- 1.5% = 51.22 to 52.78 Hz
- Assumed ODR: exactly 52 Hz
- Batch size: 26 samples (500 ms poll)
- Bus read latency: ~10 ms for full batch

Worst-case timestamp error for oldest sample in batch:
- ODR drift: 26 samples * |19.23 - 19.52| ms = 7.5 ms
- Bus latency: up to 10 ms (not compensated)
- Scheduler jitter: typically 1-5 ms on RTOS
- **Total worst case: ~22 ms error on the oldest sample**

For PPG motion artifact cancellation, timing errors above 10-15 ms at 50+ Hz sampling can cause significant phase misalignment between the motion and PPG signals, reducing the effectiveness of adaptive noise cancellation.

### Recommendations for VSM Improvement

1. **Enable hardware timestamps.** Configure `odr_ts_batch` in FIFO_CTRL4 to batch timestamps into the FIFO. The LSM6DSO's internal timestamp counter runs at 25 us resolution, providing far more accurate inter-sample timing than kernel uptime back-calculation.

2. **Match accel ODR exactly to PPG ODR, or use an integer multiple.** If PPG runs at 25 Hz, configure accel at 50 Hz (index 3 maps to 52 Hz, not 50 Hz -- there is no exact 50 Hz or 25 Hz setting on the LSM6DSO). The closest options:
   - 26 Hz (index 2) -- close to 25 Hz
   - 52 Hz (index 3) -- close to 50 Hz / 2x 25 Hz
   - 104 Hz (index 4) -- close to 100 Hz / 4x 25 Hz

   Given the LSM6DSO's ODR options, 52 Hz or 104 Hz are the most practical. PSP must handle non-integer resampling regardless.

3. **Reduce polling interval for lower latency.** Polling at 250 ms instead of 500 ms would halve the batch size (13 samples) and reduce worst-case timestamp back-calculation drift.

4. **Consider enabling gyro FIFO batching.** Some PSP configurations benefit from angular rate data for improved motion artifact removal during fast wrist rotation. The comment in the code notes this was disabled "to reduce I2C bus load" -- this tradeoff should be evaluated against HR accuracy requirements.

---

## Summary Table

| Parameter | Value | Source |
|-----------|-------|--------|
| Accel ODR | 52 Hz (enforced) | lsm6dso.c:1353-1356 |
| Gyro ODR | 52 Hz (default, not enforced) | DTS gyro-odr=3 |
| Accel Full Scale | +/-2g (overridden to 2g) | lsm6dso.c:1400 |
| Gyro Full Scale | +/-2000 dps (overridden) | lsm6dso.c:1401 |
| Accel Sensitivity | 0.061 mg/LSB | Hardcoded in FIFO read |
| Gyro Sensitivity | 70.0 mdps/LSB | Hardcoded in FIFO read |
| FIFO Mode | Stream (continuous) | lsm6dso.c:1405 |
| FIFO Watermark | 52 samples | lsm6dso.c:1404 |
| FIFO Flush Threshold | 60 samples | lsm6dso.h:40 |
| Accel FIFO Batching | Enabled at 52 Hz | lsm6dso.c:1407 |
| Gyro FIFO Batching | **Disabled** | lsm6dso.c:1409-1413 |
| DRDY Mode | Pulsed | lsm6dso.c:1406 |
| Accel Power Mode | High Performance (default) | DTS accel-pm=0 |
| Gyro Power Mode | High Performance (default) | DTS gyro-pm=0 |
| Interrupt Usage | Motion/wake-up only | lsm6dso.c:1086 |
| FIFO Read Method | Polling (not interrupt) | sample main.c:89 |
| Timestamp Source | Zephyr k_uptime_get_32() | lsm6dso.c:468 |
| HW Timestamp | **Not enabled** | odr_ts_batch not set |
| I2C Addresses | 0x6A or 0x6B | DTS/reg.h |
| SPI Max Freq | 10 MHz | DTS binding |
| Bus Mutex | Optional (CONFIG_CK_LSM6DSO_BUS_MUTEX) | Kconfig |
| I2C Retries | 3 (without mutex) | stmemsc_i2c.c:195 |
| Motion Threshold | 250 mg default | lsm6dso.c:1099 |
| Motion Duration | 0 ms (instant) default | lsm6dso.c:1104 |
| Block Data Update | Enabled | lsm6dso.c:1394 |
| I3C | Disabled | lsm6dso.c:1203 |
| Thread Priority | 8 (trigger thread) | lsm6dso.h:61 |
| Thread Stack | 1024 bytes | lsm6dso.h:64 |
| Compatible String | "ck,lsm6dso" | DTS binding |
| Chip ID | 0x6C | lsm6dso_reg.h:195 |
