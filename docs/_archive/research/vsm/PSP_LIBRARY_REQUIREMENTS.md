# PSP Library Integration Requirements

Technical requirements extracted from the Philips PSP (Personal Signal Processing) library
documentation suite. This document covers PSP version 6.1.x (x >= 9), specifically the
CoreKinect Wellness build for ARM Cortex M4F.

**Source documents:**
- DG1901 PSP Library Integration Guide, Rev 1.3 (14-Jul-2023)
- DG1903 PSP Biosensing by PPG Integration Guide, Rev 1.2 (07-Aug-2023)
- SY1901 PSP API Specification, Rev 1.3 (30-Jul-2023)
- SY1902 PSP Metrics Specification, Rev 1.3 (13-Jul-2023)
- SY1903 PSP-S API Specification, Rev 1.2 (07-Aug-2023)
- DS1905 PSP Metric Description, v1.1 (04-Aug-2023)
- TS1611 SpO2 Measurement and Calibration, Rev 1.3 (01-Aug-2023)
- Release Notes PSP_6.1.0.520-e2fc0616, Rev 1.1 (02-May-2025)
- Info_ARM_M4F_CoreKinect_Wellness.txt (license info file)

---

## Table of Contents

1. [Version and License Info](#1-version-and-license-info)
2. [Input Data Requirements](#2-input-data-requirements)
3. [Interpolation and Resampling Requirements](#3-interpolation-and-resampling-requirements)
4. [Data Format Specifications](#4-data-format-specifications)
5. [Timing and Synchronization](#5-timing-and-synchronization)
6. [Buffer Sizes and Samples Per Call](#6-buffer-sizes-and-samples-per-call)
7. [API Call Sequence](#7-api-call-sequence)
8. [Configuration Parameters](#8-configuration-parameters)
9. [Quality Metrics and Indicators](#9-quality-metrics-and-indicators)
10. [Error Conditions and Limitations](#10-error-conditions-and-limitations)
11. [SpO2 Specifics](#11-spo2-specifics)
12. [PSP-S vs PSP](#12-psp-s-vs-psp)
13. [Memory and Resource Requirements](#13-memory-and-resource-requirements)
14. [Sensor Signal Requirements Per Metric](#14-sensor-signal-requirements-per-metric)

---

## 1. Version and License Info

### Library Version
- **PSP version:** 6.1.0.520-e2fc0616 (SLA special release based on PSP 6.1.9)
- **Previous release:** PSP_6.1.9.519-1504cf96 (26-Jul-2024)
- **Current release date:** 02-May-2025
- **Architecture:** ARM Cortex M4F
- **Flash code starting address:** 0x000E0000

### License Configuration (CoreKinect Wellness)
- **Customer:** CoreKinect_Wellness (0x00830002)
- **License Type:** Full
- **SpO2 lower bound:** 90%
- **Evaluation restrictions (6.1.0.520):** None for HR (full range). SpO2 lower bound: 90%.
- **Evaluation restrictions (6.1.9.519):** Heart rate upper bound: 120 BPM. SpO2 lower bound: 90%.

### Licensed Metrics
Acceleration, Activity Count, Activity Type, Compressed Acceleration, Compressed PPG,
Energy Expenditure, Fitness Index, Heartbeats, Heart Rate, Low Power Energy Expenditure,
Low Power Heart Rate, Motion Cadence, PPG Ambient, PPG Infrared, PPG Motion, PPG Green,
PPG Red, Private Data, Respiration Rate, Resting Heart Rate, Skin Proximity, Sleep Stages,
Speed, SpO2, Stress Level Heart Rate, VO2 Max.

### Known Issues
The release notes list no known issues (to be solved) and no accepted issues (not to be solved)
for the 6.1.0.520 release.

---

## 2. Input Data Requirements

### 2.1 PPG Signal Requirements

| Parameter | Requirement |
|-----------|-------------|
| **Sampling Rate** | **32 Hz** |
| **Dynamic Range** | 0 to 65535 (2^16 - 1) |
| **Resolution** | 16 bits unsigned (0 to 65535) |
| **SNR (Green channel)** | > 80 dB |
| **SNR (Red/IR channels)** | > 85 dB |
| **PPG Signal** | Ambient cancelled |
| **Ambient Signal** | Optional but recommended (improves Skin Proximity). If not available, set to zero but still feed to the library. |
| **LED power / PD gain** | Control interface must be available or automatic |
| **Sample format** | Only format 0x60 supported (32 samples per 1-second update) |

**PPG channels required per metric:**
- Heart Rate: PPG-Green + PPG-Ambient
- SpO2: PPG-Green + PPG-Ambient + PPG-Red + PPG-Infrared
- Respiration Rate: PPG-Green + Acceleration
- Heart Beat Timestamps: PPG-Green + Acceleration

**Multi-stream support (PSP 6.1.8+):**
- Maximum 2x PPG-Green, 2x PPG-Ambient, 4x PPG-Motion, 2x PPG-Red, 2x PPG-Infrared
- Multiple streams use the same metric ID but different Stream location identifiers (SI)
- Streams are processed by a sophisticated internal algorithm (not averaged)
- It is NOT recommended to combine streams outside the PSP library

### 2.2 Accelerometer Signal Requirements (Standard -- all metrics except Fall Occurrence)

| Parameter | Requirement |
|-----------|-------------|
| **Sampling Rate** | **32 Hz** |
| **Dynamic Range** | +/- 8 g |
| **Resolution** | 13 bits signed, 1/512 g per unit (-4096 to +4095) |
| **Sensor Noise** | < 6 mg RMS |
| **Allowed 0g Offset** | < 150 mg on any axis |
| **Acceleration format ID** | 0x6E (32 samples at 32 Hz) |

If the accelerometer offset exceeds 150 mg, offset calibration is required.

### 2.3 Accelerometer Signal Requirements (Fall Occurrence)

| Parameter | Requirement |
|-----------|-------------|
| **Sampling Rate** | **50 Hz** |
| **Dynamic Range** | +/- 16 g |
| **Resolution** | 15 bits signed, 1/1024 g per unit (-16384 to +16383) |
| **Sensor Noise** | < 6 mg RMS |
| **Allowed 0g Offset** | < 150 mg on any axis |
| **Acceleration format ID** | 0x70 (50 samples at 50 Hz) |

Fall Occurrence CANNOT be combined with other metrics in the same PSP package.

### 2.4 Skin Conductance Signal Requirements

| Parameter | Requirement |
|-----------|-------------|
| **Sampling Rate** | 25 Hz |
| **Dynamic Range** | 0 to 1677 uS (Siemens) |
| **Resolution** | 24 bits unsigned, 0.1 nS per unit (0 to 16,777,216) |
| **SNR** | > 100 dB |
| **Sensor Noise & Interference** | < 1 nS peak-to-peak |
| **Linearity** | < 0.003 |

### 2.5 Gyroscope Signal Requirements

| Parameter | Requirement |
|-----------|-------------|
| **Sampling Rate** | 50 Hz |
| **Dynamic Range** | +/- 2000 dps |
| **Resolution** | 16 bits signed, 0.061 dps per unit (-32768 to +32767) |
| **Sensor Noise** | < 0.1125 dps RMS |
| **Angular Rate 0 offset** | < 0.75 dps |

### 2.6 Barometer Signal Requirements

| Parameter | Requirement |
|-----------|-------------|
| **Sampling Rate** | 4 Hz |
| **Dynamic Range** | 70,000 to 135,535 Pa |
| **Resolution** | 16 bits unsigned, 1 Pa per unit |
| **Sensor Noise** | < 1.5 Pa RMS |

The dynamic range starts at 70,000 Pa. This offset must be accounted for: a value of 0x01 means 70,001 Pa.

### 2.7 LED Wavelength Requirements

| LED Color | Min (nm) | Typical (nm) | Max (nm) |
|-----------|----------|--------------|----------|
| Green | 515 | 525 | 535 |
| Red | 655 | **660** | 665 |
| Infrared | 870 | **880** | 890 |

**Critical for SpO2:** The 660 nm Red wavelength is much more sensitive to deviation than IR.
Deviation of the Red LED wavelength significantly influences SpO2 calibration and sensitivity.
IR at 940 nm is sometimes used but may require different calibration parameters.

---

## 3. Interpolation and Resampling Requirements

### 3.1 Core Requirement

PSP requires **exactly 32 Hz PPG and 32 Hz ACC** input signals, synchronized. If the hardware
sensors do not natively sample at 32 Hz, the integrator MUST resample to 32 Hz before
feeding data to the library.

### 3.2 PPG Interpolation

- Use **linear interpolation** to convert from the native PPG sampling rate to 32 Hz.
- The interpolation formula is: `out = y1 + (y2 - y1) * (x - x1) / (x2 - x1)`
- PPG signal is 16-bit unsigned; use saturation: `SATURATE_UINT16(X) = (X < 0 ? 0 : X > 65535 ? 65535 : X)`
- The last sample of input and output arrays are aligned.
- State (last sample value) must be preserved between calls. Initialize state to zero at startup.
- It is recommended to minimize PPG resampling to preserve signal integrity. Use the PPG clock as the reference.

### 3.3 ACC Resampling

ACC resampling is more complex because anti-aliasing filtering is required when downsampling:

- **~25 Hz ACC input:** Use linear interpolation to get 32 Hz signals directly.
- **~50 Hz ACC input:** Linear interpolation to 64 Hz, then 2x decimation with anti-aliasing filter to get 32 Hz.
- **~100 Hz ACC input:** Linear interpolation to 128 Hz, then 4x decimation with anti-aliasing filter to get 32 Hz.

**Rule of thumb:** Interpolate ACC to the nearest multiple of 32 Hz (32, 64, 128, 256 Hz),
apply anti-aliasing filtering, then downsample to 32 Hz.

The ACC interpolation function for signed 16-bit values uses the same linear interpolation algorithm
but with signed types (`FX_SINT16`).

The decimation filters provided are efficient half-band IIR filters:
- `Filter_Decimate_2x_SINT16` -- downsample by factor 2
- `Filter_Decimate_4x_SINT16` -- downsample by factor 4
- Both require state arrays initialized to zero at startup.

### 3.4 What Happens Without Proper Interpolation

- If PPG sampling rate is not correct and accurate, this **directly affects accuracy of heart rate,
  heartbeat timestamps**, and all metrics requiring PPG signal.
- Without proper anti-aliasing filtering on ACC downsampling, the **performance of heart rate
  estimation is affected**.
- Clock drift between PPG and ACC clock sources causes sampling drift that varies device to device,
  making consistency control between devices difficult.

### 3.5 ACC Signal Clipping

When feeding ACC signal to PSP, make sure the signal is actually within the +/- 8g operating range
by **clipping** out-of-range values. If the accelerometer exceeds +/- 16g (for Fall Occurrence),
the signal will clip and performance will degrade.

---

## 4. Data Format Specifications

### 4.1 PPG Metric Data Format

PPG metrics (Green, Red, IR, Ambient, Motion) all use the same format (metric 0x7B structure):

```
<ID> <NL> <NH> <IX> <Q> <BPI> <PF> <SI> <OFS> <EXP> <L0..L3> <G0..G3> <P0_L> <P0_H> ... <P31_L> <P31_H>
```

Field breakdown:
- **ID:** Metric ID (0x7E=Green, 0x7B=IR, 0x7C=Red, 0x7F=Ambient, 0x7D=Motion)
- **NL, NH:** Size of remaining metric data (little-endian). For 32 samples with EXP: (32 * 2) + 15 = 79 bytes. Without EXP: 78 bytes.
- **IX:** Sequence index (0-255), increment by 1 each call, wraps around
- **Q:** Quality -- set to 4 for input metrics
- **BPI:** Body Position Index (0=unspecified, 1=left wrist, 2=right wrist, 3=unspecified wrist)
- **PF:** PPG format -- fixed to 0x60 for 32 samples at 32 Hz
- **SI:** Stream location identifier (bit7-4: LED position, bit3-0: photodiode position, clock positions 1-12)
- **OFS:** PPG Offset -- set to 0x00 (not yet supported)
- **EXP:** (optional) PPG Exponent + Offset extension -- set to 0x00 (not yet supported). Can be omitted (reduces total size by 1).
- **L0..L3:** Relative LED power [0..100] for each quarter-second of samples
- **G0..G3:** ADC gain (0=1x, 1=2x, 2=4x, 3=8x) for each quarter-second of samples
- **P0..P31:** 32 PPG samples, each 16-bit unsigned, little-endian (LSB first)

### 4.2 Acceleration Metric Data Format

```
<ID> <NL> <NH> <IX> <Q> <BPI> <AF> <X0_L> <X0_H> <Y0_L> <Y0_H> <Z0_L> <Z0_H> ... <X31_L> <X31_H> <Y31_L> <Y31_H> <Z31_L> <Z31_H>
```

Field breakdown:
- **ID:** 0x2B (Acceleration)
- **NL, NH:** Size = (32 * 6) + 4 = 196 bytes
- **IX:** Sequence index
- **Q:** Quality -- set to 4
- **BPI:** Body Position Index
- **AF:** Acceleration format -- 0x6E for 32 samples at 32 Hz (+/- 8g, 13-bit, 1/512 g). 0x70 for Fall Occurrence (50 samples at 50 Hz, +/- 32g, 16-bit, 1/1024 g).
- **X, Y, Z:** 3-axis acceleration data, each 16-bit signed, little-endian

### 4.3 Acceleration Sample Formats Table

| AF (hex) | Sample Rate (Hz) | Update Interval (s) | Samples/Update | Range (g) | Width (MSBs) | Resolution (g) |
|----------|-------------------|---------------------|----------------|-----------|---------------|----------------|
| 0xFF | 128 | 1/16 | 8 | +/- 8 | 12 | 1/256 |
| **0x6E** | **32** | **1** | **32** | **+/- 8** | **13** | **1/512** |
| 0x70 | 50 | 1 | 50 | +/- 32 | 16 | 1/1024 |

### 4.4 PPG Sample Formats Table

| PF (hex) | Sample Rate (Hz) | Update Interval (s) | Samples/Update |
|----------|-------------------|---------------------|----------------|
| 0x7F | 32 | 1/16 | 2 |
| **0x60** | **32** | **1** | **32** |

### 4.5 ACC Sensor Orientation (Axis Conventions)

For a wrist-worn watch embodiment, the axes MUST be aligned such that:
- **X axis** points to 12 o'clock (upward) -- reading 1g when 12 o'clock faces sky
- **Y axis** points to 9 o'clock (left) -- reading 1g when 9 o'clock faces sky
- **Z axis** points toward the wearer's nose (out of display) -- reading 1g when watch face faces up

A remapping may be needed in the ACC driver if the physical sensor axes do not match this convention.

### 4.6 Output Metric Data Format (General)

All output metrics follow this preamble:
```
<ID> <NL> <NH> <IX> <Q> <V0> ... <VN-3>
```

Where:
- ID: metric identifier
- N: 2-byte little-endian size of remaining data
- IX: index, incremented at every update
- Q: quality indicator (0-4)
- V: N-2 data value bytes

### 4.7 Key Output Metric Formats

| Metric | ID (hex) | Update Interval | Value Format |
|--------|----------|-----------------|--------------|
| Heart Rate | 0x20 | 1 sec | 1 byte: HR in BPM (range 30-220) |
| Resting Heart Rate | 0x21 | 3600 sec | 1 byte: RHR in BPM (range 30-120) |
| Skin Proximity | 0x22 | 1 sec | 1 byte: 0=on-skin, 254=off-skin, 255=unspecified |
| Active Energy Expenditure | 0x23 | 1 sec | 2 bytes LE: kcal/h (range 0-1200) |
| Speed | 0x24 | 1 sec | 1 byte: 0.1 m/s (range 0-150) |
| Cadence | 0x25 | 1 sec | 1 byte: strides/min (range 20-120) |
| Activity Type | 0x26 | 1 sec | 1 byte: 0=unspecified, 1=other, 2=walk, 4=run, 6=cycle, 7=rest |
| Heart Beat Timestamps | 0x27 | 1 sec | Complex: M beats (0-5), each with quality, time(ms), type |
| VO2Max | 0x28 | 60 sec | 1 byte: ml/kg/min (range 10-100) |
| Fitness Index | 0x29 | 60 sec | 1 byte: percentile (range 0-100) |
| Respiration Rate | 0x2A | 1 sec | 1 byte: 0.25 breaths/min (range 20-180, = 5-45 brpm) |
| Low Power Heart Rate | 0x2D | 60 sec | 1 byte: BPM (range 30-220) |
| Activity Count | 0x2E | 1 sec | 2 bytes LE + BPI: arbitrary unit (range 0-65535) |
| SpO2 | 0x41 | 1 sec | 1 byte: oxygen level % (range 0-100) |
| Stress Level HR | 0x40 | 1 sec | 2 bytes LE: arbitrary unit (range 0-1000) |
| Fall Occurrence | 0x42 | 1 sec | 1 byte: 0=no fall, 1=fall detected |
| Private Data | 0x2F | 60 sec | Variable length (0-300 bytes) |
| Sleep Stages | 0x30 | Async | Complex: session times, epochs (30s each), stages per epoch |

---

## 5. Timing and Synchronization

### 5.1 PPG-ACC Synchronization

The PSP library requires PPG and ACC to be **synchronized and simultaneously fed** at a constant
number of samples per second. Both must be at **exactly 32 Hz** with an exact ratio of 1:1.

The best scenario: PPG front-end, accelerometer, and MCU share a **common 32768 Hz clock source**.

### 5.2 Recommended Synchronization Method

1. Use the **PPG clock as the timing reference** (let PPG dictate the time).
2. Program the PPG AFE to provide an interrupt when 32 samples are available (once per second).
3. On each PPG interrupt, also read the ACC FIFO.
4. The ACC may have a variable number of samples due to clock drift. Resample the ACC
   to exactly 32 samples to match the 32 PPG samples.
5. Feed acceleration data **before** PPG data, following the order returned by `ListRequiredMetrics()`.

### 5.3 Clock Drift Compensation

If different clocks are used for PPG and ACC:
- Use PPG as the reference to avoid resampling PPG (preserves signal integrity).
- Dynamically resample ACC: if PPG delivers 32 samples, and ACC delivered N samples (e.g., 31),
  interpolate ACC from N to 32 samples.

### 5.4 Time Tracking

PSP tracks elapsed time by counting PPG and ACC samples. If the PPG sample rate has drift,
the internal time will drift. Compensation:

```
Adjusted HR = Reported HR / T32sample
```
Where `T32sample` is the actual MCU-measured time (in seconds) for the PPG sensor to deliver
32 samples. Example: if MCU takes 0.97s to receive 32 samples and library reports 100 BPM,
adjusted HR = 100 / 0.97 = 103 BPM.

This method does NOT correct heartbeat timestamps, where sampling variation directly propagates.

### 5.5 Time Metric

- Time is set via `SetMetric(PSP_METRIC_ID_TIME, ...)` as UTC seconds since epoch (Unix time).
- Must be set at least once before enabling metrics that require time.
- PSP maintains time by counting samples. Set time regularly (e.g., from NTP) to prevent drift.
- Time is maintained as long as any metrics (other than Time itself) are enabled.
- When all metrics are disabled, time is "frozen."
- After re-enabling metrics, set the absolute time again.

---

## 6. Buffer Sizes and Samples Per Call

### 6.1 Per-Call Input Requirements

Each call to `PSP_Process()` expects:
- **32 PPG samples** per channel per second (PPG-Green, PPG-Ambient, PPG-Red, PPG-IR each get 32 samples)
- **32 ACC samples** (X, Y, Z) per second
- **25 Skin Conductance samples** per second (if EDA metrics enabled)
- **50 Gyroscope samples** per second (if Fall Detection enabled)
- **4 Barometer samples** per second (if Fall Detection with barometer enabled)

### 6.2 Process Call Frequency

`PSP_Process()` must be called **at least once per second** (determined by the smallest update
interval of all required input metrics). The minimum is 16 calls per second for certain sub-processing,
though the typical main loop is once per second with 32 samples.

### 6.3 Metric Data Buffer Size

- Use `PSP_MAX_METRIC_SIZE` for the GetMetric output buffer.
- ListRequiredMetrics requires a buffer of at least 10 metric IDs.
- ListUpdatedMetrics requires a buffer large enough for all enabled metrics (at least 32).

---

## 7. API Call Sequence

### 7.1 Fresh Start Lifecycle

```
1. Allocate static memory (uint32_t array, 32-bit aligned)
2. PSP_GetDefaultParams(&params)        -- get minimum memory size
3. Set params.pMem, params.memorySize, params.pSourceID, params.calCoefSpO2, etc.
4. PSP_Initialise(&params, &instance)   -- create instance

5. [Main loop - repeat]:
   a. PSP_EnableMetrics(instance, count, metricIdList)   -- enable desired output metrics
   b. PSP_ListRequiredMetrics(instance, list, &count)    -- check what inputs are needed
   c. For each required metric:
      PSP_SetMetric(instance, metricID, data, size)      -- feed sensor data
   d. PSP_Process(instance)                               -- process inputs
   e. PSP_ListUpdatedMetrics(instance, list, &count)     -- check what outputs are ready
   f. For each updated metric:
      PSP_GetMetric(instance, metricID, data, &size)     -- read output

6. PSP_DisableMetrics(instance, count, metricIdList)     -- disable metrics
7. PSP_Terminate(&instance)                               -- release resources
```

### 7.2 Restart Maintaining History

To preserve accumulated metrics (RHR, Stress, etc.) across resets:

1. Stop feeding data to the library.
2. Disable metrics that require reset (keep history-maintaining metrics like RHR enabled if desired).
3. Save the entire instance RAM (`pspmem` array) and `pInst` to NVM.
4. Save enabled metric list to NVM.
5. Write a unique marker (e.g., 0xAB23EF88) to a NVM variable to indicate history is stored.
6. After reset: check marker. If present, restore RAM from NVM, restore `pInst`, retrieve metric list.
7. Set new TIME metric (with current time) to indicate time jump of reboot.
8. Clear the marker in NVM.
9. Continue normal processing.

The `pspmem` array MUST be a static variable so its address is the same after reboot.

### 7.3 Protocol State Machine

States: **Idle** -> **Active.Controlling** -> **Active.Inputting** -> **Active.Outputting**

| Function | Idle | Controlling | Inputting | Outputting |
|----------|------|-------------|-----------|------------|
| EnableMetrics | Y | Y | | Y |
| DisableMetrics | | Y | | Y |
| ListRequiredMetrics | | Y | | Y |
| SetMetric | | | Y | |
| Process | | | Y | |
| ListUpdatedMetrics | | | | Y |
| GetMetric | | | | Y |
| GetVersion | Y | Y | Y | Y |
| Terminate | Y | Y | Y | Y |

### 7.4 Critical Rules

- Functions must be called **one after another, sequentially** -- no parallel operation.
- In Active.Inputting state, **exactly 1 value per required input metric** must be set before calling `Process()`.
- The order of `SetMetric` calls should follow the order returned by `ListRequiredMetrics()` -- specifically, feed **acceleration data before PPG data**.
- `ListRequiredMetrics()` may vary dynamically over time (e.g., Low Power HR only needs PPG 6-15 seconds per minute).

---

## 8. Configuration Parameters

### 8.1 Instance Parameters (PSP_INST_PARAMS)

```c
typedef struct psp_inst_params_tag {
    FX_VOID     *pMem;            // Pointer to allocated memory block
    FX_UINT08   *pSourceID;       // Pointer to unique source ID string
    FX_UINT32   memorySize;       // Size of memory block
    FX_UINT16   sourceIDSize;     // Size of source ID (string length + 1)
    FX_SINT16   calCoefSpO2[3];   // SpO2 calibration coefficients: a, b, c (scaled x100)
    FX_UINT08   alarmRateFall;    // Fall false alarm rate: 0=daily, 1=weekly, 2=monthly
} PSP_INST_PARAMS;
```

### 8.2 Person-Specific Input Metrics

| Metric | Format | Notes |
|--------|--------|-------|
| Age | 1 byte (0-120 years) | Required for AEE, VO2Max, Fitness Index. AEE quality is low if Age < 10. |
| Profile | Year(2B), Month, Day, Sex, Handedness | Sex: 0=unspecified, 1=male, 2=female. Handedness: 0=unspecified, 1=right, 2=left, 3=mixed. |
| Height | 1 byte (0-255 cm) | Required for Speed, AEE, VO2Max, Fitness Index. 0=unspecified. |
| Weight | 2 bytes LE (hectograms, 0-2000) | E.g., 741 = 74.1 kg. Required for AEE, VO2Max, Fitness Index. |
| Body Position Index | Per metric | 0=unspecified, 1=left wrist, 2=right wrist, 3=unspecified wrist. Must be set correctly for SpO2 orientation check. |
| Sleep Preference | 1 byte | 0=unspecified, 1=yes (intent to sleep), 2=no. |

### 8.3 SpO2 Calibration Coefficients

Passed via `calCoefSpO2[3]` in `PSP_INST_PARAMS`:
- `calCoefSpO2[0]` = a (quadratic term, 0 for linear)
- `calCoefSpO2[1]` = b (linear term)
- `calCoefSpO2[2]` = c (constant term)
- Formula: `SpO2 = a * R^2 + b * R + c` where R is the Red/IR ratio
- Coefficients are **scaled by factor 100** (e.g., 110 becomes 11000)
- These are form-factor and sensor-specific -- each device design needs calibration.
- Must be set **before library initialization**.

### 8.4 Fall Occurrence Parameters

- `alarmRateFall` in instance params: 0 = once per day (more sensitive, more false positives), 1 = once per week, 2 = once per month (less sensitive, fewer false positives)
- Must be set before initialization.

### 8.5 Source ID

- `pSourceID`: 8-byte unique identifier (including null terminator) identifying the data source for Sleep algorithm.
- Required for Sleep Stages. If not using sleep, set to NULL with sourceIDSize = 0.

### 8.6 Platform Macro

Define `FX_PLATFORM_ARM_M4` for ARM Cortex M4F targets. This selects correct data types in `fx_datatypes.h`.

---

## 9. Quality Metrics and Indicators

### 9.1 Quality Indicator (Q)

Every output metric includes a quality indicator (0-4):
- **0:** Fully unreliable -- metric value SHALL be ignored
- **1-3:** Increasing reliability
- **4:** Most reliable value the metric source can provide

Quality cannot be compared between different metrics or between library versions.

### 9.2 Quality vs Accuracy (Heart Rate Example)

From validation data across activities:

| Activity | Availability Q>=1 | Availability Q>=4 | MAE Q>=1 (BPM) | MAE Q>=4 (BPM) |
|----------|--------------------|--------------------|-----------------|-----------------|
| Walk | 99.0% | 52.9% | 2.0 | 0.8 |
| Run | 99.0% | 61.6% | 2.0 | 0.5 |
| Cycle | 99.5% | 67.1% | 1.7 | 0.6 |
| Gym | 98.6% | 53.1% | 3.0 | 0.8 |
| Sit | 99.8% | 86.6% | 1.2 | 0.6 |
| Free living | 99.6% | 56.1% | 2.3 | 1.2 |
| Sleep | 99.9% | 96.6% | 0.4 | 0.3 |
| **Overall** | **99.5%** | **75.4%** | **1.4** | **0.5** |

### 9.3 Recommendations

- Use metrics output when quality indicator is **higher than zero**.
- Quality evaluates input signal quality from PPG and ACC sensors. Potential misjudgment may occur in some cases -- use quality as a guideline alongside the metric value, not to alter or replace it.

---

## 10. Error Conditions and Limitations

### 10.1 Conditions That Produce Bad Data

1. **Incorrect PPG sampling rate** -- directly affects HR, heartbeat timestamps, and all PPG-dependent metrics.
2. **PPG/ACC not synchronized** -- causes phase errors in motion artifact cancellation.
3. **ACC offset > 150 mg** -- reduces effective dynamic range below +/- 8g.
4. **Poor mechanical/optical design** -- crosstalk (LED light path directly to photodiode) degrades SNR.
5. **Incorrect axis orientation** -- ACC axes must follow the 12-9-nose convention.
6. **LED power control loop not functioning** -- PPG signal outside optimal window causes signal quality degradation.
7. **Incorrect body position index** -- affects Activity Type, Speed, SpO2 orientation check.
8. **Activity Type mismatch** -- if set Activity Type does not match actual activity, HR calculation suffers.
9. **Too frequent LED/gain adjustments** -- introduces discontinuities in PPG signal.
10. **Not feeding Ambient channel** -- degrades Skin Proximity accuracy.

### 10.2 Skin Proximity Limitations

- **False on-skin:** Device in motion near reflective surface (e.g., handbag).
- **False on-skin:** Device stationary near reflective surface (e.g., reflective table).
- **False on-skin:** Device taken off in dark environment.
- **False off-skin:** User asleep with body pressing on wrist (no blood flow to PPG).
- On-skin detection latency: ~30-35 seconds.
- Off-skin detection latency: 1-2 seconds to 15-20 seconds.

### 10.3 Resting Heart Rate Limitations

- Initial value available after 1 hour of enabling.
- Stable value (Q=4) after 12-15 hours of wear. Longer if person was very active.
- History retained for up to 7 days. After 7+ days disabled, all history lost.
- RHR does not automatically disable during non-worn periods; the application must handle this.

### 10.4 SpO2 Limitations

- Requires sitting still, wrist resting on table, no motion of hands or fingers.
- Strap must not touch the table or lift the backplate.
- Orientation check requires absolute pitch < 45 degrees, absolute roll < 90 degrees.
- Calibration is sensor-geometry and wavelength specific.
- SpO2 lower bound in the license: 90% (values below 90% are not reported in the licensed build).

### 10.5 Respiration Rate Limitations

- Works only in the **absence of motion**.
- Requires 20-30 seconds acquisition time.

### 10.6 Heart Beat Timestamps Limitations

- Only yields values when user is **at rest or asleep** (motion causes "last beat in sequence" type).
- Sampling time variation directly reflects in timestamp accuracy.

### 10.7 VO2Max and Fitness Index Limitations

- Requires walking (> 3 km/h) or running (> 6 km/h) for at least 20 minutes (VO2Max) or 1 hour (Fitness Index).
- Information is discarded when metrics are disabled (no history retention).

### 10.8 Sleep Stages Limitations

- Minimum sleep session length: 20 minutes.
- Maximum sleep session length: 960 minutes.
- Automatic session end detection has 100-minute latency after actual session end.
- Missing Private Data for < 60 minutes results in "Unspecified" sleep stages.
- Missing Private Data for > 60 minutes may cause missing or prematurely ended sessions.
- Time adjustments > 60 seconds backward are interpreted as packet sorting errors and may cause session loss.

### 10.9 Stress Level Heart Rate

- Takes approximately 52-60 seconds to produce the first Stress Level value after first valid PPG sample.
- "Lock-in time" (delay from system startup to first functionally valid output): roughly < 5 minutes.

---

## 11. SpO2 Specifics

### 11.1 Principle

SpO2 is calculated from the ratio (R) between Red and Infrared PPG signals using the formula:
```
SpO2 = a * R^2 + b * R + c
```
Where a, b, c are calibration coefficients specific to the sensor geometry and LED wavelengths.

### 11.2 Required Input Metrics

- PPG-Green (with Ambient)
- PPG-Red
- PPG-Infrared
- Acceleration

Both AC and DC components of Red and IR signals must remain intact. If scaling is applied in
preprocessing, the same scaling factor must be applied to both AC and DC. If subtraction is
performed, the subtracted value must be known to reconstruct the original signals.

### 11.3 Multi-Wavelength Input

For SpO2 measurement with the reference design (multi-color optical design):
- Green LEDs (525 nm): 2x Green LEDs, center position, 128 mA max per LED
- Red LEDs (660 nm): 3x Red LEDs (positions 12, 6, center), 128 mA max (64 mA for motion/center)
- IR LEDs (880 nm): 2x IR LEDs (positions 12, 6), 128 mA max
- 2x Photodiodes

Firing sequence for SpO2: Red + IR + Green + Ambient, each sample period (1/32 Hz):
M1=PD4+D1(Red top), M2=PD1+D5(Red bottom), M3=PD1+D9(IR top), M4=PD4+D3(IR bottom),
M5=PD1+PD4+D2&D6(Green center), M7=PD1+PD4(Ambient)

**Red and IR LEDs should fire close together** in time for SpO2 accuracy.

### 11.4 Calibration Requirements

**Wellness domain (SpO2 > 95%):**
- At least 20 healthy subjects
- Minimum 30% each gender
- 15% dark skin (Fitzpatrick scale V or VI)
- Inclusion: aged 22-65, good health
- Exclusion: BMI > 35 or < 18.5, tattoos/lesions at sensor site, current smoker
- Protocol: 5 recordings of 3 minutes each per subject, wrist on table, Nellcor reference on finger

**Medical domain (FDA clearance, SpO2 > 70%):**
- Hypoxia lab with desaturation test
- At least 20 subjects, 15% dark skin
- Six plateaus: SpO2 of ~94%, 90%, 85%, 80%, 75%, 70%
- Each plateau held for at least 1 minute for PPG signal stabilization
- ABG or approved pulse oximeter reference
- More stringent exclusion criteria (no heart/lung/kidney disease, no diabetes, no clotting disorders, etc.)

### 11.5 Auto Scaling for SpO2

For sensors with automatic gain control (e.g., Pixart) that deliver 32-bit PPG:
- Must scale from 32-bit to 16-bit unsigned for PSP library
- **Red and IR channels MUST use the same scaling factor (SF1)** for SpO2 accuracy
- A dynamic scaling function adjusts gain and scaling factor based on signal amplitude
- Calibration period of N seconds at startup determines the initial scaling factor

### 11.6 SpO2 Timing

- First SpO2 value output: 20-30 seconds after feeding valid PPG and ACC signals
- Updates every 1 second thereafter

---

## 12. PSP-S vs PSP

### 12.1 Overview

| Feature | PSP | PSP-S |
|---------|-----|-------|
| **Full name** | Philips Biosensing Platform | Philips Biosensing Platform -- Sleep Sensing by PPG |
| **Runs on** | Embedded MCU (ARM Cortex M4F) | Mobile device / resource-rich environment (Linux) |
| **Form factor** | Pre-built binary (psp.bin/psp.hex) | C library for Linux (psp_s.a) |
| **Primary function** | Real-time metric extraction from sensors | Sleep Stages extraction from Private Data |
| **Input** | Raw sensor data (PPG, ACC, SC, Gyro, Baro) | Private Data metric output by PSP |
| **Extraction control** | Has its own EnableMetrics/DisableMetrics | No own extraction control -- uses PSP's |

### 12.2 How They Work Together

1. PSP runs on the wearable, processes sensor data, and produces a **Private Data** metric packet once per minute.
2. The application transfers Private Data packets (via Bluetooth or similar) to the mobile device.
3. PSP-S on the mobile device receives Private Data and extracts **Sleep Stages**.
4. Sleep Stages output includes: session start/end times, sleep stages per 30-second epoch (Wake, REM, Light, Deep, Unspecified), and sleeping heart rate.

### 12.3 PSP-S Key Requirements

- Private Data packets must arrive **in strictly original chronological order**, without duplication.
- Out-of-order packets cause an exception and are ignored.
- PSP-S is robust to incidental packet loss, but > 60 minutes of missing data may cause missing sessions.
- PSP-S version: 1.4 or above.
- Memory: application must provide instance memory (obtained via `GetDefaultParams()`).
- PSP-S instances are person-specific (one instance per user).

### 12.4 Sleep Session Detection

- **Automatic start:** User inactive for >= 20 minutes.
- **Manual start:** Sleep Preference set to "Intent to Sleep" (overrides automatic).
- **Automatic end:** User active for >= 60 minutes.
- **Manual end:** Sleep Preference set to "No Intent to Sleep."
- Manual end takes priority unless it occurs > 20 minutes after activity start.
- Sleeping Heart Rate = minimum of averaged HR values (4.5-minute windows) over the entire session.

### 12.5 Embedded Sleep Stages

Sleep Stages can also be enabled within PSP on the embedded device:
- Requires enabling both Private Data and Sleep Stages metrics.
- Mandatory inputs: PPG_G_INPUT (PPG-Green + Ambient), Sleep Preference, Height, Weight, Profile.
- Sleep Preference is optional if automatic detection suffices.

---

## 13. Memory and Resource Requirements

### 13.1 Memory Footprint (ARM Cortex M4F)

| Component | Biosensing by PPG | Biosensing by EDA | Fall Detection (ACC+Gyro+Baro) |
|-----------|--------------------|--------------------|-------------------------------|
| **ROM** | 78 KB | 21 KB | 24 KB |
| **Data RAM** | 23 KB (per instance) | 25 KB | 43 KB |
| **NVM** (for history) | 23 KB | 25 KB | 43 KB |
| **Stack RAM** | 3.5 KB | 0.8 KB | 1.7 KB |
| **MIPS** | 0.6 MIPS | 1.5 MIPS | Peak 91.8 / Median 0.2 MIPS |

### 13.2 Memory Allocation Rules

- Instance memory MUST be aligned to **32-bit word boundary** (use `uint32_t` array).
- Allocate at least the size returned by `PSP_GetDefaultParams()`.
- Example: `uint32_t pspmem[PSP_MEMORY_SIZE / 4];` with `PSP_MEMORY_SIZE = 50000`.
- Instance memory must be declared **static** so the address is the same after reboot (important for NVM restore).
- Do NOT modify the instance memory during the library's lifecycle.

### 13.3 Data Logging Storage

- Approximately 20.5 KB per minute of sensor data.
- Approximately 0.5 MB per hour.
- Minimum transmission rate: 3.5 kbps for real-time streaming.

### 13.4 Library Deployment

- PSP binary is loaded at a **fixed predetermined memory address** (0x000E0000 for CoreKinect).
- Linker must reserve the code memory range for the library.
- Two methods: Keil uVision5 (scatter file + INCBIN) or IAR Embedded Workbench (--image_input linker option).
- Binary can also be merged with application image using `srec_cat.exe` before flashing.

---

## 14. Sensor Signal Requirements Per Metric

Summary of which sensors must provide continuous data for each output metric:

| Metric | PPG | ACC | SC | Gyro/Baro | Update Rate |
|--------|-----|-----|----|-----------|-------------|
| Heart Rate | Continuous | Continuous | - | - | 1 sec |
| Low Power Heart Rate | 6-15 sec/min | Continuous | - | - | 60 sec |
| Resting Heart Rate | 1 min per 15 min inactive | Continuous | - | - | 3600 sec |
| Respiration Rate | Continuous | Continuous | - | - | 1 sec |
| Heart Beat Timestamps | Continuous | Continuous | - | - | 1 sec |
| Active Energy Expenditure | Continuous | Continuous | - | - | 1 sec |
| Low Power AEE | 6-15 sec/min | Continuous | - | - | 60 sec |
| Activity Type | - | Continuous | - | - | 1 sec |
| Activity Count | - | Continuous | - | - | 1 sec |
| Cadence | - | Continuous | - | - | 1 sec |
| Speed | - | Continuous | - | - | 1 sec |
| VO2Max | Continuous | Continuous | - | - | 60 sec |
| Fitness Index | Continuous | Continuous | - | - | 60 sec |
| SpO2 | Continuous | Continuous | - | - | 1 sec |
| Skin Proximity | Continuous (on-skin); during movement (off-skin) | Continuous | Optional | - | 1 sec |
| Stress Level HR | Continuous | Continuous | - | - | 1 sec |
| Private Data | - | Continuous | - | - | 60 sec |
| Sleep Stages | Continuous | Continuous | - | - | Async (session end) |
| Stress Level SC | - | - | Continuous | - | 1 sec |
| Cognitive Zone | - | - | Continuous | - | 60 sec |
| Fall Occurrence | - | Continuous | - | Continuous | 1 sec |
| Compressed PPG | Continuous | - | - | - | 1 sec |
| Compressed ACC | - | Continuous | - | - | 1 sec |

---

## Appendix: Firing Sequence for MAX86178 AFE

For the Philips reference multi-color design with MAX86178 AFE:
- 6 measurements per sample period at 32 Hz (31.25 ms interval)
- LED pulse duration: 117 us each
- SpO2 sequence: M1(Red-top), M2(Red-bottom), M3(IR-top), M4(IR-bottom), M5(Green-center), M7(Ambient)
- HR-only sequence: M5(Green-center), M7(Ambient)
- Red and IR firings should be close together in time

## Appendix: Crosstalk Test Thresholds

- Green LED (HR): PPG count < 5K out of 2^19 (with black rubber patch, 100% LED current, max gain)
- Red/IR LED (SpO2): PPG count < 600 out of 2^19

## Appendix: SNR Test Criteria

- Green channel: SNR > 80 dB at required operating current
- Red and IR channels: SNR > 85 dB at required operating current
- Measured with reflector in black box, staircase current profile, 3-second windows
