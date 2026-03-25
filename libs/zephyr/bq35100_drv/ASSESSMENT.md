# BQ35100 Chip Assessment

**Date:** 2026-03-20
**Evaluator:** CoreKinect Firmware Team
**Hardware:** IWSCK A0 + BQ35100 (0x55) on bit-bang I2C
**Firmware:** NCS v3.2.1 / Zephyr 4.2.99

## Executive Summary

The BQ35100 is a **strong fit** for primary (non-rechargeable) battery applications with
predictable discharge profiles. Its ultra-low shutdown current (50 nA) and host-controlled
power make it ideal for intermittent-duty IoT devices. The chip is **not suitable** for
rechargeable battery applications — use BQ27xx series for that.

**Verdict: RECOMMENDED** for primary battery products where end-of-service detection and
accurate capacity tracking are required.

## Test Results from Hardware Evaluation

| Test | Result | Notes |
|------|--------|-------|
| I2C communication @ 0x55 | PASS | Bit-bang I2C on nRF54L15 works reliably |
| Voltage measurement | PASS | 3.94V reading, 0 mV spread over 5 reads (excellent stability) |
| Current measurement | PASS | -3 mA to 0 mA range confirmed, signed correctly |
| Internal temperature | PASS | 27.65°C (room temp, accurate) |
| External temperature | N/A | No NTC on IWSCK A0, reads -39°C (expected) |
| Design capacity | PASS | 2200 mAh factory default confirmed |
| GAUGE_START/STOP | PASS | GA bit sets, G_DONE fires after stop |
| GE pin control | PASS | Enable/disable cycle works, I2C resumes after re-enable |
| ALERT interrupt | PASS | INT fires on INITCOMP, clears on BatteryAlert read |
| Data flash read | PASS | Device name "bq35100", OpCfgA=0x80 confirmed |
| Data flash write | Not tested | Requires unseal (risk of bricking with wrong writes) |
| Seal/Unseal | Partial | Device reports FULL_ACCESS already — default keys may work |
| SOH reading | PASS | Returns 0% in ACC mode (expected — SOH needs SOH/EOS mode + chemistry) |
| Impedance | N/A | Returns 0 in ACC mode (requires EOS mode + load pulse) |

## Feature Evaluation

### Strengths

1. **Ultra-low quiescent current (50 nA)**
   The GE pin control is exceptional. When GE=LOW, the chip draws 50 nA — negligible
   for any battery application. Most competitors require 1-10 µA in sleep.

2. **Primary battery specialization**
   The only TI fuel gauge designed for non-rechargeable cells. Li-SOCl2 impedance
   tracking (EOS mode) is unique — no other gauge does this without forced discharge.

3. **No forced discharge required**
   SOH and EOS modes estimate remaining capacity from voltage or impedance measurements
   alone. Critical for high-value primary cells where you can't waste capacity.

4. **Host-controlled lifecycle**
   The GE pin + GAUGE_START/STOP model gives the host full control over when the
   gauge is active. Perfect for duty-cycled IoT devices that wake periodically.

5. **I2C simplicity**
   Standard I2C at 0x55, simple register interface. Works with bit-bang I2C on
   constrained platforms (verified on nRF54L15 GPIO I2C).

6. **Data flash configurability**
   1 KB of on-chip flash for calibration, chemistry parameters, and alert thresholds.
   Can be factory-programmed via I2C without external tools.

7. **ALERT interrupt**
   Configurable for battery low, temperature, SOH low, EOS detection, and gauge done.
   Single open-drain output covers all alert conditions.

### Weaknesses

1. **Not for rechargeable batteries**
   No charge detection, no coulomb counter with charge integration, no charge
   termination. BQ27xx series is the rechargeable counterpart.

2. **Temperature sensor requires external NTC**
   Default OpCfgA has TEMPS=1 (external NTC). Without an NTC connected, the
   temperature register reads garbage (-39°C in our test). The internal die
   temp (0x28) works but measures the IC, not the battery.

3. **Control subcommand timing**
   The DEVICE_TYPE subcommand response via Control() register is unreliable on
   some firmware revisions (returns CONTROL_STATUS instead). Workaround: use
   MAC-based reads. This is a documentation vs silicon mismatch.

4. **Data flash write risk**
   Writing wrong values to calibration or chemistry flash can make the gauge
   report incorrect data. No factory-reset mechanism other than reflash via
   TI's EV2400 tool. 20,000 write cycle limit.

5. **No on-chip battery switch**
   The BQ35100 monitors only — it cannot disconnect the battery. For battery
   disconnect/ship mode, a separate MOSFET + protection IC is needed.

6. **EOS mode complexity**
   End-of-Service mode requires a specific load pulse pattern (GAUGE_START 1s before
   pulse, GAUGE_STOP immediately after). Timing-sensitive and needs careful
   integration with the application's power profile.

7. **Limited current range**
   The sense resistor input range is ±125 mV. With a typical 10 mΩ resistor,
   max measurable current is ±12.5 A. For micro-power applications (<1 mA),
   a larger sense resistor (100 mΩ) is needed but limits max current to ±1.25 A.

### Neutral

- **SHA-1/HMAC authentication**: Available for counterfeit battery detection.
  Useful for medical/industrial but overkill for consumer IoT.
- **Lifetime data logging**: Records min/max voltage, current, temperature.
  Useful for post-mortem analysis but requires LT_ENABLE and uses flash writes.
- **Chemistry profiles**: TI provides profiles for common Li-SOCl2 and Li-MnO2
  cells via CHEM_ID. Custom chemistries require TI's BQSTUDIO tool.

## Software Assessment

### Driver Completeness

| Feature Category | Coverage | Notes |
|------------------|----------|-------|
| Register reads (voltage, current, temp, etc.) | 100% | All 15 readable registers |
| Control subcommands | 100% | All 17 subcommands via control_cmd() or dedicated APIs |
| Data flash access | 100% | Read + write with checksum verification |
| Gauge lifecycle | 100% | Enable/disable, start/stop, G_DONE wait |
| Security | 100% | Seal/unseal with default keys |
| Alert interrupt | 100% | GPIO trigger + workqueue handler |
| Sensor API | 100% | sample_fetch, channel_get, attr_set, trigger_set |
| Shell commands | 100% | 9 commands covering all interactive operations |
| Calibration | Partial | Registers exposed but no high-level calibration API |
| SHA-1 auth | Not impl | Use control_cmd() for raw subcommand access |

### Zephyr Integration Quality

- Standard `DEVICE_DT_INST_DEFINE` instantiation from devicetree
- Follows CK driver module pattern (pah8151_drv, lsm6dso_drv style)
- DTS binding with typed properties and validation
- Kconfig with log level, trigger, shell options
- 23 hardware-on-target tests (all passing)
- 93 KB flash, 25 KB RAM (sample with shell)
- 70 KB flash, 18 KB RAM (tests only)

### Comparison with Alternatives

| Feature | BQ35100 | MAX17048 | LTC2959 | SBS Gauge |
|---------|---------|----------|---------|-----------|
| Target | Primary | Li-Ion | Coulomb | Rechargeable |
| Shutdown | 50 nA | 2 µA | 100 nA | Varies |
| SOH | Yes | No | No | Yes |
| EOS | Yes (Li-SOCl2) | No | No | No |
| Impedance | Yes | No | No | Some |
| Coulomb count | Yes (ACC) | No (ModelGauge) | Yes | Yes |
| NTC support | Yes | No | No | Varies |
| Price (1K) | ~$1.50 | ~$0.80 | ~$2.00 | Varies |

## Recommendations

### Use BQ35100 when:
- Product uses primary (non-rechargeable) batteries
- End-of-service detection is a product requirement
- Ultra-low quiescent current matters (battery-powered IoT with multi-year life)
- Host can control gauge power (periodic wake model)

### Do NOT use BQ35100 when:
- Product uses rechargeable batteries (use BQ27xx)
- Continuous monitoring is required (BQ35100 is designed for periodic wake)
- Cost is critical and you only need voltage monitoring (use a simple ADC)
- Product needs battery disconnect/protection (add external circuit)

### Integration Notes for IWSCK

1. **Add NTC thermistor** or change OpCfgA.TEMPS=0 to use internal temp sensor.
   Without NTC, external temperature reads are meaningless.
2. **Move to hardware I2C** (A1 board) for better performance and lower CPU overhead.
   Bit-bang works but ties up the CPU during transactions.
3. **Consider EOS mode** for Li-SOCl2 cells — this is the BQ35100's unique capability.
   Requires defining a load pulse profile matching the product's typical power draw.
4. **Factory calibration**: Use BQStudio or the shell `df_read`/`unseal`/`df_write` commands
   to calibrate voltage offset and CC gain for the specific PCB layout.
