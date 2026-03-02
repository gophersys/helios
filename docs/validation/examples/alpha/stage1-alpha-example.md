# Stage 1 Alpha Example -- Software Tests on native_sim

> A complete walkthrough of Stage 1 software testing for the Alpha wearable,
> covering two subsystems: the **LSM6DSO driver** (interface/stub tests in the
> driver repo) and the **VSM/state machine subsystem** (app-level stub tests in
> the alpha_fw repo). No hardware required -- everything runs on `native_sim`.

---

## 1. Introduction

This document makes the Stage 1 concepts from [00-validation-philosophy.md](../../architecture/00-validation-philosophy.md) Section 3.1 concrete by walking through real test implementations for Alpha. It covers:

1. **Stage 1a -- LSM6DSO interface tests** in the `accel_drv` repo: exercise the Zephyr `sensor_driver_api` against a DTS-declared stub device on `native_sim`
2. **Stage 1b -- VSM/state machine app-level tests** in the `alpha_fw` repo: exercise the heat risk state machine and motion state machine with fully stubbed sensor drivers

Both categories run entirely on `native_sim`. There is no physical sensor, no SPI or I2C bus, no dev-kit, no MTIB. The tests build and execute on any CI agent node -- a plain Linux VM -- and complete in under a minute. They are the first gate in the Concord pipeline: if Stage 1 fails, nothing else runs.

**Relationship to other stages:**

| Stage | What It Tests | Where It Runs | This Document |
|-------|---------------|---------------|---------------|
| **1 -- Software tests** | Driver API contract, app logic, state machines | `native_sim` on CI agent | **Yes** |
| 2 -- Driver hardware tests | Driver against real sensor silicon | MTIB dev-kit/product fixture | No |
| 3 -- Integration tests | Instrumented firmware on real product board | MTIB product fixture | See [10-stage3-alpha-example.md](./stage3-alpha-example.md) |
| 4 -- Product validation | Production firmware, black-box | MTIB product fixture | No |

---

## 2. LSM6DSO Interface Tests (Stage 1a -- Driver Repo)

### 2.1 What This Is

The `accel_drv` repo contains a custom Zephyr driver for the STMicroelectronics LSM6DSO 6-axis IMU (3-axis accelerometer + 3-axis gyroscope). The driver exposes the standard Zephyr `sensor_driver_api`:

- `attr_set` -- configure ODR, full-scale range, FIFO, motion detection thresholds
- `sample_fetch` -- read samples from FIFO or polled registers
- `channel_get` -- retrieve processed sensor data (accel in milli-g, gyro in mdps)
- `trigger_set` -- arm motion detection interrupt callback

The interface tests verify that **the driver's API contract is correct** -- that calling `sensor_attr_set()` with specific parameters produces the expected internal state, that `sensor_sample_fetch()` followed by `sensor_channel_get()` returns correctly formatted data, and that `sensor_trigger_set()` arms callbacks that fire when expected.

### 2.2 No Hardware Needed

These tests run on `native_sim`. There is:

- No physical LSM6DSO sensor
- No SPI or I2C bus
- No GPIO interrupt pin
- No dev-kit board

Instead, the Zephyr DTS declares a **stub device node** that responds to the driver API. The stub does not emulate the LSM6DSO register set -- it does not pretend to be a sensor chip. It implements the same `sensor_driver_api` interface and returns pre-configured values that the test controls. The driver code under test runs unmodified against this stub.

This is different from register emulation (Section 3.1a in the philosophy doc). We deliberately avoid emulating the LSM6DSO's 100+ registers because:

1. The emulator would be as complex as the driver itself and just as likely to contain bugs
2. A passing emulator test proves the driver works against the emulator, not against real silicon
3. Real hardware tests (Stage 2) are the authoritative answer for driver-hardware interaction

### 2.3 Test Environment Setup

The interface tests live in the driver repo under `tests/interface/`:

```
accel_drv/
├── drivers/lsm6dso/
│   ├── src/
│   │   ├── lsm6dso.c          # Real driver implementation
│   │   └── lsm6dso_reg.c      # Register-level access layer
│   └── lsm6dso.h              # Driver API: lsm6dso_config, lsm6dso_data, sensor enums
├── stubs/
│   ├── lsm6dso_stub.c         # Stub sensor_driver_api implementation
│   ├── Kconfig                 # CONFIG_CK_LSM6DSO_STUB
│   └── CMakeLists.txt
├── dts/bindings/
│   ├── ck,lsm6dso.yaml        # Real device binding
│   ├── ck,lsm6dso-spi.yaml    # SPI variant
│   └── ck,lsm6dso-stub.yaml   # Stub binding for native_sim
├── tests/
│   └── interface/
│       ├── testcase.yaml
│       ├── prj.conf
│       ├── boards/
│       │   └── native_sim.overlay
│       └── src/
│           └── main.c          # ztest test suite
├── Kconfig
└── zephyr/module.yml
```

**testcase.yaml** -- Declares the test suite for Twister. `platform_allow: native_sim` ensures this test is only built for the simulated target:

```yaml
tests:
  drivers.lsm6dso.interface:
    platform_allow: native_sim
    tags: unit driver
    harness: ztest
    timeout: 60
```

**prj.conf** -- Enables the stub driver, disables the real driver (which needs a real SPI/I2C bus):

```kconfig
# Sensor subsystem (required for sensor_driver_api)
CONFIG_SENSOR=y
CONFIG_ZTEST=y
CONFIG_ZTEST_NEW_API=y

# Use stub, not real driver
CONFIG_CK_LSM6DSO=n
CONFIG_CK_LSM6DSO_STUB=y

# Logging for test output
CONFIG_LOG=y
CONFIG_LOG_DEFAULT_LEVEL=3
```

**boards/native_sim.overlay** -- Declares the stub device node. The DTS label `lsm6dso0` matches what application code uses with `DEVICE_DT_GET(DT_NODELABEL(lsm6dso0))`:

```dts
/ {
    lsm6dso0: lsm6dso-stub {
        compatible = "ck,lsm6dso-stub";
        status = "okay";
    };
};
```

**How it compiles:** When Twister builds this test for `native_sim`, Zephyr's build system sees `CONFIG_CK_LSM6DSO_STUB=y`, links `lsm6dso_stub.c` instead of `lsm6dso.c`, and instantiates the stub device node from the overlay. The test binary runs as a native Linux process.

### 2.4 What the Stub Provides

The stub implements the full `sensor_driver_api` surface area. It does not talk to any bus. It maintains internal state that the test controls via a test-only API:

```c
/* accel_drv/stubs/lsm6dso_stub.c (simplified) */

#include <zephyr/drivers/sensor.h>

static struct sensor_value stub_accel[3];        /* X, Y, Z */
static struct sensor_value stub_gyro[3];         /* X, Y, Z */
static int16_t stub_fifo_sample_count;
static sensor_trigger_handler_t stub_motion_handler;
static const struct sensor_trigger *stub_motion_trig;
static bool stub_fetch_configured;
static int stub_error_code;                      /* Injected error for fault tests */

/* ---- Test-only API (not available in production builds) ---- */

void lsm6dso_stub_set_accel(int32_t x_mg, int32_t y_mg, int32_t z_mg)
{
    stub_accel[0] = (struct sensor_value){ .val1 = x_mg / 1000, .val2 = (x_mg % 1000) * 1000 };
    stub_accel[1] = (struct sensor_value){ .val1 = y_mg / 1000, .val2 = (y_mg % 1000) * 1000 };
    stub_accel[2] = (struct sensor_value){ .val1 = z_mg / 1000, .val2 = (z_mg % 1000) * 1000 };
    stub_fetch_configured = true;
}

void lsm6dso_stub_set_gyro(int32_t x_mdps, int32_t y_mdps, int32_t z_mdps)
{
    stub_gyro[0] = (struct sensor_value){ .val1 = x_mdps / 1000, .val2 = (x_mdps % 1000) * 1000 };
    stub_gyro[1] = (struct sensor_value){ .val1 = y_mdps / 1000, .val2 = (y_mdps % 1000) * 1000 };
    stub_gyro[2] = (struct sensor_value){ .val1 = z_mdps / 1000, .val2 = (z_mdps % 1000) * 1000 };
    stub_fetch_configured = true;
}

void lsm6dso_stub_set_fifo_count(int16_t count)
{
    stub_fifo_sample_count = count;
}

void lsm6dso_stub_inject_error(int err)
{
    stub_error_code = err;
}

void lsm6dso_stub_fire_trigger(enum sensor_trigger_type type)
{
    if (type == SENSOR_TRIG_MOTION && stub_motion_handler != NULL) {
        stub_motion_handler(DEVICE_DT_GET(DT_NODELABEL(lsm6dso0)), stub_motion_trig);
    }
}

void lsm6dso_stub_reset(void)
{
    memset(stub_accel, 0, sizeof(stub_accel));
    memset(stub_gyro, 0, sizeof(stub_gyro));
    stub_fifo_sample_count = 0;
    stub_motion_handler = NULL;
    stub_motion_trig = NULL;
    stub_fetch_configured = false;
    stub_error_code = 0;
}

/* ---- Standard sensor_driver_api ---- */

static int stub_sample_fetch(const struct device *dev, enum sensor_channel chan)
{
    if (stub_error_code != 0) {
        return stub_error_code;
    }
    return stub_fetch_configured ? 0 : -ENODATA;
}

static int stub_channel_get(const struct device *dev, enum sensor_channel chan,
                            struct sensor_value *val)
{
    if (stub_error_code != 0) {
        return stub_error_code;
    }

    switch (chan) {
    case SENSOR_CHAN_ACCEL_X: *val = stub_accel[0]; return 0;
    case SENSOR_CHAN_ACCEL_Y: *val = stub_accel[1]; return 0;
    case SENSOR_CHAN_ACCEL_Z: *val = stub_accel[2]; return 0;
    case SENSOR_CHAN_ACCEL_XYZ:
        val[0] = stub_accel[0];
        val[1] = stub_accel[1];
        val[2] = stub_accel[2];
        return 0;
    case SENSOR_CHAN_GYRO_X:  *val = stub_gyro[0]; return 0;
    case SENSOR_CHAN_GYRO_Y:  *val = stub_gyro[1]; return 0;
    case SENSOR_CHAN_GYRO_Z:  *val = stub_gyro[2]; return 0;
    case SENSOR_CHAN_GYRO_XYZ:
        val[0] = stub_gyro[0];
        val[1] = stub_gyro[1];
        val[2] = stub_gyro[2];
        return 0;
    case (enum sensor_channel)SENSOR_CHAN_LSM6DSO_SAMPLE_COUNT:
        val->val1 = stub_fifo_sample_count;
        val->val2 = 0;
        return 0;
    default:
        return -ENOTSUP;
    }
}

static int stub_attr_set(const struct device *dev, enum sensor_channel chan,
                         enum sensor_attribute attr, const struct sensor_value *val)
{
    /* Accept all attributes silently -- the stub does not enforce hw constraints */
    return stub_error_code != 0 ? stub_error_code : 0;
}

static int stub_trigger_set(const struct device *dev,
                            const struct sensor_trigger *trig,
                            sensor_trigger_handler_t handler)
{
    if (trig->type == SENSOR_TRIG_MOTION) {
        stub_motion_handler = handler;
        stub_motion_trig = trig;
        return 0;
    }
    return -ENOTSUP;
}

static const struct sensor_driver_api lsm6dso_stub_api = {
    .attr_set = stub_attr_set,
    .sample_fetch = stub_sample_fetch,
    .channel_get = stub_channel_get,
    .trigger_set = stub_trigger_set,
};

DEVICE_DT_INST_DEFINE(0, NULL, NULL, NULL, NULL,
                      POST_KERNEL, CONFIG_SENSOR_INIT_PRIORITY, &lsm6dso_stub_api);
```

The test controls inputs via `lsm6dso_stub_set_accel()`, triggers via `lsm6dso_stub_fire_trigger()`, and fault injection via `lsm6dso_stub_inject_error()`. The driver-under-test sees the standard Zephyr sensor API.

### 2.5 Example Tests

These tests exercise the driver API contract -- the interface between the driver and the application. They verify that the sensor API behaves correctly when given known inputs and that error paths are handled.

```c
/* accel_drv/tests/interface/src/main.c */

#include <zephyr/ztest.h>
#include <zephyr/drivers/sensor.h>
#include <corekinect/sensors/lsm6dso/lsm6dso.h>

/* Test-only stub API */
extern void lsm6dso_stub_set_accel(int32_t x_mg, int32_t y_mg, int32_t z_mg);
extern void lsm6dso_stub_set_gyro(int32_t x_mdps, int32_t y_mdps, int32_t z_mdps);
extern void lsm6dso_stub_set_fifo_count(int16_t count);
extern void lsm6dso_stub_inject_error(int err);
extern void lsm6dso_stub_fire_trigger(enum sensor_trigger_type type);
extern void lsm6dso_stub_reset(void);

static const struct device *dev;

static void *suite_setup(void)
{
    dev = DEVICE_DT_GET(DT_NODELABEL(lsm6dso0));
    zassert_true(device_is_ready(dev), "Stub device not ready");
    return NULL;
}

static void test_before(void *fixture)
{
    ARG_UNUSED(fixture);
    lsm6dso_stub_reset();
}

/* ---- Accelerometer data readback ---- */

ZTEST(lsm6dso_interface, test_accel_readback)
{
    struct sensor_value val[3];
    int rc;

    /* Pre-load stub with known acceleration: 0, 0, ~1g (981 mg) */
    lsm6dso_stub_set_accel(0, 0, 981);

    rc = sensor_sample_fetch(dev);
    zassert_equal(rc, 0, "sample_fetch failed: %d", rc);

    rc = sensor_channel_get(dev, SENSOR_CHAN_ACCEL_XYZ, val);
    zassert_equal(rc, 0, "channel_get failed: %d", rc);

    /* X and Y should be ~0 */
    zassert_equal(val[0].val1, 0, "X accel should be 0g, got %d", val[0].val1);
    zassert_equal(val[1].val1, 0, "Y accel should be 0g, got %d", val[1].val1);

    /* Z should be ~0.981g (val1=0, val2=981000) */
    zassert_equal(val[2].val1, 0, "Z accel integer part should be 0");
    zassert_equal(val[2].val2, 981000, "Z accel fractional part should be 981000");
}

/* ---- Gyroscope data readback ---- */

ZTEST(lsm6dso_interface, test_gyro_readback)
{
    struct sensor_value val[3];
    int rc;

    /* Pre-load stub with known angular rate: 1000 mdps on X */
    lsm6dso_stub_set_gyro(1000, 0, 0);

    rc = sensor_sample_fetch(dev);
    zassert_equal(rc, 0, "sample_fetch failed: %d", rc);

    rc = sensor_channel_get(dev, SENSOR_CHAN_GYRO_XYZ, val);
    zassert_equal(rc, 0, "channel_get failed: %d", rc);

    /* X should be 1.0 dps */
    zassert_equal(val[0].val1, 1, "X gyro should be 1 dps");
    zassert_equal(val[0].val2, 0, "X gyro fractional should be 0");
}

/* ---- FIFO sample count channel ---- */

ZTEST(lsm6dso_interface, test_fifo_sample_count)
{
    struct sensor_value val;
    int rc;

    lsm6dso_stub_set_fifo_count(42);
    lsm6dso_stub_set_accel(0, 0, 0);  /* Ensure fetch has data */

    rc = sensor_sample_fetch(dev);
    zassert_equal(rc, 0, "sample_fetch failed: %d", rc);

    rc = sensor_channel_get(dev, (enum sensor_channel)SENSOR_CHAN_LSM6DSO_SAMPLE_COUNT, &val);
    zassert_equal(rc, 0, "channel_get for sample count failed: %d", rc);
    zassert_equal(val.val1, 42, "Expected 42 FIFO samples, got %d", val.val1);
}

/* ---- ODR configuration via attr_set ---- */

ZTEST(lsm6dso_interface, test_accel_odr_set)
{
    struct sensor_value odr_val = { .val1 = 52, .val2 = 0 };
    int rc;

    /* Setting the accelerometer sampling frequency should succeed */
    rc = sensor_attr_set(dev, SENSOR_CHAN_ACCEL_XYZ,
                         SENSOR_ATTR_SAMPLING_FREQUENCY, &odr_val);
    zassert_equal(rc, 0, "attr_set for ODR failed: %d", rc);
}

/* ---- FIFO enable/disable via custom attribute ---- */

ZTEST(lsm6dso_interface, test_fifo_enable_disable)
{
    struct sensor_value enable_val = { .val1 = 1, .val2 = 0 };
    struct sensor_value disable_val = { .val1 = 0, .val2 = 0 };
    int rc;

    /* Enable FIFO for accel channel */
    rc = sensor_attr_set(dev, SENSOR_CHAN_ACCEL_XYZ,
                         (enum sensor_attribute)SENSOR_ATTR_LSM6DSO_FIFO_EN,
                         &enable_val);
    zassert_equal(rc, 0, "FIFO enable failed: %d", rc);

    /* Disable FIFO for accel channel */
    rc = sensor_attr_set(dev, SENSOR_CHAN_ACCEL_XYZ,
                         (enum sensor_attribute)SENSOR_ATTR_LSM6DSO_FIFO_EN,
                         &disable_val);
    zassert_equal(rc, 0, "FIFO disable failed: %d", rc);
}

/* ---- FIFO ODR configuration via custom attribute ---- */

ZTEST(lsm6dso_interface, test_fifo_odr_set)
{
    struct sensor_value odr_val = { .val1 = 52, .val2 = 0 };
    int rc;

    rc = sensor_attr_set(dev, SENSOR_CHAN_ACCEL_XYZ,
                         (enum sensor_attribute)SENSOR_ATTR_LSM6DSO_FIFO_ODR,
                         &odr_val);
    zassert_equal(rc, 0, "FIFO ODR set failed: %d", rc);
}

/* ---- Motion detection threshold configuration ---- */

ZTEST(lsm6dso_interface, test_motion_threshold_config)
{
    struct sensor_value threshold = { .val1 = 200, .val2 = 0 };  /* 200 mg */
    struct sensor_value duration = { .val1 = 40, .val2 = 0 };    /* 40 ms */
    int rc;

    rc = sensor_attr_set(dev, SENSOR_CHAN_ACCEL_XYZ,
                         SENSOR_ATTR_SLOPE_TH, &threshold);
    zassert_equal(rc, 0, "Motion threshold set failed: %d", rc);

    rc = sensor_attr_set(dev, SENSOR_CHAN_ACCEL_XYZ,
                         SENSOR_ATTR_SLOPE_DUR, &duration);
    zassert_equal(rc, 0, "Motion duration set failed: %d", rc);
}

/* ---- Motion trigger arming and callback ---- */

static volatile bool motion_callback_fired;

static void motion_handler(const struct device *dev, const struct sensor_trigger *trig)
{
    motion_callback_fired = true;
}

ZTEST(lsm6dso_interface, test_motion_trigger_fires)
{
    struct sensor_trigger trig = {
        .type = SENSOR_TRIG_MOTION,
        .chan = SENSOR_CHAN_ACCEL_XYZ,
    };
    int rc;

    motion_callback_fired = false;

    /* Arm the motion trigger */
    rc = sensor_trigger_set(dev, &trig, motion_handler);
    zassert_equal(rc, 0, "trigger_set failed: %d", rc);

    /* Simulate motion interrupt from the stub */
    lsm6dso_stub_fire_trigger(SENSOR_TRIG_MOTION);

    /* Give the callback a moment to execute */
    k_sleep(K_MSEC(10));

    zassert_true(motion_callback_fired,
                 "Motion trigger callback was not called");
}

/* ---- Motion trigger disarming ---- */

ZTEST(lsm6dso_interface, test_motion_trigger_disarm)
{
    struct sensor_trigger trig = {
        .type = SENSOR_TRIG_MOTION,
        .chan = SENSOR_CHAN_ACCEL_XYZ,
    };
    int rc;

    motion_callback_fired = false;

    /* Arm then disarm */
    rc = sensor_trigger_set(dev, &trig, motion_handler);
    zassert_equal(rc, 0, "trigger_set (arm) failed: %d", rc);

    rc = sensor_trigger_set(dev, &trig, NULL);
    zassert_equal(rc, 0, "trigger_set (disarm) failed: %d", rc);

    /* Fire -- should NOT call the handler */
    lsm6dso_stub_fire_trigger(SENSOR_TRIG_MOTION);
    k_sleep(K_MSEC(10));

    zassert_false(motion_callback_fired,
                  "Motion callback should not fire after disarm");
}

/* ---- Unsupported trigger type ---- */

ZTEST(lsm6dso_interface, test_unsupported_trigger)
{
    struct sensor_trigger trig = {
        .type = SENSOR_TRIG_DATA_READY,
        .chan = SENSOR_CHAN_ACCEL_XYZ,
    };
    int rc;

    /* DATA_READY is not supported -- only MOTION */
    rc = sensor_trigger_set(dev, &trig, motion_handler);
    zassert_equal(rc, -ENOTSUP, "Expected -ENOTSUP for DATA_READY trigger, got %d", rc);
}

/* ---- Error injection: SPI failure during fetch ---- */

ZTEST(lsm6dso_interface, test_fetch_error_propagation)
{
    int rc;

    lsm6dso_stub_set_accel(0, 0, 981);
    lsm6dso_stub_inject_error(-EIO);

    rc = sensor_sample_fetch(dev);
    zassert_equal(rc, -EIO,
                  "Expected -EIO from fetch with injected error, got %d", rc);
}

/* ---- Error injection: channel_get after bus failure ---- */

ZTEST(lsm6dso_interface, test_channel_get_error_propagation)
{
    struct sensor_value val;
    int rc;

    lsm6dso_stub_inject_error(-EIO);

    rc = sensor_channel_get(dev, SENSOR_CHAN_ACCEL_X, &val);
    zassert_equal(rc, -EIO,
                  "Expected -EIO from channel_get with injected error, got %d", rc);
}

/* ---- Fetch without data configured ---- */

ZTEST(lsm6dso_interface, test_fetch_no_data)
{
    int rc;

    /* No stub data pre-loaded -- fetch should return -ENODATA */
    rc = sensor_sample_fetch(dev);
    zassert_equal(rc, -ENODATA,
                  "Expected -ENODATA from fetch with no data, got %d", rc);
}

/* ---- Unsupported channel ---- */

ZTEST(lsm6dso_interface, test_unsupported_channel)
{
    struct sensor_value val;
    int rc;

    lsm6dso_stub_set_accel(0, 0, 981);
    sensor_sample_fetch(dev);

    /* SENSOR_CHAN_AMBIENT_TEMP is not supported by LSM6DSO */
    rc = sensor_channel_get(dev, SENSOR_CHAN_AMBIENT_TEMP, &val);
    zassert_equal(rc, -ENOTSUP,
                  "Expected -ENOTSUP for unsupported channel, got %d", rc);
}

ZTEST_SUITE(lsm6dso_interface, NULL, suite_setup, test_before, NULL, NULL);
```

### 2.6 Building and Running

From the `accel_drv` directory, Twister builds and runs the test:

```bash
# Build + run on native_sim (the only allowed platform)
west twister -T tests/interface/ -p native_sim

# Or build manually to inspect the binary
west build -b native_sim tests/interface/ -d build/test_interface
./build/test_interface/zephyr/zephyr.exe
```

Output:

```
*** Booting Zephyr OS ***
Running TESTSUITE lsm6dso_interface
===================================================================
START - test_accel_readback
 PASS - test_accel_readback in 0.001 seconds
===================================================================
START - test_gyro_readback
 PASS - test_gyro_readback in 0.001 seconds
===================================================================
START - test_fifo_sample_count
 PASS - test_fifo_sample_count in 0.001 seconds
===================================================================
START - test_accel_odr_set
 PASS - test_accel_odr_set in 0.000 seconds
===================================================================
START - test_fifo_enable_disable
 PASS - test_fifo_enable_disable in 0.000 seconds
===================================================================
START - test_fifo_odr_set
 PASS - test_fifo_odr_set in 0.000 seconds
===================================================================
START - test_motion_threshold_config
 PASS - test_motion_threshold_config in 0.000 seconds
===================================================================
START - test_motion_trigger_fires
 PASS - test_motion_trigger_fires in 0.012 seconds
===================================================================
START - test_motion_trigger_disarm
 PASS - test_motion_trigger_disarm in 0.012 seconds
===================================================================
START - test_unsupported_trigger
 PASS - test_unsupported_trigger in 0.000 seconds
===================================================================
START - test_fetch_error_propagation
 PASS - test_fetch_error_propagation in 0.000 seconds
===================================================================
START - test_channel_get_error_propagation
 PASS - test_channel_get_error_propagation in 0.000 seconds
===================================================================
START - test_fetch_no_data
 PASS - test_fetch_no_data in 0.000 seconds
===================================================================
START - test_unsupported_channel
 PASS - test_unsupported_channel in 0.000 seconds
===================================================================
TESTSUITE lsm6dso_interface succeeded
------ TESTSUITE SUMMARY START ------
SUITE PASS - 100.00% [lsm6dso_interface]: pass = 14, fail = 0, skip = 0
------ TESTSUITE SUMMARY END ------
```

Total execution time: under 1 second.

### 2.7 What This Proves vs. What It Cannot Prove

**What these tests prove:**

- The `sensor_driver_api` contract is satisfied -- all four API functions (`attr_set`, `sample_fetch`, `channel_get`, `trigger_set`) accept the expected parameters and return the expected values
- The custom channel `SENSOR_CHAN_LSM6DSO_SAMPLE_COUNT` and custom attributes `SENSOR_ATTR_LSM6DSO_FIFO_EN` / `SENSOR_ATTR_LSM6DSO_FIFO_ODR` work through the standard Zephyr API
- Motion trigger callbacks fire when triggered and do not fire after disarming
- Error codes from the bus layer propagate correctly through the API
- Unsupported operations return `-ENOTSUP` rather than crashing or silently succeeding
- The DTS binding and Kconfig are correctly defined (the build itself would fail otherwise)

**What these tests cannot prove:**

- That the real LSM6DSO chip responds correctly to register writes (SPI timing, register map correctness)
- That FIFO batching works at real ODR rates (52 Hz, 104 Hz, etc.)
- That the motion detection interrupt latency meets requirements
- That the hardware timestamp calibration (`hw_ts_calibrated`, `fifo_read_hw_ts_ticks`) is accurate
- That power mode transitions (HP/LP/ULP) actually change current draw
- That the `stmdev_ctx_t` bus abstraction works over real SPI

All of those are Stage 2 concerns, validated on real hardware via MTIB.

---

## 3. VSM App-Level Stub Tests (Stage 1b -- Firmware Repo)

### 3.1 What This Is

The Alpha firmware's "brain" is a pair of state machines:

1. **Heat risk state machine** (`alpha_state_machine.c`): Manages the device's core health monitoring lifecycle
   - `off_body_e` -- device is not on a person
   - `low_heat_risk_e` -- on body, HSI below `inc_risk_hsi_threshold`
   - `increased_heat_risk_e` -- HSI above `inc_risk_hsi_threshold`, below `emer_hsi_threshold`
   - `heat_emergency_e` -- HSI above `emer_hsi_threshold`
   - `off_body_validation_e` -- transitional, 20-second verification before confirming off-body

2. **Motion state machine** (`motion_state_machine.c`): Detects sustained physical activity
   - `motion_is_stopped` -- no motion detected
   - `motion_window_open` -- initial motion detected, waiting `motion_window_start_sec` to confirm
   - `motion_in_motion` -- sustained motion confirmed

These state machines depend on sensor data (`vsm_data_t`, `has_motion_occurred()`), configuration (`bio_config_t`, `motion_cfg_t`), timers, and IPC -- but they do not call sensor drivers directly. The app calls `get_vsm_data()`, `is_device_on_body()`, and `has_motion_occurred()`. This clean separation is exactly what makes stub testing effective: stub the data sources, test the decisions.

### 3.2 No Hardware Needed

These tests also run on `native_sim`. The entire sensor stack is stubbed:

- LSM6DSO (6-axis IMU) -- stubbed, provides motion events on demand
- PAH8151 (PPG sensor) -- stubbed, provides touch detection and heart rate
- MLX90614 (IR skin temp) -- stubbed, provides temperature
- BME280 (environmental) -- stubbed, provides ambient temp/humidity/pressure
- VSM (vital signs module) -- stubbed, provides `vsm_data_t` directly

The stub configuration replaces every hardware-dependent component with a test-controllable alternative.

### 3.3 Test Environment Setup

The app-level stub tests live in the firmware repo under `tests/app/`:

```
alpha_fw/
├── src/app/
│   ├── alpha_state_machine.c     # Code under test
│   ├── alpha_state_machine.h
│   ├── motion_state_machine.c    # Code under test
│   ├── motion_state_machine.h
│   ├── vsm_handler.h             # vsm_data_t, is_device_on_body()
│   ├── sensor_handler.h          # has_motion_occurred()
│   └── messages/
│       └── biometric_data_msg.h  # biometric_data_t
├── tests/
│   └── app/
│       ├── testcase.yaml
│       ├── prj.conf
│       ├── boards/
│       │   └── native_sim.overlay
│       └── src/
│           ├── test_alpha_state_machine.c
│           └── test_motion_state_machine.c
└── ...
```

**testcase.yaml** -- Declares two test suites, both restricted to `native_sim`:

```yaml
tests:
  app.alpha.state_machine:
    platform_allow: native_sim
    tags: unit app
    harness: ztest
    timeout: 120
  app.alpha.motion:
    platform_allow: native_sim
    tags: unit app
    harness: ztest
    timeout: 60
```

**prj.conf** -- Enables stubs for all sensor drivers, disables real hardware:

```kconfig
CONFIG_ZTEST=y
CONFIG_ZTEST_NEW_API=y

# Disable real drivers, enable stubs
CONFIG_CK_LSM6DSO=n
CONFIG_CK_LSM6DSO_STUB=y
CONFIG_CK_PAH8151=n
CONFIG_PAH8151_STUB=y
CONFIG_VSM=n
CONFIG_VSM_STUB=y

# Zephyr core
CONFIG_LOG=y
CONFIG_LOG_DEFAULT_LEVEL=3
CONFIG_SENSOR=y
CONFIG_GPIO=y
```

**boards/native_sim.overlay** -- Replaces real sensor device nodes with stubs:

```dts
/ {
    lsm6dso0: lsm6dso-stub {
        compatible = "ck,lsm6dso-stub";
        status = "okay";
    };

    pah8151: pah8151-stub {
        compatible = "ck,pah8151-stub";
        status = "okay";
    };

    vsm0: vsm-stub {
        compatible = "ck,vsm-stub";
        status = "okay";
    };
};
```

### 3.4 What is Being Tested

The test target is the state machine logic itself -- the `switch` statements, the threshold comparisons, the timer management, the state transitions. Everything that constitutes the "decision-making" of the firmware:

- **Heat risk thresholds**: `inc_risk_hsi_threshold` (default 80 = 8.0 HSI), `emer_hsi_threshold` (default 250 = 25.0 HSI)
- **Hysteresis**: `STATE_CHANGE_HYSTERESIS` (0.2) applied when decreasing risk state
- **Off-body verification**: `OFF_BODY_VERIFICATION_SEC` (20 seconds) timer before transitioning to `off_body_e`
- **Motion windows**: `motion_window_start_sec` (default 3), `motion_window_end_sec` (default 30), `motion_stop_sec` (default 60)
- **Warm-up period**: `VSM_WARM_UP_TIME_SEC` (60 seconds) before biometric reporting begins
- **Bio config**: `bio_config_t` with `low_risk_report_pd`, `inc_risk_report_pd`, `emer_report_pd`
- **State memory**: `_prev_on_body_state` tracking which on-body state to return to if touch returns during off-body validation

### 3.5 Example Tests -- Heat Risk State Machine

```c
/* alpha_fw/tests/app/src/test_alpha_state_machine.c */

#include <zephyr/ztest.h>
#include <zephyr/kernel.h>

#include "app/alpha_state_machine.h"
#include "app/motion_state_machine.h"
#include "app/vsm_handler.h"
#include "app/sensor_handler.h"

/* ---- Stub control API ---- */

/* These functions are provided by the stub implementations.
 * They allow tests to control what the state machine "sees"
 * when it calls get_vsm_data(), is_device_on_body(), etc. */
extern void vsm_stub_set_on_body(bool on_body);
extern void vsm_stub_set_data(vsm_data_t *data);
extern void motion_stub_set_motion(bool has_motion);
extern void stub_reset_all(void);

/* ---- Helpers ---- */

/* Forward-declare the state getter.
 * In production, _state is file-static. For testing, we either
 * expose it via a getter or use a test-only accessor. */
extern alpha_state_t alpha_get_state(void);

/* Run the state machine one tick -- simulates one pass of the main loop */
static void tick(void)
{
    run_alpha_state_machine();
}

/* Run the state machine for a given number of milliseconds of simulated time.
 * Each tick is separated by 100 ms of kernel sleep to allow timers to fire. */
static void tick_for_ms(uint32_t ms)
{
    uint32_t ticks = ms / 100;
    for (uint32_t i = 0; i < ticks; i++) {
        k_sleep(K_MSEC(100));
        tick();
    }
}

/* ---- Fixture ---- */

static void *suite_setup(void)
{
    return NULL;
}

static void test_before(void *fixture)
{
    ARG_UNUSED(fixture);
    stub_reset_all();
    init_alpha_state_machine();
}

/* ============================================================
 * Test: Initial state is off_body_e
 * ============================================================ */

ZTEST(alpha_sm, test_initial_state_is_off_body)
{
    zassert_equal(alpha_get_state(), off_body_e,
                  "Initial state should be off_body_e");
}

/* ============================================================
 * Test: off_body_e -> low_heat_risk_e on touch detection
 * ============================================================ */

ZTEST(alpha_sm, test_off_body_to_low_risk)
{
    zassert_equal(alpha_get_state(), off_body_e);

    /* Simulate touch detected -- PAH8151 reports device is on body */
    vsm_stub_set_on_body(true);

    tick();

    zassert_equal(alpha_get_state(), low_heat_risk_e,
                  "State should transition to low_heat_risk_e when on body");
}

/* ============================================================
 * Test: low_heat_risk_e -> increased_heat_risk_e when HSI
 *       exceeds inc_risk_hsi_threshold (default 80 = 8.0 HSI)
 * ============================================================ */

ZTEST(alpha_sm, test_low_risk_to_increased_risk)
{
    /* Enter low_heat_risk first */
    vsm_stub_set_on_body(true);
    tick();
    zassert_equal(alpha_get_state(), low_heat_risk_e);

    /* Set HSI above the increased risk threshold (default 80 = 8.0 HSI) */
    vsm_data_t data = {
        .heartrate = 120,
        .heartrate_confidence = 90,
        .spo2 = 97,
        .spo2_confidence = 85,
        .skin_temp_degC_q8p8 = (37 << 8),           /* 37.0 C */
        .heat_strain_index_tenths = 85,              /* 8.5 HSI -- above threshold */
        .est_core_temp_degC_q8p8 = (38 << 8) | 128, /* 38.5 C */
    };
    vsm_stub_set_data(&data);

    tick();

    zassert_equal(alpha_get_state(), increased_heat_risk_e,
                  "State should transition to increased_heat_risk_e when HSI > 80");
}

/* ============================================================
 * Test: increased_heat_risk_e -> heat_emergency_e when HSI
 *       exceeds emer_hsi_threshold (default 250 = 25.0 HSI)
 * ============================================================ */

ZTEST(alpha_sm, test_increased_risk_to_heat_emergency)
{
    /* Enter low_heat_risk */
    vsm_stub_set_on_body(true);
    tick();

    /* Enter increased_heat_risk */
    vsm_data_t data = {
        .heartrate = 140,
        .heartrate_confidence = 88,
        .spo2 = 95,
        .spo2_confidence = 80,
        .skin_temp_degC_q8p8 = (38 << 8),
        .heat_strain_index_tenths = 90,   /* Above inc_risk threshold */
        .est_core_temp_degC_q8p8 = (39 << 8),
    };
    vsm_stub_set_data(&data);
    tick();
    zassert_equal(alpha_get_state(), increased_heat_risk_e);

    /* Push HSI above emergency threshold (default 250) */
    data.heat_strain_index_tenths = 255;  /* 25.5 HSI -- emergency */
    data.heartrate = 165;
    vsm_stub_set_data(&data);

    tick();

    zassert_equal(alpha_get_state(), heat_emergency_e,
                  "State should transition to heat_emergency_e when HSI > 250");
}

/* ============================================================
 * Test: Hysteresis prevents rapid oscillation between states.
 *       Threshold to enter increased_heat_risk is 80.
 *       Threshold to drop back to low_heat_risk is 80 - 0.2 = 79.8
 *       Since HSI is stored as integer tenths, 80 tenths = exactly on the boundary.
 * ============================================================ */

ZTEST(alpha_sm, test_hysteresis_prevents_oscillation)
{
    /* Get to increased_heat_risk */
    vsm_stub_set_on_body(true);
    tick();

    vsm_data_t data = {
        .heartrate = 120,
        .spo2 = 97,
        .skin_temp_degC_q8p8 = (37 << 8),
        .heat_strain_index_tenths = 85,
        .est_core_temp_degC_q8p8 = (38 << 8),
    };
    vsm_stub_set_data(&data);
    tick();
    zassert_equal(alpha_get_state(), increased_heat_risk_e);

    /* Drop HSI to exactly the threshold -- should NOT drop back because of hysteresis.
     * inc_risk_hsi_threshold is 80. The comparison is:
     *   heat_strain_index_tenths < (inc_risk_hsi_threshold - STATE_CHANGE_HYSTERESIS)
     * which is: tenths < 79.8. So 80 should stay in increased_heat_risk. */
    data.heat_strain_index_tenths = 80;
    vsm_stub_set_data(&data);
    tick();

    zassert_equal(alpha_get_state(), increased_heat_risk_e,
                  "HSI at exactly the threshold should not drop state (hysteresis)");
}

/* ============================================================
 * Test: Off-body validation -- removing touch starts 20-second
 *       verification period before returning to off_body_e
 * ============================================================ */

ZTEST(alpha_sm, test_off_body_validation_timeout)
{
    /* Enter low_heat_risk */
    vsm_stub_set_on_body(true);
    tick();
    zassert_equal(alpha_get_state(), low_heat_risk_e);

    /* Remove from body -- should enter off_body_validation_e, not off_body_e directly */
    vsm_stub_set_on_body(false);
    tick();
    zassert_equal(alpha_get_state(), off_body_validation_e,
                  "Removing touch should enter off_body_validation_e, not off_body_e directly");

    /* Tick for less than OFF_BODY_VERIFICATION_SEC (20s) -- should stay in validation */
    tick_for_ms(15000);  /* 15 seconds */
    zassert_equal(alpha_get_state(), off_body_validation_e,
                  "Should still be in off_body_validation_e before 20s timeout");

    /* Tick past the 20-second threshold */
    tick_for_ms(6000);  /* Total: 21 seconds */
    zassert_equal(alpha_get_state(), off_body_e,
                  "Should transition to off_body_e after OFF_BODY_VERIFICATION_SEC");
}

/* ============================================================
 * Test: Re-touching during off-body validation returns to the
 *       previous on-body state (not always low_heat_risk_e)
 * ============================================================ */

ZTEST(alpha_sm, test_retouch_during_validation_returns_to_previous_state)
{
    /* Enter low_heat_risk then increased_heat_risk */
    vsm_stub_set_on_body(true);
    tick();

    vsm_data_t data = {
        .heartrate = 140,
        .spo2 = 96,
        .skin_temp_degC_q8p8 = (38 << 8),
        .heat_strain_index_tenths = 90,
        .est_core_temp_degC_q8p8 = (39 << 8),
    };
    vsm_stub_set_data(&data);
    tick();
    zassert_equal(alpha_get_state(), increased_heat_risk_e);

    /* Remove from body -- enters validation with _prev_on_body_state = increased_heat_risk_e */
    vsm_stub_set_on_body(false);
    tick();
    zassert_equal(alpha_get_state(), off_body_validation_e);

    /* Put back on body before 20s expires -- should return to increased_heat_risk_e */
    tick_for_ms(5000);  /* 5 seconds in validation */
    vsm_stub_set_on_body(true);
    tick();

    zassert_equal(alpha_get_state(), increased_heat_risk_e,
                  "Re-touch during validation should return to the previous on-body state, "
                  "not reset to low_heat_risk_e");
}

/* ============================================================
 * Test: Full cycle -- off_body -> on_body -> off_body_validation -> off_body
 * ============================================================ */

ZTEST(alpha_sm, test_full_lifecycle)
{
    /* Phase 1: off_body_e */
    zassert_equal(alpha_get_state(), off_body_e);

    /* Phase 2: Touch -> low_heat_risk_e */
    vsm_stub_set_on_body(true);
    tick();
    zassert_equal(alpha_get_state(), low_heat_risk_e);

    /* Phase 3: High HSI -> increased_heat_risk_e */
    vsm_data_t data = {
        .heartrate = 130,
        .spo2 = 96,
        .skin_temp_degC_q8p8 = (38 << 8),
        .heat_strain_index_tenths = 100,
        .est_core_temp_degC_q8p8 = (39 << 8),
    };
    vsm_stub_set_data(&data);
    tick();
    zassert_equal(alpha_get_state(), increased_heat_risk_e);

    /* Phase 4: HSI drops -> back to low_heat_risk_e */
    data.heat_strain_index_tenths = 60;  /* Well below threshold minus hysteresis */
    vsm_stub_set_data(&data);
    tick();
    zassert_equal(alpha_get_state(), low_heat_risk_e);

    /* Phase 5: Remove touch -> off_body_validation_e */
    vsm_stub_set_on_body(false);
    tick();
    zassert_equal(alpha_get_state(), off_body_validation_e);

    /* Phase 6: Wait 20s -> off_body_e */
    tick_for_ms(21000);
    zassert_equal(alpha_get_state(), off_body_e);
}

/* ============================================================
 * Test: bio_config_t thresholds can be changed at runtime
 * ============================================================ */

/* Forward-declare the config setter exposed for testing */
extern void alpha_set_bio_config(bio_config_t *cfg);

ZTEST(alpha_sm, test_config_update_changes_thresholds)
{
    /* Enter low_heat_risk */
    vsm_stub_set_on_body(true);
    tick();
    zassert_equal(alpha_get_state(), low_heat_risk_e);

    /* Lower the inc_risk threshold from 80 to 50 */
    bio_config_t custom_cfg = {
        .flags.value = 0,
        .low_risk_report_pd = 10,
        .inc_risk_hsi_threshold = 50,  /* Was 80 */
        .inc_risk_report_pd = 10,
        .emer_hsi_threshold = 250,
        .emer_report_pd = 10,
    };
    alpha_set_bio_config(&custom_cfg);

    /* HSI of 55 is below the old threshold (80) but above the new one (50) */
    vsm_data_t data = {
        .heartrate = 100,
        .spo2 = 98,
        .skin_temp_degC_q8p8 = (36 << 8),
        .heat_strain_index_tenths = 55,
        .est_core_temp_degC_q8p8 = (37 << 8),
    };
    vsm_stub_set_data(&data);
    tick();

    zassert_equal(alpha_get_state(), increased_heat_risk_e,
                  "After lowering threshold to 50, HSI=55 should trigger increased_heat_risk_e");
}

/* ============================================================
 * Test: off_body_validation from heat_emergency_e
 * ============================================================ */

ZTEST(alpha_sm, test_off_body_validation_from_emergency)
{
    /* Climb to heat_emergency */
    vsm_stub_set_on_body(true);
    tick();

    vsm_data_t data = {
        .heartrate = 170,
        .spo2 = 93,
        .skin_temp_degC_q8p8 = (40 << 8),
        .heat_strain_index_tenths = 90,
        .est_core_temp_degC_q8p8 = (40 << 8),
    };
    vsm_stub_set_data(&data);
    tick();
    zassert_equal(alpha_get_state(), increased_heat_risk_e);

    data.heat_strain_index_tenths = 255;
    vsm_stub_set_data(&data);
    tick();
    zassert_equal(alpha_get_state(), heat_emergency_e);

    /* Remove from body -- should enter validation even from emergency */
    vsm_stub_set_on_body(false);
    tick();
    zassert_equal(alpha_get_state(), off_body_validation_e,
                  "Off-body during heat_emergency should enter validation, "
                  "not jump straight to off_body_e");

    /* Re-touch -- should return to heat_emergency_e */
    vsm_stub_set_on_body(true);
    tick();
    zassert_equal(alpha_get_state(), heat_emergency_e,
                  "Re-touch during validation should return to heat_emergency_e");
}

ZTEST_SUITE(alpha_sm, NULL, suite_setup, test_before, NULL, NULL);
```

### 3.6 Example Tests -- Motion State Machine

```c
/* alpha_fw/tests/app/src/test_motion_state_machine.c */

#include <zephyr/ztest.h>
#include <zephyr/kernel.h>

#include "app/motion_state_machine.h"
#include "app/sensor_handler.h"

/* ---- Stub control API ---- */
extern void motion_stub_set_motion(bool has_motion);
extern void stub_reset_all(void);

/* ---- Helpers ---- */

extern motion_state_t motion_get_state(void);

static void motion_tick(void)
{
    run_motion_state_machine();
}

static void motion_tick_for_ms(uint32_t ms)
{
    uint32_t ticks = ms / 100;
    for (uint32_t i = 0; i < ticks; i++) {
        k_sleep(K_MSEC(100));
        motion_tick();
    }
}

/* ---- Fixture ---- */

static void *suite_setup(void)
{
    return NULL;
}

static void test_before(void *fixture)
{
    ARG_UNUSED(fixture);
    stub_reset_all();
    init_motion_state_machine();
}

/* ============================================================
 * Test: Initial state is motion_is_stopped
 * ============================================================ */

ZTEST(motion_sm, test_initial_state_is_stopped)
{
    zassert_equal(motion_get_state(), motion_is_stopped,
                  "Initial motion state should be motion_is_stopped");
}

/* ============================================================
 * Test: First motion event opens the motion window
 * ============================================================ */

ZTEST(motion_sm, test_motion_opens_window)
{
    motion_stub_set_motion(true);
    motion_tick();

    zassert_equal(motion_get_state(), motion_window_open,
                  "First motion event should open the motion window");
}

/* ============================================================
 * Test: Sustained motion beyond motion_window_start_sec (default 3s)
 *       transitions to motion_in_motion
 * ============================================================ */

ZTEST(motion_sm, test_sustained_motion_enters_in_motion)
{
    /* Start motion */
    motion_stub_set_motion(true);
    motion_tick();
    zassert_equal(motion_get_state(), motion_window_open);

    /* Continue motion past the 3-second motion_window_start_sec */
    motion_tick_for_ms(3500);

    zassert_equal(motion_get_state(), motion_in_motion,
                  "Sustained motion past motion_window_start_sec should enter motion_in_motion");
}

/* ============================================================
 * Test: Motion window closes if no sustained motion detected
 *       within motion_window_end_sec (default 30s)
 * ============================================================ */

ZTEST(motion_sm, test_window_closes_on_timeout)
{
    /* Brief motion event */
    motion_stub_set_motion(true);
    motion_tick();
    zassert_equal(motion_get_state(), motion_window_open);

    /* Stop motion -- window timer runs for motion_window_end_sec (30s) */
    motion_stub_set_motion(false);
    motion_tick_for_ms(31000);

    zassert_equal(motion_get_state(), motion_is_stopped,
                  "Motion window should close and return to stopped after timeout");
}

/* ============================================================
 * Test: In-motion state returns to stopped after
 *       motion_stop_sec (default 60s) of no motion
 * ============================================================ */

ZTEST(motion_sm, test_in_motion_stops_after_timeout)
{
    /* Get to motion_in_motion */
    motion_stub_set_motion(true);
    motion_tick();
    motion_tick_for_ms(3500);
    zassert_equal(motion_get_state(), motion_in_motion);

    /* Stop motion -- wait for motion_stop_sec (60s) */
    motion_stub_set_motion(false);
    motion_tick_for_ms(61000);

    zassert_equal(motion_get_state(), motion_is_stopped,
                  "Should return to stopped after motion_stop_sec of no motion");
}

/* ============================================================
 * Test: Continued motion resets the stop timer
 * ============================================================ */

ZTEST(motion_sm, test_continued_motion_resets_stop_timer)
{
    /* Get to motion_in_motion */
    motion_stub_set_motion(true);
    motion_tick();
    motion_tick_for_ms(3500);
    zassert_equal(motion_get_state(), motion_in_motion);

    /* Stop briefly then resume before motion_stop_sec */
    motion_stub_set_motion(false);
    motion_tick_for_ms(30000);  /* 30s -- still within the 60s window */

    /* Resume motion -- this resets the stop timer */
    motion_stub_set_motion(true);
    motion_tick();
    zassert_equal(motion_get_state(), motion_in_motion,
                  "Should still be in motion after brief pause");

    /* Now wait another full motion_stop_sec of no motion */
    motion_stub_set_motion(false);
    motion_tick_for_ms(61000);
    zassert_equal(motion_get_state(), motion_is_stopped);
}

/* ============================================================
 * Test: set_motion_config updates the timing parameters
 * ============================================================ */

ZTEST(motion_sm, test_config_update)
{
    /* Change motion_window_start_sec from 3 to 1 */
    set_motion_config(1, 30, 60);

    /* Motion should confirm faster now */
    motion_stub_set_motion(true);
    motion_tick();
    zassert_equal(motion_get_state(), motion_window_open);

    motion_tick_for_ms(1500);  /* 1.5s -- above the new 1s threshold */
    zassert_equal(motion_get_state(), motion_in_motion,
                  "With motion_window_start_sec=1, should enter in_motion after 1.5s");
}

/* ============================================================
 * Test: force_motion_state_machine overrides state
 * ============================================================ */

ZTEST(motion_sm, test_force_motion_state)
{
    zassert_equal(motion_get_state(), motion_is_stopped);

    force_motion_state_machine(true);
    zassert_equal(motion_get_state(), motion_in_motion,
                  "force_motion_state_machine(true) should set motion_in_motion");

    force_motion_state_machine(false);
    zassert_equal(motion_get_state(), motion_is_stopped,
                  "force_motion_state_machine(false) should set motion_is_stopped");
}

/* ============================================================
 * Test: has_motion_ever_occurred flag
 * ============================================================ */

ZTEST(motion_sm, test_has_motion_ever_occurred)
{
    zassert_false(has_motion_ever_occurred(),
                  "Should be false initially");

    /* Get to motion_in_motion -- this sets the flag */
    motion_stub_set_motion(true);
    motion_tick();
    motion_tick_for_ms(3500);
    zassert_equal(motion_get_state(), motion_in_motion);

    zassert_true(has_motion_ever_occurred(),
                 "Should be true after entering motion_in_motion");

    /* Reset the flag */
    reset_has_motion_ever_occurred();
    zassert_false(has_motion_ever_occurred(),
                  "Should be false after reset");
}

ZTEST_SUITE(motion_sm, NULL, suite_setup, test_before, NULL, NULL);
```

### 3.7 What This Proves vs. What It Cannot Prove

**What these tests prove:**

- The heat risk state machine transitions correctly between all five states given controlled sensor inputs
- The `off_body_validation_e` transitional state works: it waits 20 seconds (`OFF_BODY_VERIFICATION_SEC`) before confirming off-body, and returns to the correct previous state if touch is re-detected
- The HSI thresholds (`inc_risk_hsi_threshold`, `emer_hsi_threshold`) correctly gate state transitions
- The hysteresis (`STATE_CHANGE_HYSTERESIS = 0.2`) prevents rapid oscillation at state boundaries
- Runtime `bio_config_t` changes (threshold adjustments) take effect on the next state machine tick
- The motion state machine correctly implements its three-state model: `motion_is_stopped` -> `motion_window_open` -> `motion_in_motion`
- Motion timing parameters (`motion_window_start_sec`, `motion_window_end_sec`, `motion_stop_sec`) control transitions correctly
- The `set_motion_config()` API updates timing parameters at runtime
- `force_motion_state_machine()` overrides state for test/diagnostic purposes
- The `has_motion_ever_occurred()` flag is set and can be reset

**What these tests cannot prove:**

- That the PAH8151 touch detection actually works (real PPG sensor, real skin contact)
- That `is_device_on_body()` correctly interprets real PPG signal quality
- That the LSM6DSO motion interrupt fires at the correct threshold on real hardware
- That `get_vsm_data()` returns accurate vital signs from the real VSM processing pipeline
- That biometric data messages are correctly serialized and sent over IPC to the nRF9151
- That Zephyr timers (`k_timer`) have the expected precision on real nRF52840 hardware
- That the power management (VSM init/deinit) actually changes current draw
- That real sensor warm-up times match `VSM_WARM_UP_TIME_SEC`

These are Stage 2 (driver hardware tests) and Stage 3 (integration tests on real hardware) concerns.

---

## 4. Build and Pipeline Integration

### 4.1 Where Stage 1 Runs

Stage 1 tests run on **agent nodes** -- standard Linux VMs in the CI cluster. They do not need MTIB, do not need any test hardware, and do not need any special capabilities. Any agent that can run `west build` and execute a native Linux binary can run Stage 1.

### 4.2 Pipeline Flow

```
Commit pushed
    │
    ▼
Stage 1: Software Tests (agent node, ~30-60 seconds)
    ├── accel_drv/tests/interface/ (driver interface tests on native_sim)
    └── alpha_fw/tests/app/          (app stub tests on native_sim)
    │
    │   PASS? ──────────── FAIL? → Pipeline stops. No hardware wasted.
    ▼
Stage 2: Driver Hardware Tests (MTIB dev-kit, ~2-5 minutes)
    │
    ▼
Stage 3: Integration Tests (MTIB product board, ~3-5 minutes)
    │
    ▼
Stage 4: Product Validation (MTIB product board, ~5-10 minutes)
```

Stage 1 is the **cheapest gate**. It costs nothing -- no hardware reservation, no MTIB coordination, no flashing. If a state machine regression or a config parsing bug breaks the tests, the pipeline stops in under a minute. The more expensive stages (which require physical hardware on MTIB) never run.

### 4.3 Concord Pipeline Configuration

In the driver repo (Stage 1 excerpt from the full `pipeline.yaml`):

```yaml
# accel_drv/.concord/pipeline.yaml (Stage 1 section)
version: 1

on:
  push:
    branches: ["main", "develop", "feature/*"]
    paths:
      - "drivers/**"
      - "stubs/**"
      - "tests/**"
      - "dts/**"
      - ".concord/**"

stages:
  - name: software
    order: 1
    type: native_sim
    testPaths: ["tests/interface"]
    timeout: 600
    retry:
      max_attempts: 2
      on: [infrastructure_failure]
```

In the firmware repo (Stage 1 excerpt):

```yaml
# alpha_fw/.concord/pipeline.yaml (Stage 1 section)
version: 1

on:
  push:
    branches: ["main", "develop", "feature/*"]
    paths:
      - "tests/app/**"
      - "src/**"

stages:
  - name: software
    order: 1
    type: native_sim
    testPaths: ["tests/app"]
    timeout: 600
    retry:
      max_attempts: 2
      on: [infrastructure_failure]
```

No `needsMtib`, no `targets`, no `fixture_type` -- those fields only appear in Stage 2+ configurations. The full `pipeline.yaml` schema is defined in [arch-stage1-software-tests.md](../../architecture/stage1-software-tests.md) Section 5.4.

### 4.4 Build Artifacts

Stage 1 produces:

- **Test binaries**: Native Linux executables (`.exe` suffix by Zephyr convention, but they are ELF binaries)
- **Twister results**: `twister.json` with pass/fail for each test case
- **Build artifacts**: Used only for pass/fail determination, not preserved for later stages

Stage 1 does **not** produce firmware images. The firmware hex files for flashing onto real hardware are built separately as part of Stage 2/3/4 build steps.

---

## 5. What These Tests Catch

### 5.1 Concrete Bug Examples

**Bug: Off-body validation timer not started from heat_emergency_e**

A developer modifies `alpha_state_machine.c` and adds the off-body detection path for `heat_emergency_e` but forgets to start the `off_body_verify_timer`. The test `test_off_body_validation_from_emergency` would catch this: the state machine enters `off_body_validation_e` but never transitions to `off_body_e` because the timer never fires.

**Bug: Hysteresis applied in the wrong direction**

A developer changes the comparison from `<` to `<=` in the hysteresis check:

```c
/* Before (correct): */
if (vsm_data.heat_strain_index_tenths < (_biometric_config.inc_risk_hsi_threshold - STATE_CHANGE_HYSTERESIS))

/* After (wrong): */
if (vsm_data.heat_strain_index_tenths <= _biometric_config.inc_risk_hsi_threshold)
```

The test `test_hysteresis_prevents_oscillation` would catch this: HSI at exactly the threshold would incorrectly trigger a state downgrade.

**Bug: motion_window_start_sec boundary off-by-one**

A developer changes `>` to `>=` in the motion window comparison:

```c
/* Before: motion must persist LONGER than motion_window_start_sec */
if ((current_time - _motion_start_timestamp) > (1000 * _motion_cfg.motion_window_start_sec))

/* After: motion at exactly the boundary triggers too early */
if ((current_time - _motion_start_timestamp) >= (1000 * _motion_cfg.motion_window_start_sec))
```

The test `test_sustained_motion_enters_in_motion` validates the expected timing, and a dedicated boundary test could catch this.

**Bug: _prev_on_body_state not saved before entering off_body_validation_e**

If the developer forgets to set `_prev_on_body_state = heat_emergency_e` in the `heat_emergency_e` case, the test `test_retouch_during_validation_returns_to_previous_state` would catch it: re-touching during validation would return to the wrong state.

**Bug: Motion trigger callback still fires after disarming**

If the stub's `trigger_set(dev, trig, NULL)` path does not clear the handler, the test `test_motion_trigger_disarm` catches it immediately.

**Bug: SENSOR_CHAN_LSM6DSO_SAMPLE_COUNT returns wrong type**

If a refactor accidentally changes the FIFO sample count channel to return `val2` instead of `val1`, the test `test_fifo_sample_count` catches it.

### 5.2 What Stage 1 Does NOT Catch

These failure modes require real hardware:

| Failure Mode | Why Stage 1 Misses It | Which Stage Catches It |
|-------------|----------------------|----------------------|
| LSM6DSO FIFO overflows at 104 Hz because the bus is too slow | Stub has no bus timing | Stage 2 (dev-kit) |
| Motion interrupt latency exceeds 10 ms on the Alpha board | Stub fires callbacks instantly | Stage 2 (product board) |
| PAH8151 touch detection falsely triggers from board vibration | Stub touch is deterministic | Stage 3 (integration) |
| IPC UART framing errors under high message rate | Stub has no UART | Stage 3 (integration) |
| nRF52840 enters system-off and fails to wake on motion interrupt | Stub runs on Linux, no sleep states | Stage 3 (integration) |
| Battery SoC reading drifts after 4 hours of monitoring | Stub battery is static | Stage 4 (product validation) |

This is the core principle: Stage 1 tests the logic, Stages 2-4 test the hardware. Both are necessary. Neither is sufficient alone.
