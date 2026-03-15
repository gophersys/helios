# IWSCK A0 Power Study

**Date:** 2026-03-04
**Board:** CoreKinect IWSCK A0 (nRF54L15-QFAA)
**Measurement:** Joulescope JS220 inline on battery input, 1 MHz sampling
**Performed by:** Mateo Segura

---

## 1. Hardware Setup

```
Battery → TPS63802 (buck-boost) → +3.3V rail
                                    ├── nRF54L15 (MCU + BLE radio)
                                    ├── SP3232ECA-L (RS232 level shifter)
                                    ├── BQ35100 (fuel gauge, also from VBAT)
                                    └── EAST1616RGBB2 (RGB LED, 698 ohm series)
```

| Device | Identifier | Role |
|--------|-----------|------|
| Joulescope JS220 | Serial 001998 | Inline battery current (1 MHz) |
| J-Link PLUS | SNR 821009546 | SWD debug/flash |
| FTDI UART | /dev/ttyUSB1 | Console (uart30 @ 115200) |

One gotcha: nrfjprog doesn't know about nRF54L, and JLinkExe can connect as
CORTEX-M33 but can't write RRAM. The only thing that works for flashing is
`nrfutil device program --family nrf54l`.

```bash
west build --pristine --no-sysbuild -b iwsck_a0/nrf54l15/cpuapp .
nrfutil device program --firmware build/zephyr/zephyr.hex \
  --serial-number 821009546 --family nrf54l --core application \
  --options chip_erase_mode=ERASE_ALL,reset=RESET_SYSTEM,verify=VERIFY_READ
```

```python
import joulescope, numpy as np
js = joulescope.scan_require_one()
js.open()
data = js.read(contiguous_duration=20.0)  # (samples, 2): [current_A, voltage_V]
current_ua = data[:, 0] * 1e6
js.close()
```

---

## 2. Baseline Measurements

Stock firmware, nothing special going on — just the shell sitting at idle.

| Mode | Mean (uA) | P5 (uA) | P95 (uA) | Notes |
|------|-----------|---------|----------|-------|
| Idle (shell, no BLE, LEDs off) | 3794 | 180 | 14040 | Baseline |
| LED Green on | 4634 | 420 | 14873 | +840 uA |
| LED Blue on | 4592 | 407 | 14823 | +798 uA |
| LED Red on | 3795 | 180 | 14043 | +0 uA — red LED is dead (A0 errata) |
| All LEDs on | 5436 | 727 | 15882 | +1642 uA |
| BLE advertising (100ms) | 3356 | 41 | 13993 | BLE init takes ~60s (RC32K cal) |

Looking at the 1 MHz capture, the idle state is not quiet at all. The shell's UART RX
polling causes ~17,000 wakeups/sec with ~35 us active bursts at 5 mA. 60% of the time
the CPU is active, 40% it's between polls at ~190 uA.

### Datasheet expectations

For reference, here's what the datasheets say each part should draw:

| Component | Mode | Expected (uA) |
|-----------|------|---------------|
| nRF54L15 | System ON idle (datasheet best case) | 3 |
| nRF54L15 | CONSTLAT + 2x UART + GRTC (realistic) | 600 - 1300 |
| TPS63802 | Quiescent (PFM) | 11 |
| BQ35100 | GE=HIGH, WAITING | 15 |
| BQ35100 | GE=LOW | 0.05 |
| SP3232ECA-L | Charge pump running | 300 |
| SP3232ECA-L | Shutdown | <1 |

So naively you'd expect maybe 1-2 mA at the battery. We're at 3.8 mA. Something is off.

---

## 3. Firmware Optimization (7 Rounds)

Went through these one at a time, measuring after each change. All 9 hardware tests
kept passing throughout.

| Round | Change | Mean (mA) | Median (mA) | Delta |
|-------|--------|-----------|-------------|-------|
| 0 | Stock firmware | 3.794 | 1.638 | -- |
| 1 | Remove `CONFIG_SOC_NRF_FORCE_CONSTLAT` | 3.024 | 0.860 | -0.770 |
| 2 | + Minimal logging mode | 3.025 | 0.847 | -0.001 |
| 3 | + `CONFIG_PM_DEVICE` / device PM | 3.024 | 0.832 | -0.001 |
| 4 | + BQ35100 GE LOW at boot | 3.025 | 0.789 | -0.001 |
| 5 | + uart20 disabled + tick 1kHz | 3.188 | 0.600 | +0.163 |
| 6 | + UART async API (no effect) | 3.195 | 0.589 | +0.007 |
| **Final** | **All optimizations** | **3.425** | **0.528** | -- |
| 7a | BLE slow adv (1s) + UART off | 3.006 | 0.696 | -- |
| 7b | BLE slow adv + UART suspended | 3.340 | 0.437 | -- |
| 7c | No-shell firmware (k_sleep only) | 3.775 | 1.697 | -- |

Median went from 1.638 to 0.528 mA — 68% drop in the sleep-state current.

### What actually moved the needle

**CONSTLAT removal (-770 uA).** By far the biggest win. The board defconfig had
`CONFIG_SOC_NRF_FORCE_CONSTLAT=y`, which pins the HF regulators on all the time. One
line change, instant 770 uA off the mean.

**BQ35100 GE pin LOW at boot.** The fuel gauge was hogged HIGH in the DTS, burning
15 uA for no reason. Ripped out the gpio-hog, added a SYS_INIT that drives P0.01 LOW,
and the fuel shell commands now auto-enable GE on first use (with a 1s settling delay).

**Disable uart20 + lazy RS232 init.** The RS232 UART was running with IRQ RX enabled
at all times. Set it to `status = "disabled"` in the DTS and added `rs232_ensure_active()`
so the UART only spins up when you actually run an RS232 command.

### What didn't matter

- **Minimal logging** — the deferred log thread wasn't waking the system enough to care
- **UART Async API** — doesn't help because the shell backend uses IRQ-driven internally
- **`CONFIG_PM`** — flat out not available for nRF54L15 in NCS
- **Tick reduction (10kHz to 1kHz)** — UART RX interrupts dominate, not the tick

---

## 4. Ultra-Low Power Modes

To see how low we could actually go, added two shell commands that kill the UART and
put the board into headless mode (power cycle to get the shell back).

### `power ultralow` — BLE beacon, no UART

Starts BLE advertising at 1s interval, calls `shell_uninit()` so the shell thread aborts,
then a deferred work item kills UART30.

| BLE Adv Interval | Mean (mA) | Median (mA) |
|-----------------|-----------|-------------|
| Fast (100ms) + UART off | 3.845 | 0.661 |
| Slow (1s) + UART off | 3.006 | 0.696 |
| Slow (1s) + UART suspended | 3.340 | 0.437 |

### `power deadlow` — nothing running, no BLE

Same idea but skips BLE. Just shell_uninit + UART off.

### No-shell firmware — the real floor

Built a stripped-down firmware that does literally nothing: `main()` calls
`k_sleep(K_FOREVER)`. No shell, no BLE, no UART, no logging. 32 KB flash.

**Result: 3.775 mA with zero quiet milliseconds.**

The board never drops below 500 uA for even 1 ms. This is the hardware floor.

---

## 5. What We Learned

### The median was misleading

The shell firmware's median of 0.528 mA looked great, but it's a statistical artifact.
The current has a bimodal distribution — ~52% of the time the shell's UART polling is
active at 5-6 mA, ~48% of the time it's between polls at ~0.5 mA. That's not deep
sleep, it's just the gaps between polling bursts.

The no-shell firmware proved it. Without the bimodal pattern, you get a flat 3.7 mA
with no dips at all.

### The board can't go below ~3.7 mA

Three things we can't fix in firmware:

| Problem | Current | Fix |
|---------|---------|-----|
| SP3232 charge pump always on (no SHDN pin) | ~300 uA | A1: add shutdown control |
| No LFXO — HFXO fires every ~8s for LFRC cal | ~mA spikes | A1: add 32.768 kHz crystal |
| nRF54L15 Rev 1 silicon errata | bulk of the floor | Rev 2 silicon |

### What firmware can vs can't do

| Target | Firmware? | Result |
|--------|-----------|--------|
| CONSTLAT removal | Yes | -770 uA |
| Disable unused peripherals | Yes | -50-100 uA |
| BQ35100 on-demand | Yes | -15 uA |
| SP3232 charge pump | No | Need SHDN pin |
| LFRC calibration | No | Need LFXO |
| Silicon errata | No | Need Rev 2 |

---

## 6. A1 Board Changes Needed

To get anywhere near the datasheet's 3 uA System ON idle:

1. **32.768 kHz LFXO crystal** — kills the HFXO calibration spikes entirely
2. **SP3232 shutdown control** — GPIO-switched load switch or route the SHDN pin,
   saves 300 uA when RS232 isn't needed
3. **nRF54L15 Rev 2** — whenever Nordic ships it, the System ON errata should be fixed
4. **GPIO audit** — check every pin for unnecessary pull resistors bleeding current
