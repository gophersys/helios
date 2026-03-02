# Stage 3 Integration Test Infrastructure -- Implementation Architecture

> The implementation blueprint for the `concord_harness` Zephyr module, the firmware
> integration contract, the Python-side transport layer, and all surrounding build and
> runtime infrastructure that makes Stage 3 integration testing work.
>
> **This is not an example.** For a worked Alpha example, see
> [10-stage3-alpha-example.md](../examples/alpha/stage3-alpha-example.md). This document defines the
> engineering design that the example depends on.

---

## 1. Scope and Goals

### 1.1 What Stage 3 Proves

Stage 3 answers the question: **do the firmware subsystems integrate correctly on real
hardware?** It sits between Stage 2 (isolated driver characterization on dev-kit
fixtures) and Stage 4 (black-box product validation against the spec sheet). Stage 3
runs instrumented firmware on the actual product board, observing and controlling
internal firmware state through a structured harness while real hardware components
interact with each other.

Concretely, Stage 3 tests verify:

- State machine transitions driven by real sensor events propagate correctly through
  the system (touch detection triggers monitoring, motion events update motion state,
  off-body validation timeout works).
- IPC between MCUs correctly serializes, transmits, deserializes, and dispatches
  messages.
- Sensor orchestration timing is correct (warm-up periods, sampling cadence, sensor
  wake/sleep coordination).
- Runtime configuration changes propagate to the subsystems that consume them.
- Power-state transitions cause the expected current draw changes (coarse system-level,
  not per-sensor isolation -- that is Stage 2).

### 1.2 The Instrumentation Problem

External interfaces (BLE, LED, button) only show final outcomes. To verify that a
state machine transitioned through the right intermediate states, or that an IPC
message was correctly parsed before being forwarded, or that sensor orchestration
happened in the right order, you need to see inside the running firmware.

Ad-hoc `printk` debugging changes timing and behavior. Parsing log strings is fragile
and couples tests to messages that change without notice. The solution:
**`concord_harness`** -- a structured instrumentation harness that provides a stable
observation and control interface, compiles out completely for production builds, and
requires minimal changes to production code.

### 1.3 Key Design Constraints

| Constraint | Implication |
|------------|-------------|
| Firmware uses file-static variables and cooperative polling | The harness cannot use extern globals. It must work through accessor functions or registration-based callbacks. |
| Firmware will evolve (event-driven, RTOS queues, etc.) | The harness framework must not be married to the current polling model. The injection pattern must be an adapter that the firmware engineer writes, not a framework assumption. |
| Production code changes must be minimized | Every hook in app code must be behind `#ifdef CONFIG_CONCORD_HARNESS` and compile to nothing in production. |
| The harness module is novel infrastructure | It does not exist yet. It must be thoroughly documented because firmware engineers will write product-specific declarations against its API. |
| First Alpha implementation by infra team | The infra team writes both the framework and the first `concord_harness.c`. Future products are owned by firmware engineers. |

---

## 2. `concord_harness` Module Architecture

### 2.1 Module Identity

- **Repository**: `concord_harness` (standalone Git repo)
- **Zephyr module type**: External module, pulled into firmware repos via west manifest
- **DTS vendor prefix**: `ck,` (CoreKinect)
- **Kconfig namespace**: `CONFIG_CONCORD_HARNESS*`
- **Product-specific code**: None. The module is entirely generic. Product-specific
  declarations live in the firmware repo's `src/concord_harness.c`.

### 2.2 Repository Layout

```
concord_harness/
  zephyr/
    module.yml                  # Zephyr module descriptor
    CMakeLists.txt              # Build system entry point
    Kconfig                     # Module Kconfig options
    include/
      concord_harness/
        concord_harness.h       # Public API: macros, emit function
        concord_harness_types.h # Internal types (registration structs)
    src/
      concord_shell.c           # Shell command handlers (get/set/inject/list)
      concord_registry.c        # Registration data structures and lookup
      concord_emit.c            # Event emission from any thread context
      concord_log_backend.c     # Optional Zephyr log backend (CONFIG_LOG_BACKEND_CONCORD)
  README.md
```

### 2.3 `module.yml`

```yaml
name: concord_harness
build:
  cmake: zephyr
  kconfig: zephyr/Kconfig
  settings:
    dts_root: .
```

### 2.4 Kconfig

```kconfig
# concord_harness/zephyr/Kconfig

menuconfig CONCORD_HARNESS
    bool "Concord test harness instrumentation"
    depends on SHELL
    depends on SHELL_BACKEND_SERIAL
    help
      Enable the Concord test harness. Registers shell commands under
      'concord' and provides CONCORD_GETTER/SETTER/INJECT/EVENT macros
      for declaring instrumentation points.

      When disabled, all macros expand to nothing and no code is generated.

if CONCORD_HARNESS

config CONCORD_HARNESS_MAX_POINTS
    int "Maximum number of harness instrumentation points"
    default 64
    help
      Maximum number of CONCORD_GETTER + CONCORD_SETTER + CONCORD_INJECT +
      CONCORD_EVENT declarations across the entire firmware. Increase if
      the firmware needs more instrumentation points.

config CONCORD_HARNESS_EVENT_QUEUE_SIZE
    int "Event emission queue depth"
    default 16
    help
      Number of events that can be buffered before the oldest is dropped.
      Events are emitted by firmware threads and consumed by the harness
      shell thread for UART output.

config CONCORD_HARNESS_THREAD_STACK_SIZE
    int "Harness thread stack size"
    default 2048

config CONCORD_HARNESS_THREAD_PRIORITY
    int "Harness thread priority (preemptible)"
    default 14
    help
      The harness thread should run at the LOWEST priority in the system,
      below all application threads, to minimize timing impact on real
      firmware behavior. Zephyr's default CONFIG_NUM_PREEMPT_PRIORITIES
      is 15 (0-14), so 14 is the lowest preemptible priority.

config LOG_BACKEND_CONCORD
    bool "Concord-prefixed log backend"
    depends on LOG
    help
      Adds a Zephyr log backend that prefixes log output with standard
      Zephyr timestamp format on UART0. This is the same UART as the
      shell, and the Python-side demuxer uses the absence of [CONCORD:]
      prefix to route these lines to the device log buffer.

      When this is disabled, standard Zephyr log output still appears on
      UART0 -- this option simply ensures the log format is consistent
      and parseable by the demuxer.

endif # CONCORD_HARNESS
```

### 2.5 CMakeLists.txt

```cmake
# concord_harness/zephyr/CMakeLists.txt

if(CONFIG_CONCORD_HARNESS)
  zephyr_include_directories(include)

  zephyr_library_named(concord_harness)
  zephyr_library_sources(
    src/concord_registry.c
    src/concord_shell.c
    src/concord_emit.c
  )

  zephyr_library_sources_ifdef(CONFIG_LOG_BACKEND_CONCORD
    src/concord_log_backend.c
  )
endif()
```

### 2.6 Macro Design

All macros are defined in `concord_harness.h`. When `CONFIG_CONCORD_HARNESS` is not
set, every macro expands to nothing -- zero code, zero data, zero overhead.

#### 2.6.1 Internal Registration Structures

```c
/* concord_harness_types.h */

#ifndef CONCORD_HARNESS_TYPES_H
#define CONCORD_HARNESS_TYPES_H

#include <stdint.h>

typedef enum {
    CONCORD_POINT_GETTER,
    CONCORD_POINT_SETTER,
    CONCORD_POINT_INJECT,
    CONCORD_POINT_EVENT,
} concord_point_type_t;

/**
 * Getter handler: called with no arguments, returns a string value.
 * The returned pointer must remain valid until the next call to ANY getter
 * (static buffers are fine -- the shell prints immediately).
 */
typedef const char *(*concord_getter_fn_t)(void);

/**
 * Setter handler: called with the value string from the shell command.
 * Returns "OK" on success, "ERR:<reason>" on failure.
 */
typedef const char *(*concord_setter_fn_t)(const char *value);

/**
 * Inject handler: identical signature to setter. The semantic difference
 * is that inject triggers a firmware-side action (posting to a queue,
 * overriding a flag, calling an API) rather than writing a config value.
 * Returns "OK" on success, "ERR:<reason>" on failure.
 */
typedef const char *(*concord_inject_fn_t)(const char *value);

typedef struct {
    const char           *name;
    concord_point_type_t  type;
    union {
        concord_getter_fn_t  getter;
        concord_setter_fn_t  setter;
        concord_inject_fn_t  inject;
        /* Events have no handler -- they are emit-only */
    } handler;
} concord_point_t;

#endif /* CONCORD_HARNESS_TYPES_H */
```

#### 2.6.2 `CONCORD_GETTER(name, body)`

Declares a read-only observation point. The `body` is the function body that returns a
`const char *`.

**Expansion when `CONFIG_CONCORD_HARNESS=y`:**

```c
#define CONCORD_GETTER(point_name, body)                                   \
    static const char *_concord_getter_##__COUNTER__(void) body            \
    static const STRUCT_SECTION_ITERABLE(concord_point,                    \
        _concord_point_##__COUNTER__) = {                                  \
        .name    = point_name,                                             \
        .type    = CONCORD_POINT_GETTER,                                   \
        .handler = { .getter = _concord_getter_##__COUNTER__ },            \
    };
```

When `CONFIG_CONCORD_HARNESS` is not set, the macro expands to nothing.

**Usage:** `CONCORD_GETTER("app.state", { return get_alpha_state_str(); })`

`STRUCT_SECTION_ITERABLE` is Zephyr's linker-section-based iteration pattern (same as
shell commands, device drivers, test suites). Each `concord_point_t` is placed in a
contiguous linker section for iteration without manual registration.

#### 2.6.3 `CONCORD_SETTER(name, body)`

Declares a writable configuration point. The `body` receives `const char *value` and
returns `const char *` (`"OK"` or `"ERR:<reason>"`).

```c
#define CONCORD_SETTER(point_name, body)                                   \
    static const char *_concord_setter_##__COUNTER__(const char *value)    \
        body                                                               \
    static const STRUCT_SECTION_ITERABLE(concord_point,                    \
        _concord_point_##__COUNTER__) = {                                  \
        .name    = point_name,                                             \
        .type    = CONCORD_POINT_SETTER,                                   \
        .handler = { .setter = _concord_setter_##__COUNTER__ },            \
    };
```

**Usage:**

```c
CONCORD_SETTER("config.low_risk_report_pd", {
    int val = atoi(value);
    if (val < 1 || val > 255) return "ERR:range";
    set_low_risk_report_period((uint8_t)val);
    return "OK";
})
```

#### 2.6.4 `CONCORD_INJECT(name, body)`

Declares an injection point. Identical signature to setter but semantically different:
inject triggers a firmware action (overriding a flag, posting to a queue, calling an
internal API). The handler is an **adapter** -- the firmware engineer writes whatever
logic is needed to translate the string argument into the firmware's internal
mechanism.

```c
#define CONCORD_INJECT(point_name, body)                                   \
    static const char *_concord_inject_##__COUNTER__(const char *value)    \
        body                                                               \
    static const STRUCT_SECTION_ITERABLE(concord_point,                    \
        _concord_point_##__COUNTER__) = {                                  \
        .name    = point_name,                                             \
        .type    = CONCORD_POINT_INJECT,                                   \
        .handler = { .inject = _concord_inject_##__COUNTER__ },            \
    };
```

The inject handler is a firmware-engineer-written adapter that bridges the shell string
to whatever internal mechanism the firmware uses (polling flag override, setter call,
`k_msgq_put`, or callback invocation). The framework is pattern-agnostic -- this is the
core flexibility that lets the harness survive firmware evolution.

**Usage (polling override -- current Alpha):**

```c
CONCORD_INJECT("sensor.motion", {
    if (strcmp(value, "start") == 0) {
        force_motion_state_machine(true);
        return "OK";
    } else if (strcmp(value, "stop") == 0) {
        force_motion_state_machine(false);
        return "OK";
    }
    return "ERR:expected start|stop";
})
```

#### 2.6.5 `CONCORD_EVENT(name)`

Declares an event emission point. Unlike getters/setters/injects, events have no
handler -- they are fire-and-forget notifications from firmware to the test. The macro
only registers the name so `concord list` can enumerate it.

```c
#define CONCORD_EVENT(point_name)                                          \
    static const STRUCT_SECTION_ITERABLE(concord_point,                    \
        _concord_point_##__COUNTER__) = {                                  \
        .name    = point_name,                                             \
        .type    = CONCORD_POINT_EVENT,                                    \
        .handler = { .getter = NULL },                                     \
    };
```

#### 2.6.6 `CONCORD_EMIT(name, value)`

Emits an event from any thread context. This is the only macro that appears in
production source files (inside `#ifdef CONFIG_CONCORD_HARNESS` guards). It is NOT a
registration macro -- it is a runtime call.

```c
#ifdef CONFIG_CONCORD_HARNESS
    /**
     * Emit an event. Safe to call from any thread, any IRQ priority.
     * Events are queued and printed by the harness thread.
     *
     * @param name   Event name (must match a CONCORD_EVENT declaration)
     * @param value  Event payload string (copied into the queue)
     */
    void concord_emit(const char *name, const char *value);

    #define CONCORD_EMIT(point_name, val)  concord_emit(point_name, val)
#else
    #define CONCORD_EMIT(point_name, val)  /* nothing */
#endif
```

**Implementation of `concord_emit()` (in `concord_emit.c`):**

```c
#include <zephyr/kernel.h>
#include <concord_harness/concord_harness.h>

#define EVT_NAME_MAX  48
#define EVT_VAL_MAX   64

struct concord_event_entry {
    char name[EVT_NAME_MAX];
    char value[EVT_VAL_MAX];
};

K_MSGQ_DEFINE(concord_event_q,
              sizeof(struct concord_event_entry),
              CONFIG_CONCORD_HARNESS_EVENT_QUEUE_SIZE,
              4);

void concord_emit(const char *name, const char *value)
{
    struct concord_event_entry entry;
    strncpy(entry.name, name, EVT_NAME_MAX - 1);
    entry.name[EVT_NAME_MAX - 1] = '\0';
    strncpy(entry.value, value ? value : "", EVT_VAL_MAX - 1);
    entry.value[EVT_VAL_MAX - 1] = '\0';

    /* Non-blocking put. If queue is full, drop the event.
     * This ensures the emitting thread (possibly time-critical app code)
     * is never blocked by harness output. */
    k_msgq_put(&concord_event_q, &entry, K_NO_WAIT);
}
```

**Thread safety**: `k_msgq_put` with `K_NO_WAIT` is safe from any context including
ISRs. The event is copied into the queue (value semantics, not pointer). The harness
thread drains the queue and prints `[CONCORD:EVT]` lines.

**Usage in production source files:**

```c
/* alpha_state_machine.c */
#include <concord_harness/concord_harness.h>  /* safe: macros expand to nothing if disabled */

    /* ... inside state transition logic ... */
    _state = low_heat_risk_e;
    CONCORD_EMIT("app.state_changed", "low_heat_risk_e");
```

When `CONFIG_CONCORD_HARNESS=n`, this line compiles to nothing. No function call, no
string literal in the binary, no overhead.

### 2.7 Shell Command Implementation

The harness registers shell commands under the `concord` root using Zephyr's standard
`SHELL_STATIC_SUBCMD_SET_CREATE` mechanism.

#### 2.7.1 Command Registration

```c
/* concord_shell.c */

#include <zephyr/shell/shell.h>
#include <concord_harness/concord_harness.h>
#include <concord_harness/concord_harness_types.h>

/* Linker-section iteration over all registered points */
STRUCT_SECTION_FOREACH_DEFINE(concord_point);

static int cmd_get(const struct shell *sh, size_t argc, char **argv);
static int cmd_set(const struct shell *sh, size_t argc, char **argv);
static int cmd_inject(const struct shell *sh, size_t argc, char **argv);
static int cmd_list(const struct shell *sh, size_t argc, char **argv);

SHELL_STATIC_SUBCMD_SET_CREATE(concord_cmds,
    SHELL_CMD_ARG(get,    NULL, "Get harness point value",
                  cmd_get,    2, 0),    /* concord get <name> */
    SHELL_CMD_ARG(set,    NULL, "Set harness point value",
                  cmd_set,    3, 0),    /* concord set <name> <value> */
    SHELL_CMD_ARG(inject, NULL, "Inject event via harness",
                  cmd_inject, 3, 0),    /* concord inject <name> <value> */
    SHELL_CMD(list, NULL, "List all registered harness points",
              cmd_list),                /* concord list */
    SHELL_SUBCMD_SET_END
);

SHELL_CMD_REGISTER(concord, &concord_cmds, "Concord test harness", NULL);
```

#### 2.7.2 Command Dispatch

All commands follow the same pattern: look up the name in the linker-section registry,
verify the point type matches the command, call the handler, format the response.

```c
static const concord_point_t *find_point(const char *name)
{
    STRUCT_SECTION_FOREACH(concord_point, p) {
        if (strcmp(p->name, name) == 0) {
            return p;
        }
    }
    return NULL;
}

static int cmd_get(const struct shell *sh, size_t argc, char **argv)
{
    const char *name = argv[1];
    const concord_point_t *p = find_point(name);

    if (!p || p->type != CONCORD_POINT_GETTER) {
        shell_print(sh, "[CONCORD:RSP] %s=ERR:not_found", name);
        return -ENOENT;
    }

    const char *val = p->handler.getter();
    shell_print(sh, "[CONCORD:RSP] %s=%s", name, val);
    return 0;
}

/* cmd_set and cmd_inject are identical to cmd_get except they pass
 * argv[2] as the value argument and check CONCORD_POINT_SETTER /
 * CONCORD_POINT_INJECT respectively. */

static int cmd_list(const struct shell *sh, size_t argc, char **argv)
{
    static const char *type_str[] = { "GET", "SET", "INJ", "EVT" };
    shell_print(sh, "[CONCORD:RSP] LIST_BEGIN");
    STRUCT_SECTION_FOREACH(concord_point, p) {
        shell_print(sh, "[CONCORD:RSP] %s %s", type_str[p->type], p->name);
    }
    shell_print(sh, "[CONCORD:RSP] LIST_END");
    return 0;
}
```

#### 2.7.3 Response Protocol

All harness responses use the `[CONCORD:RSP]` prefix. All events use `[CONCORD:EVT]`.
Everything else on UART0 is a device log line. This prefix-based protocol is
deliberately simple -- no binary framing, no escape sequences, no state machine. The
Python-side demuxer does a string prefix match on each line.

| Command | Request | Response (success) | Response (error) |
|---------|---------|-------------------|-----------------|
| get | `concord get app.state` | `[CONCORD:RSP] app.state=off_body_e` | `[CONCORD:RSP] app.state=ERR:not_found` |
| set | `concord set config.pd 5` | `[CONCORD:RSP] config.pd=OK` | `[CONCORD:RSP] config.pd=ERR:range` |
| inject | `concord inject sensor.touch detected` | `[CONCORD:RSP] sensor.touch=OK` | `[CONCORD:RSP] sensor.touch=ERR:expected detected\|removed` |
| list | `concord list` | `[CONCORD:RSP] LIST_BEGIN` ... `[CONCORD:RSP] LIST_END` | -- |
| (event) | -- (firmware-initiated) | `[CONCORD:EVT] app.state_changed=low_heat_risk_e` | -- |

### 2.8 Event Emission Thread

The harness runs a dedicated thread at the lowest preemptible priority. Its only job is
draining the event message queue and printing `[CONCORD:EVT]` lines to the shell
backend.

```c
/* concord_emit.c (continued) */

static void concord_harness_thread(void *p1, void *p2, void *p3)
{
    const struct shell *sh = shell_backend_uart_get_ptr();
    struct concord_event_entry entry;

    while (1) {
        /* Block until an event is available */
        k_msgq_get(&concord_event_q, &entry, K_FOREVER);
        shell_print(sh, "[CONCORD:EVT] %s=%s", entry.name, entry.value);
    }
}

K_THREAD_DEFINE(concord_harness_tid,
                CONFIG_CONCORD_HARNESS_THREAD_STACK_SIZE,
                concord_harness_thread, NULL, NULL, NULL,
                CONFIG_CONCORD_HARNESS_THREAD_PRIORITY, 0, 0);
```

The dedicated thread at lowest preemptible priority ensures no timing impact on
application code. `k_msgq_put` with `K_NO_WAIT` is safe from any context including ISRs.
Events may be delayed (test on *ordering*, not exact timing). If the queue overflows,
oldest events are dropped -- we never block application threads for harness output.

### 2.9 Log Backend (Optional)

When `CONFIG_LOG_BACKEND_CONCORD=y`, a custom Zephyr log backend formats log output on
UART0 in `[timestamp] <level> module: message` format. It ensures consistent timestamp
format (the demuxer relies on this), no `[CONCORD:]` prefix on log lines, and no
interference with shell command/response framing. Uses standard Zephyr
`LOG_BACKEND_DEFINE`.

---

## 3. Firmware-Side Integration Pattern

This section defines the contract that a firmware engineer follows when integrating
`concord_harness` into a product firmware. The Alpha implementation by the infra team
serves as the reference.

### 3.1 The `concord_harness.c` File

Each firmware repo contains a single file, `src/concord_harness.c`, that uses the four
macro types to declare instrumentation points. This file is the **only coupling point**
between the generic harness framework and the product-specific firmware.

**Location**: `<firmware_repo>/src/concord_harness.c`

**Compilation**: Only compiled when `CONFIG_CONCORD_HARNESS=y`. The firmware's
`src/CMakeLists.txt` includes it conditionally:

```cmake
# src/CMakeLists.txt (in firmware repo)
target_sources_ifdef(CONFIG_CONCORD_HARNESS app PRIVATE concord_harness.c)
```

**The file includes firmware headers** to access internal state. It does NOT include
implementation files or use `extern` on file-static variables.

### 3.2 Getter Pattern -- Accessor Functions, Not Extern Globals

**Problem**: The example in `10-stage3-alpha-example.md` declares `extern alpha_state_t
g_alpha_state` and 7 other extern globals. These do not exist. The firmware uses static
local variables:

```c
/* alpha_state_machine.c */
static alpha_state_t _state = off_body_e;          /* file-static, no getter */

/* motion_state_machine.c */
static motion_state_t _motion_state = motion_is_stopped;  /* file-static, no getter */
```

**Solution**: The harness calls accessor functions. Where an accessor already exists,
use it. Where one does not exist, the firmware engineer adds a minimal one behind
`#ifdef CONFIG_CONCORD_HARNESS`.

**Category 1: Accessors that already exist in the codebase.**

| Data | Existing accessor | Return type | Notes |
|------|-------------------|-------------|-------|
| VSM data (HR, SpO2, skin temp, HSI) | `get_vsm_data()` | `vsm_data_t` (copy) | Declared in `vsm_handler.h`. Returns a struct copy -- safe to call from harness thread. |
| On-body status | `is_device_on_body()` | `bool` | Declared in `vsm_handler.h`. Reads `_vsm_flags[is_on_body]`. |
| Motion occurred flag | `has_motion_occurred()` | `bool` | Declared in `sensor_handler.h`. |
| In-motion state | `is_in_motion_state()` | `bool` | Declared in `motion_state_machine.h`. Returns `_motion_state == motion_in_motion`. |
| Battery percent | `get_battery_percent()` | `uint8_t` | Declared in `sensor_handler.h`. |
| On charger | `is_on_charger()` | `bool` | Declared in `sensor_handler.h`. |
| Motion config | `get_motion_sm_config_ptr()` | `uint8_t *` | Returns pointer to `_motion_cfg`. |
| Force motion state | `force_motion_state_machine(bool)` | `void` | Declared in `motion_state_machine.h`. The existing injection point. |
| Set motion config | `set_motion_config(...)` | `void` | Declared in `motion_state_machine.h`. |

**Category 2: Accessors that need to be added (minimal, conditional).**

These are the production code changes required. Each is a 1-3 line function behind
`#ifdef CONFIG_CONCORD_HARNESS`, or preferably a small unconditional accessor that has
value beyond the harness.

| Data | Needed accessor | Where to add | Production impact |
|------|-----------------|-------------|-------------------|
| Alpha state machine state (`_state`) | `alpha_state_t get_alpha_state(void)` | `alpha_state_machine.c` / `.h` | Trivial getter. Can be unconditional -- useful for debug logging beyond harness. |
| Motion state (`_motion_state`) | `motion_state_t get_motion_state(void)` | `motion_state_machine.c` / `.h` | Trivial getter. `is_in_motion_state()` exists but only returns bool. The harness needs the enum value for three-state reporting. |
| Bio config (`_biometric_config`) | `const bio_config_t *get_bio_config(void)` | `alpha_state_machine.c` / `.h` | Returns const pointer. Needed so the harness can read config values. Alternatively, individual getters per field. |
| Bio config setter | `void set_bio_config_field(const char *field, uint8_t value)` or individual setters | `alpha_state_machine.c` / `.h` | Needed for `CONCORD_SETTER` to update config without extern access. |

**Type visibility for `alpha_state_t`:**

`alpha_state_t` is defined inside `alpha_state_machine.c` (file scope). The harness
cannot reference it. Three options, in order of preference:

1. **Move the typedef to the header** (`alpha_state_machine.h`). This is the cleanest
   option. The enum defines the product's state model -- it has value as a public
   interface for debug tooling, logging, and the harness. The header already declares
   `init_alpha_state_machine()` and `run_alpha_state_machine()`, so the state type
   belongs with them.

2. **Getter returns a string instead of the enum.** The accessor function
   `get_alpha_state_str()` returns `"off_body_e"`, `"low_heat_risk_e"`, etc. The
   harness never needs the numeric type. This avoids moving the typedef but adds a
   string conversion function to production code.

3. **Test-only header.** Create `alpha_state_machine_test.h` that is only included when
   `CONFIG_CONCORD_HARNESS=y`. This isolates the exposure but adds a file.

**Recommendation**: Option 1 (move typedef to header) for `alpha_state_t`. Option 1
for `motion_state_t` (already in the `.c` file as a typedef, move to `.h`). These are
the product's state models and should be in the public header regardless of the
harness.

**Corrected getter pattern (what `concord_harness.c` actually looks like):**

```c
/* alpha_fw/src/concord_harness.c */

#include <concord_harness/concord_harness.h>

#include "app/alpha_state_machine.h"   /* get_alpha_state(), alpha_state_t */
#include "app/motion_state_machine.h"  /* get_motion_state(), motion_state_t,
                                          force_motion_state_machine(),
                                          set_motion_config() */
#include "app/vsm_handler.h"           /* get_vsm_data(), is_device_on_body() */
#include "app/sensor_handler.h"        /* get_battery_percent(), is_on_charger(),
                                          has_motion_occurred() */

/* ---- String conversion helpers ---- */

static const char *alpha_state_to_str(alpha_state_t s)
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

static const char *motion_state_to_str(motion_state_t s)
{
    switch (s) {
    case motion_is_stopped:   return "motion_is_stopped";
    case motion_window_open:  return "motion_window_open";
    case motion_in_motion:    return "motion_in_motion";
    default:                  return "unknown";
    }
}

/* ---- Getters ---- */

CONCORD_GETTER("app.state", {
    return alpha_state_to_str(get_alpha_state());
})

CONCORD_GETTER("motion.state", {
    return motion_state_to_str(get_motion_state());
})

CONCORD_GETTER("sensor.on_body", {
    return is_device_on_body() ? "true" : "false";
})

CONCORD_GETTER("sensor.hr", {
    static char buf[16];
    vsm_data_t d = get_vsm_data();
    snprintf(buf, sizeof(buf), "%d", d.heartrate);
    return buf;
})

CONCORD_GETTER("sensor.spo2", {
    static char buf[16];
    vsm_data_t d = get_vsm_data();
    snprintf(buf, sizeof(buf), "%d", d.spo2);
    return buf;
})

CONCORD_GETTER("sensor.temp_skin", {
    static char buf[16];
    vsm_data_t d = get_vsm_data();
    int16_t raw = d.skin_temp_degC_q8p8;
    snprintf(buf, sizeof(buf), "%d.%d", raw >> 8, ((raw & 0xFF) * 10) >> 8);
    return buf;
})

CONCORD_GETTER("sensor.hsi", {
    static char buf[16];
    vsm_data_t d = get_vsm_data();
    snprintf(buf, sizeof(buf), "%u.%u",
             d.heat_strain_index_tenths / 10,
             d.heat_strain_index_tenths % 10);
    return buf;
})

CONCORD_GETTER("battery.soc", {
    static char buf[8];
    snprintf(buf, sizeof(buf), "%u", get_battery_percent());
    return buf;
})

CONCORD_GETTER("battery.charging", {
    return is_on_charger() ? "true" : "false";
})

/* ---- Setters ---- */

CONCORD_SETTER("config.motion_start_sec", {
    int val = atoi(value);
    if (val < 1 || val > 255) return "ERR:range";
    /* Use existing set_motion_config -- but it sets all three fields.
     * Read current config, update one field, write back. */
    motion_cfg_t *cfg = (motion_cfg_t *)get_motion_sm_config_ptr();
    set_motion_config((uint8_t)val, cfg->motion_window_end_sec, cfg->motion_stop_sec);
    return "OK";
})

CONCORD_SETTER("config.motion_stop_sec", {
    int val = atoi(value);
    if (val < 1 || val > 255) return "ERR:range";
    motion_cfg_t *cfg = (motion_cfg_t *)get_motion_sm_config_ptr();
    set_motion_config(cfg->motion_window_start_sec, cfg->motion_window_end_sec, (uint8_t)val);
    return "OK";
})

/* Bio config setters require new accessors -- see Section 3.2 above */

/* ---- Inject ---- */

CONCORD_INJECT("sensor.motion", {
    if (strcmp(value, "start") == 0) {
        force_motion_state_machine(true);
        return "OK";
    } else if (strcmp(value, "stop") == 0) {
        force_motion_state_machine(false);
        return "OK";
    }
    return "ERR:expected start|stop";
})

/* ---- Events ---- */

CONCORD_EVENT("app.state_changed")
CONCORD_EVENT("motion.state_changed")
CONCORD_EVENT("sensor.vitals_ready")
CONCORD_EVENT("ipc.msg_sent")
CONCORD_EVENT("alert.triggered")
```

### 3.3 Setter Pattern -- Call Configuration Update Functions

Setters call existing configuration update functions when they exist (e.g.,
`set_motion_config()`). When no function exists, the firmware engineer adds one, or
uses a pointer-based approach through an existing `get_*_config_ptr()` accessor.

**Input validation is mandatory.** The setter handler validates range, format, and
semantic constraints before applying the change. The harness framework does not
validate -- it passes the raw string through.

### 3.4 Injection Pattern -- The Adapter Design

This is the most architecturally important part of the harness. The injection handler
is a **firmware-engineer-written adapter** that translates a string command into
whatever mechanism the firmware subsystem uses.

**For the current Alpha firmware (polling-based):**

The Alpha state machine polls `is_device_on_body()` on every loop iteration
(`run_alpha_state_machine()` calls it directly). There is no event queue. To "inject" a
touch event, the harness needs to make `is_device_on_body()` return `true` on the next
poll.

Two approaches, depending on what accessors exist:

1. **Override the flag that `is_device_on_body()` reads.** `is_device_on_body()`
   returns `_vsm_flags[is_on_body]` (a static array in `vsm_handler.c`). A new
   function `force_on_body_state(bool on_body)` could be added behind
   `#ifdef CONFIG_CONCORD_HARNESS` in `vsm_handler.c` to override this flag. The next
   time the state machine polls `is_device_on_body()`, it gets the injected value.

2. **Use the existing `force_motion_state_machine()` pattern.** This function already
   exists and directly sets the internal motion state. A similar
   `force_alpha_state(alpha_state_t new_state)` could be added for the alpha state
   machine, but this is a heavier change and may skip transition logic.

**Recommended approach for Alpha's `sensor.touch` injection:**

Add a minimal conditional function in `vsm_handler.c`:

```c
/* vsm_handler.c */

#ifdef CONFIG_CONCORD_HARNESS
static bool _harness_on_body_override = false;
static bool _harness_on_body_value = false;

void concord_force_on_body(bool on_body)
{
    _harness_on_body_value = on_body;
    _harness_on_body_override = true;
}

void concord_clear_on_body_override(void)
{
    _harness_on_body_override = false;
}
#endif

bool is_device_on_body(void)
{
#ifdef CONFIG_CONCORD_HARNESS
    if (_harness_on_body_override) {
        return _harness_on_body_value;
    }
#endif
    return _vsm_flags[is_on_body];
}
```

Then in `concord_harness.c`:

```c
extern void concord_force_on_body(bool on_body);      /* only exists when harness enabled */
extern void concord_clear_on_body_override(void);

CONCORD_INJECT("sensor.touch", {
    if (strcmp(value, "detected") == 0) {
        concord_force_on_body(true);
        wakeup_app();  /* wake the app thread so it polls immediately */
        return "OK";
    } else if (strcmp(value, "removed") == 0) {
        concord_force_on_body(false);
        wakeup_app();
        return "OK";
    }
    return "ERR:expected detected|removed";
})
```

**For future event-driven firmware:**

When the firmware evolves to use Zephyr message queues, the inject handler simply posts
to the queue:

```c
/* hypothetical future concord_harness.c */
CONCORD_INJECT("sensor.touch", {
    app_event_t evt;
    if (strcmp(value, "detected") == 0) {
        evt.type = EVT_TOUCH_DETECTED;
    } else if (strcmp(value, "removed") == 0) {
        evt.type = EVT_TOUCH_REMOVED;
    } else {
        return "ERR:expected detected|removed";
    }
    k_msgq_put(&app_event_q, &evt, K_NO_WAIT);
    return "OK";
})
```

**The framework does not change.** Only the handler body changes. This is the core
flexibility.

### 3.5 Event Emission Pattern -- Where to Place `CONCORD_EMIT`

`CONCORD_EMIT` calls go directly in the production source files, at the point where the
event of interest occurs. They are always guarded by the `CONFIG_CONCORD_HARNESS` check
inside the macro itself (they expand to nothing when disabled).

**Placement guidelines:**

| Event | Where to emit | Payload |
|-------|---------------|---------|
| State transition | Immediately after `_state = new_state;` in `alpha_state_machine.c` | `alpha_state_to_str(new_state)` |
| Motion state change | After `_motion_state = new_state;` in `motion_state_machine.c` | `motion_state_to_str(new_state)` |
| Vitals ready | After `_send_bio_data = true;` (or at the point where bio data is fully populated) | `"hr:<val>,spo2:<val>,skin:<val>"` |
| IPC message sent | After the send call in the IPC handler | Message type or hex summary |
| Alert triggered | At the alert trigger point | Alert type string |

**Example placement in `alpha_state_machine.c`:**

```c
/* In run_alpha_state_machine(), after each state transition */

case off_body_e:
    if (is_device_on_body())
    {
        /* ... existing logic ... */
        _state = low_heat_risk_e;
        CONCORD_EMIT("app.state_changed", "low_heat_risk_e");
        /* ... */
    }
    break;
```

The `#include <concord_harness/concord_harness.h>` at the top of the file is safe
even when `CONFIG_CONCORD_HARNESS=n` because the header defines `CONCORD_EMIT` as
empty in that case.

### 3.6 Summary of Required Production Code Changes

| File | Change | Lines | Conditional? |
|------|--------|-------|-------------|
| `alpha_state_machine.h` | Move `alpha_state_t` typedef from `.c` to `.h` | ~8 | No (improves interface regardless) |
| `alpha_state_machine.c` | Add `get_alpha_state()` accessor | ~4 | No (useful beyond harness) |
| `alpha_state_machine.c` | Add `CONCORD_EMIT` at state transitions (5 transitions) | ~5 | Yes (compiles to nothing) |
| `alpha_state_machine.h` | Declare `get_alpha_state()` | ~1 | No |
| `motion_state_machine.c` | Move `motion_state_t` typedef from `.c` to `.h` | ~6 | No |
| `motion_state_machine.c` | Add `get_motion_state()` accessor | ~4 | No |
| `motion_state_machine.c` | Add `CONCORD_EMIT` at state transitions | ~3 | Yes |
| `motion_state_machine.h` | Declare `get_motion_state()` | ~1 | No |
| `vsm_handler.c` | Add `concord_force_on_body()` override function | ~12 | Yes (`#ifdef CONFIG_CONCORD_HARNESS`) |
| `vsm_handler.c` | Add harness check in `is_device_on_body()` | ~3 | Yes |
| `src/CMakeLists.txt` | Add conditional `concord_harness.c` source | ~1 | Yes |

**Total unconditional changes**: ~24 lines (type moves + accessors). These are
improvements to the firmware's public interface regardless of the harness.

**Total conditional changes**: ~24 lines behind `#ifdef CONFIG_CONCORD_HARNESS`. These
compile to nothing in production.

### 3.7 IPC Injection Design

The example document shows `ipc_inject_rx(buf, len)` which does not exist. The actual
IPC subsystem uses a ring buffer (`_p_rx_ring_buf`) fed by the UART ISR in
`ipc_bus_hw.c`. Direct injection into this ring buffer is the lowest-friction approach
but requires adding a test hook.

**Recommended approach:**

Add a conditional function in `ck_ipc.c` or `ipc_bus_hw.c`:

```c
/* ipc_bus_hw.c */
#ifdef CONFIG_CONCORD_HARNESS
#include <ring_buffer.h>

void concord_ipc_inject_rx(const uint8_t *data, size_t len)
{
    /* Write directly into the RX ring buffer as if the UART ISR received it */
    extern ring_buffer_t *get_rx_ring_buf_ptr(void);
    ring_buffer_t *rb = get_rx_ring_buf_ptr();
    put_bytes_to_ring_buffer(rb, data, len);
    /* Wake the IPC thread so it processes the injected data */
    extern k_tid_t ipc_tid;
    k_wakeup(ipc_tid);
}
#endif
```

This enables the `ipc.rx` inject handler in `concord_harness.c`:

```c
CONCORD_INJECT("ipc.rx", {
    uint8_t buf[128];
    int len = concord_hex_decode(value, buf, sizeof(buf));
    if (len < 0) return "ERR:hex_decode";
    concord_ipc_inject_rx(buf, len);
    return "OK";
})
```

`concord_hex_decode` is a utility provided by the `concord_harness` module (not the
firmware) -- a simple hex string to byte array converter.

---

## 4. Python-Side Transport Architecture

### 4.1 Overview

The Python-side infrastructure lives in the Concord monorepo's integration test runner.
It provides the `ctx.harness.*` and `ctx.logs.*` APIs that firmware-repo-hosted test
modules use.

```
concord/apps/validation/test-runner/src/
  integration/
    context.py              # TestContext implementation
    harness_transport.py    # UART shell command transport
    uart_demuxer.py         # Prefix-based stream splitter
    test_discovery.py       # Discovers test_*.py from build artifacts
    types.py                # HarnessEvent, PowerTrace, etc.
```

### 4.2 UART Demuxer Design

The demuxer consumes the raw UART byte stream from the MTIB V2 `UartStream` gRPC
stream and splits it into three channels based on line prefixes.

```python
# uart_demuxer.py

import asyncio
from dataclasses import dataclass, field
from collections import deque

CONCORD_RSP_PREFIX = "[CONCORD:RSP] "
CONCORD_EVT_PREFIX = "[CONCORD:EVT] "


@dataclass
class DemuxedStreams:
    """Three output channels from the UART demuxer."""
    response_queue: asyncio.Queue   # [CONCORD:RSP] lines (sans prefix)
    event_queue: asyncio.Queue      # [CONCORD:EVT] lines (sans prefix)
    log_lines: deque                # Everything else (bounded deque)
    log_event: asyncio.Event        # Signaled when a new log line arrives
    raw_lines: list = field(default_factory=list)  # Full raw UART for artifact upload


class UartDemuxer:
    """
    Splits incoming UART stream by line prefix.

    Runs as a long-lived asyncio task consuming from the MTIB UartStream.
    Each complete line (terminated by \n) is classified and routed.
    """

    def __init__(self, max_log_lines: int = 10000):
        self.streams = DemuxedStreams(
            response_queue=asyncio.Queue(),
            event_queue=asyncio.Queue(),
            log_lines=deque(maxlen=max_log_lines),
            log_event=asyncio.Event(),
        )
        self._line_buffer = bytearray()

    async def feed(self, chunk: bytes):
        """Feed raw bytes from UART. Splits into lines, classifies each."""
        self._line_buffer.extend(chunk)
        while b"\n" in self._line_buffer:
            line_bytes, self._line_buffer = self._line_buffer.split(b"\n", 1)
            line = line_bytes.decode("utf-8", errors="replace").strip()
            if not line:
                continue

            self.streams.raw_lines.append(line)

            if line.startswith(CONCORD_RSP_PREFIX):
                payload = line[len(CONCORD_RSP_PREFIX):]
                await self.streams.response_queue.put(payload)
            elif line.startswith(CONCORD_EVT_PREFIX):
                payload = line[len(CONCORD_EVT_PREFIX):]
                await self.streams.event_queue.put(payload)
            else:
                self.streams.log_lines.append(line)
                self.streams.log_event.set()
```

### 4.3 `ctx.harness.*` API Implementation

```python
# harness_transport.py

import asyncio
from typing import Optional
from .types import HarnessEvent


class HarnessTransport:
    """
    Wraps Zephyr Shell transport on UART0 for the concord_harness module.

    All public methods are async. They send a shell command string over UART
    and await the corresponding [CONCORD:RSP] line from the response queue.
    """

    def __init__(self, uart_send_fn, response_queue: asyncio.Queue,
                 event_queue: asyncio.Queue, default_timeout: float = 10.0):
        self._send = uart_send_fn          # async callable: sends bytes to UART
        self._rsp_q = response_queue       # from demuxer
        self._evt_q = event_queue          # from demuxer
        self._default_timeout = default_timeout

    async def get(self, name: str, timeout_s: Optional[float] = None) -> str:
        """
        Send `concord get <name>`, return the value string.
        Raises TimeoutError if no response within timeout.
        Raises HarnessError if response indicates ERR.
        """
        timeout = timeout_s or self._default_timeout
        await self._send(f"concord get {name}\n".encode())
        rsp = await asyncio.wait_for(self._await_response(name), timeout)
        if rsp.startswith("ERR:"):
            raise HarnessError(f"get({name}): {rsp}")
        return rsp

    async def set(self, name: str, value: str, timeout_s: Optional[float] = None) -> None:
        """
        Send `concord set <name> <value>`, verify OK response.
        Raises HarnessError on ERR response.
        """
        timeout = timeout_s or self._default_timeout
        await self._send(f"concord set {name} {value}\n".encode())
        rsp = await asyncio.wait_for(self._await_response(name), timeout)
        if rsp != "OK":
            raise HarnessError(f"set({name}, {value}): {rsp}")

    async def inject(self, name: str, value: str, timeout_s: Optional[float] = None) -> None:
        """
        Send `concord inject <name> <value>`, verify OK response.
        """
        timeout = timeout_s or self._default_timeout
        await self._send(f"concord inject {name} {value}\n".encode())
        rsp = await asyncio.wait_for(self._await_response(name), timeout)
        if rsp != "OK":
            raise HarnessError(f"inject({name}, {value}): {rsp}")

    async def wait_event(self, name: str, timeout_s: float = 30.0) -> HarnessEvent:
        """
        Wait for an [CONCORD:EVT] line matching the given event name.
        Returns HarnessEvent with .name and .value fields.

        Events that don't match the requested name are re-queued.
        """
        deadline = asyncio.get_event_loop().time() + timeout_s
        stashed = []
        try:
            while True:
                remaining = deadline - asyncio.get_event_loop().time()
                if remaining <= 0:
                    raise asyncio.TimeoutError(
                        f"wait_event({name}): no event within {timeout_s}s")
                raw = await asyncio.wait_for(self._evt_q.get(), remaining)
                evt_name, _, evt_value = raw.partition("=")
                if evt_name == name:
                    return HarnessEvent(name=evt_name, value=evt_value)
                stashed.append(raw)
        finally:
            # Re-queue non-matching events so other waiters can find them
            for item in stashed:
                await self._evt_q.put(item)

    async def list(self) -> dict:
        """
        Send `concord list`, parse the response, return dict of {name: type_str}.
        """
        await self._send(b"concord list\n")
        points = {}
        while True:
            raw = await asyncio.wait_for(self._rsp_q.get(), self._default_timeout)
            if raw == "LIST_END":
                break
            if raw == "LIST_BEGIN":
                continue
            # Format: "GET app.state" or "SET config.pd" etc.
            parts = raw.split(" ", 1)
            if len(parts) == 2:
                points[parts[1]] = parts[0]
        return points

    async def _await_response(self, expected_name: str) -> str:
        """
        Drain the response queue until we find a line starting with
        '<expected_name>='. Returns the value portion after '='.
        """
        while True:
            raw = await self._rsp_q.get()
            if raw.startswith(f"{expected_name}="):
                return raw[len(expected_name) + 1:]
            # Unexpected response line -- log warning and keep waiting
```

### 4.4 `ctx.logs.*` API Implementation

```python
# Part of context.py

class LogAccess:
    """Provides access to demuxed device log stream."""

    def __init__(self, demuxed_streams: DemuxedStreams):
        self._streams = demuxed_streams

    async def wait_for(self, pattern: str, timeout_s: float = 10.0) -> Optional[str]:
        """
        Search the device log stream for a line containing `pattern`.
        Checks already-captured lines first, then waits for new lines.
        Returns the matching line or None on timeout.
        """
        import re
        regex = re.compile(pattern)

        # Check existing lines
        for line in self._streams.log_lines:
            if regex.search(line):
                return line

        # Wait for new lines
        deadline = asyncio.get_event_loop().time() + timeout_s
        while True:
            remaining = deadline - asyncio.get_event_loop().time()
            if remaining <= 0:
                return None
            self._streams.log_event.clear()
            try:
                await asyncio.wait_for(self._streams.log_event.wait(), remaining)
            except asyncio.TimeoutError:
                return None
            # Check the newest lines
            for line in self._streams.log_lines:
                if regex.search(line):
                    return line

    def dump(self) -> list:
        """Return all captured device log lines."""
        return list(self._streams.log_lines)
```

### 4.5 `HarnessEvent` Type Definition

```python
# types.py

from dataclasses import dataclass


@dataclass
class HarnessEvent:
    """An event emitted by the firmware via CONCORD_EMIT."""
    name: str
    value: str


@dataclass
class PowerTrace:
    """Power measurement result from ctx.measure_power()."""
    avg_ua: float
    max_ua: float
    min_ua: float
    duration_s: float
    samples: list  # Raw sample data for artifact upload


class HarnessError(Exception):
    """Raised when a harness command returns an error."""
    pass
```

### 4.6 Timeout and Error Handling

| Scenario | Behavior |
|----------|----------|
| Shell command gets no `[CONCORD:RSP]` within timeout | `asyncio.TimeoutError` raised. Test fails with clear message indicating which harness command timed out. |
| Shell command returns `ERR:*` | `HarnessError` raised with the error string. Test fails with the firmware's error message. |
| `wait_event` times out | `asyncio.TimeoutError` raised. This is often a legitimate test failure (expected firmware behavior did not occur). |
| UART stream disconnects | The MTIB `UartStream` gRPC stream terminates. The demuxer task ends. All pending queue operations raise `CancelledError`. Test runner catches this and reports infrastructure failure. |
| Event queue overflow (firmware side) | Oldest events dropped silently by the firmware's `k_msgq_put` with `K_NO_WAIT`. The test may see missing events. The test should be designed to tolerate this (e.g., use `wait_event` rather than counting exact event sequences). |
| Response queue desync | If a response line arrives that does not match the expected name, `_await_response` skips it and waits for the correct one. This handles interleaved responses from concurrent test operations (though concurrent shell commands are discouraged). |

---

## 5. Build System

### 5.1 Instrumented vs. Production Build

The build service produces TWO firmware binaries from the same source tree:

| Build Variant | Kconfig Overlay | Used By | Key Differences |
|---------------|----------------|---------|----------------|
| Instrumented | `boards/alpha_b0_instrumented.conf` | Stage 3 | `CONFIG_CONCORD_HARNESS=y`, `CONFIG_SHELL=y`, `CONFIG_SHELL_BACKEND_SERIAL=y`, `CONFIG_LOG=y`, `CONFIG_LOG_BACKEND_CONCORD=y` |
| Production | (none -- base config) | Stage 4 | No shell, no harness, no harness thread. Minimum overhead. |

Both builds use the same source tree, the same `CMakeLists.txt`, the same west
manifest. The only difference is the Kconfig overlay.

### 5.2 Overlay Config File

```kconfig
# alpha_fw/boards/alpha_b0_instrumented.conf
#
# Overlay applied on top of the base prj.conf for instrumented builds.
# Enables the concord_harness module and its dependencies.

CONFIG_CONCORD_HARNESS=y

# Zephyr Shell (required by concord_harness for transport)
CONFIG_SHELL=y
CONFIG_SHELL_BACKEND_SERIAL=y
CONFIG_SHELL_PROMPT_UART="uart:~$ "

# Logging
CONFIG_LOG=y
CONFIG_LOG_BACKEND_CONCORD=y

# Ensure UART0 is available for shell (may already be default)
CONFIG_SERIAL=y
CONFIG_CONSOLE=y
CONFIG_UART_CONSOLE=y
```

### 5.3 West Manifest Integration

The firmware repo's west manifest (or `CMakeLists.txt` `ZEPHYR_EXTRA_MODULES`)
includes `concord_harness` as a module. The module is only active when
`CONFIG_CONCORD_HARNESS=y` (the `CMakeLists.txt` inside the module checks this).

**Option A -- West manifest (preferred for repos that use west):**

```yaml
# alpha_fw/west.yml (or equivalent manifest)
manifest:
  remotes:
    - name: corekinect
      url-base: https://bitbucket.org/corekinect
  projects:
    - name: concord_harness
      remote: corekinect
      path: modules/concord_harness
      revision: v1.0.0    # Pin to a stable release
```

**Option B -- CMakeLists.txt (for repos that manage modules directly):**

```cmake
# In the firmware repo's CMakeLists.txt, alongside existing ZEPHYR_EXTRA_MODULES
list(APPEND ZEPHYR_EXTRA_MODULES
  ${CMAKE_CURRENT_SOURCE_DIR}/modules/concord_harness
)
```

The build service clones or checks out the `concord_harness` module at the pinned
revision before building. This is handled by the standard west update flow or by the
build service's explicit checkout step.

### 5.4 `build.yaml` Schema

```yaml
# alpha_fw/.concord/build.yaml
version: 1

builds:
  instrumented:
    board: alpha_b0
    soc: nrf52840
    overlay_configs:
      - boards/alpha_b0_instrumented.conf
    extra_modules:
      - concord_harness
    artifacts:
      - build/integration/nrf52840/zephyr/merged.hex

  production_debug:
    board: alpha_b0
    soc: nrf52840
    artifacts:
      - build/production_debug/nrf52840/zephyr/merged.hex

  production_release:
    board: alpha_b0
    soc: nrf52840
    artifacts:
      - build/production_release/nrf52840/zephyr/merged.hex

  comms:
    board: alpha_b0_cpunet
    soc: nrf9151
    artifacts:
      - build/comms/nrf9151/zephyr/merged.hex

test_artifacts:
  - .concord/tests/integration/
  - .concord/integration_spec.yaml
```

**Field definitions:**

| Field | Description |
|-------|-------------|
| `builds.<name>.board` | Zephyr board name |
| `builds.<name>.soc` | Target SoC (for artifact path naming) |
| `builds.<name>.overlay_configs` | List of Kconfig overlay files applied on top of `prj.conf` |
| `builds.<name>.extra_modules` | Additional Zephyr modules to include (resolved by the build service from the west manifest or a known module registry) |
| `builds.<name>.artifacts` | Paths to build output files to upload to MinIO |
| `test_artifacts` | Paths to non-build files to include in the artifact bundle (test scripts, spec files) |

The `test_artifacts` field reconciles with the approach described in doc-09: the build
service includes `.concord/tests/` in the artifact bundle, and the Stage 3 test runner
downloads and dynamically imports the test modules.

### 5.5 Build Service Flow (Stage 3 Relevant)

```
1. Build service receives pipeline trigger for alpha_fw
2. Parse .concord/build.yaml
3. For each build variant:
   a. Checkout firmware source + west modules (including concord_harness at pinned rev)
   b. west build -- -b <board> -- -DOVERLAY_CONFIG=<overlay>
   c. Collect artifacts
4. Collect test_artifacts from source tree
5. Upload all to MinIO:
   validation/pipelines/{pipeline_id}/stages/build/{job_id}/
     instrumented/nrf52840/merged.hex
     production/nrf52840/merged.hex
     nrf9151/merged.hex
     tests/integration/test_state_machine.py
     tests/integration/test_vsm.py
     integration_spec.yaml
```

---

## 6. Role Definitions

### 6.1 Who Writes What

| Component | Location | Owner | Rationale |
|-----------|----------|-------|-----------|
| `concord_harness` module (macros, shell commands, event emission, log backend) | `concord_harness` repo | **Infra team** | Generic framework. Product-agnostic. Changes infrequently once stable. Requires Zephyr internals expertise (linker sections, shell subsystem, log backends). |
| `src/concord_harness.c` (product-specific declarations: getters, setters, inject handlers, event declarations) | Firmware repo | **Firmware engineer** (ideally). **Infra team** for the first Alpha implementation. | References firmware internals -- only the firmware engineer knows what to expose and how to inject. The infra team writes the first one for Alpha because no firmware engineer has done it before. This first implementation serves as the template for all future products. |
| Minimal production code changes (accessor functions, `CONCORD_EMIT` calls, type moves to headers) | Firmware repo | **Firmware engineer** | These are changes to production code. The firmware engineer must review and approve them. For the Alpha first implementation, the infra team proposes the changes via PR and the firmware engineer reviews. |
| Integration tests (Python `test_*.py` files) | Firmware repo (`.concord/tests/integration/`) | **Firmware engineer** | Product-specific tests that version with the firmware they test. The infra team writes the first Alpha test suite as an example. Future tests are the firmware engineer's responsibility. |
| `integration_spec.yaml` (power budgets, timeouts) | Firmware repo (`.concord/`) | **Firmware engineer** | They own the performance budgets for their product. |
| Test runner (UART demuxer, `ctx.harness` transport, `ctx.logs`, test discovery, artifact management) | Concord monorepo | **Infra team** | Generic infrastructure. Same for every product. |
| Build service (instrumented build support, `build.yaml` schema) | Concord monorepo | **Infra team** | Build infrastructure. |
| MTIB orchestration (node assignment, flash, power control, gRPC) | Concord monorepo | **Infra team** | Physical infrastructure management. |

### 6.2 The First Alpha Implementation (Bootstrap)

For the first Alpha implementation, the infra team does everything:

1. Writes the `concord_harness` module framework (repo, macros, shell, events).
2. Writes `alpha_fw/src/concord_harness.c` with the initial set of harness points.
3. Proposes the production code changes (accessor functions, type moves, `CONCORD_EMIT`
   calls) via PR to the firmware engineer.
4. Writes the first set of Python integration tests.
5. Writes the `build.yaml` and `integration_spec.yaml`.
6. Builds and validates the full Stage 3 pipeline end-to-end.

After this bootstrap, ownership transitions:

- **Framework changes** (new macro types, shell command protocol changes) remain with
  the infra team.
- **Harness declarations** for Alpha transfer to the Alpha firmware engineer. They add
  new getters/setters/injects/events as the firmware evolves.
- **Integration tests** transfer to the firmware engineer. They write new tests
  alongside firmware changes.
- **Production code hooks** are the firmware engineer's responsibility for all new
  additions. The infra team's initial hooks serve as the pattern.

### 6.3 Fallback Strategy

| Component | Primary Owner | Fallback | When Fallback Applies |
|-----------|---------------|----------|----------------------|
| `concord_harness` module | Infra team | -- | No fallback needed. Single ownership. |
| `src/concord_harness.c` | Firmware engineer | Infra team | If the firmware engineer is unavailable or unfamiliar with the harness. Infra team can write it by reading the firmware source. |
| Integration tests | Firmware engineer | Infra team | For the initial product implementation. Also if the firmware engineer does not write tests (infra team can write basic coverage). |
| Production code changes | Firmware engineer | Infra team (proposes PR) | Infra team should never merge production code changes without firmware engineer review. |

---

## 7. Interfaces -- Inputs and Outputs

### 7.1 Inputs (What Stage 3 Consumes)

| Input | Source | Format |
|-------|--------|--------|
| Instrumented firmware hex | Build service (MinIO) | Intel HEX (`merged.hex` with `CONFIG_CONCORD_HARNESS=y`) |
| Coprocessor firmware hex | Build service (MinIO) | Intel HEX (same binary for Stage 3 and 4) |
| Integration test modules | Build service (MinIO, from firmware repo's `.concord/tests/integration/`) | Python `test_*.py` files |
| Integration spec | Build service (MinIO, from firmware repo's `.concord/integration_spec.yaml`) | YAML |
| MTIB node assignment | Pipeline controller (K8s Job annotations) | `MTIB_HOST`, `MTIB_PORT` env vars |
| Pipeline metadata | Pipeline controller (K8s Job labels/env) | `PIPELINE_ID`, `PRODUCT`, `BOARD` env vars |

### 7.2 Outputs (What Stage 3 Produces)

| Output | Destination | Format | Description |
|--------|-------------|--------|-------------|
| `junit.xml` | MinIO (artifact upload) | JUnit XML | Standard test result format. One `<testcase>` per `test_*` function. Pass/fail with failure messages. |
| `device_logs.txt` | MinIO | Plain text | Demuxed device log lines (excludes `[CONCORD:RSP]` and `[CONCORD:EVT]` traffic). Full Zephyr log output. |
| `uart_log.txt` | MinIO | Plain text | Raw, undemuxed UART output. Includes everything: shell commands, responses, events, device logs. For debugging. |
| `harness_points.json` | MinIO | JSON | Output of `concord list` at test session start. Records all registered instrumentation points and their types. Useful for version tracking and debugging. |
| Power traces | MinIO + InfluxDB | CSV (MinIO) + time-series points (InfluxDB) | System-level current measurements during each test. Coarse validation against `integration_spec.yaml` power budgets. |
| Test metrics | InfluxDB | Time-series points | Per-test pass/fail, duration, measured values. For dashboard trending. |
| K8s Job exit code | K8s API | Exit 0 (all pass) or 1 (any fail) | Drives pipeline stage status. |

### 7.3 Artifact Path Structure in MinIO

```
validation/pipelines/{pipeline_id}/stages/integration/{job_id}/
  junit.xml
  device_logs.txt
  uart_log.txt
  harness_points.json
  power/
    test_boot_reaches_off_body.csv
    test_touch_triggers_monitoring.csv
    ...
```

---

## 8. Implementation Roadmap

Ordered work items with dependencies. Items within a phase can be parallelized.

### Phase A: `concord_harness` Module (Framework)

**Dependency**: None. Can start immediately.

| # | Work Item | Deliverable | Notes |
|---|-----------|------------|-------|
| A1 | Create `concord_harness` Git repo with Zephyr module structure | `module.yml`, `CMakeLists.txt`, `Kconfig` | Follow layout in Section 2.2. |
| A2 | Implement registration types and linker-section iteration | `concord_harness_types.h`, `concord_registry.c` | `STRUCT_SECTION_ITERABLE` pattern. |
| A3 | Implement macro definitions | `concord_harness.h` | `CONCORD_GETTER`, `CONCORD_SETTER`, `CONCORD_INJECT`, `CONCORD_EVENT`, `CONCORD_EMIT`. Verify they compile to nothing when `CONFIG_CONCORD_HARNESS=n`. |
| A4 | Implement shell commands | `concord_shell.c` | `concord get/set/inject/list`. Verify response format matches protocol spec. |
| A5 | Implement event emission | `concord_emit.c` | `concord_emit()` function, message queue, harness thread. Verify thread safety from ISR context. |
| A6 | Implement hex decode utility | `concord_utils.c` | `concord_hex_decode()` for IPC injection. |
| A7 | Optional: log backend | `concord_log_backend.c` | `CONFIG_LOG_BACKEND_CONCORD`. Can be deferred if standard Zephyr log backend output is sufficient for demuxer parsing. |
| A8 | Unit tests on `native_sim` | `tests/` in the module repo | Verify macro registration, shell command dispatch, event queue behavior. |

### Phase B: Alpha Firmware Integration (First Product)

**Dependency**: Phase A complete.

| # | Work Item | Deliverable | Notes |
|---|-----------|------------|-------|
| B1 | Move `alpha_state_t` typedef to `alpha_state_machine.h` | Header change | PR to firmware repo. Firmware engineer review required. |
| B2 | Add `get_alpha_state()` accessor to `alpha_state_machine.c/.h` | ~5 lines | Same PR as B1. |
| B3 | Move `motion_state_t` typedef to `motion_state_machine.h` | Header change | Can be same PR. |
| B4 | Add `get_motion_state()` accessor to `motion_state_machine.c/.h` | ~5 lines | Same PR. |
| B5 | Add `concord_force_on_body()` override in `vsm_handler.c` | ~15 lines (conditional) | For `sensor.touch` injection. |
| B6 | Add `concord_ipc_inject_rx()` in `ipc_bus_hw.c` | ~10 lines (conditional) | For `ipc.rx` injection. |
| B7 | Add `CONCORD_EMIT` calls at state transitions | ~10 lines across 2 files | In `alpha_state_machine.c` and `motion_state_machine.c`. |
| B8 | Write `src/concord_harness.c` | ~150 lines | All getters, setters, inject handlers, event declarations. |
| B9 | Write `boards/alpha_b0_instrumented.conf` | ~10 lines | Kconfig overlay. |
| B10 | Add `concord_harness` to west manifest / `ZEPHYR_EXTRA_MODULES` | ~3 lines | Module integration. |
| B11 | Add conditional source in `src/CMakeLists.txt` | ~1 line | `target_sources_ifdef(CONFIG_CONCORD_HARNESS ...)` |
| B12 | Build and verify: instrumented build succeeds, production build unchanged | Manual test | Verify `concord list` works on UART, verify production binary has no harness symbols. |

### Phase C: Python-Side Infrastructure

**Dependency**: Can start in parallel with Phase B. Needs Phase A protocol spec.

| # | Work Item | Deliverable | Notes |
|---|-----------|------------|-------|
| C1 | Implement `UartDemuxer` | `uart_demuxer.py` | Prefix-based stream splitting. Unit tests with synthetic UART data. |
| C2 | Implement `HarnessTransport` | `harness_transport.py` | `get/set/inject/wait_event/list`. Unit tests against mock queues. |
| C3 | Implement `LogAccess` | In `context.py` | `wait_for/dump`. |
| C4 | Implement `TestContext` | `context.py` | Wire together MTIB client, harness transport, log access, power profiler, artifact manager. |
| C5 | Implement `test_discovery.py` | Test discovery from MinIO artifacts | Dynamic import of `test_*.py` modules, `test_*` function discovery. |
| C6 | Implement test runner entry point | `integration_runner.py` | JUnit XML generation, artifact upload, InfluxDB metrics push. |
| C7 | Build runner container image | `Dockerfile` | `concord-integration-test-runner:latest`. |

### Phase D: Build Service Integration

**Dependency**: Phase B (to know the build.yaml schema).

| # | Work Item | Deliverable | Notes |
|---|-----------|------------|-------|
| D1 | Extend build service to parse `build.yaml` | Build service code change | Support `overlay_configs`, `extra_modules`, multiple build variants. |
| D2 | Extend build service to collect `test_artifacts` | Build service code change | Copy `.concord/tests/` and spec files to MinIO alongside hex files. |
| D3 | Produce both instrumented and production hex in one pipeline | Build service flow | Two `west build` invocations with different overlay configs. |

### Phase E: End-to-End Validation

**Dependency**: Phases B, C, D complete.

| # | Work Item | Deliverable | Notes |
|---|-----------|------------|-------|
| E1 | Write first Alpha integration tests | `.concord/tests/integration/test_state_machine.py` | Based on the example in doc-10 but using corrected patterns (accessor functions, not extern globals). |
| E2 | Write `integration_spec.yaml` for Alpha | `.concord/integration_spec.yaml` | Power budgets, timeouts. |
| E3 | End-to-end pipeline: webhook trigger, build both variants, flash instrumented, run tests, collect artifacts | Full pipeline validation | The first real Stage 3 run on hardware. |
| E4 | Verify production build is unchanged | Binary comparison | `CONFIG_CONCORD_HARNESS=n` build must produce identical binary to pre-harness builds (or differ only in the expected ways: module in west manifest is a no-op when disabled). |

---

## 9. Open Questions

| # | Question | Context | Impact |
|---|----------|---------|--------|
| 1 | **Should `alpha_state_t` and `motion_state_t` moves to headers be unconditional or behind `#ifdef`?** | Recommendation is unconditional (improves public interface). Firmware engineer may prefer conditional. | Affects whether the harness getter uses string-only accessors or type-aware accessors. |
| 2 | **Bio config setters: individual field setters or a generic `set_bio_config_field(name, value)` pattern?** | Currently no setter API exists for `_biometric_config`. Individual setters are cleaner but require more functions. A generic string-keyed setter is more flexible but harder to validate. | Affects number of production code changes and setter handler complexity. |
| 3 | **`CONCORD_EMIT` timestamp: should the event payload include a firmware timestamp?** | The harness thread may delay event output. If the test needs to correlate event timing with power traces or log timestamps, the firmware should include `k_uptime_get()` in the payload. | Affects event payload format and test assertion patterns. |
| 4 | **Shell command concurrency: should the test runner be allowed to send a new command before the previous response arrives?** | Current design is request-response (one command at a time). Concurrent commands could cause response queue desync. | Affects test runner implementation and error handling. Recommendation: enforce single-command-at-a-time with a lock in `HarnessTransport`. |
| 5 | **`concord_harness` module versioning: how to handle breaking changes?** | If the shell protocol or macro API changes, all firmware repos that use the module need to update. | Needs a versioning policy. Recommendation: semver the module, pin in west manifest, document migration path for breaking changes. |
| 6 | **IPC injection: should `concord_ipc_inject_rx` bypass encryption?** | The real IPC path decrypts received packets. Injected data needs to either be pre-encrypted (complex for test writers) or injected after the decryption step. | Affects where in the IPC receive path the injection hook is placed. Recommendation: inject after decryption, into the message handler dispatch layer, not the raw ring buffer. Requires a different hook point. |
| 7 | **Event emission from ISR context: is `k_msgq_put` with `K_NO_WAIT` safe from all ISR priorities?** | Zephyr's `k_msgq_put` is ISR-safe when called with `K_NO_WAIT`. Verify this is documented for all supported Zephyr versions in the NCS releases CoreKinect uses. | Affects whether `CONCORD_EMIT` can be placed in ISR handlers (e.g., sensor interrupt callbacks). |
| 8 | **UART0 conflict: does the Alpha firmware currently use UART0 for anything in production?** | The app.c has `NRF_UARTE0->TASKS_STOPRX = 1;` -- this explicitly stops UART0 RX. The instrumented build needs UART0 active for the shell. This line must be conditionally compiled out. | **Must be resolved before B12.** The instrumented build overlay must not stop UART0 RX. |
| 9 | **Harness point naming registry: should there be a machine-readable schema?** | Currently names are strings by convention (`<module>.<thing>`). A schema file (e.g., `harness_points.schema.yaml`) in the firmware repo could enable test runner pre-validation without flashing. | Nice-to-have. Can be deferred. |
| 10 | **`concord_harness` log level for harness shell output: should harness shell responses go through the Zephyr log system or directly to the shell backend?** | Current design uses `shell_print()` which goes directly to the shell backend. This avoids log-level filtering but means harness output is not captured by log backends other than the shell. | Recommendation: keep `shell_print()` for harness responses/events. Log system filtering could suppress harness output. |

---

## 10. CoreCloud Integration for End-to-End Verification

> **SDK reference:** The CoreCloud Python SDK is fully documented in
> [corecloud-library-architecture.md](./corecloud-library-architecture.md), including
> the current module inventory, public API surface, environment namespaces, and proposed
> restructuring for validation pipeline needs (FUOTA management, sessions, new message
> types).

Stage 3 integration tests verify not just that firmware state machines transition
correctly, but that the device successfully delivers messages to the CoreKinect cloud
backend. The `ctx.cloud` interface provides this end-to-end verification capability.

### 10.1 CoreCloud Client Architecture

The `ctx.cloud` interface is backed by the CoreCloud Python client library at
`libs/python/corekinect/core_cloud/`. Two interfaces are available:

| Interface | Class | Transport | Use Case |
|-----------|-------|-----------|----------|
| REST API | `CoreCloudRestInterface` | HTTPS to CoreKinect REST API | Sending config to device, reading latest messages, checking device status. Authenticated with auto-refreshing tokens. Rate-limited. |
| Direct DB | `CoreCloudDBInterface` | SQLAlchemy + SSH tunnel to PostgreSQL | Querying historical messages, waiting for message arrival with polling. Bypasses API rate limits. |

**For Stage 3, `ctx.cloud` uses `CoreCloudDBInterface` for message verification** (poll
the DB for the expected message) and `CoreCloudRestInterface` for config delivery
(push config to the device via the cloud API).

### 10.2 Initialization

The `TestContext` initializes `ctx.cloud` as a `CloudClient` instance wrapping both
interfaces, parameterized with the test device's ID and the DB environment
(`VAL_1_0`).

```python
class CloudClient:
    """Cloud message verification and config delivery for Stage 3 tests."""

    def __init__(self, device_id: int, db_env: str = "VAL_1_0"):
        self._device_id = device_id
        self._db_env = db_env
        self._rest = CoreCloudRestInterface(env_namespace=db_env)

    async def wait_for_message(self, msg_class, timeout_s=120.0, since=None,
                               poll_interval_s=5.0):
        """Poll cloud DB until a message of msg_class arrives after `since`."""
        if since is None:
            since = datetime.utcnow()
        deadline = asyncio.get_event_loop().time() + timeout_s
        while asyncio.get_event_loop().time() < deadline:
            msgs = msg_class.since_server_time(
                self._device_id, since, db_env=self._db_env)
            if msgs:
                return msgs[-1]
            await asyncio.sleep(poll_interval_s)
        raise TimeoutError(f"No {msg_class.__name__} within {timeout_s}s")

    def get_latest_message(self, msg_class):
        """Get the most recent message of msg_class from cloud DB."""
        return msg_class.last(self._device_id, db_env=self._db_env)

    def send_config(self, config_msg):
        """Send a config message to device via REST API."""
        config_msg.send_via_rest(
            device_id=self._device_id,
            env_namespace=self._db_env,
            client=self._rest,
        )
```

### 10.3 Message Verification Patterns

All verification patterns follow the same structure: record `datetime.utcnow()` before
the action, trigger the action via harness, wait for the firmware event confirming the
message was sent, then call `ctx.cloud.wait_for_message()` to verify the message arrived
in the cloud DB.

```python
# Pattern: verify position message after motion event
msg = await ctx.cloud.wait_for_message(PositionMsgV6, timeout_s=120, since=start_time)
assert msg is not None and msg.gnss_fix_ok and msg.batt_percent is not None

# Pattern: verify biometric message while on-skin
msg = await ctx.cloud.wait_for_message(BiometricDataMsg, timeout_s=120, since=start_time)
assert msg.on_body is True and msg.heart_rate > 0 and msg.spo2 is not None

# Pattern: verify boot message after power cycle
msg = await ctx.cloud.wait_for_message(BootMsgV2, timeout_s=180, since=boot_time)
assert msg is not None and msg.boot_reason is not None

# Pattern: send config via cloud and verify device applied it
ctx.cloud.send_config(GPSConfMsg(is_aiding_enabled=True))
await ctx.harness.wait_event("config.updated", timeout_s=60)
assert await ctx.harness.get("gnss.aiding_enabled") == "true"
```

### 10.4 CoreCloud Message Types Used in Stage 3

| Message Type | Class | UID | Stage 3 Usage |
|-------------|-------|-----|---------------|
| Position V6 | `PositionMsgV6` | 556 | Verify position messages contain correct GPS data, battery SoC, BMS temp, motion flag, on-charger flag, pressure altitude |
| Biometric Data | `BiometricDataMsg` | 557 | Verify biometric messages contain HR, SpO2, skin temp, HSI, on-body flag, environmental data |
| Boot V2 | `BootMsgV2` | 548 | Verify boot messages are sent on power cycle, contain correct boot reason and MCU type |
| GPS Config | `GPSConfMsg` | 524 | Send GPS configuration (aiding, PSM, accuracy targets) to device via `send_via_rest()` → `PUT /System/Devices/Configurations/Gps` |
| Network Status V4 | `NetworkStatusMsgV4` | 512 | LTE connection diagnostics — captured as artifact for failure analysis |
| Alpha HW Failure | `AlphaHwFailureMsg` | 559 | Detect hardware subsystem failures (IMU, PPG, GPS, BMS, charger, altimeter, IR, flash). Captured as diagnostic artifact |
| Device Message Log | `DeviceMessageLog` | -- | Query the full message log to verify message ordering and completeness |
| Ground Mode Config V2 | `GroundModeConfigV2` | 538 | DB reads available (`.last()`, `.since_server_time()`). **REST send deferred** — class inherits `MsgBase` not `ConfMsgBase`, so `.send_via_rest()` is not available. See Section 10.6 and [corecloud-library-architecture.md](./corecloud-library-architecture.md) Section 4.3. |
| Biometric Config | *(no Python class yet)* | 558 | **Deferred — POC scope exclusion.** See Section 10.6 |

### 10.5 Cloud Verification Timing

The end-to-end path (firmware -> IPC -> nRF9151 -> LTE-M -> backend -> PostgreSQL) adds
5-30 seconds of latency, dominated by LTE-M network attach on first connection.
**Recommended timeout: 120 seconds** for `wait_for_message`. After first connection,
subsequent messages typically arrive within 10-15 seconds.

Tests should record `datetime.utcnow()` before triggering the action, then pass that
timestamp as `since` to `wait_for_message` to avoid picking up stale messages.

### 10.6 POC Scope Exclusions — Missing CoreCloud Config Delivery

> **Full gap analysis:** See
> [corecloud-library-architecture.md](./corecloud-library-architecture.md) Sections 4.3-4.5
> for the complete missing capabilities inventory, proposed solutions, and implementation
> priority.

The following CoreCloud config delivery capabilities are required for full PRDTST coverage
but **do not yet have REST send support**. They are excluded from the proof of concept
and will be implemented in a later milestone.

**Ground Mode Config V2 (UID 538):**
- `GroundModeConfigV2` **exists** in `msg_def_v1_0.py` as a `MsgBase` subclass — DB
  reads (`.last()`, `.since_server_time()`) work today for verifying config state.
- **What's missing:** The class inherits from `MsgBase`, not `ConfMsgBase`. It has no
  `api_endpoint`, `api_field_map`, or `api_types` — so `.send_via_rest()` is unavailable.
  Only `GPSConfMsg` currently has `ConfMsgBase` inheritance with REST send capability.
- No REST endpoint is documented for Ground Mode Config delivery. The `PUT /System/Devices/
  Configurations/Gps` endpoint only handles GPS Config (UID 524). Config delivery for
  UID 538 may go through the Socket Server downlink path, but this needs confirmation
  from the CoreCloud team.
- **Impact:** Blocks 18 Config Value PRDTST tests (PRDTST-328, 330, 335, 342, 344, 347,
  352, 353, 356, 359, 364, 369, 371, 374, 387, 388, 394, 399). These tests require
  pushing config to the device and verifying behavior changes.
- **Post-POC work:** Extend `GroundModeConfigV2` to inherit from `ConfMsgBase`, add the
  REST endpoint path and field maps following the `GPSConfMsg` pattern, and implement the
  18 deferred tests.

**Biometric Config (UID 558):**
- The Confluence message spec defines: flags, low risk state report period, increased
  risk HSI threshold, increased risk state report period, emergency HSI threshold,
  emergency state report period.
- No `BiometricConfig` class exists in `msg_def_v1_0.py`.
- No REST endpoint exists for Biometric Config delivery.
- **Impact:** Blocks biometric interval configuration tests. Core biometric *data*
  verification (PRDTST-327, 379, 400) still works via `BiometricDataMsg` queries.
- **Post-POC work:** Write `BiometricConfig(ConfMsgBase)` in the Python SDK, create or
  document the REST endpoint, and implement biometric config tests.

**What the POC DOES cover:**
- All tests that verify *uplink messages* (PositionMsgV6, BiometricDataMsg, BootMsgV2) —
  these only need the existing query methods (`.last()`, `.since_server_time()`).
- GPS Config delivery via `GPSConfMsg.send_via_rest()` — this endpoint exists and works.
- AlphaHwFailureMsg (UID 559) as a diagnostic artifact.
- Full harness instrumentation for state machine, motion, sensor, and IPC verification.

---

## 11. Complete Harness Point Declarations for Alpha PRDTST Suite

This section defines ALL harness instrumentation points required to support the full
Alpha PRDTST test suite. These replace the minimal examples in Section 3 with a
comprehensive, implementable declaration set.

The harness points are grouped by firmware subsystem. Each group lists the point name,
type (GETTER/SETTER/INJECT/EVENT), the firmware accessor or mechanism it uses, and
which PRDTST tests require it.

### 11.1 App State Machine

| Point Name | Type | Firmware Accessor | PRDTST Coverage |
|-----------|------|-------------------|-----------------|
| `app.state` | GETTER | `get_alpha_state()` -> `alpha_state_t` enum | All tests (boot state verification) |
| `app.on_body` | GETTER | `is_device_on_body()` -> `bool` | PRDTST-327, 379, 400 |
| `app.heat_risk_level` | GETTER | `get_alpha_state()` mapped to risk level string | PRDTST-327, 379 |
| `app.state_changed` | EVENT | `CONCORD_EMIT` at each `_state =` assignment | All state transition tests |
| `app.off_body_timeout_sec` | GETTER | `OFF_BODY_VERIFICATION_SEC` constant or config | PRDTST-400 |

```c
/* ---- App State Machine ---- */

CONCORD_GETTER("app.state", {
    return alpha_state_to_str(get_alpha_state());
})

CONCORD_GETTER("app.on_body", {
    return is_device_on_body() ? "true" : "false";
})

CONCORD_GETTER("app.heat_risk_level", {
    alpha_state_t s = get_alpha_state();
    switch (s) {
    case off_body_e:
    case off_body_validation_e:   return "none";
    case low_heat_risk_e:         return "low";
    case increased_heat_risk_e:   return "increased";
    case heat_emergency_e:        return "emergency";
    default:                      return "unknown";
    }
})

CONCORD_EVENT("app.state_changed")
```

### 11.2 Motion Detection

| Point Name | Type | Firmware Accessor | PRDTST Coverage |
|-----------|------|-------------------|-----------------|
| `motion.state` | GETTER | `get_motion_state()` -> `motion_state_t` enum | PRDTST-324, 326, 375, 389, 393 |
| `motion.in_motion` | GETTER | `is_in_motion_state()` -> `bool` | PRDTST-326, 342, 369 |
| `motion.has_occurred` | GETTER | `has_motion_occurred()` -> `bool` | PRDTST-326, 393 |
| `motion.state_changed` | EVENT | `CONCORD_EMIT` at motion state transitions | PRDTST-324, 326, 375, 389, 393 |
| `sensor.motion` | INJECT | `force_motion_state_machine(bool)` | PRDTST-324, 326, 375, 393 |

The remaining subsystem harness points follow the same GETTER/EVENT/INJECT patterns
shown in Section 11.1. Each group's points are listed in the table below. C
implementations follow the patterns established in Section 3 (accessor-based getters,
string-returning handlers, `CONCORD_EMIT` for events).

### 11.3 Biometrics (PPG / VSM)

| Point Name | Type | Firmware Accessor | PRDTST Coverage |
|-----------|------|-------------------|-----------------|
| `sensor.on_body` | GETTER | `is_device_on_body()` -> `bool` | PRDTST-327, 379, 400 |
| `sensor.hr` | GETTER | `get_vsm_data().heartrate` | PRDTST-327 |
| `sensor.spo2` | GETTER | `get_vsm_data().spo2` | PRDTST-327 |
| `sensor.temp_skin` | GETTER | `get_vsm_data().skin_temp_degC_q8p8` (Q8.8) | PRDTST-327, 345 |
| `sensor.hsi` | GETTER | `get_vsm_data().heat_strain_index_tenths` | PRDTST-327 |
| `sensor.core_temp` | GETTER | `get_vsm_data().est_core_temp_degC_q8p8` (Q8.8) | PRDTST-327 |
| `sensor.vitals_ready` | EVENT | `CONCORD_EMIT` when bio data is fully populated | PRDTST-327, 379 |
| `sensor.touch` | INJECT | `concord_force_on_body(bool)` + `wakeup_app()` | PRDTST-327, 379, 400 |
| `vsm.power` | GETTER | `is_vsm_power_enabled()` (reads VSM enable GPIO P1.10) | PRDTST-410 |

### 11.4 Environmental Sensors (BME280, MLX90614)

| Point Name | Type | Firmware Accessor | PRDTST Coverage |
|-----------|------|-------------------|-----------------|
| `env.temperature` | GETTER | BME280 last reading (centi-degC) | PRDTST-345, 406 |
| `env.humidity` | GETTER | BME280 last reading (centi-%RH) | PRDTST-398, 405 |
| `env.pressure` | GETTER | BME280 last reading (Pa, reported as hPa) | PRDTST-329, 336, 357 |
| `env.altitude` | GETTER | Calculated from pressure (meters) | PRDTST-329, 336 |
| `env.ir_skin_temp` | GETTER | MLX90614 object temperature (centi-degC) | PRDTST-345 |

### 11.5 BMS (Battery Management System)

| Point Name | Type | Firmware Accessor | PRDTST Coverage |
|-----------|------|-------------------|-----------------|
| `battery.soc` | GETTER | `get_battery_percent()` -> `uint8_t` | PRDTST-334, 338, 350, 366, 385 |
| `battery.voltage_mv` | GETTER | `get_battery_voltage_mv()` (MAX17063) | PRDTST-361, 385, 392, 411 |
| `battery.temp_c` | GETTER | BMS board thermistor via MAX17063 | PRDTST-350, 367 |
| `battery.charging` | GETTER | `is_on_charger()` -> `bool` | PRDTST-354, 355, 368, 386, 397, 402 |
| `battery.lockout` | GETTER | BMS empty detection flag | PRDTST-354, 361, 385, 411 |
| `battery.soc_changed` | EVENT | `CONCORD_EMIT` on SoC change | PRDTST-334, 338, 366 |
| `battery.lockout_changed` | EVENT | `CONCORD_EMIT` on lockout state change | PRDTST-354, 385, 411 |

### 11.6 Charge Controller (BQ25622)

| Point Name | Type | Firmware Accessor | PRDTST Coverage |
|-----------|------|-------------------|-----------------|
| `charger.state` | GETTER | BQ25622 status register (not_charging/trickle/fast_cc/fast_cv/done/fault) | PRDTST-332, 339, 351, 365, 370, 372, 383, 390, 391, 392, 409 |
| `charger.temp_c` | GETTER | BQ25622 TS pin temperature | PRDTST-332, 339, 351, 372, 383, 390, 407, 409 |
| `charger.current_ma` | GETTER | BQ25622 charge current register | PRDTST-365, 370, 391, 392 |
| `charger.state_changed` | EVENT | `CONCORD_EMIT` on charge state transition | PRDTST-354, 365, 391 |

### 11.7 GNSS

| Point Name | Type | Firmware Accessor | PRDTST Coverage |
|-----------|------|-------------------|-----------------|
| `gnss.state` | GETTER | GPS handler state (off/searching/fix_acquired) | PRDTST-333, 343, 358, 360, 378, 384, 396 |
| `gnss.fix_valid` | GETTER | Whether current fix is valid | PRDTST-343, 360, 378, 384, 396 |
| `gnss.accuracy_m` | GETTER | Horizontal accuracy in meters | PRDTST-343, 360, 378, 384, 396 |
| `gnss.num_sats` | GETTER | Number of satellites in fix | PRDTST-343 |
| `gnss.latitude` | GETTER | Latitude (1e-7 degrees, printed as decimal) | PRDTST-333, 343, 358 |
| `gnss.longitude` | GETTER | Longitude (1e-7 degrees, printed as decimal) | PRDTST-333, 343, 358 |
| `gnss.speed_mps` | GETTER | Ground speed in m/s | PRDTST-358 |
| `gnss.heading_deg` | GETTER | Heading in degrees | PRDTST-333 |
| `gnss.aiding_enabled` | GETTER | Whether A-GNSS aiding is enabled | PRDTST-378, 396 |
| `gnss.on_time_s` | GETTER | GNSS active time in seconds | PRDTST-343, 384 |
| `gnss.fix_acquired` | EVENT | `CONCORD_EMIT` when fix acquired | PRDTST-343, 360, 378, 384, 396 |

### 11.8 Configuration (Heartbeat, Motion, Acquisition)

| Point Name | Type | Firmware Accessor | PRDTST Coverage |
|-----------|------|-------------------|-----------------|
| `config.heartbeat_period_s` | GETTER / SETTER | Heartbeat period in seconds (0 = disabled, 2-byte value) | PRDTST-335, 344, 352, 356, 371 |
| `config.heartbeat_acq_timeout_s` | GETTER / SETTER | Heartbeat GPS acquisition timeout in seconds | PRDTST-330, 359 |
| `config.cont_motion_period_s` | GETTER / SETTER | Continuous motion period in seconds (0 = disabled) | PRDTST-342, 364, 369, 387, 394 |
| `config.stop_motion_timeout_s` | GETTER / SETTER | Stop motion timeout in seconds | PRDTST-347, 399 |
| `config.stop_motion_acq_timeout_s` | GETTER / SETTER | Motion stop GPS acquisition timeout | PRDTST-328 |
| `config.motion_start_sec` | GETTER / SETTER | Motion start window in seconds | PRDTST-353, 393 |
| `config.motion_stop_sec` | GETTER / SETTER | `set_motion_config()` | PRDTST-347, 399 |
| `config.low_risk_report_pd` | GETTER / SETTER | Low-risk biometric report period (from `bio_config_t`) | State machine tests |
| `config.inc_risk_hsi_threshold` | GETTER / SETTER | Increased-risk HSI threshold (from `bio_config_t`) | State machine tests |
| `config.updated` | EVENT | `CONCORD_EMIT` when config is received and applied | PRDTST-374, 388 |

Config GETTER/SETTER points follow a uniform pattern: the getter calls
`get_<config>()` and formats as a string; the setter calls `atoi(value)`, validates
range (0-65535 for 16-bit values, 1-255 for 8-bit motion config), calls
`set_<config>()`, and returns `"OK"` or `"ERR:range"`. The `config.motion_start_sec`
and `config.motion_stop_sec` setters use the existing `set_motion_config()` function
(read-modify-write pattern via `get_motion_sm_config_ptr()`).

```c
/* Representative config pair — all others follow this pattern */
CONCORD_GETTER("config.heartbeat_period_s", {
    static char buf[16];
    snprintf(buf, sizeof(buf), "%u", get_heartbeat_period_sec());
    return buf;
})
CONCORD_SETTER("config.heartbeat_period_s", {
    int val = atoi(value);
    if (val < 0 || val > 65535) return "ERR:range";
    set_heartbeat_period_sec((uint16_t)val);
    return "OK";
})

CONCORD_EVENT("config.updated")
```

### 11.9 Messages (IPC / Cloud)

| Point Name | Type | Firmware Accessor | PRDTST Coverage |
|-----------|------|-------------------|-----------------|
| `ipc.last_msg_age_ms` | GETTER | Time since last IPC message received | All IPC-dependent tests |
| `ipc.msg_sent` | EVENT | `CONCORD_EMIT` when IPC message sent to nRF9151 | PRDTST-327, 366, 374, 379 |
| `ipc.rx` | INJECT | `concord_ipc_inject_rx()` | IPC round-trip tests |
| `msg.position_sent` | EVENT | `CONCORD_EMIT` when position message queued for send | PRDTST-326, 342, 352, 379 |
| `msg.biometric_sent` | EVENT | `CONCORD_EMIT` when biometric message queued for send | PRDTST-327 |
| `msg.boot_sent` | EVENT | `CONCORD_EMIT` when boot message queued for send | PRDTST-374 |
| `msg.config_sent` | EVENT | `CONCORD_EMIT` when ground mode config message queued | PRDTST-374, 388 |
| `msg.sos_sent` | EVENT | `CONCORD_EMIT` when SOS emergency message queued | PRDTST-382 |

The `ipc.rx` inject handler uses `concord_hex_decode()` (provided by the harness
module) to convert hex string to bytes, then calls `concord_ipc_inject_rx()` to deliver
into the IPC receive path. See Section 3.7 for the inject design.

### 11.10 Button / LED / Haptic

| Point Name | Type | Firmware Accessor | PRDTST Coverage |
|-----------|------|-------------------|-----------------|
| `button.state` | GETTER | Current button GPIO state (P0.12, active low) | PRDTST-325, 338, 346, 377, 382, 395, 403, 408, 412 |
| `button.press` | INJECT | Simulate button press via MTIB GPIO or software | PRDTST-325, 338, 346, 377, 382, 395, 403, 408, 412 |
| `button.pressed` | EVENT | `CONCORD_EMIT` on button press detection | PRDTST-325, 382, 412 |
| `led.pattern` | GETTER | Current LED pattern (off, red, green, blue, ...) | PRDTST-338, 355, 373 |
| `led.pattern_changed` | EVENT | `CONCORD_EMIT` on LED pattern change | PRDTST-338, 355, 373 |
| `haptic.active` | GETTER | Whether haptic motor is currently active | PRDTST-362, 380, 395, 403, 408 |
| `haptic.activated` | EVENT | `CONCORD_EMIT` when haptic motor fires | PRDTST-362, 380, 395, 403, 408 |

**Note on button press injection:** For Stage 3, button presses should prefer MTIB GPIO
control (`ctx.mtib.gpio_set()`) over software injection, because the real button GPIO
path (including debounce logic and ISR) is part of the integration test. The
`button.press` inject point is provided as a fallback.

### 11.11 VSM Power Switch

| Point Name | Type | Firmware Accessor | PRDTST Coverage |
|-----------|------|-------------------|-----------------|
| `vsm.power` | GETTER | VSM enable pin state (P1.10, active high) | PRDTST-410 |
| `vsm.power_set` | INJECT | Override VSM power pin (`on`/`off`) | PRDTST-410 |

### 11.12 Harness Point Summary

Total harness points required for Alpha PRDTST coverage:

| Type | Count | Names |
|------|-------|-------|
| GETTER | 47 | `app.state`, `app.on_body`, `app.heat_risk_level`, `motion.state`, `motion.in_motion`, `motion.has_occurred`, `sensor.on_body`, `sensor.hr`, `sensor.spo2`, `sensor.temp_skin`, `sensor.hsi`, `sensor.core_temp`, `vsm.power`, `env.temperature`, `env.humidity`, `env.pressure`, `env.altitude`, `env.ir_skin_temp`, `battery.soc`, `battery.voltage_mv`, `battery.temp_c`, `battery.charging`, `battery.lockout`, `charger.state`, `charger.temp_c`, `charger.current_ma`, `gnss.state`, `gnss.fix_valid`, `gnss.accuracy_m`, `gnss.num_sats`, `gnss.latitude`, `gnss.longitude`, `gnss.speed_mps`, `gnss.heading_deg`, `gnss.aiding_enabled`, `gnss.on_time_s`, `config.heartbeat_period_s`, `config.heartbeat_acq_timeout_s`, `config.cont_motion_period_s`, `config.stop_motion_timeout_s`, `config.stop_motion_acq_timeout_s`, `config.motion_start_sec`, `config.motion_stop_sec`, `ipc.last_msg_age_ms`, `button.state`, `led.pattern`, `haptic.active` |
| SETTER | 9 | `config.heartbeat_period_s`, `config.heartbeat_acq_timeout_s`, `config.cont_motion_period_s`, `config.stop_motion_timeout_s`, `config.stop_motion_acq_timeout_s`, `config.motion_start_sec`, `config.motion_stop_sec`, `config.low_risk_report_pd`, `config.inc_risk_hsi_threshold` |
| INJECT | 5 | `sensor.touch`, `sensor.motion`, `ipc.rx`, `button.press`, `vsm.power_set` |
| EVENT | 17 | `app.state_changed`, `motion.state_changed`, `sensor.vitals_ready`, `battery.soc_changed`, `battery.lockout_changed`, `charger.state_changed`, `gnss.fix_acquired`, `config.updated`, `ipc.msg_sent`, `msg.position_sent`, `msg.biometric_sent`, `msg.boot_sent`, `msg.config_sent`, `msg.sos_sent`, `button.pressed`, `led.pattern_changed`, `haptic.activated` |
| **Total** | **78** | (exceeds `CONCORD_HARNESS_MAX_POINTS` default of 64; set to 96 in Alpha overlay) |

**Note**: `CONCORD_HARNESS_MAX_POINTS` must be set to 96 in the Alpha
instrumented build overlay (76 actual points + 20 headroom for future additions).

---

## 12. PRDTST-to-Stage 3 Test Mapping

This section maps every Alpha PRDTST test case to its Stage 3 and Stage 4 coverage.
Stage 3 tests use the instrumented harness to verify firmware integration behavior.
Stage 4 tests are black-box product validation using production firmware.

Some tests are **Stage 4 only** -- they require physical stimulus (temperature chambers,
charger hardware, long-duration current measurement, NFC readers, FUOTA infrastructure)
that Stage 3's software harness cannot replace. These are clearly marked.

### 12.1 PRDTST Mapping Table

#### Power / Runtime (7 tests)

| PRDTST | Test Name | Stage 3? | Stage 4? | Harness Points | CoreCloud? | Notes |
|--------|-----------|----------|----------|----------------|------------|-------|
| PRDTST-331 | Sleep Current Average (1.5mA) | No | Yes | -- | No | Requires 12h-1wk current measurement. Stage 4 weekly. |
| PRDTST-340 | 3-Day Worst-Case Operation | No | Yes | -- | No | 72-hour endurance test. Stage 4 weekly. |
| PRDTST-341 | Active Mode < 150mA | Partial | Yes | `app.state` | No | Stage 3 can verify coarse system power via `ctx.mtib.power_measure()` but not sustained active mode profile. |
| PRDTST-348 | Sleep Mode < 500uA | Partial | Yes | `app.state` | No | Stage 3 verifies off-body power drop. Stage 4 measures exact budget. |
| PRDTST-361 | Lockout Mode < 400nA | No | Yes | -- | No | Requires nA-resolution current measurement. Stage 4 only. |
| PRDTST-363 | 3-Day Normal Use | No | Yes | -- | No | 72-hour endurance test. Stage 4 weekly. |
| PRDTST-404 | Normal Use < 50mA (10 min) | Partial | Yes | `app.state`, `sensor.on_body` | No | Stage 3 can measure 10-min power during on-body monitoring. |

#### Config Values (18 tests)

| PRDTST | Test Name | Stage 3? | Stage 4? | Harness Points | CoreCloud? | Notes |
|--------|-----------|----------|----------|----------------|------------|-------|
| PRDTST-328 | Motion Stop Acq Timeout Default | Yes | Yes | `config.stop_motion_acq_timeout_s` | Yes | Verify default = expected, verify GPS runs for that duration on motion stop. |
| PRDTST-330 | Heartbeat Acq Timeout Default (60s) | Yes | Yes | `config.heartbeat_acq_timeout_s` | Yes | Verify default = 60, verify GPS runs for 60s on heartbeat. |
| PRDTST-335 | Zero Heartbeat Period | Yes | Yes | `config.heartbeat_period_s` | Yes | Set to 0 via harness, verify no heartbeat messages sent to cloud. |
| PRDTST-342 | Continuous Motion Period Default | Yes | Yes | `config.cont_motion_period_s`, `motion.state` | Yes | Verify default value, inject motion, verify position message timing. |
| PRDTST-344 | Heartbeat Period Max Value | Yes | Yes | `config.heartbeat_period_s` | Yes | Set to 65535 (2-byte max), verify accepted. |
| PRDTST-347 | Stop Motion Timeout Non-Default | Yes | Yes | `config.stop_motion_timeout_s` | Yes | Set non-default, inject motion stop, verify timeout. |
| PRDTST-352 | Heartbeat Period Default | Yes | Yes | `config.heartbeat_period_s` | Yes | Verify default value, verify heartbeat position message arrives at expected interval. |
| PRDTST-353 | Motion Start Window Default (3s) | Yes | Yes | `config.motion_start_sec` | No | Verify default = 3. |
| PRDTST-356 | Heartbeat Period Non-Default | Yes | Yes | `config.heartbeat_period_s` | Yes | Set non-default via harness, verify position messages at new interval. |
| PRDTST-359 | Heartbeat Acq Timeout Non-Default | Yes | Yes | `config.heartbeat_acq_timeout_s` | Yes | Set non-default, verify GPS on-time matches. |
| PRDTST-364 | Continuous Motion Disabled | Yes | Yes | `config.cont_motion_period_s` | Yes | Set to 0, inject continuous motion, verify no continuous motion messages. |
| PRDTST-369 | Continuous Motion Period Non-Default | Yes | Yes | `config.cont_motion_period_s` | Yes | Set non-default, verify timing. |
| PRDTST-371 | Heartbeat Period Min Value | Yes | Yes | `config.heartbeat_period_s` | Yes | Set to minimum, verify accepted. |
| PRDTST-374 | Ground Mode Config Sent on Boot | Yes | Yes | `msg.config_sent`, `msg.boot_sent` | Yes | Power cycle, verify boot message + ground mode config message arrive in cloud. |
| PRDTST-387 | Continuous Motion Period Min (1s) | Yes | Yes | `config.cont_motion_period_s` | No | Set to 1, verify accepted (behavior undefined per PRDTST note). |
| PRDTST-388 | Default Ground Mode Config Values | Yes | Yes | `config.*` (all config getters) | Yes | Fresh boot, read all config values via harness, verify defaults, verify cloud receives matching config. |
| PRDTST-394 | Continuous Motion Period Max (65535s) | Yes | Yes | `config.cont_motion_period_s` | No | Set to 65535, verify accepted. |
| PRDTST-399 | Stop Motion Timeout Default (2 min) | Yes | Yes | `config.stop_motion_timeout_s` | No | Verify default = 120s. |

#### Motion Detection (5 tests)

| PRDTST | Test Name | Stage 3? | Stage 4? | Harness Points | CoreCloud? | Notes |
|--------|-----------|----------|----------|----------------|------------|-------|
| PRDTST-324 | Ignore Motion Below Accel Threshold | Partial | Yes | `motion.state`, `motion.state_changed` | No | Stage 3 verifies state machine does not transition. Stage 4 uses physical motion stage for precise acceleration. |
| PRDTST-326 | Detect Motion Above Thresholds (Default) | Yes | Yes | `motion.state`, `motion.state_changed`, `sensor.motion` | Yes | Inject motion, verify state transition, verify position message sent. |
| PRDTST-375 | Ignore Motion Below Duration Threshold | Partial | Yes | `motion.state`, `motion.state_changed` | No | Stage 3 verifies timing logic via inject. Stage 4 uses physical stimulus. |
| PRDTST-389 | Axis Independence | No | Yes | -- | No | Requires physical 3-axis motion stage. Stage 4 only. |
| PRDTST-393 | Respect Motion Start Window | Yes | Yes | `motion.state`, `config.motion_start_sec`, `sensor.motion` | No | Set start window, inject motion before window elapses, verify no transition. |

#### Charging / BMS (29 tests)

**Stage 3 (full or partial: 12 tests):**

| PRDTST | Test Name | Stage 3? | Harness Points | CoreCloud? | Notes |
|--------|-----------|----------|----------------|------------|-------|
| PRDTST-334 | SoC Reporting Accuracy (+-2%) | Partial | `battery.soc` | No | Stage 3 reads SoC. Stage 4 compares to external reference. |
| PRDTST-338 | LED Battery Level on Button Press | Yes | `battery.soc`, `led.pattern`, `button.press`, `led.pattern_changed` | No | Inject button press, verify LED pattern matches SoC range. |
| PRDTST-350 | Battery Temp in Position Message | Yes | `battery.temp_c`, `msg.position_sent` | Yes | Verify position message in cloud contains battery temperature. |
| PRDTST-354 | Charger Delatches from Lockout | Partial | `battery.lockout`, `battery.charging`, `battery.lockout_changed` | No | Stage 3 observes lockout state. Stage 4 uses charger relay. |
| PRDTST-355 | On-Charger LED State | Partial | `battery.charging`, `led.pattern`, `led.pattern_changed` | No | Stage 3 verifies LED pattern logic. Stage 4 physically connects charger. |
| PRDTST-366 | BMS SoC and Temp in Position Message | Yes | `battery.soc`, `battery.temp_c`, `sensor.on_body`, `msg.position_sent` | Yes | Verify position message has SoC + temp. |
| PRDTST-368 | On-Charger in Position Message | Yes | `battery.charging`, `msg.position_sent` | Yes | Verify position message on-charger flag. |
| PRDTST-373 | LED Charge Level While Charging | Partial | `battery.charging`, `battery.soc`, `led.pattern` | No | Stage 3 verifies LED mapping. Stage 4 verifies physical LEDs. |
| PRDTST-381 | BMS Parameter Retention | Yes | `battery.soc`, `battery.voltage_mv` | No | Power cycle via MTIB, verify BMS parameters persist. |
| PRDTST-385 | Battery Lockout at 3.5V | Partial | `battery.voltage_mv`, `battery.lockout`, `battery.lockout_changed` | No | Stage 3 monitors lockout state. Stage 4 drains battery to threshold. |
| PRDTST-411 | BMS Recovery Voltage (3.88V) | Partial | `battery.voltage_mv`, `battery.lockout` | No | Stage 3 observes flag. Stage 4 controls voltage precisely. |
| PRDTST-412 | Button Press Check Battery Status | Yes | `button.press`, `led.pattern`, `led.pattern_changed`, `battery.soc` | No | Press button via MTIB GPIO, verify LED response. |

**Stage 4 only (17 tests):**

| PRDTST | Test Name | Reason |
|--------|-----------|--------|
| PRDTST-332 | TS Pin Short Circuit Start Charging | Physical TS pin manipulation |
| PRDTST-339 | TS Pin Short Circuit While Charging | Physical TS pin manipulation |
| PRDTST-349 | No FUOTA on Low Battery (3.7V) | FUOTA infrastructure + controlled voltage |
| PRDTST-351 | No Charge Below 0C | Peltier temperature controller |
| PRDTST-365 | Charge Using Charge Ladder | Full charge cycle monitoring |
| PRDTST-367 | BMS Temp Accuracy (+-2C) | Calibrated reference thermometer |
| PRDTST-370 | Charge 3.5V to 4.2V in < 3 Hours | Full charge cycle timing |
| PRDTST-372 | No Charge Above 45C | Peltier temperature controller |
| PRDTST-383 | No Charge Below 10C | Temperature controller |
| PRDTST-386 | Detect Charger Low Battery Not Charging | Physical charger at low battery |
| PRDTST-390 | TS Pin Open Circuit Start Charging | Physical TS pin manipulation |
| PRDTST-391 | Stop Charging at 4.3V / 10mA Termination | Full charge cycle monitoring |
| PRDTST-392 | Trickle Charge Below 3.5V | Controlled battery voltage + current measurement |
| PRDTST-397 | Detect Charger Full Battery | Physical charger at full battery |
| PRDTST-402 | Detect Charger Low Battery | Physical charger across voltage range |
| PRDTST-407 | Charger Controller Temp Accuracy (+-2C) | Calibrated reference |
| PRDTST-409 | TS Pin Open Circuit While Charging | Physical TS pin manipulation |

#### Environmental Sensors (7 tests)

| PRDTST | Test Name | Stage 3? | Stage 4? | Harness Points | CoreCloud? | Notes |
|--------|-----------|----------|----------|----------------|------------|-------|
| PRDTST-329 | Altitude Ceiling (+-25m / +-1.0 hPa) | Partial | Yes | `env.pressure`, `env.altitude` | No | Stage 3 reads sensor values. Stage 4 compares to calibrated reference. |
| PRDTST-336 | Detect 3m Elevation Change | Partial | Yes | `env.altitude`, `env.pressure` | No | Stage 3 verifies sensor reads. Stage 4 uses pressure chamber. |
| PRDTST-345 | Absolute Temp Accuracy (+-0.5C) | Partial | Yes | `env.temperature`, `env.ir_skin_temp` | No | Stage 3 reads sensors. Stage 4 compares to calibrated thermometer. |
| PRDTST-357 | Absolute Pressure (+-0.05 inHg / +-1.7 hPa) | Partial | Yes | `env.pressure` | No | Stage 3 verifies plausible readings. Stage 4 compares to calibrated barometer. |
| PRDTST-398 | Absolute Humidity (+-3%RH) | Partial | Yes | `env.humidity` | No | Stage 3 verifies plausible readings. Stage 4 compares to calibrated hygrometer. |
| PRDTST-405 | Detect 5% Humidity Change | Partial | Yes | `env.humidity` | No | Stage 3 verifies sensor responsiveness. Stage 4 uses humidity chamber. |
| PRDTST-406 | Detect 0.1C Temp Change | Partial | Yes | `env.temperature` | No | Stage 3 verifies sensor resolution. Stage 4 uses temperature chamber. |

#### GNSS (7 tests)

| PRDTST | Test Name | Stage 3? | Stage 4? | Harness Points | CoreCloud? | Notes |
|--------|-----------|----------|----------|----------------|------------|-------|
| PRDTST-333 | Position-Based Heading (+-10 deg) | No | Yes | -- | Yes | Requires physical movement and known heading. Stage 4 only. |
| PRDTST-343 | Cold Start No Aiding (< 1 min, < 6m) | Yes | Yes | `gnss.state`, `gnss.fix_valid`, `gnss.accuracy_m`, `gnss.on_time_s`, `gnss.fix_acquired` | Yes | Verify cold start TTFF and accuracy. Requires clear sky (outdoor MTIB or RF repeater). |
| PRDTST-358 | Position-Based Speed (+-20%) | No | Yes | -- | Yes | Requires known-speed movement. Stage 4 only. |
| PRDTST-360 | Warm Start No Aiding (< 30s, < 1m) | Yes | Yes | `gnss.state`, `gnss.fix_valid`, `gnss.accuracy_m`, `gnss.fix_acquired` | Yes | Power cycle after fix, verify warm start TTFF. |
| PRDTST-378 | Cold Start With Aiding (< 30s, < 1m) | Yes | Yes | `gnss.aiding_enabled`, `gnss.fix_valid`, `gnss.accuracy_m`, `gnss.fix_acquired` | Yes | Verify A-GNSS aiding reduces TTFF. |
| PRDTST-384 | Cold Start No Aiding Extended (< 3 min, < 1m) | Yes | Yes | `gnss.state`, `gnss.fix_valid`, `gnss.accuracy_m`, `gnss.on_time_s`, `gnss.fix_acquired` | Yes | Extended cold start with tighter accuracy. |
| PRDTST-396 | Warm Start With Aiding (< 30s, < 1m) | Yes | Yes | `gnss.aiding_enabled`, `gnss.fix_valid`, `gnss.accuracy_m`, `gnss.fix_acquired` | Yes | Verify aided warm start performance. |

#### On-Skin / Biometrics (3 tests)

| PRDTST | Test Name | Stage 3? | Stage 4? | Harness Points | CoreCloud? | Notes |
|--------|-----------|----------|----------|----------------|------------|-------|
| PRDTST-327 | Biometric Messages When On-Skin | Yes | Yes | `sensor.touch`, `sensor.on_body`, `sensor.hr`, `sensor.spo2`, `sensor.vitals_ready`, `msg.biometric_sent` | Yes | Inject on-skin, wait for vitals, verify biometric message in cloud. |
| PRDTST-379 | Position Messages When On-Skin | Yes | Yes | `sensor.touch`, `sensor.on_body`, `sensor.motion`, `msg.position_sent` | Yes | Set on-skin + in-motion, verify position messages sent to cloud. |
| PRDTST-400 | On-Skin Detection | Yes | Yes | `sensor.touch`, `sensor.on_body`, `app.state`, `app.state_changed` | No | Inject touch detected/removed, verify on-body state transitions. |

#### Button / SOS / Haptic (9 tests)

| PRDTST | Test Name | Stage 3? | Stage 4? | Harness Points | CoreCloud? | Notes |
|--------|-----------|----------|----------|----------------|------------|-------|
| PRDTST-325 | Negative SOS Button Press | Yes | Yes | `button.press`, `app.state`, `haptic.active` | No | Press < 3s and > 6s, verify NO SOS mode entry, NO haptic. |
| PRDTST-346 | 7x Button Press Hard Reset | Yes | Yes | `button.press` | No | 7 rapid presses via MTIB GPIO, verify device reboots (detect via boot log or boot message). |
| PRDTST-362 | Haptic on SOS Entry | Yes | Yes | `button.press`, `haptic.active`, `haptic.activated`, `app.state` | No | 3-6s button press, verify SOS entry + haptic feedback. |
| PRDTST-377 | Double-Click Mfg Test Mode | Yes | Yes | `button.press`, `app.state` | No | Double-click via MTIB GPIO, verify mfg test mode entry. |
| PRDTST-380 | Haptic on SOS Acknowledgement | Yes | Yes | `haptic.active`, `haptic.activated`, `ipc.rx` | No | Inject SOS ack via IPC, verify haptic fires. |
| PRDTST-382 | SOS Button Press (3-6s) | Yes | Yes | `button.press`, `app.state`, `app.state_changed`, `msg.sos_sent` | Yes | 3-6s press, verify SOS mode, verify SOS message sent to cloud. |
| PRDTST-395 | Negative Haptic < 3s Press | Yes | Yes | `button.press`, `haptic.active` | No | Press < 3s, verify NO haptic feedback. |
| PRDTST-403 | Haptic on Mfg Test Entry/Exit | Yes | Yes | `button.press`, `haptic.activated` | No | Double-click in/out of mfg test mode, verify haptic each time. |
| PRDTST-408 | Haptic on 3s Button Press | Yes | Yes | `button.press`, `haptic.active`, `haptic.activated` | No | Press for exactly 3s, verify haptic fires. |

#### NFC (1 test)

| PRDTST | Test Name | Stage 3? | Stage 4? | Harness Points | CoreCloud? | Notes |
|--------|-----------|----------|----------|----------------|------------|-------|
| PRDTST-337 | NFC Broadcast Device ID | No | Yes | -- | No | Requires NFC reader. Stage 4 only. |

#### FUOTA (1 test)

| PRDTST | Test Name | Stage 3? | Stage 4? | Harness Points | CoreCloud? | Notes |
|--------|-----------|----------|----------|----------------|------------|-------|
| PRDTST-376 | FUOTA Previous to Current | No | Yes | -- | No | Requires FUOTA infrastructure. Stage 4 only. |

#### VSM / IPC (1 test)

| PRDTST | Test Name | Stage 3? | Stage 4? | Harness Points | CoreCloud? | Notes |
|--------|-----------|----------|----------|----------------|------------|-------|
| PRDTST-410 | VSM Power Cut-off Switch | Yes | Yes | `vsm.power`, `vsm.power_set` | No | Toggle VSM power via harness, verify PPG sensor power state changes, verify current draw changes. |

#### Cloud Messages / Temp Range (1 test)

| PRDTST | Test Name | Stage 3? | Stage 4? | Harness Points | CoreCloud? | Notes |
|--------|-----------|----------|----------|----------------|------------|-------|
| PRDTST-401 | Operate -20C to +60C | No | Yes | -- | No | Requires temperature chamber cycling. Stage 4 only. |

### 12.2 Coverage Summary

| Category | Total | Stage 3 (full) | Stage 3 (partial) | Stage 4 Only | CoreCloud |
|----------|-------|---------------|-------------------|-------------|-----------|
| Power / Runtime | 7 | 0 | 3 | 4 | 0 |
| Config Values | 18 | 18 | 0 | 0 | 14 |
| Motion Detection | 5 | 3 | 2 | 0 | 1 |
| Charging / BMS | 29 | 5 | 7 | 17 | 3 |
| Environmental | 7 | 0 | 7 | 0 | 0 |
| GNSS | 7 | 5 | 0 | 2 | 6 |
| On-Skin / Biometrics | 3 | 3 | 0 | 0 | 2 |
| Button / SOS / Haptic | 9 | 9 | 0 | 0 | 1 |
| NFC | 1 | 0 | 0 | 1 | 0 |
| FUOTA | 1 | 0 | 0 | 1 | 0 |
| VSM / IPC | 1 | 1 | 0 | 0 | 0 |
| Cloud / Temp Range | 1 | 0 | 0 | 1 | 0 |
| **Total** | **89** | **44** | **19** | **26** | **27** |

**44 tests are fully covered by Stage 3** (49%). These are config validation, state
machine transitions, button/haptic interactions, biometric/position message verification,
and GNSS fix acquisition tests.

**19 tests have partial Stage 3 coverage** (21%). Stage 3 can verify firmware-side
behavior (sensor reads, state flags, message construction) but cannot provide the
physical stimulus or calibrated reference needed for full validation. Stage 4 completes
these.

**26 tests are Stage 4 only** (29%). These require physical stimulus (temperature
chambers, charger manipulation, TS pin manipulation, NFC readers, FUOTA infrastructure,
long-duration current measurement) that cannot be replicated through the software
harness.

---

## 13. PRDTST Test Examples (Python)

This section provides realistic Python test implementations for representative PRDTST
tests across each category. These examples use the real acceptance criteria from the
Jira test cases.

### 13.1 Config Validation Tests

#### PRDTST-352: Heartbeat Period Default Value

```python
# alpha_fw/.concord/tests/integration/test_config.py

async def test_prdtst_352_heartbeat_period_default(ctx):
    """
    PRDTST-352: Verify default heartbeat period.
    The device shall send heartbeat messages at the default period.

    Acceptance: On fresh boot, heartbeat period matches the documented
    default value. A position message arrives in the cloud within the
    expected heartbeat interval.
    """
    await ctx.flash_firmware()
    await ctx.power_on()
    await ctx.wait_for_boot()

    # Read the default heartbeat period from harness
    period_s = int(await ctx.harness.get("config.heartbeat_period_s"))
    assert period_s > 0, "Heartbeat period should be > 0 on default config"

    # Put device on-body so it starts sending messages
    await ctx.harness.inject("sensor.touch", "detected")
    await ctx.harness.wait_event("app.state_changed", timeout_s=10)

    # Record time before waiting for heartbeat message
    from datetime import datetime
    start_time = datetime.utcnow()

    # Wait for a position message (heartbeat-triggered)
    await ctx.harness.wait_event("msg.position_sent", timeout_s=period_s + 60)

    # Verify the message arrived in the cloud
    msg = await ctx.cloud.wait_for_message(
        PositionMsgV6, timeout_s=120, since=start_time
    )
    assert msg is not None, "Heartbeat position message not received in cloud"
    assert msg.batt_percent is not None, "Position message missing battery SoC"
```

#### PRDTST-335, 374, 388: Additional Config Tests

**PRDTST-335** (zero heartbeat): `fresh_boot()`, `set("config.heartbeat_period_s", "0")`,
`put_device_on_body()`, then assert no `msg.position_sent` event fires within the default
period. Uses `asyncio.wait_for` with `TimeoutError` as the passing condition.

**PRDTST-374** (config on boot): Record `datetime.utcnow()` before `fresh_boot()`, then
`wait_event("msg.boot_sent")` and `wait_event("msg.config_sent")`. Verify `BootMsgV2`
arrives in cloud with non-null `boot_reason`.

**PRDTST-388** (default config): `fresh_boot()`, then loop over expected defaults
(`heartbeat_period_s=300`, `heartbeat_acq_timeout_s=60`, `cont_motion_period_s=60`,
`stop_motion_timeout_s=120`, `motion_start_sec=3`) and assert each `ctx.harness.get()`
matches. Values also defined in `integration_spec.yaml` so tests can reference the spec.

All remaining config tests (PRDTST-328/330/342/344/347/353/356/359/364/369/371/387/394/399)
follow the same `set`/`get` pattern: set a config value via harness, verify it reads back,
optionally wait for the configured behavior timing.

### 13.2 Motion Detection Tests

#### PRDTST-326: Detect Motion Above Thresholds (Default Config)

```python
async def test_prdtst_326_detect_motion_above_threshold(ctx):
    """
    PRDTST-326: Inject motion -> state transition -> position message
    with is_in_motion=True in cloud.
    """
    await fresh_boot(ctx)
    await put_device_on_body(ctx)
    assert await ctx.harness.get("motion.state") == "motion_is_stopped"

    from datetime import datetime
    motion_time = datetime.utcnow()

    await ctx.harness.inject("sensor.motion", "start")
    evt = await ctx.harness.wait_event("motion.state_changed", timeout_s=10)
    assert evt.value in ("motion_window_open", "motion_in_motion")

    if evt.value == "motion_window_open":
        evt2 = await ctx.harness.wait_event("motion.state_changed", timeout_s=10)
        assert evt2.value == "motion_in_motion"

    await ctx.harness.wait_event("msg.position_sent", timeout_s=30)
    msg = await ctx.cloud.wait_for_message(PositionMsgV6, timeout_s=120, since=motion_time)
    assert msg is not None and msg.is_in_motion is True
```

#### PRDTST-393: Respect Motion Start Window

Verifies the motion start window timing constraint. Pattern: `fresh_boot()`, read
`config.motion_start_sec` (default 3), `put_device_on_body()`, inject motion, record
`time.monotonic()`. First `motion.state_changed` event should be `motion_window_open`
(immediate). Second event should be `motion_in_motion` only after `>= window - 0.5s`
elapsed. PRDTST-324 (below threshold) and PRDTST-375 (below duration) use similar
inject-and-verify-no-transition patterns with `TimeoutError` as passing condition.

### 13.3 On-Skin / Biometric Tests

#### PRDTST-327: Biometric Data Messages Sent When On-Skin

```python
async def test_prdtst_327_biometric_messages_on_skin(ctx):
    """PRDTST-327: On-skin -> VSM warm-up -> BiometricDataMsg in cloud."""
    await fresh_boot(ctx)
    assert await ctx.harness.get("sensor.on_body") == "false"
    from datetime import datetime; skin_time = datetime.utcnow()

    await put_device_on_body(ctx)
    await ctx.harness.wait_event("sensor.vitals_ready", timeout_s=90)  # VSM warm-up ~60s
    hr = int(await ctx.harness.get("sensor.hr"))
    assert hr > 0, f"Invalid HR={hr} after warm-up"

    await ctx.harness.wait_event("msg.biometric_sent", timeout_s=30)
    bio = await ctx.cloud.wait_for_message(BiometricDataMsg, timeout_s=120, since=skin_time)
    assert bio is not None and bio.on_body and bio.heart_rate > 0 and bio.spo2 is not None
```

#### PRDTST-400: On-Skin Detection

Verifies both on-skin and off-skin transitions. Pattern: `fresh_boot()`, assert
`sensor.on_body == "false"`, then `put_device_on_body()` and verify
`app.state_changed -> low_heat_risk_e` and `sensor.on_body == "true"`. Then inject
`sensor.touch: removed`, verify `app.state_changed -> off_body_validation_e`, then
`app.state_changed -> off_body_e`, and `sensor.on_body == "false"`.

### 13.4 Button / SOS / Haptic Tests

#### PRDTST-382: SOS Button Press (3-6 Seconds)

```python
async def test_prdtst_382_sos_button_press(ctx):
    """PRDTST-382: SOS mode on 3-6 second button press."""
    await fresh_boot(ctx)
    await ctx.mtib.gpio_set("button", 0)          # Press (active low)
    import asyncio; await asyncio.sleep(4.0)       # Hold 4s (within 3-6s window)
    await ctx.mtib.gpio_set("button", 1)           # Release

    haptic = await ctx.harness.wait_event("haptic.activated", timeout_s=5)
    assert haptic is not None, "No haptic feedback on 4s press"
    sos = await ctx.harness.wait_event("msg.sos_sent", timeout_s=30)
    assert sos is not None, "No SOS message sent after 4s press"
```

#### PRDTST-325, 412: Additional Button Tests

**PRDTST-325** (negative SOS): Loop over durations [1.0s, 8.0s], use MTIB GPIO to press
and release, assert `msg.sos_sent` does NOT fire within 5s (`TimeoutError` = pass).

**PRDTST-412** (battery check): Short press (500ms) via MTIB GPIO, wait for
`led.pattern_changed`, verify `led.pattern != "off"`. Cross-reference against
`battery.soc` to confirm the LED indicates the correct SoC range.

Remaining button tests (PRDTST-346/362/377/380/395/403/408) follow the same MTIB GPIO
press/release pattern with different durations and expected event/LED/haptic outcomes.

### 13.5 GNSS Tests

#### PRDTST-343: Cold Start, No Aiding (< 1 min, < 6m)

```python
async def test_prdtst_343_gnss_cold_start_no_aiding(ctx):
    """PRDTST-343: TTFF <= 60s, accuracy <= 6m, clear sky, no aiding."""
    await fresh_boot(ctx)
    assert await ctx.harness.get("gnss.aiding_enabled") == "false"
    await put_device_on_body(ctx)
    await put_device_in_motion(ctx)

    import time; from datetime import datetime
    gps_start = time.monotonic(); fix_time = datetime.utcnow()
    fix_evt = await ctx.harness.wait_event("gnss.fix_acquired", timeout_s=60)
    assert fix_evt is not None and (time.monotonic() - gps_start) <= 60.0
    assert int(await ctx.harness.get("gnss.accuracy_m")) <= 6

    msg = await ctx.cloud.wait_for_message(PositionMsgV6, timeout_s=120, since=fix_time)
    assert msg is not None and msg.gnss_fix_ok and msg.horizontal_accuracy <= 6
```

PRDTST-378/360/396 follow the same pattern with different TTFF/accuracy thresholds and
pre-conditions (enable aiding via `GPSConfMsg.send_via_rest()`, power cycle for warm vs cold start).

### 13.6 BMS / Charging Tests (Stage 3 Partial)

#### PRDTST-366: BMS SoC and Temp in Position Message

```python
async def test_prdtst_366_bms_soc_temp_in_position(ctx):
    """PRDTST-366: Position msg has battery SoC + temp while in motion on-skin."""
    await fresh_boot(ctx)
    soc = int(await ctx.harness.get("battery.soc"))
    from datetime import datetime; msg_time = datetime.utcnow()

    await put_device_on_body(ctx)
    await put_device_in_motion(ctx)
    await ctx.harness.wait_event("msg.position_sent", timeout_s=30)

    msg = await ctx.cloud.wait_for_message(PositionMsgV6, timeout_s=120, since=msg_time)
    assert msg is not None and msg.batt_percent is not None and msg.bms_temp is not None
    assert abs(msg.batt_percent - soc) <= 2, f"SoC mismatch: {msg.batt_percent}% vs {soc}%"
```

#### PRDTST-381: BMS Parameter Retention After Power Cycle

Verifies BMS state survives power cycle. Pattern: `fresh_boot()`, read `battery.soc` and
`battery.voltage_mv`, then `power_off()`, sleep 2s, `power_on()`, `wait_for_boot()`, read
again. Assert SoC delta <= 5% and voltage delta <= 100mV. Remaining BMS tests
(PRDTST-334/338/354/355/373/385/411) read BMS harness points and verify against
acceptance criteria; many are partial Stage 3 coverage (see Section 12).

### 13.7 VSM, Position, and Environmental Tests

These tests follow patterns established above. Brief descriptions:

**PRDTST-410** (VSM power): `fresh_boot()`, `put_device_on_body()`, verify
`vsm.power == "enabled"`, measure current via `ctx.mtib.power_measure(duration_s=5)`,
inject `vsm.power_set: off`, verify `vsm.power == "disabled"` and current decreased,
then re-enable and verify recovery.

**PRDTST-379** (position on-skin): `fresh_boot()`, `put_device_on_body()`,
`put_device_in_motion()`, wait for `msg.position_sent`, verify `PositionMsgV6` in cloud
with non-null `batt_percent` and `air_pressure`.

**PRDTST-345** (temperature, partial): `fresh_boot()`, sleep 5s for sensor warm-up, read
`env.temperature` and `env.ir_skin_temp`, assert both in 10-45C range and within 5C of
each other. Full +-0.5C accuracy against calibrated reference is Stage 4 only.

Environmental tests (PRDTST-329/336/357/398/405/406) follow the same pattern: read
harness point, assert plausible range. Precision accuracy tests are Stage 4.

---

## 14. Stage 3 Test Organization and Execution

### 14.1 Test File Structure

```
alpha_fw/.concord/tests/integration/
    conftest.py                  # Shared fixtures and helpers
    test_config.py               # PRDTST-328/330/335/342/344/347/352/353/356/359/
                                 #   364/369/371/374/387/388/394/399
    test_motion.py               # PRDTST-324/326/375/393
    test_biometrics.py           # PRDTST-327/400
    test_position.py             # PRDTST-379/366/368/350
    test_gnss.py                 # PRDTST-343/360/378/384/396
    test_button.py               # PRDTST-325/346/362/377/380/382/395/403/408/412
    test_bms.py                  # PRDTST-334/338/354/355/373/381/385/411
    test_vsm.py                  # PRDTST-410
    test_environmental.py        # PRDTST-329/336/345/357/398/405/406
    test_power.py                # PRDTST-341/348/404 (partial)
    test_boot.py                 # PRDTST-374/388 (boot-specific)
```

### 14.2 Common Test Helpers (`conftest.py`)

```python
# alpha_fw/.concord/tests/integration/conftest.py

async def put_device_on_body(ctx):
    """Inject on-skin and wait for state transition to low_heat_risk_e."""
    await ctx.harness.inject("sensor.touch", "detected")
    return await ctx.harness.wait_event("app.state_changed", timeout_s=10)

async def put_device_in_motion(ctx):
    """Inject motion start and wait for motion state change."""
    await ctx.harness.inject("sensor.motion", "start")
    return await ctx.harness.wait_event("motion.state_changed", timeout_s=10)

async def fresh_boot(ctx):
    """Flash, power on, wait for boot, verify off_body_e."""
    await ctx.flash_firmware()
    await ctx.power_on()
    await ctx.wait_for_boot()
    state = await ctx.harness.get("app.state")
    assert state == "off_body_e", f"Expected off_body_e after boot, got {state}"
```

The `conftest.py` also defines `EXPECTED_HARNESS_POINTS` (the full set of 62 point
names from Section 11.12) and a `test_harness_points` function that runs as a
pre-flight check at the start of every test session.

### 14.3 Execution Timing Estimates

| Test File | Approx. Tests | Estimated Duration | Dominant Factor |
|-----------|---------------|-------------------|-----------------|
| `test_config.py` | 18 | 4-6 min | Config reads are fast; heartbeat timing tests need ~1 period wait each |
| `test_motion.py` | 4 | 1-2 min | Motion state machine transitions are fast (< 10s each) |
| `test_biometrics.py` | 2 | 3-4 min | VSM warm-up period (60s) for PRDTST-327 |
| `test_position.py` | 4 | 5-8 min | GNSS fix acquisition + cloud message delivery |
| `test_gnss.py` | 5 | 5-10 min | GNSS cold start (60s) + warm start tests |
| `test_button.py` | 10 | 3-5 min | Button press timings (4s SOS, 1s short, etc.) |
| `test_bms.py` | 7 | 2-3 min | BMS reads are fast; power cycle for PRDTST-381 adds ~5s |
| `test_vsm.py` | 1 | 1-2 min | VSM power cycle + current measurement |
| `test_environmental.py` | 7 | 1-2 min | Sensor reads are fast |
| `test_power.py` | 3 | 3-5 min | 10-minute measurement for PRDTST-404 |
| `test_boot.py` | 2 | 3-5 min | Power cycle + cloud message wait |
| **Total** | **63** | **30-50 min** | GNSS + cloud message delivery dominate |

Tests sharing firmware state should be grouped to avoid redundant flash + boot cycles.

### 14.4 Test Tagging for Cadence

| Tag | When | Tests | Rationale |
|-----|------|-------|-----------|
| `commit` | Every push | Config, motion, biometric, button, boot (42 tests, ~20 min) | Core regression |
| `gnss` | Nightly | GNSS tests (5 tests, ~10 min) | Requires outdoor MTIB / RF repeater |
| `power` | Weekly | Power measurement (3 tests, ~15 min) | Slower, unlikely to regress per-commit |
| `cloud` | Every push | Cloud message verification (27 tests, in commit suite) | E2E delivery regression |

### 14.5 Integration Spec (`integration_spec.yaml`)

The spec file defines power budgets (from PRDTST-341/348/404), GNSS timing limits
(from PRDTST-343/360/378/384/396), accuracy budgets (from PRDTST-334/345/357/398),
timing constants (motion window, off-body verification, VSM warm-up), cloud message
timeouts, and config defaults (for PRDTST-388 verification). Tests reference these
values rather than hardcoding thresholds.

```yaml
# alpha_fw/.concord/integration_spec.yaml (abbreviated)
version: 1
product: alpha
board: alpha_b0

power_budgets:
  off_body_idle_ua: 500          # PRDTST-348
  active_monitoring_ma: 50       # PRDTST-404
gnss:
  cold_start_no_aiding_s: 60    # PRDTST-343
  cold_start_aiding_s: 30       # PRDTST-378
accuracy:
  gnss_cold_start_m: 6          # PRDTST-343
  gnss_aided_m: 1               # PRDTST-378/384/396
config_defaults:
  heartbeat_period_s: 300
  heartbeat_acq_timeout_s: 60
  cont_motion_period_s: 60
  stop_motion_timeout_s: 120
  motion_start_sec: 3
```
