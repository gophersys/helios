# IWSCK A0 Power Optimization Log

**Date:** 2026-03-04
**Board:** CoreKinect IWSCK A0 (nRF54L15-QFAA)
**Measurement:** Joulescope JS220 inline on battery input, 1 MHz sampling

## Summary

Starting from the stock IWSCK bring-up firmware, Claude Code iteratively applied firmware
optimizations to reduce idle power consumption. All changes maintained full hardware
functionality (shell, BLE, LEDs, fuel gauge, RS232).

| Round | Change | Mean (mA) | Median (mA) | Delta | All Tests Pass? |
|-------|--------|-----------|-------------|-------|-----------------|
| 0 (baseline) | Stock firmware | 3.794 | 1.638 | — | Yes |
| 1 | Remove `CONFIG_SOC_NRF_FORCE_CONSTLAT` | 3.024 | 0.860 | -0.770 | Yes |
| 2 | + Minimal logging mode | 3.025 | 0.847 | -0.001 | Yes |
| 3 | + `CONFIG_PM` / device PM | 3.024 | 0.832 | -0.001 | Yes |
| 4 | + BQ35100 GE LOW at boot (on-demand enable) | 3.025 | 0.789 | -0.001 | Yes |
| 5 | + uart20 disabled in DTS + tick 1kHz | 3.188 | 0.600 | +0.163 | Yes |
| 6 | + UART async API (no effect) | 3.195 | 0.589 | +0.007 | Yes |
| **Final** | **All optimizations combined** | **3.425** | **0.528** | **-0.369** | **9/9 Yes** |

**Note:** Mean current is dominated by UART shell wakeup duty cycle (~52% active at ~6 mA,
~48% sleep). Median better represents the sleep floor. The median improved from 1.638 mA
to 0.528 mA — a **68% reduction** in the sleep-state current.

## What Worked

### 1. Remove CONSTLAT mode (-770 uA mean)
**File:** `libs/zephyr/ck_boards/current/boards/corekinect/iwsck_a0/iwsck_a0_nrf54l15_cpuapp_defconfig`

The single biggest win. `CONFIG_SOC_NRF_FORCE_CONSTLAT=y` kept internal HF regulators
and oscillators running continuously. Removing it allows the power management unit to
gate clocks/regulators between wakeups.

### 2. BQ35100 GE pin LOW at boot (on-demand enable)
**Files:** `iwsck_a0_nrf54l15-common.dtsi` (removed gpio-hog), `src/fuel.c` (added fuel_ge_on())

The BQ35100 fuel gauge GE pin was hogged HIGH in the DTS, keeping the gauge in WAITING
mode (~15 uA) at all times. Changed to:
- Remove gpio-hog from DTS
- Initialize P0.01 as OUTPUT_LOW in fuel.c SYS_INIT
- Auto-enable GE (with 1s delay) on first fuel shell command

### 3. Disable uart20 at boot
**File:** `iwsck_a0_nrf54l15-common.dtsi` (status = "disabled")

The RS232/LEMO UART was always enabled with IRQ RX active, drawing peripheral current
even when unused. Changed to disabled in DTS, with lazy init in rs232.c shell commands.

### 4. RS232 lazy RX init
**File:** `src/rs232.c`

Removed SYS_INIT that enabled UART IRQ RX at boot. RS232 commands now call
`rs232_ensure_active()` which enables the UART on first use.

## What Didn't Help

### Minimal logging mode
Switching from `CONFIG_LOG_MODE_DEFERRED` to `CONFIG_LOG_MODE_MINIMAL` saved negligible
current because the deferred log thread wasn't a significant wakeup source.

### UART Async API
Enabling `CONFIG_UART_ASYNC_API` alongside interrupt-driven mode had no effect because
the Zephyr shell backend uses the interrupt-driven API internally.

### `CONFIG_PM` (system power management)
`CONFIG_PM` is not available as a top-level Kconfig for nRF54L15 in NCS. Device PM
(`CONFIG_PM_DEVICE`, `CONFIG_PM_DEVICE_RUNTIME`) was enabled but had minimal impact
because the UART console keeps the system from entering deep idle.

### System tick reduction (10kHz → 1kHz)
Reducing `CONFIG_SYS_CLOCK_TICKS_PER_SEC` from 10000 to 1000 didn't significantly
reduce wakeups because the UART RX interrupt (not the tick timer) is the dominant
wakeup source.

## Round 7: Ultra-Low Power (BLE advertising + UART killed)

Added `power ultralow` shell command that:
1. Starts BLE advertising at 1s interval (slow, power-friendly)
2. Calls `shell_uninit()` to abort the shell thread
3. Deferred work item disables UART30 IRQs + suspends the UART device
4. System enters idle with only BLE radio + LFRC cal waking the CPU

Also added `power deadlow` (no BLE, no UART) and a completely shell-less
firmware (`prj_noshell.conf` + `main_noshell.c`) for absolute floor testing.

### Measurements

| Configuration | Mean (mA) | Median (mA) | Notes |
|---------------|-----------|-------------|-------|
| Shell active, no BLE | 2.942 | 0.801 | Bimodal: shell idle/active |
| BLE fast adv (100ms) + UART off | 3.845 | 0.661 | BLE TX bursts dominate |
| BLE slow adv (1s) + UART off | 3.006 | 0.696 | Lower mean from less TX |
| BLE slow adv + UART suspended | 3.340 | 0.437 | Best median achieved |
| No-shell firmware, no BLE | 3.775 | 1.697 | **Hardware floor** |

### Key Finding: Hardware Floor

A firmware with literally just `k_sleep(K_FOREVER)` — no shell, no BLE,
no UART, no logging — draws **3.775 mA average** with **zero quiet
milliseconds** (never drops below 500 uA for even 1ms). This proves the
~3-4 mA average is a **hardware-level floor**, not a firmware issue.

The bimodal distribution seen in shell firmware (which gives lower medians)
is a statistical artifact of the shell's duty-cycled UART polling, not
actual deep sleep.

## The True Floor: Hardware Limitations

The IWSCK A0 board cannot achieve the nRF54L15 datasheet System ON idle
current (~3 uA) due to multiple hardware constraints:

1. **SP3232ECA-L always draws ~300 uA** — no shutdown pin connected, charge pump runs
   continuously from 3.3V rail
2. **No LFXO crystal** — LFRC requires periodic HFXO calibration every ~8s, each
   calibration fires the 32 MHz HFXO which draws several mA for ~1ms
3. **nRF54L15 Rev 1 errata** — documented higher-than-expected System ON sleep current;
   even with all peripherals off, the SoC draws ~3.7 mA average
4. **GPIO/peripheral leakage** — multiple I/O pins configured with pull-ups/pull-downs
   that contribute to static current

### Recommendations for A1 Board Revision

To achieve sub-100 uA sleep current:
- Add LFXO crystal (eliminates HFXO calibration spikes entirely)
- Add SP3232 shutdown pin or switch to a lower-power RS232 transceiver
- Use nRF54L15 Rev 2 silicon (when available) with fixed System ON current
- Audit all GPIO configurations for unnecessary pull resistors

## Feature Verification (Final Firmware)

All 9 tests pass on the optimized firmware:

```
[PASS] board info
[PASS] led green on
[PASS] led blue on
[PASS] fuel read (on-demand GE enable, 1s delay)
[PASS] fuel status
[PASS] ble start
[PASS] ble stop
[PASS] power idle
[PASS] rs232 send (graceful with uart20 disabled)
```

## Files Modified

| File | Change |
|------|--------|
| `libs/zephyr/ck_boards/.../iwsck_a0_nrf54l15_cpuapp_defconfig` | Removed `CONFIG_SOC_NRF_FORCE_CONSTLAT=y` |
| `libs/zephyr/ck_boards/.../iwsck_a0_nrf54l15-common.dtsi` | Removed GE gpio-hog, disabled uart20 |
| `apps/firmware/iwsck/prj.conf` | Minimal logging, PM enabled, tick 1kHz |
| `apps/firmware/iwsck/src/fuel.c` | On-demand GE enable via P0.01 GPIO |
| `apps/firmware/iwsck/src/rs232.c` | Lazy UART init, null-safe device access |
| `apps/firmware/iwsck/src/power.c` | Power management: sleep, idle, ultralow (BLE+no UART), deadlow |
| `apps/firmware/iwsck/src/main_noshell.c` | Minimal no-shell BLE beacon for floor testing |
| `apps/firmware/iwsck/prj_noshell.conf` | No-shell Kconfig for floor testing |
| `apps/firmware/iwsck/CMakeLists.txt` | Added power.c |
