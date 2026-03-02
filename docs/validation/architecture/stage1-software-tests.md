# Stage 1 Software Tests -- Implementation Architecture

> Implementation blueprint for Stage 1 (native_sim software tests) targeting
> the Alpha product and LSM6DSO accelerometer. This is NOT an example document
> -- see [11-stage1-alpha-example.md](../examples/alpha/stage1-alpha-example.md) for worked
> examples. This document specifies what needs to be built, how it fits
> together, the interfaces between components, and a concrete roadmap.

**Key decisions already locked:**

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Driver repo | `accel_drv` (Sigma's existing accelerometer repo) | Re-use existing repo identity; new clean branch |
| First chip | LSM6DSO only; LIS2DE12/LIS2DW12 not in initial scope | Thin vertical slice; Alpha product coverage |
| DTS vendor prefix | `ck,` for everything including stubs (`ck,lsm6dso-stub`) | Consistent namespace across production and test |
| Production code changes | Minimize; framework must be maximally decoupled from app | State machine testability via test-only accessor, not restructuring |
| `CONFIG_CK_LSM6DSO_TRIGGER` | Deferred | Wait for new accel driver interface; may not be chip-specific |

**Prerequisite reading:**
- [00-validation-philosophy.md](./00-validation-philosophy.md) -- Sections 3.1, 5.1, 8
- [09-final-architecture.md](./09-final-architecture.md) -- Stage 1 runner spec, build service, pipeline.yaml schema
- [11-stage1-alpha-example.md](../examples/alpha/stage1-alpha-example.md) -- Worked examples (reference only)

---

## 1. Scope and Goals

### 1.1 What Stage 1 Proves

Stage 1 software tests answer one question: **is the application logic correct given known sensor inputs?** They run on `native_sim` -- Zephyr's POSIX simulation platform -- on any amd64 CI agent node. No physical hardware. No MTIB. Execution time under 60 seconds.

Concretely, Stage 1 for Alpha validates:

- Heat risk state machine transitions (`off_body_e` -> `low_heat_risk_e` -> `increased_heat_risk_e` -> `heat_emergency_e` -> `off_body_validation_e`) given controlled VSM data
- HSI threshold comparisons against `bio_config_t` parameters
- Hysteresis logic (`STATE_CHANGE_HYSTERESIS = 0.2`) preventing oscillation at state boundaries
- Off-body verification timer (20-second `off_body_verify_timer`)
- Previous-state memory (`_prev_on_body_state`) for re-touch during validation
- Motion state machine three-state model (`motion_is_stopped` -> `motion_window_open` -> `motion_in_motion`)
- Motion timing parameters and runtime config updates via `set_motion_config()`
- LSM6DSO `sensor_driver_api` interface contract (accel/gyro readback, FIFO count, motion triggers, error propagation)

### 1.2 What Stage 1 Does NOT Prove

- That any real sensor works on real silicon (Stage 2)
- That SPI/I2C bus transactions succeed (Stage 2)
- That interrupt latency meets requirements (Stage 2)
- That multi-sensor orchestration works end-to-end (Stage 3)
- That the product works as a product in black-box conditions (Stage 4)

Stage 1 is the cheapest gate. If it fails, nothing else runs.

### 1.3 Two Sub-Categories

| Category | What | Where It Lives | Trigger |
|----------|------|----------------|---------|
| **Stage 1a -- Interface tests** | Driver API contract on `native_sim` via stub | `accel_drv` repo, `tests/interface/` | Push to `accel_drv` |
| **Stage 1b -- App-level stub tests** | State machine logic with all sensors stubbed | `alpha_fw` repo, `tests/app/` | Push to `alpha_fw` OR push to `accel_drv` (cross-repo build) |

---

## 2. Repository Layout

### 2.1 `accel_drv` Repo -- Clean Nuke Branch

The new branch **nukes everything** in the existing `accel_drv` repo. This is an experiment — a clean-slate implementation of the driver repo architecture defined in [00-validation-philosophy.md](./00-validation-philosophy.md) Section 3.1c. The legacy LIS2DE12/LIS2DW12 code remains on the old branch and is not carried forward. Only the LSM6DSO driver is implemented initially.

**Target state (the only thing on the new branch):**
```
accel_drv/
├── drivers/lsm6dso/                       # Fresh custom driver (NOT a fork of upstream Zephyr driver)
│   └── src/
│       ├── lsm6dso.c                     # Real driver (sensor_driver_api)
│       ├── lsm6dso.h                     # Driver types, custom channels/attrs
│       └── lsm6dso_reg.h                 # Register definitions
├── dts/bindings/                          # Sensor DT bindings OWNED by this repo
│   ├── ck,lsm6dso.yaml                   # Binding: accel/gyro config, IRQ, power modes
│   └── ck,lsm6dso-stub.yaml              # Stub binding for native_sim
├── stubs/                                 # Stub implementations for ALL drivers in this group
│   ├── lsm6dso_stub.c                    # sensor_driver_api stub
│   ├── Kconfig                            # CONFIG_CK_LSM6DSO_STUB
│   └── CMakeLists.txt
├── tests/                                 # Zephyr-native test code (C, ztest, Twister metadata)
│   ├── interface/                         # Interface contract tests (native_sim via stubs)
│   │   ├── testcase.yaml                 # platform_allow: native_sim
│   │   └── src/main.c
│   └── lsm6dso/                           # Chip-specific HW tests (product-agnostic)
│       ├── src/main.c                     # ztest firmware exercising the driver
│       ├── testcase.yaml                  # NO product boards — pipeline decides
│       └── test_spec.yaml                 # power budgets from DATASHEET
├── .concord/                              # Pipeline infrastructure (Concord-specific config)
│   ├── pipeline.yaml                      # targets, triggers, stages, notifications
│   └── build.yaml                         # build recipe (how to compile tests for each board)
└── zephyr/module.yml                      # Registers repo as Zephyr module (makes dts/bindings/ discoverable)
```

**Key design principles:**

1. **Clean slate.** No legacy code. No backward compatibility shims. The old `zephyr/`, `test/`, `unit_testing/` directories do not exist on this branch. If Sigma needs the old LIS2DE12 driver, it stays on the old branch.
2. **Flat driver paths.** Drivers live at `drivers/<chip>/src/`, not nested under vendor directories. This matches the philosophy doc's canonical layout and keeps paths short.
3. **One repo, multiple chips.** The layout supports adding `drivers/lis2de12/` later with the same structure. Stubs, bindings, and tests follow the same per-chip pattern.
4. **Tests are first-class citizens.** The `tests/` directory has both `interface/` (Stage 1, native_sim) and per-chip HW tests (Stage 2). The repo is designed for testability from day one.
5. **No product knowledge.** The driver repo doesn't know which products use it, which boards they run on, or what the pin assignments are. That information comes from `ck_boards` (DTS) and `SubmoduleMapping` (pipeline).

### 2.3 Root Build Files

**`accel_drv/Kconfig`** (merged):

```kconfig
# LSM6DSO driver (Zephyr sensor_driver_api)
rsource "drivers/lsm6dso/Kconfig"

# LSM6DSO stub for testing
rsource "stubs/Kconfig"
```

Note: the LSM6DSO driver's own Kconfig lives at `drivers/lsm6dso/Kconfig` and contains the `CK_LSM6DSO` menuconfig. That file is not duplicated here -- it is `rsource`'d from the root.

**`accel_drv/CMakeLists.txt`** (merged):

```cmake
# LSM6DSO driver
if(CONFIG_CK_LSM6DSO)
  zephyr_include_directories(drivers)
  add_subdirectory(drivers/lsm6dso)
endif()

# LSM6DSO stub driver (test builds only)
if(CONFIG_CK_LSM6DSO_STUB)
  add_subdirectory(stubs)
endif()
```

**`accel_drv/zephyr/module.yml`** (updated):

```yaml
name: accel_drv
build:
  cmake: .
  kconfig: Kconfig
  settings:
    dts_root: .
```

The `dts_root: .` setting makes Zephyr's build system search `dts/bindings/` relative to the repo root. This is how both `ck,lsm6dso.yaml` and `ck,lsm6dso-stub.yaml` become discoverable to the DTS compiler.

### 2.4 `alpha_fw` Test Directory

```
alpha_fw/
├── src/app/
│   ├── alpha_state_machine.c        # Code under test (MINIMAL changes)
│   ├── alpha_state_machine.h        # Public header (add test accessor)
│   ├── motion_state_machine.c       # Code under test (MINIMAL changes)
│   ├── motion_state_machine.h       # Public header (add test accessor)
│   ├── vsm_handler.h               # vsm_data_t, is_device_on_body()
│   ├── sensor_handler.h            # has_motion_occurred()
│   └── ...
├── tests/                           # NEW directory
│   └── app/                         # App-level stub tests (Stage 1b)
│       ├── testcase.yaml
│       ├── prj.conf
│       ├── CMakeLists.txt
│       ├── boards/
│       │   └── native_sim.overlay
│       └── src/
│           ├── main.c               # ztest registration
│           ├── stubs.c              # Module-level stubs for ~15 dependencies
│           ├── test_alpha_state_machine.c
│           └── test_motion_state_machine.c
└── ...
```

---

## 3. Stub Driver Architecture

### 3.1 LSM6DSO Stub Driver (`accel_drv/stubs/`)

The stub implements the Zephyr `sensor_driver_api` -- the same API surface the real LSM6DSO driver exposes. It does not emulate registers, SPI, or any hardware behavior. It returns whatever values the test pre-loads.

**`accel_drv/stubs/Kconfig`:**

```kconfig
config CK_LSM6DSO_STUB
    bool "Use LSM6DSO stub driver (for testing)"
    depends on !CK_LSM6DSO
    select SENSOR
    help
      Stub implementation of LSM6DSO sensor_driver_api.
      Returns pre-configured values set via test API.
      Only for native_sim app-level testing.
```

The `depends on !CK_LSM6DSO` ensures mutual exclusivity -- you cannot enable both the real driver and the stub in the same build.

**`accel_drv/stubs/CMakeLists.txt`:**

```cmake
zephyr_library()
zephyr_library_sources_ifdef(CONFIG_CK_LSM6DSO_STUB lsm6dso_stub.c)
zephyr_include_directories(.)
```

**`accel_drv/stubs/lsm6dso_stub.h`** -- Test-only API:

```c
#ifndef LSM6DSO_STUB_H_
#define LSM6DSO_STUB_H_

#include <zephyr/drivers/sensor.h>

/**
 * Pre-load accelerometer values (milli-g).
 * Next sensor_channel_get(SENSOR_CHAN_ACCEL_*) will return these.
 */
void lsm6dso_stub_set_accel(int32_t x_mg, int32_t y_mg, int32_t z_mg);

/**
 * Pre-load gyroscope values (milli-degrees per second).
 */
void lsm6dso_stub_set_gyro(int32_t x_mdps, int32_t y_mdps, int32_t z_mdps);

/**
 * Pre-load FIFO sample count.
 */
void lsm6dso_stub_set_fifo_count(int16_t count);

/**
 * Inject an error code. Next sample_fetch/channel_get returns this.
 * Set to 0 to clear.
 */
void lsm6dso_stub_inject_error(int err);

/**
 * Fire a trigger callback (e.g., SENSOR_TRIG_MOTION).
 * Only works if the trigger was previously armed via sensor_trigger_set().
 */
void lsm6dso_stub_fire_trigger(enum sensor_trigger_type type);

/**
 * Reset all stub state to defaults. Call in test_before().
 */
void lsm6dso_stub_reset(void);

#endif /* LSM6DSO_STUB_H_ */
```

**`accel_drv/stubs/lsm6dso_stub.c`** -- implementation:

The stub must define `DT_DRV_COMPAT` as `ck_lsm6dso_stub` (the C-token form of the compatible string `ck,lsm6dso-stub`):

```c
#define DT_DRV_COMPAT ck_lsm6dso_stub

#include <zephyr/drivers/sensor.h>
#include <zephyr/device.h>
#include <string.h>
#include "lsm6dso_stub.h"

/* Import custom channels/attributes from the real driver header */
#include <corekinect/sensors/lsm6dso/lsm6dso.h>

static struct sensor_value stub_accel[3];
static struct sensor_value stub_gyro[3];
static int16_t stub_fifo_sample_count;
static sensor_trigger_handler_t stub_motion_handler;
static const struct sensor_trigger *stub_motion_trig;
static bool stub_fetch_configured;
static int stub_error_code;

/* ... test-only API implementations ... */
/* ... sensor_driver_api implementations ... */

static const struct sensor_driver_api lsm6dso_stub_api = {
    .attr_set = stub_attr_set,
    .sample_fetch = stub_sample_fetch,
    .channel_get = stub_channel_get,
    .trigger_set = stub_trigger_set,
};

DEVICE_DT_INST_DEFINE(0, NULL, NULL, NULL, NULL,
                      POST_KERNEL, CONFIG_SENSOR_INIT_PRIORITY,
                      &lsm6dso_stub_api);
```

The full implementation follows the pattern shown in [11-stage1-alpha-example.md](../examples/alpha/stage1-alpha-example.md) Section 2.4. Key details:

- `stub_channel_get` handles all channels the real driver supports: `SENSOR_CHAN_ACCEL_{X,Y,Z,XYZ}`, `SENSOR_CHAN_GYRO_{X,Y,Z,XYZ}`, `SENSOR_CHAN_LSM6DSO_SAMPLE_COUNT`, `SENSOR_CHAN_LSM6DSO_TIMESTAMP`. Returns `-ENOTSUP` for unrecognized channels.
- `stub_attr_set` accepts all attributes silently (returns 0 or injected error).
- `stub_trigger_set` stores the handler for `SENSOR_TRIG_MOTION`. Returns `-ENOTSUP` for other trigger types.
- `lsm6dso_stub_fire_trigger(SENSOR_TRIG_MOTION)` invokes the stored handler if armed.

### 3.2 DTS Stub Binding

**`accel_drv/dts/bindings/ck,lsm6dso-stub.yaml`:**

```yaml
description: |
  LSM6DSO stub sensor for testing on native_sim.
  Implements sensor_driver_api with pre-configured test data.
  Does not talk to any bus.

compatible: "ck,lsm6dso-stub"

include: sensor-device.yaml
```

The binding deliberately includes no bus properties (no `on-bus: spi`, no `reg`, no `irq-gpios`). The stub does not need them.

### 3.3 DTS Overlay for native_sim

**`accel_drv/tests/interface/boards/native_sim.overlay`:**

```dts
/ {
    lsm6dso0: lsm6dso-stub {
        compatible = "ck,lsm6dso-stub";
        status = "okay";
    };
};
```

The node label `lsm6dso0` matches what application code uses: `DEVICE_DT_GET(DT_NODELABEL(lsm6dso0))`. This is the mechanism that makes the swap transparent -- same label, different implementation.

### 3.4 Kconfig Integration Pattern

The switching mechanism relies on Kconfig mutual exclusivity:

```
Production build (alpha_b0):          Test build (native_sim):
  CONFIG_CK_LSM6DSO=y                  CONFIG_CK_LSM6DSO=n
  CONFIG_CK_LSM6DSO_STUB=n             CONFIG_CK_LSM6DSO_STUB=y
  DTS: ck,lsm6dso on &spi0             DTS: ck,lsm6dso-stub (no bus)
  Links: lsm6dso.c                     Links: lsm6dso_stub.c
```

The test's `prj.conf` explicitly sets both symbols. The `depends on !CK_LSM6DSO` in the stub's Kconfig prevents accidental co-enablement.

---

## 4. App-Level Test Architecture

### 4.1 The Dependency Isolation Problem

This is the hardest problem in Stage 1. The Alpha state machines have deep coupling to many modules. Here is the complete dependency graph for `alpha_state_machine.c`:

**Direct `#include` dependencies:**

| Header | Provides | Category |
|--------|----------|----------|
| `alpha_state_machine.h` | Own public interface | Test target |
| `app_thread.h` | `wakeup_app()` | Needs stub |
| `hw_failure_handler.h` | `is_hw_failure()`, `is_emergency_trigger()`, `handle_emergency_conditions()`, `is_emergency_acked()`, `is_vsm_failure()` | Needs stub |
| `lights_handler.h` | `lights_handler_set_status()`, `lights_handler_get_status_mode()` | Needs stub |
| `motion_state_machine.h` | `is_in_motion_state()` | Co-tested (link real code) |
| `position_handler.h` | `init_position_handler()`, `set_position_handler_mode()`, `run_position_handler()`, `is_new_position_data()` | Needs stub |
| `sensor_handler.h` | `has_motion_occurred()`, `reset_motion_flag()`, `get_air_pressure_hPa()`, `get_temperature_degC()`, `get_humidity_percentage()` | Needs stub |
| `sos_handler.h` | `init_sos_handler()`, `run_sos_handler()`, `is_active_sos_event()` | Needs stub |
| `vsm_handler.h` | `get_vsm_data()`, `is_device_on_body()`, `reinit_vsm_sensor()`, `deinit_vsm_sensor()`, `is_vsm_initialized()`, `set_est_core_data_persistent_state()` | Needs stub |
| `messages/biometric_data_msg.h` | `send_biometric_data_msg()`, `biometric_data_t` | Needs stub |
| `platform/vibrator.h` | (may be included transitively) | Needs stub |
| `persistent_data/persistent_data.h` | `persistent_data_save()` | Needs stub |
| `sockserv_util/storage_handler_defs.h` | `storage_priority_t` enum | Needs type definition |
| `server_time.h` | `get_server_time()` | Needs stub |

**Additional dependencies for `motion_state_machine.c`:**

| Header | Provides | Category |
|--------|----------|----------|
| `sensor_handler.h` | `has_motion_occurred()`, `reset_motion_flag()` | Needs stub |
| `ck_ipc/comm_coproc/motion_event.h` | `send_ipc_motion_event()`, `ipc_motion_event_t` | Needs stub |
| `fw_utils.h` | `handle_running_timer()` | Needs stub |

That is approximately **15 modules** that need stubs. This is the single largest effort item in Stage 1.

### 4.2 Proposed Solution: Module-Level Stub File + Test-Only Accessors

**Principle: minimize production code changes. The framework adapts to the code, not the other way around.**

The solution has two parts:

#### Part A: Module-Level Stubs (`tests/app/src/stubs.c`)

A single C file provides stub implementations for all ~15 external dependencies. These are NOT sensor driver stubs (those are in `accel_drv/stubs/`). These are app-module stubs -- they replace the functions that `alpha_state_machine.c` and `motion_state_machine.c` call.

```c
/* alpha_fw/tests/app/src/stubs.c */

#include <zephyr/kernel.h>
#include <stdbool.h>
#include <stdint.h>
#include <string.h>

/* Include the REAL headers so we get the correct type definitions */
#include "app/vsm_handler.h"
#include "app/sensor_handler.h"
#include "app/motion_state_machine.h"
#include "messages/biometric_data_msg.h"

/* ---- Controllable stub state ---- */

static bool _stub_on_body = false;
static vsm_data_t _stub_vsm_data;
static bool _stub_has_motion = false;
static bool _stub_vsm_initialized = false;

/* ---- Test control API ---- */

void vsm_stub_set_on_body(bool on_body)
{
    _stub_on_body = on_body;
}

void vsm_stub_set_data(vsm_data_t *data)
{
    memcpy(&_stub_vsm_data, data, sizeof(vsm_data_t));
}

void motion_stub_set_motion(bool has_motion)
{
    _stub_has_motion = has_motion;
}

void stub_reset_all(void)
{
    _stub_on_body = false;
    memset(&_stub_vsm_data, 0, sizeof(vsm_data_t));
    _stub_has_motion = false;
    _stub_vsm_initialized = false;
}

/* ---- vsm_handler.h stubs ---- */

bool is_device_on_body(void) { return _stub_on_body; }
vsm_data_t get_vsm_data(void) { return _stub_vsm_data; }
void reinit_vsm_sensor(void) { _stub_vsm_initialized = true; }
void deinit_vsm_sensor(void) { _stub_vsm_initialized = false; }
bool is_vsm_initialized(void) { return _stub_vsm_initialized; }
void init_vsm_handler(void) {}
void run_vsm_handler(void) {}
bool is_vsm_handler_event(void) { return false; }
void reset_ect_calc_params(void) {}
void set_est_core_data_persistent_state(bool do_save) {}
uint8_t *get_est_core_temp_ptr(void) { return NULL; }
uint32_t get_est_core_temp_size(void) { return 0; }
bool is_est_core_temp_to_save(void) { return false; }

/* ---- sensor_handler.h stubs ---- */

bool has_motion_occurred(void) { return _stub_has_motion; }
void reset_motion_flag(void) { _stub_has_motion = false; }
double get_air_pressure_hPa(void) { return 1013.25; }
double get_temperature_degC(void) { return 25.0; }
double get_humidity_percentage(void) { return 50.0; }
void init_sensor_handler(void) {}
void run_sensor_handler(void) {}
bool is_sensor_trigger_to_process(void) { return false; }
uint8_t get_avg_force(bool r) { return 0; }
uint8_t get_max_force(bool r) { return 0; }
/* ... remaining sensor_handler.h functions ... */

/* ---- app_thread.h stubs ---- */

void wakeup_app(void) {}  /* No-op: tests drive the loop explicitly */

/* ---- lights_handler.h stubs ---- */

void lights_handler_set_status(int mode, int period_ms) {}
int lights_handler_get_status_mode(void) { return 0; }

/* ---- position_handler.h stubs ---- */

void init_position_handler(void) {}
void set_position_handler_mode(bool active) {}
void run_position_handler(void) {}
bool is_new_position_data(void) { return false; }

/* ---- sos_handler.h stubs ---- */

void init_sos_handler(void) {}
void run_sos_handler(void) {}
bool is_active_sos_event(void) { return false; }
bool is_emergency_acked(void) { return false; }

/* ---- hw_failure_handler.h stubs ---- */

bool is_hw_failure(void) { return false; }
bool is_emergency_trigger(void) { return false; }
void handle_emergency_conditions(void) {}
bool is_vsm_failure(void) { return false; }

/* ---- messages/biometric_data_msg.h stubs ---- */

void send_biometric_data_msg(biometric_data_t *data, int priority) {}

/* ---- persistent_data stubs ---- */

void persistent_data_save(void) {}

/* ---- server_time.h stubs ---- */

uint32_t get_server_time(void) { return 1000000; }

/* ---- ck_ipc motion event stubs (for motion_state_machine.c) ---- */

void send_ipc_motion_event(void *msg) {}

/* ---- fw_utils.h stubs ---- */

void handle_running_timer(struct k_timer *timer, uint32_t period_ms, bool restart)
{
    if (restart) {
        k_timer_start(timer, K_MSEC(period_ms), K_NO_WAIT);
    }
}
```

This approach uses **link-time substitution**: the test binary links `stubs.c` instead of the real module implementations. The linker resolves `is_device_on_body()` to the stub function because the real `vsm_handler.c` is not included in the build.

#### Part B: Test-Only Accessors for File-Static State

The core testability problem: `alpha_state_t _state` and `motion_state_t _motion_state` are `static` variables in their respective `.c` files. Tests need to observe them.

**Evaluated approaches:**

| Approach | Pros | Cons | Decision |
|----------|------|------|----------|
| Simple getter behind `#ifdef CONFIG_ZTEST` | Minimal change, clear intent, compiler strips it | Adds 3-5 lines per module | **Selected** |
| Test-only accessor header (`*_test.h`) with `extern` | No production code change | Violates `static` contract, fragile | Rejected |
| Weak symbols | Clever | Obscure, hard to maintain | Rejected |
| Linker section tricks | Zero production change | Non-portable, maintenance burden | Rejected |
| Remove `static` entirely | Simplest | Breaks encapsulation for all code | Rejected |

**Implementation -- add to `alpha_state_machine.c`:**

```c
/* At the bottom of alpha_state_machine.c, after all other functions */

#ifdef CONFIG_ZTEST
#include "alpha_state_machine.h"

alpha_state_t alpha_get_state(void)
{
    return _state;
}

void alpha_set_bio_config(bio_config_t *cfg)
{
    memcpy(&_biometric_config, cfg, sizeof(bio_config_t));
}
#endif /* CONFIG_ZTEST */
```

**Implementation -- add to `motion_state_machine.c`:**

```c
#ifdef CONFIG_ZTEST
motion_state_t motion_get_state(void)
{
    return _motion_state;
}
#endif /* CONFIG_ZTEST */
```

**Implementation -- add to `alpha_state_machine.h`:**

```c
#ifdef CONFIG_ZTEST
/* Test-only accessors. Not available in production builds. */
typedef enum alpha_state {
    off_body_e,
    low_heat_risk_e,
    increased_heat_risk_e,
    heat_emergency_e,
    off_body_validation_e,
} alpha_state_t;

typedef struct __attribute__((packed)) bio_config {
    union {
        struct {
            uint16_t force_checkin : 1;
            uint16_t reserved      : 15;
        } bits;
        uint16_t value;
    } flags;
    uint8_t low_risk_report_pd;
    uint8_t inc_risk_hsi_threshold;
    uint8_t inc_risk_report_pd;
    uint8_t emer_hsi_threshold;
    uint8_t emer_report_pd;
} bio_config_t;

alpha_state_t alpha_get_state(void);
void alpha_set_bio_config(bio_config_t *cfg);
#endif /* CONFIG_ZTEST */
```

**Implementation -- add to `motion_state_machine.h`:**

```c
#ifdef CONFIG_ZTEST
typedef enum {
    motion_is_stopped,
    motion_window_open,
    motion_in_motion
} motion_state_t;

motion_state_t motion_get_state(void);
#endif /* CONFIG_ZTEST */
```

**Total production code changes:**

| File | Change | Lines |
|------|--------|-------|
| `alpha_state_machine.c` | Add `#ifdef CONFIG_ZTEST` block at bottom | ~10 |
| `alpha_state_machine.h` | Add `#ifdef CONFIG_ZTEST` type exports + getter decl | ~20 |
| `motion_state_machine.c` | Add `#ifdef CONFIG_ZTEST` block at bottom | ~5 |
| `motion_state_machine.h` | Add `#ifdef CONFIG_ZTEST` type export + getter decl | ~8 |

**Total: ~43 lines across 4 files.** All behind `#ifdef CONFIG_ZTEST` -- zero impact on production builds.

Note: The type definitions (`alpha_state_t`, `bio_config_t`, `motion_state_t`) are currently defined inside the `.c` files as file-scope types. The `#ifdef CONFIG_ZTEST` blocks in the headers duplicate these definitions for test code. This is intentional -- it avoids moving the type definitions out of the `.c` files (which would be a larger refactor). If a future refactor moves these types to the headers anyway, the `#ifdef` blocks can be simplified to just the function declarations.

### 4.3 Test Build Configuration

**`alpha_fw/tests/app/CMakeLists.txt`:**

```cmake
cmake_minimum_required(VERSION 3.20.0)
find_package(Zephyr REQUIRED HINTS $ENV{ZEPHYR_BASE})
project(alpha_app_tests)

# Include app source directory for headers
target_include_directories(app PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}/../../src
)

# Link the REAL state machine code (the code under test)
target_sources(app PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}/../../src/app/alpha_state_machine.c
    ${CMAKE_CURRENT_SOURCE_DIR}/../../src/app/motion_state_machine.c
)

# Link the test stubs (replaces all other app modules)
target_sources(app PRIVATE
    src/stubs.c
    src/test_alpha_state_machine.c
    src/test_motion_state_machine.c
    src/main.c
)
```

This is the critical build trick: the CMakeLists.txt includes only the `.c` files under test (the two state machine files) and the stub file. It does NOT include `vsm_handler.c`, `sensor_handler.c`, `lights_handler.c`, etc. The linker resolves all those symbols from `stubs.c`.

**`alpha_fw/tests/app/prj.conf`:**

```kconfig
CONFIG_ZTEST=y
CONFIG_ZTEST_NEW_API=y

# Disable real drivers, enable stubs
CONFIG_CK_LSM6DSO=n
CONFIG_CK_LSM6DSO_STUB=y

# Stubs for other sensor drivers (when they exist)
# CONFIG_CK_PAH8151=n
# CONFIG_CK_PAH8151_STUB=y
# CONFIG_VSM=n
# CONFIG_VSM_STUB=y

# Zephyr core
CONFIG_LOG=y
CONFIG_LOG_DEFAULT_LEVEL=3
CONFIG_SENSOR=y

# GPIO stub for native_sim (needed for some Kconfig dependencies)
CONFIG_GPIO=y
```

Note on `CONFIG_CK_PAH8151_STUB`: The example doc (11) uses `CONFIG_PAH8151_STUB` without the `CK_` prefix. This is a known issue. When the PAH8151 stub is implemented, it must use `CONFIG_CK_PAH8151_STUB` for consistency with the `ck,` vendor prefix convention. The commented-out lines above use the correct naming.

**`alpha_fw/tests/app/boards/native_sim.overlay`:**

```dts
/ {
    lsm6dso0: lsm6dso-stub {
        compatible = "ck,lsm6dso-stub";
        status = "okay";
    };
};
```

For the initial implementation, the LSM6DSO stub is the only sensor stub needed. The state machines under test do not call the LSM6DSO driver directly -- they call `get_vsm_data()` and `has_motion_occurred()`, which are stubbed in `stubs.c`. The DTS overlay is still needed because the test build includes the stub Kconfig, and Zephyr's device model needs a matching DTS node to instantiate `DEVICE_DT_INST_DEFINE`.

**`alpha_fw/tests/app/testcase.yaml`:**

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

### 4.4 How alpha_fw Tests Discover Stubs from accel_drv

The `accel_drv` repo is a Git submodule of `alpha_fw`. When building tests:

1. `alpha_fw`'s west manifest (or Git submodule config) points to `accel_drv`
2. `accel_drv/zephyr/module.yml` registers it as a Zephyr module
3. Zephyr's build system automatically picks up:
   - `Kconfig` -- makes `CONFIG_CK_LSM6DSO_STUB` available
   - `CMakeLists.txt` -- links `lsm6dso_stub.c` when `CONFIG_CK_LSM6DSO_STUB=y`
   - `dts/bindings/` -- makes `ck,lsm6dso-stub` compatible string recognized

No explicit path configuration needed. The Zephyr module system handles it.

---

## 5. Build and Execution

### 5.1 Twister Integration

**Interface tests (accel_drv):**

```bash
# From accel_drv root:
west twister -T tests/interface/ -p native_sim
```

Twister discovers `tests/interface/testcase.yaml`, builds for `native_sim` with the stub driver, executes the native binary, and parses ztest output.

**App-level tests (alpha_fw):**

```bash
# From alpha_fw root:
west twister -T tests/app/ -p native_sim
```

Same pattern. The test's `CMakeLists.txt` selectively includes source files as described in Section 4.3.

### 5.2 Concord Build Service Flow

The build service handles two scenarios for Stage 1:

**Scenario A: Push to `accel_drv`**

```
1. Webhook fires → Concord HTTP API receives push event for accel_drv
2. HTTP API resolves pipeline config:
   a. Fetches accel_drv/.concord/pipeline.yaml at the pushed commit
   b. Evaluates on.push.branches and on.push.paths filters
3. HTTP API creates pipeline, sends BuildRequest to build service:
   a. Build "test_native" for accel_drv itself:
      → west update
      → twister -p native_sim -T tests/interface/ --outdir twister-out
   b. Cross-repo build for alpha_fw (from SubmoduleMapping):
      → git clone alpha_fw at HEAD
      → Override accel_drv submodule to point at the triggered commit
      → west update
      → twister -p native_sim -T tests/app/ --outdir twister-out
4. Build artifacts uploaded to MinIO
5. Pipeline controller creates Stage 1 K8s Job(s)
```

**Scenario B: Push to `alpha_fw`**

```
1. Webhook fires → Concord HTTP API receives push event for alpha_fw
2. HTTP API resolves pipeline config from alpha_fw/.concord/pipeline.yaml
3. BuildRequest for "test_native":
   → west update
   → twister -p native_sim -T tests/app/ --outdir twister-out
4. Artifacts to MinIO
5. Stage 1 K8s Job
```

### 5.3 Stage 1 K8s Job Spec

From [09-final-architecture.md](./09-final-architecture.md) Section 4, the Stage 1 runner:

```yaml
# K8s Job created by pipeline controller
apiVersion: batch/v1
kind: Job
metadata:
  name: pl-{pipeline_id}-software-{job_id}
  labels:
    corekinect.com/pipeline-id: "{pipeline_id}"
    corekinect.com/pipeline-stage: "software"
    corekinect.com/pipeline-stage-order: "1"
    corekinect.com/pipeline-repo: "accel_drv"
    corekinect.com/pipeline-commit: "{commit_sha}"
    corekinect.com/pipeline-trigger: "webhook"
spec:
  activeDeadlineSeconds: 600
  template:
    spec:
      nodeSelector:
        corekinect.com/role: agent
      containers:
        - name: test-runner
          image: containers.ad.corekinect.com/ncs-fw-dev:2.4.2
          env:
            - name: PIPELINE_ID
              value: "{pipeline_id}"
            - name: STAGE
              value: "software"
            - name: MINIO_URL
              value: "http://minio.concord.svc:9000"
            - name: BUILD_ARTIFACT_PATH
              value: "validation/pipelines/{pipeline_id}/stages/software/build/"
          command: ["/bin/sh", "-c"]
          args:
            - |
              # Download build artifacts from MinIO
              mc cp -r minio/$BUILD_ARTIFACT_PATH ./twister-out/
              # For pre-built approach: just check results
              # For build-in-job approach: run twister directly
              # Upload results
              mc cp twister-out/twister_report.xml minio/$BUILD_ARTIFACT_PATH/results/
              # Exit based on test results
              python3 /opt/concord/check_twister_results.py twister-out/twister_report.xml
      restartPolicy: Never
```

For Stage 1, there are two valid execution models:

1. **Build service pre-builds, Job checks results**: The build service runs Twister during the build step and uploads `twister_report.xml`. The K8s Job downloads and evaluates it. This is simpler and leverages ccache.

2. **Job builds and runs**: The K8s Job itself runs `west twister`. This is closer to how most CI systems work but loses ccache benefits.

**Recommendation: Use model 1 (build service pre-builds).** The build service already has ccache and west module caches. Running Twister there avoids duplicate work. The Stage 1 Job becomes a thin wrapper that downloads the report and exits 0 or 1.

### 5.4 Pipeline Configuration Files

**`accel_drv/.concord/pipeline.yaml`:**

```yaml
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

notifications:
  on_failure:
    slack: "#accel-driver-ci"
  on_recovery:
    slack: "#accel-driver-ci"

artifacts:
  retention_days: 90

targets:
  - board: devkit_nrf52840_lsm6dso_spi
    chip: lsm6dso
    test_mode: full
  - board: alpha_b0/nrf52840
    chip: lsm6dso
    product: alpha
    test_mode: functional
```

**`accel_drv/.concord/build.yaml`:**

```yaml
version: 1
container: containers.ad.corekinect.com/ncs-fw-dev:2.4.2

builds:
  # Interface contract tests (Stage 1a)
  test_native:
    steps:
      - west update
      - twister -p native_sim -T tests/interface/ --outdir twister-out
    artifacts:
      - twister-out/twister_report.xml
      - twister-out/

  # Hardware test firmware (Stage 2)
  test_device:
    steps:
      - west update
      - twister -p ${BOARD} --prep-artifacts-for-testing -T tests/${CHIP}/ --outdir twister-out
    artifacts:
      - twister-out/
```

**`alpha_fw/.concord/pipeline.yaml`** (relevant Stage 1 section):

```yaml
version: 1

on:
  push:
    branches: ["main", "develop"]
    paths:
      - "src/**"
      - "tests/**"
      - ".concord/**"
    ignore_paths:
      - "docs/**"

concurrency:
  group: "${{ repo }}/${{ branch }}"
  supersede: true

stages:
  - name: software
    order: 1
    type: native_sim
    testPaths: ["tests/app"]
    timeout: 600
```

**`alpha_fw/.concord/build.yaml`** (relevant Stage 1 section):

```yaml
version: 1
container: containers.ad.corekinect.com/ncs-fw-dev:2.4.2

builds:
  test_native:
    steps:
      - west update
      - twister -p native_sim -T tests/app/ --outdir twister-out
    artifacts:
      - twister-out/twister_report.xml
      - twister-out/
```

---

## 6. Interfaces

### 6.1 What Stage 1 Produces

Stage 1 generates artifacts that serve two purposes: gate the pipeline (pass/fail), and provide diagnostic data.

**Artifacts uploaded to MinIO:**

```
validation/pipelines/{pipeline_id}/stages/software/
├── accel_drv/                          # Interface tests (Stage 1a)
│   ├── twister_report.xml              # JUnit XML -- pass/fail per test case
│   ├── twister.json                    # Full Twister output (timestamps, logs)
│   └── native_sim/                     # Build output
│       └── zephyr/zephyr.exe           # Native binary (for debugging)
├── alpha_fw/                           # App-level tests (Stage 1b)
│   ├── twister_report.xml
│   ├── twister.json
│   └── native_sim/
│       └── zephyr/zephyr.exe
└── metadata.json                       # Pipeline metadata (commit, trigger, timing)
```

**Pass/fail determination:**

The pipeline controller reads `twister_report.xml` (JUnit XML format). If any `<testcase>` has a `<failure>` element, Stage 1 fails. The pipeline stops. No Stage 2 Jobs are created.

**What Stage 2+ consumes from Stage 1:**

Stage 2 does NOT consume Stage 1 artifacts. Stage 2 has its own build step that produces hardware test firmware. The only relationship is the gate: Stage 2 only runs if Stage 1 passed.

In the future, coverage data (gcov/lcov) from `native_sim` runs could be extracted and uploaded. This is not in scope for the initial implementation but the artifact structure accommodates it:

```
├── coverage/                           # Future: gcov/lcov output
│   ├── lcov.info
│   └── coverage.html
```

### 6.2 Bitbucket Commit Status

The pipeline controller reports Stage 1 results back to Bitbucket as commit statuses:

```
POST /2.0/repositories/{workspace}/{repo}/commit/{sha}/statuses/build
{
  "state": "SUCCESSFUL" | "FAILED" | "INPROGRESS",
  "key": "concord/software",
  "name": "Stage 1: Software Tests",
  "url": "https://concord.corekinect.com/pipelines/{pipeline_id}"
}
```

### 6.3 Interface Between Build Service and Twister

The build service invokes Twister as a subprocess. The interface is:

```
Input:  west twister -p native_sim -T {test_path}/ --outdir twister-out
Output: twister-out/twister_report.xml (JUnit XML)
        twister-out/twister.json (full report)
        exit code 0 (all pass) or non-zero (failures)
```

The build service captures the exit code and the XML report. Both are used:
- Exit code determines BuildStatus (SUCCEEDED/FAILED)
- XML report is uploaded to MinIO for the pipeline controller and dashboard

---

## 7. Implementation Roadmap

### Phase 0: Preparation (Week 1)

| # | Work Item | Effort | Owner | Dependencies |
|---|-----------|--------|-------|--------------|
| 0.1 | Create `validation/stage1` branch on `accel_drv` repo | 1h | Firmware | None |
| 0.2 | Audit all `#include` dependencies from `alpha_state_machine.c` and `motion_state_machine.c` | 2h | Firmware | None |
| 0.3 | Verify `native_sim` builds work with the NCS toolchain in the devcontainer | 2h | Firmware | None |
| 0.4 | Document the exact set of function signatures that `stubs.c` must implement | 2h | Firmware | 0.2 |

### Phase 1: `accel_drv` Repo Restructuring (Week 1-2)

| # | Work Item | Effort | Owner | Dependencies |
|---|-----------|--------|-------|--------------|
| 1.1 | Write fresh LSM6DSO driver in `accel_drv/drivers/lsm6dso/` (clean implementation, not a fork of upstream Zephyr or legacy `lsm6dso_drv`) | 4h | Firmware | 0.1 |
| 1.2 | Copy DTS bindings into `accel_drv/dts/bindings/` | 1h | Firmware | 0.1 |
| 1.3 | Create merged root `Kconfig` and `CMakeLists.txt` | 2h | Firmware | 1.1, 1.2 |
| 1.4 | Update `zephyr/module.yml` | 30m | Firmware | 1.3 |
| 1.5 | Verify existing `alpha_fw` build still works with `accel_drv` submodule swap | 4h | Firmware | 1.1-1.4 |
| 1.6 | Create stub binding `ck,lsm6dso-stub.yaml` | 30m | Firmware | 1.2 |
| 1.7 | Implement `lsm6dso_stub.c` and `lsm6dso_stub.h` | 4h | Firmware | 1.6 |
| 1.8 | Create `stubs/Kconfig` and `stubs/CMakeLists.txt` | 1h | Firmware | 1.7 |
| 1.9 | Verify stub builds for `native_sim`: `west build -b native_sim` with `CONFIG_CK_LSM6DSO_STUB=y` | 2h | Firmware | 1.7, 1.8 |

### Phase 2: Interface Tests (Week 2)

| # | Work Item | Effort | Owner | Dependencies |
|---|-----------|--------|-------|--------------|
| 2.1 | Create `tests/interface/` directory structure (testcase.yaml, prj.conf, overlay, CMakeLists.txt) | 1h | Firmware | 1.9 |
| 2.2 | Write interface test suite (`main.c`): accel readback, gyro readback, FIFO count, ODR set, FIFO enable/disable, motion trigger arm/disarm/fire, error injection, unsupported channel | 6h | Firmware | 2.1 |
| 2.3 | Run via Twister: `west twister -T tests/interface/ -p native_sim` | 1h | Firmware | 2.2 |
| 2.4 | Fix any build/link issues, iterate until all tests pass | 4h | Firmware | 2.3 |

### Phase 3: Alpha App-Level Test Infrastructure (Week 2-3)

| # | Work Item | Effort | Owner | Dependencies |
|---|-----------|--------|-------|--------------|
| 3.1 | Add `#ifdef CONFIG_ZTEST` accessor blocks to `alpha_state_machine.c` and `.h` | 1h | Firmware | 0.2 |
| 3.2 | Add `#ifdef CONFIG_ZTEST` accessor blocks to `motion_state_machine.c` and `.h` | 30m | Firmware | 0.2 |
| 3.3 | Create `alpha_fw/tests/app/` directory structure | 1h | Firmware | 3.1 |
| 3.4 | Write `stubs.c` with all ~15 module stubs | 6h | Firmware | 0.4 |
| 3.5 | Write `CMakeLists.txt` with selective source inclusion | 2h | Firmware | 3.4 |
| 3.6 | Write `prj.conf`, `testcase.yaml`, `native_sim.overlay` | 1h | Firmware | 3.5 |
| 3.7 | Build test: verify it compiles and links for `native_sim` | 4h | Firmware | 3.4-3.6 |
| 3.8 | Debug link errors (this is where missing stubs will surface) | 4h | Firmware | 3.7 |

### Phase 4: Alpha App-Level Tests (Week 3-4)

| # | Work Item | Effort | Owner | Dependencies |
|---|-----------|--------|-------|--------------|
| 4.1 | Write `test_alpha_state_machine.c`: initial state, on-body transition, HSI threshold transitions, hysteresis, off-body validation timer, re-touch during validation, full lifecycle, config update | 8h | Firmware | 3.8 |
| 4.2 | Write `test_motion_state_machine.c`: initial state, motion opens window, sustained motion, window timeout, stop timeout, continued motion resets timer, config update, force state, has_motion_ever_occurred | 6h | Firmware | 3.8 |
| 4.3 | Run full suite via Twister, fix timing issues (k_sleep in native_sim can behave differently) | 4h | Firmware | 4.1, 4.2 |
| 4.4 | Verify all tests pass: `west twister -T tests/app/ -p native_sim` | 2h | Firmware | 4.3 |

### Phase 5: Concord Pipeline Integration (Week 4-5)

| # | Work Item | Effort | Owner | Dependencies |
|---|-----------|--------|-------|--------------|
| 5.1 | Create `accel_drv/.concord/pipeline.yaml` and `build.yaml` | 2h | Infra | 2.4 |
| 5.2 | Create `alpha_fw/.concord/pipeline.yaml` and `build.yaml` (software stage) | 2h | Infra | 4.4 |
| 5.3 | Implement `pipeline.yaml` parsing in HTTP API trigger flow | 8h | Infra | 5.1, 5.2 |
| 5.4 | Implement build service `test_native` build type (Twister invocation) | 4h | Infra | 5.1 |
| 5.5 | Implement cross-repo build for `alpha_fw` when `accel_drv` changes (submodule override in build service) | 8h | Infra | 5.4 |
| 5.6 | Implement Stage 1 K8s Job template in pipeline controller | 4h | Infra | 5.4 |
| 5.7 | Implement Twister XML result evaluation in Stage 1 Job | 2h | Infra | 5.6 |
| 5.8 | Implement stage gate: Stage 1 pass -> create Stage 2 Jobs | 4h | Infra | 5.7 |
| 5.9 | Implement Bitbucket commit status reporting for Stage 1 | 2h | Infra | 5.7 |
| 5.10 | End-to-end test: push to `accel_drv` -> Stage 1 runs -> pass/fail reported | 4h | Infra + Firmware | 5.1-5.9 |

### Effort Summary

| Phase | Total Effort | Calendar Time |
|-------|-------------|---------------|
| Phase 0: Preparation | 7h | Week 1 |
| Phase 1: Repo restructuring | 17h | Week 1-2 |
| Phase 2: Interface tests | 12h | Week 2 |
| Phase 3: App test infra | 19.5h | Week 2-3 |
| Phase 4: App tests | 20h | Week 3-4 |
| Phase 5: Pipeline integration | 40h | Week 4-5 |
| **Total** | **~116h** | **~5 weeks** |

Note: The BOM (bom-validation-pipeline.md) allocates ~130h for Stage 1 (55h FW + 72h Infra + 3h Docs). The 14h delta accounts for cross-stage infrastructure items partially allocated to Stage 1.

Phase 3 (app test infrastructure, especially `stubs.c`) is the highest-risk item. The ~15 module dependencies will surface link errors that require iterative debugging. Budget extra time here.

---

## 8. Open Questions

### 8.1 Type Duplication in Test Headers

The `#ifdef CONFIG_ZTEST` approach duplicates `alpha_state_t`, `bio_config_t`, and `motion_state_t` definitions between the `.c` file and the `.h` file. If a developer changes the type in the `.c` but not the `.h`, the test will use the wrong definition. Mitigations:

- A build error will occur if the test uses a field that doesn't exist in the production type (mismatch on `sizeof` or field access)
- A CI pre-commit check could verify that the `#ifdef CONFIG_ZTEST` type definitions match the `.c` file definitions (simple regex or AST check)
- Long-term: if the types are moved to the header as part of a larger refactor, this duplication goes away

**Decision needed:** Accept the duplication risk for now (with the mitigation that mismatches cause compile errors in most cases), or invest in moving the types to the headers upfront?

### 8.2 Stub Completeness for `stubs.c`

The dependency audit in Section 4.1 is based on reading the current source. Transitive dependencies (headers included by headers) may surface additional symbols that need stubs. The Phase 3 effort estimate includes time for this, but the exact count is uncertain until the first successful link.

**Action:** Phase 0.2 (dependency audit) should produce the authoritative list. Run `gcc -M` or equivalent to get the full transitive include tree.

### 8.3 Timer Behavior on native_sim

The state machine tests rely on `k_timer` and `k_sleep`. On native_sim, the Zephyr kernel simulates time progression. The `tick_for_ms()` helper from the example doc uses `k_sleep(K_MSEC(100))` between ticks. This should work on native_sim, but there may be edge cases around timer precision that differ from real hardware. Tests should use tolerances (e.g., "wait at least 21 seconds for a 20-second timer") rather than exact timing.

**Action:** Verify during Phase 4 that `k_timer` callbacks fire at the expected simulated times on `native_sim`.

### 8.4 `CONFIG_CK_LSM6DSO_TRIGGER` Deferral

This Kconfig symbol does not exist yet in the LSM6DSO driver. The current driver uses a thread + GPIO callback pattern that is not gated by a `TRIGGER` Kconfig symbol. The stub implements `trigger_set` for `SENSOR_TRIG_MOTION` regardless.

**Decision:** Deferred. When the new accelerometer driver interface is designed, the trigger mechanism may be unified across chips rather than being chip-specific. The stub's trigger support is independent of this decision and works today.

### 8.5 IPC and Message Stubs

`alpha_state_machine.c` calls `send_biometric_data_msg()` which sends data over IPC to the nRF9151 coprocessor. The stub no-ops this call. Should the test verify that `send_biometric_data_msg()` was called with correct arguments?

**Options:**
- No-op stub (current approach): simplest, tests state transitions only
- Recording stub: captures the last `biometric_data_t` argument for assertion. More thorough but adds complexity to stubs.

**Recommendation:** Start with no-op. Add recording stubs as a follow-up if biometric data formatting bugs become a real failure mode.

### 8.6 Cross-Repo Build Triggering

When `accel_drv` changes, the build service needs to build `alpha_fw/tests/app/` with the new `accel_drv` version. This requires the build service to:

1. Clone `alpha_fw`
2. Override the `accel_drv` submodule to point at the triggered commit
3. Run `west update` and Twister

The submodule override mechanism (`git submodule set-url` + `git submodule update`, or west manifest override) needs to be implemented and tested. This is described in [09-final-architecture.md](./09-final-architecture.md) Section 3 (Build Service) but the exact implementation is not yet specified.

**Action:** Implement and test the submodule override mechanism in Phase 5.5. If `alpha_fw` uses west, then `west config manifest.project-filter` or manifest overrides may be cleaner than raw git submodule manipulation.

