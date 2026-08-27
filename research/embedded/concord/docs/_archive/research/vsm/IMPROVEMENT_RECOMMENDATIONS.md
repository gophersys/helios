# VSM Improvement Recommendations

**Date:** 2026-02-09
**Last Updated:** 2026-02-10
**Synthesized from:** CSV Data Analysis, VSM Driver Architecture, PAH8151 PPG Driver Analysis, LSM6DSO Motion Driver Analysis, PSP Library Requirements, Alpha App Build Configuration, PixArt PAH8151 Vendor Documentation

This document cross-references findings from all seven research documents to produce prioritized, evidence-based recommendations for improving heart rate accuracy, SpO2 reliability, and overall vital signs monitoring quality on the Alpha wearable platform.

---

## 1. Critical Issues (Immediate Impact on HR Quality)

### 1.1 ~~Accelerometer Downsampling Lacks Anti-Aliasing Filter~~ [DONE]

- **Priority:** P0 (critical)
- **Status:** **FIXED (2026-02-10)**
- **Impact:** Degraded HR accuracy during motion, increased false HR jumps
- **Effort:** Medium
- **What was done:** Replaced the timestamp-weighted average downsampling with a full Philips-compliant pipeline: (1) linear interpolation from 52 Hz to 64 uniformly-spaced samples, (2) 5th-order elliptic IIR half-band anti-aliasing filter (~46 dB stopband rejection) in polyphase allpass decomposition, (3) 2x decimation to 32 Hz output. Filter state persists across batches via the `vsm_t` structure and resets on touch-detected transitions. **Result:** HR Q:4 held through sustained 1.48g motion (previously dropped at ~1.4g).

---

### 1.2 ~~Channel Mapping Bug: Red/Green AE Metadata Swapped~~ [NOT A BUG]

- **Priority:** ~~P0 (critical)~~ N/A
- **Status:** **NOT A BUG (2026-02-10)** — Reverted after empirical validation.
- **Original Assessment:** Appeared that AE metadata channels (Expo_time_A, LEDDAC_A) should map to Green (matching FIFO intensity channel A=Green). However, swapping the metadata to match FIFO ordering caused SpO2 to stay permanently at Q:0.
- **Finding:** The AE metadata channel ordering is **different from the FIFO intensity channel ordering**. In the AE info struct, channel A corresponds to Red (not Green). The original mapping (`Expo_time_A` → `red_expo_us`) was correct. The FIFO raw data uses a different channel order than the AE metadata — this is a PixArt SDK implementation detail, not a bug.
- **Validation:** SpO2 achieves Q:4 at 99% with the original mapping. Swapping to match FIFO order breaks SpO2 completely.

---

### 1.3 ~~Synthesized Accelerometer Timestamps Cause Phase Misalignment~~ [DONE]

- **Priority:** P0 (critical)
- **Status:** **FIXED (2026-02-09)**
- **Impact:** Up to 22 ms timestamp error on oldest samples in each batch, degrading PSP's motion artifact cancellation
- **Effort:** Medium
- **What was done:** Enabled LSM6DSO hardware timestamp batching (`odr_ts_batch` in FIFO_CTRL4). The FIFO read now parses `LSM6DSO_TIMESTAMP_TAG` entries to get true inter-sample timing at 25 µs resolution. Hardware timestamps are anchored to a single `k_uptime_get_32()` reference point per batch, eliminating the back-calculated timing assumption.

---

### 1.4 ISR Performs Extensive I2C Work -- Blocks Interrupts for 10-15 ms

- **Priority:** P1 (high)
- **Impact:** Potential missed sensor interrupts, BLE timing violations, UART data loss; indirectly affects data pipeline reliability
- **Effort:** High
- **Evidence:**
  - VSM Driver Architecture document (Section 10.1) identifies that `_ppg_data_ready_handler` runs in ISR context and performs hundreds of bytes of I2C transfers (full IMU FIFO read + 32 PPG sample reads).
  - At 400 kHz I2C, transferring ~500+ bytes takes 10-15 ms during which all lower-priority interrupts are blocked.
  - The Alpha App Build Configuration shows the BLE thread runs at priority 3, the IPC UART runs at 460800 baud -- both are time-sensitive and can be disrupted by extended ISR blocking.
  - The shell UART (115200 baud for manufacturing) could lose characters during the ISR window.

**Recommendation:** Move the sensor read operations from ISR context to the vitals thread using a deferred work pattern. The ISR should only signal a semaphore; the thread should perform all I2C reads. This is a structural change that requires careful sequencing to avoid data loss between the interrupt assertion and the thread read, but it follows standard Zephyr best practices for I2C-intensive sensor drivers.

---

### 1.5 ~~PPG Scaling Calibration State Not Reset on PSP Reset~~ [DONE]

- **Priority:** P1 (high)
- **Status:** **FIXED (2026-02-09)**
- **Impact:** Incorrect PPG signal scaling after touch-lost/touch-regained transitions, causing PSP to receive data outside its optimal input range
- **Effort:** Low
- **What was done:** Added `memset(&p_thread->ppg_cal_state, 0, sizeof(p_thread->ppg_cal_state))` in the `TOUCH_DETECTED` state handler, alongside the existing PSP reset. Also resets the IIR anti-aliasing filter state at the same point. Each measurement session now starts with fresh calibration and filter state.

---

## 2. Configuration Optimizations (Tuning Existing Settings)

### 2.1 DTS Accelerometer Range Mismatch: +/-8g Configured but Driver Forces +/-2g

- **Priority:** P1 (high)
- **Impact:** PSP format byte (0x6E) claims +/-8g range while actual data is +/-2g, causing PSP to misinterpret accelerometer magnitude by 4x
- **Effort:** Low
- **Evidence:**
  - Alpha App Build Configuration (Section 3) shows DTS `accel-range = <3>` which maps to +/-8g.
  - LSM6DSO Motion Driver Analysis (Section 3) reveals the driver overrides this to +/-2g in `lsm6dso_init()`: `lsm6dso_xl_full_scale_set(ctx, LSM6DSO_2g)` with hardcoded 0.061 mg/LSB sensitivity.
  - VSM Driver Architecture (Section 3.4) shows the PSP accelerometer format byte is set to `0x6E` which encodes "+/- 8G range, 13-bit signed, 1/512 g/unit."
  - PSP Library Requirements (Section 2.2) specifies the accelerometer must provide "+/- 8 g" dynamic range.
  - If the actual sensor is at +/-2g but PSP interprets the data as +/-8g scale (1/512 g per unit at 8g range), the acceleration values fed to PSP would be 4x too small, severely undermining motion artifact cancellation.

**Recommendation:** Verify the actual unit conversion chain end-to-end. The VSM `transform.c` converts from m/s^2 to g, then multiplies by 512 to get PSP units. If the sensor is at +/-2g and the raw data is in mg with 0.061 mg/LSB sensitivity, the conversion to g-force is correct regardless of the full-scale setting. However, the format byte 0x6E tells PSP the data could go up to +/-8g. At +/-2g, values above 2g would clip. Either: (a) change the sensor to actually use +/-8g (change to 0.244 mg/LSB) to match the PSP format byte, or (b) if +/-2g is sufficient for wrist motion, change the PSP format byte to reflect the true range. Option (a) is preferred because PSP documentation explicitly requires +/-8g range and wrist impacts during activities can exceed 2g.

---

### 2.2 Gyroscope Data Read but Not Used

- **Priority:** P2 (medium)
- **Impact:** Wasted I2C/SPI bandwidth and ISR time; PSP supports gyroscope input for improved motion artifact rejection
- **Effort:** Medium
- **Evidence:**
  - VSM Driver Architecture (Section 10.11) notes: "The IMU read collects both accelerometer and gyroscope data (X/Y/Z for both), but only accelerometer data is used. Gyroscope data is read and discarded."
  - LSM6DSO Motion Driver Analysis (Section 4) confirms gyroscope FIFO batching is disabled, but gyro is still sampled at 26 Hz (DTS `gyro-odr=2`), consuming power (~550 uA in high-performance mode).
  - PSP Library Requirements (Section 2.5) defines gyroscope input requirements: 50 Hz, +/-2000 dps, 16-bit signed, 0.061 dps per unit. PSP can use gyroscope data for improved motion artifact removal.
  - The LSM6DSO driver currently reads gyro data in the ISR (if present in the FIFO) but the VSM driver ignores it.

**Recommendation:** Either: (a) Feed gyroscope data to PSP via `PSP_METRIC_ID_GYRO` for improved motion artifact cancellation (requires upsampling from current 26 Hz to 50 Hz per PSP requirements), or (b) fully disable the gyroscope (set ODR to 0 / power-down mode) to save ~550 uA and reduce ISR time. Option (b) is recommended short-term for power savings; option (a) should be evaluated if motion artifact performance is insufficient after other fixes.

---

### 2.3 Skin Detection Period May Be Too Long

- **Priority:** P2 (medium)
- **Impact:** 6-second detection period delays measurement start; first 3+ minutes of data already show low confidence
- **Effort:** Low
- **Evidence:**
  - Alpha App Build Configuration (Section 2) shows `skin_detection_period_ms = 6000` (6 seconds).
  - The CSV Data Analysis (Section 3) shows the first 12 samples (~3 minutes) have exclusively low confidence (25), not just the first 6 seconds.
  - VSM Driver Architecture (Section 7.2) shows the valid range for `skin_detection_period_ms` is 500-10000 ms.
  - The 6-second delay adds latency to the start of meaningful measurement but does not appear to prevent the 3-minute PSP convergence period.

**Recommendation:** The 6-second skin detection period is reasonable for reliable skin contact confirmation. The 3-minute low-confidence startup period is inherent to the PSP algorithm convergence (not the skin detection). Consider reducing `skin_detection_period_ms` to 2000-3000 ms to improve responsiveness while still filtering out brief touches. The application should flag data during the first 3 minutes as unreliable regardless of skin detection timing.

---

### 2.4 Green LED DAC Maximum May Be Too Low for Dark Skin

- **Priority:** P2 (medium)
- **Impact:** Insufficient green LED optical power on darker skin tones could reduce PPG SNR below the 80 dB threshold
- **Effort:** Low
- **Evidence:**
  - PAH8151 PPG Driver Analysis (Section 4) shows Green channel DAC max is 63 (25.2 mA) vs. 127 (50.8 mA) for Red and IR.
  - PSP Library Requirements (Section 2.1) requires Green channel SNR > 80 dB.
  - PixArt Vendor Docs (Section 4.5) shows Green has the longest maximum exposure time (3000T) to compensate for lower LED current, but this increases frame time.
  - The AEC system will maximize both exposure time and LED current if the signal is too weak. If both max out before reaching adequate SNR, measurement quality degrades.
  - The CSV Data shows HSI (Heart Signal Index) starting low (0.2-0.8 range for 7.2% of samples), particularly in the first quarter of the session.

**Recommendation:** Monitor AEC convergence by logging exposure time and DAC values during operation. If the Green channel consistently hits both DAC max (63) and exposure max (3000T) on darker skin tones, increase the Green DAC max toward 127 to provide more headroom. This change should be validated against power budget constraints (higher LED current increases battery drain).

---

### 2.5 SpO2 Watermark Difference from SDK Default

- **Priority:** P2 (medium)
- **Impact:** Potentially suboptimal SpO2 measurement timing; PixArt SDK uses 25 for SpO2 mode
- **Effort:** Low
- **Evidence:**
  - PixArt Vendor Docs (Section 8.1) shows in-repo config uses `PPG_WATERMARK_SpO2 = 32` vs. SDK default of 25.
  - The in-repo firmware initializes the sensor with Config 5 (32 Hz, 3-channel) and watermark 32, meaning the interrupt fires every 1 second.
  - The HRD_SPO2 SDK uses Config 4 (25 Hz, Red+IR) with watermark 25 for dedicated SpO2 mode, also firing every 1 second but at 25 Hz.
  - The PSP library expects 32 samples at 32 Hz (format 0x60), so the current watermark of 32 at 32 Hz is correct for PSP integration.

**Recommendation:** The current watermark of 32 at 32 Hz is correct for PSP integration and provides 1-second batches as required. No change needed. However, if a dedicated SpO2 mode is ever implemented using PixArt's PXI SpO2 algorithm (not PSP), revert to the SDK's recommended watermark of 25 with Config 4 (25 Hz, Red+IR).

---

### 2.6 ~~Accelerometer Power Mode Set to Normal Instead of High Performance~~ [DONE]

- **Priority:** P2 (medium)
- **Status:** **FIXED (2026-02-10)**
- **Impact:** Reduced accelerometer bandwidth and increased noise compared to high-performance mode
- **Effort:** Low
- **What was done:** Implemented dynamic power mode switching in `lsm6dso.c` `reconfigure()`. When FIFO accel is active and ODR ≤ 52 Hz (vitals monitoring), the driver now uses `HIGH_PERFORMANCE_MD` for optimal noise density. When only motion detection is active (no FIFO), it stays in `ULTRA_LOW_POWER_MD` to save power. This provides the best of both worlds: high-quality accel data during active monitoring sessions, minimal power draw otherwise.

---

## 3. Signal Processing Improvements (Code Changes)

### 3.1 ~~Implement Philips-Recommended Interpolation Pipeline~~ [DONE]

- **Priority:** P0 (critical)
- **Status:** **FIXED (2026-02-10)** — See 1.1 above.
- **Impact:** Correct ACC resampling per PSP specifications; directly improves HR accuracy during motion
- **Effort:** Medium
- **What was done:** Implemented the full pipeline: linear interpolation to 64 samples → IIR half-band anti-aliasing filter → 2x decimation to 32 samples. Used a 5th-order elliptic IIR in polyphase allpass decomposition (coefficients: c0=0.0799, c1=0.5454, c2=0.2838) instead of the Philips-provided FIR, achieving ~46 dB stopband rejection vs ~22 dB for a 7-tap FIR. Filter state persists across batches in `vsm_t.aa_filter_state`.

---

### 3.2 Improve PPG-ACC Synchronization Using PPG Clock as Reference

- **Priority:** P1 (high)
- **Impact:** Eliminates clock drift between PPG and accelerometer, improving PSP's motion artifact cancellation
- **Effort:** Medium
- **Evidence:**
  - PSP Library Requirements (Section 5.2) recommends: "Use the PPG clock as the timing reference. On each PPG interrupt, also read the ACC FIFO. The ACC may have a variable number of samples due to clock drift. Resample the ACC to exactly 32 samples."
  - The VSM Driver Architecture (Section 2.2) shows this is already partially implemented: the PPG data-ready ISR reads the IMU FIFO as its first action.
  - However, the downsampling does not account for the actual number of accelerometer samples received. It should dynamically interpolate from N received samples to exactly 32, rather than assuming approximately 52 samples per second.
  - The CSV Data Analysis shows HR confidence is significantly lower during motion (mean 77.4 vs. 94.9 during still), which is partly attributable to imperfect PPG-ACC synchronization.

**Recommendation:** Modify the downsampling logic to dynamically interpolate from the actual number of accelerometer samples received (N) to exactly 32 output samples per PPG batch, rather than assuming N is always close to 52. This naturally compensates for clock drift between the sensors.

---

### 3.3 ~~Feed Acceleration Data Before PPG Data to PSP~~ [DONE]

- **Priority:** P1 (high)
- **Status:** **FIXED (2026-02-09)**
- **Impact:** PSP documentation requires specific input ordering; incorrect ordering may affect algorithm convergence
- **Effort:** Low
- **What was done:** Reordered `PSP_SetMetric()` calls in `_psp_update_input_metrics()` so acceleration is fed before the four PPG metrics (IR, Red, Green, Ambient), matching the PSP-required ordering.

---

### 3.4 ~~Implement HR Clock Drift Compensation~~ [DONE]

- **Priority:** P2 (medium)
- **Status:** **FIXED (2026-02-10)**
- **Impact:** Corrects systematic HR bias caused by PPG clock drift
- **Effort:** Low
- **What was done:** Added drift compensation after `_psp_get_output_metrics()` in the ACTIVE_MONITORING processing path. Computes actual PPG batch duration from first/last sample timestamps vs nominal (31/32s), applies `drift_ratio = t_nominal / t_actual` to the reported HR value. Clamped to ±5% to avoid applying corrections from corrupted timestamps.

---

### 3.5 Add Accelerometer Offset Calibration

- **Priority:** P2 (medium)
- **Impact:** PSP requires < 150 mg offset on any axis; uncalibrated sensors may exceed this
- **Effort:** Medium
- **Evidence:**
  - PSP Library Requirements (Section 2.2) states: "Allowed 0g Offset: < 150 mg on any axis. If the accelerometer offset exceeds 150 mg, offset calibration is required."
  - The LSM6DSO Motion Driver Analysis shows no offset calibration is implemented. The raw data is converted with a fixed 0.061 mg/LSB factor.
  - LSM6DSO typical zero-g offset is +/-40 mg (datasheet typical), but individual units can be worse, and PCB stress can add additional offset.

**Recommendation:** Implement a one-time factory calibration step that: (1) places the device on a known flat surface, (2) collects 5-10 seconds of accelerometer data, (3) computes the mean offset on each axis (expecting [0, 0, 1g]), (4) stores the offset correction in NVS, (5) applies the correction during normal operation. Add a manufacturing test that verifies per-axis offset is within the 150 mg specification.

---

## 4. Data Quality Observations (From CSV Analysis)

### 4.1 Overall HR Quality Assessment

- **Priority:** Observational
- **Evidence:** CSV Data Analysis Sections 2-4
- **Findings:**
  - HR availability is 100% (all 512 rows have HR values) -- no data loss in the pipeline.
  - 79.9% of readings achieve confidence >= 75, which is acceptable but below the PSP validation benchmarks (Overall availability Q>=1 is 99.5%, Q>=4 is 75.4% per PSP Requirements Section 9.2).
  - The confidence values are discrete at 25-point intervals (25, 50, 75, 100), suggesting the VSM driver maps PSP quality (0-4) to confidence via `quality * 25`.
  - Mean HR confidence during still periods (94.9) vs. motion (77.4) shows a 17.5-point degradation, indicating motion artifact cancellation is functional but has room for improvement.

### 4.2 Startup Convergence Period

- **Priority:** P2 (medium) for application-level handling
- **Evidence:** CSV Data Analysis Sections 3, 12
- **Findings:**
  - The first 12 samples (~3 minutes) show exclusively low confidence (25) with HR variability of 70-104 BPM.
  - This matches PSP behavior: the algorithm needs time to converge, especially for the first HR estimate.
  - PSP Requirements (Section 10.9) states Stress Level HR "lock-in time" is roughly < 5 minutes, suggesting 3 minutes for basic HR convergence is within expected bounds.

**Recommendation:** The application layer should flag or suppress HR readings during the first 3 minutes (approximately 18 samples at 10-second cadence) or until confidence exceeds 50 for at least 3 consecutive readings. The VSM warm-up constant (`CONFIG_VITALS_WARMUP_PERIOD = 6000 ms`) is far too short for this purpose; consider increasing it or implementing a separate algorithm convergence tracker.

### 4.3 Duplicate Records Suggest Transmission Issue

- **Priority:** P2 (medium) for cloud/comms team
- **Evidence:** CSV Data Analysis Section 8
- **Findings:**
  - 34% of records are exact duplicates (same measurement values, different server timestamps, average 15s apart).
  - This is a transmission-layer issue, not a VSM driver issue. It is likely caused by a retry mechanism in the nRF9151 cellular uplink or the cloud ingestion pipeline.

**Recommendation:** Add deduplication in the cloud ingestion pipeline using (device_id, measurement_timestamp) as a unique key. On the firmware side, investigate whether the store-and-forward mechanism or IPC retry logic is double-sending measurements.

### 4.4 SpO2 Intermittency Pattern

- **Priority:** P2 (medium)
- **Evidence:** CSV Data Analysis Section 5
- **Findings:**
  - SpO2 is available only 28.1% of the time despite all three PPG channels being active.
  - SpO2 availability is much higher during still periods (54.8%) vs. motion (23.7%).
  - PSP Library Requirements (Section 10.4) states SpO2 "Requires sitting still, wrist resting on table, no motion."
  - The 17-minute SpO2 outage (21:57-22:14 UTC) coincides with a period of continuous motion.

**Recommendation:** This intermittency appears to be expected PSP behavior -- SpO2 measurement requires minimal motion. The application should communicate to the user that SpO2 readings require stillness. Consider switching to Config 1 (Green only, 32 Hz) during detected motion periods to save power, reverting to Config 5 (3-channel) during still periods.

### 4.5 Force Data Not Populated

- **Priority:** P3 (nice-to-have)
- **Evidence:** CSV Data Analysis Section 10
- **Findings:**
  - All `avgforce` and `maxforce` values in pos.csv are 0.0 despite active motion detection.
  - The accelerometer is configured and operational (motion state machine works), but force magnitude is not being calculated or reported.

**Recommendation:** If force data is needed for safety applications (e.g., fall detection, impact alerts), implement the force magnitude calculation in the motion state machine: `force = sqrt(x^2 + y^2 + z^2)`. Track min/max/avg over each reporting period.

---

## 5. Architecture Improvements (Longer-Term)

### 5.1 Move Sensor Reads Out of ISR Context

- **Priority:** P1 (high)
- **Impact:** Eliminates 10-15 ms interrupt blocking, improves system-wide timing reliability
- **Effort:** High
- **Evidence:** See Section 1.4 above.

**Recommendation:** Restructure the data pipeline to use a two-phase approach:
1. ISR phase: Only signal `ppg_data_ready_sem` (takes < 1 us).
2. Thread phase: Read IMU FIFO, then read PPG FIFO, then process.
This requires ensuring the PPG FIFO does not overflow between interrupt assertion and thread read. With a 132-sample max FIFO capacity (at 3 channels) and 32-sample watermark, there is a 100-sample margin (~3.1 seconds at 32 Hz), providing ample time for thread scheduling.

### 5.2 Implement Dual-Mode PPG Configuration

- **Priority:** P2 (medium)
- **Impact:** Significant power savings when SpO2 is not needed; Config 1 (1 channel, 32 Hz) uses ~1/3 the LED power of Config 5 (3 channels)
- **Effort:** Medium
- **Evidence:**
  - PixArt Vendor Docs (Section 1.4) defines Config 1 (Green only, 32 Hz) for basic HR and Config 5 (all channels, 32 Hz) for one-key measurement.
  - PSP Library Requirements (Section 14) shows Heart Rate requires only PPG-Green + Acceleration, while SpO2 additionally requires PPG-Red + PPG-IR.
  - The CSV Data Analysis shows SpO2 is only measurable during still periods (54.8% availability vs. 23.7% during motion). Running all three LEDs during motion wastes power.

**Recommendation:** Implement a motion-aware PPG mode switch:
- During motion: Config 1 (Green only, 32 Hz) -- saves ~2/3 of LED power.
- During still periods: Config 5 (all channels, 32 Hz) -- enables SpO2 measurement.
- On transition: Allow 2-3 seconds for AEC re-convergence on newly enabled channels.
This requires the motion state machine to communicate with the VSM driver.

### 5.3 Enable PSP Algorithm State Persistence Across Resets

- **Priority:** P2 (medium)
- **Impact:** Eliminates the 3-minute convergence period after brief touch-lost events
- **Effort:** Medium
- **Evidence:**
  - VSM Driver Architecture (Section 4.6) shows the PSP algorithm is fully reset via deinit/init on each `TOUCH_DETECTED` transition, clearing all internal state.
  - PSP Library Requirements (Section 7.2) describes a "Restart Maintaining History" pattern where the entire PSP instance RAM can be saved to NVM and restored, preserving accumulated metrics.
  - The CSV Data Analysis shows the first 3 minutes produce unreliable data. If the device briefly loses skin contact (e.g., adjusting the strap), the full 3-minute convergence period restarts.

**Recommendation:** For brief touch-lost events (< 30 seconds), skip the PSP reset and continue processing. Only perform a full PSP reset for extended off-wrist periods (> 2 minutes) where signal conditions will have changed significantly. Alternatively, implement the NVM save/restore pattern from PSP documentation to preserve algorithm state across resets.

### 5.4 Implement SNR and Reflectivity Manufacturing Tests

- **Priority:** P2 (medium)
- **Impact:** Catch defective sensors before they reach production; currently only cross-talk is tested
- **Effort:** Medium
- **Evidence:**
  - VSM Driver Architecture (Section 9.2-9.3) documents that SNR and reflectivity tests are stubs returning `passed = false`.
  - PSP Library Requirements (Appendix: SNR Test Criteria) specifies Green > 80 dB, Red/IR > 85 dB.
  - PixArt Vendor Docs (Section 10) shows the factory test infrastructure exists in the SDK.
  - A device that passes cross-talk but fails SNR could produce marginal PPG data -- the sensor would work but with degraded HR accuracy.

**Recommendation:** Implement the SNR test using the planned staircase current profile with a calibrated reflector fixture. Define pass/fail thresholds per PSP specifications (Green > 80 dB, Red/IR > 85 dB). This test should run during MTIB validation before devices ship.

### 5.5 Fix Deactivate Monitoring Path

- **Priority:** P3 (nice-to-have)
- **Impact:** Currently, once monitoring starts, there is no clean way to return to IDLE state
- **Effort:** Low
- **Evidence:**
  - VSM Driver Architecture (Section 10.3) documents that the `STATE_REQUEST_DEACTIVATE_MONITORING` handler is entirely commented out.
  - The only paths out of `ACTIVE_MONITORING` are hardware error, watchdog timeout, or `vsm_deinit()`.
  - The deskin detection shortcut (Section 10.2) also immediately confirms deskin without temperature verification.

**Recommendation:** Implement the deactivate monitoring path and the proper deskin temperature verification. This enables cleaner state management and more graceful handling of off-wrist transitions.

---

## 6. Vendor Recommendation Gaps

### 6.1 ~~PSP Requires ACC Before PPG in SetMetric Order~~ [DONE]

- **Priority:** P1 (high)
- **Status:** **FIXED (2026-02-09)** — See Section 3.3 above.

### 6.2 ~~PSP Requires Anti-Aliased ACC Downsampling~~ [DONE]

- **Priority:** P0 (critical)
- **Status:** **FIXED (2026-02-10)** — See Sections 1.1 and 3.1 above.

### 6.3 PixArt SDK Uses 20 Hz for HRD, In-Repo Uses 32 Hz

- **Priority:** P2 (medium) -- informational
- **Gap:** The PixArt HRD_SPO2 SDK configures PPG at 20 Hz for heart rate detection mode, while the in-repo firmware uses 32 Hz (Config 5).
- **PixArt Recommendation:** HRD mode at 20 Hz with watermark 20 for optimal PXI algorithm performance.
- **Evidence:** PixArt Vendor Docs (Section 2.4) summarizes: HRD = 20 Hz, SpO2 = 25 Hz, RAW = 32 Hz.
- **Context:** The Alpha firmware does not use the PXI algorithm; it uses the Philips PSP library which requires 32 Hz. The 32 Hz configuration is correct for PSP integration. This gap is expected and intentional.

### 6.4 PixArt Recommends CAP Touch Detection, In-Repo Has It Disabled [WONTFIX]

- **Priority:** P3 (nice-to-have)
- **Status:** **WONTFIX** — Intentionally keeping CAP touch disabled. IR-only touch detection is working reliably for the current hardware design. CAP touch adds calibration complexity and is not needed.
- **Gap:** In-repo firmware sets `ENABLE_CAP_TOUCH_DETECT = 0`, relying only on IR touch.
- **PixArt Recommendation:** HRD_SPO2 SDK enables both IR and CAP touch for more robust wear detection.

### 6.5 ~~PSP Body Position Index Should Be Set Correctly~~ [DONE]

- **Priority:** P2 (medium)
- **Status:** **FIXED (2026-02-09)**
- **What was done:** Set the accelerometer BPI to 2 (right wrist) to match the PPG BPI, ensuring PSP receives consistent body position context for SpO2 orientation checks.

### 6.6 SpO2 Calibration Coefficients Need Device-Specific Calibration

- **Priority:** P1 (high) -- for SpO2 accuracy
- **Gap:** Unknown whether the current `calCoefSpO2[3]` values have been calibrated for the Alpha hardware.
- **PSP Specification:** "Calibration is sensor-geometry and wavelength specific -- each device design needs calibration" (PSP Requirements Section 8.3). Requires validation with at least 20 subjects per the wellness calibration protocol.
- **Evidence:** PSP Library Requirements (Section 11.4) describes a detailed calibration protocol involving 20+ subjects, 15% dark skin, and reference pulse oximetry.
- **Recommendation:** If SpO2 accuracy matters for the product, perform the wellness-domain calibration study to derive correct `calCoefSpO2` values for the Alpha hardware's specific optical geometry and LED wavelengths. Without proper calibration, SpO2 values should be treated as indicative only.

### 6.7 ~~IMU Buffer Overflow Risk~~ [DONE]

- **Priority:** P1 (high)
- **Status:** **FIXED (2026-02-09)**
- **What was done:** Added a clamp in the accel downsampler to cap the input sample count to the buffer size (52). When 53-54 samples arrive from the FIFO, the excess samples are safely ignored rather than causing an out-of-bounds write.

---

## Priority Summary

| Priority | Total | Done | Remaining | Items |
|----------|-------|------|-----------|-------|
| P0 (Critical) | 4 | **2** | 1 | ~~ACC anti-aliasing filter (1.1, 3.1, 6.2)~~, ~~Red/Green AE swap (1.2)~~ [NOT A BUG], ~~ACC timestamps (1.3)~~, ACC full-scale mismatch (2.1) |
| P1 (High) | 8 | **4** | 4 | ISR duration (1.4), ~~PPG cal reset (1.5)~~, PPG-ACC sync (3.2), ~~ACC-before-PPG order (3.3, 6.1)~~, SpO2 calibration (6.6), ~~Buffer overflow (6.7)~~, Move ISR work to thread (5.1) |
| P2 (Medium) | 10 | **3** | 7 | Gyro unused (2.2), Skin detect period (2.3), Green LED DAC (2.4), ~~HR drift compensation (3.4)~~, ACC offset cal (3.5), Startup handling (4.2), Duplicates (4.3), Dual-mode PPG (5.2), PSP state persist (5.3), ~~Accel power mode (2.6)~~, ~~BPI (6.5)~~ |
| P3 (Nice-to-have) | 3 | **0** | 3 | Force data (4.5), Deactivate path (5.5), ~~CAP touch (6.4)~~ [WONTFIX] |

**Overall: 9 of 25 recommendations resolved (36%).** 1.2 (AE swap) was found to not be a bug — AE metadata uses different channel ordering than FIFO intensity data.

## Quick Wins (Low Effort, High Impact)

1. ~~**Fix Red/Green AE metadata swap**~~ (P0, Low effort) -- **NOT A BUG** (AE metadata uses different channel order than FIFO)
2. ~~**Reverse ACC/PPG SetMetric order**~~ (P1, Low effort) -- **DONE**
3. ~~**Reset PPG calibration state on PSP reset**~~ (P1, Low effort) -- **DONE**
4. ~~**Fix IMU buffer overflow**~~ (P1, Low effort) -- **DONE**
5. ~~**Change accel power mode to high-performance**~~ (P2, Low effort) -- **DONE**

All original quick wins have been completed. See [PPG_SPO2_TUNING_OPPORTUNITIES.md](./PPG_SPO2_TUNING_OPPORTUNITIES.md) for deferred SpO2/power tuning opportunities.
