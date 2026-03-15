# Twister and Hardware-in-the-Loop (HIL) Testing Reference

This document is a comprehensive reference for using Zephyr's Twister test runner and
implementing hardware-in-the-loop (HIL) testing for embedded firmware projects. It covers
test discovery, emulation, real-hardware testing, sensor driver patterns, HIL architecture,
submodule strategies, and CI/CD integration.

> **Scope**: Current as of early 2026. Based on Zephyr 3.6+/4.x documentation and
> community practices observed between 2024 and 2026.

---

## Table of Contents

1. [Zephyr Twister Overview](#1-zephyr-twister-overview)
2. [Twister for Hardware Testing](#2-twister-for-hardware-testing)
3. [Zephyr Sensor Driver Testing Patterns](#3-zephyr-sensor-driver-testing-patterns)
4. [HIL Testing Architecture Patterns](#4-hil-testing-architecture-patterns)
5. [Submodule Testing Strategy](#5-submodule-testing-strategy)
6. [CI/CD for Embedded](#6-cicd-for-embedded)

---

## 1. Zephyr Twister Overview

### 1.1 What Is Twister?

Twister (`scripts/twister`) is Zephyr's built-in test runner and orchestration tool. It
discovers test applications across the repository, builds them for one or more target
platforms, executes them (on emulators, simulators, or real hardware), and reports results.

**Key responsibilities:**

- Scan directories for `testcase.yaml` / `sample.yaml` files.
- Resolve which (platform, test-scenario) combinations are valid based on architecture,
  RAM/flash requirements, `depends_on` features, and Kconfig filters.
- Build each valid combination (calling `west build` / CMake under the hood).
- Execute the resulting binary via the appropriate handler (native binary, QEMU, hardware
  flash+serial).
- Parse console output through a *harness* to determine pass/fail.
- Produce JUnit XML, JSON, and CSV reports.

### 1.2 Test Discovery

Twister discovers tests by recursively scanning directories for two file types:

| File              | Purpose                                     |
|-------------------|---------------------------------------------|
| `testcase.yaml`   | Defines test scenarios for test applications |
| `sample.yaml`     | Defines sample demonstrations (same schema) |

The default scan roots are `tests/` and `samples/` relative to the Zephyr tree. Override
with `-T / --testsuite-root`:

```bash
# Scan only your project's test directory
west twister -T my_project/tests/
```

Each YAML file can declare multiple test scenarios under the `tests:` key. A *test
scenario* is a unique combination of configuration and expected behavior. The scenario
identifier is derived from the file path + YAML key (e.g.,
`tests/drivers/sensor/bme680/test.bme680.i2c`).

### 1.3 testcase.yaml / sample.yaml Format

Both files share the same schema. A full annotated example:

```yaml
# testcase.yaml
common:
  # Fields here apply to ALL scenarios in this file
  tags: sensor i2c
  depends_on: i2c
  min_ram: 32
  min_flash: 64
  timeout: 120

tests:
  # Scenario 1: basic functionality
  sensor.bme680.basic:
    tags: bme680
    platform_allow:
      - native_sim
      - nrf52840dk/nrf52840
    extra_configs:
      - CONFIG_BME680=y
      - CONFIG_EMUL=y
    harness: ztest

  # Scenario 2: SPI variant
  sensor.bme680.spi:
    tags: bme680 spi
    depends_on: spi
    platform_allow:
      - native_sim
    extra_args: DTC_OVERLAY_FILE=boards/native_sim_spi.overlay
    harness: ztest

  # Scenario 3: console output verification
  sensor.bme680.sample_output:
    tags: bme680
    harness: console
    harness_config:
      type: multi_line
      ordered: false
      regex:
        - "Temperature:(.*)C"
        - "Pressure:(.*)Pa"
        - "Humidity:(.*)%"

  # Scenario 4: pytest-based test
  sensor.bme680.pytest:
    tags: bme680
    harness: pytest
    harness_config:
      pytest_root:
        - "pytest/test_bme680.py"
```

#### Key Fields Reference

| Field                  | Type          | Description                                                        |
|------------------------|---------------|--------------------------------------------------------------------|
| `tags`                 | string/list   | Functional domain tags for filtering (`--tag` / `--exclude-tag`)   |
| `platform_allow`       | list          | Restrict to these platforms only                                   |
| `platform_exclude`     | list          | Exclude these platforms                                            |
| `arch_allow`           | list          | Restrict to architectures (e.g., `arm`, `x86`)                    |
| `depends_on`           | list          | Board must advertise these features (e.g., `i2c`, `spi`, `gpio`)  |
| `min_ram` / `min_flash`| int (KB)      | Minimum memory requirements                                       |
| `timeout`              | int (seconds) | Per-test timeout (default 60)                                      |
| `build_only`           | bool          | Only verify compilation, do not execute                            |
| `slow`                 | bool          | Mark as slow; skipped unless `--enable-slow` is passed             |
| `skip`                 | bool          | Unconditionally skip this scenario                                 |
| `extra_args`           | string        | Extra CMake arguments (supports `platform:`, `arch:` namespacing)  |
| `extra_configs`        | list          | Kconfig options merged with `prj.conf`                             |
| `filter`               | string        | Expression filter using `CONFIG_*` and devicetree properties       |
| `harness`              | string        | Handler type: `ztest`, `pytest`, `console`, `robot`, `gtest`, `shell`, `bsim` |
| `harness_config`       | map           | Harness-specific options (see below)                               |
| `fixture`              | string        | External fixture required (matched against hardware map)           |
| `sysbuild`             | bool          | Use sysbuild infrastructure                                        |
| `required_snippets`    | list          | Configuration snippets needed                                      |
| `levels`               | list          | Test level categorization for `--level` selection                  |

#### Harness Types

| Harness    | How It Determines Pass/Fail                                                  |
|------------|------------------------------------------------------------------------------|
| `ztest`    | Parses console for ztest framework pass/fail markers                         |
| `gtest`    | Parses console for Google Test framework markers                             |
| `console`  | Matches console output against `regex` patterns in `harness_config`          |
| `pytest`   | Delegates to pytest subprocess; uses `pytest-twister-harness` plugin         |
| `shell`    | Interacts with Zephyr shell over serial                                      |
| `robot`    | Delegates to Robot Framework                                                 |
| `bsim`     | BabbleSim-based Bluetooth simulation tests                                   |

### 1.4 Emulation vs. Hardware Targets

Twister uses different *handlers* depending on the execution environment:

```
+-----------------------+----------------------------+-------------------------------+
|  Handler              |  Used When                 |  How It Works                 |
+-----------------------+----------------------------+-------------------------------+
|  BinaryHandler        |  native_sim / native_posix |  Runs compiled ELF directly   |
|                       |                            |  as a host process            |
+-----------------------+----------------------------+-------------------------------+
|  QEMUHandler          |  QEMU platforms            |  Launches QEMU with the       |
|                       |  (qemu_cortex_m3, etc.)    |  compiled binary, captures    |
|                       |                            |  serial output via pipe       |
+-----------------------+----------------------------+-------------------------------+
|  SimulationHandler    |  Renode, nsim, armfvp,     |  Launches the simulator       |
|                       |  custom simulators         |  process with appropriate     |
|                       |                            |  arguments                    |
+-----------------------+----------------------------+-------------------------------+
|  DeviceHandler        |  Real hardware boards      |  Flashes via west flash,      |
|                       |                            |  opens serial port, reads     |
|                       |                            |  output until timeout/marker  |
+-----------------------+----------------------------+-------------------------------+
```

**native_sim** (replacement for the older `native_posix`) compiles Zephyr as a regular
Linux executable. Tests run at native speed with full debugging support (GDB, Valgrind,
ASan). This is the fastest feedback loop and the default choice for unit/integration tests.

**QEMU** emulates actual ARM/RISC-V/x86 targets. The binary is a real microcontroller
firmware image. QEMU is slower but more realistic than native_sim. Twister auto-selects
QEMU when a board's definition includes `simulation: [qemu]`.

**Simulation selection override:**

```bash
west twister --simulation qemu -p qemu_cortex_m3 -T tests/kernel/
west twister --emulation-only -T tests/  # Only build/run emulated platforms
```

### 1.5 Serial / UART Connection for Real Hardware

When running on physical boards, Twister:

1. Builds the firmware for the specified platform.
2. Flashes the binary using `west flash` (or a custom `--flash-command`).
3. Opens the serial port at the configured baud rate (default 115200).
4. Reads console output until a pass/fail marker is detected or `timeout` expires.
5. Closes the serial connection and records results.

The `--flash-before` flag (recommended for USB CDC boards) ensures flashing completes
*before* the serial port is opened, preventing disconnection issues on boards that reset
their USB interface during flash.

### 1.6 Output Formats

Twister produces several output files in the output directory (`twister-out/` by default,
override with `-O`):

| File                         | Format    | Description                                           |
|------------------------------|-----------|-------------------------------------------------------|
| `twister.json`               | JSON      | Full test metadata, results, footprint data           |
| `twister.xml`                | JUnit XML | CI-compatible test results (Jenkins, GitHub, etc.)    |
| `twister_suite_report.xml`   | JUnit XML | Per-suite report (when using pytest harness)          |
| `twister_discard.csv`        | CSV       | Filtered-out tests with exclusion reasons             |
| `twister_footprint.json`     | JSON      | Detailed ROM/RAM symbol analysis                      |
| `recording.csv`              | CSV       | Console harness extracted metrics                     |
| `testplan.json`              | JSON      | Discovered test plan (scenarios + platform matrix)    |

**Specifying report output:**

```bash
west twister -T tests/ \
  -o reports/ \
  --report-name my_test_run \
  --report-summary 10      # Show top 10 failures in console summary
```

---

## 2. Twister for Hardware Testing

### 2.1 Single Device: Quick Start

The simplest way to test on a connected board:

```bash
west twister \
  --device-testing \
  --device-serial /dev/ttyACM0 \
  --device-serial-baud 115200 \
  -p nrf52840dk/nrf52840 \
  -T tests/drivers/sensor/bme680/ \
  --flash-before \
  -v
```

| Flag                      | Purpose                                                    |
|---------------------------|------------------------------------------------------------|
| `--device-testing`         | Enable hardware execution mode                             |
| `--device-serial`          | Serial port path (repeatable for multi-UART boards)        |
| `--device-serial-baud`     | Baud rate (default 115200)                                 |
| `--flash-before`           | Flash before opening serial (prevents USB CDC issues)      |
| `-p`                       | Target platform identifier                                 |
| `-T`                       | Test suite root directory                                  |
| `-v`                       | Verbose output                                             |

### 2.2 Hardware Map Files

For multi-device setups or CI environments, use a hardware map YAML file.

**Auto-generate from connected devices:**

```bash
west twister --generate-hardware-map hardware_map.yaml
```

This probes connected serial devices and creates a map. You must then manually fill in the
`platform` field for each device.

**hardware_map.yaml format:**

```yaml
# hardware_map.yaml
- available: true
  connected: true
  id: 000683459357
  platform: nrf52840dk/nrf52840
  product: "J-Link"
  runner: jlink
  serial: /dev/ttyACM0
  baud: 115200
  fixtures:
    - gpio_loopback
    - sensor_bme680

- available: true
  connected: true
  id: 0240000026334e450015400f5e0e000b4eb1000097969900
  platform: frdm_k64f
  product: "DAPLink CMSIS-DAP"
  runner: pyocd
  serial: /dev/ttyACM1
  baud: 115200
  fixtures:
    - i2c_devices

- available: false
  connected: false
  id: ESP32_USB_001
  platform: esp32s3_devkitc/esp32s3/procpu
  product: "ESP32-S3-DevKitC"
  runner: esp32
  serial: /dev/ttyUSB0
  baud: 115200
```

| Field       | Required | Description                                                      |
|-------------|----------|------------------------------------------------------------------|
| `platform`  | Yes      | Board identifier matching Zephyr board name                      |
| `serial`    | Yes      | Serial port path (e.g., `/dev/ttyACM0`)                         |
| `runner`    | Yes      | Flash tool: `jlink`, `pyocd`, `nrfjprog`, `openocd`, `dediprog` |
| `id`        | No       | Probe/board serial number (used for multi-probe disambiguation)  |
| `product`   | No       | Human-readable hardware description                              |
| `baud`      | No       | Serial baud rate (defaults to 115200)                            |
| `connected` | No       | Whether the device is physically connected                       |
| `available` | No       | Whether the device is available for testing                      |
| `fixtures`  | No       | List of test fixtures this board provides                        |

**Running with a hardware map:**

```bash
west twister \
  --device-testing \
  --hardware-map hardware_map.yaml \
  -T tests/ \
  --flash-before \
  -v
```

Twister will:
- Build tests for each `platform` in the map where `connected: true`.
- Match `fixture` requirements in `testcase.yaml` against `fixtures` in the hardware map.
- Flash and execute on each device, collecting results in parallel where possible.

### 2.3 Two-Stage Build and Test (CI Pattern)

Separate the build phase (which can run in the cloud) from the device test phase (which
must run on a machine with physical hardware):

**Stage 1 -- Build (cloud CI runner):**

```bash
west twister \
  -p nrf52840dk/nrf52840 \
  -T tests/ \
  --prep-artifacts-for-testing \
  -O twister-out/
```

This compiles all binaries and saves only the files needed for flashing into `twister-out/`.

**Stage 2 -- Device Test (self-hosted runner with hardware):**

```bash
west twister \
  -p nrf52840dk/nrf52840 \
  -T tests/ \
  --device-testing \
  --device-serial /dev/ttyACM0 \
  --test-only \
  --west-flash="--skip-rebuild,--dev-id=000683459357" \
  --flash-before \
  -O twister-out/ \
  -v
```

`--test-only` skips rebuild and reuses compiled binaries from Stage 1.
`--west-flash` passes extra arguments to `west flash` (e.g., J-Link serial number).

### 2.4 Pytest Integration with Twister

Starting with Zephyr 3.4+, the `pytest-twister-harness` plugin enables writing Python-based
tests that interact with devices through Twister's infrastructure.

#### Project Structure

```
test_sensor/
  pytest/
    test_sensor_readings.py
  src/
    main.c
  CMakeLists.txt
  prj.conf
  testcase.yaml
```

#### testcase.yaml Configuration

```yaml
tests:
  sensor.bme680.pytest_validation:
    harness: pytest
    harness_config:
      pytest_root:
        - "pytest/test_sensor_readings.py"
      pytest_args:
        - "--timeout=120"
      pytest_dut_scope: session   # Keep device running across all tests
    platform_allow:
      - nrf52840dk/nrf52840
      - native_sim
    tags: sensor pytest
```

#### Available Fixtures

**`dut` (DeviceAdapter)** -- Core fixture for device interaction:

```python
from twister_harness import DeviceAdapter

def test_sensor_boot(dut: DeviceAdapter):
    """Verify the sensor driver initializes successfully."""
    dut.readlines_until(regex="Sensor initialized", timeout=10)

def test_sensor_reading(dut: DeviceAdapter):
    """Verify sensor produces valid readings."""
    lines = dut.readlines_until(
        regex=r"Temperature: [\d.]+ C",
        timeout=30
    )
    assert len(lines) > 0
```

**`shell` (Shell)** -- For Zephyr shell interaction:

```python
from twister_harness import Shell

def test_sensor_shell_command(shell: Shell):
    """Test the sensor read shell command."""
    result = shell.exec_command("sensor get bme680")
    assert "Temperature" in "\n".join(result)
    assert "Pressure" in "\n".join(result)
```

**`mcumgr` (McuMgr)** -- For MCUmgr-based device management:

```python
from twister_harness import DeviceAdapter, Shell, McuMgr

def test_firmware_upload(dut: DeviceAdapter, shell: Shell, mcumgr: McuMgr):
    """Test OTA firmware upload."""
    dut.disconnect()
    mcumgr.image_upload("/path/to/zephyr.signed.bin")
```

**`unlaunched_dut`** -- For manual device lifecycle control:

```python
from twister_harness import DeviceAdapter

def test_boot_sequence(unlaunched_dut: DeviceAdapter):
    """Test with manual device launch control."""
    unlaunched_dut.launch()
    unlaunched_dut.readlines_until(regex="Booting Zephyr", timeout=5)
```

#### DeviceAdapter API

| Method                | Description                                                  |
|-----------------------|--------------------------------------------------------------|
| `launch()`            | Initialize device (flash, connect serial, start readers)     |
| `close()`             | Disconnect and clean up                                      |
| `readline()`          | Read single line from device output                          |
| `readlines()`         | Read all available buffered output                           |
| `readlines_until()`   | Read until regex match, timeout, or line count               |
| `write()`             | Send raw bytes to device                                     |

Tests written against the `DeviceAdapter` API are **device-type-agnostic**: the same
Python test works on native_sim, QEMU, and real hardware without modification.

#### Running pytest Tests via Twister

```bash
# Run with specific pytest argument filtering
west twister \
  -p native_sim \
  -T tests/drivers/sensor/bme680/ \
  --pytest-args="-k test_sensor_reading" \
  -v
```

---

## 3. Zephyr Sensor Driver Testing Patterns

### 3.1 Emulator Framework Overview

Zephyr's emulator framework allows testing peripheral drivers without real hardware. The
architecture layers are:

```
+-----------------------------+
|  Test Application (ztest)   |
+-----------------------------+
|  Sensor Driver (real code)  |  <-- Unmodified driver code
+-----------------------------+
|  I2C/SPI Bus Driver         |  <-- Emulated bus controller
+-----------------------------+
|  Device Emulator            |  <-- Simulates sensor registers
+-----------------------------+
|  native_sim / native_posix  |
+-----------------------------+
```

The key insight: the *real driver code* runs unmodified. The emulator sits beneath the bus
layer, intercepting I2C/SPI transactions and responding as the real hardware would.

### 3.2 Creating a Sensor Emulator

Emulators are defined using `EMUL_DT_DEFINE()` or `EMUL_DT_INST_DEFINE()`.

Each emulator provides:
- **`bus_api`** (required): Handles bus-level transactions (I2C transfer, SPI transceive).
- **`backend_api`** (optional): Exposes test-facing functions to set simulated values.

**Example: I2C Temperature Sensor Emulator**

```c
/* emul_my_temp_sensor.c */

#include <zephyr/device.h>
#include <zephyr/drivers/emul.h>
#include <zephyr/drivers/i2c_emul.h>

/* Internal state for the emulated sensor */
struct my_sensor_emul_data {
    int32_t temperature_mdegc;  /* milli-degrees C */
    int32_t humidity_mpercent;  /* milli-percent */
    uint8_t registers[16];
};

/* I2C transfer handler -- responds to I2C reads/writes */
static int my_sensor_emul_transfer(const struct emul *target,
                                    struct i2c_msg *msgs,
                                    int num_msgs, int addr)
{
    struct my_sensor_emul_data *data = target->data;

    /* Handle register reads/writes based on msgs content */
    for (int i = 0; i < num_msgs; i++) {
        if (msgs[i].flags & I2C_MSG_READ) {
            /* Return simulated register data */
            memcpy(msgs[i].buf, &data->registers[0], msgs[i].len);
        } else {
            /* Store written register address/data */
            memcpy(&data->registers[0], msgs[i].buf, msgs[i].len);
        }
    }
    return 0;
}

static const struct i2c_emul_api my_sensor_i2c_api = {
    .transfer = my_sensor_emul_transfer,
};

/* Backend API for tests to set simulated values */
struct my_sensor_backend_api {
    void (*set_temperature)(const struct emul *emul, int32_t mdegc);
    void (*set_humidity)(const struct emul *emul, int32_t mpercent);
};

static void my_sensor_set_temperature(const struct emul *emul,
                                       int32_t mdegc)
{
    struct my_sensor_emul_data *data = emul->data;
    data->temperature_mdegc = mdegc;
    /* Update register values to reflect new temperature */
    data->registers[0] = (mdegc >> 8) & 0xFF;
    data->registers[1] = mdegc & 0xFF;
}

static const struct my_sensor_backend_api my_sensor_backend = {
    .set_temperature = my_sensor_set_temperature,
};

/* Emulator initialization */
static int my_sensor_emul_init(const struct emul *emul,
                                const struct device *parent)
{
    return 0;
}

#define MY_SENSOR_EMUL_DEFINE(n)                                      \
    static struct my_sensor_emul_data my_sensor_data_##n;             \
    EMUL_DT_INST_DEFINE(n, my_sensor_emul_init,                       \
                        &my_sensor_data_##n, NULL,                    \
                        &my_sensor_i2c_api, &my_sensor_backend)

DT_INST_FOREACH_STATUS_OKAY(MY_SENSOR_EMUL_DEFINE)
```

### 3.3 Devicetree Overlay for Emulated Testing

Create a `boards/native_sim.overlay` alongside your test:

```dts
/* boards/native_sim.overlay */
&i2c0 {
    status = "okay";

    my_temp_sensor: my_temp_sensor@48 {
        compatible = "vendor,my-temp-sensor";
        reg = <0x48>;
        status = "okay";
    };
};
```

### 3.4 Test Code Using the Emulator

```c
/* src/main.c */
#include <zephyr/ztest.h>
#include <zephyr/device.h>
#include <zephyr/drivers/sensor.h>
#include <zephyr/drivers/emul.h>

/* Include the backend API header */
#include "emul_my_temp_sensor.h"

static const struct device *sensor_dev =
    DEVICE_DT_GET(DT_NODELABEL(my_temp_sensor));

static const struct emul *sensor_emul =
    EMUL_DT_GET(DT_NODELABEL(my_temp_sensor));

ZTEST_SUITE(sensor_tests, NULL, NULL, NULL, NULL, NULL);

ZTEST(sensor_tests, test_sensor_ready)
{
    zassert_true(device_is_ready(sensor_dev),
                 "Sensor device not ready");
}

ZTEST(sensor_tests, test_temperature_reading)
{
    struct sensor_value val;
    const struct my_sensor_backend_api *api = sensor_emul->backend_api;

    /* Set simulated temperature to 25.5 C (25500 milli-degrees) */
    api->set_temperature(sensor_emul, 25500);

    /* Fetch sensor data through the real driver */
    int ret = sensor_sample_fetch(sensor_dev);
    zassert_equal(ret, 0, "Failed to fetch sample");

    ret = sensor_channel_get(sensor_dev, SENSOR_CHAN_AMBIENT_TEMP, &val);
    zassert_equal(ret, 0, "Failed to get temperature channel");

    /* Verify the driver correctly parsed the emulated register data */
    zassert_within(sensor_value_to_double(&val), 25.5, 0.1,
                   "Temperature reading incorrect");
}

ZTEST(sensor_tests, test_negative_temperature)
{
    struct sensor_value val;
    const struct my_sensor_backend_api *api = sensor_emul->backend_api;

    /* Set simulated temperature to -10.0 C */
    api->set_temperature(sensor_emul, -10000);

    sensor_sample_fetch(sensor_dev);
    sensor_channel_get(sensor_dev, SENSOR_CHAN_AMBIENT_TEMP, &val);

    zassert_within(sensor_value_to_double(&val), -10.0, 0.1,
                   "Negative temperature reading incorrect");
}
```

### 3.5 Kconfig and CMakeLists.txt for Emulator Tests

**prj.conf:**
```ini
CONFIG_ZTEST=y
CONFIG_SENSOR=y
CONFIG_I2C=y
CONFIG_EMUL=y
CONFIG_MY_TEMP_SENSOR=y
CONFIG_MY_TEMP_SENSOR_EMUL=y
```

**testcase.yaml:**
```yaml
tests:
  drivers.sensor.my_temp_sensor:
    tags: drivers sensor
    depends_on: i2c
    platform_allow:
      - native_sim
    harness: ztest
    extra_configs:
      - CONFIG_EMUL=y
```

### 3.6 ADC-Based Sensor Emulation (Alternative Pattern)

For sensors read via ADC (e.g., NTC thermistors, analog voltage sensors), use the ADC
emulator:

```dts
/* native_sim.overlay */
&adc0 {
    #address-cells = <1>;
    #size-cells = <0>;
    ref-internal-mv = <3300>;
    channel@0 {
        reg = <0>;
        zephyr,resolution = <12>;
    };
};
```

```ini
# prj.conf
CONFIG_ADC=y
CONFIG_ADC_EMUL=y
```

The ADC emulator lets test code programmatically set millivolt values on channels, and the
real ADC driver code reads them as if from hardware.

### 3.7 Existing Emulator Examples in Zephyr

These in-tree examples serve as reference implementations:

| Sensor      | Bus | Location                                          |
|-------------|-----|---------------------------------------------------|
| BMI160      | I2C/SPI | `tests/drivers/sensor/accel/` and `drivers/sensor/bmi160/emul_bmi160.c` |
| BME680/688  | I2C | `tests/drivers/i2c/i2c_bme688/`                   |
| AT24 EEPROM | I2C | `tests/drivers/eeprom/`                            |
| FUSB302     | I2C | `drivers/usb_c/tcpc/emul_fusb302.c`               |

---

## 4. HIL Testing Architecture Patterns

### 4.1 Typical HIL Test Farm Architecture

A modern embedded HIL setup typically consists of:

```
+-----------------------------------------------------+
|                  CI/CD Server                        |
|  (Bitbucket Pipelines / GitHub Actions / Jenkins)    |
|                                                      |
|  Cloud Runners: build firmware                       |
|  Self-Hosted Runners: flash + test on hardware       |
+-----------------------------------------------------+
          |                           |
          | SSH / Runner Agent        | SSH / Runner Agent
          v                           v
+-------------------+       +-------------------+
|  Test Station 1   |       |  Test Station 2   |
|  (Raspberry Pi /  |       |  (Raspberry Pi /  |
|   x86 SBC)        |       |   x86 SBC)        |
|                    |       |                    |
|  USB connections:  |       |  USB connections:  |
|  - J-Link probe    |       |  - ST-Link probe   |
|  - Serial UART     |       |  - Serial UART     |
|  - Power relay     |       |  - Power relay     |
+-------------------+       +-------------------+
          |                           |
          | SWD/JTAG + UART           | SWD/JTAG + UART
          v                           v
+-------------------+       +-------------------+
|  DUT Board 1      |       |  DUT Board 2      |
|  (nRF52840DK)     |       |  (STM32L4 custom) |
+-------------------+       +-------------------+
```

**Key components:**

- **CI/CD Server**: Orchestrates the pipeline. Cloud runners handle building; self-hosted
  runners handle hardware interaction.
- **Test Station**: A single-board computer (Raspberry Pi 4/5, Intel NUC) running the CI
  runner agent. Connected to one or more DUT boards via USB (debug probe + serial).
- **DUT (Device Under Test)**: The target embedded board being tested.
- **Debug Probe**: J-Link, ST-Link, DAPLink, etc. -- used for flashing.
- **Serial Connection**: UART for console output capture (test result parsing).

### 4.2 GPIO Simulation for Button/Input Testing

Use a supervisory microcontroller or GPIO expander on the test station to simulate
physical inputs on the DUT:

**Hardware approach:**

```
Test Station (RPi)
    |
    | I2C
    v
MCP23008 GPIO Expander
    |
    | GPIO wires
    v
DUT: Button inputs, switch inputs
```

**Software approach (pytest test):**

```python
import RPi.GPIO as GPIO
from twister_harness import DeviceAdapter

# RPi GPIO pin connected to DUT button input
BUTTON_SIM_PIN = 17

def setup_gpio():
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(BUTTON_SIM_PIN, GPIO.OUT, initial=GPIO.HIGH)

def simulate_button_press(duration_ms=100):
    GPIO.output(BUTTON_SIM_PIN, GPIO.LOW)
    time.sleep(duration_ms / 1000)
    GPIO.output(BUTTON_SIM_PIN, GPIO.HIGH)

def test_button_press_event(dut: DeviceAdapter):
    """Verify DUT detects and reports a button press."""
    setup_gpio()
    simulate_button_press(duration_ms=200)
    dut.readlines_until(regex="Button pressed", timeout=5)
```

### 4.3 LED / Output Verification

Use a light sensor (BH1750) or direct GPIO read on the test station to verify DUT outputs:

```python
import smbus2

BH1750_ADDR = 0x23
BH1750_ONE_TIME_HIGH_RES = 0x20

def read_light_level():
    """Read lux from BH1750 sensor positioned over DUT LED."""
    bus = smbus2.SMBus(1)
    data = bus.read_i2c_block_data(BH1750_ADDR, BH1750_ONE_TIME_HIGH_RES, 2)
    lux = (data[0] << 8 | data[1]) / 1.2
    return lux

def test_led_turns_on(dut: DeviceAdapter, shell: Shell):
    """Verify LED turns on when commanded via shell."""
    baseline_lux = read_light_level()
    shell.exec_command("led on 0")
    time.sleep(0.5)
    active_lux = read_light_level()
    assert active_lux > baseline_lux + 50, "LED did not produce expected light output"
```

### 4.4 Power Monitoring During Tests

Monitor DUT power consumption using an INA219/INA226 current sensor on the test station:

```python
from ina219 import INA219

SHUNT_OHMS = 0.1

def get_power_metrics():
    """Read current draw from INA219 on the DUT power rail."""
    ina = INA219(SHUNT_OHMS, busnum=1, address=0x40)
    ina.configure()
    return {
        "voltage_v": ina.voltage(),
        "current_ma": ina.current(),
        "power_mw": ina.power(),
    }

def test_sleep_mode_current(dut: DeviceAdapter, shell: Shell):
    """Verify DUT enters low-power sleep mode."""
    shell.exec_command("power sleep")
    time.sleep(2)  # Allow time to enter sleep
    metrics = get_power_metrics()
    assert metrics["current_ma"] < 0.05, (
        f"Sleep current too high: {metrics['current_ma']} mA"
    )
```

### 4.5 Multi-Device Test Orchestration

For tests involving multiple boards (e.g., BLE central + peripheral, mesh networking):

**Using Twister hardware map with multiple entries:**

```yaml
# hardware_map.yaml
- connected: true
  platform: nrf52840dk/nrf52840
  serial: /dev/ttyACM0
  runner: jlink
  id: 000683459357
  fixtures:
    - ble_central

- connected: true
  platform: nrf52840dk/nrf52840
  serial: /dev/ttyACM1
  runner: jlink
  id: 000683459358
  fixtures:
    - ble_peripheral
```

**Using pytest for multi-device coordination:**

```python
import serial
from twister_harness import DeviceAdapter

PERIPHERAL_SERIAL = "/dev/ttyACM1"

def test_ble_connection(dut: DeviceAdapter):
    """Test BLE connection between central (DUT) and peripheral."""
    # The peripheral is managed separately
    peripheral = serial.Serial(PERIPHERAL_SERIAL, 115200, timeout=10)

    # Wait for peripheral to advertise
    while True:
        line = peripheral.readline().decode().strip()
        if "Advertising started" in line:
            break

    # Trigger central to scan and connect
    dut.readlines_until(regex="Connected to peripheral", timeout=30)

    peripheral.close()
```

### 4.6 Test Station Hardware Bill of Materials

A practical minimal HIL test station:

| Component                  | Purpose                              | Approximate Cost |
|----------------------------|--------------------------------------|------------------|
| Raspberry Pi 4/5 (4GB+)   | Test station controller              | $55-80           |
| USB hub (powered, 7-port)  | Connect multiple DUT boards          | $25              |
| J-Link EDU Mini            | Debug probe for flashing             | $20              |
| INA219 breakout board      | Power monitoring                     | $8               |
| MCP23008 breakout          | GPIO expansion for input simulation  | $5               |
| BH1750 light sensor        | LED output verification              | $4               |
| USB-UART adapter (FTDI)    | Additional serial connections        | $10              |
| Relay module (2-channel)   | Power cycling DUT boards             | $5               |
| Custom wiring harness      | Connect all components               | $10              |
| **Total per station**      |                                      | **~$150-175**    |

---

## 5. Submodule Testing Strategy

### 5.1 The Submodule Problem

When shared drivers or libraries live in a Git submodule used by multiple product
repositories, testing must answer:

- Does the shared code compile for all target boards?
- Does the shared code pass its own tests?
- Does updating the submodule break any product that depends on it?

### 5.2 Layered Testing Architecture

```
+-------------------------------------------------------------+
|  Layer 3: Product Integration Tests                          |
|  (Each product repo runs its full test suite including       |
|   the submodule code, on its specific board)                 |
+-------------------------------------------------------------+
|  Layer 2: Submodule Hardware Tests                           |
|  (Submodule repo tests drivers on reference hardware         |
|   using board overlays for each supported board)             |
+-------------------------------------------------------------+
|  Layer 1: Submodule Unit/Emulation Tests                     |
|  (Submodule repo runs ztest on native_sim with emulators)    |
+-------------------------------------------------------------+
```

### 5.3 Submodule Repository Test Structure

```
shared-drivers/
  drivers/
    sensor/
      my_sensor/
        my_sensor.c
        my_sensor.h
        Kconfig
        CMakeLists.txt
        emul_my_sensor.c              # Emulator implementation
  tests/
    drivers/
      sensor/
        my_sensor/
          src/
            main.c                    # ztest test code
          boards/
            native_sim.overlay        # Emulator devicetree
            nrf52840dk_nrf52840.overlay  # Real HW devicetree
            stm32l476rg.overlay       # Another board overlay
          prj.conf
          testcase.yaml
          pytest/
            test_my_sensor.py         # Python-based tests
  CMakeLists.txt
  west.yml                            # West manifest for standalone testing
```

### 5.4 testcase.yaml for Multi-Board Testing

```yaml
# tests/drivers/sensor/my_sensor/testcase.yaml
common:
  tags: drivers sensor my_sensor
  depends_on: i2c
  timeout: 120

tests:
  # Layer 1: Emulation tests (run in CI cloud, no hardware needed)
  drivers.sensor.my_sensor.emulation:
    platform_allow:
      - native_sim
    extra_configs:
      - CONFIG_EMUL=y
    harness: ztest

  # Layer 2: Hardware tests on reference board 1
  drivers.sensor.my_sensor.nrf52840dk:
    platform_allow:
      - nrf52840dk/nrf52840
    harness: pytest
    harness_config:
      pytest_root:
        - "pytest/test_my_sensor.py"
    fixture: sensor_my_sensor

  # Layer 2: Hardware tests on reference board 2
  drivers.sensor.my_sensor.stm32:
    platform_allow:
      - nucleo_l476rg
    harness: pytest
    harness_config:
      pytest_root:
        - "pytest/test_my_sensor.py"
    fixture: sensor_my_sensor

  # Build-only verification for other boards
  drivers.sensor.my_sensor.build_all:
    build_only: true
    platform_allow:
      - nrf52840dk/nrf52840
      - nucleo_l476rg
      - esp32s3_devkitc/esp32s3/procpu
      - native_sim
```

### 5.5 Board Overlay Strategy

Board overlays allow the same driver test to run on different hardware by providing
board-specific devicetree configuration:

**boards/native_sim.overlay** (emulation):
```dts
&i2c0 {
    my_sensor: my_sensor@48 {
        compatible = "vendor,my-sensor";
        reg = <0x48>;
        int-gpios = <&gpio0 10 GPIO_ACTIVE_LOW>;
    };
};
```

**boards/nrf52840dk_nrf52840.overlay** (real hardware):
```dts
&i2c0 {
    status = "okay";
    my_sensor: my_sensor@48 {
        compatible = "vendor,my-sensor";
        reg = <0x48>;
        int-gpios = <&gpio0 31 GPIO_ACTIVE_LOW>;
    };
};
```

**boards/nucleo_l476rg.overlay** (different hardware):
```dts
&i2c1 {
    status = "okay";
    my_sensor: my_sensor@48 {
        compatible = "vendor,my-sensor";
        reg = <0x48>;
        int-gpios = <&gpioa 5 GPIO_ACTIVE_LOW>;
    };
};
```

Twister automatically selects the correct overlay by matching the board name to the
overlay filename (e.g., `boards/<BOARD>.overlay`).

### 5.6 Base Firmware Test Image Strategy

Create a minimal "test harness" firmware image that exercises the shared driver APIs.
This image is not a product -- it exists solely for testing:

```c
/* tests/drivers/sensor/my_sensor/src/main.c */
#include <zephyr/ztest.h>
#include <zephyr/device.h>
#include <zephyr/drivers/sensor.h>

/* Use devicetree alias so the same code works across boards */
#define SENSOR_NODE DT_NODELABEL(my_sensor)

static const struct device *dev = DEVICE_DT_GET(SENSOR_NODE);

ZTEST_SUITE(my_sensor_base, NULL, NULL, NULL, NULL, NULL);

ZTEST(my_sensor_base, test_device_ready)
{
    zassert_true(device_is_ready(dev), "Device not ready");
}

ZTEST(my_sensor_base, test_sample_fetch)
{
    int ret = sensor_sample_fetch(dev);
    zassert_equal(ret, 0, "sensor_sample_fetch failed: %d", ret);
}

ZTEST(my_sensor_base, test_channel_get_temperature)
{
    struct sensor_value val;
    sensor_sample_fetch(dev);
    int ret = sensor_channel_get(dev, SENSOR_CHAN_AMBIENT_TEMP, &val);
    zassert_equal(ret, 0, "channel_get failed: %d", ret);
    /* Sanity check: temperature between -40 and 85 C */
    double temp = sensor_value_to_double(&val);
    zassert_between_inclusive(temp, -40.0, 85.0,
                              "Temperature out of range: %f", temp);
}
```

This base test image compiles for any board that has the sensor connected and an
appropriate overlay.

### 5.7 Product Repository Integration

In each product repository, the shared submodule is referenced and tested as part of the
product's full test suite:

```
product-a/
  firmware/
    CMakeLists.txt      # Includes shared-drivers as a Zephyr module
    west.yml            # References shared-drivers submodule
  tests/
    integration/
      testcase.yaml     # Product-specific integration tests
  shared-drivers/       # Git submodule
```

**west.yml:**
```yaml
manifest:
  projects:
    - name: shared-drivers
      path: shared-drivers
      url: https://bitbucket.org/myorg/shared-drivers.git
      revision: v1.2.0
```

---

## 6. CI/CD for Embedded

### 6.1 Bitbucket Pipelines Configuration

#### Basic Firmware Build Pipeline

```yaml
# bitbucket-pipelines.yml
image: ghcr.io/zephyrproject-rtos/ci:v0.26.14

definitions:
  caches:
    west-modules: /workspace/.west
    zephyr-sdk: /opt/zephyr-sdk
    ccache: /root/.cache/ccache
    pip: /root/.cache/pip

  steps:
    - step: &build-firmware
        name: Build Firmware
        caches:
          - west-modules
          - ccache
          - pip
        script:
          - export CCACHE_DIR=/root/.cache/ccache
          - export CCACHE_MAXSIZE=2G
          - export USE_CCACHE=1
          - west init -l firmware/
          - west update --narrow --fetch-opt=--depth=1
          - west build -b nrf52840dk/nrf52840 firmware/
        artifacts:
          - build/zephyr/zephyr.hex
          - build/zephyr/zephyr.elf
          - build/zephyr/zephyr.bin

    - step: &run-emulation-tests
        name: Emulation Tests
        caches:
          - west-modules
          - ccache
          - pip
        script:
          - west init -l firmware/
          - west update --narrow --fetch-opt=--depth=1
          - west twister -p native_sim -T tests/ -v
          - west twister -p qemu_cortex_m3 -T tests/ -v
        artifacts:
          - twister-out/twister.xml
          - twister-out/twister.json

    - step: &run-hardware-tests
        name: Hardware Tests
        runs-on:
          - self.hosted
          - linux
          - hil-station-1
        script:
          - west init -l firmware/
          - west update --narrow --fetch-opt=--depth=1
          - west twister
              --device-testing
              --hardware-map /etc/hil/hardware_map.yaml
              -T tests/
              --flash-before
              -v
        artifacts:
          - twister-out/twister.xml
          - twister-out/twister.json

pipelines:
  default:
    - step: *build-firmware
    - step: *run-emulation-tests

  branches:
    main:
      - step: *build-firmware
      - step: *run-emulation-tests
      - step: *run-hardware-tests

  pull-requests:
    '**':
      - step: *build-firmware
      - step: *run-emulation-tests
```

#### Self-Hosted Runner for HIL Testing

Bitbucket Pipelines self-hosted runners run on your own infrastructure. Set up one on each
test station (e.g., Raspberry Pi):

```bash
# On the Raspberry Pi test station:
# 1. Install Docker
# 2. Configure the runner via Bitbucket UI:
#    Repository Settings > Runners > Add Runner
# 3. The runner registers with labels like:
#    self.hosted, linux, hil-station-1
```

In the pipeline YAML, target specific runners:

```yaml
- step:
    name: HIL Tests
    runs-on:
      - self.hosted
      - linux
      - hil-station-1     # Specific station with nRF52840DK attached
    script:
      - west twister --device-testing --hardware-map /etc/hil/hardware_map.yaml ...
```

### 6.2 Webhook-Based Triggering on Submodule Changes

Since Bitbucket Pipelines does not natively trigger builds in a downstream repository when
a submodule changes, use a webhook + API call pattern:

**In the shared-drivers (submodule) repository, add a webhook:**

1. Go to Repository Settings > Webhooks > Add Webhook.
2. Set the URL to your intermediary service or directly use a pipeline trigger.
3. Select trigger: "Push" events.

**Option A: Direct API Trigger (recommended)**

Add a pipeline step in the submodule repo that triggers builds in all downstream product
repos:

```yaml
# bitbucket-pipelines.yml (in shared-drivers repo)
pipelines:
  branches:
    main:
      - step:
          name: Test Shared Drivers
          script:
            - west twister -p native_sim -T tests/ -v
      - step:
          name: Trigger Downstream Builds
          script:
            # Trigger product-a pipeline
            - >
              curl -X POST
              -u "${BB_USERNAME}:${BB_APP_PASSWORD}"
              -H "Content-Type: application/json"
              "https://api.bitbucket.org/2.0/repositories/${BB_WORKSPACE}/product-a/pipelines/"
              -d '{
                "target": {
                  "ref_type": "branch",
                  "type": "pipeline_ref_target",
                  "ref_name": "main",
                  "selector": {
                    "type": "custom",
                    "pattern": "submodule-update-test"
                  }
                },
                "variables": [
                  {
                    "key": "SHARED_DRIVERS_COMMIT",
                    "value": "'${BITBUCKET_COMMIT}'"
                  }
                ]
              }'
            # Trigger product-b pipeline
            - >
              curl -X POST
              -u "${BB_USERNAME}:${BB_APP_PASSWORD}"
              -H "Content-Type: application/json"
              "https://api.bitbucket.org/2.0/repositories/${BB_WORKSPACE}/product-b/pipelines/"
              -d '{
                "target": {
                  "ref_type": "branch",
                  "type": "pipeline_ref_target",
                  "ref_name": "main",
                  "selector": {
                    "type": "custom",
                    "pattern": "submodule-update-test"
                  }
                }
              }'
```

**In each product repo, define the custom pipeline:**

```yaml
# bitbucket-pipelines.yml (in product-a repo)
pipelines:
  custom:
    submodule-update-test:
      - step:
          name: Update Submodule and Test
          script:
            - git submodule update --init --remote shared-drivers/
            - west init -l firmware/
            - west update --narrow
            - west twister -p native_sim -T tests/ -v
            - west build -b nrf52840dk/nrf52840 firmware/
```

**Option B: Webhook to Intermediary Service**

For more complex logic (e.g., only trigger if certain files changed), use a lightweight
webhook receiver (AWS Lambda, Cloud Function, or a simple Flask app):

```python
# webhook_handler.py (runs on a server or as a serverless function)
import requests
import json

BB_USERNAME = "ci-bot"
BB_APP_PASSWORD = "app-password-here"
BB_WORKSPACE = "myorg"

DOWNSTREAM_REPOS = ["product-a", "product-b", "product-c"]

def handle_submodule_push(event):
    """Triggered by webhook from shared-drivers repo."""
    commit = event["push"]["changes"][0]["new"]["target"]["hash"]

    for repo in DOWNSTREAM_REPOS:
        trigger_pipeline(repo, commit)

def trigger_pipeline(repo_slug, submodule_commit):
    url = (
        f"https://api.bitbucket.org/2.0/repositories/"
        f"{BB_WORKSPACE}/{repo_slug}/pipelines/"
    )
    payload = {
        "target": {
            "ref_type": "branch",
            "type": "pipeline_ref_target",
            "ref_name": "main",
            "selector": {
                "type": "custom",
                "pattern": "submodule-update-test"
            }
        },
        "variables": [
            {"key": "SHARED_DRIVERS_COMMIT", "value": submodule_commit}
        ]
    }
    response = requests.post(
        url, json=payload, auth=(BB_USERNAME, BB_APP_PASSWORD)
    )
    return response.status_code
```

### 6.3 Build Caching Strategies for Zephyr

Zephyr builds are slow. Caching is essential for CI performance.

#### ccache (Compilation Cache)

ccache caches compiled object files. When the same source file is compiled with the same
flags, ccache returns the cached result instantly.

```yaml
# bitbucket-pipelines.yml
definitions:
  caches:
    ccache:
      path: /root/.cache/ccache
      key:
        files:
          - "west.yml"          # Invalidate when dependencies change

steps:
  - step:
      caches:
        - ccache
      script:
        - export CCACHE_DIR=/root/.cache/ccache
        - export CCACHE_MAXSIZE=2G
        - export USE_CCACHE=1
        - west build -b nrf52840dk/nrf52840 firmware/
```

#### West Module Cache

The `west update` step downloads all Zephyr modules, which can take several minutes.
Cache the workspace:

```yaml
definitions:
  caches:
    west-workspace:
      path: /workspace
      key:
        files:
          - "west.yml"          # Invalidate when manifest changes
```

#### Docker Image with Pre-installed SDK

Instead of installing the Zephyr SDK every build, use the official CI Docker image or
build a custom one with your SDK version pre-installed:

```dockerfile
# Dockerfile.ci
FROM ghcr.io/zephyrproject-rtos/ci:v0.26.14

# Pre-install west and any additional Python deps
RUN pip3 install west pyocd

# Pre-fetch the Zephyr SDK if not included in base image
# (The official CI image already includes it)
```

```yaml
# bitbucket-pipelines.yml
image:
  name: myregistry/zephyr-ci:latest
```

#### Incremental Builds with Twister

Use `--no-clean` to reuse previous build artifacts (use cautiously -- can cause stale
build issues):

```bash
west twister -T tests/ --no-clean -n
```

### 6.4 Test Result Aggregation and Reporting

#### JUnit XML for CI Dashboards

Twister's `twister.xml` is JUnit-compatible. Most CI systems parse it natively:

**Bitbucket Pipelines** -- no built-in JUnit display, but you can use a pipe:

```yaml
- step:
    name: Test and Report
    script:
      - west twister -p native_sim -T tests/ -o test-reports/ -v
    after-script:
      # Upload test results as artifacts
      - cp test-reports/twister.xml test-results/
    artifacts:
      - test-reports/**
```

**For richer reporting**, parse `twister.json` in a post-processing step:

```python
#!/usr/bin/env python3
"""parse_twister_results.py -- Generate a summary from twister.json."""
import json
import sys

def summarize(json_path):
    with open(json_path) as f:
        data = json.load(f)

    testsuites = data.get("testsuites", [])
    total = len(testsuites)
    passed = sum(1 for t in testsuites if t.get("status") == "passed")
    failed = sum(1 for t in testsuites if t.get("status") == "failed")
    skipped = sum(1 for t in testsuites if t.get("status") == "skipped")
    errors = sum(1 for t in testsuites if t.get("status") == "error")

    print(f"Total: {total}  Passed: {passed}  Failed: {failed}  "
          f"Skipped: {skipped}  Errors: {errors}")

    if failed > 0 or errors > 0:
        print("\nFailed/Error tests:")
        for t in testsuites:
            if t.get("status") in ("failed", "error"):
                print(f"  - {t['name']} ({t.get('platform', 'unknown')}): "
                      f"{t.get('reason', 'no reason')}")
        return 1
    return 0

sys.exit(summarize(sys.argv[1]))
```

#### Aggregating Results Across Multiple Test Runs

When running separate Twister invocations (e.g., emulation + hardware), merge the XML
files:

```bash
# Install junit-xml-merge or use xmlstarlet
pip install junitparser

python3 -c "
from junitparser import JUnitXml
xml1 = JUnitXml.fromfile('twister-out-emulation/twister.xml')
xml2 = JUnitXml.fromfile('twister-out-hardware/twister.xml')
xml1 += xml2
xml1.write('combined-results.xml')
"
```

### 6.5 Complete CI/CD Pipeline Example

The following shows a full pipeline for a product repository with shared drivers as a
submodule:

```yaml
# bitbucket-pipelines.yml
image: ghcr.io/zephyrproject-rtos/ci:v0.26.14

definitions:
  caches:
    west-modules:
      path: /workspace/modules
      key:
        files:
          - west.yml
    ccache:
      path: /root/.cache/ccache

pipelines:
  # ---------------------------------------------------------------
  # Triggered on every push to any branch
  # ---------------------------------------------------------------
  default:
    - parallel:
        - step:
            name: Build (nRF52840)
            caches: [west-modules, ccache]
            script:
              - export CCACHE_DIR=/root/.cache/ccache && export USE_CCACHE=1
              - west init -l firmware/ && west update --narrow --fetch-opt=--depth=1
              - west build -b nrf52840dk/nrf52840 firmware/
            artifacts:
              - build/**

        - step:
            name: Emulation Tests
            caches: [west-modules, ccache]
            script:
              - export CCACHE_DIR=/root/.cache/ccache && export USE_CCACHE=1
              - west init -l firmware/ && west update --narrow --fetch-opt=--depth=1
              - west twister -p native_sim -T tests/ -o test-reports-emu/ -v
              - west twister -p qemu_cortex_m3 -T tests/ -o test-reports-qemu/ -v
            artifacts:
              - test-reports-emu/twister.xml
              - test-reports-qemu/twister.xml

  # ---------------------------------------------------------------
  # Triggered on push to main (includes HIL tests)
  # ---------------------------------------------------------------
  branches:
    main:
      - parallel:
          - step:
              name: Build All Targets
              caches: [west-modules, ccache]
              script:
                - export CCACHE_DIR=/root/.cache/ccache && export USE_CCACHE=1
                - west init -l firmware/ && west update --narrow --fetch-opt=--depth=1
                - west build -b nrf52840dk/nrf52840 firmware/
                - west build -b nucleo_l476rg firmware/ --build-dir build-stm32
              artifacts:
                - build/**
                - build-stm32/**

          - step:
              name: Emulation Tests
              caches: [west-modules, ccache]
              script:
                - export CCACHE_DIR=/root/.cache/ccache && export USE_CCACHE=1
                - west init -l firmware/ && west update --narrow --fetch-opt=--depth=1
                - west twister -p native_sim -T tests/ -o test-reports-emu/ -v
              artifacts:
                - test-reports-emu/twister.xml

      - step:
          name: Hardware-in-the-Loop Tests
          runs-on:
            - self.hosted
            - linux
            - hil-station
          script:
            - west init -l firmware/ && west update --narrow --fetch-opt=--depth=1
            - west twister
                --device-testing
                --hardware-map /etc/hil/hardware_map.yaml
                -T tests/
                --flash-before
                -o test-reports-hil/
                -v
          artifacts:
            - test-reports-hil/twister.xml
            - test-reports-hil/twister.json

      - step:
          name: Aggregate Results
          script:
            - pip install junitparser
            - python3 scripts/ci/merge_junit.py
                test-reports-emu/twister.xml
                test-reports-hil/twister.xml
                --output combined-results.xml
            - python3 scripts/ci/parse_twister_results.py
                test-reports-hil/twister.json
          artifacts:
            - combined-results.xml

  # ---------------------------------------------------------------
  # Custom pipeline triggered by shared-drivers submodule webhook
  # ---------------------------------------------------------------
  custom:
    submodule-update-test:
      - step:
          name: Submodule Integration Test
          caches: [west-modules, ccache]
          script:
            - git submodule update --init --remote shared-drivers/
            - export CCACHE_DIR=/root/.cache/ccache && export USE_CCACHE=1
            - west init -l firmware/ && west update --narrow --fetch-opt=--depth=1
            - west twister -p native_sim -T tests/ -v
            - west build -b nrf52840dk/nrf52840 firmware/
```

---

## Quick Reference: Common Twister Commands

```bash
# --- Discovery and Dry Run ---
west twister -T tests/ --list-tests                    # List all discovered tests
west twister -T tests/ -p native_sim --cmake-only      # Only run CMake (validate config)

# --- Emulation Testing ---
west twister -p native_sim -T tests/ -v                # Run on native simulator
west twister -p qemu_cortex_m3 -T tests/ -v            # Run on QEMU
west twister --emulation-only -T tests/                 # All emulated platforms

# --- Hardware Testing ---
west twister --device-testing \
  --device-serial /dev/ttyACM0 \
  -p nrf52840dk/nrf52840 \
  -T tests/ --flash-before -v                          # Single device

west twister --device-testing \
  --hardware-map hardware_map.yaml \
  -T tests/ --flash-before -v                          # Multiple devices

# --- Filtering ---
west twister -T tests/ -t sensor                       # Filter by tag
west twister -T tests/ -e slow                         # Exclude tag
west twister -T tests/ -s tests/drivers/sensor/bme680/test.basic  # Specific scenario
west twister -T tests/ --platform-pattern "nrf.*"      # Platform regex

# --- CI Optimization ---
west twister -T tests/ -B 1/4                          # Run 25% subset (for parallelism)
west twister -T tests/ -f                              # Rerun only previously failed
west twister -T tests/ --retry-failed 2                # Retry failures up to 2 times

# --- Reporting ---
west twister -T tests/ -o reports/ --report-name run1  # Custom output dir and name
west twister -T tests/ --report-summary 20             # Print top 20 failures

# --- Coverage ---
west twister -p native_sim -T tests/ \
  --enable-coverage -C                                 # Generate gcov coverage report
```

---

## Sources and Further Reading

- [Twister Test Runner -- Zephyr Project Documentation](https://docs.zephyrproject.org/latest/develop/test/twister.html)
- [Integration with pytest test framework -- Zephyr Documentation](https://docs.zephyrproject.org/latest/develop/test/pytest.html)
- [ztest Test Framework -- Zephyr Documentation](https://docs.zephyrproject.org/latest/develop/test/ztest.html)
- [External Bus and Bus Connected Peripherals Emulators -- Zephyr Documentation](https://docs.zephyrproject.org/latest/hardware/emulator/bus_emulators.html)
- [Zephyr's Device Emulators/Simulators -- Zephyr Documentation](https://docs.zephyrproject.org/latest/hardware/emulator/index.html)
- [How to use Twister to cycle test Zephyr devices -- Jumptuck (2024)](https://jumptuck.com/blog/2024-02-10-twister-device-testing/)
- [Golioth HIL Testing with Twister -- GitHub](https://github.com/golioth/zephyr_twister_hil_testing)
- [Automated hardware testing using pytest -- Golioth Blog (2024)](https://blog.golioth.io/automated-hardware-testing-using-pytest/)
- [Writing a Zephyr Peripheral Emulator -- Jonas Otto](https://jonasotto.com/posts/zephyr_emulators/)
- [Using Emulators and Fake Devices in Zephyr -- Mind Blog](https://mind.be/blog/using-emulators-and-fake-devices-in-zephyr/)
- [Unit Testing Embedded Systems with Zephyr/Ztest -- MistyWest (2024)](https://www.mistywest.com/wp-content/uploads/2024/10/MistyWest-Unit-Testing-Embedded-Systems-with-Zephyr-Ztest-Oct-2024.pdf)
- [Pytest Tests in Twister -- EOSS 2024 Presentation](https://eoss24.sched.com/event/1aBGT/pytest-tests-in-twister-maciej-perkowski-nordic-semiconductor)
- [Hardware CI Arena -- Electric UI](https://electricui.com/blog/hardware-testing)
- [Bitbucket Pipelines Runners -- Atlassian Support](https://support.atlassian.com/bitbucket-cloud/docs/runners/)
- [Bitbucket Pipelines Cache Dependencies -- Atlassian Support](https://support.atlassian.com/bitbucket-cloud/docs/cache-dependencies/)
- [Bitbucket REST API: Pipelines -- Atlassian Developer](https://developer.atlassian.com/cloud/bitbucket/rest/api-group-pipelines/)
- [Embedded CI/CD -- embedded-cicd.org](https://embedded-cicd.org/)
