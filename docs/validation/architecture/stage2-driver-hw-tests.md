# Stage 2 Implementation Architecture: Driver Hardware Tests

> Implementation blueprint for the Stage 2 driver hardware validation pipeline.
> This document specifies what must be built, how components fit together,
> the interfaces between them, and a concrete implementation roadmap.
>
> **Not an example.** For a walkthrough of what a Stage 2 test run looks like
> end-to-end, see [12-stage2-alpha-example.md](../examples/alpha/stage2-alpha-example.md).
> This document is the engineering specification for building the system
> described there.

---

## 1. Scope and Goals

### 1.1 What Stage 2 Proves That Stage 1 Cannot

Stage 1 runs on `native_sim` with stub drivers. It proves that application logic is correct given known sensor inputs. It cannot prove anything about real hardware interaction.

Stage 2 runs on real silicon via MTIB. It proves:

- **Bus communication works.** SPI/I2C transactions succeed on real hardware with real timing, real signal integrity, and real electrical characteristics.
- **The driver initializes correctly.** The full init sequence (reset, WHO_AM_I, register configuration from DTS properties) completes on the actual chip.
- **Interrupts fire.** GPIO wiring, interrupt polarity, edge detection, and GPIOTE all work end-to-end. Pulsed vs latched mode behaves as configured.
- **FIFO hardware behaves correctly.** Batching at configured ODR, watermark interrupt at correct sample count, data tags and sample ordering match the datasheet.
- **Power consumption matches datasheet budgets.** Sleep current, active current, and transition current are within spec. Catches gross anomalies: gyro left running, sensor stuck in high-performance mode, pull-ups drawing excess current.
- **The DTS binding maps correctly to hardware.** Every DTS property (`accel-odr`, `accel-range`, `int-pin`, `drdy-pulsed`, etc.) produces the correct register configuration on the real chip.

### 1.2 What Stage 2 Does NOT Cover

- Multi-sensor interaction (LSM6DSO + PAH8151 + BME280 sharing resources) -- that is Stage 3.
- Application state machine behavior -- that is Stage 1 (stubs) and Stage 3 (integration).
- Product-level specification compliance -- that is Stage 4.

### 1.3 Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Driver repo | `accel_drv` (Sigma's accelerometer repo). New branch, clean architecture. | Existing repo, already a Zephyr module. Only LSM6DSO implemented initially. |
| DTS vendor prefix | `ck,` for all CoreKinect bindings | Consistent with existing `ck,lsm6dso` binding in the driver repo. |
| Dev-kit fixture | nRF52840-DK + sensor breakout boards (LSM6DSO, LIS2DE12). MTIB relays select which chip is powered. | Isolates single-sensor current draw. Simple, reproducible, uses commodity dev kits. |
| `CONFIG_CK_LSM6DSO_TRIGGER` | Deferred -- wait for new accel driver interface design | Trigger infrastructure works but the API surface is changing. Test trigger via direct register configuration + GPIO observation for now. |
| Stage gating | Stage 1 must pass before Stage 2 runs | Fail fast, fail cheap. Don't occupy an MTIB node if the software tests already caught a regression. |

---

## 2. Hardware Architecture

### 2.1 Dev-Kit Fixture Design

The dev-kit fixture is simple: an nRF52840-DK + LSM6DSO dev kit (breakout board) wired together and connected to an MTIB test head. MTIB provides all external control — flashing, UART, power relay, current sense, GPIO observation. Only one sensor is powered at a time via MTIB power relays for chip-level isolation.

When additional chips are added (LIS2DE12), they get a second breakout board on the same fixture. Each sensor slot has its own MTIB relay channel and current sense channel. The fixture design details (LDO voltage selection, sense resistor value, level shifting, PCB layout) are deferred to the hardware engineering team — this document specifies only what the test infrastructure needs from the fixture.

### 2.2 Per-Chip Power Isolation via MTIB Relays

The fixture supports multiple sensor breakout slots. Each slot connects to an independent MTIB relay channel for power control and an MTIB current sense channel for power measurement. Only one relay is closed at a time during test execution.

```
MTIB Test Head                              Dev-Kit Fixture
+-----------------------+                   +---------------------------------------------+
|                       |                   |                                             |
|  DUT_POWER    -----------------------------> nRF52840-DK power                         |
|                       |                   |                                             |
|  RELAY_0 + ISENSE_0  ----> [power ckt] ---> Sensor A (LSM6DSO breakout)               |
|  RELAY_1 + ISENSE_1  ----> [power ckt] ---> Sensor B (LIS2DE12 breakout, future)      |
|                       |                   |                                             |
|  SWD          -----------------------------> nRF52840-DK J-Link                        |
|  UART0        -----------------------------> nRF52840 UART0 (P0.23 TX, P0.25 RX)      |
|  GND          -----------------------------> Common GND                                 |
|                       |                   |                                             |
|  GPIO_0 (optional)    ----> passive tap ---> LSM6DSO INT2 (P0.14)                      |
|  GPIO_1 (optional)    ----> passive tap ---> LIS2DE12 INT (TBD)                        |
+-----------------------+                   +---------------------------------------------+
```

Everything goes through MTIB — the test runner never touches the hardware directly:

1. **Flashing** → `FlashProgram` gRPC via MTIB SWD channel.
2. **UART / ztest output** → `UartStream` gRPC via MTIB UART channel.
3. **Power on/off sensor** → `GpioSet` gRPC on MTIB relay channel (close = power on, open = power off). Only one sensor relay closed at a time.
4. **Power measurement** → `PowerMeasure` gRPC on the MTIB current sense channel for the active sensor.
5. **MCU power** → `DutPowerEnable` gRPC via MTIB DUT power channel.
6. **Interrupt observation** (optional) → `GpioRead`/`GpioStream` gRPC on MTIB GPIO tap channels.

Between test runs for different chips, the runner opens the current relay, waits for discharge, then closes the next chip's relay.

### 2.3 MCU-to-Sensor Wiring

**Sensor A: LSM6DSO (SPI)**

Mirrors the Alpha board's SPI0 pinctrl exactly, so the same driver code runs on both:

| Signal | nRF52840 Pin | LSM6DSO Pin | Notes |
|--------|-------------|-------------|-------|
| SCK | P0.07 | SPC | SPI clock, 1 MHz (matches Alpha `spi-max-frequency`) |
| MOSI | P0.05 | SDI | Master out, sensor data in |
| MISO | P1.08 | SDO | Sensor data out, master in |
| CS | P0.08 | CS | Active low. `reg = <0>` on dev-kit (only device on SPI0), `reg = <1>` on Alpha (second after flash) |
| IRQ | P0.14 | INT2 | Active high, edge-triggered, pulsed mode. Matches Alpha `int-pin = <2>` |

**Sensor B: LIS2DE12 (I2C)**

Uses the nRF52840-DK's I2C1 peripheral (same pins as Alpha I2C1 for Sigma5 compatibility):

| Signal | nRF52840 Pin | LIS2DE12 Pin | Notes |
|--------|-------------|--------------|-------|
| SDA | P1.05 | SDA | I2C data |
| SCL | P1.03 | SCL | I2C clock, 400 kHz |
| IRQ | P1.06 | INT1 | Active high (TBD -- depends on LIS2DE12 DTS binding) |

LIS2DE12 I2C address: 0x19 (SA0 pulled high on breakout) or 0x18 (SA0 low).

### 2.4 MTIB Connection Map

| MTIB Channel | Target | Purpose |
|-------------|--------|---------|
| SWD | nRF52840-DK debug port (J-Link on-board) | Flash test firmware via `FlashProgram` gRPC. J-Link bridges SWD to MTIB test head. |
| UART0 | nRF52840 UART0 (P0.23 TX, P0.25 RX) | Bidirectional stream for ztest markers. 115200 baud. Parser extracts `START`/`PASS`/`FAIL`/`SKIP` lines. |
| Relay A + ISENSE A | Sensor A VDD rail (LSM6DSO) | Relay controls sensor power. Current sense provides continuous measurement via `PowerMeasure` gRPC. |
| Relay B + ISENSE B | Sensor B VDD rail (LIS2DE12) | Same as above, for the second sensor slot. |
| GPIO CH0 (optional) | P0.14 / LSM6DSO INT2 | Passive tap for MTIB-side interrupt timing measurement. Not required for basic tests. |
| GPIO CH1 (optional) | P1.06 / LIS2DE12 INT1 | Same, for LIS2DE12 interrupt. |
| DUT power | nRF52840-DK VDD | MCU power. Always on when fixture is active. |
| GND | Common ground | Shared between MCU, sensors, and MTIB. |

### 2.5 MTIB Fixture Profile

The fixture profile maps abstract test runner actions to physical MTIB commands. Stored in the Concord `Node.fixtureProfile` field (PostgreSQL) for each dev-kit MTIB node.

```json
{
  "fixture_type": "devkit",
  "mcu": "nrf52840",
  "sensors": {
    "lsm6dso": {
      "slot": "A",
      "bus": "spi",
      "power_relay": { "mtib_channel": "RELAY_0", "on": "CLOSE", "off": "OPEN" },
      "current_sense": { "mtib_channel": "ISENSE_0", "resistor_ohm": 10.0 },
      "gpio_tap": { "mtib_channel": "GPIO_0" }
    },
    "lis2de12": {
      "slot": "B",
      "bus": "i2c",
      "power_relay": { "mtib_channel": "RELAY_1", "on": "CLOSE", "off": "OPEN" },
      "current_sense": { "mtib_channel": "ISENSE_1", "resistor_ohm": 10.0 },
      "gpio_tap": { "mtib_channel": "GPIO_1" }
    }
  },
  "uart": { "mtib_channel": "UART_0", "baud": 115200 },
  "swd": { "mtib_channel": "SWD_0" },
  "mcu_power": { "mtib_channel": "DUT_POWER", "voltage_v": 3.3 }
}
```

**Abstract action mapping:**

| Abstract Action | Physical MTIB RPCs |
|----------------|-------------------|
| `power_on_sensor(chip="lsm6dso")` | `GpioSet(RELAY_1, LOW)` (open LIS2DE12 relay), wait 10ms, `GpioSet(RELAY_0, HIGH)` (close LSM6DSO relay) |
| `power_off_sensor(chip="lsm6dso")` | `GpioSet(RELAY_0, LOW)` (open LSM6DSO relay) |
| `start_power_measure(chip="lsm6dso")` | `PowerMeasure(stream=true, channel=ISENSE_0)` |
| `flash_firmware(hex_path)` | `FlashProgram(hex_path, interface=SWD_0)` |
| `start_uart()` | `UartStream(channel=UART_0, baud=115200)` |
| `power_on_mcu()` | `DutPowerEnable(channel=DUT_POWER, voltage=3.3)` |

---

## 3. Test Firmware Architecture

### 3.1 Repository Structure

The driver repo (`accel_drv`) adopts the following layout on the new branch:

```
accel_drv/
├── drivers/lsm6dso/                       # Fresh custom driver (NOT a fork of upstream Zephyr driver)
│   └── src/
│       ├── lsm6dso.c                      # driver implementation (sensor_driver_api)
│       ├── lsm6dso.h                      # driver data structures, config
│       ├── lsm6dso_reg.h                  # ST register definitions
│       └── lsm6dso_reg.c                  # ST platform-independent register access
├── dts/bindings/                          # Sensor DT bindings OWNED by this repo
│   ├── ck,lsm6dso.yaml                   # Binding: accel/gyro config, IRQ, power modes
│   └── ck,lsm6dso-stub.yaml              # Stub binding for native_sim
├── stubs/                                 # Stub implementations for ALL drivers in this group
│   ├── lsm6dso_stub.c                    # sensor_driver_api stub for Stage 1
│   ├── Kconfig                            # CONFIG_CK_LSM6DSO_STUB
│   └── CMakeLists.txt
├── tests/                                 # Zephyr-native test code (C, ztest, Twister metadata)
│   ├── interface/                         # Interface contract tests (native_sim via stubs)
│   │   ├── testcase.yaml                  # platform_allow: native_sim
│   │   └── src/main.c
│   ├── lsm6dso/                           # Chip-specific HW tests (Stage 2, product-agnostic)
│   │   ├── src/main.c                     # ztest firmware -- ALL hardware tests
│   │   ├── src/test_helpers.h             # register read/write helpers, callback flags
│   │   ├── testcase.yaml                  # NO product boards — pipeline decides
│   │   ├── test_spec.yaml                 # power budgets from DATASHEET
│   │   └── CMakeLists.txt
├── .concord/                              # Pipeline infrastructure (Concord-specific config)
│   ├── pipeline.yaml                      # targets, triggers, stages, notifications
│   └── build.yaml                         # build recipe (how to compile tests for each board)
└── zephyr/module.yml                      # Registers repo as Zephyr module
```

This matches the canonical layout from [00-validation-philosophy.md](./00-validation-philosophy.md) Section 3.1c. The branch nukes everything — no legacy code, no backward compatibility.

### 3.2 Test Firmware Design Principles

**1. All tests in one source file per chip.**

`tests/lsm6dso/src/main.c` contains every test for the LSM6DSO. DTS preprocessor guards (`#if DT_ON_BUS(...)`, `#if DT_NODE_HAS_PROP(...)`) conditionally compile tests based on the target board's wiring. One source file produces different binaries per board.

**2. Three-level test hierarchy.**

Tests are organized by what they exercise:

| Level | When | Examples |
|-------|------|---------|
| **Core** (always compiled) | Every board, regardless of bus or interrupt wiring | `test_device_ready`, `test_sensor_presence`, `test_accel_data_readback` |
| **Bus-specific** (`#if DT_ON_BUS`) | Compiled only for the wired bus type | `test_spi_whoami`, `test_spi_register_write_readback` (SPI boards) |
| **Interrupt-dependent** (`#if DT_NODE_HAS_PROP(irq_gpios)`) | Compiled only if the board wires an interrupt pin | `test_drdy_interrupt`, `test_fifo_watermark_interrupt`, `test_fifo_batch_at_52hz` |
| **Runtime-conditional** (`zassume_true`) | Always compiled, skipped at runtime if precondition fails | `test_motion_interrupt` (needs physical stimulus) |

**3. Register-level vs API-level: use both, for different purposes.**

- **Zephyr sensor API** (`sensor_sample_fetch`, `sensor_channel_get`, `sensor_trigger_set`): Used for tests that verify the driver's public interface works end-to-end. These are the "does the driver work as a Zephyr sensor" tests.
- **Direct register access** (via `read_register` / `write_register` helpers): Used when the test needs to configure hardware state that the driver API doesn't expose, or to verify register contents independently of the driver's interpretation. Examples: FIFO configuration, power mode verification, raw WHO_AM_I bypass.

Direct register access helpers use the driver config struct to get the SPI/I2C bus spec, then perform raw bus transactions:

```c
static int read_register(const struct device *dev, uint8_t reg, uint8_t *val)
{
    const struct lsm6dso_config *cfg = dev->config;
    uint8_t tx[2] = { reg | 0x80, 0x00 };   /* SPI read: bit 7 set */
    uint8_t rx[2] = { 0 };
    /* ... spi_transceive_dt(&cfg->bus.spi, ...) ... */
    *val = rx[1];
    return ret;
}
```

**4. State cleanup between tests: use `before` and `after` hooks.**

The example doc (`12-stage2-alpha-example.md`) has a known issue: direct register writes in one test (e.g., FIFO configuration in `test_fifo_watermark_interrupt`) leave hardware state that conflicts with subsequent tests. The architecture requires explicit cleanup.

Implementation: Use ztest `before` and `after` suite hooks:

```c
static void lsm6dso_hw_before(void *fixture)
{
    /* Reset sensor to known state before each test.
     * Option A: Software reset via CTRL3_C.SW_RESET bit.
     * Option B: Write known-good register values to all config registers.
     * Option A is preferred -- it matches the chip's POR state. */
    const struct device *dev = get_dev();
    write_register(dev, LSM6DSO_CTRL3_C, 0x01);  /* SW_RESET */
    k_sleep(K_MSEC(10));  /* Wait for reset to complete (datasheet: 50us typ) */

    /* Re-initialize driver state after hardware reset */
    /* The driver init function runs at boot but doesn't re-run after a
     * software reset. Call the driver's init path explicitly or accept
     * that post-reset register state is POR defaults (all zeros except
     * CTRL3_C.IF_INC=1, BDU=0). */
}

static void lsm6dso_hw_after(void *fixture)
{
    /* Disable all interrupt routing to avoid ghost interrupts during
     * the next test's setup phase. */
    const struct device *dev = get_dev();
    write_register(dev, LSM6DSO_INT1_CTRL, 0x00);
    write_register(dev, LSM6DSO_INT2_CTRL, 0x00);
    write_register(dev, LSM6DSO_MD1_CFG, 0x00);
    write_register(dev, LSM6DSO_MD2_CFG, 0x00);

    /* Disable FIFO */
    write_register(dev, LSM6DSO_FIFO_CTRL4, 0x00);

    /* Power down accel and gyro */
    write_register(dev, LSM6DSO_CTRL1_XL, 0x00);
    write_register(dev, LSM6DSO_CTRL2_G, 0x00);
}

ZTEST_SUITE(lsm6dso_hw, NULL, NULL, lsm6dso_hw_before, lsm6dso_hw_after, NULL);
```

**5. Trigger tests: deferred but structurally prepared.**

`CONFIG_CK_LSM6DSO_TRIGGER` is deferred pending the new driver interface design. However, the test firmware already exercises interrupts via direct register configuration:

- DRDY interrupt: Configured via direct writes to `CTRL1_XL` (set ODR) and `INT2_CTRL` (route DRDY to INT2). Verified by checking that the GPIO callback fires.
- FIFO watermark: Configured via `FIFO_CTRL1/3/4` and `INT2_CTRL`. Callback verified.
- Motion wake-up: Configured via `WAKE_UP_THS`, `WAKE_UP_DUR`, `MD2_CFG`. Callback verified.

When `CONFIG_CK_LSM6DSO_TRIGGER` is finalized, tests should migrate from direct register configuration to the `sensor_trigger_set()` API. The `before`/`after` hooks and callback infrastructure remain the same.

### 3.3 Known Bugs in the Example Document to Fix

These bugs are documented in `12-stage2-alpha-example.md` and must be addressed in the actual implementation:

| Bug | Location | Fix |
|-----|----------|-----|
| `wm_callback` never registered via `sensor_trigger_set` | `test_fifo_watermark_interrupt` | The test configures FIFO watermark via direct register writes and routes to INT2 via `INT2_CTRL`, but the GPIO ISR in the driver only dispatches to registered `sensor_trigger_set` callbacks. Fix: either register a watermark trigger callback via `sensor_trigger_set`, or wire the GPIO ISR to set `wm_fired` directly by adding a raw GPIO callback. For the initial implementation, use a raw GPIO callback on P0.14 that sets `wm_fired = true` whenever INT2 fires, bypassing the driver's trigger dispatch. |
| No teardown between tests | Multiple tests | Direct register writes in `test_fifo_watermark_interrupt` (FIFO mode, batch rate, INT2 routing) persist into subsequent tests. Fix: `lsm6dso_hw_after` hook (see Section 3.2 above). |
| `test_accel_data_readback` gravity assertion missing | `test_accel_data_readback` | The test checks that "at least one axis is non-zero" but does not verify that the Z-axis magnitude is approximately 1g. Fix: add a gravity magnitude check. The example doc includes a z_mg computation but no assertion on it. Add: `zassert_true(z_mg > 500 && z_mg < 1500, "Gravity magnitude out of range: %d mg", z_mg);` after converting to milli-g (but note sensor_value is m/s^2, so convert: 1g = 9.81 m/s^2). |
| Dev-kit fixture design not specified | Section 2 of example doc | Section 2.1 now defines the fixture concept (nRF52840-DK + sensor dev kit via MTIB). Detailed electrical design (LDO, sense resistor, level shifting, PCB layout) deferred to HW engineering team. |

### 3.4 Test Ordering

ztest does not guarantee execution order across `ZTEST()` macros. The architecture does not depend on test ordering because the `before` hook resets hardware state before every test. However, for power profiling, the test runner needs clean power state boundaries. The recommended convention:

1. **Core tests first** (quick, establish basic connectivity).
2. **Bus-specific tests** (verify raw communication).
3. **Interrupt / FIFO tests** (longer, more complex hardware interaction).
4. **Power profiling tests last** (need the longest clean measurement windows).

To enforce ordering in ztest, use `ZTEST_F` with a priority annotation or split into separate `ZTEST_SUITE` groups that execute in declaration order. For the initial implementation, a single suite with `before`/`after` hooks is sufficient -- ordering is a nice-to-have, not a requirement, because each test starts from a reset state.

### 3.5 prj.conf for Test Firmware

```kconfig
# tests/lsm6dso/prj.conf

# Zephyr test framework
CONFIG_ZTEST=y
CONFIG_ZTEST_NEW_API=y

# Sensor subsystem
CONFIG_SENSOR=y

# LSM6DSO driver
CONFIG_CK_LSM6DSO=y
# CONFIG_CK_LSM6DSO_TRIGGER is NOT set -- deferred pending interface redesign

# SPI (LSM6DSO on dev-kit uses SPI; I2C boards override via overlay)
CONFIG_SPI=y

# GPIO for interrupt line (direct GPIO callback, not driver trigger)
CONFIG_GPIO=y

# Clean UART output -- ztest markers only
CONFIG_LOG=n
CONFIG_BOOT_BANNER=n
CONFIG_PRINTK=y
CONFIG_EARLY_CONSOLE=n

# Stack sizes
CONFIG_MAIN_STACK_SIZE=4096
CONFIG_SYSTEM_WORKQUEUE_STACK_SIZE=2048
```

---

## 4. Test Runner Architecture

The test runner is a Python application that runs in a K8s pod on an agent node. It is **driver-agnostic** -- the same code runs for LSM6DSO, LIS2DE12, PAH8151, or any future driver. It receives pre-built artifacts and an MTIB endpoint, and produces standardized outputs.

### 4.1 Module Structure

All modules live in the Concord monorepo at `apps/validation/test-runner/src/`:

| Module | Responsibility |
|--------|---------------|
| `main.py` | Entry point. Reads environment variables, dispatches by stage. For Stage 2: runs `driver_hw_runner()`. |
| `mtib_client.py` | Thin gRPC wrapper around MTIB V2 RPCs: `FlashProgram`, `UartStream`, `PowerMeasure`, `GpioSet`, `DutPowerEnable`, `DutPowerDisable`. Handles connection lifecycle and error retry. |
| `ztest_parser.py` | Parses ztest UART markers from the UART stream. Emits structured events: `TestStarted(name, timestamp)`, `TestResult(name, verdict, duration, timestamp)`, `SuiteComplete(name, passed, failed, skipped)`. |
| `power_profiler.py` | Runs `PowerMeasure` stream concurrently with UART. Receives timestamped current samples. When `ztest_parser` emits `TestStarted`/`TestResult`, slices the power trace at those boundaries. Computes per-test statistics (avg, peak, min, energy). |
| `test_spec_evaluator.py` | Loads `test_spec.yaml` and `board_features.json`. For each test in the spec, evaluates: (a) `required` / `required_when` conditions against board features, (b) power budget assertions against measured power (only if `TEST_MODE=full`), (c) timeout violations. Produces a coverage report. |
| `artifact_manager.py` | Uploads artifacts to MinIO with structured prefix. Pushes power stats to InfluxDB. |
| `report_generator.py` | Generates JUnit XML (with power data extensions), `summary.json`, `coverage.json`, `metadata.json`. |
| `fixture_controller.py` | Reads the MTIB node's fixture profile. Translates abstract actions (`power_on_sensor`, `start_power_measure`) to physical MTIB RPCs. For dev-kit fixtures: manages relay state, selects correct current sense channel for the chip under test. |

### 4.2 Execution Flow

```
 1. STARTUP
    - Read env: PIPELINE_ID, STAGE, JOB_ID, MINIO_URL, BUILD_ARTIFACT_PATH,
      MTIB_HOST, MTIB_PORT, PRODUCT, BOARD, DRIVER, CHIP, TEST_MODE
    - Download from MinIO: test firmware hex, test_spec.yaml, board_features.json

 2. CONNECT
    - mtib_client.connect(MTIB_HOST, MTIB_PORT)
    - fixture_controller.load_profile(mtib_node_fixture_profile)

 3. FLASH
    - fixture_controller.power_on_mcu()                         # MCU always powered
    - fixture_controller.power_off_sensor(chip=CHIP)             # ensure sensor is off
    - mtib_client.flash_program(hex_path)                        # flash via J-Link/SWD
    - fixture_controller.power_on_sensor(chip=CHIP)              # power on the sensor under test

 4. START STREAMS (concurrent)
    - uart_stream = mtib_client.uart_stream(baud=115200)         # bidirectional gRPC stream
    - power_stream = fixture_controller.start_power_measure(chip=CHIP)  # correct ISENSE channel
    - parser = ztest_parser.ZtestParser(uart_stream)
    - profiler = power_profiler.PowerProfiler(power_stream)

 5. BOOT WAIT
    - Wait for parser to see "Running TESTSUITE" or "START -" within 30s
    - If timeout: ABORT with "firmware boot timeout"

 6. TEST EXECUTION LOOP
    For each event from parser:
      - TestStarted(name, ts):
          profiler.mark_test_start(name, ts)
      - TestResult(name, verdict, duration, ts):
          profiler.mark_test_end(name, ts)
          record result (name, verdict, duration)
      - SuiteComplete:
          break

 7. SHUTDOWN
    - fixture_controller.power_off_sensor(chip=CHIP)
    - mtib_client.dut_power_disable()
    - Stop UART and power streams

 8. EVALUATION
    - profiler.compute_statistics()          # per-test: avg_ua, peak_ua, min_ua, energy_uj
    - evaluator = test_spec_evaluator.evaluate(
        spec=test_spec,
        board_features=board_features,
        test_results=results,
        power_stats=profiler.stats,
        test_mode=TEST_MODE
      )
    - Produces: coverage_report, power_report, timeout_report

 9. ARTIFACTS
    - report_generator.generate_junit_xml(results, power_stats)
    - artifact_manager.upload_to_minio(
        prefix="validation/pipelines/{pipeline_id}/stages/driver_hw/{job_id}/",
        files=[junit.xml, uart_log.txt, power/*.csv, summary.json,
               coverage.json, metadata.json, test_spec.yaml, board_features.json]
      )
    - artifact_manager.push_to_influxdb(power_stats, metadata)

10. EXIT
    - Exit 0 if: all required tests PASS, no coverage gaps,
      power within budget (if TEST_MODE=full), no timeouts
    - Exit 1 if: any FAIL, any coverage gap, any budget violation (full mode),
      any timeout, boot failure
```

### 4.3 UART Parsing

The parser uses anchored regexes that match only ztest-formatted lines. All non-matching lines are captured in `uart_log.txt` but ignored for result parsing.

```python
ZTEST_START_RE  = re.compile(r"^\s*START - (\S+)\s*$")
ZTEST_RESULT_RE = re.compile(r"^\s*(PASS|FAIL|SKIP) - (\S+) in (\d+\.\d+) seconds\s*$")
ZTEST_SUITE_RE  = re.compile(r"^Running TESTSUITE (\S+)\s*$")
ZTEST_END_RE    = re.compile(r"^PROJECT EXECUTION (SUCCESSFUL|FAILED)\s*$")
ZTEST_SUMMARY_RE = re.compile(r"^SUITE (PASS|FAIL)")
```

Each UART line arrives with an MTIB-assigned timestamp (MTIB server clock). The parser pairs `START` and `PASS/FAIL/SKIP` lines by test name and records both timestamps. These timestamps are the power slice boundaries.

### 4.4 Power Profiling Pipeline

```
MTIB PowerMeasure stream (continuous, ~10kHz+)
    |
    v
power_profiler.py accumulates timestamped (t_mtib, current_ua) samples
    |
    +--- on mark_test_start(name, t_start):
    |       record t_start for this test
    |
    +--- on mark_test_end(name, t_end):
    |       slice samples where t_start - 50ms <= t <= t_end + 50ms
    |       compute: avg_ua, peak_ua, min_ua, energy_uj, duration_s
    |       store as per-test power trace CSV
    |
    +--- on compute_statistics():
            for each test with a power slice:
              emit stats to summary dict
            emit full_trace.csv (all samples, unsliced)
```

**Timing alignment:** Both UART and power streams use MTIB server timestamps (same clock). Alignment is within ~1ms. The 50ms margin on each side of the power slice window ensures full transient capture.

**Per-test power trace CSV format:**

```
timestamp_us,current_ua
0,2.81
100,2.79
200,2.83
...
```

Timestamps are relative to the slice start (0 = test start - 50ms margin).

### 4.5 Timeout Handling

| Timeout | Source | Behavior |
|---------|--------|----------|
| Session boot timeout (30s) | Hardcoded in runner | If no `TESTSUITE`/`START` marker within 30s of power-on, abort. Verdict: FAIL, reason: "firmware boot timeout". |
| Per-test timeout | `test_spec.yaml` `timeout_s` field (default: 60s from `defaults.timeout_s`) | If a `START` marker is seen but no `PASS/FAIL/SKIP` within `timeout_s`, abort the current test. Verdict: FAIL, reason: "test timeout". |
| Overall Job timeout (600s) | K8s `activeDeadlineSeconds` on the Job spec | K8s kills the pod. Hard backstop for runaway tests. |

---

## 5. Data Formats

### 5.1 test_spec.yaml Schema

```yaml
version: 1                          # schema version

metadata:
  chip: string                      # e.g., "LSM6DSO"
  datasheet_ref: string             # e.g., "LSM6DSO datasheet Rev 9, Table 4"
  author: string
  last_reviewed: string             # ISO 8601 date

defaults:
  timeout_s: integer                # default per-test timeout (seconds)

tests:
  <test_function_name>:             # must match the ztest function name exactly
    required: "always" | false      # "always" = must appear in output for every board
                                    # false = optional, no coverage judgment
    required_when:                  # conditional requirement (mutually exclusive with required)
      bus: "spi" | "i2c"           # test required when board wires this bus
      has_prop: string             # test required when DTS node has this property
      not_has_prop: string         # test required when DTS node lacks this property
      kconfig: string              # test required when this Kconfig symbol is enabled
    timeout_s: integer             # override per-test timeout
    power_budget:                  # power assertions (evaluated only when TEST_MODE=full)
      avg_ua: number               # average current must be <= this value
      peak_ua: number              # peak current must be <= this value
      min_ua: number               # minimum current must be >= this value (catches stuck-off)
      energy_uj: number            # total energy must be <= this value
```

**Evaluation rules:**

- `required: "always"` -- test must appear in ztest output. If absent: COVERAGE_GAP.
- `required_when: { bus: spi }` -- test must appear if `board_features.features.bus == "spi"`. If the board uses I2C, test is NOT_APPLICABLE (not a gap).
- `required_when: { has_prop: irq_gpios }` -- test must appear if `"irq_gpios"` is in `board_features.features.has_prop` array.
- `required: false` -- test may or may not appear. Never a gap.
- If a test appears in ztest output but is not in `test_spec.yaml`: UNEXPECTED (noted, not an error).
- `power_budget` fields are only evaluated when `TEST_MODE=full`. When `TEST_MODE=functional`, power stats are computed and stored but `budget_pass` is set to `null`.

### 5.2 board_features.json Schema

Generated at build time by `scripts/extract_board_features.py`, which parses the compiled DTS output (`build/zephyr/zephyr.dts`) and extracts feature flags for the sensor node.

```json
{
  "board": "devkit_nrf52840_lsm6dso_spi",
  "chip": "lsm6dso",
  "node_label": "lsm6dso0",
  "features": {
    "bus": "spi",
    "has_prop": ["irq_gpios", "int_pin", "accel_odr", "gyro_odr", "drdy_pulsed"],
    "kconfig": ["CK_LSM6DSO"]
  }
}
```

The extraction script is approximately 30 lines of Python that:
1. Finds the sensor node by label in the DTS output.
2. Reads the parent bus node's `compatible` to determine bus type.
3. Lists all properties present on the sensor node.
4. Reads the generated `.config` file for enabled Kconfig symbols matching `CK_*`.

### 5.3 JUnit XML Extensions for Power Data

The JUnit XML follows the standard schema but adds custom properties for power data:

```xml
<testsuites>
  <testsuite name="lsm6dso_hw" tests="11" failures="0" skipped="1">
    <testcase name="test_sleep_current" time="1.108">
      <properties>
        <property name="power.avg_ua" value="2.8"/>
        <property name="power.peak_ua" value="8.2"/>
        <property name="power.energy_uj" value="3.1"/>
        <property name="power.budget_pass.avg_ua" value="true"/>
        <property name="power.budget_pass.peak_ua" value="true"/>
      </properties>
    </testcase>
    <testcase name="test_motion_interrupt" time="2.005">
      <skipped message="No motion interrupt detected"/>
    </testcase>
  </testsuite>
</testsuites>
```

### 5.4 Power Summary JSON (summary.json)

```json
{
  "test_mode": "full",
  "tests": {
    "test_sleep_current": {
      "avg_ua": 2.8,
      "peak_ua": 8.2,
      "min_ua": 2.1,
      "energy_uj": 3.1,
      "duration_s": 1.108,
      "budget_pass": {
        "avg_ua": true,
        "peak_ua": true
      }
    },
    "test_active_current_at_52hz": {
      "avg_ua": 27.3,
      "peak_ua": 183.5,
      "min_ua": 22.1,
      "energy_uj": 57.4,
      "duration_s": 2.105,
      "budget_pass": {
        "avg_ua": true,
        "peak_ua": true
      }
    },
    "test_device_ready": {
      "avg_ua": 45.2,
      "peak_ua": 120.0,
      "min_ua": 3.1,
      "energy_uj": 0.14,
      "duration_s": 0.003,
      "budget_pass": null
    }
  }
}
```

When `test_mode` is `"functional"`, all `budget_pass` fields are `null`.

### 5.5 Coverage Report (coverage.json)

```json
{
  "board": "devkit_nrf52840_lsm6dso_spi",
  "chip": "lsm6dso",
  "test_mode": "full",
  "tests": {
    "test_device_ready": { "status": "PASS", "category": "required" },
    "test_sensor_presence": { "status": "PASS", "category": "required" },
    "test_spi_whoami": { "status": "PASS", "category": "required_when:bus=spi" },
    "test_i2c_whoami": { "status": "NOT_APPLICABLE", "category": "required_when:bus=i2c", "reason": "board bus is spi" },
    "test_drdy_interrupt": { "status": "PASS", "category": "required_when:has_prop=irq_gpios" },
    "test_polled_fifo_read": { "status": "NOT_APPLICABLE", "category": "required_when:not_has_prop=irq_gpios", "reason": "board has irq_gpios" },
    "test_motion_interrupt": { "status": "SKIP", "category": "optional" }
  },
  "summary": {
    "pass": 9,
    "fail": 0,
    "skip": 1,
    "not_applicable": 2,
    "coverage_gap": 0,
    "unexpected": 0
  }
}
```

### 5.6 Artifact Tree in MinIO

```
validation/pipelines/{pipeline_id}/stages/driver_hw/{job_id}/
+-- junit.xml
+-- uart_log.txt
+-- power/
|   +-- full_trace.csv
|   +-- per_test/
|   |   +-- test_sleep_current.csv
|   |   +-- test_active_current_at_52hz.csv
|   |   +-- test_fifo_watermark_interrupt.csv
|   |   +-- test_fifo_batch_at_52hz.csv
|   |   +-- ...
|   +-- summary.json
+-- coverage.json
+-- metadata.json
+-- board_features.json
+-- test_spec.yaml
```

`metadata.json` contains:

```json
{
  "pipeline_id": "pl-abc123",
  "job_id": "pl-abc123-driver-hw-lsm6dso-devkit-spi",
  "board": "devkit_nrf52840_lsm6dso_spi",
  "chip": "lsm6dso",
  "test_mode": "full",
  "firmware_version": "0.3.1",
  "commit": "a1b2c3d",
  "repo": "accel_drv",
  "branch": "main",
  "mtib_node": "verdin-imx8mm-15702160",
  "started_at": "2026-02-25T10:30:00Z",
  "completed_at": "2026-02-25T10:31:42Z",
  "duration_s": 102
}
```

---

## 6. Build and Pipeline

### 6.1 Board Definitions in ck_boards

Two new board definitions are needed in `ck_boards` for the dev-kit fixture:

**`devkit_nrf52840_lsm6dso_spi`** -- nRF52840-DK + LSM6DSO breakout on SPI0.

```
ck_boards/current/boards/corekinect/devkit_nrf52840_lsm6dso_spi/
+-- board.yml
+-- devkit_nrf52840_lsm6dso_spi_nrf52840.dts
+-- devkit_nrf52840_lsm6dso_spi_nrf52840-pinctrl.dtsi
+-- devkit_nrf52840_lsm6dso_spi_nrf52840_defconfig
+-- Kconfig.devkit_nrf52840_lsm6dso_spi
+-- Kconfig.defconfig
+-- board.cmake
```

`board.yml`:
```yaml
board:
  name: devkit_nrf52840_lsm6dso_spi
  vendor: corekinect
  socs:
  - name: nrf52840
```

Key DTS content (`devkit_nrf52840_lsm6dso_spi_nrf52840.dts`):
```dts
/dts-v1/;
#include <nordic/nrf52840_qiaa.dtsi>
#include "devkit_nrf52840_lsm6dso_spi_nrf52840-pinctrl.dtsi"

/ {
    model = "CoreKinect Dev-Kit nRF52840 + LSM6DSO (SPI)";
    compatible = "corekinect,devkit-nrf52840-lsm6dso-spi";

    chosen {
        zephyr,console = &uart0;
        zephyr,sram = &sram0;
        zephyr,flash = &flash0;
    };
};

&uart0 {
    status = "okay";
    current-speed = <115200>;
    pinctrl-0 = <&uart0_default>;
    pinctrl-1 = <&uart0_sleep>;
    pinctrl-names = "default", "sleep";
};

&spi0 {
    compatible = "nordic,nrf-spim";
    status = "okay";
    pinctrl-0 = <&spi0_default>;
    pinctrl-1 = <&spi0_sleep>;
    pinctrl-names = "default", "sleep";

    cs-gpios = <&gpio0 8 (GPIO_ACTIVE_LOW)>;

    lsm6dso0: lsm6dso0@0 {
        compatible = "ck,lsm6dso";
        reg = <0>;
        int-pin = <2>;
        spi-max-frequency = <1000000>;
        irq-gpios = <&gpio0 14 GPIO_ACTIVE_HIGH>;
        accel-pm = <1>;
        accel-range = <3>;
        accel-odr = <3>;
        gyro-pm = <1>;
        gyro-range = <0>;
        gyro-odr = <2>;
        drdy-pulsed;
    };
};

/* Minimal config -- no flash, no I2C, no BLE, no PWM */
&gpiote { status = "okay"; };
&gpio0 { status = "okay"; };
&gpio1 { status = "okay"; };
```

Pinctrl matches the Alpha B0 board exactly:
```dts
&pinctrl {
    uart0_default: uart0_default {
        group1 { psels = <NRF_PSEL(UART_TX, 0, 23)>; };
        group2 { psels = <NRF_PSEL(UART_RX, 0, 25)>; bias-pull-up; };
    };
    uart0_sleep: uart0_sleep {
        group1 { psels = <NRF_PSEL(UART_TX, 0, 23)>, <NRF_PSEL(UART_RX, 0, 25)>; low-power-enable; };
    };
    spi0_default: spi0_default {
        group1 {
            psels = <NRF_PSEL(SPIM_SCK, 0, 7)>,
                    <NRF_PSEL(SPIM_MOSI, 0, 5)>,
                    <NRF_PSEL(SPIM_MISO, 1, 8)>;
        };
    };
    spi0_sleep: spi0_sleep {
        group1 {
            psels = <NRF_PSEL(SPIM_SCK, 0, 7)>,
                    <NRF_PSEL(SPIM_MOSI, 0, 5)>,
                    <NRF_PSEL(SPIM_MISO, 1, 8)>;
            low-power-enable;
        };
    };
};
```

`devkit_nrf52840_lsm6dso_spi_nrf52840_defconfig`:
```kconfig
CONFIG_SOC_SERIES_NRF52X=y
CONFIG_SOC_NRF52840_QIAA=y
CONFIG_BOARD_DEVKIT_NRF52840_LSM6DSO_SPI=y
CONFIG_GPIO=y
CONFIG_PINCTRL=y
CONFIG_SERIAL=y
CONFIG_CONSOLE=y
CONFIG_UART_CONSOLE=y
```

**`devkit_nrf52840_lis2de12_i2c`** -- Same MCU, LIS2DE12 on I2C1. Separate board definition with different DTS (I2C bus node, LIS2DE12 compatible, different interrupt pin). Deferred until LIS2DE12 driver is ready.

### 6.2 Build Manifest (.concord/build.yaml)

```yaml
# accel_drv/.concord/build.yaml
version: 1
container: containers.ad.corekinect.com/ncs-fw-dev:2.4.2

builds:
  # Interface contract tests (native_sim, Stage 1)
  test_native:
    steps:
      - west update
      - twister -p native_sim -T tests/interface/ --outdir twister-out
    artifacts:
      - twister-out/twister_report.xml

  # Hardware test firmware (per board, per chip -- Stage 2)
  test_device:
    steps:
      - west update
      - >-
        twister -p ${BOARD}
        --prep-artifacts-for-testing
        -T tests/${CHIP}/
        --outdir twister-out
      - >-
        cp tests/${CHIP}/test_spec.yaml twister-out/ 2>/dev/null || true
      - >-
        python3 scripts/extract_board_features.py
        --dts twister-out/${CHIP}/build/zephyr/zephyr.dts
        --node ${CHIP}0
        --board ${BOARD}
        --chip ${CHIP}
        -o twister-out/board_features.json
    artifacts:
      - twister-out/
      - tests/${CHIP}/test_spec.yaml
      - twister-out/board_features.json
```

**Variable substitution:** `${BOARD}` and `${CHIP}` are provided by the pipeline controller via `BuildRequest` parameters, resolved from the `targets:` block in `pipeline.yaml`.

### 6.3 Pipeline Configuration (.concord/pipeline.yaml)

```yaml
# accel_drv/.concord/pipeline.yaml
# Canonical version — see also arch-stage1 Section 6.2 for the same file.
version: 1

on:
  push:
    branches: ["main", "develop", "feature/*", "release/*"]
    paths:
      - "drivers/**"
      - "stubs/**"
      - "tests/**"
      - "dts/**"
      - ".concord/**"
      - "Kconfig"
      - "CMakeLists.txt"
    ignore_paths:
      - "docs/**"
      - "**/*.md"
      - "**/.gitignore"

  manual:
    allowed_run_types: ["commit"]

concurrency:
  group: "${{ repo }}/${{ branch }}"
  supersede: true

stages:
  - name: software
    order: 1
    type: native_sim
    testPaths: ["tests/interface"]
    timeout: 600
    retry:
      max_attempts: 2
      on: [infrastructure_failure]

  - name: driver_hw
    order: 2
    type: hardware
    needsMtib: true
    timeout: 1800
    retry:
      max_attempts: 2
      on: [infrastructure_failure]

targets:
  # Dev-kit targets: isolated power measurement + functional tests
  - board: devkit_nrf52840_lsm6dso_spi
    chip: lsm6dso
    test_mode: full

  # Product targets: functional DTS verification only
  - board: alpha_b0/nrf52840
    chip: lsm6dso
    product: alpha
    test_mode: functional

notifications:
  on_failure:
    slack: "#accel-driver-ci"
  on_recovery:
    slack: "#accel-driver-ci"
```

### 6.4 Pipeline Flow

```
  Push to accel_drv
       |
       v
  Concord HTTP API receives webhook
       |
       v
  Trigger evaluation:
    - Branch matches on.push.branches?
    - Changed files match on.push.paths?
    - Not all in ignore_paths?
       |
       v
  Resolve targets from pipeline.yaml:
    target 1: devkit_nrf52840_lsm6dso_spi / lsm6dso / full
    target 2: alpha_b0/nrf52840 / lsm6dso / functional
       |
       v
  BUILD PHASE (all builds complete before any stage runs):
    Build 1: test_native (native_sim, interface tests)
    Build 2: test_device (BOARD=devkit_nrf52840_lsm6dso_spi, CHIP=lsm6dso)
    Build 3: test_device (BOARD=alpha_b0/nrf52840, CHIP=lsm6dso)
       |
       v
  STAGE 1: Software Tests
    Job: run twister report from Build 1 on native_sim
    Result: PASS / FAIL
       |
       +-- FAIL --> pipeline stops, notify, exit
       |
       v (PASS)
  STAGE 2: Driver HW Tests (fan-out per target)
    Job A: driver_hw, devkit_nrf52840_lsm6dso_spi, TEST_MODE=full
      requires: { fixture_type: devkit, chip: lsm6dso, bus: spi }
      --> queued in MTIB work queue
      --> matched to a dev-kit MTIB node
      --> test runner executes full flow (flash, UART, power, evaluate)
    Job B: driver_hw, alpha_b0/nrf52840, TEST_MODE=functional
      requires: { fixture_type: product, product: alpha }
      --> queued in MTIB work queue
      --> matched to an alpha product MTIB node
      --> test runner executes functional flow (flash, UART, power captured but not enforced)
       |
       v
  STAGE 2 COMPLETE when all Jobs pass
    Pipeline status: SUCCESS
    Artifacts in MinIO, power stats in InfluxDB
    Bitbucket commit status updated
```

### 6.5 MTIB Node Registration

For the dev-kit fixture to be schedulable, the MTIB node must be registered in Concord with the correct capability labels:

```bash
# K8s node labels (set during physical setup)
kubectl label node verdin-xxx-004 \
  corekinect.com/fixture-type=devkit \
  corekinect.com/chip=lsm6dso \
  corekinect.com/bus=spi \
  corekinect.com/mcu=nrf52840

# Concord node registration (via API)
PUT /v2/nodes/{node_id}
{
  "capabilities": {
    "fixture_type": "devkit",
    "chips": ["lsm6dso"],
    "bus": "spi",
    "power_isolation": true,
    "mcu": "nrf52840"
  },
  "fixtureProfile": { /* ... JSON from Section 2.5 ... */ }
}
```

For multi-sensor dev-kits (LSM6DSO + LIS2DE12 on one fixture board):

```json
{
  "capabilities": {
    "fixture_type": "devkit",
    "chips": ["lsm6dso", "lis2de12"],
    "bus": ["spi", "i2c"],
    "power_isolation": true,
    "mcu": "nrf52840"
  }
}
```

The scheduler matches any job that requires one of the listed chips. The relay ensures only one sensor is powered at a time.

---

## 7. Interfaces

### 7.1 What Stage 2 Consumes

| Input | Source | Format |
|-------|--------|--------|
| Test firmware hex | Build service via MinIO | `.hex` (Intel HEX, Zephyr build output) |
| `test_spec.yaml` | Driver repo (`tests/{chip}/test_spec.yaml`), copied to MinIO by build | YAML (schema in Section 5.1) |
| `board_features.json` | Build step (`extract_board_features.py`), stored in MinIO | JSON (schema in Section 5.2) |
| MTIB endpoint | Pipeline controller (env vars `MTIB_HOST`, `MTIB_PORT`) | gRPC address |
| Fixture profile | Concord `Node.fixtureProfile` (injected by controller or fetched via API) | JSON (schema in Section 2.5) |
| Stage 1 gate | Pipeline controller | Stage 2 Jobs are only created after all Stage 1 Jobs succeed |

### 7.2 What Stage 2 Produces

| Output | Destination | Format | Consumer |
|--------|------------|--------|----------|
| JUnit XML | MinIO | XML (Section 5.3) | Dashboard, Bitbucket commit status |
| Per-test power traces | MinIO | CSV (Section 4.4) | Dashboard power trend charts |
| Power summary | MinIO | JSON (Section 5.4) | Dashboard, test_spec evaluation |
| Coverage report | MinIO | JSON (Section 5.5) | Dashboard, pipeline verdict |
| UART log | MinIO | Plain text | Debugging |
| Metadata | MinIO | JSON (Section 5.6) | Traceability, dashboard |
| Power time-series | InfluxDB | InfluxDB line protocol | Grafana trend analysis |
| Pipeline verdict | K8s Job exit code (0 or 1) | K8s-native | Pipeline controller (stage gate) |

### 7.3 What Stage 2 Provides to Stage 3

Stage 2 does not produce artifacts that Stage 3 directly consumes. The relationship is:

- **Stage 2 proves the driver works in isolation.** If Stage 2 passes, Stage 3 can assume the driver is functional when debugging integration failures.
- **Stage 2 power baselines** become the reference for Stage 3 power budgets. If Stage 2 shows the LSM6DSO draws 27 uA at 52Hz, Stage 3's integrated power budget should account for this.
- **Stage gating:** Stage 2 must pass before Stage 3 runs (for pipelines that include both stages -- driver repo pipelines include Stage 2 only; firmware repo pipelines include Stage 1, 2, 3, and 4).

---

## 8. Implementation Roadmap

Ordered by dependency. Each item must be completed before the items that depend on it.

### Phase 1: Foundation (Weeks 1-3)

| # | Work Item | Owner | Deliverable | Depends On |
|---|-----------|-------|-------------|------------|
| 1 | **Dev-kit fixture design and assembly** | HW eng | nRF52840-DK + LSM6DSO dev kit wired to MTIB test head. Must provide: per-sensor MTIB relay + current sense, SWD, UART0, optional GPIO taps for interrupt observation. Fixture design details (voltage regulation, sense resistor, PCB layout) are HW eng's call. | -- |
| 3 | **Dev-kit board definition (LSM6DSO SPI)** | FW eng | `devkit_nrf52840_lsm6dso_spi` in `ck_boards`. board.yml, DTS, pinctrl, defconfig. Must compile with `west build -b devkit_nrf52840_lsm6dso_spi`. | -- |
| 4 | **Driver repo restructure** | FW eng | New branch on `accel_drv` with `tests/`, `stubs/`, `.concord/` directories. `tests/lsm6dso/` directory with `src/main.c` (empty test suite), `prj.conf`, `testcase.yaml`, `test_spec.yaml`, `CMakeLists.txt`. Must compile: `west build -b devkit_nrf52840_lsm6dso_spi -T tests/lsm6dso/`. | 3 |
| 5 | **`extract_board_features.py` script** | Infra eng | Python script that reads compiled DTS + .config and produces `board_features.json`. Input: `--dts`, `--node`, `--board`, `--chip`. Output: JSON per Section 5.2 schema. Unit tests included. | -- |

### Phase 2: Test Firmware (Weeks 3-5)

| # | Work Item | Owner | Deliverable | Depends On |
|---|-----------|-------|-------------|------------|
| 6 | **Test helper utilities (`test_helpers.h`)** | FW eng | `read_register()`, `write_register()` for SPI and I2C. Callback flag declarations (`drdy_fired`, `wm_fired`, `motion_fired`, `drdy_count`). Callback functions. Raw GPIO callback setup for interrupt testing (bypass driver trigger dispatch). | 4 |
| 7 | **Core tests** | FW eng | `test_device_ready`, `test_sensor_presence`, `test_accel_data_readback` (with gravity assertion). `before`/`after` hooks with software reset and cleanup. | 6 |
| 8 | **SPI bus tests** | FW eng | `test_spi_whoami`, `test_spi_register_write_readback`. Guarded by `#if DT_ON_BUS(LSM6DSO_NODE, spi)`. | 6 |
| 9 | **Interrupt and FIFO tests** | FW eng | `test_drdy_interrupt`, `test_fifo_watermark_interrupt` (with raw GPIO callback fix), `test_fifo_batch_at_52hz`. Guarded by `#if DT_NODE_HAS_PROP(LSM6DSO_NODE, irq_gpios)`. Polled fallback: `test_polled_fifo_read`. | 6 |
| 10 | **Power profiling tests** | FW eng | `test_sleep_current`, `test_active_current_at_52hz`. Hold steady state for 1-2 seconds to provide clean measurement windows. | 6 |
| 11 | **Motion detection test** | FW eng | `test_motion_interrupt` with `zassume_true` for runtime skip. | 6 |
| 12 | **test_spec.yaml** | FW eng | Complete spec per Section 5.1 schema. Power budgets derived from LSM6DSO datasheet Rev 9, Table 4, with margins. | 7, 8, 9, 10, 11 |

### Phase 3: Test Runner (Weeks 4-7)

| # | Work Item | Owner | Deliverable | Depends On |
|---|-----------|-------|-------------|------------|
| 13 | **`mtib_client.py`** | Infra eng | gRPC client wrapper for FlashProgram, UartStream, PowerMeasure, GpioSet, DutPowerEnable/Disable. Connection management, error retry, stream lifecycle. Unit tests with mocked gRPC. | -- |
| 14 | **`ztest_parser.py`** | Infra eng | UART line parser with anchored regexes. Emits structured events. Handles noise lines gracefully. Unit tests with sample UART output from Section 4 of the example doc. | -- |
| 15 | **`power_profiler.py`** | Infra eng | Concurrent power stream accumulation. Test boundary marking from parser events. Per-test slicing with 50ms margin. Statistics computation (avg, peak, min, energy). CSV export. Unit tests with synthetic power data. | -- |
| 16 | **`test_spec_evaluator.py`** | Infra eng | Loads test_spec.yaml + board_features.json. Evaluates required/required_when conditions. Evaluates power budgets (conditional on TEST_MODE). Evaluates timeouts. Produces coverage report. Unit tests with multiple board_features permutations (SPI vs I2C, with vs without IRQ). | 5 |
| 17 | **`fixture_controller.py`** | Infra eng | Loads fixture profile JSON. Implements abstract actions: `power_on_sensor(chip)`, `power_off_sensor(chip)`, `start_power_measure(chip)`, `flash_firmware(hex)`, `start_uart()`, `power_on_mcu()`. Maps to `mtib_client` calls using fixture profile channel mappings. | 13 |
| 18 | **`artifact_manager.py`** | Infra eng | MinIO upload with structured prefix. InfluxDB push for power stats. | -- |
| 19 | **`report_generator.py`** | Infra eng | JUnit XML generation (with power properties). summary.json, coverage.json, metadata.json. | -- |
| 20 | **`main.py` (Stage 2 driver_hw flow)** | Infra eng | Orchestrates the full flow from Section 4.2. Wires all modules together. Timeout handling. Exit code logic. | 13-19 |
| 21 | **Dockerfile** | Infra eng | `concord-driver-test-runner:latest`. Python 3.11, grpcio, minio, influxdb-client, pyyaml. | 20 |

### Phase 4: Pipeline Integration (Weeks 6-8)

| # | Work Item | Owner | Deliverable | Depends On |
|---|-----------|-------|-------------|------------|
| 22 | **Pipeline controller: Stage 2 Job creation** | Infra eng | After Stage 1 passes, create Stage 2 K8s Jobs for each target in pipeline.yaml. Set env vars: MTIB_HOST/PORT, TEST_MODE, CHIP, BOARD. Capability-based MTIB node matching for dev-kit and product fixture types. | 20 |
| 23 | **Build service: test_device build recipe** | Infra eng | Handle `${BOARD}` and `${CHIP}` substitution. Execute twister `--prep-artifacts-for-testing`. Run `extract_board_features.py`. Upload hex + test_spec.yaml + board_features.json to MinIO. | 5 |
| 24 | **MTIB node registration for dev-kit fixture** | Infra eng + HW eng | Physical wiring of fixture to MTIB test head. K8s node labels. Concord Node registration with capabilities and fixture profile. | 1, 22 |
| 25 | **End-to-end smoke test** | All | Push a test commit to `accel_drv`. Verify: webhook triggers pipeline, Stage 1 builds and runs, Stage 2 builds for dev-kit target, Stage 2 Job runs on dev-kit MTIB, all tests pass, artifacts in MinIO, power stats in InfluxDB. | 12, 21, 22, 23, 24 |

### Phase 5: Production Hardening (Weeks 8-10)

| # | Work Item | Owner | Deliverable | Depends On |
|---|-----------|-------|-------------|------------|
| 26 | **Alpha product board Stage 2** | FW eng | Verify `test_device` build for `alpha_b0/nrf52840`. Test firmware runs on Alpha hardware via product MTIB node. `test_mode: functional` -- power captured but not enforced. | 25 |
| 27 | **Dashboard integration** | Infra eng | Concord dashboard displays Stage 2 results: per-test pass/fail, power trends over time, coverage report visualization. | 25 |
| 28 | **Retry and error handling** | Infra eng | Handle MTIB connection failures (retry with backoff). Handle flash failures (retry once). Handle intermittent test failures (mark flaky if a test fails once then passes on retry -- future, not MVP). | 25 |
| 29 | **Documentation** | All | Update README in `accel_drv` with test running instructions. Update Concord runbook with dev-kit fixture setup procedure. | 25 |

---

## 9. Open Questions

| # | Question | Impact | Proposed Resolution |
|---|----------|--------|-------------------|
| 1 | **Sense resistor value.** 10 ohm gives good resolution at low currents (3 uA sleep = 30 uV) but adds 10 ohm in series with VDD. At 3 mA gyro current, this drops 30 mV -- is this acceptable for the LDO headroom? | Power measurement accuracy vs LDO dropout | Verify LDO dropout voltage at 1.8V output with 30 mV series drop. TLV75518 dropout is 115 mV typ at 200 mA -- 30 mV is well within margin. If higher currents are tested (sensor + gyro active = ~3.2 mA), verify 32 mV drop is still acceptable. Alternative: use 1 ohm sense resistor and rely on MTIB's amplifier gain, but this reduces resolution to ~3 uV at sleep current -- may be below MTIB ADC noise floor. |
| 2 | **VDDIO at 3.3V vs 1.8V.** Running VDDIO at 3.3V avoids level shifting but differs from Alpha board (1.8V). Does this affect power measurement accuracy for VDD-only measurements? | Power budget accuracy | VDDIO current is dominated by bus pull-ups and is typically <1 uA for SPI (no pull-ups). VDD current includes the analog front-end and digital core, which is what the datasheet specifies. Recommend: document the VDDIO difference, proceed with 3.3V for Phase 1, add a 1.8V VDDIO variant with level shifter if power discrepancies are observed. |
| 3 | **CONFIG_CK_LSM6DSO_TRIGGER timeline.** When will the new accel driver interface design be ready? | Interrupt tests currently use direct register config + raw GPIO callbacks instead of the driver's `sensor_trigger_set` path. | Proceed with raw GPIO approach for Phase 1. When the trigger interface is finalized, update tests to use `sensor_trigger_set`. The raw GPIO approach tests the hardware interrupt path independently of the driver's trigger dispatch, which is arguably more thorough for Stage 2 purposes. |
| 4 | **Multi-chip relay sequencing.** When switching from LSM6DSO to LIS2DE12 on the same fixture, what is the minimum discharge time between power-off and power-on? | Test isolation between chips on same fixture | LSM6DSO datasheet specifies 5 us power-on time. LDO output capacitor (1 uF typ) with 10-ohm sense resistor has RC = 10 us. Use 100 ms between relay transitions for margin (includes capacitor discharge, relay switching time, and sensor boot). |
| 5 | **nRF52840-DK J-Link compatibility with MTIB SWD.** The nRF52840-DK has an on-board J-Link debugger. Does MTIB's `FlashProgram` RPC work with the on-board J-Link, or does it require direct SWD access (bypassing J-Link)? | Fixture wiring complexity | Verify with MTIB team. The on-board J-Link should be addressable via USB (MTIB USB passthrough) or via the DK's debug-out header (direct SWD to MTIB test head). If the on-board J-Link is used, MTIB connects via USB. If bypassed, MTIB connects via SWD test points on the DK. |
| 6 | **LIS2DE12 I2C address conflict.** If a future sensor on the same I2C bus uses address 0x19, the LIS2DE12 address must be changed to 0x18 (SA0 low). Does the breakout board support SA0 configuration? | LIS2DE12 dev-kit fixture | Verify breakout board. Most Adafruit/SparkFun breakouts have an SA0 jumper. If not, cut/solder the address jumper. |
| 7 | **InfluxDB retention policy for power data.** How long should per-pipeline power time-series be retained? | Storage cost vs trend analysis depth | Propose: 90 days at full resolution, 1 year at downsampled (hourly) resolution. Power trend analysis is most valuable for recent history. |
