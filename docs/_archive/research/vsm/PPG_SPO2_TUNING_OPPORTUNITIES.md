# PPG & SpO2 Tuning Opportunities

**Date:** 2026-02-10
**Status:** Deferred (SpO2 Q:4 achieved with current settings)
**Platform:** Alpha B0 Wearable (nRF52840 + PAH8151 PPG + LSM6DSO IMU + Philips PSP)

This document catalogs known tuning opportunities for the PAH8151 PPG sensor and PSP SpO2 pipeline. These are **not critical** — SpO2 is currently achieving Q:4 at 99% during still periods — but represent potential improvements for signal robustness, power efficiency, darker skin tones, or edge-case scenarios.

---

## Current Baseline Performance (2026-02-10)

| Metric | Value | Notes |
|--------|-------|-------|
| HR Quality | Q:4 sustained | Holds through 1.48g motion |
| SpO2 Quality | Q:4 at rest | Reaches Q:4 in ~28 seconds |
| SpO2 Reading | 99% | Consistent, realistic value |
| SpO2 During Motion | Q:0 | Expected per PSP docs (requires stillness) |
| Time to HR Q:4 | ~17 seconds | From ACTIVE_MONITORING start |
| Time to SpO2 Q:4 | ~28 seconds | From ACTIVE_MONITORING start |

---

## 1. Increase Red/IR Exposure Time Maximums

### Current Configuration

From `pah_815x_reg_default.h` (Config 5, PAH_815X_REG_INIT array):

| Channel | Register Pair | Raw Value | Exposure Max | LED Current Max |
|---------|--------------|-----------|-------------|-----------------|
| Green (A) | 0x48-0x49 | 0x0BB8 | 3000T = **750 µs** | 25.2 mA (DAC 63) |
| Red (B) | 0x53-0x54 | 0x0100 | 256T = **64 µs** | 50.8 mA (DAC 127) |
| IR (C) | 0x5E-0x5F | 0x0040 | 64T = **16 µs** | 50.8 mA (DAC 127) |

### Observation

Red has **11.7x shorter** exposure than Green. IR has **46.9x shorter** exposure than Green. This is by design — Red and IR penetrate deeper into tissue and use higher current to compensate — but the extremely short IR exposure (16 µs) gives the AEC very little room to boost signal amplitude.

### Proposed Change

Double Red exposure, quadruple IR exposure:

```c
// Red (Channel B): 256T → 512T = 128 µs
{0x53, 0x00},  // ExpoTime_max_b low byte
{0x54, 0x02},  // ExpoTime_max_b high byte (was 0x01)

// IR (Channel C): 64T → 256T = 64 µs
{0x5E, 0x00},  // ExpoTime_max_c low byte (was 0x40)
{0x5F, 0x01},  // ExpoTime_max_c high byte (was 0x00)
```

### Expected Impact

- AEC has 2-4x more headroom to boost Red/IR signal amplitude
- Particularly beneficial on darker skin tones where optical absorption is higher
- Faster SpO2 Q convergence (stronger signals during calibration window)
- Slight increase in frame time (negligible at 32 Hz)
- **No impact on Green/HR performance**

### When to Implement

If SpO2 quality degrades on darker skin tones, or if the 28-second convergence time needs to be shortened.

---

## 2. Adjust AEC Convergence Bounds for Red/IR

### Current Configuration

The Auto-Exposure Control targets an ADC average between 2044-2556 (~30-40% of the 12-bit range) for all channels:

```
Bank 0, Channel B (Red):
  avg_hibu_b = 2812  (0x0AFC)  — upper outer bound
  avg_lobu_b = 1788  (0x06FC)  — lower outer bound
  avg_hi_b   = 2556  (0x09FC)  — upper inner bound (fine-tune target)
  avg_lo_b   = 2044  (0x07FC)  — lower inner bound (fine-tune target)

Bank 0, Channel C (IR):
  avg_hibu_c = 2812  — same bounds as Red
  avg_lobu_c = 1788
  avg_hi_c   = 2556
  avg_lo_c   = 2044
```

### Observation

These bounds are conservative. If the Red/IR ADC averages are consistently at the low end of this range (or below `avg_lobu`), the AEC will push DAC and exposure to maximum and oscillate. Raising the target gives the AEC a higher "comfort zone" resulting in stronger signals with better SNR.

### Proposed Change

Raise the Red/IR AEC target range to 50-70% of ADC range:

```c
// Channel B (Red) — registers in Bank 0
avg_hibu_b → 3500 (0x0DAC)   // was 2812
avg_lobu_b → 2500 (0x09C4)   // was 1788
avg_hi_b   → 3000 (0x0BB8)   // was 2556
avg_lo_b   → 2700 (0x0A8C)   // was 2044

// Channel C (IR) — same adjustments
avg_hibu_c → 3500
avg_lobu_c → 2500
avg_hi_c   → 3000
avg_lo_c   → 2700
```

### Expected Impact

- Red/IR ADC levels converge to a higher, more stable range
- Reduced AEC oscillation near the bounds
- Better SNR for SpO2 ratio calculation
- May slightly increase LED power consumption (higher target = brighter LEDs)

### When to Implement

If diagnostics show Red/IR DAC values consistently at maximum (127) while ADC averages remain low, indicating the AEC is struggling to reach its target.

---

## 3. Reduce Green LED Current for Power Savings

### Current Configuration

Green channel DAC max is 0x3F (63) = 25.2 mA. HR quality is excellent (Q:4 sustained through 1.48g motion).

### Observation

If the Green AEC is NOT consistently maxing out the DAC (i.e., the AEC settles at DAC < 50), the maximum can be safely reduced. Every mA of LED current saved directly extends battery life.

### Proposed Change

Reduce Green DAC max from 63 to 48:

```c
// In pah_815x_reg_default.h, Config 5:
{0x4B, 0x30},  // DAC_Max_a: was 0x3F (63), now 0x30 (48) = 19.2 mA
```

### Expected Impact

- Saves ~6 mA average LED current during monitoring
- At 3.7V nominal battery: ~22 mW savings
- HR quality should remain Q:4 (Green signal was over-provisioned)

### Validation Required

Before deploying, log the Green DAC value during a monitoring session:
- If Green DAC typically settles at 30-45, reducing max to 48 is safe
- If Green DAC hits 63 on darker skin tones, keep the current max
- Test across at least 3 skin tones (Fitzpatrick I/II, III/IV, V/VI)

### When to Implement

During power optimization phase. Must be validated across skin tones first.

---

## 4. SpO2 Calibration Coefficients

### Background

The PSP library uses a quadratic calibration model for SpO2:

```
SpO2 = a × R² + b × R + c
where R = Red_AC/Red_DC ÷ IR_AC/IR_DC  (ratio of ratios)
```

The coefficients `{a, b, c}` (scaled by 100) are device-specific — they depend on:
- LED wavelengths (Red: 660 nm, IR: 880 nm for PAH8151)
- Optical geometry (LED-to-PD spacing, packaging)
- Light guide / window material
- Sensor-to-skin coupling characteristics

### Current Status

**Unknown.** The current `calCoefSpO2[3]` values in the PSP initialization need to be verified. If they are the PSP defaults (not calibrated for Alpha B0 hardware), SpO2 readings may have a systematic offset.

### What Needs to Happen

Per PSP Library Requirements Section 11.4, a proper wellness-domain calibration requires:
1. **20+ subjects** (minimum 15% with dark skin, Fitzpatrick V/VI)
2. **Reference device**: FDA-cleared pulse oximeter (e.g., Masimo Rad-97)
3. **Protocol**: Subjects breathe varying O2 concentrations to produce SpO2 range 70-100%
4. **Analysis**: Least-squares fit of `{a, b, c}` coefficients to minimize RMSE vs reference
5. **Validation**: Independent dataset confirms RMSE < 3% (wellness threshold)

### Impact of Incorrect Coefficients

- SpO2 **readings will still appear** (quality can be Q:4)
- SpO2 **absolute values may be offset** (e.g., reading 99% when actual is 96%)
- The offset is systematic and consistent, not random

### Current Reading Assessment

SpO2 reading of 99% at Q:4 is within the physiologically normal range (95-100%) for a healthy individual at rest. Whether it's accurate to ±2% requires reference validation.

### When to Implement

Before any medical or wellness claims are made about SpO2 accuracy. For development and testing purposes, the current uncalibrated values are sufficient.

---

## 5. DTS LED Current Properties Not Used by Driver

### Observation

The Alpha B0 device tree overlay specifies LED current properties:

```dts
pah8151: pah8151@15 {
    compatible = "pixart,pah8151";
    reg = <0x15>;
    irq-gpios = <&gpio0 20 GPIO_ACTIVE_HIGH>;
    led-current-ir = <255>;
    led-current-red = <255>;
    led-current-green = <255>;
};
```

**These values are defined in the DTS binding but never parsed by the driver.** The PAH8151 driver uses the static register arrays in `pah_815x_reg_default.h` exclusively.

### Recommendation

Either:
- **(a)** Wire up the DTS properties to override the register defaults at init time — makes configuration more flexible without recompiling the vendor SDK
- **(b)** Remove the DTS properties to avoid confusion — they currently have no effect

Option (a) is the better long-term approach but requires modifying the vendor SDK init path to accept runtime configuration.

### When to Implement

Low priority. Only matters if per-board LED current tuning is needed (e.g., different optical windows on different hardware revisions).

---

## 6. AEC Step Size Tuning

### Current Configuration

```
Green (A):  ExposureLineNormStep = 8,  LED_DAC_step = 2
Red (B):    ExposureLineNormStep = 4,  LED_DAC_step = 2
IR (C):     ExposureLineNormStep = 4,  LED_DAC_step = 2
```

### Observation

The step sizes control how aggressively the AEC adjusts to reach its target:
- Larger steps = faster convergence but more oscillation
- Smaller steps = slower convergence but more stable

Green has 2x the exposure step of Red/IR. If Red/IR convergence is too slow (visible as wandering signal during the first few seconds), increasing their exposure step could help.

### Proposed Change (if needed)

```c
// Increase Red/IR exposure step from 4 to 8:
{0x22, 0x08},  // Cmd_ExposureLineNormStep_b (Red): was 0x04
{0x3C, 0x08},  // Cmd_ExposureLineNormStep_c (IR): was 0x04
```

### When to Implement

Only if diagnostics show Red/IR AEC taking more than 2-3 seconds to converge. Not a problem currently.

---

## 7. Motion-Aware PPG Mode Switching

### Concept

Since SpO2 requires stillness (Q drops to 0 during motion), the Red and IR LEDs are wasting power during motion periods. A motion-aware mode switch could:

1. **During motion**: Switch to Config 1 (Green only, 32 Hz) — saves ~2/3 LED power
2. **During stillness**: Switch to Config 5 (all channels, 32 Hz) — enables SpO2

### Implementation Complexity

- Requires the motion detection state machine to communicate with the VSM driver
- Config switch involves a `pah8151_set_operating_mode()` call
- AEC needs 2-3 seconds to reconverge on Red/IR after switching back to Config 5
- PSP may need to be notified that SpO2 inputs are temporarily unavailable

### When to Implement

During power optimization phase. The savings are significant (potentially 20-30 mA during motion) but the implementation is non-trivial and risks introducing SpO2 convergence delays.

---

## Summary: Priority Order for Future Work

| # | Opportunity | Impact | Effort | When |
|---|-----------|--------|--------|------|
| 1 | SpO2 calibration coefficients | Accuracy | High (study) | Before wellness claims |
| 2 | Increase Red/IR exposure times | Robustness on dark skin | Low | If SpO2 fails on dark skin |
| 3 | Adjust AEC bounds for Red/IR | Faster convergence | Low | If AEC is struggling |
| 4 | Reduce Green LED current | Power savings | Low | Power optimization phase |
| 5 | Motion-aware PPG mode switching | Power savings | Medium | Power optimization phase |
| 6 | Wire up DTS LED properties | Flexibility | Medium | Multi-revision support |
| 7 | AEC step size tuning | Convergence speed | Low | If AEC is slow |

---

## Appendix: PAH8151 Hardware Capabilities Reference

| Parameter | Min | Max | Current Setting |
|-----------|-----|-----|-----------------|
| LED peak sink current (per LED) | 0 mA | 100 mA | Green: 25.2 mA, Red/IR: 50.8 mA |
| DAC resolution | 0 | 255 | Green: max 63, Red/IR: max 127 |
| Exposure time | 0 | 3000T (750 µs) | Green: 750 µs, Red: 64 µs, IR: 16 µs |
| PPG sampling rate | ~1 Hz | 1000 Hz | 32 Hz (Config 5) |
| FIFO depth | - | 488 samples | Watermark: 32 |
| ADC resolution | - | 20-bit | Mapped to 32-bit in driver |
| Channels | 1 | 4 (A/B/C/D) | 3 (Green/Red/IR) |
| AEC convergence bounds | 0 | 4095 | Target: 2044-2556 (all channels) |
| Touch detection | IR only | IR + Capacitive | IR only (cap disabled) |
