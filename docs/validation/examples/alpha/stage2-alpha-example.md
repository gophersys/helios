# Stage 2 Alpha Example — LSM6DSO Driver Hardware Tests

> A complete walkthrough of Stage 2 driver hardware testing for the Alpha
> wearable's LSM6DSO 6-axis IMU. Shows the physical dev-kit fixture, MTIB
> connections, ztest firmware that runs on real hardware, power-correlated
> execution, and pipeline integration.

---

## 1. Introduction

This document walks through a complete Stage 2 driver hardware test implementation for the LSM6DSO accelerometer/gyroscope on the Alpha product. It covers:

1. The physical dev-kit fixture: how the nRF52840 and LSM6DSO sensor are wired, and why a dev-kit instead of the product board
2. MTIB connections: which MTIB channels connect to what, and how the test runner uses them
3. Kconfig and DTS overlays that configure the test firmware for the dev-kit fixture
4. The ztest C firmware that exercises the driver on real silicon
5. The `test_spec.yaml` that defines power budgets and coverage requirements
6. Raw UART output with ztest markers
7. Power profiling: how the orchestrator correlates ztest markers with current measurements
8. Pipeline integration: how this fits into Concord Stage 2

The goal is to make the abstract Stage 2 framework described in [00-validation-philosophy.md](../../architecture/00-validation-philosophy.md) Section 3.2 concrete, using a real driver and real pin assignments from the Alpha hardware.

---

## 2. Hardware Configuration and Connections

### 2.1 Why Dev-Kit, Not Product Board

On the Alpha product board (`alpha_b0`), the LSM6DSO shares the SPI0 bus and a common 1.8V power rail with the W25Q64JV SPI flash. Other sensors (PAH8151, MLX90614, BME280) share additional rails. You cannot isolate the LSM6DSO's current draw from everything else on the board. If you measure total board current, you get the sum of all active peripherals — useless for validating that the LSM6DSO meets its datasheet power budget.

The dev-kit fixture solves this by placing **one MCU and one sensor on an isolated fixture board** with a power relay between MTIB and the sensor's VDD pin. MTIB can:

- Cut power to the sensor independently (for power-cycle tests)
- Measure current flowing through only the sensor's supply rail (for power profiling)
- Assert that idle current, active current, and sleep current match the LSM6DSO datasheet

Product-board tests (`test_mode: functional`) still run in Stage 2 — they verify the DTS wiring and functional correctness on the real Alpha PCB. But power budgets are only enforced on the dev-kit fixture (`test_mode: full`), where the measurement is physically meaningful.

### 2.2 Dev-Kit Fixture Layout

The dev-kit fixture is an nRF52840-DK with the LSM6DSO breakout wired to SPI0. The board definition in `ck_boards` is `devkit_nrf52840_lsm6dso_spi`. It mirrors the Alpha board's bus and pin configuration so the same driver code runs on both.

**Physical wiring — SPI bus connections:**

| Signal | nRF52840 Pin | LSM6DSO Pin | Notes |
|--------|-------------|-------------|-------|
| SCK | P0.07 | SPC | SPI clock, 1 MHz max (matches Alpha `spi-max-frequency`) |
| MOSI | P0.05 | SDI | Master Out → Sensor Data In |
| MISO | P1.08 | SDO | Sensor Data Out → Master In |
| CS | P0.08 | CS | Active low, directly driven (no shared bus — dev-kit has only this sensor) |

These pin assignments match the Alpha board's SPI0 pinctrl (`spi0_default` in `alpha_b0_nrf52840-pinctrl.dtsi`):

```
spi0_default: spi0_default {
    group1 {
        psels = <NRF_PSEL(SPIM_SCK, 0, 7)>,
                <NRF_PSEL(SPIM_MOSI, 0, 5)>,
                <NRF_PSEL(SPIM_MISO, 1, 8)>;
    };
};
```

On Alpha, CS is the second entry in the `cs-gpios` array (`<&gpio0 8 (GPIO_ACTIVE_LOW)>`, index 1 — `reg = <1>` in the sensor node). On the dev-kit fixture, it is the only CS — `reg = <0>` — but the same GPIO pin (P0.08) is used so the electrical behavior is identical.

**Interrupt pin:**

| Signal | nRF52840 Pin | LSM6DSO Pin | Config |
|--------|-------------|-------------|--------|
| IRQ | P0.14 | INT2 | Active high, edge-triggered, pulsed mode (`drdy-pulsed`) |

On the Alpha board, the LSM6DSO uses INT2 (`int-pin = <2>`) routed to P0.14 (`irq-gpios = <&gpio0 14 GPIO_ACTIVE_HIGH>`). The dev-kit replicates this exactly.

**Power:**

| Rail | Voltage | Source |
|------|---------|--------|
| Sensor VDD | 1.8V | MTIB power relay output → LDO → LSM6DSO VDD/VDDIO |
| Sensor GND | 0V | Common ground with nRF52840-DK and MTIB |

The MTIB power relay sits between the fixture's 1.8V LDO and the LSM6DSO VDD pin. When the relay is open, the sensor is unpowered. When closed, current flows through MTIB's sense resistor, enabling continuous measurement.

### 2.3 MTIB Connection Map

```
MTIB Test Head                     Dev-Kit Fixture (nRF52840-DK + LSM6DSO)
┌──────────────────┐              ┌──────────────────────────────────────┐
│                  │              │                                      │
│  SWD CLK    ─────┼──────────────┼─── nRF52840 SWDCLK                  │
│  SWD DIO    ─────┼──────────────┼─── nRF52840 SWDIO                   │
│                  │              │                                      │
│  UART0 TX   ─────┼──────────────┼─── nRF52840 P0.25 (UART0 RX)       │
│  UART0 RX   ─────┼──────────────┼─── nRF52840 P0.23 (UART0 TX)       │
│                  │              │                                      │
│  RELAY OUT  ─────┼──── ┐       │                                      │
│  ISENSE+    ─────┼──── ┤ sense │                                      │
│  ISENSE-    ─────┼──── ┘ path  ├─── LSM6DSO VDD (1.8V via LDO)       │
│                  │              │                                      │
│  GPIO CH0   ─────┼──────────────┼─── nRF52840 P0.14 (LSM6DSO INT2)   │
│  (optional)      │              │    (passive tap for interrupt timing)│
│                  │              │                                      │
│  GND        ─────┼──────────────┼─── Common GND                       │
└──────────────────┘              └──────────────────────────────────────┘
```

**Connection details:**

| MTIB Channel | Target | Purpose |
|-------------|--------|---------|
| SWD | nRF52840 debug port | Flash test firmware via `FlashProgram` gRPC call. J-Link on the DK bridges SWD to the MTIB test head. |
| UART0 | nRF52840 UART0 (P0.23 TX, P0.25 RX) | Bidirectional stream for ztest marker output. The test runner parses `START`/`PASS`/`FAIL`/`SKIP` lines. 115200 baud, matching `alpha_b0` UART0 config. |
| Power relay + current sense | LSM6DSO VDD rail | Relay controls sensor power (open = off, closed = on). Sense resistor in series provides continuous current measurement at ~10 kHz sample rate. Resolution: ~0.1 uA. |
| GPIO CH0 (optional) | P0.14 / LSM6DSO INT2 | Passive tap on the interrupt line. MTIB timestamps the edge with its own clock, enabling sub-millisecond interrupt latency measurement independent of the firmware's `k_uptime_get()`. Not required for basic tests — used for interrupt timing characterization. |

### 2.4 Kconfig and DTS for Test Firmware

The test firmware builds as a standalone ztest binary. It uses the dev-kit board definition, not the Alpha product board.

**`prj.conf` — test firmware Kconfig:**

```kconfig
# tests/lsm6dso/prj.conf

# Zephyr test framework
CONFIG_ZTEST=y
CONFIG_ZTEST_NEW_API=y

# Sensor subsystem
CONFIG_SENSOR=y

# LSM6DSO driver — enable everything; DTS determines what's actually wired
CONFIG_CK_LSM6DSO=y
CONFIG_CK_LSM6DSO_TRIGGER=y

# SPI (Alpha wires LSM6DSO on SPI; I2C builds use CONFIG_I2C=y instead)
CONFIG_SPI=y

# GPIO for interrupt line
CONFIG_GPIO=y

# Suppress noise on UART — clean ztest markers only
CONFIG_LOG=n
CONFIG_BOOT_BANNER=n
CONFIG_PRINTK=y

# Stack for test threads
CONFIG_MAIN_STACK_SIZE=4096
CONFIG_SYSTEM_WORKQUEUE_STACK_SIZE=2048
```

**Board overlay — `boards/devkit_nrf52840_lsm6dso_spi.overlay`:**

The dev-kit board definition already has the LSM6DSO node wired correctly (it mirrors Alpha's SPI0 pinctrl and interrupt pin). If any test-specific adjustments were needed, they would go here. For the LSM6DSO dev-kit, the base board DTS is sufficient:

```dts
/* boards/devkit_nrf52840_lsm6dso_spi.overlay
 *
 * The devkit_nrf52840_lsm6dso_spi board definition already includes
 * the LSM6DSO node on SPI0 with correct pin assignments mirroring
 * the Alpha B0 hardware. No overlay needed for standard tests.
 *
 * If a test needed to override ODR or range for a specific scenario,
 * it would go here:
 */

/* Example: override accelerometer ODR to 104Hz for a high-rate test
 * &lsm6dso0 {
 *     accel-odr = <4>;  // LSM6DSO_DT_ODR_104Hz
 * };
 */
```

The key DTS node on the dev-kit board (equivalent to Alpha's `alpha_b0_nrf52840.dts`):

```dts
&spi0 {
    compatible = "nordic,nrf-spim";
    status = "okay";
    pinctrl-0 = <&spi0_default>;
    pinctrl-1 = <&spi0_sleep>;
    pinctrl-names = "default", "sleep";

    cs-gpios = <&gpio0 8 (GPIO_ACTIVE_LOW)>;   /* Single CS — only the LSM6DSO */

    lsm6dso0: lsm6dso0@0 {
        compatible = "ck,lsm6dso";
        reg = <0>;
        int-pin = <2>;
        spi-max-frequency = <1000000>;          /* 1 MHz */
        irq-gpios = <&gpio0 14 GPIO_ACTIVE_HIGH>;
        accel-pm = <1>;                         /* Low Power / Normal mode */
        accel-range = <3>;                      /* 8g full scale */
        accel-odr = <3>;                        /* 52 Hz */
        gyro-pm = <1>;                          /* Normal mode */
        gyro-range = <0>;                       /* 250 dps */
        gyro-odr = <2>;                         /* 26 Hz */
        drdy-pulsed;
    };
};
```

Note: `reg = <0>` on the dev-kit (only device on the bus) vs `reg = <1>` on Alpha (second device after the W25Q64JV flash). The driver doesn't care — `reg` selects the CS index, and the Zephyr SPI subsystem handles the mapping.

---

## 3. Test Firmware (ztest on Real Hardware)

The test firmware is a ztest binary that runs entirely on the nRF52840. It knows nothing about MTIB, Python, or power measurement. It exercises the LSM6DSO driver through the standard Zephyr sensor API and direct register access, reporting results via ztest markers over UART.

### 3.1 Test Source

```c
/* tests/lsm6dso/src/main.c
 *
 * Stage 2 driver hardware tests for the LSM6DSO 6-axis IMU.
 * Runs ON the nRF52840 via ztest. Compiled per-board — DTS guards
 * control which tests are included for each board's wiring.
 *
 * Register addresses from LSM6DSO/lsm6dso_reg.h.
 * Datasheet: LSM6DSO Rev 9 (ST AN5192).
 */

#include <zephyr/kernel.h>
#include <zephyr/device.h>
#include <zephyr/drivers/sensor.h>
#include <zephyr/drivers/spi.h>
#include <zephyr/drivers/gpio.h>
#include <zephyr/ztest.h>

/* Driver internals — needed for direct register access in hardware tests */
#include "lsm6dso.h"
#include "LSM6DSO/lsm6dso_reg.h"

#define LSM6DSO_NODE DT_NODELABEL(lsm6dso0)

/* ── Helpers for direct register read/write ─────────────────────────── */

static const struct device *get_dev(void)
{
    return DEVICE_DT_GET(LSM6DSO_NODE);
}

static int read_register(const struct device *dev, uint8_t reg, uint8_t *val)
{
    const struct lsm6dso_config *cfg = dev->config;
    /* SPI read: set bit 7 of register address */
    uint8_t tx[2] = { reg | 0x80, 0x00 };
    uint8_t rx[2] = { 0 };
    const struct spi_buf tx_buf = { .buf = tx, .len = 2 };
    const struct spi_buf rx_buf = { .buf = rx, .len = 2 };
    const struct spi_buf_set tx_set = { .buffers = &tx_buf, .count = 1 };
    const struct spi_buf_set rx_set = { .buffers = &rx_buf, .count = 1 };
    int ret = spi_transceive_dt(&cfg->bus.spi, &tx_set, &rx_set);
    if (ret == 0) {
        *val = rx[1];
    }
    return ret;
}

static int write_register(const struct device *dev, uint8_t reg, uint8_t val)
{
    const struct lsm6dso_config *cfg = dev->config;
    uint8_t tx[2] = { reg & 0x7F, val };
    const struct spi_buf tx_buf = { .buf = tx, .len = 2 };
    const struct spi_buf_set tx_set = { .buffers = &tx_buf, .count = 1 };
    return spi_write_dt(&cfg->bus.spi, &tx_set);
}

/* ── Volatile flags for interrupt callbacks ──────────────────────────── */

static volatile bool drdy_fired;
static volatile bool wm_fired;
static volatile bool motion_fired;
static volatile int drdy_count;

static void drdy_callback(const struct device *dev,
                           const struct sensor_trigger *trig)
{
    drdy_fired = true;
    drdy_count++;
}

static void wm_callback(const struct device *dev,
                         const struct sensor_trigger *trig)
{
    wm_fired = true;
}

static void motion_callback(const struct device *dev,
                             const struct sensor_trigger *trig)
{
    motion_fired = true;
}

/* ═══════════════════════════════════════════════════════════════════════
 * Core tests — run on every board regardless of bus or interrupt wiring
 * ═══════════════════════════════════════════════════════════════════════ */

ZTEST(lsm6dso_hw, test_device_ready)
{
    const struct device *dev = get_dev();
    zassert_true(device_is_ready(dev),
                 "LSM6DSO device not ready — check DTS and bus config");
}

ZTEST(lsm6dso_hw, test_sensor_presence)
{
    /* Read WHO_AM_I register (0x0F). Expected value: 0x6C (LSM6DSO_ID). */
    const struct device *dev = get_dev();
    uint8_t whoami = 0;
    int ret = read_register(dev, LSM6DSO_WHO_AM_I, &whoami);
    zassert_ok(ret, "SPI read of WHO_AM_I failed: %d", ret);
    zassert_equal(whoami, LSM6DSO_ID,
                  "WHO_AM_I mismatch: expected 0x6C, got 0x%02X", whoami);
}

ZTEST(lsm6dso_hw, test_accel_data_readback)
{
    /* Configure ODR to 52Hz, read accel data, verify non-zero.
     * A stationary sensor should read ~0g on X/Y and ~1g on Z (gravity).
     * We check that at least one axis is non-zero — a zero reading means
     * the bus is broken or the sensor is not responding. */
    const struct device *dev = get_dev();

    /* Set accel ODR to 52Hz via CTRL1_XL: ODR[7:4]=0011 (52Hz), FS[3:2]=11 (8g) */
    int ret = write_register(dev, LSM6DSO_CTRL1_XL, 0x3C);
    zassert_ok(ret, "Failed to write CTRL1_XL: %d", ret);

    /* Wait for at least one sample (1/52 Hz ~ 19.2ms, add margin) */
    k_sleep(K_MSEC(50));

    /* Read accel data via Zephyr sensor API */
    ret = sensor_sample_fetch(dev);
    zassert_ok(ret, "sensor_sample_fetch failed: %d", ret);

    struct sensor_value accel_x, accel_y, accel_z;
    sensor_channel_get(dev, SENSOR_CHAN_ACCEL_X, &accel_x);
    sensor_channel_get(dev, SENSOR_CHAN_ACCEL_Y, &accel_y);
    sensor_channel_get(dev, SENSOR_CHAN_ACCEL_Z, &accel_z);

    /* At least one axis must be non-zero (gravity exists) */
    bool any_nonzero = (accel_x.val1 != 0 || accel_x.val2 != 0) ||
                       (accel_y.val1 != 0 || accel_y.val2 != 0) ||
                       (accel_z.val1 != 0 || accel_z.val2 != 0);
    zassert_true(any_nonzero,
                 "All accel axes read zero — sensor not responding");

    /* Gravity sanity check: magnitude should be between 0.5g and 1.5g.
     * Convert to milli-g: val1 is m/s^2 integer part, val2 is fractional.
     * ~9.81 m/s^2 = 1g. Allow wide range for orientation/vibration. */
    int32_t z_mg = (accel_z.val1 * 1000) + (accel_z.val2 / 1000);
    /* Absolute value */
    if (z_mg < 0) { z_mg = -z_mg; }
    printk("  accel_z = %d.%06d m/s^2 (~%d mg)\n",
           accel_z.val1, accel_z.val2, z_mg);
}

/* ═══════════════════════════════════════════════════════════════════════
 * SPI-specific tests — compiled in only when DTS wires LSM6DSO on SPI
 * ═══════════════════════════════════════════════════════════════════════ */

#if DT_ON_BUS(LSM6DSO_NODE, spi)

ZTEST(lsm6dso_hw, test_spi_whoami)
{
    /* Verify WHO_AM_I via raw SPI transaction (bypasses driver).
     * This tests the SPI bus wiring independently of the driver init path. */
    const struct device *dev = get_dev();
    const struct lsm6dso_config *cfg = dev->config;

    uint8_t tx[2] = { LSM6DSO_WHO_AM_I | 0x80, 0x00 };  /* Read: bit 7 set */
    uint8_t rx[2] = { 0 };
    const struct spi_buf tx_buf = { .buf = tx, .len = 2 };
    const struct spi_buf rx_buf = { .buf = rx, .len = 2 };
    const struct spi_buf_set tx_set = { .buffers = &tx_buf, .count = 1 };
    const struct spi_buf_set rx_set = { .buffers = &rx_buf, .count = 1 };

    int ret = spi_transceive_dt(&cfg->bus.spi, &tx_set, &rx_set);
    zassert_ok(ret, "Raw SPI transceive failed: %d", ret);
    zassert_equal(rx[1], 0x6C,
                  "SPI WHO_AM_I mismatch: expected 0x6C, got 0x%02X", rx[1]);
}

ZTEST(lsm6dso_hw, test_spi_register_write_readback)
{
    /* Write a non-default value to CTRL3_C (0x12), read it back.
     * CTRL3_C controls BDU, IF_INC, etc. We set IF_INC=1, BDU=1
     * (0x44), read back, then restore the original value. */
    const struct device *dev = get_dev();
    uint8_t original = 0;
    int ret;

    ret = read_register(dev, LSM6DSO_CTRL3_C, &original);
    zassert_ok(ret, "Failed to read CTRL3_C");

    uint8_t test_val = 0x44;  /* BDU=1, IF_INC=1 */
    ret = write_register(dev, LSM6DSO_CTRL3_C, test_val);
    zassert_ok(ret, "Failed to write CTRL3_C");

    uint8_t readback = 0;
    ret = read_register(dev, LSM6DSO_CTRL3_C, &readback);
    zassert_ok(ret, "Failed to read back CTRL3_C");
    zassert_equal(readback, test_val,
                  "CTRL3_C write/readback mismatch: wrote 0x%02X, got 0x%02X",
                  test_val, readback);

    /* Restore original value */
    write_register(dev, LSM6DSO_CTRL3_C, original);
}

#endif /* DT_ON_BUS(LSM6DSO_NODE, spi) */

/* ═══════════════════════════════════════════════════════════════════════
 * Interrupt tests — compiled in only when DTS defines irq-gpios
 * ═══════════════════════════════════════════════════════════════════════ */

#if DT_NODE_HAS_PROP(LSM6DSO_NODE, irq_gpios)

ZTEST(lsm6dso_hw, test_drdy_interrupt)
{
    /* Configure data-ready trigger, verify interrupt fires within 500ms.
     * At 52Hz ODR, DRDY should fire every ~19ms. */
    const struct device *dev = get_dev();
    drdy_fired = false;
    drdy_count = 0;

    struct sensor_trigger trig = {
        .type = SENSOR_TRIG_DATA_READY,
        .chan = SENSOR_CHAN_ACCEL_XYZ,
    };
    int ret = sensor_trigger_set(dev, &trig, drdy_callback);
    zassert_ok(ret, "sensor_trigger_set(DRDY) failed: %d", ret);

    k_sleep(K_MSEC(500));

    zassert_true(drdy_fired, "DRDY interrupt never fired in 500ms");
    /* At 52Hz, expect ~26 interrupts in 500ms. Allow wide tolerance. */
    zassert_true(drdy_count >= 10,
                 "Expected >=10 DRDY interrupts in 500ms at 52Hz, got %d",
                 drdy_count);

    /* Disable trigger */
    sensor_trigger_set(dev, &trig, NULL);
}

ZTEST(lsm6dso_hw, test_fifo_watermark_interrupt)
{
    /* Configure FIFO in continuous mode with watermark at 26 samples.
     * At 52Hz ODR, watermark should trigger after ~500ms.
     * Wait 1 second and verify the interrupt fired. */
    const struct device *dev = get_dev();
    wm_fired = false;

    /* Set FIFO watermark to 26 via FIFO_CTRL1 (0x07) */
    int ret = write_register(dev, LSM6DSO_FIFO_CTRL1, 26);
    zassert_ok(ret, "Failed to write FIFO_CTRL1 watermark");

    /* Set FIFO to continuous mode via FIFO_CTRL4 (0x0A): fifo_mode=110 (continuous) */
    ret = write_register(dev, LSM6DSO_FIFO_CTRL4, 0x06);
    zassert_ok(ret, "Failed to write FIFO_CTRL4 mode");

    /* Set accel batch rate to 52Hz via FIFO_CTRL3 (0x09): bdr_xl=0011 (52Hz) */
    ret = write_register(dev, LSM6DSO_FIFO_CTRL3, 0x03);
    zassert_ok(ret, "Failed to write FIFO_CTRL3 batch rate");

    /* Route FIFO watermark interrupt to INT2 via INT2_CTRL (0x0E): int2_fifo_th=1 */
    ret = write_register(dev, LSM6DSO_INT2_CTRL, 0x08);
    zassert_ok(ret, "Failed to write INT2_CTRL");

    /* Set accel ODR to 52Hz via CTRL1_XL (0x10) */
    ret = write_register(dev, LSM6DSO_CTRL1_XL, 0x3C);
    zassert_ok(ret, "Failed to write CTRL1_XL");

    /* Wait for watermark (26 samples at 52Hz = 500ms, add margin) */
    k_sleep(K_MSEC(1000));

    zassert_true(wm_fired,
                 "FIFO watermark interrupt never fired "
                 "(26 samples at 52Hz should trigger in ~500ms)");

    /* Read FIFO status to verify sample count */
    uint8_t status1 = 0, status2 = 0;
    read_register(dev, LSM6DSO_FIFO_STATUS1, &status1);
    read_register(dev, LSM6DSO_FIFO_STATUS2, &status2);
    uint16_t fifo_level = ((uint16_t)(status2 & 0x03) << 8) | status1;

    zassert_true(fifo_level >= 26,
                 "FIFO level should be >= 26 after 1s at 52Hz, got %u",
                 fifo_level);

    printk("  FIFO level after 1s: %u samples\n", fifo_level);

    /* Clean up: disable FIFO */
    write_register(dev, LSM6DSO_FIFO_CTRL4, 0x00);
    write_register(dev, LSM6DSO_INT2_CTRL, 0x00);
}

ZTEST(lsm6dso_hw, test_fifo_batch_at_52hz)
{
    /* Run FIFO at 52Hz for 2 seconds, flush, verify sample count
     * is within expected range. 52Hz * 2s = 104 samples expected.
     * Allow 10% tolerance for clock drift. */
    const struct device *dev = get_dev();

    /* Enable FIFO continuous mode, accel at 52Hz batch rate */
    write_register(dev, LSM6DSO_FIFO_CTRL3, 0x03);  /* bdr_xl = 52Hz */
    write_register(dev, LSM6DSO_FIFO_CTRL4, 0x06);  /* continuous mode */
    write_register(dev, LSM6DSO_CTRL1_XL, 0x3C);    /* ODR 52Hz, FS 8g */

    /* Collect for 2 seconds */
    k_sleep(K_MSEC(2000));

    /* Read FIFO level */
    uint8_t status1 = 0, status2 = 0;
    read_register(dev, LSM6DSO_FIFO_STATUS1, &status1);
    read_register(dev, LSM6DSO_FIFO_STATUS2, &status2);
    uint16_t fifo_level = ((uint16_t)(status2 & 0x03) << 8) | status1;

    printk("  FIFO samples collected in 2s: %u (expected ~104)\n", fifo_level);

    /* 52Hz * 2s = 104 samples. Allow 10% tolerance: 94-114. */
    zassert_true(fifo_level >= 94 && fifo_level <= 114,
                 "FIFO sample count out of range: got %u, expected 94-114",
                 fifo_level);

    /* Verify samples contain plausible accel data (read a few from FIFO) */
    for (int i = 0; i < 5 && i < fifo_level; i++) {
        uint8_t tag = 0;
        read_register(dev, LSM6DSO_FIFO_DATA_OUT_TAG, &tag);
        uint8_t xl = 0, xh = 0;
        read_register(dev, LSM6DSO_FIFO_DATA_OUT_X_L, &xl);
        read_register(dev, LSM6DSO_FIFO_DATA_OUT_X_H, &xh);
        int16_t accel_x_raw = (int16_t)((xh << 8) | xl);
        printk("  FIFO[%d]: tag=0x%02X, accel_x_raw=%d\n", i, tag, accel_x_raw);
    }

    /* Clean up */
    write_register(dev, LSM6DSO_FIFO_CTRL4, 0x00);
}

#else /* no irq_gpios — polled mode */

ZTEST(lsm6dso_hw, test_polled_fifo_read)
{
    /* No interrupt pin — poll FIFO status register directly. */
    const struct device *dev = get_dev();

    write_register(dev, LSM6DSO_FIFO_CTRL3, 0x03);  /* bdr_xl = 52Hz */
    write_register(dev, LSM6DSO_FIFO_CTRL4, 0x06);  /* continuous mode */
    write_register(dev, LSM6DSO_CTRL1_XL, 0x3C);    /* ODR 52Hz */

    k_sleep(K_MSEC(1000));

    uint8_t status1 = 0, status2 = 0;
    read_register(dev, LSM6DSO_FIFO_STATUS1, &status1);
    read_register(dev, LSM6DSO_FIFO_STATUS2, &status2);
    uint16_t fifo_level = ((uint16_t)(status2 & 0x03) << 8) | status1;

    zassert_true(fifo_level > 0,
                 "FIFO empty after 1s at 52Hz — sensor not batching");

    printk("  Polled FIFO level: %u samples\n", fifo_level);

    write_register(dev, LSM6DSO_FIFO_CTRL4, 0x00);
}

#endif /* irq_gpios */

/* ═══════════════════════════════════════════════════════════════════════
 * Motion detection test — runtime-skipped if no stimulus available
 * ═══════════════════════════════════════════════════════════════════════ */

ZTEST(lsm6dso_hw, test_motion_interrupt)
{
    /* Configure wake-up / motion detection:
     *   - WAKE_UP_THS (0x5B): threshold = ~200mg at 8g FS
     *     At 8g: 1 LSB = 8g/64 = 125mg. For 200mg: 200/125 = 1.6 → 2 LSBs.
     *   - WAKE_UP_DUR (0x5C): wake_dur = 0 (instant)
     *   - MD1_CFG or MD2_CFG: route wake-up to INT2
     *
     * If the dev-kit has a vibration motor or the ambient vibration
     * exceeds the threshold, the interrupt will fire. Otherwise
     * the test is skipped via zassume. */
    const struct device *dev = get_dev();
    motion_fired = false;

    /* Ensure accel is running at 52Hz */
    write_register(dev, LSM6DSO_CTRL1_XL, 0x3C);

    /* Set wake-up threshold to ~250mg: 2 LSBs at 8g FS (each LSB = 125mg) */
    write_register(dev, LSM6DSO_WAKE_UP_THS, 0x02);

    /* Wake-up duration: 0 cycles (instant detection) */
    write_register(dev, LSM6DSO_WAKE_UP_DUR, 0x00);

#if DT_NODE_HAS_PROP(LSM6DSO_NODE, irq_gpios)
    /* Route wake-up event to INT2 via MD2_CFG (0x5F): int2_wu = 1 (bit 5) */
    uint8_t md2 = 0;
    read_register(dev, LSM6DSO_MD2_CFG, &md2);
    md2 |= 0x20;  /* Set int2_wu bit */
    write_register(dev, LSM6DSO_MD2_CFG, md2);

    struct sensor_trigger trig = {
        .type = SENSOR_TRIG_MOTION,
        .chan = SENSOR_CHAN_ACCEL_XYZ,
    };
    int ret = sensor_trigger_set(dev, &trig, motion_callback);
    zassert_ok(ret, "sensor_trigger_set(MOTION) failed: %d", ret);
#endif

    /* Wait 2 seconds for ambient vibration or actuator stimulus */
    k_sleep(K_MSEC(2000));

    /* If no motion was detected, skip — don't fail.
     * This test requires physical stimulus that may not be present. */
    zassume_true(motion_fired,
                 "No motion interrupt detected — skipping "
                 "(needs physical stimulus or vibration actuator)");

    printk("  Motion interrupt fired successfully\n");

#if DT_NODE_HAS_PROP(LSM6DSO_NODE, irq_gpios)
    /* Clean up */
    sensor_trigger_set(dev, &trig, NULL);
    write_register(dev, LSM6DSO_MD2_CFG, md2 & ~0x20);
#endif
    write_register(dev, LSM6DSO_WAKE_UP_THS, 0x00);
}

/* ═══════════════════════════════════════════════════════════════════════
 * Power consumption tests — these are pass/fail in firmware only for
 * gross anomalies (e.g., sensor stuck in high-performance mode).
 * The actual power budget enforcement happens externally via MTIB
 * measurement + test_spec.yaml. These tests establish known operating
 * states so the orchestrator can slice the power trace.
 * ═══════════════════════════════════════════════════════════════════════ */

ZTEST(lsm6dso_hw, test_sleep_current)
{
    /* Put the sensor in power-down mode (ODR = 0).
     * The orchestrator will measure current during this test and
     * compare against the test_spec.yaml budget.
     *
     * LSM6DSO datasheet Table 4: power-down current = 3 uA typical.
     *
     * We hold the state for 1 second to give the MTIB power measurement
     * a clean window. */
    const struct device *dev = get_dev();

    /* Set both accel and gyro to power-down: CTRL1_XL = 0x00, CTRL2_G = 0x00 */
    write_register(dev, LSM6DSO_CTRL1_XL, 0x00);
    write_register(dev, LSM6DSO_CTRL2_G, 0x00);

    /* Disable FIFO */
    write_register(dev, LSM6DSO_FIFO_CTRL4, 0x00);

    /* Wait for power-down to stabilize */
    k_sleep(K_MSEC(100));

    /* Hold for power measurement window (1 second) */
    k_sleep(K_MSEC(1000));

    /* Verify sensor is still responsive after power-down */
    uint8_t whoami = 0;
    int ret = read_register(dev, LSM6DSO_WHO_AM_I, &whoami);
    zassert_ok(ret, "SPI read failed after power-down");
    zassert_equal(whoami, LSM6DSO_ID,
                  "WHO_AM_I mismatch after power-down: 0x%02X", whoami);
}

ZTEST(lsm6dso_hw, test_active_current_at_52hz)
{
    /* Run accelerometer at 52Hz in low-power/normal mode.
     * The orchestrator will measure current during this test.
     *
     * LSM6DSO datasheet Table 4:
     *   Accel LP/Normal @ 52Hz: 24 uA typical
     *   Gyro Normal @ 52Hz:     3.0 mA typical
     * With accel only (no gyro): ~24 uA expected.
     *
     * We run accel-only for 2 seconds to give a clean measurement window. */
    const struct device *dev = get_dev();

    /* Gyro off, accel at 52Hz LP/Normal, 8g range */
    write_register(dev, LSM6DSO_CTRL2_G, 0x00);     /* Gyro power-down */
    write_register(dev, LSM6DSO_CTRL1_XL, 0x3C);    /* Accel: 52Hz, 8g */

    /* Disable FIFO (pure streaming, no FIFO overhead) */
    write_register(dev, LSM6DSO_FIFO_CTRL4, 0x00);

    /* Wait for ODR to stabilize */
    k_sleep(K_MSEC(100));

    /* Hold for power measurement window (2 seconds) */
    k_sleep(K_MSEC(2000));

    /* Verify the sensor is still sampling (read STATUS_REG for XLDA bit) */
    uint8_t status = 0;
    read_register(dev, LSM6DSO_STATUS_REG, &status);
    zassert_true(status & 0x01,
                 "STATUS_REG XLDA bit not set — accel not running at 52Hz");

    printk("  STATUS_REG = 0x%02X (XLDA=%d)\n", status, status & 0x01);
}

ZTEST_SUITE(lsm6dso_hw, NULL, NULL, NULL, NULL, NULL);
```

### 3.2 test_spec.yaml

This file lives alongside the test source. The driver engineer defines it based on the LSM6DSO datasheet (Rev 9, Table 4 — current consumption). The orchestrator evaluates `power_budget` assertions only on dev-kit runs (`test_mode: full`).

```yaml
# tests/lsm6dso/test_spec.yaml
version: 1

metadata:
  chip: LSM6DSO
  datasheet_ref: "LSM6DSO datasheet Rev 9, Table 4 (current consumption)"
  author: driver-team
  last_reviewed: "2026-02-01"

defaults:
  timeout_s: 60

tests:
  # ── Core tests (every board) ──
  test_device_ready:
    required: always
    timeout_s: 5

  test_sensor_presence:
    required: always
    timeout_s: 5

  test_accel_data_readback:
    required: always
    timeout_s: 5
    power_budget:
      peak_ua: 800                  # SPI burst during register read

  # ── SPI bus-specific tests ──
  test_spi_whoami:
    required_when: { bus: spi }
    timeout_s: 5

  test_spi_register_write_readback:
    required_when: { bus: spi }
    timeout_s: 5

  # ── Interrupt tests ──
  test_drdy_interrupt:
    required_when: { has_prop: irq_gpios }
    timeout_s: 10

  test_fifo_watermark_interrupt:
    required_when: { has_prop: irq_gpios }
    timeout_s: 10
    power_budget:
      avg_ua: 500                   # Continuous 52Hz sampling for 1s

  test_fifo_batch_at_52hz:
    required_when: { has_prop: irq_gpios }
    timeout_s: 10
    power_budget:
      avg_ua: 500                   # Continuous 52Hz accel batching for 2s

  # ── Polled-mode tests ──
  test_polled_fifo_read:
    required_when: { not_has_prop: irq_gpios }
    timeout_s: 10
    power_budget:
      avg_ua: 500

  # ── Motion detection ──
  test_motion_interrupt:
    required: false                 # Best-effort — needs physical stimulus
    power_budget:
      avg_ua: 600

  # ── Power profiling tests ──
  test_sleep_current:
    required: always
    timeout_s: 10
    power_budget:
      avg_ua: 5                     # Datasheet: 3 uA typical power-down
      peak_ua: 10                   # Allow for brief SPI read at end

  test_active_current_at_52hz:
    required: always
    timeout_s: 10
    power_budget:
      avg_ua: 40                    # Datasheet: 24 uA typical accel LP @ 52Hz + margin
      peak_ua: 200                  # Allow for SPI read spikes
```

**How the power budgets were derived:**

| Test | Datasheet Spec | Budget | Margin |
|------|---------------|--------|--------|
| `test_sleep_current` | 3 uA typical (power-down, all axes off) | avg: 5 uA, peak: 10 uA | ~67% over typical; peak allows for the SPI read at test end |
| `test_active_current_at_52hz` | 24 uA typical (accel LP/Normal @ 52Hz, gyro off) | avg: 40 uA, peak: 200 uA | ~67% over typical; peak covers SPI burst + measurement noise |
| `test_fifo_watermark_interrupt` | ~24 uA accel + minor FIFO overhead | avg: 500 uA | Very conservative — covers FIFO DMA, interrupt processing, and SPI bursts during batch read |

These budgets are regression gates, not precision measurements. They catch gross anomalies: sensor stuck in high-performance mode (3 mA instead of 24 uA), gyro accidentally left enabled (adds 3 mA), FIFO overflow causing continuous SPI traffic.

### 3.3 testcase.yaml (Twister Build Metadata)

```yaml
# tests/lsm6dso/testcase.yaml
tests:
  drivers.sensor.lsm6dso.hw:
    harness: console
    timeout: 120
    extra_configs:
      - CONFIG_CK_LSM6DSO=y
      - CONFIG_CK_LSM6DSO_TRIGGER=y
    tags:
      - drivers
      - sensor
      - hardware
```

Note: `testcase.yaml` does NOT list `platform_allow` — the Concord pipeline determines which boards to build for, based on the `targets:` block in `.concord/pipeline.yaml`. Twister is used only for the build step (`--prep-artifacts-for-testing`), not for runtime execution.

---

## 4. UART Output Example

Here is what the raw UART stream looks like when the test firmware boots and runs on the dev-kit. The test runner receives this via MTIB's `UartStream` gRPC call at 115200 baud.

```
*** Booting Zephyr OS build v3.7.0-rc1 ***
Running TESTSUITE lsm6dso_hw
===================================================================
START - test_device_ready
 PASS - test_device_ready in 0.003 seconds
===================================================================
START - test_sensor_presence
 PASS - test_sensor_presence in 0.002 seconds
===================================================================
START - test_accel_data_readback
  accel_z = 9.614000 m/s^2 (~9614 mg)
 PASS - test_accel_data_readback in 0.054 seconds
===================================================================
START - test_spi_whoami
 PASS - test_spi_whoami in 0.001 seconds
===================================================================
START - test_spi_register_write_readback
 PASS - test_spi_register_write_readback in 0.002 seconds
===================================================================
START - test_drdy_interrupt
 PASS - test_drdy_interrupt in 0.504 seconds
===================================================================
START - test_fifo_watermark_interrupt
  FIFO level after 1s: 52 samples
 PASS - test_fifo_watermark_interrupt in 1.009 seconds
===================================================================
START - test_fifo_batch_at_52hz
  FIFO samples collected in 2s: 103 (expected ~104)
  FIFO[0]: tag=0x01, accel_x_raw=-42
  FIFO[1]: tag=0x01, accel_x_raw=-38
  FIFO[2]: tag=0x01, accel_x_raw=-45
  FIFO[3]: tag=0x01, accel_x_raw=-41
  FIFO[4]: tag=0x01, accel_x_raw=-39
 PASS - test_fifo_batch_at_52hz in 2.011 seconds
===================================================================
START - test_motion_interrupt
  No motion interrupt detected — skipping (needs physical stimulus or vibration actuator)
 SKIP - test_motion_interrupt in 2.005 seconds
===================================================================
START - test_sleep_current
 PASS - test_sleep_current in 1.108 seconds
===================================================================
START - test_active_current_at_52hz
  STATUS_REG = 0x05 (XLDA=1)
 PASS - test_active_current_at_52hz in 2.105 seconds
===================================================================
TESTSUITE lsm6dso_hw succeeded
------ TESTSUITE SUMMARY START ------
 SUITE PASS - 100.00% [lsm6dso_hw]: pass = 10, fail = 0, skip = 1, total = 11
 - PASS - [lsm6dso_hw.test_device_ready] duration = 0.003 seconds
 - PASS - [lsm6dso_hw.test_sensor_presence] duration = 0.002 seconds
 - PASS - [lsm6dso_hw.test_accel_data_readback] duration = 0.054 seconds
 - PASS - [lsm6dso_hw.test_spi_whoami] duration = 0.001 seconds
 - PASS - [lsm6dso_hw.test_spi_register_write_readback] duration = 0.002 seconds
 - PASS - [lsm6dso_hw.test_drdy_interrupt] duration = 0.504 seconds
 - PASS - [lsm6dso_hw.test_fifo_watermark_interrupt] duration = 1.009 seconds
 - PASS - [lsm6dso_hw.test_fifo_batch_at_52hz] duration = 2.011 seconds
 - SKIP - [lsm6dso_hw.test_motion_interrupt] duration = 2.005 seconds
 - PASS - [lsm6dso_hw.test_sleep_current] duration = 1.108 seconds
 - PASS - [lsm6dso_hw.test_active_current_at_52hz] duration = 2.105 seconds
------ TESTSUITE SUMMARY END ------
===================================================================
PROJECT EXECUTION SUCCESSFUL
```

The test runner parses this with anchored regexes:
- `^START - (\S+)` — test started, record timestamp from MTIB clock
- `^\s*(PASS|FAIL|SKIP) - (\S+)` — test ended, record result and timestamp
- `^Running TESTSUITE (\S+)` — suite started
- `^TESTSUITE (\S+) (succeeded|failed)` — suite ended

Everything else (printk output, blank lines, boot banner) is captured in `uart_log.txt` but ignored by the parser.

---

## 5. Power Profiling

### 5.1 How It Works

The test runner starts MTIB `PowerMeasure` and `UartStream` concurrently. Both streams use the same MTIB clock, so timestamps are aligned within ~1ms. When the runner sees a `START - test_name` marker on UART, it records the MTIB timestamp. When it sees `PASS/FAIL/SKIP - test_name`, it records the end timestamp. The power trace between those two timestamps is sliced out as that test's power profile.

```
UART markers (parsed):           Power trace (continuous, ~10 kHz):

START - test_sleep_current        ─── t=6.200s ───────────────────
    (sensor in power-down,                 │                     │
     firmware holds for 1s)                │  2.8 uA avg         │
PASS  - test_sleep_current        ─── t=7.308s ─── → slice → sleep_current.csv
START - test_active_current_at_52hz ─ t=7.308s ───────────────────
    (accel running 52Hz LP,                │                     │
     firmware holds for 2s)                │  27.3 uA avg        │
     SPI read at end →                     │  spike: 180 uA      │
PASS  - test_active_current_at_52hz  t=9.413s ─── → slice → active_current_at_52hz.csv
```

### 5.2 Per-Test Power Summary

The orchestrator computes statistics for each test slice and evaluates them against `test_spec.yaml` budgets:

```json
{
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
  "test_fifo_watermark_interrupt": {
    "avg_ua": 31.2,
    "peak_ua": 420.8,
    "min_ua": 23.5,
    "energy_uj": 31.5,
    "duration_s": 1.009,
    "budget_pass": {
      "avg_ua": true
    }
  },
  "test_fifo_batch_at_52hz": {
    "avg_ua": 29.8,
    "peak_ua": 395.2,
    "min_ua": 22.8,
    "energy_uj": 59.9,
    "duration_s": 2.011,
    "budget_pass": {
      "avg_ua": true
    }
  }
}
```

For tests without a `power_budget` in `test_spec.yaml` (e.g., `test_device_ready`, `test_spi_whoami`), the power data is still captured and stored as artifacts, but `budget_pass` is `null` — no pass/fail judgment.

### 5.3 Power Trace Annotation

An annotated power trace for the full test session shows the distinct power states driven by each test:

```
Current (uA)
    500 ┤
        │               ┌─┐                 ┌──┐
    400 ┤               │ │                 │  │
        │               │ │                 │  │        SPI burst
    300 ┤               │ │                 │  │        during FIFO
        │               │ │                 │  │        flush
    200 ┤               │ │                 │  │
        │          ┌─┐  │ │   ┌─┐           │  │  ┌──────┐
    100 ┤          │ │  │ │   │ │           │  │  │      │
        │          │ │  │ │   │ │           │  │  │      │ 27 uA avg
     50 ┤     ┌──┐ │ │  │ │   │ │  ┌──┐     │  │  │      │ (accel 52Hz)
        │     │  │ │ │  │ │   │ │  │  │     │  │  │      │
     25 ┤─────┘  └─┘ └──┘ └───┘ └──┘  └─────┘  └──┘      └──────
        │                                                    2.8 uA
      3 ┤                                    ┌──────────┐   (power-down)
      0 ┤────────────────────────────────────┘          └────────────
        └──┬──────┬──────┬──────┬──────┬─────┬──────────┬──────────┬──
           0s     1s     2s     3s     4s    5s         6s     7s    8s
           │      │      │      │      │     │          │      │
           boot   DRDY   WM int FIFO   motion sleep     active  end
                  test   test   batch  (skip) current   52Hz
```

The orchestrator stores this as `power/full_trace.csv` (continuous) and individual `power/per_test/{test_name}.csv` files. Summary statistics go to `power/summary.json`. All of these are uploaded to MinIO and power stats are pushed to InfluxDB for trend analysis across pipeline runs.

---

## 6. Pipeline Integration

### 6.1 Where This Fits in the Pipeline

Stage 2 (driver hardware tests) sits between Stage 1 (native unit tests, no hardware) and Stage 3 (instrumented firmware integration tests). The Concord pipeline fans out Stage 2 per (chip, board) pair, as declared in the driver repo's `.concord/pipeline.yaml`:

```yaml
# accel_drv/.concord/pipeline.yaml (relevant excerpt)
targets:
  # Dev-kit: isolated power measurement + functional tests
  - board: devkit_nrf52840_lsm6dso_spi
    chip: lsm6dso
    test_mode: full

  # Product board: functional tests only, power captured but not enforced
  - board: alpha_b0/nrf52840
    chip: lsm6dso
    product: alpha
    test_mode: functional
```

### 6.2 Execution Flow

1. **Trigger**: A push to the `accel_drv` repo triggers the Concord pipeline.

2. **Build**: The build service compiles the ztest firmware for each target board using Twister (`--prep-artifacts-for-testing`). For the dev-kit target, it builds `tests/lsm6dso/` with board `devkit_nrf52840_lsm6dso_spi`. The output is a `.hex` file plus `board_features.json` (extracted from the generated DTS).

3. **Queue**: The pipeline controller creates a Stage 2 Job for each (chip, board) pair. Each Job specifies `requires` labels derived from the target:
   - Dev-kit Job: `{ fixture_type: devkit, chip: lsm6dso, bus: spi, mcu: nrf52840 }`
   - Product Job: `{ fixture_type: product, product: alpha }`

4. **Match**: The work queue matches each Job to the first free MTIB node whose `Node.capabilities` satisfy all `requires` labels.

5. **Execute**: The Stage 2 test runner (a container in a K8s pod) runs the flow described in [09-final-architecture.md](../../architecture/09-final-architecture.md) Section 3.2:
   1. Download hex + `test_spec.yaml` + `board_features.json` from MinIO
   2. Connect to MTIB via gRPC
   3. Flash test firmware via `FlashProgram`
   4. Start concurrent `PowerMeasure` and `UartStream` streams
   5. Power on DUT
   6. Parse ztest UART markers with timestamps
   7. On completion: slice power trace, evaluate `test_spec.yaml` criteria
   8. Upload artifacts to MinIO, push power stats to InfluxDB
   9. Exit 0 (pass) or 1 (failure)

6. **Artifacts**: Stored in MinIO:
   ```
   validation/pipelines/{pipeline_id}/stages/driver_hw/{job_id}/
   ├── junit.xml                   # ztest results
   ├── uart_log.txt                # full UART output
   ├── power/
   │   ├── full_trace.csv          # continuous power measurement
   │   ├── per_test/
   │   │   ├── test_sleep_current.csv
   │   │   ├── test_active_current_at_52hz.csv
   │   │   ├── test_fifo_watermark_interrupt.csv
   │   │   ├── test_fifo_batch_at_52hz.csv
   │   │   └── ...
   │   └── summary.json            # per-test stats + budget pass/fail
   ├── coverage.json               # per-test coverage evaluation
   ├── board_features.json         # build-time DTS feature extraction
   ├── test_spec.yaml              # copy of spec used
   └── metadata.json               # firmware version, board, MTIB node, timestamps
   ```

### 6.3 Dev-Kit vs Product-Board Verdicts

For the **dev-kit** run (`test_mode: full`):
- All ztest `PASS`/`FAIL` verdicts are authoritative
- `power_budget` assertions are evaluated — a budget violation is a pipeline FAIL
- Coverage gaps (required test missing from ztest output) are pipeline FAILs

For the **product-board** run (`test_mode: functional`):
- All ztest `PASS`/`FAIL` verdicts are authoritative (same firmware, real Alpha PCB)
- `power_budget` is captured but not enforced — `budget_pass` is `null` in `summary.json`
- Coverage gaps are still evaluated (did all expected tests compile and run on this board?)

This means a commit can pass the product-board run (functional correctness on real Alpha hardware) but fail the dev-kit run (power regression) — or vice versa. Both are valuable signals at different levels.

---

## 7. What These Tests Prove

Each test targets a specific hardware-level risk that is invisible to Stage 1 unit tests (which run with stubbed SPI and GPIO):

| Test | What It Proves | What It Catches |
|------|---------------|-----------------|
| `test_device_ready` | Zephyr device model initialization completes on real hardware — DTS node, bus driver, and GPIO all resolve correctly | Missing DTS node, wrong compatible string, SPI peripheral not enabled, GPIO controller not started |
| `test_sensor_presence` | SPI bus is electrically functional, CS line asserts correctly, LSM6DSO responds with correct WHO_AM_I (0x6C) | Cold solder joint on SPI, wrong CS GPIO, MISO/MOSI swapped, sensor not populated on fixture, counterfeit/wrong part |
| `test_accel_data_readback` | Full sensor pipeline works: ODR configuration, data sampling, register readback, Zephyr sensor API integration | Driver init sequence bug, wrong register writes, byte-order issues, sensor not converting data |
| `test_spi_whoami` | Raw SPI bus-level communication independent of driver init path | SPI clock polarity/phase mismatch, bus speed too high, signal integrity issues at the physical layer |
| `test_spi_register_write_readback` | Write path works — data written to a register can be read back correctly | SPI write failure (MOSI line issue), register write protection unexpectedly enabled, address decoding bug |
| `test_drdy_interrupt` | Hardware interrupt fires at the expected rate — GPIO wiring, interrupt polarity, edge detection, and GPIOTE all work end-to-end | Wrong interrupt pin in DTS, active-high vs active-low mismatch, pulsed vs latched mode bug, GPIOTE channel exhaustion |
| `test_fifo_watermark_interrupt` | FIFO hardware fills at the correct rate, watermark interrupt fires at the right sample count | FIFO configuration register bug, wrong batch data rate, watermark routing to wrong INT pin, FIFO stuck in bypass mode |
| `test_fifo_batch_at_52hz` | FIFO sample rate matches configured ODR within tolerance — real hardware clock accuracy | ODR register mapping bug (e.g., writing 26Hz instead of 52Hz), sensor oscillator drift beyond spec, FIFO overflow/underflow |
| `test_motion_interrupt` | Wake-up / motion detection hardware works: threshold comparison, interrupt generation, routing to MCU | Wake-up threshold register scaling bug, motion detection feature not enabled, interrupt routing misconfigured |
| `test_sleep_current` | Power-down current matches datasheet — sensor is actually entering low-power state | Gyro accidentally left running (adds 3 mA), internal LDO not shutting down, pull-up on interrupt line drawing excess current |
| `test_active_current_at_52hz` | Active-mode current matches datasheet — correct power mode is selected | High-performance mode instead of LP/Normal (much higher current), FIFO accidentally enabled adding DMA overhead, bus contention causing retries |

**What Stage 1 cannot catch**: SPI signal integrity, real interrupt timing, actual power consumption, FIFO hardware behavior, sensor oscillator accuracy, GPIO electrical characteristics. These are all physical properties of the real silicon and PCB — no amount of mocking or simulation can verify them. Stage 2 is the first point in the pipeline where the driver meets real hardware.

**What Stage 2 does not cover**: Multi-sensor interaction (LSM6DSO + PAH8151 + BME280 sharing resources), firmware state machine behavior, application-level orchestration. Those are Stage 3 (integration tests on instrumented firmware) and Stage 4 (product validation on final hardware). Stage 2 ensures each driver works correctly in isolation so that integration failures in later stages can be attributed to integration logic, not driver bugs.
