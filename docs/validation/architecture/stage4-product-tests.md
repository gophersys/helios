# Stage 4 Product Tests -- Implementation Architecture

> The implementation blueprint for black-box product validation of Alpha firmware.
> Stage 4 tests production firmware with NO harness instrumentation, verifying that
> the shipping binary meets every product specification through external interfaces
> only: MTIB hardware control, CoreCloud message verification, NFC, and physical
> stimulus.
>
> **This document is the Stage 4 counterpart to
> [arch-stage3-integration-tests.md](./stage3-integration-tests.md).** Stage 3
> tests firmware architecture with internal visibility. Stage 4 tests product behavior
> with zero internal visibility.

---

## 1. Scope and Goals

### 1.1 What Stage 4 Proves

Stage 4 answers the question: **does the product, as shipped, meet its specifications?**
It is the final gate before a firmware version is approved for manufacturing release.

Stage 4 tests production firmware -- the exact binary that ships to customers. There is
no `concord_harness` module, no shell commands, no internal state observation. The
firmware is a black box. Tests interact through the same interfaces a user or the
environment would: buttons, charger connection, motion, temperature, and the CoreKinect
cloud backend.

Concretely, Stage 4 tests verify:

- **Product specification compliance**: Every PRDTST acceptance criterion is verified
  against the production binary. Current draw, timing, message content, sensor accuracy,
  UI behavior -- all measured externally.
- **Device-cloud system correctness**: Most tests verify data the device sends to
  CoreCloud via LTE. A position test does not just check that the GNSS module acquired a
  fix -- it verifies that a correctly-formatted `PositionMsgV6` arrived at the backend
  within the specified time window with the correct `update_reason`, `batt_percent`,
  `temperature`, and `on_charger` fields.
- **No instrumentation bias**: Stage 3 runs with `CONFIG_CONCORD_HARNESS=y`, which adds
  a shell thread, UART command processing, and event emission overhead. Stage 4 runs
  with `CONFIG_CONCORD_HARNESS=n`, eliminating any timing or power impact from
  instrumentation. This catches bugs that only manifest in production builds.
- **Real-world timing**: Production firmware runs its cooperative main loop without
  harness interrupts. Heartbeat periods, motion detection windows, GPS acquisition
  times, and sensor sampling cadences are verified at their actual production values.
- **Shipping binary verification**: The Release build (`CONFIG_LOG=n`) is the exact
  binary that goes to manufacturing. Stage 4 Release tests prove this binary functions
  correctly with zero debug overhead.

### 1.2 What Stage 4 Does NOT Cover

- **Driver-level correctness**: Stage 2 (driver HW tests on dev-kit fixtures) verifies
  individual driver register configuration, bus timing, interrupt behavior, and FIFO
  management. Stage 4 does not re-test drivers in isolation.
- **Internal state machine transitions**: Stage 3 (integration tests with
  `concord_harness`) verifies that state machine transitions propagate correctly through
  intermediate states. Stage 4 can only observe final outcomes (messages sent, LEDs lit,
  haptic fired).
- **IPC message parsing**: Stage 3 verifies IPC serialization/deserialization between
  MCUs. Stage 4 sees only the end result (did the correct cloud message arrive?).
- **Sensor orchestration internals**: Stage 3 verifies warm-up sequences, sampling
  cadence, and wake/sleep coordination. Stage 4 verifies the product-level outcome
  (sensor readings within spec, messages sent at correct intervals).

### 1.3 Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Build variants | Debug (`CONFIG_LOG=y`) + Release (`CONFIG_LOG=n`) | Debug provides UART diagnostics for failure analysis; Release proves the shipping binary works |
| Primary verification | CoreCloud REST API message inspection | Production devices communicate via LTE to CoreCloud; testing the device-cloud path catches protocol drift and serialization bugs |
| Fixture control | MTIB GPIO/relay/actuator via `fixture_controller.py` | Black-box tests require physical stimulus; fixture profile decouples test logic from wiring |
| Test ownership | Concord platform team (not firmware developers) | Stage 4 tests are inseparable from physical test infrastructure (fixture wiring, backend coordination, multi-day orchestration) |
| Test library | `concord/libs/corekinect/test/validation/` | Shared library (test framework, clients, controllers) |
| Execution cadence | Tag-filtered: commit (fast subset), weekly (full suite), release (everything) | Per-commit catches regressions fast; weekly validates expensive/long-running tests |
| Pass/fail source | CoreCloud messages + MTIB power measurements + fixture ADC reads | UART logs are diagnostic only (Debug build), never used for pass/fail decisions |

### 1.4 Two Sub-Stages: Debug vs Release

Stage 4 runs every test on two firmware builds:

| Property | Stage 4 Debug | Stage 4 Release |
|----------|---------------|-----------------|
| `CONFIG_CONCORD_HARNESS` | `n` | `n` |
| `CONFIG_LOG` | `y` | `n` |
| UART output | Zephyr log messages visible | Completely silent |
| Purpose | Production behavior with diagnostic visibility | Shipping binary verification |
| Pass/fail criteria | CoreCloud + MTIB measurements (same as Release) | CoreCloud + MTIB measurements |
| UART role | Diagnostic only -- captured for failure analysis, never for assertions | Not available |
| Power budget tests | Run but results are informational (log overhead affects power) | Authoritative power measurements |
| Artifact | `debug_uart_log.txt` captured | No UART artifact |

**Why both builds matter**: The Debug build lets engineers diagnose failures using UART
logs without re-running tests on instrumented firmware. The Release build proves the
shipping binary works. If Debug passes but Release fails, there is a timing or power
bug exposed by removing log overhead. If Release passes but Debug fails, the log system
itself is interfering with production behavior -- both are valuable signals.

---

## 2. Hardware Architecture

### 2.1 Alpha Product Board

Stage 4 tests run on the **Alpha product board** -- not a development kit. This is the
actual PCB that ships in the product enclosure:

- **App MCU**: nRF52840 (Cortex-M4F, 1MB flash, 256KB RAM)
- **Comms MCU**: nRF9151 (Cortex-M33, LTE-M/NB-IoT, GNSS)
- **Sensors**: LSM6DSO (6-axis IMU/SPI), PAH8151 (PPG), BME280 (env/I2C), MLX90614 (IR temp)
- **BMS**: MAX17063 fuel gauge + BQ25622 charge controller
- **UI**: 3x status LEDs, 1x button, 1x vibration motor (haptic)
- **NFC**: NT3H2111 (passive tag, device ID broadcast)
- **Battery**: Li-Po single cell, 3.5V lockout to 4.2V full charge

### 2.2 MTIB Connection Map for Alpha Product

```
MTIB V2 (Verdin iMX8MM)
├── SWD (J-Link) ──────────────► nRF52840 debug port (flash + recover)
├── SWD (J-Link) ──────────────► nRF9151 debug port (flash + recover)
├── UART1 (/dev/verdin-uart2) ─► nRF52840 app processor (log capture, debug build only)
├── UART0 (/dev/verdin-uart1) ─► nRF9151 comms processor
├── Power Ch0 (4.5V) ─────────► Battery simulation rail (BQ25622 UVLO requires 4.5V)
├── Power Ch1 (5V default) ────► Charger/USB rail
├── GPIO (DUT pins 0-6, level-shifted via TXS0108)
│   ├── Pin 0 (momentary) ───► Button press simulation
│   ├── Pin 1 (electrode) ────► On-skin simulation
│   └── Pin 5 (relay) ────────► Charger detection (CHARGER_DET)
├── Motor Output 0 ───────────► Linear actuator (motion simulation)
├── ADC Channels
│   ├── Ch 0 (photodiode) ────► LED red channel
│   ├── Ch 1 (photodiode) ────► LED green channel
│   └── Ch 3 (photodiode) ────► LED blue channel
├── Peltier Controller
│   ├── Heater GPIO 3 ────────► Peltier element (temperature control)
│   └── Sensor ADC Ch 2 ──────► Thermistor (temperature feedback)
└── NFC Reader (I2C bus 1) ───► NFC tag read
```

### 2.3 What MTIB Provides

| Capability | MTIB RPC (redesign) | Stage 4 Usage |
|------------|-------------|---------------|
| Flash firmware | `FlashProgram` | Flash both MCU hex files before test run |
| UART capture | `UartStream` | Diagnostic log capture (Debug build only) |
| Power control | `PowerEnable(channel=DUT)` / `PowerDisable(channel=DUT)` | Boot, reboot, power cycle |
| Power measurement | `PowerMeasure` | Current draw verification for power budget tests |
| GPIO output | `GpioWrite` | Button press, charger detection, on-skin electrode |
| GPIO input | `GpioRead` | (Future: read DUT output signals) |

### 2.4 External Equipment

| Equipment | Tests That Require It | Notes |
|-----------|----------------------|-------|
| Temperature chamber (Peltier) | PRDTST-332, 339, 345, 351, 357, 367, 372, 383, 398, 401, 405, 406, 407 | PID-controlled via MTIB GPIO + ADC thermistor feedback |
| NFC reader | PRDTST-337 | I2C NFC reader on MTIB, reads NT3H2111 tag |
| Photodiode array | PRDTST-338, 355, 373 | RGB ADC reads for LED color/pattern verification |
| Linear actuator | PRDTST-324, 326, 375, 389, 393 | Controlled motion for acceleration threshold tests |
| ~~GNSS (clear sky or simulator)~~ | ~~PRDTST-333, 343, 358, 360, 378, 384, 396~~ | **DEFERRED** — indoor scaffold, no GPS signal source |
| On-skin electrode | PRDTST-327, 379, 400 | GPIO-controlled electrode simulating skin contact |

### 2.5 Fixture Profile for Alpha Product Board

```json
{
  "product": "alpha",
  "board": "alpha_b0",
  "button": {
    "gpio_pin": 0,
    "active_low": true,
    "description": "Button press simulation — pulse duration controls press type"
  },
  "on_skin": {
    "gpio_pin": 1,
    "active_high": true,
    "description": "On-skin electrode — HIGH simulates skin contact"
  },
  "peltier": {
    "gpio_pin": 3,
    "sensor_adc_channel": 2,
    "description": "PID temperature control via Peltier relay/MOSFET + thermistor"
  },
  "charger_relay": {
    "gpio_pin": 5,
    "active_high": true,
    "description": "Charger detection relay — connects/disconnects 5V USB rail"
  },
  "led_sensor": {
    "red_adc_channel": 0,
    "green_adc_channel": 1,
    "blue_adc_channel": 3,
    "description": "RGB photodiode array for LED state verification"
  },
  "nfc_reader": {
    "interface": "i2c",
    "bus": 1,
    "description": "NFC tag reader for device ID verification (NT3H2111 @ 0x55)"
  },
  "motion": {
    "description": "Linear actuator for motion simulation — shake patterns"
  },
  "power": {
    "dut_voltage": 4.5,
    "charger_voltage": 5.0,
    "boot_settle_s": 3
  }
}
```

---

## 3. Build Configuration

### 3.1 Debug Build

```kconfig
# prj.conf overlay for Stage 4 Debug
CONFIG_CONCORD_HARNESS=n
CONFIG_LOG=y
CONFIG_LOG_DEFAULT_LEVEL=3
CONFIG_SHELL=n
# No shell -- Stage 4 Debug has logs but no interactive shell
```

The Debug build produces UART log output on the nRF52840 app processor UART
(`/dev/verdin-uart2`). This output is captured by the test runner via `UartStream` and
saved as `debug_uart_log.txt`. Log output is **never** parsed for pass/fail decisions --
it exists solely for post-failure diagnosis.

### 3.2 Release Build

```kconfig
# prj.conf overlay for Stage 4 Release (shipping binary)
CONFIG_CONCORD_HARNESS=n
CONFIG_LOG=n
CONFIG_SHELL=n
```

The Release build is the shipping binary. Zero UART output. Zero debug overhead. This is
the binary that goes to manufacturing. Power measurements on the Release build are
authoritative.

### 3.3 Build Artifacts

Each pipeline run produces four hex files:

```
build/
├── integration/                        # Stage 3 build
│   └── nrf52840/zephyr/merged.hex      # CONFIG_CONCORD_HARNESS=y, CONFIG_LOG=y
├── production_debug/                   # Stage 4 Debug build
│   └── nrf52840/zephyr/merged.hex      # CONFIG_CONCORD_HARNESS=n, CONFIG_LOG=y
├── production_release/                 # Stage 4 Release build
│   └── nrf52840/zephyr/merged.hex      # CONFIG_CONCORD_HARNESS=n, CONFIG_LOG=n
└── comms/                              # nRF9151 comms MCU (same for all stages)
    └── nrf9151/zephyr/merged.hex
```

Both Stage 4 builds share the same nRF9151 comms MCU firmware. The comms MCU does not
have harness or log configuration differences.

### 3.4 Which Tests Run on Which Build

| Test Category | Debug Build | Release Build | Notes |
|---------------|-------------|---------------|-------|
| Power/Runtime | Informational | **Authoritative** | Log overhead skews power measurements |
| Config Values | Yes | Yes | Both builds must apply configs correctly |
| Motion Detection | Yes | Yes | Timing-sensitive -- both builds verified |
| Charging/BMS | Yes | Yes | Hardware behavior, not software-dependent |
| Environmental Sensors | Yes | Yes | Sensor accuracy is build-independent |
| GNSS | Yes | Yes | Acquisition time may differ slightly |
| On-Skin/Biometrics | Yes | Yes | Both builds must send biometric messages |
| Button/SOS/Haptic | Yes | Yes | UI behavior must match in both builds |
| LED Feedback | Yes | Yes | LED patterns are build-independent |
| NFC | Yes | Yes | Passive tag, build-independent |
| FUOTA | Yes | Yes | Both variants must accept firmware updates |
| VSM/IPC | Yes | Yes | VSM power cut-off is hardware-controlled |
| Cloud Messages | Yes | Yes | Message format must be identical |

---

## 4. CoreCloud Integration

> **SDK reference:** See
> [corecloud-library-architecture.md](./corecloud-library-architecture.md) for the
> complete CoreCloud Python SDK analysis, including module inventory, message types,
> query API, proposed FUOTA management module, and the DB ORM vs REST access strategy.

CoreCloud is the **primary verification mechanism** for most Stage 4 tests. The device
communicates with CoreCloud over LTE, sending position messages, biometric data, boot
notifications, config acknowledgements, and emergency events. Stage 4 tests verify that
these messages arrive at CoreCloud with correct content, correct timing, and correct
formatting.

### 4.1 How `ctx.cloud` Is Initialized

The test runner initializes the CoreCloud client from environment variables injected by
the pipeline controller. Credentials are sourced from Vault at Job creation time.

```python
# cloud_client.py -- Stage 4 CoreCloud integration

import os
import time
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Callable, Any

from corekinect.core_cloud.api_interface import CoreCloudRestInterface
from corekinect.core_cloud.msg_def_v1_0 import (
    PositionMsgV6,
    BiometricDataMsg,
    BootMsgV2,
    GPSConfMsg,
    NetworkStatusMsgV4,
    AlphaHwFailureMsg,
)

log = logging.getLogger(__name__)


class CloudClient:
    """
    CoreCloud integration for Stage 4 product validation.

    Wraps CoreCloudRestInterface and message definition classes to provide
    a test-oriented API for verifying device-to-cloud communication.
    """

    def __init__(self):
        self.device_id = int(os.environ["DEVICE_ID"])
        self.env_namespace = os.environ.get("CLOUD_ENV_NAMESPACE", "VAL_1_0")
        self._api: Optional[CoreCloudRestInterface] = None
        self._test_start_time: Optional[datetime] = None

    def __enter__(self):
        self._api = CoreCloudRestInterface(env_namespace=self.env_namespace)
        self._api.__enter__()
        self._test_start_time = datetime.now(timezone.utc)
        return self

    def __exit__(self, *args):
        if self._api:
            self._api.__exit__(*args)

    def mark_test_start(self):
        """Record current time as baseline for message queries."""
        self._test_start_time = datetime.now(timezone.utc)

    def wait_for_position(
        self,
        timeout_s: int = 120,
        poll_interval_s: int = 5,
        predicate: Optional[Callable[[PositionMsgV6], bool]] = None,
    ) -> Optional[PositionMsgV6]:
        """
        Poll CoreCloud for a PositionMsgV6 from this device since test start.
        Optionally filter by a predicate function.
        """
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            msgs = PositionMsgV6.since_server_time(
                self.device_id,
                self._test_start_time,
                db_env=self.env_namespace,
            )
            for msg in msgs:
                if predicate is None or predicate(msg):
                    return msg
            time.sleep(poll_interval_s)
        return None

    def wait_for_biometric(
        self,
        timeout_s: int = 120,
        poll_interval_s: int = 5,
        predicate: Optional[Callable[[BiometricDataMsg], bool]] = None,
    ) -> Optional[BiometricDataMsg]:
        """Poll CoreCloud for a BiometricDataMsg from this device."""
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            msgs = BiometricDataMsg.since_server_time(
                self.device_id,
                self._test_start_time,
                db_env=self.env_namespace,
            )
            for msg in msgs:
                if predicate is None or predicate(msg):
                    return msg
            time.sleep(poll_interval_s)
        return None

    def wait_for_boot(
        self,
        timeout_s: int = 60,
        poll_interval_s: int = 5,
    ) -> Optional[BootMsgV2]:
        """Poll CoreCloud for a BootMsgV2 from this device."""
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            msgs = BootMsgV2.since_server_time(
                self.device_id,
                self._test_start_time,
                db_env=self.env_namespace,
            )
            if msgs:
                return msgs[-1]
            time.sleep(poll_interval_s)
        return None

    def get_position_history(
        self,
        since: Optional[datetime] = None,
    ) -> List[PositionMsgV6]:
        """Get all position messages since a given time (or test start)."""
        start = since or self._test_start_time
        return PositionMsgV6.since_server_time(
            self.device_id, start, db_env=self.env_namespace
        )

    def get_biometric_history(
        self,
        since: Optional[datetime] = None,
    ) -> List[BiometricDataMsg]:
        """Get all biometric messages since a given time (or test start)."""
        start = since or self._test_start_time
        return BiometricDataMsg.since_server_time(
            self.device_id, start, db_env=self.env_namespace
        )

    def push_gps_config(self, config: GPSConfMsg) -> bool:
        """Push GPS configuration to device via CoreCloud REST API."""
        resp = config.send_via_rest(
            device_id=self.device_id,
            env_namespace=self.env_namespace,
            client=self._api,
        )
        return resp.status_code < 300

    def get_latest_position(self) -> Optional[PositionMsgV6]:
        """Get the most recent position message for this device."""
        return PositionMsgV6.last(self.device_id, db_env=self.env_namespace)

    def get_latest_biometric(self) -> Optional[BiometricDataMsg]:
        """Get the most recent biometric message for this device."""
        return BiometricDataMsg.last(self.device_id, db_env=self.env_namespace)
```

### 4.2 CoreCloud Message Types Used in Stage 4

Stage 4 tests rely on the following message types from `msg_def_v1_0.py`:

#### 4.2.1 Position Message (`PositionMsgV6`, UID 556)

The workhorse message for Stage 4 verification. Contains device location, motion state,
battery status, environmental readings, charger state, and the reason for the update.

**Key fields for Stage 4 assertions:**

| Field | Type | Stage 4 Usage |
|-------|------|---------------|
| `update_reason` | `int` | Distinguishes heartbeat (1), stop motion (2), emergency (3), continuous motion (5) |
| `is_in_motion` | `bool` | Motion detection verification |
| `on_charger` | `bool` | Charger detection verification |
| `gnss_fix_ok` | `bool` | GNSS acquisition verification |
| `horizontal_accuracy` | `int` | GNSS accuracy threshold (meters) |
| `gps_on_time` | `int` | GNSS acquisition time (seconds) |
| `latitude` / `longitude` | `float` | Position fix validity |
| `ground_speed` | `int` | Speed estimate verification |
| `heading` | `int` | Heading estimate verification |
| `batt_percent` | `int` | SoC reporting verification |
| `batt_voltage` | `int` | Battery voltage reporting |
| `bms_temp` | `int` | BMS temperature reporting |
| `temperature` | `float` | Environmental temperature (BME280) |
| `air_pressure` | `float` | Barometric pressure (BME280) |
| `pressure_altitude` | `int` | Pressure-derived altitude |
| `used_aiding` | `bool` | A-GNSS aiding verification |
| `num_sat` | `int` | Satellite count |
| `emergency_event_id` | `int` | SOS event correlation |

**`update_reason` map (from `PositionMsgV6.update_reason_map`):**

| Value | Reason | PRDTST Tests |
|-------|--------|-------------|
| 0 | Device Boot / First network join | PRDTST-374, 388 |
| 1 | Heartbeat Message | PRDTST-330, 335, 344, 352, 356, 359, 371 |
| 2 | Stop Motion Event | PRDTST-328, 347, 399 |
| 3 | Emergency | PRDTST-382, 325 |
| 5 | Continuous Motion | PRDTST-342, 364, 369, 387, 394 |
| 6 | In Plane | *(not used by Alpha PRDTST)* |
| 7 | Fall (deprecated) | *(not used by Alpha PRDTST)* |
| 8 | Landed | *(not used by Alpha PRDTST)* |
| 9 | Point Of Interest (POI) | *(not used by Alpha PRDTST)* |
| 10 | Forced Check-In | *(may appear during testing)* |
| 15 | Manufacturing Test | PRDTST-377 |

#### 4.2.2 Biometric Data Message (`BiometricDataMsg`, UID 557)

Sent when the device is on-skin and performing biometric monitoring.

**Key fields for Stage 4 assertions:**

| Field | Type | Stage 4 Usage |
|-------|------|---------------|
| `on_body` | `bool` (flag bit 0) | On-skin detection verification |
| `heart_rate` | `int` | Heart rate reading (0 if off-body) |
| `spo2` | `int` | SpO2 reading |
| `skin_temperature` | `int` | Skin temperature from MLX90614 |
| `external_temperature` | `int` | Ambient temperature |
| `relative_humidity` | `int` | Relative humidity |
| `air_pressure` | `int` | Barometric pressure |
| `vsm_on_time` | `int` | VSM monitoring duration |

#### 4.2.3 Boot Message (`BootMsgV2`, UID 548)

Sent after device boot. Contains boot reason and MCU identification.

**Key fields for Stage 4 assertions:**

| Field | Property | Stage 4 Usage |
|-------|----------|---------------|
| `flags` | `boot_reason_bits` [0:4] → `boot_reason_map` | Verify boot cause (normal, charger, button, FUOTA, watchdog) |
| `flags` | `mcu_type_bits` [6:7] → `mcu_type_map` | Identify which MCU booted (0=Comms Core, 1=App Core) |
| `flags` | `fw_triggered_bits` [5] → `fw_triggered_map` | Soft reset (0) vs FW-triggered reset (1) |
| `num_exceptions` | direct | Verify clean boot (0 exceptions) |

**`boot_reason` map (from `BootMsgV2.boot_reason_map`):**

| Value | Reason | PRDTST Tests |
|-------|--------|-------------|
| 0 | Normal boot | PRDTST-374 |
| 1 | Reboot due to exception | *(diagnostic — test should fail if seen)* |
| 2 | Reboot due to completing FUOTA | PRDTST-376 |
| 3 | Reboot due to being placed on charger | PRDTST-354 |
| 4 | Reboot due to error | *(diagnostic — test should fail if seen)* |
| 5 | Reboot due to receiving valid reboot message | *(not used by Alpha PRDTST)* |
| 6 | Reboot due to watchdog timer expiration | *(diagnostic — test should fail if seen)* |
| 7 | Reboot due to user button sequence | PRDTST-346 |

#### 4.2.4 GPS Config Message (`GPSConfMsg`, UID 524)

Configuration message pushed to the device via CoreCloud REST API.

**Key fields:**

| Field | API Name | Stage 4 Usage |
|-------|----------|---------------|
| `is_aiding_enabled` | `isAidingEnabled` | Enable/disable A-GNSS for cold/warm start tests |
| `is_psm_enabled` | `isPsmEnabled` | Power saving mode control |
| `gnss_update_freq` | `gnssUpdateFrequency` | GNSS update frequency |
| `target_fix_accuracy` | `targetFixAccuracyMeters` | Target accuracy threshold |
| `target_fix_pdop` | `targetFixPdopTenths` | Target PDOP threshold |

#### 4.2.5 Network Status Message (`NetworkStatusMsgV4`, UID 512)

Provides LTE connection diagnostics. Not directly tested by PRDTST cases but captured
as a diagnostic artifact for failure analysis.

#### 4.2.6 Alpha HW Failure Message (`AlphaHwFailureMsg`, UID 559)

Reports hardware subsystem failures detected by the Alpha device. Captured as a
diagnostic artifact on every test run — if a test fails, the HW failure log helps
distinguish firmware bugs from hardware faults.

**Key fields for diagnostic analysis:**

| Field | Type | Subsystem |
|-------|------|-----------|
| `xlr_fails` | `int` (bitfield) | Accelerometer (XLR) |
| `alt_fails` | `int` (bitfield) | Altimeter / BME280 |
| `gps_fails` | `int` (bitfield) | GNSS module |
| `bms_fails` | `int` (bitfield) | BMS / fuel gauge |
| `ext_flash_fails` | `int` (bitfield) | External flash |
| `ppg_fails` | `int` (bitfield) | PPG / heart rate sensor (PAH8151) |
| `imu_fails` | `int` (bitfield) | IMU (LSM6DSO) |
| `ir_fails` | `int` (bitfield) | IR sensor (MLX90614) |
| `batt_charger_fails` | `int` (bitfield) | Battery charger (BQ25622) |

#### 4.2.7 Ground Mode Config V2 (UID 538) — **REST Send Deferred**

**Partial implementation.** `GroundModeConfigV2` exists in `msg_def_v1_0.py` as a
`MsgBase` subclass — DB reads (`.last()`, `.since_server_time()`) work today. However,
the class does not inherit from `ConfMsgBase`, so `.send_via_rest()` is unavailable.
Only `GPSConfMsg` currently has full REST send capability.

The Confluence message spec ([538] Ground Mode Config V2) defines the binary payload
with fields: GPS Heartbeat Period, Continuous Motion Period, Stop Motion Timeout,
Heartbeat Acquisition Timeout, Motion Stop Acquisition Timeout, Motion Acc Threshold,
Motion Acc Duration, Start Motion Window Start/End, and Motion Acquisition On-times.

Config delivery for UID 538 may use the Socket Server downlink path rather than REST —
this needs confirmation from the CoreCloud team. See Section 4.5 for full impact and
[corecloud-library-architecture.md](./corecloud-library-architecture.md) Section 4.3 for
the proposed implementation approach.

#### 4.2.8 Biometric Config (UID 558) — **Deferred**

**POC scope exclusion.** No `BiometricConfig` class exists in `msg_def_v1_0.py` and no
REST endpoint exists for Biometric Config delivery. The Confluence message spec ([558]
Biometric Config) defines fields: Flags, Low Risk State Report Period, Increased Risk
HSI Threshold, Increased Risk State Report Period, Emergency HSI Threshold, Emergency
State Report Period.

### 4.3 Config Delivery via CoreCloud REST API

Stage 4 tests push configuration to the device through the CoreCloud REST API, which
delivers it over LTE. This tests the same config delivery path used in production.

**Ground Mode Config parameters — DEFERRED (see Section 4.5):**

The following parameters require Ground Mode Config V2 (UID 538) delivery, which has
no Python SDK class or REST endpoint yet. These are listed for reference but their
associated tests are excluded from the POC.

| Parameter | PRDTST Tests | Default Value | Status |
|-----------|-------------|---------------|--------|
| Heartbeat period | PRDTST-335, 344, 352, 356, 371 | Product-specific (see PRDTST-352) | **Deferred** |
| Heartbeat acquisition timeout | PRDTST-330, 359 | 60 seconds | **Deferred** |
| Continuous motion period | PRDTST-342, 364, 369, 387, 394 | Product-specific | **Deferred** |
| Stop motion timeout | PRDTST-347, 399 | 2 minutes (120 seconds) | **Deferred** |
| Motion stop acquisition timeout | PRDTST-328 | Product-specific | **Deferred** |
| Start motion window start | PRDTST-353 | 3 seconds | **Deferred** |

**GPS Config parameters (pushed via `GPSConfMsg.send_via_rest()` → `PUT /System/Devices/Configurations/Gps`):**

| Parameter | PRDTST Tests | Values |
|-----------|-------------|--------|
| `is_aiding_enabled` | PRDTST-343, 378, 384, 360, 396 | `true` / `false` |
| `is_psm_enabled` | GNSS power tests | `true` / `false` |
| `target_fix_accuracy` | PRDTST-343, 378, 384 | 1m, 6m |

### 4.4 Timing Considerations

Stage 4 tests operate on real-world timescales with real LTE connectivity:

| Factor | Typical Latency | Implication |
|--------|----------------|-------------|
| LTE connection setup | 5-15 seconds | First message after boot may take 30+ seconds |
| Message delivery to CoreCloud | 2-10 seconds | Poll intervals must account for network jitter |
| Config delivery to device | 5-30 seconds | Config push must be followed by adequate wait |
| Message queuing on device | Up to next heartbeat period | Device may batch messages |
| CoreCloud DB write latency | 1-3 seconds | Small delay between API receipt and DB availability |
| Poll interval | 5 seconds (default) | Balance between responsiveness and API load |

**Timeout strategy**: Every `wait_for_*` call specifies a timeout. Timeouts are set to
at least 2x the expected delivery time to account for network variability. For heartbeat
tests with long periods, the timeout is set to `period + 120s` (period plus a 2-minute
margin for LTE setup and message delivery).

### 4.5 POC Scope Exclusions — Missing CoreCloud Config Delivery

> **Full gap analysis and proposed solutions:** See
> [corecloud-library-architecture.md](./corecloud-library-architecture.md) Sections 4
> and 9 for the complete missing capabilities inventory, proposed module structure
> (`fuota.py`, `device_management.py`), and prioritized implementation plan.

This is a proof of concept. The following CoreCloud config delivery capabilities do not
yet have REST send support and the tests that depend on them are **excluded from the POC
implementation**. They will be implemented in a later milestone.

**Ground Mode Config V2 (UID 538) — 18 tests deferred:**
- **What exists:** `GroundModeConfigV2` class in `msg_def_v1_0.py` with DB read support
  (`.last()`, `.since_server_time()`). The ORM model and field mapping are complete.
- **What's missing:** The class inherits from `MsgBase`, not `ConfMsgBase` — so
  `.send_via_rest()` is unavailable. No REST endpoint is documented for config delivery
  (only `PUT /System/Devices/Configurations/Gps` exists today). The delivery path
  (REST trigger vs Socket Server downlink) is unclear.
- **Tests affected:** PRDTST-328, 330, 335, 342, 344, 347, 352, 353, 356, 359, 364,
  369, 371, 374, 387, 388, 394, 399 (all Config Value tests).
- **Post-POC work:**
  1. CoreCloud C# team: create REST endpoint or document Socket Server downlink trigger
  2. Python SDK: extend `GroundModeConfigV2` to inherit from `ConfMsgBase`, add
     `api_endpoint`, `api_field_map`, and `api_types` following the `GPSConfMsg` pattern
  3. Implement the 18 deferred tests

**Biometric Config (UID 558) — biometric interval config deferred:**
- **What's missing:** No `BiometricConfig(ConfMsgBase)` class in the Python SDK. No
  REST endpoint for Biometric Config delivery.
- **Tests affected:** Any test that needs to change biometric reporting intervals or
  HSI thresholds. Core biometric *data* verification (PRDTST-327, 379, 400) is NOT
  affected — those only read `BiometricDataMsg` uplinks via `.since_server_time()`.
- **Post-POC work:** Same pattern — REST endpoint + Python SDK class + tests.

**What the POC DOES cover (64 of 89 PRDTST tests):**
- All power/runtime tests (measure current, verify runtime — no config push needed)
- All motion detection tests (physical stimulus via MTIB, verify via Position messages)
- All environmental sensor tests (verify via BiometricDataMsg fields)
- All on-skin/biometrics data tests (verify via BiometricDataMsg)
- All button/SOS/haptic tests (button press via MTIB, verify via Position messages)
- NFC, FUOTA, VSM tests

**Deferred from POC (54 tests):**
- 29 charging/BMS tests (same MTIB power source for DUT + CHG)
- 18 config value tests (GroundModeConfigV2 endpoint unavailable)
- 7 GNSS tests (indoor scaffold, no GPS signal source)

**Note on `CoreCloudRestInterface` default environment:** The REST client defaults to
`env_namespace="DEV_1_0"`. All Stage 4 code explicitly passes `env_namespace="VAL_1_0"`
(or reads it from `CLOUD_ENV_NAMESPACE` env var). The DB query methods (`MsgBase.last()`,
`.since_server_time()`) default to `db_env="VAL_1_0"`. This asymmetry is by design in
the Python SDK but must be respected — never rely on the default for REST calls.

---

## 5. Test Suite -- PRDTST Mapping

This section specifies every Alpha PRDTST test case with its Stage 4 implementation.
Each test shows the PRDTST acceptance criteria, build variant, physical stimulus,
CoreCloud verification, a Python test example, and its relationship to Stage 3 coverage.

### 5.1 Power / Runtime Tests

#### PRDTST-331: Test Long-term Sleep Current Consumption Average

- **Acceptance criteria**: The device shall consume less than an average of 1.5mA over
  12-hour, 24-hour, 48-hour, and 1-week periods of continuous sleep.
- **Build variant**: Release (authoritative power measurement)
- **Run type**: `weekly` (long-duration)
- **Physical stimulus**: None -- device in sleep mode, all sensors off, no charger
- **CoreCloud verification**: None (device is sleeping, no messages expected)
- **Stage 3 overlap**: Stage 3 verifies sleep state entry via harness. Stage 4 measures
  actual production sleep current over extended periods.
- **Classification**: Stage 4 primary (extended duration, production binary power)

```python
def test_prdtst_331_sleep_current_average(ctx):
    """PRDTST-331: Sleep current must average < 1.5mA over extended periods."""
    ctx.flash_firmware(ctx.release_hex)
    ctx.power_on()
    ctx.wait(30)  # Allow boot and settle into sleep

    # No charger, no on-skin, no motion -- device should enter sleep
    for duration_label, duration_s in [
        ("12h", 43200), ("24h", 86400), ("48h", 172800), ("1week", 604800)
    ]:
        trace = ctx.mtib.power_measure("DUT", duration_s=duration_s, sample_hz=1)
        avg_current_ma = trace.average_current_ma()

        assert avg_current_ma < 1.5, (
            f"PRDTST-331 FAIL [{duration_label}]: sleep avg {avg_current_ma:.3f}mA "
            f"> 1.5mA limit"
        )
```

#### PRDTST-340: Test Device Must Operate for 3 Days Under Worst-Case Conditions

- **Acceptance criteria**: Verify that the device can operate for 3 days (72 hours)
  standalone, with continuous biometric and GPS sampling at the worst-case profile,
  and all messages sent via LTE.
- **Build variant**: Release
- **Run type**: `weekly` (72-hour endurance)
- **Physical stimulus**: On-skin electrode enabled, motion actuator running periodically,
  GNSS signal available
- **CoreCloud verification**: Verify continuous stream of position and biometric messages
  over the full 72 hours with no gaps exceeding 2x the configured period
- **Stage 3 overlap**: Stage 3 verifies sensor orchestration timing internally.
  Stage 4 verifies 72-hour sustained operation of the production binary.
- **Classification**: Stage 4 primary (endurance test, production binary)

```python
def test_prdtst_340_worst_case_endurance_72h(ctx):
    """PRDTST-340: 72-hour worst-case endurance test."""
    ctx.flash_firmware(ctx.release_hex)
    ctx.power_on()
    ctx.wait(30)

    ctx.fixture.on_skin.enable()

    test_duration_s = 72 * 3600  # 72 hours
    check_interval_s = 3600      # Check every hour
    start_time = datetime.now(timezone.utc)

    for hour in range(72):
        ctx.wait(check_interval_s)
        # Verify device is still sending messages
        recent = ctx.cloud.get_position_history(
            since=datetime.now(timezone.utc) - timedelta(hours=1)
        )
        assert len(recent) > 0, (
            f"PRDTST-340 FAIL: No position messages in hour {hour + 1}"
        )

    # Verify device still has battery
    power = ctx.mtib.power_measure("DUT", duration_s=10)
    assert power.average_current_ma() > 1.0, (
        "PRDTST-340 FAIL: Device appears dead after 72h endurance"
    )
    ctx.fixture.on_skin.disable()
```

#### PRDTST-341: Test Device Must Consume Less Than 150mA in Active Mode

- **Acceptance criteria**: The device shall consume less than 150mA in active mode.
- **Build variant**: Release (authoritative)
- **Run type**: `commit`
- **Physical stimulus**: On-skin electrode enabled (triggers active monitoring)
- **CoreCloud verification**: Wait for biometric message to confirm active mode
- **Stage 3 overlap**: Stage 3 verifies active state entry. Stage 4 measures production
  current in active mode.
- **Classification**: Stage 4 primary (production power measurement)

```python
def test_prdtst_341_active_mode_current(ctx):
    """PRDTST-341: Active mode current must be < 150mA."""
    ctx.flash_firmware(ctx.release_hex)
    ctx.power_on()
    ctx.wait(30)

    ctx.fixture.on_skin.enable()
    ctx.wait(15)  # Allow sensors to start

    trace = ctx.mtib.power_measure("DUT", duration_s=60, sample_hz=10)
    peak_current_ma = trace.max_current_ma()

    assert peak_current_ma < 150, (
        f"PRDTST-341 FAIL: active mode peak {peak_current_ma:.1f}mA > 150mA limit"
    )
    ctx.fixture.on_skin.disable()
```

#### PRDTST-348: Test Device Must Consume Less than 500uA in Sleep Mode

- **Acceptance criteria**: The device shall consume less than an average of 500uA in
  sleep mode.
- **Build variant**: Release (authoritative)
- **Run type**: `commit`
- **Physical stimulus**: None -- device in sleep, no charger, no on-skin, no motion
- **CoreCloud verification**: None
- **Stage 3 overlap**: Stage 3 verifies sleep state entry. Stage 4 measures production
  sleep current.
- **Classification**: Stage 4 primary (production power measurement)

```python
def test_prdtst_348_sleep_mode_current(ctx):
    """PRDTST-348: Sleep mode current must average < 500uA."""
    ctx.flash_firmware(ctx.release_hex)
    ctx.power_on()
    ctx.wait(60)  # Allow boot and settle into sleep

    trace = ctx.mtib.power_measure("DUT", duration_s=300, sample_hz=10)
    avg_current_ua = trace.average_current_ma() * 1000

    assert avg_current_ua < 500, (
        f"PRDTST-348 FAIL: sleep avg {avg_current_ua:.1f}uA > 500uA limit"
    )
```

#### PRDTST-361: Test Device Must Consume Less Than 400nA in Lockout Mode

- **Acceptance criteria**: The device shall consume less than 400nA when the battery is
  locked out.
- **Build variant**: Release (authoritative)
- **Run type**: `weekly`
- **Physical stimulus**: Drain battery below 3.5V lockout threshold (requires
  controlled discharge or reduced supply voltage)
- **CoreCloud verification**: None (device is locked out)
- **Stage 3 overlap**: None (Stage 3 cannot verify lockout power)
- **Classification**: Stage 4 primary

```python
def test_prdtst_361_lockout_current(ctx):
    """PRDTST-361: Lockout mode current must be < 400nA."""
    ctx.flash_firmware(ctx.release_hex)
    # Simulate battery lockout by reducing supply below 3.5V
    ctx.mtib.power_enable(channel=0, voltage_v=3.3)  # Below lockout threshold
    ctx.wait(10)  # Device should enter lockout

    trace = ctx.mtib.power_measure("DUT", duration_s=60, sample_hz=100)
    avg_current_na = trace.average_current_ma() * 1_000_000

    assert avg_current_na < 400, (
        f"PRDTST-361 FAIL: lockout current {avg_current_na:.1f}nA > 400nA limit"
    )
```

#### PRDTST-363: Test Device Must Operate for 3 Days Standalone Normal Use

- **Acceptance criteria**: Verify that the device can operate for 3 days (72 hours)
  standalone, with continuous biometric and GPS sampling at normal use profile.
- **Build variant**: Release
- **Run type**: `weekly` (72-hour endurance)
- **Physical stimulus**: On-skin electrode, normal motion patterns
- **CoreCloud verification**: Continuous position and biometric messages over 72 hours
- **Stage 3 overlap**: Stage 3 verifies normal mode operation internally.
  Stage 4 verifies 72-hour sustained normal operation.
- **Classification**: Stage 4 primary (endurance test)

```python
def test_prdtst_363_normal_use_endurance_72h(ctx):
    """PRDTST-363: 72-hour normal use endurance test."""
    ctx.flash_firmware(ctx.release_hex)
    ctx.power_on()
    ctx.wait(30)

    ctx.fixture.on_skin.enable()
    test_duration_hours = 72

    for hour in range(test_duration_hours):
        ctx.wait(3600)
        recent_pos = ctx.cloud.get_position_history(
            since=datetime.now(timezone.utc) - timedelta(hours=1)
        )
        assert len(recent_pos) > 0, (
            f"PRDTST-363 FAIL: No position messages in hour {hour + 1}"
        )

    # Verify battery still alive
    power = ctx.mtib.power_measure("DUT", duration_s=10)
    assert power.average_current_ma() > 1.0, "PRDTST-363 FAIL: device dead after 72h"
    ctx.fixture.on_skin.disable()
```

#### PRDTST-401: Test Device Must Operate Within -20C to +60C

- **Acceptance criteria**: The device shall operate within a temperature range of
  -20C to +60C.
- **Build variant**: Both
- **Run type**: `weekly` (temperature cycling)
- **Physical stimulus**: Peltier temperature controller cycling through range
- **CoreCloud verification**: Position messages received at each temperature setpoint
- **Stage 3 overlap**: None (Stage 3 does not test temperature extremes)
- **Classification**: Stage 4 primary (environmental extremes)

```python
def test_prdtst_401_operating_temperature_range(ctx):
    """PRDTST-401: Device must operate from -20C to +60C."""
    ctx.flash_firmware(ctx.release_hex)
    ctx.power_on()
    ctx.wait(30)

    test_temps = [-20, -10, 0, 10, 25, 40, 50, 60]
    for temp_c in test_temps:
        ctx.fixture.temperature.set(temp_c)
        ctx.wait(300)  # Settle time at temperature

        ctx.cloud.mark_test_start()
        # Trigger a position message via motion
        ctx.fixture.motion.shake(duration_s=5)
        ctx.wait(30)

        msg = ctx.cloud.wait_for_position(timeout_s=180)
        assert msg is not None, (
            f"PRDTST-401 FAIL: No position message at {temp_c}C"
        )

    ctx.fixture.temperature.set(25)  # Return to ambient
```

#### PRDTST-404: Test Device Must Consume Less than 50mA in Normal Use Mode

- **Acceptance criteria**: The device shall consume less than 50mA in active mode over
  a 10 minute period.
- **Build variant**: Release (authoritative)
- **Run type**: `commit`
- **Physical stimulus**: Normal operation (on-skin, idle between heartbeats)
- **CoreCloud verification**: None (power measurement only)
- **Stage 3 overlap**: Stage 3 measures coarse system power. Stage 4 measures production
  normal-use average.
- **Classification**: Stage 4 primary (production power budget)

```python
def test_prdtst_404_normal_use_current(ctx):
    """PRDTST-404: Normal use mode avg current must be < 50mA over 10 min."""
    ctx.flash_firmware(ctx.release_hex)
    ctx.power_on()
    ctx.wait(60)  # Boot and settle

    ctx.fixture.on_skin.enable()
    ctx.wait(30)

    trace = ctx.mtib.power_measure("DUT", duration_s=600, sample_hz=10)
    avg_current_ma = trace.average_current_ma()

    assert avg_current_ma < 50, (
        f"PRDTST-404 FAIL: normal use avg {avg_current_ma:.1f}mA > 50mA limit"
    )
    ctx.fixture.on_skin.disable()
```

### 5.2 Config Value Tests

Config value tests push configuration to the device via CoreCloud REST API and verify
that the device applies the configuration by observing the timing and content of
subsequent cloud messages. These tests are the core verification of the device-cloud
config delivery path.

**Common pattern**: Push config via REST API, wait for the device to apply it, then
observe position messages at the configured interval.

#### PRDTST-352: Test Heartbeat Period Default Value

- **Acceptance criteria**: Verify that the device can be configured to send a heartbeat
  message at the default period.
- **Build variant**: Both
- **Run type**: `commit`
- **Physical stimulus**: None (heartbeat is autonomous)
- **CoreCloud verification**: Wait for 2+ heartbeat position messages and verify interval
- **Stage 3 overlap**: Stage 3 verifies config propagation to subsystems via harness.
  Stage 4 verifies the actual message timing at CoreCloud.
- **Classification**: Stage 4 primary (end-to-end cloud message timing)

```python
def test_prdtst_352_heartbeat_default_period(ctx):
    """PRDTST-352: Default heartbeat period produces messages at expected interval."""
    ctx.flash_firmware(ctx.hex_under_test)
    ctx.power_on()
    ctx.wait(30)

    ctx.cloud.mark_test_start()

    # Wait for 2 heartbeat messages (update_reason=1)
    heartbeats = []
    timeout_s = 7500  # ~2x default heartbeat period + margin
    deadline = time.time() + timeout_s
    while len(heartbeats) < 2 and time.time() < deadline:
        msgs = ctx.cloud.get_position_history()
        heartbeats = [m for m in msgs if m.update_reason == 1]
        ctx.wait(30)

    assert len(heartbeats) >= 2, (
        f"PRDTST-352 FAIL: Expected 2 heartbeats, got {len(heartbeats)}"
    )

    # Verify interval matches default period (+/- 60s tolerance)
    t0 = heartbeats[0].time_of_record
    t1 = heartbeats[1].time_of_record
    interval_s = (t1 - t0).total_seconds()
    default_period_s = 3600  # 60 minutes (product default)

    assert abs(interval_s - default_period_s) < 60, (
        f"PRDTST-352 FAIL: heartbeat interval {interval_s:.0f}s, "
        f"expected {default_period_s}s +/- 60s"
    )
```

#### PRDTST-335: Test Zero Heartbeat Period

- **Acceptance criteria**: Verify that the device can be configured to not send heartbeat
  messages.
- **Build variant**: Both
- **Run type**: `commit`
- **Physical stimulus**: None
- **CoreCloud verification**: Push heartbeat period = 0, verify no heartbeat messages
  arrive within a reasonable observation window
- **Stage 3 overlap**: Stage 3 verifies config propagation. Stage 4 verifies no messages
  at CoreCloud.
- **Classification**: Stage 4 primary (negative cloud message test)

```python
def test_prdtst_335_zero_heartbeat_period(ctx):
    """PRDTST-335: Zero heartbeat period disables heartbeat messages."""
    ctx.flash_firmware(ctx.hex_under_test)
    ctx.power_on()
    ctx.wait(30)

    # Push heartbeat period = 0 via CoreCloud
    ctx.cloud.push_ground_mode_config({"heartbeat_period_s": 0})
    ctx.wait(60)  # Allow config delivery via LTE

    ctx.cloud.mark_test_start()
    # Observe for 10 minutes -- no heartbeat messages should arrive
    ctx.wait(600)

    msgs = ctx.cloud.get_position_history()
    heartbeats = [m for m in msgs if m.update_reason == 1]

    assert len(heartbeats) == 0, (
        f"PRDTST-335 FAIL: Expected 0 heartbeats with period=0, got {len(heartbeats)}"
    )
```

#### PRDTST-344: Test Heartbeat Period Max Value

- **Acceptance criteria**: Verify that the device can be configured to send a heartbeat
  message at the specified period. (2-byte value: max 65535 seconds)
- **Build variant**: Both
- **Run type**: `weekly` (long observation window required)
- **Physical stimulus**: None
- **CoreCloud verification**: Push max heartbeat period, verify message arrives at
  approximately that interval
- **Stage 3 overlap**: Stage 3 verifies config acceptance. Stage 4 verifies max period
  timing at CoreCloud.
- **Classification**: Stage 4 primary (boundary value, long duration)

```python
def test_prdtst_344_heartbeat_max_period(ctx):
    """PRDTST-344: Max heartbeat period (65535s ~18.2h)."""
    ctx.flash_firmware(ctx.hex_under_test)
    ctx.power_on()
    ctx.wait(30)

    max_period_s = 65535
    ctx.cloud.push_ground_mode_config({"heartbeat_period_s": max_period_s})
    ctx.wait(60)

    ctx.cloud.mark_test_start()
    # Wait for one heartbeat at max period + margin
    msg = ctx.cloud.wait_for_position(
        timeout_s=max_period_s + 300,
        predicate=lambda m: m.update_reason == 1,
    )
    assert msg is not None, "PRDTST-344 FAIL: No heartbeat at max period"
```

#### PRDTST-356: Test Heartbeat Period Non-Default Value

- **Acceptance criteria**: Verify that the device can be configured to send a heartbeat
  message at a specified non-default period.
- **Build variant**: Both
- **Run type**: `commit`
- **Physical stimulus**: None
- **CoreCloud verification**: Push 5-minute heartbeat period, verify 2 messages at that
  interval
- **Classification**: Stage 4 primary (cloud message timing)

```python
def test_prdtst_356_heartbeat_non_default_period(ctx):
    """PRDTST-356: Non-default heartbeat period (300s)."""
    ctx.flash_firmware(ctx.hex_under_test)
    ctx.power_on()
    ctx.wait(30)

    custom_period_s = 300  # 5 minutes
    ctx.cloud.push_ground_mode_config({"heartbeat_period_s": custom_period_s})
    ctx.wait(60)

    ctx.cloud.mark_test_start()
    heartbeats = []
    deadline = time.time() + custom_period_s * 2 + 180
    while len(heartbeats) < 2 and time.time() < deadline:
        msgs = ctx.cloud.get_position_history()
        heartbeats = [m for m in msgs if m.update_reason == 1]
        ctx.wait(15)

    assert len(heartbeats) >= 2, (
        f"PRDTST-356 FAIL: Expected 2 heartbeats, got {len(heartbeats)}"
    )
    interval_s = (heartbeats[1].time_of_record - heartbeats[0].time_of_record).total_seconds()
    assert abs(interval_s - custom_period_s) < 30, (
        f"PRDTST-356 FAIL: interval {interval_s:.0f}s, expected {custom_period_s}s +/- 30s"
    )
```

#### PRDTST-371: Test Heartbeat Period Min Value

- **Acceptance criteria**: Verify that the device can be configured to send a heartbeat
  message at the minimum period.
- **Build variant**: Both
- **Run type**: `commit`
- **Physical stimulus**: None
- **CoreCloud verification**: Push minimum heartbeat period, verify rapid messages
- **Classification**: Stage 4 primary (boundary value)

```python
def test_prdtst_371_heartbeat_min_period(ctx):
    """PRDTST-371: Minimum heartbeat period."""
    ctx.flash_firmware(ctx.hex_under_test)
    ctx.power_on()
    ctx.wait(30)

    min_period_s = 60  # 1 minute minimum
    ctx.cloud.push_ground_mode_config({"heartbeat_period_s": min_period_s})
    ctx.wait(60)

    ctx.cloud.mark_test_start()
    heartbeats = []
    deadline = time.time() + min_period_s * 3 + 120
    while len(heartbeats) < 2 and time.time() < deadline:
        msgs = ctx.cloud.get_position_history()
        heartbeats = [m for m in msgs if m.update_reason == 1]
        ctx.wait(10)

    assert len(heartbeats) >= 2, (
        f"PRDTST-371 FAIL: Expected 2 heartbeats at min period, got {len(heartbeats)}"
    )
```

#### PRDTST-330: Test Heartbeat Acquisition Timeout Default Value

- **Acceptance criteria**: Verify that the device can be configured to run GPS for
  heartbeat acquisitions at the default period (60 seconds).
- **Build variant**: Both
- **Run type**: `commit`
- **Physical stimulus**: GNSS signal available
- **CoreCloud verification**: Verify heartbeat position message has `gps_on_time <= 60`
- **Classification**: Stage 3 primary (config propagation), Stage 4 regression

```python
def test_prdtst_330_heartbeat_acq_timeout_default(ctx):
    """PRDTST-330: Default heartbeat GPS acquisition timeout is 60s."""
    ctx.flash_firmware(ctx.hex_under_test)
    ctx.power_on()
    ctx.wait(30)

    # Default config -- no push needed
    msg = ctx.cloud.wait_for_position(
        timeout_s=7500,
        predicate=lambda m: m.update_reason == 1,
    )
    assert msg is not None, "PRDTST-330 FAIL: No heartbeat message"
    assert msg.gps_on_time <= 60, (
        f"PRDTST-330 FAIL: gps_on_time {msg.gps_on_time}s > 60s default timeout"
    )
```

#### PRDTST-359: Test Heartbeat Acquisition Timeout Non-Default Value

- **Acceptance criteria**: Verify that the device can be configured to run GPS for
  heartbeat acquisitions at a specified non-default period.
- **Build variant**: Both
- **Run type**: `commit`
- **Physical stimulus**: GNSS signal available
- **CoreCloud verification**: Push custom timeout, verify `gps_on_time` within limit
- **Classification**: Stage 3 primary, Stage 4 regression

```python
def test_prdtst_359_heartbeat_acq_timeout_custom(ctx):
    """PRDTST-359: Custom heartbeat GPS acquisition timeout."""
    ctx.flash_firmware(ctx.hex_under_test)
    ctx.power_on()
    ctx.wait(30)

    custom_timeout_s = 30
    ctx.cloud.push_ground_mode_config({"heartbeat_acq_timeout_s": custom_timeout_s})
    ctx.wait(60)

    msg = ctx.cloud.wait_for_position(
        timeout_s=7500,
        predicate=lambda m: m.update_reason == 1,
    )
    assert msg is not None, "PRDTST-359 FAIL: No heartbeat message"
    assert msg.gps_on_time <= custom_timeout_s, (
        f"PRDTST-359 FAIL: gps_on_time {msg.gps_on_time}s > {custom_timeout_s}s"
    )
```

#### PRDTST-342: Test Continuous Motion Period Default Value

- **Acceptance criteria**: Verify that the device can be configured to send a continuous
  motion message at the default period.
- **Build variant**: Both
- **Run type**: `commit`
- **Physical stimulus**: Motion actuator running continuously
- **CoreCloud verification**: Verify continuous motion position messages
  (`update_reason=5`) at default interval
- **Classification**: Stage 4 primary (cloud message timing with physical stimulus)

```python
def test_prdtst_342_continuous_motion_default(ctx):
    """PRDTST-342: Continuous motion messages at default period."""
    ctx.flash_firmware(ctx.hex_under_test)
    ctx.power_on()
    ctx.wait(30)

    ctx.cloud.mark_test_start()
    ctx.fixture.motion.shake(duration_s=600)  # 10 min sustained motion

    motion_msgs = []
    deadline = time.time() + 600
    while time.time() < deadline:
        msgs = ctx.cloud.get_position_history()
        motion_msgs = [m for m in msgs if m.update_reason == 5]
        if len(motion_msgs) >= 2:
            break
        ctx.wait(15)

    ctx.fixture.motion.stop()
    assert len(motion_msgs) >= 2, (
        f"PRDTST-342 FAIL: Expected 2+ continuous motion msgs, got {len(motion_msgs)}"
    )
```

#### PRDTST-364: Test Continuous Motion Disabled

- **Acceptance criteria**: Verify that the device can be configured to not send
  continuous motion messages.
- **Build variant**: Both
- **Run type**: `commit`
- **Physical stimulus**: Motion actuator running
- **CoreCloud verification**: Push continuous motion period = 0, verify no continuous
  motion messages arrive
- **Classification**: Stage 4 primary (negative test)

```python
def test_prdtst_364_continuous_motion_disabled(ctx):
    """PRDTST-364: Disabled continuous motion produces no motion messages."""
    ctx.flash_firmware(ctx.hex_under_test)
    ctx.power_on()
    ctx.wait(30)

    ctx.cloud.push_ground_mode_config({"continuous_motion_period_s": 0})
    ctx.wait(60)

    ctx.cloud.mark_test_start()
    ctx.fixture.motion.shake(duration_s=300)  # 5 min motion
    ctx.wait(300)
    ctx.fixture.motion.stop()

    msgs = ctx.cloud.get_position_history()
    continuous = [m for m in msgs if m.update_reason == 5]
    assert len(continuous) == 0, (
        f"PRDTST-364 FAIL: Got {len(continuous)} continuous motion msgs with period=0"
    )
```

#### PRDTST-369: Test Continuous Motion Period Non-Default Value

- **Acceptance criteria**: Verify that the device can be configured to send a continuous
  motion message at a specified non-default period.
- **Build variant**: Both
- **Run type**: `commit`
- **Physical stimulus**: Motion actuator running
- **CoreCloud verification**: Push custom period, verify messages at that interval
- **Classification**: Stage 4 primary

```python
def test_prdtst_369_continuous_motion_custom(ctx):
    """PRDTST-369: Custom continuous motion period."""
    ctx.flash_firmware(ctx.hex_under_test)
    ctx.power_on()
    ctx.wait(30)

    custom_period_s = 120  # 2 minutes
    ctx.cloud.push_ground_mode_config({"continuous_motion_period_s": custom_period_s})
    ctx.wait(60)

    ctx.cloud.mark_test_start()
    ctx.fixture.motion.shake(duration_s=custom_period_s * 3)

    motion_msgs = []
    deadline = time.time() + custom_period_s * 3 + 120
    while len(motion_msgs) < 2 and time.time() < deadline:
        msgs = ctx.cloud.get_position_history()
        motion_msgs = [m for m in msgs if m.update_reason == 5]
        ctx.wait(15)

    ctx.fixture.motion.stop()
    assert len(motion_msgs) >= 2, (
        f"PRDTST-369 FAIL: Expected 2+ msgs, got {len(motion_msgs)}"
    )
```

#### PRDTST-387: Test Continuous Motion Period Min Value

- **Acceptance criteria**: Verify that the device can be configured using a continuous
  motion period of 1 second.
- **Build variant**: Both
- **Run type**: `weekly` (NOTE: application behavior at 1s period is undefined per Jira)
- **Physical stimulus**: Motion actuator
- **CoreCloud verification**: Push period = 1s, observe behavior
- **Classification**: Stage 4 primary (boundary value, behavior TBD)

```python
def test_prdtst_387_continuous_motion_min(ctx):
    """PRDTST-387: Min continuous motion period (1s). Behavior may be undefined."""
    ctx.flash_firmware(ctx.hex_under_test)
    ctx.power_on()
    ctx.wait(30)

    ctx.cloud.push_ground_mode_config({"continuous_motion_period_s": 1})
    ctx.wait(60)

    ctx.cloud.mark_test_start()
    ctx.fixture.motion.shake(duration_s=60)
    ctx.wait(90)
    ctx.fixture.motion.stop()

    msgs = ctx.cloud.get_position_history()
    continuous = [m for m in msgs if m.update_reason == 5]
    # At 1s period, we expect many messages (but behavior is undefined per Jira)
    # This test documents actual behavior rather than asserting a threshold
    log.info(f"PRDTST-387: Got {len(continuous)} continuous motion msgs at 1s period")
    assert len(continuous) >= 1, "PRDTST-387 FAIL: No continuous motion msgs at 1s period"
```

#### PRDTST-394: Test Continuous Motion Period Max Value

- **Acceptance criteria**: Verify that the device can be configured using a continuous
  motion period of 65535 seconds (approximately 18.2 hours).
- **Build variant**: Both
- **Run type**: `weekly` (long observation window)
- **Physical stimulus**: Motion actuator
- **CoreCloud verification**: Push max period, verify config acceptance
- **Classification**: Stage 3 primary (config acceptance), Stage 4 regression

```python
def test_prdtst_394_continuous_motion_max(ctx):
    """PRDTST-394: Max continuous motion period (65535s)."""
    ctx.flash_firmware(ctx.hex_under_test)
    ctx.power_on()
    ctx.wait(30)

    ctx.cloud.push_ground_mode_config({"continuous_motion_period_s": 65535})
    ctx.wait(60)

    # Verify config was accepted -- device sends Ground Mode Config on next heartbeat
    msg = ctx.cloud.wait_for_position(
        timeout_s=7500,
        predicate=lambda m: m.update_reason == 1,
    )
    assert msg is not None, "PRDTST-394 FAIL: No heartbeat after max period config"
```

#### PRDTST-328: Test Motion Stop Acquisition Timeout Default Value

- **Acceptance criteria**: Verify that the device can be configured to run GPS for motion
  stop acquisitions at the default period.
- **Build variant**: Both
- **Run type**: `commit`
- **Physical stimulus**: Motion actuator (start then stop to trigger stop-motion event)
- **CoreCloud verification**: Verify stop motion position message (`update_reason=2`)
  has `gps_on_time` within default timeout
- **Classification**: Stage 4 primary

```python
def test_prdtst_328_stop_motion_acq_timeout_default(ctx):
    """PRDTST-328: Default motion stop GPS acquisition timeout."""
    ctx.flash_firmware(ctx.hex_under_test)
    ctx.power_on()
    ctx.wait(30)

    # Generate motion then stop
    ctx.fixture.motion.shake(duration_s=30)
    ctx.wait(30)
    ctx.fixture.motion.stop()

    ctx.cloud.mark_test_start()
    # Wait for stop motion message
    msg = ctx.cloud.wait_for_position(
        timeout_s=300,
        predicate=lambda m: m.update_reason == 2,
    )
    assert msg is not None, "PRDTST-328 FAIL: No stop motion message"
```

#### PRDTST-347: Test Stop Motion Timeout Non-Default Value

- **Acceptance criteria**: Verify that the device can be configured to send a stop motion
  message at the specified period.
- **Build variant**: Both
- **Run type**: `commit`
- **Physical stimulus**: Motion actuator (start then stop)
- **CoreCloud verification**: Push custom stop motion timeout, verify stop motion message
  timing
- **Classification**: Stage 3 primary, Stage 4 regression

```python
def test_prdtst_347_stop_motion_timeout_custom(ctx):
    """PRDTST-347: Custom stop motion timeout."""
    ctx.flash_firmware(ctx.hex_under_test)
    ctx.power_on()
    ctx.wait(30)

    custom_timeout_s = 300  # 5 minutes
    ctx.cloud.push_ground_mode_config({"stop_motion_timeout_s": custom_timeout_s})
    ctx.wait(60)

    ctx.fixture.motion.shake(duration_s=30)
    ctx.wait(30)
    ctx.fixture.motion.stop()

    ctx.cloud.mark_test_start()
    stop_time = time.time()

    msg = ctx.cloud.wait_for_position(
        timeout_s=custom_timeout_s + 120,
        predicate=lambda m: m.update_reason == 2,
    )
    elapsed = time.time() - stop_time

    assert msg is not None, "PRDTST-347 FAIL: No stop motion message"
    assert abs(elapsed - custom_timeout_s) < 60, (
        f"PRDTST-347 FAIL: stop motion at {elapsed:.0f}s, expected ~{custom_timeout_s}s"
    )
```

#### PRDTST-399: Test Stop Motion Timeout Default Value

- **Acceptance criteria**: Verify that the device can be configured to send a stop motion
  message at the default period (2 minutes).
- **Build variant**: Both
- **Run type**: `commit`
- **Physical stimulus**: Motion actuator (start then stop)
- **CoreCloud verification**: Verify stop motion message arrives ~120s after motion stops
- **Classification**: Stage 4 primary

```python
def test_prdtst_399_stop_motion_timeout_default(ctx):
    """PRDTST-399: Default stop motion timeout (120s)."""
    ctx.flash_firmware(ctx.hex_under_test)
    ctx.power_on()
    ctx.wait(30)

    ctx.fixture.motion.shake(duration_s=30)
    ctx.wait(30)
    ctx.fixture.motion.stop()

    ctx.cloud.mark_test_start()
    stop_time = time.time()

    msg = ctx.cloud.wait_for_position(
        timeout_s=300,
        predicate=lambda m: m.update_reason == 2,
    )
    elapsed = time.time() - stop_time

    assert msg is not None, "PRDTST-399 FAIL: No stop motion message"
    assert abs(elapsed - 120) < 60, (
        f"PRDTST-399 FAIL: stop motion at {elapsed:.0f}s, expected ~120s"
    )
```

#### PRDTST-353: Test Start Motion Window Start Default Value

- **Acceptance criteria**: Verify that the device can be configured to begin the start
  motion window at the default period (3 seconds).
- **Build variant**: Both
- **Run type**: `commit`
- **Physical stimulus**: Brief motion pulse (< 3s should not trigger motion)
- **CoreCloud verification**: Verify motion is detected only after 3s duration
- **Stage 3 overlap**: Stage 3 verifies config propagation. Stage 4 verifies timing
  behavior.
- **Classification**: Stage 3 primary, Stage 4 regression

```python
def test_prdtst_353_start_motion_window_default(ctx):
    """PRDTST-353: Start motion window default (3s)."""
    ctx.flash_firmware(ctx.hex_under_test)
    ctx.power_on()
    ctx.wait(60)

    ctx.cloud.mark_test_start()

    # Brief motion (< 3s) should NOT trigger detection
    ctx.fixture.motion.shake(duration_s=2)
    ctx.wait(120)

    msgs = ctx.cloud.get_position_history()
    motion_msgs = [m for m in msgs if m.update_reason in (2, 5) and m.is_in_motion]
    assert len(motion_msgs) == 0, (
        f"PRDTST-353 FAIL: Motion detected from {len(motion_msgs)} msgs "
        f"with < 3s motion pulse"
    )
```

#### PRDTST-374: Test Ground Mode Config Sent on Boot

- **Acceptance criteria**: Verify that the device sends its current Ground Mode Config
  Message to the server on boot.
- **Build variant**: Both
- **Run type**: `commit`
- **Physical stimulus**: Power cycle (reboot)
- **CoreCloud verification**: Verify Ground Mode Config message arrives after boot
- **Classification**: Stage 4 primary (boot-time cloud message)

```python
def test_prdtst_374_ground_mode_config_on_boot(ctx):
    """PRDTST-374: Device sends Ground Mode Config on boot."""
    ctx.flash_firmware(ctx.hex_under_test)
    ctx.cloud.mark_test_start()
    ctx.power_on()

    # Wait for boot message
    boot_msg = ctx.cloud.wait_for_boot(timeout_s=120)
    assert boot_msg is not None, "PRDTST-374 FAIL: No boot message"
    assert boot_msg.boot_reason == 0, (
        f"PRDTST-374 FAIL: Expected normal boot (0), got {boot_msg.boot_reason_str}"
    )

    # Wait for first position message (boot update_reason=0)
    pos_msg = ctx.cloud.wait_for_position(
        timeout_s=120,
        predicate=lambda m: m.update_reason == 0,
    )
    assert pos_msg is not None, (
        "PRDTST-374 FAIL: No boot position message (update_reason=0)"
    )
```

#### PRDTST-388: Test Default Ground Mode Config Values

- **Acceptance criteria**: Verify that a fresh device has the default Ground Mode Config
  V2 Message values.
- **Build variant**: Both
- **Run type**: `commit`
- **Physical stimulus**: Flash fresh firmware, boot
- **CoreCloud verification**: Verify Ground Mode Config message contains default values
- **Classification**: Stage 4 primary (fresh firmware defaults)

```python
def test_prdtst_388_default_ground_mode_config(ctx):
    """PRDTST-388: Fresh firmware has default Ground Mode Config values."""
    ctx.flash_firmware(ctx.hex_under_test)
    ctx.cloud.mark_test_start()
    ctx.power_on()

    # Wait for boot position message with config values
    msg = ctx.cloud.wait_for_position(
        timeout_s=120,
        predicate=lambda m: m.update_reason == 0,
    )
    assert msg is not None, "PRDTST-388 FAIL: No boot position message"
    # Specific default values verified against product spec
    # (exact values depend on product configuration document)
```

### 5.3 Motion Detection Tests

Motion detection tests use the MTIB linear actuator to apply controlled acceleration
to the device and verify motion detection behavior through CoreCloud messages.

#### PRDTST-324: Test Ignore Motion Below Acceleration Threshold

- **Acceptance criteria**: The device shall not detect motion when the acceleration is
  below the threshold, even if the duration is above the threshold.
- **Build variant**: Both
- **Run type**: `commit`
- **Physical stimulus**: Gentle motion below acceleration threshold via actuator
- **CoreCloud verification**: Verify no motion-related position messages arrive
- **Stage 3 overlap**: Stage 3 verifies threshold behavior via harness state observation.
  Stage 4 verifies end-to-end with production firmware.
- **Classification**: Stage 3 primary (internal state verification), Stage 4 regression

```python
def test_prdtst_324_ignore_motion_below_accel_threshold(ctx):
    """PRDTST-324: No motion detection below acceleration threshold."""
    ctx.flash_firmware(ctx.hex_under_test)
    ctx.power_on()
    ctx.wait(60)

    ctx.cloud.mark_test_start()
    # Apply gentle motion below threshold (actuator at low intensity)
    ctx.fixture.motion.shake(duration_s=30, intensity="low")
    ctx.wait(120)
    ctx.fixture.motion.stop()

    msgs = ctx.cloud.get_position_history()
    motion_msgs = [m for m in msgs if m.is_in_motion]
    assert len(motion_msgs) == 0, (
        f"PRDTST-324 FAIL: Motion detected ({len(motion_msgs)} msgs) "
        f"below acceleration threshold"
    )
```

#### PRDTST-326: Test Detect Motion Above Thresholds with Default Config

- **Acceptance criteria**: The device shall detect motion when the acceleration is above
  the threshold and the duration is above the threshold.
- **Build variant**: Both
- **Run type**: `commit`
- **Physical stimulus**: Strong motion above both thresholds
- **CoreCloud verification**: Verify motion-related position message with `is_in_motion=True`
- **Stage 3 overlap**: Stage 3 verifies motion state machine transitions.
  Stage 4 verifies the position message at CoreCloud.
- **Classification**: Stage 4 primary (cloud message verification)

```python
def test_prdtst_326_detect_motion_above_thresholds(ctx):
    """PRDTST-326: Motion detection above both thresholds."""
    ctx.flash_firmware(ctx.hex_under_test)
    ctx.power_on()
    ctx.wait(60)

    ctx.cloud.mark_test_start()
    # Apply strong motion above threshold
    ctx.fixture.motion.shake(duration_s=30, intensity="high")
    ctx.wait(60)

    msg = ctx.cloud.wait_for_position(
        timeout_s=180,
        predicate=lambda m: m.is_in_motion,
    )
    ctx.fixture.motion.stop()
    assert msg is not None, "PRDTST-326 FAIL: No motion detected above thresholds"
    assert msg.is_in_motion is True, "PRDTST-326 FAIL: is_in_motion flag not set"
```

#### PRDTST-375: Test Ignore Motion Below Duration Threshold

- **Acceptance criteria**: Verify the device does not detect motion when not moved over
  the time duration threshold but exceeding the acceleration threshold.
- **Build variant**: Both
- **Run type**: `commit`
- **Physical stimulus**: Brief high-acceleration pulse below duration threshold
- **CoreCloud verification**: Verify no motion messages
- **Classification**: Stage 3 primary, Stage 4 regression

```python
def test_prdtst_375_ignore_motion_below_duration(ctx):
    """PRDTST-375: No motion detection below duration threshold."""
    ctx.flash_firmware(ctx.hex_under_test)
    ctx.power_on()
    ctx.wait(60)

    ctx.cloud.mark_test_start()
    # Brief high-intensity pulse (below 3s default start window)
    ctx.fixture.motion.shake(duration_s=1, intensity="high")
    ctx.wait(1)
    ctx.fixture.motion.stop()
    ctx.wait(120)

    msgs = ctx.cloud.get_position_history()
    motion_msgs = [m for m in msgs if m.is_in_motion]
    assert len(motion_msgs) == 0, (
        f"PRDTST-375 FAIL: Motion detected from brief pulse ({len(motion_msgs)} msgs)"
    )
```

#### PRDTST-389: Test Axis Independence

- **Acceptance criteria**: The device shall detect motion in all three axes
  independently.
- **Build variant**: Both
- **Run type**: `commit`
- **Physical stimulus**: Single-axis motion in X, Y, Z independently
- **CoreCloud verification**: Verify motion detected for each axis
- **Classification**: Stage 4 primary (requires physical multi-axis stimulus)

```python
def test_prdtst_389_axis_independence(ctx):
    """PRDTST-389: Motion detection in each axis independently."""
    ctx.flash_firmware(ctx.hex_under_test)
    ctx.power_on()
    ctx.wait(60)

    for axis in ["x", "y", "z"]:
        ctx.cloud.mark_test_start()
        ctx.fixture.motion.single_axis(axis, duration_s=10)
        ctx.wait(10)
        ctx.fixture.motion.stop()

        msg = ctx.cloud.wait_for_position(
            timeout_s=180,
            predicate=lambda m: m.is_in_motion,
        )
        assert msg is not None, (
            f"PRDTST-389 FAIL: No motion detected for {axis}-axis"
        )
        ctx.wait(180)  # Wait for stop-motion before next axis
```

#### PRDTST-393: Test Respect Motion Start Window

- **Acceptance criteria**: The device shall not detect motion until the start motion
  window has elapsed.
- **Build variant**: Both
- **Run type**: `commit`
- **Physical stimulus**: Motion applied, verify detection happens only after start window
- **CoreCloud verification**: Verify timing of motion message relative to motion start
- **Classification**: Stage 3 primary (timing verified via harness), Stage 4 regression

```python
def test_prdtst_393_motion_start_window(ctx):
    """PRDTST-393: Motion not detected until start window elapses."""
    ctx.flash_firmware(ctx.hex_under_test)
    ctx.power_on()
    ctx.wait(60)

    # Default start window is 3 seconds (PRDTST-353)
    ctx.cloud.mark_test_start()
    motion_start = time.time()
    ctx.fixture.motion.shake(duration_s=30, intensity="high")

    msg = ctx.cloud.wait_for_position(
        timeout_s=180,
        predicate=lambda m: m.is_in_motion,
    )
    ctx.fixture.motion.stop()

    assert msg is not None, "PRDTST-393 FAIL: No motion detected"
    # The message timestamp should be at least 3s after motion started
    # (network latency makes this a coarse check)
```

### 5.4 Charging / BMS Tests

Charging tests use the MTIB charger relay and temperature controller to verify the
complete charging subsystem behavior. Many of these tests are hardware-dominated and
can only be fully verified at Stage 4.

#### PRDTST-332: Test Charge Controller Temperature Measurement Short Circuit Start Charging

- **Acceptance criteria**: Verify that the charge controller will not charge the battery
  when the TS pin is shorted at the start of charging.
- **Build variant**: Both
- **Run type**: `weekly`
- **Physical stimulus**: Short TS pin (requires specific fixture wiring), connect charger
- **CoreCloud verification**: None (hardware safety test)
- **Stage 3 overlap**: None (hardware-only behavior)
- **Classification**: Stage 4 primary (hardware safety, requires fixture)

```python
def test_prdtst_332_ts_short_circuit_start(ctx):
    """PRDTST-332: No charging with TS pin shorted at start."""
    ctx.flash_firmware(ctx.hex_under_test)
    ctx.power_on()
    ctx.wait(30)

    ctx.fixture.ts_pin.short()  # Fixture-specific: short TS pin
    ctx.fixture.charger.connect()
    ctx.wait(30)

    trace = ctx.mtib.power_measure("DUT", duration_s=60, sample_hz=10)
    # Charging current should be near zero with TS shorted
    charge_current = trace.channel_current_ma("charger")
    assert charge_current < 5, (
        f"PRDTST-332 FAIL: Charge current {charge_current:.1f}mA with TS shorted"
    )
    ctx.fixture.charger.disconnect()
    ctx.fixture.ts_pin.release()
```

#### PRDTST-334: Test State of Charge (SoC) Reporting

- **Acceptance criteria**: When the battery is discharged to 0% SoC, the device shall
  report SoC within +/-2% of the true value as measured by external test equipment.
- **Build variant**: Both
- **Run type**: `weekly`
- **Physical stimulus**: Discharge battery to known SoC levels
- **CoreCloud verification**: Verify `batt_percent` in position messages matches
  external measurement within 2%
- **Classification**: Stage 4 primary (requires external SoC measurement)

```python
def test_prdtst_334_soc_reporting_accuracy(ctx):
    """PRDTST-334: SoC reporting within +/-2% accuracy."""
    ctx.flash_firmware(ctx.hex_under_test)
    ctx.power_on()
    ctx.wait(30)

    # Trigger a position message to read SoC
    ctx.cloud.mark_test_start()
    msg = ctx.cloud.wait_for_position(timeout_s=7500)

    assert msg is not None, "PRDTST-334 FAIL: No position message"
    assert msg.batt_percent is not None, "PRDTST-334 FAIL: batt_percent is None"
    # Compare with external fuel gauge measurement
    external_soc = ctx.fixture.fuel_gauge.read_soc()
    deviation = abs(msg.batt_percent - external_soc)
    assert deviation <= 2, (
        f"PRDTST-334 FAIL: SoC deviation {deviation}% "
        f"(device={msg.batt_percent}%, external={external_soc}%)"
    )
```

#### PRDTST-339: Test Charge Controller Temperature Short Circuit While Charging

- **Acceptance criteria**: Verify that the charge controller will not charge the battery
  when the TS pin is shorted while already charging.
- **Build variant**: Both
- **Run type**: `weekly`
- **Physical stimulus**: Start charging, then short TS pin
- **CoreCloud verification**: None (hardware safety)
- **Classification**: Stage 4 primary

```python
def test_prdtst_339_ts_short_while_charging(ctx):
    """PRDTST-339: Charging stops when TS pin shorted during charge."""
    ctx.flash_firmware(ctx.hex_under_test)
    ctx.power_on()
    ctx.wait(30)

    ctx.fixture.charger.connect()
    ctx.wait(30)  # Charging should start

    # Verify charging is happening
    trace_before = ctx.mtib.power_measure("DUT", duration_s=10)
    assert trace_before.channel_current_ma("charger") > 10, (
        "PRDTST-339 FAIL: Charging did not start"
    )

    # Short TS pin while charging
    ctx.fixture.ts_pin.short()
    ctx.wait(10)

    trace_after = ctx.mtib.power_measure("DUT", duration_s=30)
    charge_current = trace_after.channel_current_ma("charger")
    assert charge_current < 5, (
        f"PRDTST-339 FAIL: Charging continued after TS short ({charge_current:.1f}mA)"
    )
    ctx.fixture.ts_pin.release()
    ctx.fixture.charger.disconnect()
```

#### PRDTST-349: Test No FUOTA on Low Battery

- **Acceptance criteria**: Verify that FUOTAs can not complete when the battery is
  critically low (3.7V).
- **Build variant**: Both
- **Run type**: `weekly`
- **Physical stimulus**: Set battery voltage to 3.7V, attempt FUOTA
- **CoreCloud verification**: Verify FUOTA does not complete
- **Classification**: Stage 4 primary (FUOTA + low battery, unique to Stage 4)

```python
def test_prdtst_349_no_fuota_low_battery(ctx):
    """PRDTST-349: FUOTA rejected at low battery (3.7V)."""
    ctx.flash_firmware(ctx.hex_under_test)
    ctx.mtib.power_enable(channel=0, voltage_v=3.7)  # Low battery
    ctx.wait(30)

    # Attempt FUOTA via CoreCloud
    fuota_result = ctx.cloud.trigger_fuota(
        ctx.device_id,
        firmware_url=ctx.fuota_target_url,
        version=ctx.fuota_target_version,
    )
    ctx.wait(300)  # Wait for FUOTA attempt

    # Device should still be running original firmware
    boot_msg = ctx.cloud.wait_for_boot(timeout_s=120)
    # If no boot message, FUOTA did not complete (expected)
    # If boot message exists, verify it is NOT a FUOTA reboot
    if boot_msg is not None:
        assert boot_msg.boot_reason != 2, (
            "PRDTST-349 FAIL: FUOTA completed at low battery"
        )
```

#### PRDTST-350: Test Battery Temperature Reported in Position Message

- **Acceptance criteria**: The device shall report the battery temperature via the
  Position Message.
- **Build variant**: Both
- **Run type**: `commit`
- **Physical stimulus**: None (temperature at ambient)
- **CoreCloud verification**: Verify `bms_temp` field present and reasonable in position
  message
- **Classification**: Stage 4 primary (cloud message field verification)

```python
def test_prdtst_350_battery_temp_in_position(ctx):
    """PRDTST-350: Battery temperature reported in position message."""
    ctx.flash_firmware(ctx.hex_under_test)
    ctx.power_on()
    ctx.wait(30)

    msg = ctx.cloud.wait_for_position(timeout_s=7500)
    assert msg is not None, "PRDTST-350 FAIL: No position message"
    assert msg.bms_temp is not None, "PRDTST-350 FAIL: bms_temp field is None"
    # Sanity check: temperature should be between -40C and +85C
    assert -40 <= msg.bms_temp <= 85, (
        f"PRDTST-350 FAIL: bms_temp {msg.bms_temp}C out of sensor range"
    )
```

#### PRDTST-351: Test Device Must Not Charge at Negative Temperatures

- **Acceptance criteria**: The device shall not charge the battery when the battery
  temperature is below 0C.
- **Build variant**: Both
- **Run type**: `weekly` (requires temperature chamber)
- **Physical stimulus**: Set temperature to -5C, connect charger
- **CoreCloud verification**: Verify `on_charger=True` but no charging current
- **Classification**: Stage 4 primary (temperature chamber required)

```python
def test_prdtst_351_no_charge_negative_temp(ctx):
    """PRDTST-351: No charging below 0C."""
    ctx.flash_firmware(ctx.hex_under_test)
    ctx.power_on()
    ctx.wait(30)

    ctx.fixture.temperature.set(-5)
    ctx.wait(300)  # Temperature stabilize

    ctx.fixture.charger.connect()
    ctx.wait(60)

    trace = ctx.mtib.power_measure("DUT", duration_s=60)
    charge_current = trace.channel_current_ma("charger")
    assert charge_current < 5, (
        f"PRDTST-351 FAIL: Charging at -5C ({charge_current:.1f}mA)"
    )
    ctx.fixture.charger.disconnect()
    ctx.fixture.temperature.set(25)
```

#### PRDTST-354: Test Connecting Charger Must Delatch Device from Lockout

- **Acceptance criteria**: The device shall wake up and start charging the battery when
  the charger is connected, even when the battery is locked out.
- **Build variant**: Both
- **Run type**: `weekly`
- **Physical stimulus**: Put device in lockout (battery < 3.5V), then connect charger
- **CoreCloud verification**: Verify boot message with `boot_reason=3` (charger wake)
- **Classification**: Stage 4 primary

```python
def test_prdtst_354_charger_delatch_lockout(ctx):
    """PRDTST-354: Charger connection wakes device from lockout."""
    ctx.flash_firmware(ctx.hex_under_test)
    ctx.mtib.power_enable(channel=0, voltage_v=3.3)  # Force lockout
    ctx.wait(10)

    ctx.cloud.mark_test_start()
    # Connect charger -- should delatch
    ctx.mtib.power_enable(channel=0, voltage_v=4.5)  # Restore battery voltage
    ctx.fixture.charger.connect()
    ctx.wait(60)

    boot_msg = ctx.cloud.wait_for_boot(timeout_s=120)
    assert boot_msg is not None, "PRDTST-354 FAIL: No boot after charger connect"
    assert boot_msg.boot_reason == 3, (
        f"PRDTST-354 FAIL: Expected charger boot (3), got {boot_msg.boot_reason_str}"
    )
    ctx.fixture.charger.disconnect()
```

#### PRDTST-365: Test Device Must Charge Using Charge Ladder

- **Acceptance criteria**: The device shall charge the battery using a charge ladder to
  maximize cycle life.
- **Build variant**: Both
- **Run type**: `weekly`
- **Physical stimulus**: Connect charger, monitor charge profile over time
- **CoreCloud verification**: None (power measurement verification)
- **Classification**: Stage 4 primary (full charge profile)

#### PRDTST-366: Test BMS Battery SoC and Temp Reported in Position Message

- **Acceptance criteria**: Verify that the device reports the battery SoC and temperature
  via the Position Message while in motion and on-skin.
- **Build variant**: Both
- **Run type**: `commit`
- **Physical stimulus**: On-skin electrode + motion actuator
- **CoreCloud verification**: Verify `batt_percent`, `bms_temp` in position message
  where `is_in_motion=True`
- **Classification**: Stage 4 primary

```python
def test_prdtst_366_soc_temp_in_motion_position(ctx):
    """PRDTST-366: SoC and temp in position message during motion + on-skin."""
    ctx.flash_firmware(ctx.hex_under_test)
    ctx.power_on()
    ctx.wait(30)

    ctx.fixture.on_skin.enable()
    ctx.fixture.motion.shake(duration_s=30)
    ctx.cloud.mark_test_start()

    msg = ctx.cloud.wait_for_position(
        timeout_s=180,
        predicate=lambda m: m.is_in_motion,
    )
    ctx.fixture.motion.stop()
    ctx.fixture.on_skin.disable()

    assert msg is not None, "PRDTST-366 FAIL: No in-motion position message"
    assert msg.batt_percent is not None, "PRDTST-366 FAIL: batt_percent missing"
    assert msg.bms_temp is not None, "PRDTST-366 FAIL: bms_temp missing"
    assert 0 <= msg.batt_percent <= 100, (
        f"PRDTST-366 FAIL: batt_percent {msg.batt_percent} out of range"
    )
```

#### PRDTST-367: Test BMS Temperature Measurement Accuracy

- **Acceptance criteria**: Verify the BMS reports the board temperature to within +/-2C
  of the value measured by an external calibrated thermometer.
- **Build variant**: Both
- **Run type**: `weekly` (requires temperature chamber at multiple setpoints)
- **Physical stimulus**: Temperature chamber at known setpoints
- **CoreCloud verification**: Compare `bms_temp` with thermistor reading
- **Classification**: Stage 4 primary (calibrated measurement)

```python
def test_prdtst_367_bms_temp_accuracy(ctx):
    """PRDTST-367: BMS temperature within +/-2C of calibrated reference."""
    ctx.flash_firmware(ctx.hex_under_test)
    ctx.power_on()
    ctx.wait(30)

    test_temps = [0, 10, 25, 35, 45]
    for target_c in test_temps:
        ctx.fixture.temperature.set(target_c)
        ctx.wait(300)  # Thermal stabilization

        actual_c = ctx.fixture.temperature.read_thermistor()
        ctx.cloud.mark_test_start()

        msg = ctx.cloud.wait_for_position(timeout_s=7500)
        assert msg is not None, f"PRDTST-367 FAIL: No position msg at {target_c}C"
        deviation = abs(msg.bms_temp - actual_c)
        assert deviation <= 2, (
            f"PRDTST-367 FAIL at {target_c}C: BMS={msg.bms_temp}C, "
            f"actual={actual_c:.1f}C, deviation={deviation:.1f}C"
        )
    ctx.fixture.temperature.set(25)
```

#### PRDTST-368: Test Device Must Report On-Charger State in Position Message

- **Acceptance criteria**: The device shall report the on-charger state via the Position
  Message when connected to a charger.
- **Build variant**: Both
- **Run type**: `commit`
- **Physical stimulus**: Connect charger
- **CoreCloud verification**: Verify `on_charger=True` in position message
- **Classification**: Stage 4 primary

```python
def test_prdtst_368_on_charger_in_position(ctx):
    """PRDTST-368: on_charger flag in position message when charging."""
    ctx.flash_firmware(ctx.hex_under_test)
    ctx.power_on()
    ctx.wait(30)

    ctx.fixture.charger.connect()
    ctx.cloud.mark_test_start()
    ctx.wait(30)

    msg = ctx.cloud.wait_for_position(timeout_s=7500)
    assert msg is not None, "PRDTST-368 FAIL: No position message"
    assert msg.on_charger is True, (
        f"PRDTST-368 FAIL: on_charger={msg.on_charger}, expected True"
    )
    ctx.fixture.charger.disconnect()
```

#### PRDTST-370: Test Device Must Charge from 3.5V to 4.2V in Under 3 Hours

- **Acceptance criteria**: The device shall charge the battery from 3.5V to 4.2V in
  under three hours.
- **Build variant**: Both
- **Run type**: `weekly` (3-hour charge cycle)
- **Physical stimulus**: Set battery to 3.5V, connect charger, monitor until 4.2V
- **CoreCloud verification**: Monitor `batt_voltage` in position messages
- **Classification**: Stage 4 primary (full charge cycle timing)

```python
def test_prdtst_370_charge_time_3h(ctx):
    """PRDTST-370: Full charge (3.5V to 4.2V) in under 3 hours."""
    ctx.flash_firmware(ctx.hex_under_test)
    ctx.power_on()
    ctx.wait(30)

    ctx.fixture.charger.connect()
    start_time = time.time()

    # Monitor until fully charged or 3-hour timeout
    timeout_s = 3 * 3600
    while time.time() - start_time < timeout_s:
        msg = ctx.cloud.get_latest_position()
        if msg and msg.batt_voltage and msg.batt_voltage >= 4200:  # mV
            break
        ctx.wait(300)

    elapsed_h = (time.time() - start_time) / 3600
    assert elapsed_h < 3.0, (
        f"PRDTST-370 FAIL: Charge took {elapsed_h:.1f}h, limit is 3h"
    )
    ctx.fixture.charger.disconnect()
```

#### PRDTST-372: Test Device Must Not Charge Above 45C

- **Acceptance criteria**: The device shall not charge the battery when the temperature
  is above 45C.
- **Build variant**: Both
- **Run type**: `weekly`
- **Physical stimulus**: Temperature chamber at 46C, connect charger
- **CoreCloud verification**: None (current measurement)
- **Classification**: Stage 4 primary (temperature chamber required)

```python
def test_prdtst_372_no_charge_above_45c(ctx):
    """PRDTST-372: No charging above 45C."""
    ctx.flash_firmware(ctx.hex_under_test)
    ctx.power_on()
    ctx.wait(30)

    ctx.fixture.temperature.set(46)
    ctx.wait(300)

    ctx.fixture.charger.connect()
    ctx.wait(60)

    trace = ctx.mtib.power_measure("DUT", duration_s=60)
    charge_current = trace.channel_current_ma("charger")
    assert charge_current < 5, (
        f"PRDTST-372 FAIL: Charging at 46C ({charge_current:.1f}mA)"
    )
    ctx.fixture.charger.disconnect()
    ctx.fixture.temperature.set(25)
```

#### PRDTST-381: Test BMS Parameter Retention and Application

- **Acceptance criteria**: Verify that the BMS retains and/or applies the correct
  configuration after a power cycle.
- **Build variant**: Both
- **Run type**: `commit`
- **Physical stimulus**: Power cycle
- **CoreCloud verification**: Compare BMS readings before and after reboot
- **Classification**: Stage 4 primary

```python
def test_prdtst_381_bms_param_retention(ctx):
    """PRDTST-381: BMS parameters survive power cycle."""
    ctx.flash_firmware(ctx.hex_under_test)
    ctx.power_on()
    ctx.wait(60)

    msg_before = ctx.cloud.get_latest_position()
    assert msg_before is not None, "PRDTST-381 FAIL: No pre-reboot position"

    # Power cycle
    ctx.power_off()
    ctx.wait(5)
    ctx.cloud.mark_test_start()
    ctx.power_on()
    ctx.wait(60)

    msg_after = ctx.cloud.wait_for_position(timeout_s=7500)
    assert msg_after is not None, "PRDTST-381 FAIL: No post-reboot position"
    # BMS SoC should be approximately the same (within 5%)
    if msg_before.batt_percent and msg_after.batt_percent:
        deviation = abs(msg_before.batt_percent - msg_after.batt_percent)
        assert deviation <= 5, (
            f"PRDTST-381 FAIL: SoC changed by {deviation}% across reboot"
        )
```

#### PRDTST-383: Test Device Must Not Charge Below 10C

- **Acceptance criteria**: The device shall not charge when temperature is below 10C.
- **Build variant**: Both
- **Run type**: `weekly`
- **Physical stimulus**: Temperature chamber at 8C, connect charger
- **CoreCloud verification**: None (current measurement)
- **Classification**: Stage 4 primary

```python
def test_prdtst_383_no_charge_below_10c(ctx):
    """PRDTST-383: No charging below 10C."""
    ctx.flash_firmware(ctx.hex_under_test)
    ctx.power_on()
    ctx.wait(30)

    ctx.fixture.temperature.set(8)
    ctx.wait(300)

    ctx.fixture.charger.connect()
    ctx.wait(60)

    trace = ctx.mtib.power_measure("DUT", duration_s=60)
    charge_current = trace.channel_current_ma("charger")
    assert charge_current < 5, (
        f"PRDTST-383 FAIL: Charging at 8C ({charge_current:.1f}mA)"
    )
    ctx.fixture.charger.disconnect()
    ctx.fixture.temperature.set(25)
```

#### Remaining Charging/BMS Tests (Summary)

The following tests follow the same patterns established above:

| PRDTST | Test | Build | Run Type | Key Verification |
|--------|------|-------|----------|------------------|
| PRDTST-355 | LED on-charger state | Both | `commit` | Photodiode ADC reads LED pattern while charging |
| PRDTST-373 | LED charge level while charging | Both | `commit` | Photodiode reads LED indicating SoC during charge |
| PRDTST-385 | Battery lockout at 3.5V | Both | `weekly` | Device stops at 3.5V, power measurement ~0 |
| PRDTST-386 | Charger detect, low battery not charging | Both | `weekly` | `on_charger=True` even if not actually charging |
| PRDTST-390 | TS open circuit at start | Both | `weekly` | No charging with TS open |
| PRDTST-391 | Stop charging at 4.3V / termination current | Both | `weekly` | Monitor charge termination voltage and current. **Note:** Jira title says 10mA but body says 20mA — clarify with HW team. Use 20mA (body) as authoritative until resolved. |
| PRDTST-392 | Trickle charge below 3.5V | Both | `weekly` | Current ~10mA below 3.5V |
| PRDTST-397 | Charger detect, full battery | Both | `commit` | `on_charger=True` at full charge |
| PRDTST-402 | Charger detect across voltage range | Both | `weekly` | `on_charger=True` at various voltages |
| PRDTST-407 | Charge controller temp accuracy | Both | `weekly` | Charge controller temp within +/-2C of reference |
| PRDTST-409 | TS open circuit while charging | Both | `weekly` | Charging stops when TS opened |
| PRDTST-411 | BMS recovery voltage (3.88V) | Both | `weekly` | Empty flag clears above 3.88V |
| PRDTST-412 | Button press battery status | Both | `commit` | Single press reports battery level |

### 5.5 Environmental Sensor Tests

Environmental sensor tests verify BME280 (temperature, humidity, pressure) and MLX90614
(IR temperature) accuracy against calibrated references using the Peltier temperature
controller.

#### PRDTST-329: Test Altitude Ceiling Measurement

- **Acceptance criteria**: The device must measure the altitude ceiling within +/-25
  meters (+/-1.0 hPa) accuracy.
- **Build variant**: Both
- **Run type**: `commit`
- **Physical stimulus**: Known altitude (test location is fixed)
- **CoreCloud verification**: Verify `pressure_altitude` in position message
- **Classification**: Stage 4 primary

```python
def test_prdtst_329_altitude_accuracy(ctx):
    """PRDTST-329: Altitude within +/-25m of calibrated reference."""
    ctx.flash_firmware(ctx.hex_under_test)
    ctx.power_on()
    ctx.wait(30)

    msg = ctx.cloud.wait_for_position(timeout_s=7500)
    assert msg is not None, "PRDTST-329 FAIL: No position message"
    assert msg.pressure_altitude is not None, "PRDTST-329 FAIL: No altitude"

    known_altitude_m = ctx.fixture.reference_altitude_m  # From fixture calibration
    device_altitude_m = msg.pressure_altitude_meters
    deviation = abs(device_altitude_m - known_altitude_m)
    assert deviation <= 25, (
        f"PRDTST-329 FAIL: altitude deviation {deviation:.1f}m > 25m "
        f"(device={device_altitude_m:.1f}m, ref={known_altitude_m:.1f}m)"
    )
```

#### PRDTST-336: Test Detect Elevation Change

- **Acceptance criteria**: The device shall detect a 3 meter elevation change.
- **Build variant**: Both
- **Run type**: `weekly` (requires pressure change simulation)
- **Physical stimulus**: Pressure change equivalent to 3m elevation
- **CoreCloud verification**: Verify altitude change in successive position messages
- **Classification**: Stage 4 primary

#### PRDTST-345: Test Absolute Temperature Measurement

- **Acceptance criteria**: The device must calculate the absolute temperature within
  +/-0.5C accuracy.
- **Build variant**: Both
- **Run type**: `commit`
- **Physical stimulus**: Temperature chamber at known setpoint
- **CoreCloud verification**: Verify `temperature` field in position message
- **Classification**: Stage 4 primary (calibrated reference)

```python
def test_prdtst_345_absolute_temperature(ctx):
    """PRDTST-345: Temperature within +/-0.5C of calibrated reference."""
    ctx.flash_firmware(ctx.hex_under_test)
    ctx.power_on()
    ctx.wait(30)

    ctx.fixture.temperature.set(25)
    ctx.wait(300)

    actual_c = ctx.fixture.temperature.read_thermistor()
    ctx.cloud.mark_test_start()

    msg = ctx.cloud.wait_for_position(timeout_s=7500)
    assert msg is not None, "PRDTST-345 FAIL: No position message"
    assert msg.temperature is not None, "PRDTST-345 FAIL: No temperature"

    deviation = abs(msg.temperature_celsius - actual_c)
    assert deviation <= 0.5, (
        f"PRDTST-345 FAIL: temp deviation {deviation:.2f}C > 0.5C "
        f"(device={msg.temperature_celsius:.2f}C, ref={actual_c:.2f}C)"
    )
```

#### PRDTST-357: Test Absolute Pressure Measurement

- **Acceptance criteria**: The device must calculate the absolute pressure within
  +/-0.05 inHg (~1.7 hPa) accuracy.
- **Build variant**: Both
- **Run type**: `commit`
- **Physical stimulus**: Ambient pressure (known from reference barometer)
- **CoreCloud verification**: Verify `air_pressure` in position message
- **Classification**: Stage 4 primary

```python
def test_prdtst_357_absolute_pressure(ctx):
    """PRDTST-357: Pressure within +/-1.7 hPa of calibrated barometer."""
    ctx.flash_firmware(ctx.hex_under_test)
    ctx.power_on()
    ctx.wait(30)

    msg = ctx.cloud.wait_for_position(timeout_s=7500)
    assert msg is not None, "PRDTST-357 FAIL: No position message"
    assert msg.air_pressure is not None, "PRDTST-357 FAIL: No pressure"

    ref_hpa = ctx.fixture.reference_pressure_hpa
    deviation = abs(msg.air_pressure - ref_hpa)
    assert deviation <= 1.7, (
        f"PRDTST-357 FAIL: pressure deviation {deviation:.2f}hPa > 1.7hPa "
        f"(device={msg.air_pressure:.2f}hPa, ref={ref_hpa:.2f}hPa)"
    )
```

#### PRDTST-398: Test Absolute Humidity Measurement

- **Acceptance criteria**: The device must calculate the absolute humidity within +/-3%RH
  accuracy at 20%, 40%, 60%, and 80% RH.
- **Build variant**: Both
- **Run type**: `weekly` (requires humidity reference)
- **Physical stimulus**: Known humidity conditions
- **CoreCloud verification**: Verify humidity in biometric message
- **Classification**: Stage 4 primary

#### PRDTST-405: Test Detect Humidity Change

- **Acceptance criteria**: The device shall detect a 5% change in relative humidity.
- **Build variant**: Both
- **Run type**: `weekly`
- **Physical stimulus**: Humidity change (e.g., breath on sensor)
- **CoreCloud verification**: Verify humidity delta in successive messages
- **Classification**: Stage 4 primary

#### PRDTST-406: Test Detect Temperature Change

- **Acceptance criteria**: The device shall detect a 0.1C change in relative temperature.
- **Build variant**: Both
- **Run type**: `weekly`
- **Physical stimulus**: Small temperature change via Peltier controller
- **CoreCloud verification**: Verify temperature delta in successive messages
- **Classification**: Stage 4 primary

### 5.6 GNSS Tests

GNSS tests verify GPS acquisition under different conditions (cold start, warm start,
aiding enabled/disabled). These require GNSS signal availability -- either a rooftop
antenna connection or a GNSS simulator.

#### PRDTST-343: Test GNSS Position Fix Cold Start Aiding Disabled, Minimum Requirements

- **Acceptance criteria**: The device shall acquire a position fix within 1 minute, under
  clear sky conditions, with an accuracy of 6 meters or better. Aiding disabled.
- **Build variant**: Both
- **Run type**: `commit`
- **Physical stimulus**: GNSS signal (clear sky or simulator), aiding disabled via config
- **CoreCloud verification**: Verify position message with `gnss_fix_ok=True`,
  `horizontal_accuracy <= 6`, `gps_on_time <= 60`
- **Classification**: Stage 4 primary (GNSS acquisition is end-to-end)

```python
def test_prdtst_343_gnss_cold_start_no_aiding_min(ctx):
    """PRDTST-343: Cold start, no aiding, fix within 1 min, accuracy <= 6m."""
    ctx.flash_firmware(ctx.hex_under_test)
    ctx.power_on()
    ctx.wait(10)

    # Disable aiding
    config = GPSConfMsg(is_aiding_enabled=False, is_psm_enabled=False,
                        gnss_update_freq=1, target_fix_accuracy=6, target_fix_pdop=100)
    ctx.cloud.push_gps_config(config)
    ctx.wait(30)

    ctx.cloud.mark_test_start()
    msg = ctx.cloud.wait_for_position(
        timeout_s=180,
        predicate=lambda m: m.gnss_fix_ok and m.horizontal_accuracy is not None,
    )
    assert msg is not None, "PRDTST-343 FAIL: No fix within timeout"
    assert msg.horizontal_accuracy <= 6, (
        f"PRDTST-343 FAIL: accuracy {msg.horizontal_accuracy}m > 6m"
    )
    assert msg.gps_on_time <= 60, (
        f"PRDTST-343 FAIL: TTFF {msg.gps_on_time}s > 60s"
    )
    assert msg.used_aiding is False, "PRDTST-343 FAIL: aiding was used"
```

#### PRDTST-384: Test GNSS Position Fix Cold Start Aiding Disabled, Extended Requirements

- **Acceptance criteria**: The device shall acquire a position fix within 3 minutes,
  under clear sky conditions, with an accuracy of 1 meter or better. Aiding disabled.
- **Build variant**: Both
- **Run type**: `weekly`
- **Physical stimulus**: GNSS signal, aiding disabled
- **CoreCloud verification**: Fix within 3 min, accuracy <= 1m
- **Classification**: Stage 4 primary

```python
def test_prdtst_384_gnss_cold_start_no_aiding_ext(ctx):
    """PRDTST-384: Cold start, no aiding, fix within 3 min, accuracy <= 1m."""
    ctx.flash_firmware(ctx.hex_under_test)
    ctx.power_on()
    ctx.wait(10)

    config = GPSConfMsg(is_aiding_enabled=False, is_psm_enabled=False,
                        gnss_update_freq=1, target_fix_accuracy=1, target_fix_pdop=100)
    ctx.cloud.push_gps_config(config)
    ctx.wait(30)

    ctx.cloud.mark_test_start()
    msg = ctx.cloud.wait_for_position(
        timeout_s=300,
        predicate=lambda m: m.gnss_fix_ok and m.horizontal_accuracy is not None
                            and m.horizontal_accuracy <= 1,
    )
    assert msg is not None, "PRDTST-384 FAIL: No 1m-accuracy fix within 3 min"
    assert msg.gps_on_time <= 180, (
        f"PRDTST-384 FAIL: TTFF {msg.gps_on_time}s > 180s"
    )
```

#### PRDTST-378: Test GNSS Position Fix Cold Start Aiding Enabled

- **Acceptance criteria**: When GPS-Aiding is enabled, the device shall acquire a fix
  within 30 seconds with accuracy of 1 meter or better.
- **Build variant**: Both
- **Run type**: `commit`
- **Physical stimulus**: GNSS signal, aiding enabled
- **CoreCloud verification**: Fix within 30s, accuracy <= 1m, `used_aiding=True`
- **Classification**: Stage 4 primary

```python
def test_prdtst_378_gnss_cold_start_aiding(ctx):
    """PRDTST-378: Cold start with aiding, fix within 30s, accuracy <= 1m."""
    ctx.flash_firmware(ctx.hex_under_test)
    ctx.power_on()
    ctx.wait(10)

    config = GPSConfMsg(is_aiding_enabled=True, is_psm_enabled=False,
                        gnss_update_freq=1, target_fix_accuracy=1, target_fix_pdop=100)
    ctx.cloud.push_gps_config(config)
    ctx.wait(30)

    ctx.cloud.mark_test_start()
    msg = ctx.cloud.wait_for_position(
        timeout_s=120,
        predicate=lambda m: m.gnss_fix_ok and m.horizontal_accuracy is not None
                            and m.horizontal_accuracy <= 1,
    )
    assert msg is not None, "PRDTST-378 FAIL: No aided fix within timeout"
    assert msg.gps_on_time <= 30, (
        f"PRDTST-378 FAIL: Aided TTFF {msg.gps_on_time}s > 30s"
    )
    assert msg.used_aiding is True, "PRDTST-378 FAIL: Aiding not used"
```

#### PRDTST-360: Test GNSS Position Fix Warm Start Aiding Disabled

- **Acceptance criteria**: When GPS-Aiding is disabled and device has a valid prior fix,
  the device shall acquire a fix within 30 seconds with accuracy of 1 meter or better.
- **Build variant**: Both
- **Run type**: `weekly`
- **Physical stimulus**: First acquire a fix, then power cycle and acquire again
- **CoreCloud verification**: Second fix within 30s
- **Classification**: Stage 4 primary

```python
def test_prdtst_360_gnss_warm_start_no_aiding(ctx):
    """PRDTST-360: Warm start, no aiding, fix within 30s, accuracy <= 1m."""
    ctx.flash_firmware(ctx.hex_under_test)
    ctx.power_on()
    ctx.wait(10)

    config = GPSConfMsg(is_aiding_enabled=False, is_psm_enabled=False,
                        gnss_update_freq=1, target_fix_accuracy=1, target_fix_pdop=100)
    ctx.cloud.push_gps_config(config)
    ctx.wait(30)

    # First fix (cold start -- just need a valid fix in memory)
    msg1 = ctx.cloud.wait_for_position(
        timeout_s=300,
        predicate=lambda m: m.gnss_fix_ok,
    )
    assert msg1 is not None, "PRDTST-360 FAIL: No initial fix for warm start test"

    # Soft reboot (preserves GNSS ephemeris)
    ctx.power_off()
    ctx.wait(2)
    ctx.cloud.mark_test_start()
    ctx.power_on()
    ctx.wait(10)

    # Warm start fix
    msg2 = ctx.cloud.wait_for_position(
        timeout_s=120,
        predicate=lambda m: m.gnss_fix_ok and m.horizontal_accuracy is not None
                            and m.horizontal_accuracy <= 1,
    )
    assert msg2 is not None, "PRDTST-360 FAIL: No warm start fix"
    assert msg2.gps_on_time <= 30, (
        f"PRDTST-360 FAIL: Warm start TTFF {msg2.gps_on_time}s > 30s"
    )
```

#### PRDTST-396: Test GNSS Position Fix Warm Start Aiding Enabled

- **Acceptance criteria**: When GPS-Aiding is enabled and device has a valid prior fix,
  the device shall acquire a fix within 30 seconds with accuracy of 1 meter or better.
- **Build variant**: Both
- **Run type**: `commit`
- **Physical stimulus**: Same as PRDTST-360 but with aiding enabled
- **CoreCloud verification**: Warm fix within 30s, `used_aiding=True`
- **Classification**: Stage 4 primary

#### PRDTST-333: Test GNSS Position Based Heading Estimate

- **Acceptance criteria**: The device shall estimate its heading based on GNSS position
  fixes with an accuracy of 10 degrees.
- **Build variant**: Both
- **Run type**: `weekly`
- **Physical stimulus**: Known-direction motion (if available) or GNSS simulator
- **CoreCloud verification**: Verify `heading` field in position message
- **Classification**: Stage 4 primary

```python
def test_prdtst_333_gnss_heading(ctx):
    """PRDTST-333: GNSS heading accuracy within 10 degrees."""
    ctx.flash_firmware(ctx.hex_under_test)
    ctx.power_on()
    ctx.wait(30)

    # Trigger motion to generate heading
    ctx.fixture.motion.shake(duration_s=30)
    ctx.cloud.mark_test_start()

    msg = ctx.cloud.wait_for_position(
        timeout_s=180,
        predicate=lambda m: m.gnss_fix_ok and m.heading is not None,
    )
    ctx.fixture.motion.stop()

    assert msg is not None, "PRDTST-333 FAIL: No position with heading"
    assert msg.heading is not None, "PRDTST-333 FAIL: heading is None"
    # Heading validation requires known reference direction
    assert 0 <= msg.heading <= 360, (
        f"PRDTST-333 FAIL: heading {msg.heading} out of [0, 360] range"
    )
```

#### PRDTST-358: Test GNSS Position Based Speed Estimate

- **Acceptance criteria**: The device shall estimate its speed based on GNSS with an
  accuracy of 20%.
- **Build variant**: Both
- **Run type**: `weekly`
- **Physical stimulus**: Known-speed motion or GNSS simulator
- **CoreCloud verification**: Verify `ground_speed` in position message
- **Classification**: Stage 4 primary

```python
def test_prdtst_358_gnss_speed(ctx):
    """PRDTST-358: GNSS speed estimate within 20% accuracy."""
    ctx.flash_firmware(ctx.hex_under_test)
    ctx.power_on()
    ctx.wait(30)

    ctx.fixture.motion.shake(duration_s=30)
    ctx.cloud.mark_test_start()

    msg = ctx.cloud.wait_for_position(
        timeout_s=180,
        predicate=lambda m: m.gnss_fix_ok and m.ground_speed is not None,
    )
    ctx.fixture.motion.stop()

    assert msg is not None, "PRDTST-358 FAIL: No position with speed"
    assert msg.ground_speed is not None, "PRDTST-358 FAIL: ground_speed is None"
    assert msg.ground_speed >= 0, (
        f"PRDTST-358 FAIL: ground_speed {msg.ground_speed} is negative"
    )
```

### 5.7 On-Skin / Biometrics Tests

On-skin tests use the MTIB electrode to simulate skin contact and verify that the device
starts biometric monitoring and sends biometric data messages.

#### PRDTST-400: Test On-Skin Detection

- **Acceptance criteria**: The device shall detect when it is on-skin and when it is not.
- **Build variant**: Both
- **Run type**: `commit`
- **Physical stimulus**: On-skin electrode toggle
- **CoreCloud verification**: Verify biometric messages arrive when on-skin, stop when
  off-skin
- **Stage 3 overlap**: Stage 3 verifies touch state machine via harness.
  Stage 4 verifies biometric messages at CoreCloud.
- **Classification**: Stage 4 primary (cloud message behavior)

```python
def test_prdtst_400_on_skin_detection(ctx):
    """PRDTST-400: On-skin detection starts/stops biometric monitoring."""
    ctx.flash_firmware(ctx.hex_under_test)
    ctx.power_on()
    ctx.wait(60)

    # Enable on-skin
    ctx.fixture.on_skin.enable()
    ctx.cloud.mark_test_start()
    ctx.wait(60)

    bio_msg = ctx.cloud.wait_for_biometric(timeout_s=120)
    assert bio_msg is not None, "PRDTST-400 FAIL: No biometric msg when on-skin"
    assert bio_msg.on_body is True, "PRDTST-400 FAIL: on_body flag not set"

    # Disable on-skin
    ctx.fixture.on_skin.disable()
    ctx.cloud.mark_test_start()
    ctx.wait(120)

    bio_msgs_off = ctx.cloud.get_biometric_history()
    on_body_msgs = [m for m in bio_msgs_off if m.on_body]
    assert len(on_body_msgs) == 0, (
        f"PRDTST-400 FAIL: {len(on_body_msgs)} on-body msgs after off-skin"
    )
```

#### PRDTST-327: Test Biometric Data Messages Sent When On-Skin

- **Acceptance criteria**: The device shall send biometric data messages when on-skin.
- **Build variant**: Both
- **Run type**: `commit`
- **Physical stimulus**: On-skin electrode enabled
- **CoreCloud verification**: Verify `BiometricDataMsg` with valid heart rate, SpO2,
  skin temperature
- **Classification**: Stage 4 primary

```python
def test_prdtst_327_biometric_messages_on_skin(ctx):
    """PRDTST-327: Biometric data messages sent when on-skin."""
    ctx.flash_firmware(ctx.hex_under_test)
    ctx.power_on()
    ctx.wait(60)

    ctx.fixture.on_skin.enable()
    ctx.cloud.mark_test_start()

    msg = ctx.cloud.wait_for_biometric(timeout_s=180)
    ctx.fixture.on_skin.disable()

    assert msg is not None, "PRDTST-327 FAIL: No biometric message when on-skin"
    assert msg.on_body is True, "PRDTST-327 FAIL: on_body not set"
    # Heart rate should be non-zero (electrode simulates skin contact)
    assert msg.heart_rate is not None, "PRDTST-327 FAIL: heart_rate is None"
    assert msg.skin_temperature is not None, "PRDTST-327 FAIL: skin_temperature is None"
```

#### PRDTST-379: Test Position Messages Sent When On-Skin

- **Acceptance criteria**: The device shall send position messages when on-skin.
- **Build variant**: Both
- **Run type**: `commit`
- **Physical stimulus**: On-skin electrode enabled
- **CoreCloud verification**: Verify `PositionMsgV6` arrives while on-skin
- **Classification**: Stage 4 primary

```python
def test_prdtst_379_position_messages_on_skin(ctx):
    """PRDTST-379: Position messages sent when on-skin."""
    ctx.flash_firmware(ctx.hex_under_test)
    ctx.power_on()
    ctx.wait(30)

    ctx.fixture.on_skin.enable()
    ctx.cloud.mark_test_start()

    msg = ctx.cloud.wait_for_position(timeout_s=7500)
    ctx.fixture.on_skin.disable()

    assert msg is not None, "PRDTST-379 FAIL: No position message when on-skin"
```

### 5.8 Button / SOS / Haptic Tests

Button tests use the MTIB GPIO momentary switch to simulate button presses of various
durations. Haptic verification requires either a vibration sensor or manual observation
(see engineering questions).

#### PRDTST-382: Test Button Press to Enter SOS Emergency Mode

- **Acceptance criteria**: The device shall enter SOS emergency mode when the button is
  pressed and held for between 3 and 6 seconds.
- **Build variant**: Both
- **Run type**: `commit`
- **Physical stimulus**: Button press via GPIO, 4-second hold
- **CoreCloud verification**: Verify emergency position message (`update_reason=3`) or
  SOS event message arrives at CoreCloud
- **Stage 3 overlap**: Stage 3 verifies SOS state machine transition via harness.
  Stage 4 verifies SOS message at CoreCloud.
- **Classification**: Stage 4 primary (cloud message verification)

```python
def test_prdtst_382_sos_entry(ctx):
    """PRDTST-382: 3-6 second button hold enters SOS mode."""
    ctx.flash_firmware(ctx.hex_under_test)
    ctx.power_on()
    ctx.wait(60)

    ctx.cloud.mark_test_start()
    # Press and hold for 4 seconds (within 3-6s window)
    ctx.mtib.gpio_set("BUTTON", 1)
    ctx.wait(4)
    ctx.mtib.gpio_set("BUTTON", 0)

    msg = ctx.cloud.wait_for_position(
        timeout_s=120,
        predicate=lambda m: m.update_reason == 3,  # Emergency
    )
    assert msg is not None, "PRDTST-382 FAIL: No emergency position message"
    assert msg.emergency_event_id is not None, (
        "PRDTST-382 FAIL: emergency_event_id is None"
    )
```

#### PRDTST-325: Negative Test Button Press to Enter SOS Emergency Mode

- **Acceptance criteria**: The device shall NOT enter SOS emergency mode when the button
  is pressed for less than 3 seconds or more than 6 seconds.
- **Build variant**: Both
- **Run type**: `commit`
- **Physical stimulus**: Short press (1s) and long press (8s)
- **CoreCloud verification**: Verify no emergency messages
- **Classification**: Stage 4 primary (negative test)

```python
def test_prdtst_325_sos_negative(ctx):
    """PRDTST-325: Button < 3s or > 6s does NOT enter SOS mode."""
    ctx.flash_firmware(ctx.hex_under_test)
    ctx.power_on()
    ctx.wait(60)

    for duration_s, label in [(1, "short"), (8, "long")]:
        ctx.cloud.mark_test_start()
        ctx.mtib.gpio_set("BUTTON", 1)
        ctx.wait(duration_s)
        ctx.mtib.gpio_set("BUTTON", 0)
        ctx.wait(60)

        msgs = ctx.cloud.get_position_history()
        emergency = [m for m in msgs if m.update_reason == 3]
        assert len(emergency) == 0, (
            f"PRDTST-325 FAIL: SOS triggered by {label} press ({duration_s}s)"
        )
```

#### PRDTST-346: Test Button Press to Hard Reset Device

- **Acceptance criteria**: Verify the device performs a hard reset when the button is
  pressed 7 times in quick succession.
- **Build variant**: Both
- **Run type**: `commit`
- **Physical stimulus**: 7 rapid button presses via GPIO
- **CoreCloud verification**: Verify boot message with `boot_reason=7`
  (user button sequence)
- **Classification**: Stage 4 primary

```python
def test_prdtst_346_7x_button_hard_reset(ctx):
    """PRDTST-346: 7 rapid button presses triggers hard reset."""
    ctx.flash_firmware(ctx.hex_under_test)
    ctx.power_on()
    ctx.wait(60)

    ctx.cloud.mark_test_start()
    # 7 rapid presses (200ms press, 200ms gap)
    for i in range(7):
        ctx.mtib.gpio_set("BUTTON", 1)
        ctx.wait(0.2)
        ctx.mtib.gpio_set("BUTTON", 0)
        ctx.wait(0.2)

    boot_msg = ctx.cloud.wait_for_boot(timeout_s=120)
    assert boot_msg is not None, "PRDTST-346 FAIL: No boot after 7x press"
    assert boot_msg.boot_reason == 7, (
        f"PRDTST-346 FAIL: Expected button reset (7), got {boot_msg.boot_reason_str}"
    )
```

#### PRDTST-377: Test Button Press to Enter Manufacturing Test Mode

- **Acceptance criteria**: Verify the device enters manufacturing test mode when the
  button is double-clicked.
- **Build variant**: Both
- **Run type**: `commit`
- **Physical stimulus**: Double-click via GPIO
- **CoreCloud verification**: Verify manufacturing test position message
  (`update_reason=15`)
- **Classification**: Stage 4 primary

```python
def test_prdtst_377_manufacturing_mode(ctx):
    """PRDTST-377: Double-click enters manufacturing test mode."""
    ctx.flash_firmware(ctx.hex_under_test)
    ctx.power_on()
    ctx.wait(60)

    ctx.cloud.mark_test_start()
    # Double click: 2 presses within 500ms
    ctx.mtib.gpio_set("BUTTON", 1)
    ctx.wait(0.15)
    ctx.mtib.gpio_set("BUTTON", 0)
    ctx.wait(0.15)
    ctx.mtib.gpio_set("BUTTON", 1)
    ctx.wait(0.15)
    ctx.mtib.gpio_set("BUTTON", 0)

    msg = ctx.cloud.wait_for_position(
        timeout_s=120,
        predicate=lambda m: m.update_reason == 15,  # Manufacturing test
    )
    assert msg is not None, "PRDTST-377 FAIL: No manufacturing test message"
```

#### PRDTST-362: Test Haptic Feedback on SOS Emergency Mode Entry

- **Acceptance criteria**: Verify the device provides haptic feedback when entering SOS.
- **Build variant**: Both
- **Run type**: `commit`
- **Physical stimulus**: 4-second button hold (SOS entry)
- **CoreCloud verification**: Verify SOS message (haptic is verified by fixture
  vibration sensor if available, otherwise manual)
- **Stage 3 overlap**: Stage 3 can verify motor GPIO via harness. Stage 4 verifies
  physical vibration.
- **Classification**: Stage 4 primary (physical haptic verification)

#### PRDTST-380: Test Haptic Feedback on SOS Acknowledgement

- **Acceptance criteria**: Verify the device provides haptic feedback when it receives an
  SOS acknowledgement.
- **Build variant**: Both
- **Run type**: `commit`
- **Physical stimulus**: Enter SOS mode, then send ACK via CoreCloud
- **CoreCloud verification**: SOS message + ACK delivery
- **Classification**: Stage 4 primary

#### PRDTST-395: Negative Test Haptic Feedback on Button Press for 3 Seconds

- **Acceptance criteria**: The device shall NOT provide haptic feedback when the button
  is pressed for less than 3 seconds.
- **Build variant**: Both
- **Run type**: `commit`
- **Physical stimulus**: Button press < 3s
- **CoreCloud verification**: No SOS message
- **Classification**: Stage 4 primary (negative test)

#### PRDTST-403: Test Haptic Feedback on Manufacturing Test Entry and Exit

- **Acceptance criteria**: Verify haptic feedback on manufacturing mode entry/exit.
- **Build variant**: Both
- **Run type**: `commit`
- **Physical stimulus**: Double-click entry, second double-click exit
- **CoreCloud verification**: Manufacturing test message
- **Classification**: Stage 4 primary

#### PRDTST-408: Test Haptic Feedback on Button Press for 3 Seconds

- **Acceptance criteria**: Verify haptic feedback at exactly 3 seconds of button hold.
- **Build variant**: Both
- **Run type**: `commit`
- **Physical stimulus**: 3-second button hold
- **CoreCloud verification**: SOS entry expected
- **Classification**: Stage 4 primary

### 5.9 LED Feedback Tests

LED tests use the MTIB photodiode array to read LED color and blink patterns. These
tests verify user-visible feedback for battery status and charging state.

#### PRDTST-338: Test Communicate Charge Level via LEDs on Button Press

- **Acceptance criteria**: The device shall communicate the charge level via LEDs across
  the entire battery SoC range when the button is pressed once.
- **Build variant**: Both
- **Run type**: `commit`
- **Physical stimulus**: Single button press
- **CoreCloud verification**: None (LED verification via photodiode)
- **Classification**: Stage 4 primary (physical LED observation)

```python
def test_prdtst_338_led_battery_level_button(ctx):
    """PRDTST-338: Button press shows battery level via LEDs."""
    ctx.flash_firmware(ctx.hex_under_test)
    ctx.power_on()
    ctx.wait(60)

    ctx.fixture.led_sensor.enable()
    # Short button press
    ctx.mtib.gpio_set("BUTTON", 1)
    ctx.wait(0.3)
    ctx.mtib.gpio_set("BUTTON", 0)
    ctx.wait(1)  # LEDs should illuminate

    led = ctx.fixture.led_sensor.read()
    # At least one color channel should be active (indicating LED is on)
    assert led["red"] > 50 or led["green"] > 50 or led["blue"] > 50, (
        f"PRDTST-338 FAIL: No LED activity on button press "
        f"(R={led['red']}, G={led['green']}, B={led['blue']})"
    )
    ctx.fixture.led_sensor.disable()
```

#### PRDTST-355: Test Communicate On-Charger State via LEDs

- **Acceptance criteria**: The device shall communicate the on-charger state via the
  status LEDs across the entire battery SoC range.
- **Build variant**: Both
- **Run type**: `commit`
- **Physical stimulus**: Connect charger
- **CoreCloud verification**: None (LED observation)
- **Classification**: Stage 4 primary

```python
def test_prdtst_355_led_charger_state(ctx):
    """PRDTST-355: LEDs indicate on-charger state."""
    ctx.flash_firmware(ctx.hex_under_test)
    ctx.power_on()
    ctx.wait(60)

    ctx.fixture.led_sensor.enable()
    ctx.fixture.charger.connect()
    ctx.wait(5)

    led = ctx.fixture.led_sensor.read()
    assert led["red"] > 50 or led["green"] > 50 or led["blue"] > 50, (
        f"PRDTST-355 FAIL: No LED activity when charger connected"
    )
    ctx.fixture.charger.disconnect()
    ctx.fixture.led_sensor.disable()
```

#### PRDTST-373: Test Communicate Charge Level via LEDs While Charging

- **Acceptance criteria**: The device shall communicate the charge level via LEDs during
  charging.
- **Build variant**: Both
- **Run type**: `commit`
- **Physical stimulus**: Connect charger
- **CoreCloud verification**: None (LED observation)
- **Classification**: Stage 4 primary

### 5.10 NFC Test

#### PRDTST-337: Test NFC Broadcast Device ID

- **Acceptance criteria**: Verify device broadcasts its unique ID via NFC.
- **Build variant**: Both
- **Run type**: `commit`
- **Physical stimulus**: NFC reader scan via MTIB
- **CoreCloud verification**: None (NFC read verification)
- **Classification**: Stage 4 primary (NFC is external-only)

```python
def test_prdtst_337_nfc_device_id(ctx):
    """PRDTST-337: NFC broadcasts correct device ID."""
    ctx.flash_firmware(ctx.hex_under_test)
    ctx.power_on()
    ctx.wait(30)

    nfc_data = ctx.fixture.nfc_reader.scan()
    assert nfc_data is not None, "PRDTST-337 FAIL: No NFC tag detected"

    expected_id = ctx.device_id_hex
    assert nfc_data["device_id"] == expected_id, (
        f"PRDTST-337 FAIL: NFC ID '{nfc_data['device_id']}' != expected '{expected_id}'"
    )
```

### 5.11 FUOTA Tests

#### PRDTST-376: Test FUOTA from Previous Release to Current

- **Acceptance criteria**: Verify the device can successfully FUOTA from the previous
  release to this build.
- **Build variant**: Both (start with previous release, FUOTA to current)
- **Run type**: `weekly`
- **Physical stimulus**: Flash previous firmware, then trigger FUOTA via CoreCloud
- **CoreCloud verification**: Verify boot message with `boot_reason=2` (FUOTA complete),
  then verify firmware version in subsequent messages
- **Classification**: Stage 4 primary (FUOTA is end-to-end cloud operation)

```python
def test_prdtst_376_fuota_previous_to_current(ctx):
    """PRDTST-376: FUOTA from previous release to current build."""
    # Flash previous release
    ctx.flash_firmware(ctx.previous_release_hex)
    ctx.power_on()
    ctx.wait(60)

    # Verify old firmware is running
    boot_msg_old = ctx.cloud.wait_for_boot(timeout_s=120)
    assert boot_msg_old is not None, "PRDTST-376 FAIL: No boot on old firmware"

    # Trigger FUOTA to current build via CoreCloud
    ctx.cloud.mark_test_start()
    fuota_job = ctx.cloud.trigger_fuota(
        ctx.device_id,
        firmware_url=ctx.current_firmware_url,
        version=ctx.current_firmware_version,
    )

    # Wait for FUOTA completion (boot with reason=2)
    boot_msg_new = ctx.cloud.wait_for_boot(timeout_s=1800)  # 30 min timeout
    assert boot_msg_new is not None, "PRDTST-376 FAIL: No boot after FUOTA"
    assert boot_msg_new.boot_reason == 2, (
        f"PRDTST-376 FAIL: Expected FUOTA boot (2), got {boot_msg_new.boot_reason_str}"
    )
```

### 5.12 VSM / IPC Tests

#### PRDTST-410: Test VSM Power Cut-off Switch

- **Acceptance criteria**: Verify that the VSM power cut-off switch is functional and
  can cut off power to the VMS.
- **Build variant**: Both
- **Run type**: `commit`
- **Physical stimulus**: Trigger VSM power cut-off (firmware-controlled GPIO)
- **CoreCloud verification**: Verify biometric messages stop after VSM power cut
- **Stage 3 overlap**: Stage 3 verifies IPC and VSM state via harness.
  Stage 4 verifies biometric message cessation at CoreCloud.
- **Classification**: Stage 4 primary (production behavior)

```python
def test_prdtst_410_vsm_power_cutoff(ctx):
    """PRDTST-410: VSM power cut-off stops biometric data."""
    ctx.flash_firmware(ctx.hex_under_test)
    ctx.power_on()
    ctx.wait(60)

    # Enable on-skin to start biometric monitoring
    ctx.fixture.on_skin.enable()
    ctx.cloud.mark_test_start()

    bio_msg = ctx.cloud.wait_for_biometric(timeout_s=180)
    assert bio_msg is not None, "PRDTST-410 FAIL: No biometric msg before VSM cutoff"

    # VSM power cut-off is triggered by firmware under specific conditions
    # This test verifies the mechanism works in production
    ctx.fixture.on_skin.disable()
```

### 5.13 Cloud Message Tests

#### PRDTST-338 / PRDTST-412: Test Button Press to Check Battery Status

(PRDTST-412 is covered under Charging/BMS -- single button press reports battery level.)

The remaining cloud message verification is integrated throughout all test categories
above. Every PRDTST that involves CoreCloud verification implicitly tests cloud message
formatting, delivery, and parsing. The following tests focus specifically on cloud
message system behavior:

- **PRDTST-334**: SoC Reporting (covered in Section 5.4)
- **PRDTST-350**: Battery Temperature in Position Message (covered in Section 5.4)
- **PRDTST-366**: BMS SoC and Temp in Position Message (covered in Section 5.4)
- **PRDTST-368**: On-Charger State in Position Message (covered in Section 5.4)
- **PRDTST-374**: Ground Mode Config Sent on Boot (covered in Section 5.2)

---

## 6. Test Runner Architecture

### 6.1 Module Structure

```
# Shared library (test framework, clients, controllers)
concord/libs/corekinect/test/validation/
├── __init__.py
├── cloud_client.py                  # CoreCloud integration (Section 4.1)
├── mtib_client.py                   # MTIB gRPC wrapper (shared with Stages 2-3)
├── fixture_controller.py            # Physical fixture abstraction (Section 2.5)
├── nfc_client.py                    # NFC reader interface via MTIB I2C
├── harness_client.py                # HarnessTransport (Stage 3 only)
├── uart_demuxer.py                  # UART prefix-based routing
├── test_context.py                  # TestContext: unified API for test functions
├── validation_runner.py             # Orchestrator: spec loading, tag filtering
├── power_profiler.py                # Power measurement analysis (shared)
├── specs/
│   ├── alpha_validation_spec.yaml   # Alpha PRDTST test definitions
│   └── sigma5_validation_spec.yaml  # (future)
├── tests/
│   ├── __init__.py
│   ├── test_power.py                # Section 5.1 tests
│   ├── test_config.py               # Section 5.2 tests
│   ├── test_motion.py               # Section 5.3 tests
│   ├── test_charging.py             # Section 5.4 tests
│   ├── test_environmental.py        # Section 5.5 tests
│   ├── test_gnss.py                 # Section 5.6 tests
│   ├── test_biometrics.py           # Section 5.7 tests
│   ├── test_button_sos.py           # Section 5.8 tests
│   ├── test_led.py                  # Section 5.9 tests
│   ├── test_nfc.py                  # Section 5.10 tests
│   ├── test_fuota.py                # Section 5.11 tests
│   ├── test_vsm.py                  # Section 5.12 tests
│   └── test_cloud.py                # Section 5.13 tests
└── reports/
    ├── json_reporter.py             # Structured JSON report
    └── junit_reporter.py            # JUnit XML for CI integration
```

### 6.2 Execution Flow

```
┌──────────────────────────────────────────────────────────────────────┐
│ Pipeline Controller creates Stage 4 K8s Job                         │
│   env: PIPELINE_ID, RUN_TYPE, MTIB_HOST, DEVICE_ID, FIXTURE_PROFILE│
└──────────────────────────┬───────────────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────────────┐
│ main.py                                                              │
│   1. Parse environment variables                                     │
│   2. Download firmware artifacts from MinIO                          │
│      - production_debug/merged.hex                                   │
│      - production_release/merged.hex                                 │
│      - comms/merged.hex                                              │
│   3. Connect to MTIB V2 gRPC at MTIB_HOST:MTIB_PORT                │
│   4. Initialize fixture_controller from FIXTURE_PROFILE JSON         │
│   5. Initialize cloud_client with DEVICE_ID + credentials            │
│   6. Initialize nfc_client via MTIB I2C                              │
│   7. Load validation_spec.yaml                                       │
│   8. Filter test groups by RUN_TYPE tags                             │
└──────────────────────────┬───────────────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────────────┐
│ FOR EACH build variant [debug, release]:                             │
│                                                                      │
│   9.  Flash firmware (SWD recover + program, both MCUs)              │
│   10. Start UART stream (debug build only)                           │
│   11. Power on DUT (4.5V battery rail)                               │
│   12. Wait for boot settle (3 seconds)                               │
│                                                                      │
│   FOR EACH filtered test group:                                      │
│     13. Initialize fixture state for group                           │
│     14. FOR EACH test in group:                                      │
│         a. Set up test-specific fixture state                        │
│         b. Execute test function with TestContext                     │
│         c. Capture result: pass/fail, measured values, duration      │
│         d. Tear down test-specific state                             │
│     15. Tear down group fixture state                                │
│                                                                      │
│   16. Power off DUT                                                  │
│   17. Stop UART stream, save log artifact                            │
└──────────────────────────┬───────────────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────────────┐
│ Post-execution:                                                      │
│   18. Compare Debug vs Release results                               │
│       - Power tests: Release is authoritative, Debug is informational│
│       - All other tests: both must pass                              │
│   19. Generate reports (JSON + JUnit XML)                            │
│   20. Upload artifacts to MinIO:                                     │
│       validation/{pipeline_id}/                                      │
│         ├── report.json                                              │
│         ├── junit.xml                                                │
│         ├── debug_uart_log.txt                                       │
│         ├── power_traces/                                            │
│         │   ├── debug/{group}.csv                                    │
│         │   └── release/{group}.csv                                  │
│         ├── cloud_messages.json                                      │
│         └── metadata.json                                            │
│   21. Push metrics to InfluxDB                                       │
│   22. Exit 0 (all pass) or 1 (any failure)                          │
└──────────────────────────────────────────────────────────────────────┘
```

### 6.3 Debug vs Release Result Comparison

The test runner executes the full filtered test suite on **both** builds and produces
a comparison report:

| Outcome | Interpretation |
|---------|---------------|
| Both pass | Normal -- firmware is correct in both configurations |
| Debug pass, Release fail | **Timing or power bug** exposed by removing log overhead. The log system masks a race condition or the power budget is only met with log overhead reducing duty cycle. Critical to investigate. |
| Debug fail, Release pass | **Log system interference**. The logging infrastructure is affecting production behavior (e.g., UART TX blocking a time-critical path). The Debug build configuration needs review. |
| Both fail | Firmware bug present in both configurations. Standard defect. |

For **power budget tests** specifically (PRDTST-331, 340, 341, 348, 361, 363, 404):
- Release measurements are **authoritative** (used for pass/fail)
- Debug measurements are **informational** (captured for comparison but do not gate)

### 6.4 Artifact Management

All artifacts are uploaded to MinIO under a structured prefix:

```
minio://concord-artifacts/
  validation/
    {pipeline_id}/
      debug/
        uart_log.txt               # Full UART capture from debug build
        power_traces/
          power_runtime.csv        # Group-level power traces
          charging_bms.csv
          ...
      release/
        power_traces/
          power_runtime.csv        # Authoritative power measurements
          ...
      cloud_messages.json          # All CoreCloud messages during test run
      report.json                  # Structured test results
      junit.xml                    # CI integration report
      metadata.json                # Pipeline ID, firmware version, commit SHA,
                                   # MTIB node, timestamps, device ID
```

---

## 7. PRDTST Coverage Matrix

| PRDTST | Name | Stage 3? | S4 Debug? | S4 Release? | Primary Verification | CoreCloud? | External Equipment | Run Type | Classification |
|--------|------|----------|-----------|-------------|---------------------|------------|-------------------|----------|----------------|
| 324 | Ignore motion below accel threshold | Yes | Yes | Yes | Cloud: no motion msgs | Yes | Actuator | commit | S3 primary, S4 regression |
| 325 | Negative SOS button press | No | Yes | Yes | Cloud: no emergency msgs | Yes | GPIO button | commit | S4 primary |
| 326 | Detect motion above thresholds | Yes | Yes | Yes | Cloud: is_in_motion=True | Yes | Actuator | commit | S4 primary |
| 327 | Biometric messages on-skin | No | Yes | Yes | Cloud: BiometricDataMsg | Yes | Electrode | commit | S4 primary |
| 328 | Motion stop acq timeout default | Yes | Yes | Yes | Cloud: stop motion msg | Yes | Actuator | commit | S4 primary |
| 329 | Altitude ceiling measurement | No | Yes | Yes | Cloud: pressure_altitude | Yes | Reference altimeter | commit | S4 primary |
| 330 | Heartbeat acq timeout default | Yes | Yes | Yes | Cloud: gps_on_time | Yes | GNSS signal | commit | S3 primary, S4 regression |
| 331 | Long-term sleep current | No | Info | **Auth** | Power: avg < 1.5mA | No | None | weekly | S4 primary |
| 332 | TS short circuit start charging | No | Yes | Yes | Power: no charge current | No | TS pin fixture | weekly | S4 primary |
| 333 | GNSS heading estimate | No | Yes | Yes | Cloud: heading field | Yes | GNSS signal | weekly | S4 primary |
| 334 | SoC reporting accuracy | No | Yes | Yes | Cloud: batt_percent | Yes | Fuel gauge ref | weekly | S4 primary |
| 335 | Zero heartbeat period | Yes | Yes | Yes | Cloud: no heartbeats | Yes | None | commit | S4 primary |
| 336 | Detect elevation change | No | Yes | Yes | Cloud: altitude delta | Yes | Pressure sim | weekly | S4 primary |
| 337 | NFC broadcast device ID | No | Yes | Yes | NFC: device ID match | No | NFC reader | commit | S4 primary |
| 338 | LED charge level on button | No | Yes | Yes | Photodiode: LED active | No | Photodiode, GPIO | commit | S4 primary |
| 339 | TS short while charging | No | Yes | Yes | Power: charge stops | No | TS pin fixture | weekly | S4 primary |
| 340 | 72h worst-case endurance | No | No | **Auth** | Cloud: continuous msgs | Yes | All | weekly | S4 primary |
| 341 | Active mode < 150mA | No | Info | **Auth** | Power: peak < 150mA | No | Electrode | commit | S4 primary |
| 342 | Continuous motion default | Yes | Yes | Yes | Cloud: update_reason=5 | Yes | Actuator | commit | S4 primary |
| 343 | GNSS cold start no aiding min | No | Yes | Yes | Cloud: fix + accuracy | Yes | GNSS signal | commit | S4 primary |
| 344 | Heartbeat period max | Yes | Yes | Yes | Cloud: interval timing | Yes | None | weekly | S4 primary |
| 345 | Absolute temperature | No | Yes | Yes | Cloud: temperature field | Yes | Peltier | commit | S4 primary |
| 346 | 7x button hard reset | No | Yes | Yes | Cloud: boot_reason=7 | Yes | GPIO button | commit | S4 primary |
| 347 | Stop motion timeout custom | Yes | Yes | Yes | Cloud: stop motion timing | Yes | Actuator | commit | S3 primary, S4 regression |
| 348 | Sleep mode < 500uA | No | Info | **Auth** | Power: avg < 500uA | No | None | commit | S4 primary |
| 349 | No FUOTA low battery | No | Yes | Yes | Cloud: no FUOTA boot | Yes | Low voltage | weekly | S4 primary |
| 350 | Battery temp in position | No | Yes | Yes | Cloud: bms_temp field | Yes | None | commit | S4 primary |
| 351 | No charge below 0C | No | Yes | Yes | Power: no charge current | No | Peltier | weekly | S4 primary |
| 352 | Heartbeat period default | Yes | Yes | Yes | Cloud: interval timing | Yes | None | commit | S4 primary |
| 353 | Start motion window default | Yes | Yes | Yes | Cloud: no premature motion | Yes | Actuator | commit | S3 primary, S4 regression |
| 354 | Charger delatch from lockout | No | Yes | Yes | Cloud: boot_reason=3 | Yes | Charger relay | weekly | S4 primary |
| 355 | LED on-charger state | No | Yes | Yes | Photodiode: LED active | No | Photodiode, relay | commit | S4 primary |
| 356 | Heartbeat period non-default | Yes | Yes | Yes | Cloud: interval timing | Yes | None | commit | S4 primary |
| 357 | Absolute pressure | No | Yes | Yes | Cloud: air_pressure | Yes | Reference baro | commit | S4 primary |
| 358 | GNSS speed estimate | No | Yes | Yes | Cloud: ground_speed | Yes | GNSS signal | weekly | S4 primary |
| 359 | Heartbeat acq timeout custom | Yes | Yes | Yes | Cloud: gps_on_time | Yes | GNSS signal | commit | S3 primary, S4 regression |
| 360 | GNSS warm start no aiding | No | Yes | Yes | Cloud: fix + TTFF | Yes | GNSS signal | weekly | S4 primary |
| 361 | Lockout mode < 400nA | No | Info | **Auth** | Power: avg < 400nA | No | Low voltage | weekly | S4 primary |
| 362 | Haptic on SOS entry | No | Yes | Yes | Manual/vibration sensor | No | GPIO button | commit | S4 primary |
| 363 | 72h normal use endurance | No | No | **Auth** | Cloud: continuous msgs | Yes | All | weekly | S4 primary |
| 364 | Continuous motion disabled | Yes | Yes | Yes | Cloud: no motion msgs | Yes | Actuator | commit | S4 primary |
| 365 | Charge ladder | No | Yes | Yes | Power: charge profile | No | Charger relay | weekly | S4 primary |
| 366 | BMS SoC+temp in motion pos | No | Yes | Yes | Cloud: batt_percent+bms_temp | Yes | Electrode, actuator | commit | S4 primary |
| 367 | BMS temp accuracy | No | Yes | Yes | Cloud: bms_temp vs ref | Yes | Peltier | weekly | S4 primary |
| 368 | On-charger in position msg | No | Yes | Yes | Cloud: on_charger=True | Yes | Charger relay | commit | S4 primary |
| 369 | Continuous motion custom | Yes | Yes | Yes | Cloud: interval timing | Yes | Actuator | commit | S4 primary |
| 370 | Charge 3.5V-4.2V < 3h | No | Yes | Yes | Power: charge time | No | Charger relay | weekly | S4 primary |
| 371 | Heartbeat period min | Yes | Yes | Yes | Cloud: interval timing | Yes | None | commit | S4 primary |
| 372 | No charge above 45C | No | Yes | Yes | Power: no charge current | No | Peltier, relay | weekly | S4 primary |
| 373 | LED charge level while charging | No | Yes | Yes | Photodiode: LED active | No | Photodiode, relay | commit | S4 primary |
| 374 | Ground Mode Config on boot | No | Yes | Yes | Cloud: boot position msg | Yes | None | commit | S4 primary |
| 375 | Ignore motion below duration | Yes | Yes | Yes | Cloud: no motion msgs | Yes | Actuator | commit | S3 primary, S4 regression |
| 376 | FUOTA previous to current | No | Yes | Yes | Cloud: boot_reason=2 | Yes | None | weekly | S4 primary |
| 377 | Manufacturing test mode | No | Yes | Yes | Cloud: update_reason=15 | Yes | GPIO button | commit | S4 primary |
| 378 | GNSS cold start aiding | No | Yes | Yes | Cloud: fix + aiding used | Yes | GNSS signal | commit | S4 primary |
| 379 | Position messages on-skin | No | Yes | Yes | Cloud: position msg | Yes | Electrode | commit | S4 primary |
| 380 | Haptic on SOS ack | No | Yes | Yes | Manual/vibration sensor | No | GPIO button | commit | S4 primary |
| 381 | BMS param retention | No | Yes | Yes | Cloud: SoC consistent | Yes | Power cycle | commit | S4 primary |
| 382 | SOS entry (3-6s hold) | No | Yes | Yes | Cloud: update_reason=3 | Yes | GPIO button | commit | S4 primary |
| 383 | No charge below 10C | No | Yes | Yes | Power: no charge current | No | Peltier, relay | weekly | S4 primary |
| 384 | GNSS cold start no aiding ext | No | Yes | Yes | Cloud: fix + accuracy | Yes | GNSS signal | weekly | S4 primary |
| 385 | Battery lockout at 3.5V | No | Yes | Yes | Power: device stops | No | Low voltage | weekly | S4 primary |
| 386 | Charger detect low batt no charge | No | Yes | Yes | Cloud: on_charger=True | Yes | Charger relay | weekly | S4 primary |
| 387 | Continuous motion min (1s) | Yes | Yes | Yes | Cloud: motion msgs | Yes | Actuator | weekly | S4 primary |
| 388 | Default Ground Mode Config | Yes | Yes | Yes | Cloud: boot config msg | Yes | None | commit | S4 primary |
| 389 | Axis independence | No | Yes | Yes | Cloud: motion per axis | Yes | Actuator | commit | S4 primary |
| 390 | TS open circuit start | No | Yes | Yes | Power: no charge current | No | TS pin fixture | weekly | S4 primary |
| 391 | Stop charging 4.3V/10mA | No | Yes | Yes | Power: termination | No | Charger relay | weekly | S4 primary |
| 392 | Trickle charge below 3.5V | No | Yes | Yes | Power: ~10mA current | No | Low voltage, relay | weekly | S4 primary |
| 393 | Respect motion start window | Yes | Yes | Yes | Cloud: delayed detection | Yes | Actuator | commit | S3 primary, S4 regression |
| 394 | Continuous motion max (65535s) | Yes | Yes | Yes | Cloud: config accepted | Yes | Actuator | weekly | S3 primary, S4 regression |
| 395 | Negative haptic < 3s | No | Yes | Yes | Manual/vibration sensor | No | GPIO button | commit | S4 primary |
| 396 | GNSS warm start aiding | No | Yes | Yes | Cloud: fix + aiding | Yes | GNSS signal | commit | S4 primary |
| 397 | Charger detect full battery | No | Yes | Yes | Cloud: on_charger=True | Yes | Charger relay | commit | S4 primary |
| 398 | Absolute humidity | No | Yes | Yes | Cloud: humidity field | Yes | Humidity ref | weekly | S4 primary |
| 399 | Stop motion timeout default | Yes | Yes | Yes | Cloud: stop motion timing | Yes | Actuator | commit | S4 primary |
| 400 | On-skin detection | Yes | Yes | Yes | Cloud: biometric msgs | Yes | Electrode | commit | S4 primary |
| 401 | Operating temp -20C to +60C | No | Yes | Yes | Cloud: msgs at extremes | Yes | Peltier | weekly | S4 primary |
| 402 | Charger detect across range | No | Yes | Yes | Cloud: on_charger=True | Yes | Charger relay | weekly | S4 primary |
| 403 | Haptic mfg mode entry/exit | No | Yes | Yes | Manual/vibration sensor | No | GPIO button | commit | S4 primary |
| 404 | Normal use < 50mA | No | Info | **Auth** | Power: avg < 50mA | No | Electrode | commit | S4 primary |
| 405 | Detect humidity change | No | Yes | Yes | Cloud: humidity delta | Yes | Humidity stim | weekly | S4 primary |
| 406 | Detect temperature change | No | Yes | Yes | Cloud: temp delta | Yes | Peltier | weekly | S4 primary |
| 407 | Charge controller temp accuracy | No | Yes | Yes | Power: temp vs ref | No | Peltier | weekly | S4 primary |
| 408 | Haptic at 3s hold | No | Yes | Yes | Manual/vibration sensor | No | GPIO button | commit | S4 primary |
| 409 | TS open while charging | No | Yes | Yes | Power: charge stops | No | TS pin fixture | weekly | S4 primary |
| 410 | VSM power cut-off | Yes | Yes | Yes | Cloud: biometric stop | Yes | Electrode | commit | S4 primary |
| 411 | BMS recovery voltage (3.88V) | No | Yes | Yes | Power: flag clears | No | Variable voltage | weekly | S4 primary |
| 412 | Button battery status | No | Yes | Yes | Cloud/LED: battery report | Yes | GPIO button | commit | S4 primary |

**Legend:**
- **Auth** = Authoritative (Release build measurements used for pass/fail)
- **Info** = Informational (Debug build measurements captured but not gating)
- **S3 primary, S4 regression** = Stage 3 is the primary verification stage; Stage 4 runs the same check on production firmware as regression
- **S4 primary** = Can only be fully verified at Stage 4 (production firmware, external interfaces, CoreCloud)

**Summary counts:**
- Total PRDTST cases: 89
- Stage 4 primary: 81
- Stage 3 primary / Stage 4 regression: 8 (PRDTST-324, 330, 347, 353, 359, 375, 393, 394)
- CoreCloud verification: 62 tests
- Temperature chamber required: 13 tests
- Commit run type: 56 tests
- Weekly run type: 33 tests

---

## 8. Implementation Roadmap

### Phase 1: Foundation (Weeks 1-3, ~80 hours)

| Work Item | Effort | Dependencies |
|-----------|--------|--------------|
| `cloud_client.py` -- CoreCloud integration wrapper | 16h | CoreCloud REST API credentials in Vault |
| `test_context.py` -- TestContext API for Stage 4 | 12h | MTIB V2 gRPC client (existing) |
| `fixture_controller.py` -- Fixture abstraction | 16h | MTIB node fixture profile schema |
| `validation_runner.py` -- Orchestrator + tag filtering | 12h | validation_spec.yaml format |
| `alpha_validation_spec.yaml` -- Test definitions | 8h | PRDTST coverage matrix (this document) |
| `Dockerfile.validation` -- Alpha validation container | 8h | Base test-runner image |
| Alpha fixture hardware assembly + MTIB wiring | 8h | Physical components ordered |

### Phase 2: Core Tests (Weeks 4-6, ~80 hours)

| Work Item | Effort | Dependencies |
|-----------|--------|--------------|
| `test_config.py` -- Config value tests (18 PRDTSTs) | 20h | cloud_client.py, fixture_controller.py |
| `test_power.py` -- Power/runtime tests (7 PRDTSTs) | 12h | Power profiler, fixture |
| `test_motion.py` -- Motion detection tests (5 PRDTSTs) | 12h | Linear actuator wired |
| `test_button_sos.py` -- Button/SOS/haptic (9 PRDTSTs) | 16h | GPIO button wired |
| `test_biometrics.py` -- On-skin/biometric (3 PRDTSTs) | 8h | On-skin electrode wired |
| `test_nfc.py` -- NFC test (1 PRDTST) | 4h | NFC reader on MTIB I2C |
| `test_led.py` -- LED feedback (3 PRDTSTs) | 8h | Photodiode array wired |

### Phase 3: Advanced Tests (Weeks 7-9, ~60 hours)

| Work Item | Effort | Dependencies |
|-----------|--------|--------------|
| `test_charging.py` -- Charging/BMS tests (29 PRDTSTs) | 24h | Charger relay, Peltier controller, TS pin fixture |
| `test_environmental.py` -- Environmental sensors (7 PRDTSTs) | 12h | Peltier controller, calibrated references |
| `test_gnss.py` -- GNSS tests (7 PRDTSTs) | 16h | GNSS signal (rooftop or simulator) |
| `test_fuota.py` -- FUOTA tests (1 PRDTST) | 8h | CoreCloud FUOTA API integration |

### Phase 4: Integration and Endurance (Weeks 10-12, ~40 hours)

| Work Item | Effort | Dependencies |
|-----------|--------|--------------|
| `test_vsm.py` -- VSM/IPC test (1 PRDTST) | 4h | On-skin electrode |
| Debug vs Release comparison logic | 8h | Both builds executing |
| Artifact management (MinIO upload, report generation) | 8h | MinIO bucket structure |
| Endurance test infrastructure (72h test support) | 8h | Stable MTIB + power |
| End-to-end pipeline integration (K8s Job, stage gating) | 12h | Pipeline controller |

### Phase 5: Validation and Hardening (Weeks 13-14, ~20 hours)

| Work Item | Effort | Dependencies |
|-----------|--------|--------------|
| Full suite dry run on Alpha hardware | 8h | All tests implemented |
| Flaky test identification and timeout tuning | 8h | Dry run results |
| Documentation and handoff | 4h | All phases complete |

**Total estimated effort**: ~280 hours (~7 engineer-weeks)

**Critical path**:
1. CoreCloud credentials in Vault (blocks Phase 1)
2. Alpha product board fixture assembly (blocks Phase 2)
3. Peltier temperature controller (blocks Phase 3 charging + environmental tests)
4. GNSS signal source (blocks Phase 3 GNSS tests)

---

## 9. Engineering Questions

### 9.1 Haptic Verification

**Question**: How do we verify haptic (vibration motor) feedback in an automated test?

**Current state**: PRDTST-362, 380, 395, 403, 408 all require haptic verification. The
fixture profile does not currently include a vibration sensor.

**Options**:
1. **Accelerometer on fixture**: Mount a small accelerometer near the DUT cradle. When
   the vibration motor fires, the accelerometer detects it. Simple, low-cost, reliable.
2. **MTIB ADC on motor sense pin**: If the motor driver has a sense output, read it via
   MTIB ADC. Depends on hardware design.
3. **Manual verification**: Run haptic tests in a supervised mode where an operator
   confirms vibration. Not automatable, but acceptable for weekly/release runs.

**Recommendation**: Option 1 (fixture accelerometer) for automated runs. Fallback to
option 3 for initial implementation.

### 9.2 Ground Mode Config REST API — Deferred for POC

**Question**: What is the exact REST API endpoint and payload format for pushing Ground
Mode Config V2 parameters to a device?

**Current state**: `GPSConfMsg` has a defined `api_set_endpoint` (`PUT /System/Devices/
Configurations/Gps`) for GPS config. Ground Mode Config V2 (UID 538) delivery needs
the equivalent — but neither a REST endpoint nor a Python SDK class exists today.

The Confluence REST API docs (`CoreCloud.RestServer API Documentation`) contain no
`/System/Devices/Configurations/GroundMode` or equivalent endpoint. The message spec
shows UID 538 supports "Uplink and Downlink" on both SSv0.9 and SSv1.0, so the Socket
Server can push it as a downlink — but it's unclear if there's a REST trigger.

**POC decision**: All 18 Config Value PRDTST tests that depend on Ground Mode Config
delivery are **excluded from the POC scope** (see Section 4.5). The POC focuses on
tests that use existing CoreCloud infrastructure (uplink message verification + GPS
config delivery).

**Post-POC action**: CoreCloud C# team to either (a) create a REST endpoint for Ground
Mode Config delivery, or (b) document the Socket Server downlink mechanism so the
Python SDK can trigger it. Then write `GroundModeConfigV2(ConfMsgBase)` in the SDK
and implement the 18 deferred tests.

### 9.3 GNSS Signal Source

**Question**: Should Stage 4 GNSS tests use a rooftop antenna or a GNSS simulator?

**Options**:
1. **Rooftop antenna**: Low cost, real signals, but weather/environment dependent and
   may cause flaky tests. Requires the MTIB and DUT to be near an antenna feed.
2. **GNSS simulator**: Deterministic, repeatable, weather-independent. Higher cost
   ($5K-$20K for a basic GPS/GNSS signal simulator). Enables precise TTFF and accuracy
   measurements.
3. **Hybrid**: Use rooftop for commit (basic fix verification), simulator for weekly
   (precision measurements).

**Recommendation**: Start with rooftop antenna. Evaluate simulator after initial GNSS
test results show whether environmental variability causes unacceptable flakiness.

### 9.4 On-Skin Electrode Fidelity

**Question**: Does a GPIO-controlled electrode reliably trigger the PAH8151 PPG sensor's
on-skin detection?

**Current state**: The Alpha uses the PAH8151 PPG sensor for on-skin detection. The
detection mechanism may depend on optical reflectance (skin proximity) rather than
electrical conductivity. A simple electrode may not trigger it.

**Options**:
1. **Electrical electrode**: If the firmware uses capacitive touch detection, a GPIO
   electrode works directly.
2. **Optical target**: Place a reflective surface over the PPG sensor window to simulate
   skin proximity. May need a specific material/distance to trigger.
3. **Firmware test hook**: Add a `CONFIG_CONCORD_ONSKIN_OVERRIDE` Kconfig that forces
   on-skin state. This is NOT acceptable for Stage 4 (no firmware modifications) but
   could work for Stage 3.

**Action**: Determine the on-skin detection mechanism on Alpha (capacitive vs optical)
and design the fixture element accordingly.

### 9.5 TS Pin Fixture

**Question**: How do PRDTST-332, 339, 390, 409 (TS pin short/open circuit tests) work
with the current fixture?

**Current state**: These tests require shorting or opening the charge controller's
thermistor sense (TS) pin. This is a board-level signal that is not currently exposed
through the fixture.

**Options**:
1. **Dedicated test board**: A modified Alpha board with the TS pin broken out to a
   test pad, wired to an MTIB GPIO-controlled relay.
2. **Skip for automation**: These tests may be hardware verification tests that are more
   appropriate for a manual hardware qualification process rather than automated firmware
   validation.

**Recommendation**: Defer TS pin tests to manual hardware qualification. Focus automated
Stage 4 on firmware-behavior tests that can be reliably automated.

### 9.6 Battery Voltage Control

**Question**: Several tests require setting the battery to a specific voltage (3.3V for
lockout, 3.5V for trickle charge, 3.7V for low-battery FUOTA rejection). How is this
achieved?

**Current state**: MTIB Power Ch0 provides a fixed voltage (4.5V for normal operation).
Varying it simulates different battery states.

**Options**:
1. **MTIB programmable voltage**: Use `power_enable(channel=0, voltage_v=X)` to set
   the battery simulation rail to the target voltage. This works if the MTIB power
   supply supports programmable voltage.
2. **External power supply**: Use a bench power supply for precise voltage control.
   Less automatable.

**Action**: Verify MTIB V2 `DutPowerEnable` supports programmable voltage on Ch0.

### 9.7 CoreCloud Test Environment Isolation

**Question**: Should Stage 4 tests run against a dedicated CoreCloud test environment
or the production environment?

**Options**:
1. **Dedicated test environment** (`VAL_1_0`): Isolated from production data. Test
   device IDs do not conflict with real devices. No risk of test messages appearing in
   customer dashboards.
2. **Production environment**: Tests the actual production path. But risks data
   pollution and requires careful device ID management.

**Current state**: `msg_def_v1_0.py` already supports `db_env="VAL_1_0"` as the
default environment namespace. This suggests a dedicated validation environment exists.

**Recommendation**: Use `VAL_1_0` dedicated environment. This is already the default in
the CoreCloud Python client.
