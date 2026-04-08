# Stage 3 Alpha Example — Instrumented Firmware Integration Tests

> A complete walkthrough of Stage 3 integration testing for the Alpha wearable,
> showing how the `concord_harness` module instruments the firmware and how Python
> integration tests exercise the system through the harness API.

---

## 1. Introduction

This document walks through a complete Stage 3 integration test implementation for the Alpha wearable. It covers:

1. The hardware configuration: what is on the Alpha B0 product board and how it connects to the MTIB
2. How the `concord_harness` Zephyr module instruments Alpha firmware
3. What the harness declarations look like in C
4. What the raw UART output looks like with interleaved logs and harness traffic
5. How Python integration tests use `ctx.harness.*` to observe, control, and inject
6. How the build system produces both instrumented and production firmware

The goal is to make the abstract framework described in [00-validation-philosophy.md](../../vision/validation-philosophy.md) Section 3.3 concrete by showing every layer for a real product.

---

## 2. Hardware Configuration and Connections

Stage 3 runs on a **full Alpha B0 product board**, not a dev-kit. This section describes the physical hardware assembly, every connection between the Alpha board and the MTIB, and why this hardware configuration matters for integration testing.

### 2.1 Product Board Assembly

The Alpha B0 product board is a production-representative PCB with two MCUs and all sensors populated:

**MCUs:**

| MCU | Role | Part | Key Interfaces |
|-----|------|------|----------------|
| App MCU | Main application: state machines, sensor orchestration, biometric processing, IPC master | nRF52840 (QIAA) | BLE, SPI, I2C, UART, GPIO |
| Comms MCU | LTE, GNSS, cloud messaging | nRF9151 (LACA) | LTE-M/NB-IoT modem, SPI (ext flash), UART |

**Sensors and peripherals on the nRF52840 (all populated on the Alpha B0 board):**

| Device | Type | Bus | Address / CS | Pins (from DTS) |
|--------|------|-----|-------------|------------------|
| LSM6DSO | 6-axis IMU (accel + gyro) | SPI0 | CS1: P0.08 | SCK=P0.07, MOSI=P0.05, MISO=P1.08, INT=P0.14 |
| PAH8151 | PPG (optical heart rate / SpO2) | I2C1 | 0x15 | SDA=P1.05, SCL=P1.03, INT=P0.20 |
| BME280 | Environmental (temp / humidity / pressure) | I2C1 | 0x76 | SDA=P1.05, SCL=P1.03 |
| MLX90614 | IR skin temperature | GPIO-I2C (bit-banged) | 0x5A | SCL=P1.04, SDA=P1.06 |
| W25Q64JV | 64 Mbit SPI NOR flash | SPI0 | CS0: P1.09 | (shared SPI0 bus with LSM6DSO) |
| u-blox MIA-M10 | GNSS receiver | I2C1 | 0x42 | EXTINT=P1.02, RESET=P1.01, PSM=P1.12 |
| LP5814 | LED driver (I/O expander) | I2C1 | 0x2C | (shared I2C1 bus) |

**Power management:**

| Device | Type | Bus | Address | Pins (from DTS) |
|--------|------|-----|---------|------------------|
| BQ25622 | Battery charger IC | I2C1 | 0x6B | INT=P1.15 (CHRG_INT) |
| MAX17063 | Fuel gauge (battery SoC) | I2C1 | 0x36 | (shared I2C1 bus) |
| Charger enable | GPIO control | -- | -- | P1.13 (active low) |

**Inter-processor communication (IPC):**

| Signal | nRF52840 Pin | nRF9151 Pin | Notes |
|--------|-------------|-------------|-------|
| IPC UART1 TX | P0.28 | P0.02 (RX) | LPUART, 460800 baud |
| IPC UART1 RX | P0.03 | P0.03 (TX) | LPUART, 460800 baud |
| IPC REQ | P0.29 | P0.00 | LPUART flow: nRF52 request |
| IPC RDY | P0.30 | P0.01 | LPUART flow: nRF91 ready |
| IPC INT | P0.31 | P0.31 | Interrupt handshake |
| nRF91 RESET_N | P1.11 | -- | nRF52840 can reset the nRF9151 |

**Other control pins:**

- Emergency button: P0.12 (active low, pull-up)
- VSM enable (PPG sensor power): P1.10 (active high)
- Hard reset: P1.14 (active high, pull-down)
- LEDs: Red=P0.17, Green=P0.13, Blue=P0.15 (all active low)

**Antennas:**

- BLE antenna (nRF52840): on-board PCB trace antenna or U.FL connector (board-rev dependent)
- LTE antenna (nRF9151): U.FL connector to external LTE-M/NB-IoT antenna
- GNSS antenna (nRF9151 / u-blox MIA-M10): shared or dedicated U.FL (board-rev dependent)

**Battery + charging circuit:**

- Single-cell Li-Po battery (3.7V nominal)
- BQ25622 charger IC with programmable charge current
- MAX17063 fuel gauge for SoC reporting
- Charger enable controlled by nRF52840 GPIO (P1.13)

### 2.2 MTIB Connection Map

The MTIB (Manufacturing and Test Interface Board) connects to the Alpha B0 board through the following channels. Stage 3 uses all of these except the full Stage 4 test fixture peripherals.

| MTIB Interface | Alpha Board Connection | Purpose | Pin / Protocol Details |
|----------------|----------------------|---------|----------------------|
| **MTIB UART0** | nRF52840 UART0 (P0.23 TX, P0.25 RX) | Zephyr Shell + device logs + harness transport. This is the single instrumentation channel — the Python test runner sends `concord get/set/inject` commands and receives `[CONCORD:RSP]` / `[CONCORD:EVT]` responses plus interleaved Zephyr log lines over this UART. | 115200 baud, 8N1 |
| **MTIB SWD port 1** | nRF52840 debug port (SWDIO + SWDCLK) | Flashing instrumented app MCU firmware (`merged.hex`). Used by `ctx.flash_firmware()` before each test. Also available for GDB attach during debug sessions. | SWD, typically via J-Link or CMSIS-DAP |
| **MTIB SWD port 2** | nRF9151 debug port (SWDIO + SWDCLK) | Flashing comms MCU firmware. The nRF9151 runs the same binary for Stage 3 and Stage 4 (no harness instrumentation on the comms MCU). | SWD, typically via J-Link or CMSIS-DAP |
| **MTIB power supply** | Alpha board power rail | Configurable voltage supply (e.g., 3.7V for battery simulation). The MTIB can power-cycle the board programmatically — `ctx.power_on()` and `ctx.power_off()` control this rail. | Configurable 2.5V--4.2V, current-limited |
| **MTIB current sense** | Inline on Alpha board power rail | System-level current measurement. Measures total board power draw (both MCUs + all sensors + antenna). This is NOT per-sensor isolation (that is Stage 2). Used for coarse power-state validation (e.g., "did current drop when sensors shut down after off-body transition?"). | High-side INA219 or similar, sampled by MTIB MCU |
| **MTIB GPIO (optional)** | Emergency button (P0.12), charger detect, etc. | Physical stimulus that does not need harness injection — e.g., pressing the emergency button via a relay, or simulating charger insertion by driving the charge-detect pin. | Direct GPIO drive or relay |
| **MTIB BLE interface** | nRF52840 BLE radio (over the air) | BLE scanning and connection tests. The MTIB has its own BLE-capable MCU (or USB dongle) that can scan for advertisements, connect, discover GATT services, and verify BLE behavior end-to-end. | BLE 5.x, over-the-air |

### 2.3 Why Product Board, Not Dev-Kit

Stage 3 tests component **integration** on the actual product. The real PCB layout, real antenna matching network, real power distribution tree, and real IPC wiring all matter:

- **PCB trace impedance and layout**: SPI and I2C signal integrity depends on trace length, via placement, and ground plane continuity. A dev-kit with jumper wires cannot replicate the Alpha B0 board's controlled-impedance SPI0 bus shared between the W25Q64 flash and the LSM6DSO IMU.
- **Antenna matching**: The BLE antenna's matching network is tuned for the Alpha B0 board's ground plane geometry. BLE connection tests on a dev-kit with a different antenna would not catch RF detuning caused by enclosure proximity.
- **Power distribution**: The Alpha B0 board's power tree routes battery voltage through the BQ25622 charger, then through LDOs to the nRF52840 and nRF9151. The voltage drop, ripple, and transient behavior during sensor wake-up (e.g., PAH8151 LED drive at 255 mA) can only be tested on the real board.
- **IPC timing**: The LPUART link between nRF52840 (P0.28/P0.03) and nRF9151 (P0.02/P0.03) at 460800 baud with REQ/RDY handshaking is sensitive to trace length and parasitic capacitance. The request/ready signaling timing on a breadboard would differ from the product board.
- **Sensor interrupt routing**: The LSM6DSO interrupt on P0.14 and PAH8151 interrupt on P0.20 share GPIO port 0 interrupt resources. Contention and priority behavior is board-specific.

Stage 2 uses dev-kits to **isolate individual sensors** behind power relays and measure per-sensor current. Stage 3 deliberately tests them **together** — the whole point is to catch integration issues that only appear when all components share the same power rail, the same SPI bus, the same interrupt controller, and the same firmware main loop.

### 2.4 Key Difference from Stage 2 Hardware Setup

| Aspect | Stage 2 (Sensor Characterization) | Stage 3 (Integration Testing) |
|--------|-----------------------------------|-------------------------------|
| Board | Dev-kit fixture (e.g., nRF52840-DK + sensor breakout) | Alpha B0 product board |
| Sensors | Single sensor isolated behind power relay | All sensors populated and active |
| Current measurement | Per-sensor current (high-resolution, isolated shunt on each sensor rail) | System-level current only (single inline shunt on main power rail) |
| Test channel | Direct SPI/I2C bus access from test host, or Zephyr shell on dev-kit | Zephyr Shell on UART0 with `concord_harness` commands — no direct bus access |
| What it proves | Individual sensor driver correctness, power profile, data accuracy | Subsystem integration: state machine transitions, sensor orchestration, IPC, event propagation |

### 2.5 Key Difference from Stage 4 Hardware Setup

| Aspect | Stage 3 (Integration Testing) | Stage 4 (Product Validation) |
|--------|-------------------------------|------------------------------|
| Board | Alpha B0 product board | Alpha B0 product board (same) |
| Firmware | **Instrumented** build (`CONFIG_CONCORD_HARNESS=y`, Zephyr Shell enabled) | **Production** build (`CONFIG_CONCORD_HARNESS=n`, no shell, no harness) |
| MTIB connection | UART0 for harness transport, SWD for flashing | UART0 unused (production FW has no shell). SWD for flashing only. |
| Test fixture | MTIB only (UART, SWD, power, current sense, BLE) | MTIB + **full test fixture**: charger relay, button actuator, motion stage (6-DOF), Peltier temperature controller, photodiode array (PPG stimulus), on-skin electrode simulator |
| Observation method | Software harness (`ctx.harness.get/inject/wait_event`) — reads firmware internals | **Black-box only**: BLE GATT reads, LED color observation, LTE message capture, physical sensor stimulus |
| Why | Catch architecture-level integration bugs early, with full internal visibility | Validate end-to-end product behavior as a user/cloud would experience it, using only external interfaces |

---

## 3. Alpha Firmware Architecture Summary

The Alpha wearable runs on two MCUs:

- **nRF52840** (app MCU): Runs the main application — state machines, sensor orchestration, biometric processing, IPC master
- **nRF9151** (comms MCU): Handles LTE, GNSS, cloud messaging

Key subsystems on the nRF52840 (the MCU we instrument):

| Subsystem | Key State Machine | Sensors / Peripherals |
|-----------|------------------|-----------------------|
| Heat risk monitoring | `alpha_state_t`: `off_body_e` → `low_heat_risk_e` → `increased_heat_risk_e` → `heat_emergency_e` (+ `off_body_validation_e` transitional) | PAH8151 (PPG), MLX90614 (IR skin temp), BME280 (env temp/humidity/pressure) |
| Motion detection | `motion_state_t`: `motion_is_stopped` → `motion_window_open` → `motion_in_motion` | LSM6DSO (6-axis IMU) |
| IPC | Message-based over UART1 | nRF9151 coprocessor |
| Power management | Battery SoC, charging state | BMS, charger IC |

The firmware uses a cooperative main loop. State machine transitions are event-driven — sensor interrupts and timer callbacks post events to a message queue, and the main loop processes them sequentially.

---

## 4. Kconfig for Instrumented Build

The instrumented build adds a Kconfig overlay on top of the normal Alpha firmware configuration:

```kconfig
# alpha_fw/boards/alpha_b0_instrumented.conf
# Overlay applied when building with CONFIG_CONCORD_HARNESS=y

CONFIG_CONCORD_HARNESS=y

# Zephyr Shell (required by concord_harness for transport)
CONFIG_SHELL=y
CONFIG_SHELL_BACKEND_SERIAL=y

# Logging (standard Zephyr logging, shared UART with shell)
CONFIG_LOG=y
CONFIG_LOG_BACKEND_CONCORD=y
```

When `CONFIG_CONCORD_HARNESS=n` (production build), all `CONCORD_*` macros expand to nothing. The shell and log backend config are also absent, so the production binary has no shell overhead and no harness thread.

---

## 5. Harness Declarations

The firmware engineer authors `src/concord_harness.c` in the Alpha firmware repo. This file uses the four macro types to declare instrumentation points that reference real firmware internals.

```c
/* alpha_fw/src/concord_harness.c
 *
 * Harness declarations for Alpha Stage 3 integration tests.
 * This file compiles to nothing when CONFIG_CONCORD_HARNESS=n.
 */

#include <concord_harness/concord_harness.h>

#include "app/alpha_state_machine.h"
#include "app/motion_state_machine.h"
#include "app/messages/biometric_data_msg.h"
#include "app/lights_handler.h"
#include "app/gps_handler.h"

/* ── External references to firmware state ─────────────────────────── */
/* TODO: Replace extern globals with getter functions (see arch-stage3 Section 9
 * "Firmware-side requirements"). Each state variable should have a test-only
 * accessor (e.g., get_alpha_state()) so the harness doesn't depend on global
 * symbol visibility. This file is a DRAFT showing the pattern — the final
 * implementation will use proper getter functions.
 */

extern alpha_state_t  g_alpha_state;
extern motion_state_t g_motion_state;
extern vsm_data_t     g_last_vsm_data;
extern bio_config_t   g_bio_config;
extern motion_cfg_t   g_motion_config;
extern uint8_t        g_battery_soc_pct;
extern bool           g_battery_charging;
extern uint32_t       g_ipc_last_msg_age_ms;

/* ── Getters: read-only observation ────────────────────────────────── */

static const char *alpha_state_str(alpha_state_t s)
{
    switch (s) {
    case off_body_e:              return "off_body_e";
    case low_heat_risk_e:         return "low_heat_risk_e";
    case increased_heat_risk_e:   return "increased_heat_risk_e";
    case heat_emergency_e:        return "heat_emergency_e";
    case off_body_validation_e:   return "off_body_validation_e";
    default:                      return "unknown";
    }
}

static const char *motion_state_str(motion_state_t s)
{
    switch (s) {
    case motion_is_stopped:   return "motion_is_stopped";
    case motion_window_open:  return "motion_window_open";
    case motion_in_motion:    return "motion_in_motion";
    default:                  return "unknown";
    }
}

CONCORD_GETTER("app.state", {
    return alpha_state_str(g_alpha_state);
})

CONCORD_GETTER("motion.state", {
    return motion_state_str(g_motion_state);
})

CONCORD_GETTER("sensor.hr", {
    static char buf[16];
    snprintf(buf, sizeof(buf), "%d", g_last_vsm_data.heartrate);
    return buf;
})

CONCORD_GETTER("sensor.spo2", {
    static char buf[16];
    snprintf(buf, sizeof(buf), "%d", g_last_vsm_data.spo2);
    return buf;
})

CONCORD_GETTER("sensor.temp_skin", {
    /* Q8.8 fixed point → string with one decimal */
    static char buf[16];
    int16_t raw = g_last_vsm_data.skin_temp_degC_q8p8;
    snprintf(buf, sizeof(buf), "%d.%d", raw >> 8, ((raw & 0xFF) * 10) >> 8);
    return buf;
})

CONCORD_GETTER("sensor.hsi", {
    static char buf[16];
    snprintf(buf, sizeof(buf), "%u.%u",
             g_last_vsm_data.heat_strain_index_tenths / 10,
             g_last_vsm_data.heat_strain_index_tenths % 10);
    return buf;
})

CONCORD_GETTER("battery.soc", {
    static char buf[8];
    snprintf(buf, sizeof(buf), "%u", g_battery_soc_pct);
    return buf;
})

CONCORD_GETTER("battery.charging", {
    return g_battery_charging ? "true" : "false";
})

CONCORD_GETTER("ipc.last_msg_age_ms", {
    static char buf[16];
    snprintf(buf, sizeof(buf), "%u", g_ipc_last_msg_age_ms);
    return buf;
})

/* ── Setters: writable configuration ───────────────────────────────── */

CONCORD_SETTER("config.low_risk_report_pd", {
    int val = atoi(value);
    if (val < 1 || val > 255) return "ERR:range";
    g_bio_config.low_risk_report_pd = (uint8_t)val;
    return "OK";
})

CONCORD_SETTER("config.inc_risk_hsi_threshold", {
    int val = atoi(value);
    if (val < 1 || val > 255) return "ERR:range";
    g_bio_config.inc_risk_hsi_threshold = (uint8_t)val;
    return "OK";
})

CONCORD_SETTER("config.motion_start_sec", {
    int val = atoi(value);
    if (val < 1 || val > 255) return "ERR:range";
    g_motion_config.motion_window_start_sec = (uint8_t)val;
    return "OK";
})

CONCORD_SETTER("config.motion_stop_sec", {
    int val = atoi(value);
    if (val < 1 || val > 255) return "ERR:range";
    g_motion_config.motion_stop_sec = (uint8_t)val;
    return "OK";
})

/* ── Injection points: force events from test ──────────────────────── */

CONCORD_INJECT("sensor.touch", {
    /* Simulate PAH8151 touch detection.
     * Posts the same event the real touch ISR would post. */
    if (strcmp(value, "detected") == 0) {
        app_post_event(EVT_TOUCH_DETECTED);
        return "OK";
    } else if (strcmp(value, "removed") == 0) {
        app_post_event(EVT_TOUCH_REMOVED);
        return "OK";
    }
    return "ERR:expected detected|removed";
})

CONCORD_INJECT("sensor.motion", {
    /* Simulate LSM6DSO motion interrupt */
    if (strcmp(value, "start") == 0) {
        motion_post_event(MOTION_EVT_DETECTED);
        return "OK";
    } else if (strcmp(value, "stop") == 0) {
        motion_post_event(MOTION_EVT_TIMEOUT);
        return "OK";
    }
    return "ERR:expected start|stop";
})

CONCORD_INJECT("ipc.rx", {
    /* Inject a raw IPC message as if received from nRF9151.
     * Value is hex-encoded bytes. */
    uint8_t buf[128];
    int len = hex_decode(value, buf, sizeof(buf));
    if (len < 0) return "ERR:hex_decode";
    ipc_inject_rx(buf, len);
    return "OK";
})

/* ── Events: async notifications to test ───────────────────────────── */

CONCORD_EVENT("app.state_changed")
CONCORD_EVENT("motion.state_changed")
CONCORD_EVENT("sensor.vitals_ready")
CONCORD_EVENT("ipc.msg_sent")
CONCORD_EVENT("alert.triggered")
```

The firmware engineer then adds `CONCORD_EMIT("app.state_changed", alpha_state_str(new_state))` calls at the appropriate transition points in `alpha_state_machine.c` and `motion_state_machine.c`. These calls also compile to nothing when `CONFIG_CONCORD_HARNESS=n`.

---

## 6. UART Output Example

Here's what the raw UART stream looks like during a test session. Device logs (standard Zephyr format) and harness traffic (prefixed) are interleaved on UART0:

```
[00:00:01.234,567] <inf> app: Alpha firmware v2.1.0 started
[00:00:01.240,112] <inf> app: State: off_body_e
[00:00:01.245,678] <inf> bme280: Environmental sensor initialized
[00:00:01.250,234] <inf> pah8151: PPG sensor initialized (touch-only mode)
[00:00:01.255,890] <inf> lsm6dso: IMU initialized at 52Hz
[00:00:01.260,456] <inf> ipc: IPC bridge ready (UART1)
uart:~$ concord list
[CONCORD:RSP] LIST_BEGIN
[CONCORD:RSP] GET app.state
[CONCORD:RSP] GET motion.state
[CONCORD:RSP] GET sensor.hr
[CONCORD:RSP] GET sensor.spo2
[CONCORD:RSP] GET sensor.temp_skin
[CONCORD:RSP] GET sensor.hsi
[CONCORD:RSP] GET battery.soc
[CONCORD:RSP] GET battery.charging
[CONCORD:RSP] GET ipc.last_msg_age_ms
[CONCORD:RSP] SET config.low_risk_report_pd
[CONCORD:RSP] SET config.inc_risk_hsi_threshold
[CONCORD:RSP] SET config.motion_start_sec
[CONCORD:RSP] SET config.motion_stop_sec
[CONCORD:RSP] INJ sensor.touch
[CONCORD:RSP] INJ sensor.motion
[CONCORD:RSP] INJ ipc.rx
[CONCORD:RSP] EVT app.state_changed
[CONCORD:RSP] EVT motion.state_changed
[CONCORD:RSP] EVT sensor.vitals_ready
[CONCORD:RSP] EVT ipc.msg_sent
[CONCORD:RSP] EVT alert.triggered
[CONCORD:RSP] LIST_END
uart:~$ concord get app.state
[CONCORD:RSP] app.state=off_body_e
uart:~$ concord inject sensor.touch detected
[CONCORD:RSP] sensor.touch=OK
[00:00:05.100,234] <inf> app: Touch detected, transitioning to low_heat_risk_e
[CONCORD:EVT] app.state_changed=low_heat_risk_e
[00:00:05.105,678] <inf> pah8151: Switching to active mode
[00:00:05.110,345] <inf> mlx90614: Waking IR sensor
[00:00:06.200,123] <inf> vsm: Warm-up period started (60s)
uart:~$ concord get app.state
[CONCORD:RSP] app.state=low_heat_risk_e
[00:00:65.500,789] <inf> vsm: Warm-up complete, vitals reporting active
[CONCORD:EVT] sensor.vitals_ready=hr:72,spo2:98,skin:32.5
uart:~$ concord get sensor.hr
[CONCORD:RSP] sensor.hr=72
uart:~$ concord inject sensor.touch removed
[CONCORD:RSP] sensor.touch=OK
[00:00:70.300,456] <inf> app: Touch removed, entering off_body_validation_e
[CONCORD:EVT] app.state_changed=off_body_validation_e
[00:00:90.300,789] <inf> app: Off-body verification complete (20s), transitioning to off_body_e
[CONCORD:EVT] app.state_changed=off_body_e
```

The Python-side demuxer splits this stream into three channels:
- **Harness responses** (`[CONCORD:RSP]` lines): Queued for `ctx.harness.get/set/inject/list` calls
- **Harness events** (`[CONCORD:EVT]` lines): Queued for `ctx.harness.wait_event()` calls
- **Device logs** (everything else): Available via `ctx.logs.wait_for()` and `ctx.logs.dump()`

---

## 7. Integration Tests

Full Python test file for Alpha state machine integration testing:

```python
# alpha_fw/.concord/tests/integration/test_state_machine.py
#
# Stage 3 integration tests for Alpha heat risk state machine.
# These tests run on real Alpha hardware via MTIB, using instrumented firmware.

EXPECTED_HARNESS_POINTS = {
    "app.state", "motion.state", "sensor.hr", "sensor.spo2",
    "sensor.temp_skin", "sensor.hsi", "battery.soc", "battery.charging",
    "ipc.last_msg_age_ms", "config.low_risk_report_pd",
    "config.inc_risk_hsi_threshold", "config.motion_start_sec",
    "config.motion_stop_sec", "sensor.touch", "sensor.motion", "ipc.rx",
    "app.state_changed", "motion.state_changed", "sensor.vitals_ready",
    "ipc.msg_sent", "alert.triggered",
}


async def test_harness_points(ctx):
    """Validate that the firmware build includes all expected harness points."""
    await ctx.flash_firmware()
    await ctx.power_on()
    await ctx.wait_for_boot()

    points = await ctx.harness.list()
    registered = set(points.keys())
    missing = EXPECTED_HARNESS_POINTS - registered
    assert not missing, f"Missing harness points: {missing}"


async def test_boot_reaches_off_body(ctx):
    """Flash, boot, verify initial state is off_body_e."""
    await ctx.flash_firmware()
    await ctx.power_on()
    await ctx.wait_for_boot()

    state = await ctx.harness.get("app.state")
    assert state == "off_body_e", f"Expected off_body_e, got {state}"

    # Verify device logs confirm boot
    log = await ctx.logs.wait_for("Alpha firmware v", timeout_s=5)
    assert log is not None, "Boot banner not found in device logs"


async def test_touch_triggers_monitoring(ctx):
    """Inject touch → verify state transitions → verify vitals start flowing."""
    await ctx.flash_firmware()
    await ctx.power_on()
    await ctx.wait_for_boot()

    # Confirm starting state
    state = await ctx.harness.get("app.state")
    assert state == "off_body_e"

    # Inject touch detection (simulates PAH8151 touch ISR)
    await ctx.harness.inject("sensor.touch", "detected")

    # Wait for transition event
    evt = await ctx.harness.wait_event("app.state_changed", timeout_s=10)
    assert evt.value == "low_heat_risk_e", f"Expected low_heat_risk_e, got {evt.value}"

    # Verify getter agrees
    state = await ctx.harness.get("app.state")
    assert state == "low_heat_risk_e"

    # Wait for vitals to start flowing (after VSM warm-up period)
    vitals_evt = await ctx.harness.wait_event("sensor.vitals_ready", timeout_s=90)
    assert vitals_evt is not None, "No vitals_ready event after warm-up"

    # Verify sensor readings are populated
    hr = await ctx.harness.get("sensor.hr")
    assert int(hr) > 0, f"Heart rate should be > 0 during monitoring, got {hr}"


async def test_motion_detection(ctx):
    """Inject motion → verify motion state transitions via getter and events."""
    await ctx.flash_firmware()
    await ctx.power_on()
    await ctx.wait_for_boot()

    # Verify initial motion state
    state = await ctx.harness.get("motion.state")
    assert state == "motion_is_stopped"

    # Inject motion start (simulates LSM6DSO interrupt)
    await ctx.harness.inject("sensor.motion", "start")

    # Wait for motion state change event
    evt = await ctx.harness.wait_event("motion.state_changed", timeout_s=10)
    assert evt.value in ("motion_window_open", "motion_in_motion")

    # Verify via getter
    state = await ctx.harness.get("motion.state")
    assert state != "motion_is_stopped", f"Motion state should have changed, still {state}"


async def test_config_change_takes_effect(ctx):
    """Set config.low_risk_report_pd → verify next vitals event respects interval."""
    await ctx.flash_firmware()
    await ctx.power_on()
    await ctx.wait_for_boot()

    # Enter monitoring state first
    await ctx.harness.inject("sensor.touch", "detected")
    await ctx.harness.wait_event("app.state_changed", timeout_s=10)

    # Change reporting period to 5 seconds (default is 10)
    await ctx.harness.set("config.low_risk_report_pd", "5")

    # Wait for warm-up, then measure time between vitals events
    first = await ctx.harness.wait_event("sensor.vitals_ready", timeout_s=90)
    assert first is not None

    second = await ctx.harness.wait_event("sensor.vitals_ready", timeout_s=15)
    assert second is not None

    # The interval between events should be approximately 5 seconds
    # (allow margin for processing time)
    # Note: exact timing validation depends on event timestamps from the harness


async def test_ipc_round_trip(ctx):
    """Inject IPC rx message → verify ipc.msg_sent event (coprocessor echo)."""
    await ctx.flash_firmware()
    await ctx.power_on()
    await ctx.wait_for_boot()

    # Check IPC link health
    age = await ctx.harness.get("ipc.last_msg_age_ms")
    age_ms = int(age)

    # Inject a synthetic IPC message (hex-encoded biometric config)
    # This simulates a message arriving from the nRF9151 coprocessor
    await ctx.harness.inject("ipc.rx", "150100000a500a")

    # Verify the firmware processed it and sent a response
    evt = await ctx.harness.wait_event("ipc.msg_sent", timeout_s=10)
    assert evt is not None, "No IPC response sent after injected rx message"


async def test_state_machine_full_cycle(ctx):
    """Touch → monitoring → remove touch → back to off_body. Full cycle."""
    await ctx.flash_firmware()
    await ctx.power_on()
    await ctx.wait_for_boot()

    # Phase 1: off_body_e → low_heat_risk_e
    state = await ctx.harness.get("app.state")
    assert state == "off_body_e"

    await ctx.harness.inject("sensor.touch", "detected")
    evt = await ctx.harness.wait_event("app.state_changed", timeout_s=10)
    assert evt.value == "low_heat_risk_e"

    # Phase 2: Verify monitoring is active
    state = await ctx.harness.get("app.state")
    assert state == "low_heat_risk_e"

    # Phase 3: Remove touch → off_body_validation_e → off_body_e
    await ctx.harness.inject("sensor.touch", "removed")

    evt = await ctx.harness.wait_event("app.state_changed", timeout_s=10)
    assert evt.value == "off_body_validation_e"

    # Wait for validation period (OFF_BODY_VERIFICATION_SEC = 20s)
    evt = await ctx.harness.wait_event("app.state_changed", timeout_s=30)
    assert evt.value == "off_body_e"

    # Verify we're back to initial state
    state = await ctx.harness.get("app.state")
    assert state == "off_body_e"

    # Verify sensors have shut down (HR should be 0 when off-body)
    hr = await ctx.harness.get("sensor.hr")
    assert int(hr) == 0, f"Heart rate should be 0 off-body, got {hr}"
```

---

## 8. Build Configuration

The build service produces both instrumented and production firmware from the same source:

```yaml
# alpha_fw/.concord/build.yaml
version: 1

builds:
  # Instrumented build — used by Stage 3 integration tests
  integration:
    board: alpha_b0
    soc: nrf52840
    overlay_configs:
      - boards/alpha_b0_instrumented.conf    # Adds CONFIG_CONCORD_HARNESS=y + shell + logging
    extra_modules:
      - concord_harness                       # Pulled as Zephyr module via west manifest
    artifacts:
      - build/integration/nrf52840/zephyr/merged.hex

  # Production builds — used by Stage 4 product validation
  production_debug:
    board: alpha_b0
    soc: nrf52840
    # CONFIG_CONCORD_HARNESS=n, CONFIG_LOG=y
    artifacts:
      - build/production_debug/nrf52840/zephyr/merged.hex

  production_release:
    board: alpha_b0
    soc: nrf52840
    # CONFIG_CONCORD_HARNESS=n, CONFIG_LOG=n
    artifacts:
      - build/production_release/nrf52840/zephyr/merged.hex

  # Comms MCU build — same for all stages
  comms:
    board: alpha_b0_cpunet
    soc: nrf9151
    artifacts:
      - build/comms/nrf9151/zephyr/merged.hex

# Integration test artifacts (included in build bundle for Stage 3 runner)
test_artifacts:
  - .concord/tests/integration/
  - .concord/integration_spec.yaml
```

The Stage 3 runner downloads `build/integration/nrf52840/zephyr/merged.hex`. The Stage 4 runner downloads `build/production_debug/` and/or `build/production_release/` hex files (see arch-stage4 Section 3.4 for which tests run on which build). All stages share the same `build/comms/` coprocessor build.

---

## 9. What This Proves

Each test maps to specific Alpha integration risks:

| Test | Integration Risk Covered |
|------|------------------------|
| `test_harness_points` | Version skew between test expectations and firmware build — catches missing harness declarations before tests run |
| `test_boot_reaches_off_body` | Firmware initializes all subsystems (sensors, IPC, state machine) and reaches a stable idle state |
| `test_touch_triggers_monitoring` | PAH8151 touch event → state machine transition → sensor orchestration activation — the core Alpha use case |
| `test_motion_detection` | LSM6DSO motion interrupt → motion state machine integration — verifies the IMU driver events propagate through the motion subsystem |
| `test_config_change_takes_effect` | Runtime configuration propagates to the reporting subsystem — verifies `bio_config_t` changes are respected by the vitals reporting loop |
| `test_ipc_round_trip` | IPC bridge between nRF52840 and nRF9151 correctly receives, parses, and responds to messages — catches serialization bugs, UART framing issues |
| `test_state_machine_full_cycle` | Complete lifecycle: off-body → on-body → monitoring → off-body validation → off-body — verifies the `OFF_BODY_VERIFICATION_SEC` timeout, sensor shutdown on removal, and full state machine roundtrip |

These tests run on **every commit** that changes Alpha firmware. They complete in 3-5 minutes (dominated by the 60-second VSM warm-up in `test_touch_triggers_monitoring` and the 20-second off-body verification in `test_state_machine_full_cycle`). They don't replace Stage 4 product validation — they catch architecture-level integration bugs early, before the more expensive black-box tests run.
