# VSM (Vital Signs Monitoring) Research Documents

**Date:** 2026-02-09
**Last Updated:** 2026-02-10
**Platform:** Alpha B0 Wearable (nRF52840 + PAH8151 PPG + LSM6DSO IMU + Philips PSP)

This directory contains deep-dive research documents analyzing the Alpha wearable's vital signs monitoring subsystem. The goal is to identify improvements to heart rate accuracy, SpO2 reliability, and overall data quality.

---

## Documents

### [IMPROVEMENT_RECOMMENDATIONS.md](./IMPROVEMENT_RECOMMENDATIONS.md)
**Synthesis document.** Cross-references all research findings into prioritized, actionable recommendations organized by category: critical issues, configuration optimizations, signal processing improvements, data quality observations, architecture improvements, and vendor recommendation gaps. Each recommendation includes priority level (P0-P3), expected impact, effort estimate, and specific evidence references. **Updated 2026-02-10:** 10 of 25 recommendations resolved (all P0 critical except ACC full-scale mismatch, all quick wins complete).

### [PPG_SPO2_TUNING_OPPORTUNITIES.md](./PPG_SPO2_TUNING_OPPORTUNITIES.md)
**Deferred tuning catalog.** Documents 7 known tuning opportunities for the PAH8151 PPG sensor and PSP SpO2 pipeline. These are not critical — SpO2 currently achieves Q:4 at 99% during still periods — but represent potential improvements for signal robustness on darker skin tones, power efficiency, and edge-case scenarios. Covers: Red/IR exposure time increases, AEC convergence bounds, Green LED current reduction, SpO2 calibration coefficients, DTS LED property wiring, AEC step size tuning, and motion-aware PPG mode switching.

### [CSV_DATA_ANALYSIS.md](./CSV_DATA_ANALYSIS.md)
**Live data analysis.** Statistical analysis of 512 bio.csv rows and 145 pos.csv rows captured from a field session in Scottsdale, AZ. Covers HR distribution (69-124 BPM, mean 91.7), confidence patterns (79.9% at >= 75), SpO2 intermittency (28.1% availability), temperature trends, motion correlation, duplicate record detection (34% of rows), and measurement timing analysis.

### [VSM_DRIVER_ARCHITECTURE.md](./VSM_DRIVER_ARCHITECTURE.md)
**VSM module architecture.** End-to-end analysis of the VSM driver (`_fw_build/vsm_drv/`): data pipeline from sensor interrupt through PSP processing to application callback, thread model (vitals thread at priority 3, BLE thread at priority 4), state machine (IDLE through ACTIVE_MONITORING), PSP integration details (ROM-resident library at 0xE0000), BLE output format, and 12 identified potential issues including ISR duration concerns, buffer overflow risks, and timestamp domain mismatches.

### [PAH8151_PPG_DRIVER_ANALYSIS.md](./PAH8151_PPG_DRIVER_ANALYSIS.md)
**PPG sensor driver deep dive.** Four-layer architecture analysis (CK Wrapper, SDK Main, SDK Core, HAL/Comm), operating modes (AUTO_MODE with DRI), sampling rate configuration (32 Hz Config 5, 3-channel), LED configuration (Green/Red/IR channel mapping and DAC limits), FIFO operation (1584-byte buffer, watermark 32), I2C interface details, and factory test thresholds. Identifies a critical Red/Green AE metadata swap bug and several tuning opportunities.

### [LSM6DSO_MOTION_DRIVER_ANALYSIS.md](./LSM6DSO_MOTION_DRIVER_ANALYSIS.md)
**Accelerometer/gyroscope driver analysis.** Two-phase initialization, ODR configuration (52 Hz enforced for accel), full-scale range handling (+/-2g override despite +/-8g DTS config), FIFO configuration (stream mode, 52-sample watermark), synthesized timestamps (no hardware timestamps enabled), motion detection interrupt setup, and detailed analysis of accel-PPG synchronization issues including quantified timing error estimates.

### [PSP_LIBRARY_REQUIREMENTS.md](./PSP_LIBRARY_REQUIREMENTS.md)
**Philips PSP integration requirements.** Extracted from the PSP 6.1.x documentation suite (9 documents). Covers input data requirements (32 Hz PPG, 32 Hz ACC), interpolation and resampling specifications (with anti-aliasing filter requirements), data format specifications (PPG metric format, ACC format 0x6E), timing and synchronization requirements (PPG clock as reference), API call sequence, configuration parameters (SpO2 calibration coefficients), quality metrics interpretation, error conditions, SpO2 specifics, PSP-S sleep processing, and memory requirements (78 KB ROM, 23 KB RAM).

### [ALPHA_APP_BUILD_CONFIG.md](./ALPHA_APP_BUILD_CONFIG.md)
**Application firmware configuration.** Thread map (7 threads from priority 3-9), VSM Kconfig settings, device tree sensor bindings (PAH8151 on I2C1 at 0x15, LSM6DSO on SPI0, MLX90614 on GPIO-I2C), memory layout (1 MB internal flash partitioning including PSP at 0xE0000), build system (west/sysbuild with MCUboot, PSP hex merge), IPC communication with nRF9151 comms coprocessor, and derived metrics (Estimated Core Temperature via Kalman filter, Adaptive Physiological Strain Index).

### [PIXART_PAH8151_VENDOR_DOCS.md](./PIXART_PAH8151_VENDOR_DOCS.md)
**PixArt vendor documentation synthesis.** Datasheet specifications, reference design guidance, SDK comparison (HRD_SPO2 V2.12 vs RAW V2.12), PXI algorithm library details (HRD V5653, SpO2 V703), LED/PD channel setup, noise mitigation (AEC convergence bounds, ambient light rejection, motion artifact handling), BLE data logger architecture, and detailed comparison of standalone SDK configuration vs. in-repo firmware customizations.

---

## How to Use These Documents

1. **Start with IMPROVEMENT_RECOMMENDATIONS.md** for the actionable summary. Items marked `[DONE]` have been implemented and validated.
2. **Check PPG_SPO2_TUNING_OPPORTUNITIES.md** for deferred SpO2/power optimizations to revisit during the power optimization or dark skin tone validation phases.
3. **Reference individual documents** for detailed evidence and technical context.
4. **Priority levels** indicate recommended order of work:
   - **P0 (Critical):** Fix immediately -- these directly impact HR/SpO2 accuracy. **(3 of 4 done)**
   - **P1 (High):** Fix in the next sprint -- significant quality improvements. **(4 of 8 done)**
   - **P2 (Medium):** Plan for upcoming work -- meaningful but not urgent. **(3 of 10 done)**
   - **P3 (Nice-to-have):** Backlog items for future consideration.

## Current Performance (2026-02-10)

| Metric | Value | Notes |
|--------|-------|-------|
| HR Quality | Q:4 sustained | Holds through 1.48g motion |
| SpO2 Quality | Q:4 at rest | Reaches Q:4 in ~19 seconds |
| SpO2 Reading | 99% | Consistent, realistic value |
| SpO2 During Motion | Q:0 | Expected per PSP docs |
| Time to HR Q:4 | ~12 seconds | From ACTIVE_MONITORING start |
