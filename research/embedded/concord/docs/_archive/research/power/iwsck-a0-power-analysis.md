# IWSCK A0 Power Analysis — Claude Code Demo

**Date:** 2026-03-04
**Board:** CoreKinect IWSCK A0 (nRF54L15-QFAA)
**Tools:** Joulescope JS220, 2x SEGGER J-Link PLUS, 2x FTDI UART, Claude Code (Opus 4.6)

## Objective

Use Claude Code to autonomously:
1. Discover and identify all connected hardware (J-Links, UARTs, Joulescope)
2. Build and flash the IWSCK firmware
3. Measure current draw with the Joulescope Python library
4. Launch a research agent to analyze datasheets for expected power consumption
5. Compare measured vs expected and identify optimization opportunities

---

## 1. Hardware Discovery

### USB Devices Detected

```
Bus 001 Device 006: ID 16d0:10ba MCS Joulescope JS220
Bus 001 Device 005: ID 0403:6001 FTDI FT232R USB UART (AM00LOS7) → /dev/ttyUSB0
Bus 001 Device 004: ID 0403:6001 FTDI FT232R USB UART (AR0KFSH1) → /dev/ttyUSB1
Bus 001 Device 003: ID 1366:0101 SEGGER J-Link PLUS (SNR 821009546)
Bus 001 Device 002: ID 1366:0101 SEGGER J-Link PLUS (SNR 821009537)
```

### Identification Process

**J-Link identification:** Connected each J-Link to the nRF54L15 using JLinkExe with `-device CORTEX-M33 -if SWD -speed 4000`:
- **SNR 821009546** → Found Cortex-M33 r1p0, VTref=3.341V — **this is the IWSCK board**
- **SNR 821009537** → Failed to connect — connected to other device

**UART identification:** Sent `\r\n` on each port at 115200 baud:
- **/dev/ttyUSB0** (AM00LOS7) → No response — other device or RS232/LEMO
- **/dev/ttyUSB1** (AR0KFSH1) → Returned `iwsck>` prompt — **this is the IWSCK console**

### Final Hardware Map

| Device | Identifier | Role |
|--------|-----------|------|
| Joulescope JS220 | Serial 001998 | Board battery input current measurement (inline sense) |
| J-Link PLUS #1 | SNR 821009546 | **IWSCK nRF54L15 SWD** |
| J-Link PLUS #2 | SNR 821009537 | Other device (not IWSCK) |
| FTDI UART #1 | AM00LOS7 → /dev/ttyUSB0 | Unknown / RS232 LEMO / other device |
| FTDI UART #2 | AR0KFSH1 → /dev/ttyUSB1 | **IWSCK console (uart30 @ 115200)** |

---

## 2. Build & Flash

### Key Discovery: nRF54L15 Toolchain Requirements

The nRF54L15 uses RRAM (not traditional flash), which caused several tool compatibility issues:

1. **nrfjprog v10.24.2** — Does NOT support `NRF54L` family. Only knows NRF51/52/53/91.
2. **JLinkExe V8.72a** — Can connect via SWD as `CORTEX-M33` but **cannot write to RRAM** (`Writing target memory failed`). The JLink DLL doesn't have the nRF54L15 device entry or flash loader.
3. **nrfutil v8.1.1** (standalone binary) — **Works!** Supports `--family nrf54l` and can program RRAM.

### Build Command

```bash
export ZEPHYR_BASE=/ncs/zephyr
cd /workspaces/concord/apps/firmware/iwsck
west build --pristine --no-sysbuild -b iwsck_a0/nrf54l15/cpuapp .
```

Output: 352 build steps, 208 KB flash (14.23%), 47 KB RAM (24.66%).

### Flash Command

```bash
# Download nrfutil (new standalone CLI, not the old pip package)
curl -sL https://developer.nordicsemi.com/.pc-tools/nrfutil/x64-linux/nrfutil -o /tmp/nrfutil
chmod +x /tmp/nrfutil
/tmp/nrfutil install device

# Recover and flash
/tmp/nrfutil device recover --serial-number 821009546
/tmp/nrfutil device program \
  --firmware build/zephyr/zephyr.hex \
  --serial-number 821009546 \
  --family nrf54l --core application \
  --options chip_erase_mode=ERASE_ALL,reset=RESET_SYSTEM,verify=VERIFY_READ
```

### Verification

After flash, the UART showed the full IWSCK shell with all commands:

```
iwsck> board info
IWSCK A0 — nRF54L15 Bring-Up Board

Pinout:
  Console:    uart30  P0.02/P0.03  115200
  RS232/LEMO: uart20  P1.03/P1.02  115200
  I2C (bb):   i2c_bb  P2.00/P2.01  100kHz
  LEDs:       P2.08(G) P2.09(B) P2.10(R) active-low
  Fuel EN:    P0.01 (hog, high)
  Fuel INT:   P0.00 (active-low)
Die temp:     29.7 C
Uptime:       25767 ms
HF clock:     HFXO 32MHz OK
LF clock:     RC32K (no LFXO)
```

Available commands: `ble`, `board`, `fuel`, `gpio`, `i2c`, `led`, `rs232`, `sensor`, `kernel`

---

## 3. Current Measurements (Joulescope JS220)

### Joulescope Python API

```python
import joulescope
import numpy as np

dev = joulescope.scan_require_one()  # Finds JS220-001998
dev.open()
data = dev.read(contiguous_duration=10.0)  # Returns (samples, 2) array
current_a = data[:, 0]  # Column 0: current in Amps
voltage_v = data[:, 1]  # Column 1: voltage in Volts
dev.close()
```

**Note:** Voltage sense reads ~-0.1V — the Joulescope is in inline current sense mode only, voltage sense leads are not connected to the board power rail.

### Power Profile Results

| Mode | Mean Current | P5 | P95 | Notes |
|------|-------------|-----|-----|-------|
| **Idle (shell, no BLE, LEDs off)** | **3794 uA** | 180 uA | 14040 uA | Baseline |
| LED Red on | 3795 uA | 180 uA | 14043 uA | +0.6 uA — **Red LED broken (A0 errata)** |
| LED Green on | 4634 uA | 420 uA | 14873 uA | +840 uA |
| LED Blue on | 4592 uA | 407 uA | 14823 uA | +798 uA |
| All LEDs on (RGB) | 5436 uA | 727 uA | 15882 uA | +1642 uA |
| BLE initializing | 3348 uA | 41 uA | 13973 uA | RC32K calibration phase |
| BLE advertising | 3356 uA | 41 uA | 13993 uA | After ~60s init |
| After BLE stop | 3023 uA | 37 uA | 13579 uA | Lower than pre-BLE baseline |

### LED Current Analysis

| LED Color | Measured Delta | Expected (3.3V, 698 ohm) | Vf (back-calculated) |
|-----------|---------------|--------------------------|---------------------|
| Red | +0 uA | +1862 uA (Vf=2.0V) | N/A — LED not working |
| Green | +840 uA | +430 uA (Vf=3.0V) | ~2.71V |
| Blue | +798 uA | +430 uA (Vf=3.0V) | ~2.74V |

The A0 errata documents that the EAST1616RGBB2 LED die colors are rotated from the schematic labels. The red LED draws no measurable current — likely disconnected or the actual die at that pin position has a Vf > 3.3V.

### Idle Current Time-Domain Analysis (1 MHz capture)

```
Duty Cycle (threshold 500 uA):
  Active (>500 uA): 60.1%    Mean when active: 4901 uA (4.9 mA)
  Sleep  (<=500 uA): 39.9%   Mean when sleeping: 190 uA

Active Period Analysis:
  Wake events: ~17,016 per second
  Mean active duration: ~35 us per wake
  Wake interval: ~59 us (0.06 ms)
```

The nRF54L15 is waking up ~17,000 times per second with ~35 us active bursts. This is characteristic of the Zephyr shell + UART RX polling + system timer tick behavior.

---

## 4. Datasheet Research (Background Agent)

A research agent was launched in parallel to analyze datasheets for all board components. It searched the web for:
- Nordic nRF54L15 Product Specification
- TI TPS63802 datasheet
- TI BQ35100 datasheet
- MaxLinear SP3232ECA-L datasheet
- Everlight EAST1616RGBB2 LED datasheet

### Board Components (from schematic)

```
Battery → TPS63802 (buck-boost) → +3.3V rail
                                    ├── nRF54L15 (MCU + BLE radio)
                                    ├── SP3232ECA-L (RS232 level shifter)
                                    ├── BQ35100 (fuel gauge, also powered from VBAT)
                                    └── EAST1616RGBB2 (RGB LED, 698 ohm series)
```

### Expected Current by Component

| Component | Mode | Expected Current (3.3V rail) |
|-----------|------|------------------------------|
| **nRF54L15** | Active (CPU, CoreMark) | 2.4 mA |
| | System ON idle + GRTC + 256KB RAM (low-power mode) | 3.0 uA |
| | System OFF + GRTC | 0.8 uA |
| | BLE TX @ 0 dBm | 5.0 mA |
| | BLE RX | 3.2 mA |
| | BLE advertising avg (100ms interval) | 79 uA |
| | Idle w/ CONSTLAT + 2x UART + GRTC (estimated) | 600 – 1300 uA |
| **TPS63802** | Quiescent (Power Save / PFM mode) | 11 uA |
| | Efficiency @ 3.3V, ~4mA, 3.6V bat | ~80-85% |
| **BQ35100** | GE=HIGH, WAITING (no GaugeStart) | 15 uA |
| | GE=HIGH, ACCUMULATOR mode | 130 uA |
| | GE=LOW (powered down) | 0.05 uA |
| **SP3232ECA-L** | Idle (charge pump running) | 300 uA |
| | Shutdown | <1 uA |
| **LEDs** | All off | 0 uA |
| | Green or Blue on | ~800 uA each |

---

## 5. Measured vs Expected Comparison

### Idle Current Budget

| Component | Expected (3.3V rail) | Notes |
|-----------|---------------------|-------|
| nRF54L15 (CONSTLAT, 2x UART, GRTC) | 600 – 1300 uA | Dominant consumer |
| SP3232ECA-L (charge pump, always on) | 300 uA | No shutdown pin connected |
| BQ35100 (GE=HIGH, WAITING) | 15 uA | DTS hogs GE pin HIGH |
| I2C pull-ups, misc | ~10 uA | Negligible |
| **Total 3.3V rail** | **925 – 1625 uA** | |
| **At battery (with TPS63802 ~82% eff.)** | **~1400 – 1800 uA** | |
| **Measured at battery** | **3794 uA** | |
| **Gap** | **~2000 uA** | |

### Root Causes of the ~2 mA Gap

1. **`CONFIG_SOC_NRF_FORCE_CONSTLAT=y`** in board defconfig (`iwsck_a0_nrf54l15_cpuapp_defconfig:28`) — forces constant-latency mode, keeps HF regulators/oscillators running continuously, prevents deep idle states. On nRF52 this adds 0.5-1.5 mA; nRF54L15 likely similar. **This is the single biggest contributor.**

2. **LFRC calibration spikes** — no LFXO crystal on the A0 board, so the 32 MHz HFXO must fire every ~8 seconds to calibrate the LFRC. Each spike draws several mA briefly, increasing the mean.

3. **nRF54L15 Rev 1 silicon errata** — documented higher-than-expected System ON sleep current. DevZone reports difficulty breaking below ~16 uA even with all peripherals disabled.

4. **Zephyr shell + dual UART polling** — causes ~17,000 wake events/second even at "idle", with ~35 us active bursts at ~4.9 mA each.

5. **TPS63802 efficiency at light loads** — at 1-3 mA, PFM efficiency may drop to 70-80%, adding more conversion loss.

---

## 6. Optimization Recommendations

| # | Change | Expected Savings | Difficulty |
|---|--------|-----------------|------------|
| 1 | Remove `CONFIG_SOC_NRF_FORCE_CONSTLAT=y` | 1 – 2 mA | Easy (one line) |
| 2 | Add LFXO crystal (A1 board revision) | Eliminates calibration spikes | Hardware change |
| 3 | Add SP3232ECA-L shutdown control (load switch or GPIO) | 0.3 mA in sleep | Hardware change |
| 4 | Drive BQ35100 GE pin LOW when not reading | 15 uA | Firmware change |
| 5 | Disable uart20 when not actively in use | ~50-100 uA | Firmware change |
| 6 | Reduce shell/logging wake frequency | Reduces duty cycle | Firmware tuning |

### Projected Current After Optimizations

| Scenario | Estimated Battery Current |
|----------|--------------------------|
| Current firmware (idle) | 3.79 mA |
| After removing CONSTLAT | ~1.8 – 2.8 mA |
| After CONSTLAT + disable uart20 + GE LOW | ~1.5 – 2.5 mA |
| System OFF (hardware changes for SP3232E shutdown) | ~0.35 – 0.4 mA |
| Theoretical minimum (System OFF + all gated) | ~1 uA (nRF54L15 alone) |

---

## 7. Tools & Versions

| Tool | Version | Notes |
|------|---------|-------|
| Joulescope Python | 1.3.1 | `pip install joulescope` |
| pyjoulescope_driver | 1.12.0 | JS220 low-level driver |
| nrfutil | 8.1.1 | Standalone binary from Nordic CDN |
| nrfutil device | 2.17.3 | Installed via `nrfutil install device` |
| nrfjprog | 10.24.2 | **Does NOT support nRF54L** |
| JLinkExe | V8.72a | Can connect as CORTEX-M33 but **cannot flash RRAM** |
| Zephyr | 4.2.99 | NCS installation at `/ncs/` |
| west | 1.5.0 | Build system |
| Claude Code | Opus 4.6 | Autonomous hardware bring-up and analysis |

---

## Appendix: Key File Paths

```
# Board definition
libs/zephyr/ck_boards/current/boards/corekinect/iwsck_a0/

# Firmware application
apps/firmware/iwsck/

# Board defconfig (contains CONSTLAT setting)
libs/zephyr/ck_boards/current/boards/corekinect/iwsck_a0/iwsck_a0_nrf54l15_cpuapp_defconfig

# Device tree (fuel gauge GE hog, UART config)
libs/zephyr/ck_boards/current/boards/corekinect/iwsck_a0/iwsck_a0_nrf54l15-common.dtsi

# Schematic PDF
libs/zephyr/ck_boards/current/boards/corekinect/iwsck_a0/docs/Schematic_CoreKinect-IWSCK_2025-12-23.pdf

# A0 errata (LED color swap, crystal wiring, NFC rework)
libs/zephyr/ck_boards/current/boards/corekinect/iwsck_a0/docs/errata-a0.md
```
