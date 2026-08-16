# PixArt PAH8151HU-IN Vendor Documentation Analysis

Research document synthesizing technical details from PixArt vendor documentation,
SDK source code, and the Alpha project's BLE data logger implementation.

**Source documents and code:**

| Source | Version / Date | Description |
|--------|---------------|-------------|
| PAH8151HU-IN Datasheet | v1.0 / 19 Jul 2022 | Full chip specifications, register maps, initialization sequences |
| PAH8151HU-IN Reference Design Guide | v1.0 / 27 Mar 2023 | Firmware structure, demo modes, algorithm integration |
| PAH8151 Fw Porting Guide | V2.11 / 2022 | HRD and SpO2 porting instructions |
| PAH815X_FW_CODE_HRD_SPO2 SDK | V2.12 / 20 Aug 2024 | SDK with PXI algorithm libraries for HR and SpO2 |
| PAH815X_FW_CODE_RAW SDK | V2.12 / 24 Apr 2025 | SDK for raw PPG data output without algorithm processing |
| BLE Data Logger | -- | Alpha project BLE capture application (`ble-data-logger/src/main.py`) |
| In-repo firmware config | -- | `_fw_build/pah8151_drv/.../pah_815x_reg_default.h` and `pah_815x_config.h` |

---

## 1. Recommended PPG Configuration

### 1.1 Chip Overview

The PAH8151HU-IN is a low-power CMOS PPG (photoplethysmography) sensor in a 3.3 x 3.2 x 0.68 mm
CSP package. Key hardware features:

- **Pixel array:** 4 x 4 photodetector array with dual bandpass filter (supports 880/660/525 nm)
- **FIFO:** 488-sample deep buffer
- **Interfaces:** I2C (1 Mbit/s), I3C (12.5 Mbit/s), SPI (10 Mbit/s)
- **I2C slave address:** 0x15
- **Product ID:** 0x8151
- **Supply voltage:** VDDA/VDDD 1.7--1.9 V, VDDIO 1.62--3.6 V
- **LED drivers:** 4 drivers (LED0--LED3) supporting Green, Red, and IR wavelengths
- **LED peak sink current:** Up to 100 mA
- **Power consumption:**
  - PPG 20 Hz, 3 channels: ~60 uA
  - LLOB (low-power IR/CAP touch) mode: ~18 uA
  - Power down: ~1 uA

### 1.2 Register Bank Architecture

The PAH8151 uses a banked register architecture with 10 banks (0--9). Register 0x7F selects the
active bank. Each bank has a 7-bit address space (0x00--0x7F). The key banks are:

| Bank | Purpose |
|------|---------|
| 0 | AEC convergence bounds, exposure line norm steps, LED DAC steps |
| 1 | Touch/IR channel config, channel D settings, frame period, exposure time |
| 2 | PPG channel A/B/C config, LED assignments, AEC enable, normalize mode, golden report rate |
| 4 | GPIO configuration, power-on reset |
| 5 | Frame start timing, flush reset |

### 1.3 Initialization Sequence

The datasheet specifies a multi-phase initialization:

1. **Common Init** -- GPIO configuration, frame start timing, touch thresholds, exposure time
   maximums, frame periods, AEC enable flags, normalize mode, AEC convergence bounds
2. **LLOB Init** (optional) -- Low-power IR/CAP touch detection for wear detection
3. **PPG Enable** -- Channel-specific LED assignments, channel enable/disable, timing, ODR

The in-repo firmware implements these as static register arrays:

```c
// Common initialization (PAH_815X_REG_INIT): ~50 register writes across banks 0, 1, 2, 4, 5
{0x7F, 0x04},  // bank 4: GPIO config
{0x7F, 0x05},  // bank 5: frame start timing
{0x7F, 0x01},  // bank 1: touch thresholds, exposure, frame period
{0x7F, 0x02},  // bank 2: AEC enable, LED config, normalize mode
{0x7F, 0x00},  // bank 0: AEC convergence bounds
```

### 1.4 PPG Enable Configurations (In-Repo)

The in-repo firmware defines five PPG enable configurations:

| Config | ODR | Channels | Active LEDs | Use Case |
|--------|-----|----------|-------------|----------|
| PPG_ENABLE_1 | 32 Hz | 1 (Green) | Ch_A only | Basic HR monitoring |
| PPG_ENABLE_2 | 25 Hz | 1 (Green) | Ch_A only | HRV / SDNN analysis |
| PPG_ENABLE_3 | 25 Hz | 2 (Green + IR) | Ch_A + Ch_C | Improved HR across skin tones |
| PPG_ENABLE_4 | 25 Hz | 2 (Red + IR) | Ch_B + Ch_C | SpO2 measurement |
| PPG_ENABLE_5 | 32 Hz | 3 (Green + Red + IR) | Ch_A + Ch_B + Ch_C | One-key measurement (HR + SpO2 + RR) |

### 1.5 Key Register Settings

**LED assignments (Bank 2):**

| Register | Value | Meaning |
|----------|-------|---------|
| 0x4C | 0x12 | LED_a = Green, ledbias_sel=1 |
| 0x57 | 0x18 | LED_b = Red, ledbias_sel=1 |
| 0x62 | 0x11 | LED_c = IR, ledbias_sel=1 |

**Channel enable control (Bank 2):**

| Register | Enable Value | Disable Value | Channel |
|----------|-------------|---------------|---------|
| 0x51 | 0x0B | 0x08 or 0x18 | Ch_A (Green) |
| 0x5C | 0x1B | 0x18 | Ch_B (Red) |
| 0x67 | 0x1B | 0x18 | Ch_C (IR) |

**ODR / Golden Report Rate (Bank 2):**

| ODR | Reg 0x73 | Reg 0x74 | Value (decimal) |
|-----|----------|----------|-----------------|
| 32 Hz | 0xE8 | 0x03 | 1000 |
| 25 Hz | 0x00 | 0x05 | 1280 |

**AEC Configuration (Bank 2, per-channel):**

```
Ch_A AEC enable: reg 0x4D = 0x03 (ae_enable + auto_FP_enable)
Ch_B AEC enable: reg 0x58 = 0x03
Ch_C AEC enable: reg 0x63 = 0x03
```

**Normalize mode (Bank 2):**

```
Reg 0x76 = 0x51  // off-on-off_normalized
// Other options: 0x50 = On_sub_Off_Normalize
//                0x54 = Cmd_fifo_on_and_off_norm
//                0x5A = Cmd_fifo_on_and_off_bypass
```

**AEC Convergence Bounds (Bank 0, identical for all channels):**

| Parameter | Value |
|-----------|-------|
| avg_hibu | 2812 |
| avg_lobu | 1788 |
| avg_hi | 2556 |
| avg_lo | 2044 |

The AEC (Auto Exposure Control) adjusts LED current and exposure time to keep the ADC average
within these bounds. The `hibu`/`lobu` are the outer bounds that trigger larger adjustments;
`hi`/`lo` are the inner bounds for fine-tuning.

**Exposure Time Maximums (Bank 2):**

| Channel | Register Pair | Max Exposure |
|---------|--------------|--------------|
| Ch_A (Green) | 0x48--0x49 | 3000T |
| Ch_B (Red) | 0x53--0x54 | 256T |
| Ch_C (IR) | 0x5E--0x5F | 64T |

**DAC Maximums (Bank 2):**

| Channel | Register | Max DAC Value |
|---------|----------|---------------|
| Ch_A (Green) | 0x4B | 0x3F (63) |
| Ch_B (Red) | 0x56 | 0x7F (127) |
| Ch_C (IR) | 0x61 | 0x7F (127) |

---

## 2. HRD Mode vs RAW Mode

### 2.1 HRD (Heart Rate Detection) Mode

**SDK version:** PAH815X_FW_CODE_HRD_SPO2_V2.12_20240822

HRD mode performs on-device heart rate computation using the PixArt PXI algorithm library. The
data flow is:

```
Sensor FIFO  -->  Driver reads FIFO  -->  report_fifo_data_hr()  -->  PXI HRD Algorithm
                                          (organizes PPG + accel)      (outputs HR, trust, grade)
```

**Configuration:**
- PPG ODR: 20 Hz (sample_period = 50 ms)
- Watermark: 20 samples (triggers interrupt after 20 PPG frames)
- Register setting: REG_SETTING_1
- Accelerometer: Required, ODR >= PPG ODR (typically 25 Hz at 4G)
- CAP touch detection: Enabled (ENABLE_CAP_TOUCH_DETECT=1)
- Touch thresholds: CAP_TOUCH_RATIO=0.75, CAP_NOTOUCH_RATIO=0.25, DELTA_TOUCH_DIFF=400

**Algorithm outputs:**
- Heart rate (float, BPM)
- Trust level (integer, 0--100)
- Signal grade (int16)
- Wear index (optional, if `_WEAR_INDEX_EN` defined)
- Motion flag

**Processing steps in `report_fifo_data_hr()`:**
1. Read FIFO data from sensor
2. Organize into `pah8series_data_t` structure with PPG channels and accelerometer data
3. Call `pah8series_entrance()` to run algorithm
4. Check return value for `MSG_HR_READY`
5. Extract HR via `pah8series_get_hr()`, trust via `pah8series_get_hr_trust_level()`

### 2.2 SpO2 Mode

**Configuration:**
- PPG ODR: 25 Hz (sample_period = 40 ms)
- Watermark: 25 samples (HRD_SPO2 SDK) or 32 samples (in-repo config)
- Register setting: REG_SETTING_4 (Red + IR channels)
- Measurement window: 30 seconds
- Algorithm: PXI SpO2 V703, outputs median SpO2 at end of window
- Optimization: `spo2_Optimize_Enable` parameter in `report_fifo_data_spo2()`
- Buffer: PPG_BUF_MAX_SPO2 = 30 entries

**SpO2 measurement flow:**
1. Start PPG with REG_SETTING_4 (Red + IR)
2. Collect 30 seconds of data
3. Algorithm continuously outputs intermediate SpO2 values
4. At 30th second, output median SpO2
5. Driver stops SpO2 process

### 2.3 RAW Mode

**SDK version:** PAH815X_FW_CODE_RAW_V2.12_20250424

RAW mode outputs unprocessed PPG ADC data without any algorithm. There is no PXI algorithm
library linked. The data flow is:

```
Sensor FIFO  -->  Driver reads FIFO  -->  log_pah8series_data()  -->  UART/BLE output
                                          (formats PPG + accel)
```

**Configuration:**
- PPG ODR: 32 Hz (sample_period = 31.25 ms)
- Watermark: 32 samples
- Register setting: REG_SETTING_1, 2, or 3 depending on channel selection
- CAP touch detection: Disabled (ENABLE_CAP_TOUCH_DETECT=0)
- Accelerometer: Still provided (acc_num=40 per interrupt interval at 32 Hz)

**Three RAW sub-modes:**

| Define | Channels | Register Setting |
|--------|----------|-----------------|
| `demo_ppg_RAW_32HZ_G_dri_en_815x` | Green only | REG_SETTING_1 |
| `demo_ppg_RAW_32HZ_R_IR_dri_en_815x` | Red + IR | REG_SETTING_2 |
| `demo_ppg_RAW_32HZ_G_R_IR_dri_en_815x` | Green + Red + IR | REG_SETTING_3 |

**Key difference from HRD:** RAW mode includes ADC on/off data readback for each sample, logging
both the "on" (LED illuminated) and "off" (ambient) readings. The `pah_raw_data_out.c`
implementation simply formats and prints the data:

```c
// From pah_raw_data_out.c -- no algorithm, just logging
log_pah8series_data(ppg_data, ppg_ch_num, ppg_frame_count, mems_data, mems_num);
```

### 2.4 Key Differences Summary

| Feature | HRD Mode | SpO2 Mode | RAW Mode |
|---------|----------|-----------|----------|
| SDK release | Aug 2024 | Aug 2024 | Apr 2025 |
| ODR | 20 Hz | 25 Hz | 32 Hz |
| Watermark | 20 | 25 | 32 |
| Algorithm | PXI HRD V5653 | PXI SpO2 V703 | None |
| Output | HR (BPM), trust, grade | SpO2 (%), quality | Raw ADC values |
| Channels | Green (1ch) | Red + IR (2ch) | Configurable (1--3ch) |
| Touch detect | CAP + IR | CAP + IR | Disabled |
| Accel samples/interval | 25 | 25 | 40 |

---

## 3. PXI Algorithm

### 3.1 What Is the PXI Algorithm

PXI (PixArt eXtended Intelligence) is PixArt's proprietary signal processing algorithm library
distributed as pre-compiled static libraries (`.a` files). The libraries are closed-source.
Customers receive header files with API declarations and the compiled library to link against.

The algorithm library versions found in the HRD_SPO2 SDK:

| Algorithm | Library File | Version |
|-----------|-------------|---------|
| HRD | `libpah8series_motion5653#0_m4f_gcc_hard_os.a` | V5653 |
| HRD (legacy) | `libpaw8001_ofn307009_5_m4f_Os_hard_gcc.a` | V307009 |
| SpO2 | `libpxialg_spo2_v703_1_1_m4f_hard_gcc.a` | V703 |

Library naming convention: `lib<algorithm>_<version>_<arch>_<compiler>_<float_abi>.a`
- `m4f` = ARM Cortex-M4 with FPU
- `gcc` = GCC compiler
- `hard` = Hardware floating point ABI
- `os` or `Os` = Optimized for size

### 3.2 HRD Algorithm API

Defined in `pah8series_api_c.h`:

```c
// Core lifecycle
int pah8series_version(void);
int pah8series_open(void);
int pah8series_close(void);

// Main processing entry point
int pah8series_entrance(pah8series_data_t *data);

// Output retrieval
float pah8series_get_hr(void);
int   pah8series_get_hr_trust_level(void);
int16_t pah8series_get_signal_grade(void);
float pah8series_get_wear_index(void);
float pah8series_get_motion_flag(void);

// Parameter configuration
int pah8series_query_param(int index, float *value);
int pah8series_param_set(int index, float value);
```

**Input data structure** (`pah8series_data_t` from `pah8series_data_c.h`):

```c
typedef struct {
    uint32_t frame_count;
    uint32_t time;
    uint32_t touch_flag;
    uint32_t nf_ppg_channel;      // number of PPG channels
    uint32_t nf_ppg_per_channel;  // samples per channel
    int32_t  *ppg_data;           // interleaved PPG data
    int16_t  *mems_data;          // accelerometer data [x,y,z,...]
    uint32_t nf_mems;             // number of accelerometer samples
} pah8series_data_t;
```

### 3.3 HRD Algorithm Parameters

The algorithm exposes 150+ tuning parameters via `pah8series_param_idx_t` enum, spanning
versions V519 through V559. The key parameters configured during initialization:

| Parameter | Value | Purpose |
|-----------|-------|---------|
| GSENSOR_MODE | 1 (4G) | Accelerometer full-scale range |
| PPG_CH_NUM | varies | Number of active PPG channels |
| HAS_IR_CH | 0 or 1 | Whether IR channel is present |
| IS_8002 | 1.0 | Chip variant flag |
| EN_ONHAND_RECONIZATION | 1.0 | Enable on-wrist detection |
| PREDICTION_FEEDBACK | 1.0 | Enable predictive HR smoothing |
| FEEDBACK_LEN_PRED_SHORT | 16.0 | Short prediction feedback window |
| FEEDBACK_LEN_PRED_LONG | 32.0 | Long prediction feedback window |
| SET_FALG_IMP | 1.0 | Enable impedance-based features |
| EN_CHANNEL_QUALITY | 1.0 | Enable per-channel quality assessment |
| PREDICTION_SMOOTH | 1.0 | Enable smooth HR transitions |
| LIMIT_HR_UB | 220.0 | Upper bound HR limit (BPM) |
| LIMIT_HR_LB | 110.0 | Lower bound HR limit (BPM) |

### 3.4 SpO2 Algorithm API

Defined in `pah_spo2_alg.h`:

```c
void report_fifo_data_spo2(
    int32_t *ppg_data,
    int ppg_ch_num,
    int ppg_frame_count,
    int16_t *mems_data,
    int mems_num,
    int spo2_Optimize_Enable
);
```

The SpO2 algorithm requires Red and IR channel data. The ratio of Red to IR absorption is used
to compute blood oxygen saturation percentage.

### 3.5 Relationship to PSP

"PSP" (PixArt Signal Processing) appears in the BLE data logger as a distinct data stream
separate from "raw" sensor data. Based on the BLE characteristic structure:

- **Raw data:** Direct sensor ADC output (PPG intensity, accelerometer values)
- **PSP data:** Post-processed output from the PXI/PSP algorithm running on the nRF application
  processor

The PSP PPG data has a different format than raw PPG: 32-bit dummy field + 16-bit green value
(6 bytes total) vs. raw PPG's 32-bit green intensity (4 bytes). This suggests the PSP pipeline
reformats and potentially filters the data before output.

PSP accelerometer data similarly includes header fields: 32-bit dummy + 16-bit dummy + three
16-bit x/y/z values (12 bytes total) vs. raw accelerometer's three 32-bit floats (12 bytes).
The PSP version uses integer representation rather than floating-point, indicating the data has
been converted to the format expected by the PXI algorithm (int16 values).

---

## 4. LED/PD Channel Setup

### 4.1 Channel Architecture

The PAH8151 supports up to 4 PPG channels (A, B, C, D) plus dedicated touch (T) and CAP
channels. The scan sequence in PPG mode is:

```
CH_CAP -> CH_A -> CH_B -> CH_C -> CH_D -> CH_T
```

Each channel can be independently configured with:
- LED selection (which LED driver to use)
- Exposure time maximum
- Frame period
- Frame count (number of exposures per measurement)
- AEC enable/disable
- DAC maximum (LED current limit)
- Conversion gain

### 4.2 LED-to-Channel Mapping

The in-repo firmware uses the following LED assignments:

| Channel | LED Color | Register (Bank 2) | Value | LED Bias |
|---------|-----------|-------------------|-------|----------|
| Ch_A | Green (525 nm) | 0x4C | 0x12 | ledbias_sel=1 |
| Ch_B | Red (660 nm) | 0x57 | 0x18 | ledbias_sel=1 |
| Ch_C | IR (880 nm) | 0x62 | 0x11 | ledbias_sel=1 |
| Ch_D | Disabled | -- | -- | -- |
| Ch_T | IR (touch) | 0x6F | 0x01 | ledbias_sel=0 |

### 4.3 Channel Purpose by Measurement Type

**Heart Rate (HRD):** Primarily uses Green (Ch_A). Green light at 525 nm is optimal for
detecting pulsatile blood flow in superficial capillaries. The 4x4 pixel array with green
bandpass filter provides high-SNR PPG signals for HR estimation.

**SpO2:** Requires both Red (Ch_B) and IR (Ch_C). Blood oxygen saturation is calculated from
the ratio of Red (660 nm) to IR (880 nm) absorption:
- Oxygenated hemoglobin (HbO2) absorbs more IR than Red
- Deoxygenated hemoglobin (Hb) absorbs more Red than IR
- The R/IR ratio maps to SpO2 percentage via a calibration curve

**One-Key Measurement:** Uses all three channels (Green + Red + IR) simultaneously to measure
HR, SpO2, and respiration rate in a single session.

### 4.4 Touch/Wear Detection

The sensor supports two touch detection methods:

1. **IR Touch (Ch_T):** Uses a low-power IR LED with short exposure (25T) to detect skin
   proximity. The touch threshold registers (Bank 1) define high/low thresholds:
   - Touch_TH_Hi: 2048 (reg 0x18 = 0x08)
   - Touch_TH_Lo: 1024 (reg 0x1B = 0x04)

2. **CAP Touch:** Capacitive sensing using the dedicated CAP channel. The SDK defines touch
   detection ratios:
   - CAP_TOUCH_RATIO: 0.75 (75% of reference for touch)
   - CAP_NOTOUCH_RATIO: 0.25 (25% of reference for no-touch)
   - CAP_DELTA_TOUCH_DIFF_VALUE: 400 minimum delta

The HRD SDK enables both methods (ENABLE_CAP_TOUCH_DETECT=1). The RAW SDK and in-repo
firmware disable CAP touch (ENABLE_CAP_TOUCH_DETECT=0), relying only on IR touch or disabling
touch detection entirely.

### 4.5 Per-Channel Timing

Each PPG channel has independently configurable timing:

| Parameter | Ch_A (Green) | Ch_B (Red) | Ch_C (IR) | Ch_T (Touch) |
|-----------|-------------|------------|-----------|--------------|
| ExpoTime_max | 3000T | 256T | 64T | 25T |
| FramePeriod | 240 | 40 | 40 | 40 |
| frame_num | 2 | 5 | 5 | 1 |
| DAC_Max | 63 (0x3F) | 127 (0x7F) | 127 (0x7F) | -- |

The Green channel has a much longer maximum exposure time (3000T vs 256T for Red) but a lower
DAC maximum (63 vs 127). This means the Green LED operates at lower current but longer exposure,
while Red and IR can drive higher current for shorter durations. The frame periods and frame
numbers are tuned so that the effective data rates match the configured ODR.

---

## 5. Noise Mitigation

### 5.1 Auto Exposure Control (AEC)

AEC is the primary mechanism for maintaining signal quality. It automatically adjusts LED
current (via DAC) and exposure time to keep the ADC reading within an optimal range. The AEC
is enabled per-channel via Bank 2 registers:

```
Reg 0x4D = 0x03  // Ch_A: ae_enable=1, auto_FP_enable=1
Reg 0x58 = 0x03  // Ch_B: ae_enable=1, auto_FP_enable=1
Reg 0x63 = 0x03  // Ch_C: ae_enable=1, auto_FP_enable=1
```

The `auto_FP_enable` bit enables automatic frame period adjustment in addition to exposure
time and LED current adjustments.

**Convergence bounds (Bank 0):**

The AEC uses a two-tier convergence system:

```
         lobu (1788)    lo (2044)    hi (2556)    hibu (2812)
           |              |            |              |
    -------+==============+============+==============+-------
    LARGE  |   fine-tune  |   target   |   fine-tune  | LARGE
    adjust |              |   range    |              | adjust
```

- **Outer bounds (hibu/lobu):** When ADC average exceeds these, large step adjustments are made
- **Inner bounds (hi/lo):** When ADC average is between inner and outer bounds, fine-tuning
  adjustments are made
- **Target range (lo--hi):** ADC average is within acceptable range, no adjustment needed

**Step sizes (Bank 0):**

| Parameter | Ch_A | Ch_B | Ch_C |
|-----------|------|------|------|
| ExposureLineNormStep | 8 | 4 | 4 |
| LED_DAC_step | 2 | 2 | 2 |

### 5.2 Ambient Light Rejection

The normalize mode (Bank 2, reg 0x76) controls how ambient light is handled:

- **0x51 (off-on-off_normalized):** The sensor takes three readings per sample: LED-off,
  LED-on, LED-off. The average of the two LED-off readings is subtracted from the LED-on
  reading, removing ambient light contribution. This is the mode used in the in-repo firmware.

- **0x50 (On_sub_Off_Normalize):** Simple on-minus-off subtraction.

- **0x54 (Cmd_fifo_on_and_off_norm):** Both on and off data are stored in FIFO with
  normalization applied.

- **0x5A (Cmd_fifo_on_and_off_bypass):** Both on and off data stored without normalization.

The RAW SDK specifically uses `off-on-off_normalized` or the bypass mode to capture both ADC
on/off values for offline analysis.

### 5.3 Motion Artifact Mitigation

Motion artifacts are handled at two levels:

**Hardware level:**
- The 4x4 pixel array provides spatial diversity, allowing the sensor to select pixels with
  better skin contact
- Short frame periods and multiple frames per channel (frame_num=2--5) enable temporal averaging
- The FIFO buffering allows batch processing to smooth out transient motion

**Algorithm level (PXI HRD):**
- The algorithm requires accelerometer data synchronized with PPG data
- Motion flag output: `pah8series_get_motion_flag()` indicates current motion level
- Trust level: `pah8series_get_hr_trust_level()` provides confidence (0--100) in the HR estimate
- Prediction feedback: The algorithm uses short (16-sample) and long (32-sample) prediction
  windows to maintain HR tracking during motion
- On-hand recognition: Detects when the device is not worn to avoid spurious readings

**Data synchronization requirement:** The PPG and accelerometer data must be temporally aligned.
The PixArt SDK requires that the accelerometer ODR be >= PPG ODR. For example, at PPG 20 Hz
and accelerometer 25 Hz, each PPG interrupt interval contains 20 PPG samples and 25
accelerometer samples. The algorithm library handles the resampling internally.

### 5.4 Timing Tuning

The SDK includes a "Timing Tuning" feature (`#define Timing_Tuning`) that locks the sensor
report rate to the target ODR. This compensates for clock drift between the sensor's internal
oscillator and the host MCU timer, ensuring consistent sample timing for the algorithm.

### 5.5 FIFO Checksum

An optional FIFO checksum feature (`pah_815x_ENABLE_FIFO_CHECKSUM`, disabled by default)
allows verification of data integrity when reading from the sensor FIFO. This can detect
I2C/SPI communication errors.

---

## 6. SDK Version Differences

### 6.1 HRD_SPO2 V2.12 (20 Aug 2024)

**Purpose:** Production SDK for devices that compute HR and SpO2 on-device.

**Contents:**
- `pah_sensor/` -- Full driver with HRD and SpO2 support
- `PXI_ALG/HRD/V5653/` -- HRD algorithm library (V5653) + headers
- `PXI_ALG/SpO2/V703/` -- SpO2 algorithm library (V703) + headers
- `pah_factory_test/` -- PPG factory test code
- `pah_cap_factory_test/` -- CAP factory test code
- `bsp/` -- Platform BSP demo code

**Configuration highlights:**
- `ENABLE_PXI_ALG_HRD` and `ENABLE_PXI_ALG_SPO2` both defined
- `ENABLE_CAP_TOUCH_DETECT = 1`
- `PPG_WATERMARK = 20` (HRD), `PPG_WATERMARK_SpO2 = 25`
- `ALG_GSENSOR_MODE = 1` (4G)
- Active demo: `demo_ppg_SpO2_dri_en_815x`
- PPG_IR_CH_NUM = 0 (default, set at runtime for SpO2)

**Demo modes available:**
- INT Mode: `demo_ppg_HR_dri_815x`, `demo_ppg_HRV_dri_815x`, `demo_ppg_RR_dri_815x`,
  `demo_ppg_SPO2_dri_815x`, `demo_touch_mode_dri_815x`, `demo_one_key_measurement_2_dri_815x`
- Polling Mode: Same set with `_polling_` instead of `_dri_`
- Test Pattern: `test_library_HRD`, `test_library_HRV`, `test_library_SPO2`, `test_library_RR_2`
- Factory Test: `demo_factory_test_815x`, `demo_factory_test_cap_815x`

### 6.2 RAW V2.12 (24 Apr 2025)

**Purpose:** Data collection SDK for raw PPG data capture without on-device processing.
Used for algorithm development, validation, and offline analysis.

**Contents:**
- `pah_sensor/` -- Driver configured for raw output
- `PXI_ALG/RAW/` -- Minimal wrapper that only logs data (no algorithm library)
- Updated `pah_815x_reg_default_20250424.h` with April 2025 register defaults

**Configuration highlights:**
- No `ENABLE_PXI_ALG_HRD` or `ENABLE_PXI_ALG_SPO2` defines
- `ENABLE_CAP_TOUCH_DETECT = 0`
- `PPG_WATERMARK_32HZ = 32`
- Active demo: `demo_ppg_RAW_32HZ_G_R_IR_dri_en_815x`
- Three channel configurations available (Green-only, Red+IR, all three)

**Key differences from HRD_SPO2:**

| Aspect | HRD_SPO2 V2.12 | RAW V2.12 |
|--------|----------------|-----------|
| Release date | Aug 2024 | Apr 2025 |
| Algorithm libraries | HRD V5653, SpO2 V703 | None |
| Default ODR | 20 Hz (HRD), 25 Hz (SpO2) | 32 Hz |
| Watermark | 20 (HRD), 25 (SpO2) | 32 |
| CAP touch | Enabled | Disabled |
| Accel samples/interval | 25 | 40 |
| ADC on/off logging | No (normalized output) | Yes (raw on+off) |
| Register defaults file | Standard | Updated (20250424) |
| Output | Processed HR/SpO2 values | Raw ADC values |

### 6.3 Register Default Differences

The RAW SDK (April 2025) includes an updated register defaults file
(`pah_815x_reg_default_20250424.h`) with register configurations matching the three RAW
channel modes. The in-repo firmware (`_fw_build/.../pah_815x_reg_default.h`) has its own
custom register table that is distinct from both the HRD_SPO2 and RAW SDK defaults (see
Section 8 for detailed comparison).

---

## 7. BLE Data Logger

### 7.1 Architecture

The BLE data logger (`ble-data-logger/src/main.py`) is a Python asyncio application that:

1. Scans for BLE devices with "Alpha" in the device name
2. Connects via the `bleak` library
3. Subscribes to BLE notifications on multiple characteristics
4. Writes received data to InfluxDB using the `influxdb_client` library (asynchronous writes)

### 7.2 BLE Service and Characteristics

**Service UUID:** `12345678-1234-5678-1234-56789abcdef0`

| Characteristic | UUID Suffix | Data Type | Rate | Format |
|---------------|-------------|-----------|------|--------|
| VITALS_1HZ_INTENSITY | ...def1 | VitalsData | 1 Hz | 14 bytes |
| PPG_25HZ_INTENSITY | ...def2 | PPGIntensityData | 25 Hz | 4 bytes |
| PPG_32HZ_INTENSITY | ...def3 | PPGIntensityData | 32 Hz | 4 bytes |
| ACCEL_25HZ | ...def4 | AccelerometerData | 25 Hz | 12 bytes |
| ACCEL_32HZ | ...def5 | AccelerometerData | 32 Hz | 12 bytes |
| PSP_PPG_32HZ | ...def6 | PSPPPGIntensityData | 32 Hz | 6 bytes |
| PSP_ACCEL_32HZ | ...def7 | PSPAccelerometerData | 32 Hz | 12 bytes |
| PSP_READ_PPG_32HZ | ...def8 | PSPPPGIntensityData | 32 Hz | 6 bytes |
| PSP_READ_ACCEL_32HZ | ...def9 | PSPAccelerometerData | 32 Hz | 12 bytes |

### 7.3 Data Structures

**VitalsData (14 bytes, 1 Hz):**

```
Offset  Size  Type    Field
0       2     int16   heart_rate (BPM)
2       1     int8    heart_rate_quality (trust level)
3       2     int16   heart_rate_index
5       2     int16   spo2 (percentage)
7       1     int8    spo2_quality
8       2     int16   spo2_index
10      4     float32 temperature_f (Fahrenheit)
```

This is the output of the PXI algorithm running on the nRF application processor. It maps
directly to the HRD algorithm outputs: `pah8series_get_hr()` -> heart_rate,
`pah8series_get_hr_trust_level()` -> heart_rate_quality.

**PPGIntensityData (4 bytes, 25 Hz and 32 Hz):**

```
Offset  Size  Type    Field
0       4     uint32  green_intensity
```

Raw sensor ADC reading for the Green channel. The 25 Hz and 32 Hz variants likely correspond
to different PPG enable configurations (25 Hz for HRV mode, 32 Hz for standard HR mode).

**PSPPPGIntensityData (6 bytes, 32 Hz):**

```
Offset  Size  Type    Field
0       4     int32   dummy (header/metadata)
4       2     int16   green_intensity
```

Post-processed PPG data from the PSP/PXI pipeline. The 32-bit header field likely contains
frame metadata. The 16-bit signed green value (vs. 32-bit unsigned raw) suggests the data has
been normalized and potentially filtered.

**AccelerometerData (12 bytes, 25 Hz and 32 Hz):**

```
Offset  Size  Type    Field
0       4     float32 x (g-force)
4       4     float32 y (g-force)
8       4     float32 z (g-force)
```

Raw accelerometer output in floating-point g-force units.

**PSPAccelerometerData (12 bytes, 32 Hz):**

```
Offset  Size  Type     Field
0       4     int32    dummy (header/metadata)
4       2     int16    dummy2 (reserved)
6       2     int16    x
8       2     int16    y
10      2     int16    z
```

Integer representation of accelerometer data as consumed by the PXI algorithm. The int16
format matches the `mems_data` field in `pah8series_data_t`.

### 7.4 InfluxDB Schema

Data is written to InfluxDB with the following measurements and tags:

| Measurement | Tags | Fields |
|-------------|------|--------|
| `vitals` | device_id, frequency="1hz" | heart_rate, heart_rate_quality, spo2, spo2_quality, temperature |
| `ppg` | device_id, frequency, type="intensity" | ambient, red, green, ir |
| `accelerometer` | device_id, frequency | x, y, z |
| `psp_ppg` | device_id, frequency, type="psp" | ambient, red, green, ir |
| `psp_accelerometer` | device_id, frequency, type="psp" | x, y, z |

### 7.5 Known Bug in PPG Handler

The `create_ppg_handler` and `create_psp_ppg_handler` methods reference fields that do not
exist on their respective data classes:

```python
# Handler code references:
.field("ambient", int(ppg_data.ambient_intensity))
.field("red", int(ppg_data.red_intensity))
.field("green", int(ppg_data.green_intensity))
.field("ir", int(ppg_data.ir_intensity))
```

However, `PPGIntensityData` only defines `green_intensity`, and `PSPPPGIntensityData` also
only defines `green_intensity`. The handler will raise `AttributeError` at runtime when
attempting to access `ambient_intensity`, `red_intensity`, or `ir_intensity`. This indicates
the handler was written for a planned multi-channel data format that the firmware does not yet
implement. Currently only single-channel (Green) PPG data is sent over BLE.

### 7.6 Data Flow Summary

```
PAH8151 Sensor
    |
    | (I2C/SPI, 32 Hz FIFO reads)
    v
nRF52840 Application Processor
    |
    +---> Raw PPG data ---------> BLE: PPG_25HZ / PPG_32HZ (4 bytes, uint32 green)
    |
    +---> Raw Accel data -------> BLE: ACCEL_25HZ / ACCEL_32HZ (12 bytes, 3x float32)
    |
    +---> PXI Algorithm --------> BLE: VITALS_1HZ (14 bytes, HR + SpO2 + temp)
    |     (HRD V5653)     |
    |     (SpO2 V703)     +-----> BLE: PSP_PPG_32HZ (6 bytes, int32 header + int16 green)
    |                     |
    |                     +-----> BLE: PSP_ACCEL_32HZ (12 bytes, int32 header + 4x int16)
    |
    v
BLE Data Logger (Python/bleak)
    |
    v
InfluxDB (async writes)
```

---

## 8. Standalone SDK vs In-Repo Firmware Configuration

### 8.1 Configuration File Comparison

**In-repo:** `_fw_build/pah8151_drv/.../pah_815x_config.h`
**HRD_SPO2 SDK:** `PAH815X_FW_CODE_HRD_SPO2_V2.12_20240822/pah_sensor/pah_815x_config.h`
**RAW SDK:** `PAH815X_FW_CODE_RAW_V2.12_20250424/pah_sensor/pah_815x_config.h`

| Setting | In-Repo | HRD_SPO2 SDK | RAW SDK |
|---------|---------|-------------|---------|
| ENABLE_PPG_SENSOR | 1 | 1 | 1 |
| ENABLE_TOUCH_SENSOR | 1 | 1 | 1 |
| ENABLE_CAP_TOUCH_DETECT | 0 | 1 | 0 |
| ENABLE_DRI_MODE | 1 | 1 | 1 |
| ENABLE_PXI_ALG_HRD | Yes | Yes | No |
| ENABLE_PXI_ALG_SPO2 | Yes | Yes | No |
| PPG_WATERMARK | 20 | 20 | -- |
| PPG_WATERMARK_SpO2 | 32 | 25 | -- |
| PPG_WATERMARK_HRV | 25 | -- | -- |
| PPG_WATERMARK_RR | 25 | -- | -- |
| PPG_WATERMARK_32HZ | -- | -- | 32 |
| ALG_GSENSOR_MODE | 1 (4G) | 1 (4G) | -- |
| PPG_IR_CH_NUM | 0 | 0 | -- |
| Timing_Tuning | Defined | Defined | Defined |
| Optimize_SPO2_flow | Defined | Defined | -- |
| PPG_BUF_MAX_SPO2 | 30 | -- | -- |

Key observations:
- The in-repo config is based on the HRD_SPO2 SDK but adds HRV and RR watermarks
- CAP touch is disabled in-repo (matching RAW SDK behavior)
- SpO2 watermark is increased from 25 to 32 in-repo
- The in-repo config includes SpO2 optimization features from the HRD_SPO2 SDK

### 8.2 Register Default Comparison

The in-repo firmware has a custom `pah_815x_reg_default.h` that differs from both SDK versions.
The most significant differences are in the PPG enable configurations.

**Number of PPG Enable Configs:**

| Source | Configs | Description |
|--------|---------|-------------|
| HRD_SPO2 SDK | 5 (REG_SETTING_1--5) | Mapped to HRD, HRV, SpO2, etc. |
| RAW SDK | 3 (REG_SETTING_1--3) | Green, Red+IR, All channels |
| In-Repo | 5 (PPG_ENABLE_1--5) | Custom combinations (see below) |

**In-Repo PPG Enable Configuration Summary:**

| Config | ODR | Green (Ch_A) | Red (Ch_B) | IR (Ch_C) | Purpose |
|--------|-----|-------------|------------|-----------|---------|
| PPG_ENABLE_1 | 32 Hz | Enabled | Disabled | Disabled | Basic HR |
| PPG_ENABLE_2 | 25 Hz | Enabled | Disabled | Disabled | HRV/SDNN |
| PPG_ENABLE_3 | 25 Hz | Enabled | Disabled | Enabled | HR + deeper tissue |
| PPG_ENABLE_4 | 25 Hz | Disabled | Enabled | Enabled | SpO2 |
| PPG_ENABLE_5 | 32 Hz | Enabled | Enabled | Enabled | One-key measurement |

**Detailed register differences (PPG_ENABLE_1 vs SDK REG_SETTING_1):**

The in-repo PPG_ENABLE_1 explicitly disables channels B and C:
```c
{0x5C, 0x18},  // ch_b_dis
{0x67, 0x18},  // ch_c_dis
```

The SDK REG_SETTING_1 (HRD mode) uses the standard default register set with only 1 channel
active. The in-repo version includes explicit disable writes for unused channels, which is more
defensive.

**PPG_ENABLE_4 (SpO2) differences:**

The in-repo SpO2 config (PPG_ENABLE_4) differs from the SDK's REG_SETTING_4:
- In-repo: 25 Hz ODR (golden_report_rate = 0x0500 = 1280)
- SDK: 25 Hz but uses different watermark (32 in-repo vs 25 in SDK)
- In-repo adds `{0x30, 0x00}` to clear additional PPG range control
- In-repo disables Green (0x51 = 0x08) while enabling Red (0x5C = 0x1B) and IR (0x67 = 0x1B)

**PPG_ENABLE_5 (One-Key Measurement):**

This is the most comprehensive mode, enabling all three LED channels at 32 Hz:
```c
{0x51, 0x0B},  // ch_a_en (Green)
{0x5C, 0x1B},  // ch_b_en (Red)
{0x67, 0x1B},  // ch_c_en (IR)
{0x73, 0xE8},  // golden_report_rate = 1000 (32 Hz)
{0x74, 0x03},
```

This matches the datasheet's "one key measurement" mode (page 61) which enables simultaneous
HR + SpO2 + RR measurement.

### 8.3 Common Init Differences

The in-repo common init (`PAH_815X_REG_INIT`) is a custom register table that combines
elements from both the datasheet initialization sequence and the SDK defaults. Key differences
from the SDK:

1. **Explicit bank switching and comments:** The in-repo version has extensive inline
   documentation explaining each register's purpose
2. **CAP touch disabled by default:** `{0x30, 0x00}` in Bank 2 (SDK enables it)
3. **IR CAP FIFO INT mask:** `{0x2E, 0x0F}` and `{0x2F, 0x04}` -- custom interrupt masking
4. **Touch mode:** `{0x3F, 0x01}` -- touch mode select IR (same as SDK)

### 8.4 Deinit Sequence

The in-repo firmware includes an explicit deinit sequence (`PAH_815X_REG_DEINIT`) and a PPG
disable sequence (`PAH_815X_REG_PPG_DISABLE`) that safely power down the sensor. The SDK
handles deinitialization through function calls rather than static register arrays, making
the in-repo approach more portable across different host MCU platforms.

### 8.5 Summary of Customizations

The in-repo firmware configuration represents a tailored integration of the PAH8151 for the
Alpha product:

1. **Algorithm support retained:** HRD and SpO2 algorithms are enabled (matching HRD_SPO2 SDK)
2. **CAP touch disabled:** Simplifies firmware and reduces power; wear detection relies on
   IR touch only
3. **Extended watermark set:** Adds HRV (25), RR (25), and modified SpO2 (32) watermarks
4. **Five PPG configurations:** Covers all measurement modes from single-channel Green to
   full three-channel operation
5. **Defensive register writes:** Explicit disable of unused channels in each configuration
6. **Static register arrays:** All configurations are compile-time constant arrays rather than
   runtime-constructed sequences, improving determinism and debuggability
