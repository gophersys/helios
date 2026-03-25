# Stage 3 Proof-of-Concept: Execution Plan

> **Goal:** Prove the `concord_harness` integration testing concept end-to-end on
> real Alpha hardware. Flash instrumented firmware, send shell commands over UART
> via MTIB, observe state machine behavior, and run integration tests that verify
> firmware correctness.
>
> **Total Estimated Effort:** ~133h engineering + ~$200-400 hardware
>
> **Timeline:** ~3-4 weeks with 2 engineers working in parallel
>
> **Date:** 2026-02-25

---

## Table of Contents

1. [What We're Proving](#1-what-were-proving)
2. [What Already Exists](#2-what-already-exists)
3. [Work Streams & Dependency Graph](#3-work-streams--dependency-graph)
4. [Phase 0: Prerequisites & Procurement](#phase-0-prerequisites--procurement)
5. [Phase 1: Parallel Foundation (Streams A + B + C)](#phase-1-parallel-foundation)
6. [Phase 2: Harness Integration (Stream D + E)](#phase-2-harness-integration)
7. [Phase 3: End-to-End Proof (Stream F)](#phase-3-end-to-end-proof)
8. [Verification Checkpoints](#8-verification-checkpoints)
9. [Risk Register (Stage 3 Proof Specific)](#9-risk-register)
10. [Post-Proof: What Comes Next](#10-post-proof-what-comes-next)

---

## 1. What We're Proving

Stage 3 integration testing answers: **"Does the firmware behave correctly when
multiple components interact on real hardware?"**

The proof-of-concept demonstrates this flow:

```
┌─────────────────────────────────────────────────────────────┐
│                    PROOF-OF-CONCEPT FLOW                    │
│                                                             │
│  1. Build Alpha firmware with CONFIG_CONCORD_HARNESS=y      │
│  2. Flash instrumented firmware to Alpha board via MTIB SWD │
│  3. Open UART0 channel via MTIB gRPC                        │
│  4. Send shell commands:  concord list / get / set / inject │
│  5. Observe state transitions via CONCORD_EMIT events       │
│  6. Run Python integration tests that:                      │
│     a. Inject sensor stimulus (touch detected/removed)      │
│     b. Assert state machine transitions                     │
│     c. Verify timing behavior (off-body validation window)  │
│     d. Check harness point values match expected state      │
│  7. Generate pass/fail results                              │
└─────────────────────────────────────────────────────────────┘
```

**Success criteria:**
- `concord list` returns all registered harness points over UART
- `concord get app.state` returns correct current state
- `concord inject sensor.touch detected` triggers state transition
- `[CONCORD:EVT] app.state_changed=low_heat_risk_e` appears on UART
- Python test suite passes 5+ integration test scenarios
- Production build (`CONFIG_CONCORD_HARNESS=n`) compiles identically to current

---

## 2. What Already Exists

### 2.1 Repositories We Will Touch

| Repository | Location | Current State | Action |
|-----------|----------|---------------|--------|
| `alpha_fw` | `/home/mateo/work/firmware/alpha_fw/` | Production firmware, no test infra, no harness | **UPDATE** — add getters, harness declarations, `#ifdef` guards |
| `concord_harness` | Does not exist | Nothing | **CREATE** — new standalone Zephyr module repo |
| Concord monorepo | `/home/mateo/work/concord/concord/` | Has MTIB client v2, HTTP API, K8s infra | **UPDATE** — minor mtib_client tweaks + new Python test scripts |

### 2.2 Existing Infrastructure (No Changes Needed)

| Component | Location | Used For |
|-----------|----------|----------|
| MTIB server v2 | Deployed on edge nodes, source at `concord/apps/edge/mtib-server-v2/` | gRPC: flash, UART, power, GPIO |
| MTIB client v2 (Python) | `concord/libs/python/corekinect/mtib_client/v2/` | Python gRPC wrapper |
| K3s cluster | 3 servers + 3 agents | Runs MTIB nodes |
| MTIB V2 protobuf defs | `concord/libs/protocols/mtib_v2/` | gRPC service definitions |
| Alpha B0 board def | `alpha_fw/ck_boards/current/boards/corekinect/alpha_b0/` | Board definition for builds |
| Alpha build script | `alpha_fw/build_all.sh` | Existing build tooling |

### 2.3 Key Alpha Firmware Files We'll Modify

| File | What's There Now | What We Add |
|------|-----------------|-------------|
| `src/app/alpha_state_machine.c` | State machine with `alpha_state_t` defined locally in `.c` | Move typedef to `.h`, add `get_alpha_state()` accessor, add `CONCORD_EMIT()` calls |
| `src/app/alpha_state_machine.h` | Header exists but doesn't expose `alpha_state_t` | Add typedef + accessor declaration |
| `src/app/motion_state_machine.c` | Motion state machine, `motion_state_t` in `.c` | Move typedef to `.h`, add `get_motion_state()` accessor, add `CONCORD_EMIT()` |
| `src/app/motion_state_machine.h` | Header without type exposure | Add typedef + accessor declaration |
| `src/app/app.c` | Kills UART0 RX for power savings (`NRF_UARTE0->TASKS_STOPRX = 1`) | Add `#ifdef CONFIG_CONCORD_HARNESS` guard around UART0 kill |
| `src/app/vsm_handler.c` | `is_device_on_body()` reads VSM flags directly | Add conditional harness override hook |
| `src/CMakeLists.txt` | Lists app sources | Add conditional `concord_harness.c` |
| `prj.conf` | Production Kconfig | No changes (overlay file handles harness config) |

### 2.4 MTIB V2 RPCs We'll Use (Already Implemented)

| RPC | Purpose in Stage 3 |
|-----|-------------------|
| `FlashProgram` | Flash instrumented firmware via SWD |
| `UartStream` | Bidirectional UART for shell commands + event capture |
| `DutPowerEnable` / `DutPowerDisable` | Power cycle the Alpha board |
| `DebugReset` | Reset MCU after flash |
| `PowerMeasure` | Optional: coarse system-level current (nice-to-have) |
| `GpioSet` | Optional: button/charger stimulus if wired |

---

## 3. Work Streams & Dependency Graph

```
PHASE 0 (Day 1)
════════════════════════════════════════════════════════════════
  Order Alpha board (H07)  ←── do this immediately, lead time

PHASE 1 (Week 1-2): PARALLEL FOUNDATION
════════════════════════════════════════════════════════════════

  Stream A                    Stream B              Stream C
  (concord_harness module)    (alpha_fw getters)    (HW setup)
  ───────────────────────     ──────────────────    ──────────
  A1: Create repo + scaffold  B1: Move typedefs     C1: Wire Alpha
  A2: concord_harness.h       B2: Add accessors         to MTIB
  A3: concord_harness_types.h B3: UART0 RX fix      C2: Register
  A4: concord_registry.c                                MTIB node
  A5: concord_shell.c         (B done: ~5h)         C3: Verify
  A6: concord_emit.c                                    flash+UART
  A7: Kconfig + CMake + yml
                              (C done: ~18h)
  (A done: ~29.5h)

                    │                    │              │
                    ▼                    ▼              │
PHASE 2 (Week 2-3): HARNESS INTEGRATION                │
════════════════════════════════════════════════════════════════

  Stream D                              Stream E       │
  (alpha_fw harness integration)        (Python side)  │
  ────────────────────────────          ────────────── │
  D1: concord_harness.c declarations    E1: harness_client.py
  D2: CONCORD_EMIT calls               E2: fixture_controller.py
  D3: Alpha B0 harness overlay          E3: mtib_client updates
  D4: Build + verify instrumented fw
                                                       │
  (D done: ~30h)                        (E done: ~28h) │
                    │                        │         │
                    ▼                        ▼         ▼
PHASE 3 (Week 3-4): END-TO-END PROOF
════════════════════════════════════════════════════════════════

  Stream F (Integration tests)
  ────────────────────────────
  F1: integration_spec.yaml
  F2: test_vsm.py, test_state_machine.py, etc.
  F3: Manual E2E run on Alpha hardware
  F4: Fix issues, iterate, document results

  (F done: ~28h)
```

**Key dependency rules:**
- Stream A, B, C are fully independent — start all three on day 1
- Stream D requires Stream A (F28 API) + Stream B (F19 headers) to be complete
- Stream E can start partially in parallel with A (I14 has no dependency, I10 has no dependency), but I17 (harness_client) needs knowledge of the protocol from A
- Stream F requires D + E + C all complete

---

## Phase 0: Prerequisites & Procurement

### Step 0.1: Procure Alpha Hardware

**Action:** Order 1-2 Alpha product boards for the test fixture.

**Details:**
- Minimum 1 board, recommended 2 (one for wiring/debug, one as spare)
- Board revision: B0 (matches `alpha_b0` board definition in `ck_boards`)
- Cost: ~$200/unit
- Lead time: Check internal inventory first — may already have dev units available

**Who:** Hardware engineer or project lead
**When:** Day 1 — this is the longest lead time item

### Step 0.2: Identify MTIB Node for Validation

**Action:** Identify which MTIB edge node will host the Alpha validation fixture.

**Details:**
- Must be a Verdin iMX8M Mini node running MTIB server v2
- Must NOT be currently assigned to manufacturing duty
- Must have available SWD + UART + power control channels
- Check current node inventory: `kubectl get nodes -l purpose=validation` on the K3s cluster
- If no validation-purpose node exists, either repurpose a manufacturing node or provision a new one

**Who:** Infra engineer
**When:** Day 1

---

## Phase 1: Parallel Foundation

Three independent work streams. All can start on day 1 and run concurrently.

---

### Stream A: Build the `concord_harness` Zephyr Module

**Total effort:** ~29.5h
**Dependencies:** None
**Owner:** Infra engineer (someone comfortable with Zephyr module system + linker sections)

This is the core novel work. The module provides a shell-based harness for
integration testing. It uses Zephyr's `STRUCT_SECTION_ITERABLE` for zero-cost
compile-time registration of observable/controllable points.

---

#### Step A1: Create Repository & Scaffold

**Effort:** 1h
**Depends on:** Nothing
**Produces:** Empty but buildable Zephyr module skeleton

<details>
<summary><strong>Agent Prompt (click to expand)</strong></summary>

```
TASK: Create the concord_harness Zephyr external module repository scaffold.

CONTEXT:
concord_harness is a brand-new, standalone Zephyr module that provides a
shell-based instrumentation harness for integration testing of firmware on
real hardware. It will be pulled into firmware projects via west manifest.

The module does NOT contain any product-specific code. It provides a generic
framework (macros + shell commands + event emission) that firmware projects
use by writing their own `concord_harness.c` file with CONCORD_GETTER,
CONCORD_SETTER, CONCORD_INJECT, and CONCORD_EVENT declarations.

DELIVERABLES:
Create the following directory structure:

  concord_harness/
  ├── zephyr/
  │   ├── module.yml
  │   ├── CMakeLists.txt
  │   ├── Kconfig
  │   ├── include/
  │   │   └── concord_harness/
  │   │       ├── concord_harness.h         # (placeholder, populated in A2)
  │   │       └── concord_harness_types.h   # (placeholder, populated in A3)
  │   └── src/
  │       ├── concord_registry.c            # (placeholder, populated in A4)
  │       ├── concord_shell.c               # (placeholder, populated in A5)
  │       └── concord_emit.c               # (placeholder, populated in A6)
  └── tests/                                # (empty, for future unit tests)
      └── .gitkeep

1. zephyr/module.yml:
   - name: concord_harness
   - cmake: zephyr/CMakeLists.txt  (relative to module root, NOT repo root)
   - kconfig: zephyr/Kconfig

2. zephyr/CMakeLists.txt:
   - Guard everything behind: if(CONFIG_CONCORD_HARNESS)
   - zephyr_library()
   - zephyr_library_sources(src/concord_registry.c src/concord_shell.c src/concord_emit.c)
   - zephyr_include_directories(include/)

3. zephyr/Kconfig:
   - CONFIG_CONCORD_HARNESS (bool, default n)
     depends on SHELL && SHELL_BACKEND_SERIAL
     help: "Enable concord instrumentation harness for integration testing"
   - CONFIG_CONCORD_HARNESS_MAX_POINTS (int, default 64)
   - CONFIG_CONCORD_HARNESS_EVENT_QUEUE_SIZE (int, default 16)
   - CONFIG_CONCORD_HARNESS_THREAD_STACK_SIZE (int, default 2048)
   - CONFIG_CONCORD_HARNESS_THREAD_PRIORITY (int, default 14)
     help: "Lowest preemptible priority - no timing impact on application"

4. Initialize git repo, create initial commit.

IMPORTANT CONSTRAINTS:
- Module MUST follow Zephyr external module conventions exactly.
  See: https://docs.zephyrproject.org/latest/develop/modules.html
- The module.yml 'cmake' and 'kconfig' paths are relative to the module root
  (the directory containing the zephyr/ folder), NOT relative to the zephyr/
  folder itself.
- All source files are placeholders at this step. They should contain only
  a comment saying "// Implementation in step A<N>" and compile without errors.
- concord_harness.h placeholder should have an empty include guard.
- concord_harness_types.h placeholder should have an empty include guard.
- The CMakeLists.txt must only build when CONFIG_CONCORD_HARNESS=y.

LOCATION: Create at a path that makes sense for your firmware module layout.
If unsure, create at /home/mateo/work/firmware/concord_harness/ to sit
alongside other firmware repos.

VERIFICATION:
- The module should be parseable by west (module.yml is valid YAML)
- Kconfig file should parse without errors
- CMakeLists.txt should be valid CMake (even though sources are stubs)
```

</details>

---

#### Step A2: Implement `concord_harness.h` (Public API & Macros)

**Effort:** 8h
**Depends on:** A1 (scaffold exists)
**Produces:** The four registration macros + CONCORD_EMIT runtime macro
**This is the most important file in the entire module.**

<details>
<summary><strong>Agent Prompt (click to expand)</strong></summary>

```
TASK: Implement concord_harness.h — the public API header for the
concord_harness Zephyr module.

CONTEXT:
This header defines the four compile-time registration macros and the one
runtime emission macro that firmware projects use. When CONFIG_CONCORD_HARNESS
is disabled, ALL macros must expand to ABSOLUTELY NOTHING — zero code, zero
data, zero overhead.

The registration mechanism uses Zephyr's STRUCT_SECTION_ITERABLE to place
harness point descriptors in a dedicated linker section. This is the same
pattern Zephyr uses for shell commands — no manual registration arrays needed.

FILE: concord_harness/zephyr/include/concord_harness/concord_harness.h

DESIGN SPECIFICATION:

1. Include guard and conditional compilation:
   - Everything inside #ifdef CONFIG_CONCORD_HARNESS / #else (empty) / #endif
   - When disabled, every macro expands to nothing

2. Required includes (when enabled):
   - <zephyr/sys/iterable_sections.h>  (for STRUCT_SECTION_ITERABLE)
   - "concord_harness_types.h"         (for struct definitions)

3. Four registration macros (compile-time, placed in concord_harness.c files):

   CONCORD_GETTER(name_str, body)
   - Creates a function: static const char *_concord_getter_<mangled_name>(void) { body }
   - Creates a STRUCT_SECTION_ITERABLE(concord_point, ...) entry with:
     .name = name_str
     .type = CONCORD_POINT_GETTER
     .getter = _concord_getter_<mangled_name>
   - The body is a C block that returns a const char* (the value string)
   - Example usage:
       CONCORD_GETTER("app.state", {
           return alpha_state_to_str(get_alpha_state());
       })

   CONCORD_SETTER(name_str, body)
   - Creates a function: static const char *_concord_setter_<mangled_name>(const char *value) { body }
   - STRUCT_SECTION_ITERABLE entry with .type = CONCORD_POINT_SETTER, .setter = fn
   - The body receives 'value' (the string argument) and returns "OK" or "ERR:<reason>"
   - Example:
       CONCORD_SETTER("config.pd", {
           int val = atoi(value);
           if (val < 1 || val > 255) return "ERR:range";
           set_pd_config((uint8_t)val);
           return "OK";
       })

   CONCORD_INJECT(name_str, body)
   - Creates a function: static const char *_concord_inject_<mangled_name>(const char *value) { body }
   - STRUCT_SECTION_ITERABLE entry with .type = CONCORD_POINT_INJECT, .inject = fn
   - The body is a firmware-engineer-written adapter that translates the string
     command into whatever internal mechanism the firmware uses (flag override,
     message queue post, etc.)
   - Example:
       CONCORD_INJECT("sensor.touch", {
           if (strcmp(value, "detected") == 0) {
               concord_force_on_body(true);
               return "OK";
           }
           return "ERR:expected detected|removed";
       })

   CONCORD_EVENT(name_str)
   - Declares an event point (no function, just registration)
   - STRUCT_SECTION_ITERABLE entry with .type = CONCORD_POINT_EVENT, .name = name_str
   - Events are emitted at runtime via CONCORD_EMIT() from production code

4. One runtime macro:

   CONCORD_EMIT(name_str, value_str)
   - Calls concord_emit_event(name_str, value_str) when enabled
   - Expands to nothing when disabled
   - This is the ONLY macro placed in production source files (state machine .c files)
   - Must be safe to call from ANY thread context, including ISRs
   - The implementation (in concord_emit.c) uses k_msgq_put(K_NO_WAIT)

5. Function declaration (when enabled):
   void concord_emit_event(const char *name, const char *value);
   (Implemented in concord_emit.c)

NAME MANGLING:
The macro needs to generate unique C identifiers from the name string.
Use a helper macro that takes __LINE__ or __COUNTER__ to generate unique names.
A common pattern:
  #define _CONCORD_CONCAT(a, b) a ## b
  #define _CONCORD_UNIQUE(prefix) _CONCORD_CONCAT(prefix, __COUNTER__)

Or use the name string with dots replaced — but __COUNTER__ is simpler and
guaranteed unique.

CRITICAL REQUIREMENTS:
- When CONFIG_CONCORD_HARNESS=n, ALL macros MUST expand to nothing.
  No function definitions, no struct instances, no data. The resulting binary
  must be IDENTICAL to a build that never included the header.
- STRUCT_SECTION_ITERABLE entries must use the section name "concord_point"
  consistently (this is what concord_registry.c iterates over).
- CONCORD_EMIT must be non-blocking (K_NO_WAIT). It must NEVER delay the
  calling thread. If the event queue is full, the event is silently dropped.
- All registration macros are meant to be used ONLY in concord_harness.c
  files (one per firmware project). CONCORD_EMIT is the only macro used in
  production .c files.

REFERENCE:
- Zephyr STRUCT_SECTION_ITERABLE docs:
  https://docs.zephyrproject.org/latest/kernel/iterable_sections/index.html
- Zephyr shell command registration (same pattern):
  SHELL_CMD_REGISTER uses STRUCT_SECTION_ITERABLE under the hood.

VERIFICATION:
- Write a small test in your head: if a firmware file includes this header
  and writes CONCORD_GETTER("test", { return "hello"; }), the linker section
  should contain one concord_point entry.
- If CONFIG_CONCORD_HARNESS=n and the same file is compiled, zero bytes
  of code/data should be generated from the macro.
```

</details>

---

#### Step A3: Implement `concord_harness_types.h` (Registration Structs)

**Effort:** 2h
**Depends on:** A2 (needs to know the struct layout referenced by macros)
**Produces:** The `concord_point` struct and enum used by the linker section

<details>
<summary><strong>Agent Prompt (click to expand)</strong></summary>

```
TASK: Implement concord_harness_types.h — the internal type definitions for
the concord_harness module.

FILE: concord_harness/zephyr/include/concord_harness/concord_harness_types.h

CONTEXT:
This header defines the struct that gets placed in the linker section by
STRUCT_SECTION_ITERABLE. It's included by concord_harness.h and used by
concord_registry.c and concord_shell.c.

SPECIFICATION:

1. enum concord_point_type:
   - CONCORD_POINT_GETTER  = 0
   - CONCORD_POINT_SETTER  = 1
   - CONCORD_POINT_INJECT  = 2
   - CONCORD_POINT_EVENT   = 3

2. Function pointer typedefs:
   - typedef const char *(*concord_getter_fn)(void);
   - typedef const char *(*concord_setter_fn)(const char *value);
   - typedef const char *(*concord_inject_fn)(const char *value);

3. struct concord_point:
   - const char *name;            // Dot-separated name, e.g. "app.state"
   - enum concord_point_type type;
   - union {
       concord_getter_fn getter;  // For GETTER type
       concord_setter_fn setter;  // For SETTER type
       concord_inject_fn inject;  // For INJECT type
       // EVENT type has no function (emission is via CONCORD_EMIT)
     };

4. Include guard. No conditional compilation needed — this file is only
   included when CONFIG_CONCORD_HARNESS=y (guarded in concord_harness.h).

NOTES:
- The struct must be compatible with STRUCT_SECTION_ITERABLE. This means it
  needs to be a plain C struct with no C++ features.
- Using a union for the function pointers keeps the struct small (one pointer
  per entry regardless of type).
- The name string is a const char* pointing to a string literal (from the
  macro). It does NOT need to be copied — string literals have static storage.
```

</details>

---

#### Step A4: Implement `concord_registry.c` (Linker Section Iteration)

**Effort:** 4h
**Depends on:** A2, A3 (needs types and section name)
**Produces:** Functions to look up harness points by name and iterate all points

<details>
<summary><strong>Agent Prompt (click to expand)</strong></summary>

```
TASK: Implement concord_registry.c — the harness point lookup and iteration
module.

FILE: concord_harness/zephyr/src/concord_registry.c

CONTEXT:
This module provides the ability to find a registered harness point by name
and to iterate over all registered points. It uses Zephyr's
STRUCT_SECTION_FOREACH to walk the linker section populated by
STRUCT_SECTION_ITERABLE entries from the registration macros.

SPECIFICATION:

1. Required includes:
   - <zephyr/kernel.h>
   - <zephyr/sys/iterable_sections.h>
   - <string.h>
   - <concord_harness/concord_harness_types.h>

2. Functions to implement:

   const struct concord_point *concord_registry_find(const char *name);
   - Iterates over all concord_point entries in the linker section
   - Returns pointer to the matching entry, or NULL if not found
   - Uses strcmp for exact match on name field
   - Uses STRUCT_SECTION_FOREACH(concord_point, point) { ... }

   int concord_registry_count(void);
   - Returns total number of registered harness points
   - Uses STRUCT_SECTION_COUNT(concord_point, &count)

   void concord_registry_foreach(void (*callback)(const struct concord_point *point, void *user_data), void *user_data);
   - Iterates all points, calling callback for each
   - Used by the "concord list" shell command
   - Uses STRUCT_SECTION_FOREACH

3. Type-to-string helper:

   const char *concord_point_type_str(enum concord_point_type type);
   - Returns "GETTER", "SETTER", "INJECT", or "EVENT"
   - Used by "concord list" output formatting

4. Declare all public functions in a header or in concord_harness.h
   (add declarations to concord_harness.h's enabled section if that's
   the pattern — these are internal to the module, called by shell.c).

NOTES:
- STRUCT_SECTION_FOREACH is a Zephyr macro that expands to a for-loop over
  the linker section. It handles all the linker magic internally.
- The lookup is O(n) linear scan. With max 64 points (default), this is fine.
- No dynamic memory allocation. Everything is statically placed by the linker.
- Thread safety: the registry is read-only after boot (linker section is
  populated at compile time). No locking needed for reads.
```

</details>

---

#### Step A5: Implement `concord_shell.c` (Shell Command Handlers)

**Effort:** 8h
**Depends on:** A3, A4 (needs types + registry lookup)
**Produces:** The `concord` shell command with `list`, `get`, `set`, `inject` subcommands

<details>
<summary><strong>Agent Prompt (click to expand)</strong></summary>

```
TASK: Implement concord_shell.c — the Zephyr shell command handlers for the
concord harness.

FILE: concord_harness/zephyr/src/concord_shell.c

CONTEXT:
This module registers a top-level "concord" shell command with subcommands:
list, get, set, inject. All responses use the [CONCORD:RSP] prefix for
reliable demultiplexing on the host (Python test runner).

The shell is accessed over UART0 via MTIB's UartStream gRPC. The Python
harness_client sends commands and parses responses by looking for lines
starting with [CONCORD:RSP] or [CONCORD:EVT]. Everything else is treated
as device log output.

SPECIFICATION:

1. Required includes:
   - <zephyr/kernel.h>
   - <zephyr/shell/shell.h>
   - <string.h>
   - <concord_harness/concord_harness.h>
   - <concord_harness/concord_harness_types.h>

2. Response format (CRITICAL — host-side parser depends on this exactly):

   All responses MUST be printed with this exact format:
   shell_fprintf(sh, SHELL_NORMAL, "[CONCORD:RSP] %s\n", payload);

   Specific formats:
   - get success:    [CONCORD:RSP] <name>=<value>
   - get not found:  [CONCORD:RSP] <name>=ERR:not_found
   - set success:    [CONCORD:RSP] <name>=OK
   - set error:      [CONCORD:RSP] <name>=ERR:<reason>
   - inject success: [CONCORD:RSP] <name>=OK
   - inject error:   [CONCORD:RSP] <name>=ERR:<reason>
   - list begin:     [CONCORD:RSP] LIST_BEGIN
   - list entry:     [CONCORD:RSP] <type> <name>
   - list end:       [CONCORD:RSP] LIST_END

3. Shell command registration:

   Use Zephyr's shell command macros:

   SHELL_STATIC_SUBCMD_SET_CREATE(concord_subcmds,
       SHELL_CMD_ARG(list, NULL, "List all harness points", cmd_list, 1, 0),
       SHELL_CMD_ARG(get, NULL, "Get harness point value: concord get <name>", cmd_get, 2, 0),
       SHELL_CMD_ARG(set, NULL, "Set harness point: concord set <name> <value>", cmd_set, 3, 0),
       SHELL_CMD_ARG(inject, NULL, "Inject action: concord inject <name> <value>", cmd_inject, 3, 0),
       SHELL_SUBCMD_SET_END
   );
   SHELL_CMD_REGISTER(concord, &concord_subcmds, "Concord harness commands", NULL);

4. Command implementations:

   cmd_list(shell, argc, argv):
   - Print [CONCORD:RSP] LIST_BEGIN
   - For each point (via concord_registry_foreach):
     Print [CONCORD:RSP] <TYPE> <name>
     where TYPE is GETTER/SETTER/INJECT/EVENT
   - Print [CONCORD:RSP] LIST_END

   cmd_get(shell, argc, argv):
   - argv[1] = point name
   - Look up point via concord_registry_find(name)
   - If not found: print [CONCORD:RSP] <name>=ERR:not_found
   - If found but type != GETTER: print [CONCORD:RSP] <name>=ERR:not_a_getter
   - If found and GETTER: call point->getter(), print [CONCORD:RSP] <name>=<result>

   cmd_set(shell, argc, argv):
   - argv[1] = point name, argv[2] = value
   - Look up point, verify type == SETTER
   - Call point->setter(value), print [CONCORD:RSP] <name>=<result>

   cmd_inject(shell, argc, argv):
   - argv[1] = point name, argv[2] = value
   - Look up point, verify type == INJECT
   - Call point->inject(value), print [CONCORD:RSP] <name>=<result>

5. Error handling:
   - Wrong argument count: let Zephyr shell handle (SHELL_CMD_ARG min/max args)
   - Point not found: ERR:not_found
   - Wrong point type for command: ERR:not_a_getter / ERR:not_a_setter / ERR:not_an_inject
   - Handler errors: handler returns "ERR:<reason>" which gets printed as-is

CRITICAL REQUIREMENTS:
- The [CONCORD:RSP] prefix must be EXACTLY "[CONCORD:RSP] " (with trailing space).
  The Python parser does a startswith() check on this exact string.
- One response line per command. No multi-line responses except for "list".
- Shell handlers must NOT block for extended periods. Getter/setter/inject
  handlers should return quickly. If a handler needs time (e.g., waiting for
  sensor), it should have its own timeout, not block the shell thread.
- Do NOT use printk or LOG_* for harness responses. Use shell_fprintf ONLY.
  This ensures responses go through the shell backend (UART0) and not through
  the Zephyr log backend (which may have different routing).
```

</details>

---

#### Step A6: Implement `concord_emit.c` (Event Emission)

**Effort:** 4h
**Depends on:** A2, A3 (needs types + CONCORD_EMIT declaration)
**Produces:** Thread-safe, non-blocking event emission over UART

<details>
<summary><strong>Agent Prompt (click to expand)</strong></summary>

```
TASK: Implement concord_emit.c — the asynchronous event emission system for
the concord harness.

FILE: concord_harness/zephyr/src/concord_emit.c

CONTEXT:
CONCORD_EMIT() is called from production source files (state machine .c files)
at runtime when interesting things happen (state transitions, sensor events).
It must be:
- Thread-safe (callable from ANY thread, including ISRs)
- Non-blocking (NEVER delays the calling thread)
- Asynchronous (a dedicated low-priority thread drains the queue to UART)

The event output format uses [CONCORD:EVT] prefix for host-side demuxing.

SPECIFICATION:

1. Required includes:
   - <zephyr/kernel.h>
   - <zephyr/sys/printk.h> or <zephyr/shell/shell.h>
   - <string.h>
   - <concord_harness/concord_harness_types.h>

2. Data structures:

   struct concord_event {
       char name[CONFIG_CONCORD_HARNESS_MAX_NAME_LEN];    // suggest 32
       char value[CONFIG_CONCORD_HARNESS_MAX_VALUE_LEN];  // suggest 64
   };

   Add these two Kconfig options to Kconfig (or use hardcoded reasonable
   defaults if you prefer simplicity for the proof):
   - CONFIG_CONCORD_HARNESS_MAX_NAME_LEN (int, default 32)
   - CONFIG_CONCORD_HARNESS_MAX_VALUE_LEN (int, default 64)

3. Message queue:

   K_MSGQ_DEFINE(concord_event_queue,
                  sizeof(struct concord_event),
                  CONFIG_CONCORD_HARNESS_EVENT_QUEUE_SIZE,
                  4);  // alignment

4. Public function (called by CONCORD_EMIT macro):

   void concord_emit_event(const char *name, const char *value)
   {
       struct concord_event evt;
       strncpy(evt.name, name, sizeof(evt.name) - 1);
       evt.name[sizeof(evt.name) - 1] = '\0';
       strncpy(evt.value, value, sizeof(evt.value) - 1);
       evt.value[sizeof(evt.value) - 1] = '\0';

       // Non-blocking put. If queue full, event is silently dropped.
       k_msgq_put(&concord_event_queue, &evt, K_NO_WAIT);
   }

5. Dedicated drain thread:

   K_THREAD_STACK_DEFINE(concord_emit_stack,
                         CONFIG_CONCORD_HARNESS_THREAD_STACK_SIZE);
   struct k_thread concord_emit_thread;

   static void concord_emit_thread_fn(void *p1, void *p2, void *p3)
   {
       struct concord_event evt;
       while (1) {
           // Block until event available
           k_msgq_get(&concord_event_queue, &evt, K_FOREVER);
           // Print with event prefix
           printk("[CONCORD:EVT] %s=%s\n", evt.name, evt.value);
       }
   }

   // Initialize thread at boot
   static int concord_emit_init(void)
   {
       k_thread_create(&concord_emit_thread, concord_emit_stack,
                       CONFIG_CONCORD_HARNESS_THREAD_STACK_SIZE,
                       concord_emit_thread_fn, NULL, NULL, NULL,
                       CONFIG_CONCORD_HARNESS_THREAD_PRIORITY,
                       0, K_NO_WAIT);
       k_thread_name_set(&concord_emit_thread, "concord_emit");
       return 0;
   }
   SYS_INIT(concord_emit_init, APPLICATION, 90);

6. Event output format (CRITICAL — host parser depends on this):
   [CONCORD:EVT] <name>=<value>

   Example:
   [CONCORD:EVT] app.state_changed=low_heat_risk_e
   [CONCORD:EVT] motion.state_changed=motion_in_motion

CRITICAL REQUIREMENTS:
- concord_emit_event() MUST use K_NO_WAIT. It must NEVER block.
  If the queue is full, the event is dropped. This is by design — we
  sacrifice event delivery guarantees to protect firmware timing.
- The drain thread runs at priority 14 (lowest preemptible). It should
  have zero impact on application timing.
- Use printk for event output, NOT shell_fprintf. Events are asynchronous
  and not associated with any shell session. printk goes to the console
  backend (UART0), which is what the host monitors.
- String copies in concord_emit_event must be bounded (strncpy with explicit
  null termination) to prevent buffer overflows.

DESIGN DECISION — printk vs shell:
Events use printk because they originate from arbitrary threads and are not
in response to a shell command. Shell responses (in concord_shell.c) use
shell_fprintf because they're in the context of a shell command handler.
Both go to UART0. The host demuxes by prefix: [CONCORD:RSP] vs [CONCORD:EVT].
```

</details>

---

#### Step A7: Finalize Kconfig, CMakeLists.txt, module.yml

**Effort:** 2h
**Depends on:** A2-A6 (all source files exist)
**Produces:** Fully buildable module, ready for integration

<details>
<summary><strong>Agent Prompt (click to expand)</strong></summary>

```
TASK: Finalize the build system files for the concord_harness module.

CONTEXT:
Steps A2-A6 have created all the source files. Now ensure the Kconfig,
CMakeLists.txt, and module.yml are complete and correct.

FILES TO UPDATE:

1. concord_harness/zephyr/Kconfig — should now include all config options:

   menuconfig CONCORD_HARNESS
       bool "Concord instrumentation harness"
       depends on SHELL && SHELL_BACKEND_SERIAL
       help
         Enable the concord harness module for integration testing.
         Adds shell commands (concord list/get/set/inject) and event
         emission (CONCORD_EMIT) for host-driven test automation.
         Compiles to nothing when disabled.

   if CONCORD_HARNESS

   config CONCORD_HARNESS_MAX_POINTS
       int "Maximum number of harness points"
       default 64

   config CONCORD_HARNESS_EVENT_QUEUE_SIZE
       int "Event emission queue depth"
       default 16

   config CONCORD_HARNESS_THREAD_STACK_SIZE
       int "Event emission thread stack size"
       default 2048

   config CONCORD_HARNESS_THREAD_PRIORITY
       int "Event emission thread priority"
       default 14
       help
         Lowest preemptible priority. Should not impact application timing.

   config CONCORD_HARNESS_MAX_NAME_LEN
       int "Maximum harness point name length"
       default 32

   config CONCORD_HARNESS_MAX_VALUE_LEN
       int "Maximum harness point/event value length"
       default 64

   endif # CONCORD_HARNESS

2. concord_harness/zephyr/CMakeLists.txt — should be:

   if(CONFIG_CONCORD_HARNESS)
     zephyr_library()
     zephyr_library_sources(
       src/concord_registry.c
       src/concord_shell.c
       src/concord_emit.c
     )
     zephyr_include_directories(include/)
   endif()

3. concord_harness/zephyr/module.yml — verify:

   name: concord_harness
   build:
     cmake: zephyr
     kconfig: zephyr/Kconfig

   NOTE: The 'cmake' path points to the DIRECTORY containing CMakeLists.txt,
   relative to the module root. The 'kconfig' path points to the Kconfig FILE,
   also relative to the module root.

VERIFICATION CHECKLIST:
- [ ] west can parse module.yml
- [ ] Kconfig parses without errors (try: kconfig-lint or just build)
- [ ] CMakeLists.txt only activates when CONFIG_CONCORD_HARNESS=y
- [ ] All source files compile (even if firmware project hasn't declared
      any harness points — the linker section would just be empty)
- [ ] When CONFIG_CONCORD_HARNESS=n, zero code is generated from the module

ALSO: Review all source files (A2-A6) for consistency:
- Do the struct field names in concord_harness_types.h match what the macros
  in concord_harness.h use?
- Do the section names match between STRUCT_SECTION_ITERABLE (in .h macros)
  and STRUCT_SECTION_FOREACH (in registry.c)?
- Does concord_shell.c call the right registry functions?
- Does concord_emit.c's concord_emit_event() match the declaration in .h?

This is the integration checkpoint for Stream A. Everything must be consistent.
```

</details>

---

### Stream B: Alpha Firmware Getter & Safety Changes

**Total effort:** ~5h
**Dependencies:** None — these are standalone alpha_fw changes
**Owner:** Firmware engineer (someone who knows the Alpha codebase)

These changes are small, unconditional improvements to the alpha_fw public
interface, plus one critical safety fix (UART0 RX kill guard).

---

#### Step B1: Move Type Definitions to Public Headers

**Effort:** 2h
**Depends on:** Nothing
**Produces:** `alpha_state_t` and `motion_state_t` accessible from external files

<details>
<summary><strong>Agent Prompt (click to expand)</strong></summary>

```
TASK: Move alpha_state_t and motion_state_t typedefs from .c files to their
corresponding .h headers in the Alpha firmware.

REPOSITORY: /home/mateo/work/firmware/alpha_fw/

CONTEXT:
Currently, alpha_state_t is defined inside alpha_state_machine.c and
motion_state_t is defined inside motion_state_machine.c. These types are
not visible outside their respective .c files. We need them in headers so
that:
1. The concord_harness.c file (added later) can reference them
2. Test files can reference them
3. It's a general improvement to the public interface

This change is UNCONDITIONAL — it's not behind any #ifdef. It's simply
moving a typedef from a .c file to its .h file. This improves the public
API regardless of the harness.

FILES TO MODIFY:

1. src/app/alpha_state_machine.c:
   - Find the typedef for alpha_state_t (an enum with states like
     off_body_e, low_heat_risk_e, increased_heat_risk_e, heat_emergency_e,
     off_body_validation_e)
   - REMOVE the typedef from this file
   - Add #include "alpha_state_machine.h" if not already present

2. src/app/alpha_state_machine.h:
   - ADD the alpha_state_t typedef (the exact enum moved from .c)
   - This makes it part of the public interface

3. src/app/motion_state_machine.c:
   - Find the typedef for motion_state_t (an enum with states like
     motion_is_stopped, motion_window_open, motion_in_motion)
   - REMOVE from this file

4. src/app/motion_state_machine.h:
   - ADD the motion_state_t typedef

IMPORTANT:
- Read both .c files first to find the exact typedef syntax and enum values.
- Make sure no other code in the .c files depends on the typedef being local
  (e.g., forward declarations, static variables of that type). If the static
  state variable `_state` is of type alpha_state_t, it should still compile
  fine since the .c file includes its own .h.
- Do NOT change any enum values, names, or ordering.
- Do NOT add any #ifdef guards around the typedef — this is an unconditional
  change.
- Verify the project still compiles after the change:
    cd /home/mateo/work/firmware/alpha_fw && west build -b alpha_b0
  (or whatever the current build command is — check build_all.sh)

VERIFICATION:
- alpha_fw compiles without errors
- No behavior change (types are just more visible now)
- grep for alpha_state_t in the codebase to make sure no other files were
  defining it independently (would cause duplicate typedef errors)
```

</details>

---

#### Step B2: Add Accessor Functions

**Effort:** 1h
**Depends on:** B1 (types must be in headers)
**Produces:** `get_alpha_state()` and `get_motion_state()` public functions

<details>
<summary><strong>Agent Prompt (click to expand)</strong></summary>

```
TASK: Add public accessor functions for the alpha and motion state machines.

REPOSITORY: /home/mateo/work/firmware/alpha_fw/

CONTEXT:
The state machines maintain internal _state variables (static in their .c
files). We need public accessor functions so the concord_harness.c file
(added later) can read the current state without accessing the static
variable directly.

These are UNCONDITIONAL additions — useful beyond just the harness (e.g.,
for logging, debugging, other modules that need to know current state).

FILES TO MODIFY:

1. src/app/alpha_state_machine.h:
   - Add declaration: alpha_state_t get_alpha_state(void);

2. src/app/alpha_state_machine.c:
   - Find the static state variable (likely named _state or similar,
     of type alpha_state_t)
   - Add implementation:
     alpha_state_t get_alpha_state(void)
     {
         return _state;  // (use whatever the actual variable name is)
     }

3. src/app/motion_state_machine.h:
   - Add declaration: motion_state_t get_motion_state(void);

4. src/app/motion_state_machine.c:
   - Find the static state variable
   - Add implementation:
     motion_state_t get_motion_state(void)
     {
         return _state;  // (use whatever the actual variable name is)
     }

IMPORTANT:
- Read the .c files first to identify the exact variable names.
- These are simple one-line functions. No locking needed — reading an enum
  is atomic on ARM Cortex-M.
- Place the function implementations near the top of the .c file, after
  the variable declarations.
- Verify compile after changes.

VERIFICATION:
- Project compiles
- Functions are accessible from other translation units (declared in .h)
```

</details>

---

#### Step B3: Guard UART0 RX Kill

**Effort:** 2h
**Depends on:** Nothing (independent fix)
**Produces:** UART0 stays alive when CONFIG_CONCORD_HARNESS=y

<details>
<summary><strong>Agent Prompt (click to expand)</strong></summary>

```
TASK: Add #ifdef CONFIG_CONCORD_HARNESS guard around the UART0 RX kill in
Alpha firmware's app.c.

REPOSITORY: /home/mateo/work/firmware/alpha_fw/

CONTEXT:
The Alpha firmware kills UART0 RX reception for power savings. The code
is in src/app/app.c and looks something like:

    NRF_UARTE0->TASKS_STOPRX = 1;

or similar direct register manipulation that disables UART0 receive.

This is a legitimate power optimization for production. But when the
concord_harness is enabled, we NEED UART0 RX to be active because the
shell receives commands over UART0.

If this isn't fixed, the entire Stage 3 concept is dead — no shell
commands can be received.

FILES TO MODIFY:

1. src/app/app.c (or wherever the UART0 disable code lives):
   - Find the line(s) that disable UART0 RX
   - Wrap with:
     #ifndef CONFIG_CONCORD_HARNESS
         NRF_UARTE0->TASKS_STOPRX = 1;  // (or whatever the actual code is)
     #endif

IMPORTANT:
- First, READ app.c thoroughly to find ALL places where UART0 is disabled
  or its RX is stopped. There might be multiple locations (init, sleep
  entry, power management callbacks).
- Search for: UARTE0, TASKS_STOPRX, uart_rx_disable, nrf_uarte_task_trigger,
  or any other UART0-related power management.
- Guard ALL such locations, not just one.
- The guard is #ifndef (NOT #ifdef) — we SKIP the UART kill when harness
  is enabled.
- This does NOT affect production builds. When CONFIG_CONCORD_HARNESS=n
  (the default), the UART0 kill code runs exactly as before.
- If you can't find the exact UART0 kill code, document what you searched
  for and where you looked. This is flagged as Risk R7 in the BOM and
  MUST be resolved.

VERIFICATION:
- Project compiles with default config (harness disabled) — UART0 kill active
- Project compiles with CONFIG_CONCORD_HARNESS=y — UART0 kill skipped
- No other behavioral changes
```

</details>

---

### Stream C: Hardware Setup

**Total effort:** ~18h + ~$200-400
**Dependencies:** Alpha board procurement (Step 0.1) must complete first
**Owner:** Hardware engineer + infra engineer

---

#### Step C1: Wire Alpha Board to MTIB Node

**Effort:** 16h
**Depends on:** Step 0.1 (Alpha board arrived), Step 0.2 (MTIB node identified)
**Produces:** Physical test fixture with SWD + UART + power connections

<details>
<summary><strong>Agent Prompt (click to expand)</strong></summary>

```
TASK: Wire an Alpha B0 product board to an MTIB edge node for Stage 3
integration testing.

CONTEXT:
The MTIB (Manufacturing Test Interface Board) node is a Verdin iMX8M Mini
running MTIB server v2. It provides gRPC-controlled access to debug probes,
UART, power supplies, and GPIO. We need to physically connect the Alpha
board to the MTIB node's test head.

CONNECTIONS REQUIRED:

1. SWD Debug (for flashing nRF52840 app MCU):
   - SWDIO: Alpha board nRF52840 SWD pad → MTIB debug probe SWDIO
   - SWCLK: Alpha board nRF52840 SWD pad → MTIB debug probe SWCLK
   - GND: Common ground
   - NOTE: The MTIB debug probe is either J-Link or CMSIS-DAP. Check which
     probe is connected to the target MTIB node.

2. UART0 (for shell commands + harness protocol):
   - Alpha nRF52840 UART0 TX (P0.23) → MTIB UART RX
   - Alpha nRF52840 UART0 RX (P0.25) → MTIB UART TX
   - GND: Common ground
   - Settings: 115200 baud, 8N1, no flow control

3. Power Supply:
   - MTIB programmable power supply → Alpha board power rail
   - Nominal 3.7V (simulating single-cell LiPo)
   - MTIB controls power on/off for reset cycles

4. Optional (nice-to-have for fuller testing, not required for proof):
   - Current sense: Inline on power rail for coarse system-level measurement
   - GPIO: Button pin for button press simulation
   - GPIO: Charger detect pin for charging test simulation

PHYSICAL CONSIDERATIONS:
- The Alpha board is a small wearable PCB. Test pads may need pogo pins
  or soldered fly wires for reliable connection.
- Label all connections clearly.
- Secure the board mechanically (3D-printed fixture tray or adhesive mount).
- Keep UART wires short (<30cm) to avoid signal integrity issues at 115200.
- If the Alpha board has a battery connector, either:
  a. Connect MTIB power through the battery connector, OR
  b. Connect to a direct power rail and leave battery disconnected

VERIFICATION:
- MTIB can detect the debug probe connected to the Alpha board
  (test via: mtib_client debug_connect or equivalent gRPC call)
- MTIB can power on/off the Alpha board
  (test via: DutPowerEnable / DutPowerDisable RPCs)
- UART loopback works: send bytes from MTIB → Alpha TX should echo if
  firmware has a shell enabled
```

</details>

---

#### Step C2: Register MTIB Node for Validation

**Effort:** 1h
**Depends on:** C1 (physical connections verified)
**Produces:** MTIB node labeled and queryable as a validation fixture

<details>
<summary><strong>Agent Prompt (click to expand)</strong></summary>

```
TASK: Register the Alpha validation MTIB node in the K3s cluster with
appropriate labels and annotations.

CONTEXT:
The Concord system uses Kubernetes labels on edge nodes to identify what
hardware is connected. For Stage 3, we need the MTIB node to be identifiable
as having an Alpha product board connected for integration testing.

K8S LABELS TO ADD (on the K3s node object):

  kubectl label node <node-name> \
    corekinect.com/purpose=validation \
    corekinect.com/fixture-type=product \
    corekinect.com/product=alpha \
    corekinect.com/board-rev=b0 \
    corekinect.com/capabilities-swd=true \
    corekinect.com/capabilities-uart=true \
    corekinect.com/capabilities-power=true

ANNOTATIONS TO ADD:

  kubectl annotate node <node-name> \
    corekinect.com/mtib-host=<node-ip> \
    corekinect.com/mtib-port=50052 \
    corekinect.com/fixture-description="Alpha B0 integration test fixture"

WHERE:
- <node-name>: The K3s node name for the MTIB edge device
- <node-ip>: The IP address of the MTIB node on the cluster network

VERIFICATION:
- kubectl get node <node-name> --show-labels | grep validation
- The node appears when filtering: kubectl get nodes -l corekinect.com/product=alpha
```

</details>

---

#### Step C3: Verify Flash + UART via MTIB

**Effort:** 1h
**Depends on:** C1, C2
**Produces:** Confirmed working flash + UART path, ready for integration testing

<details>
<summary><strong>Agent Prompt (click to expand)</strong></summary>

```
TASK: Verify that the MTIB node can flash firmware and communicate over
UART with the connected Alpha board.

CONTEXT:
Before we build the harness-instrumented firmware, we should verify the
basic toolchain works: flash a known-good firmware image and check UART
output.

VERIFICATION STEPS:

1. Build current Alpha firmware (no harness, stock):
   cd /home/mateo/work/firmware/alpha_fw
   west build -b alpha_b0  (or use build_all.sh)
   # Produces: build/nrf52840/zephyr/merged.hex (or similar)

2. Flash via MTIB:
   Use the MTIB client to call FlashProgram RPC:
   - Target: the registered validation node
   - Firmware: the built .hex file
   - Probe type: J-Link or CMSIS-DAP (whatever is connected)
   - Verify: FlashProgram returns success

3. Open UART stream via MTIB:
   Use the MTIB client to call UartStream RPC:
   - Baud: 115200
   - Config: 8N1, no flow control
   - Verify: You see boot log output from the Alpha firmware

4. If the current firmware has any shell commands:
   Try sending a command over UART and verify response
   (The stock firmware may not have shell enabled — that's OK, we just
   need to verify UART TX from the device works)

5. Test power cycling:
   - Call DutPowerDisable → verify UART output stops
   - Call DutPowerEnable → verify device boots and UART output resumes

EXPECTED ISSUES:
- If UART shows garbage: check baud rate, check TX/RX aren't swapped
- If flash fails: check SWD wiring, check debug probe detection
- If no UART output at all: the stock firmware may not have LOG enabled,
  or UART0 may be configured differently. Check prj.conf for CONFIG_LOG
  and UART settings.

SUCCESS CRITERIA:
- Flash succeeds
- UART shows recognizable output (boot messages or at least no garbage)
- Power cycling works cleanly
```

</details>

---

## Phase 2: Harness Integration

These streams depend on Phase 1 completing. Stream D needs both Stream A
(the module) and Stream B (the getters). Stream E can start partially in
parallel — I10 and I14 have no dependency on Stream A.

---

### Stream D: Alpha Firmware Harness Integration

**Total effort:** ~30h
**Dependencies:** Stream A complete (concord_harness module exists), Stream B complete (getters + UART fix)
**Owner:** Firmware engineer (or infra engineer with FW knowledge)

---

#### Step D1: Write `alpha_fw/src/concord_harness.c`

**Effort:** 16h
**Depends on:** Stream A (F28 API), Stream B (B1 types + B2 accessors)
**Produces:** All harness point declarations for the Alpha firmware
**This is the biggest single step in Stream D.**

<details>
<summary><strong>Agent Prompt (click to expand)</strong></summary>

```
TASK: Create concord_harness.c — the harness point declarations for Alpha
firmware.

REPOSITORY: /home/mateo/work/firmware/alpha_fw/
FILE TO CREATE: src/concord_harness.c

CONTEXT:
This file uses the CONCORD_GETTER, CONCORD_SETTER, CONCORD_INJECT, and
CONCORD_EVENT macros from the concord_harness module to declare all
observable and controllable points in the Alpha firmware. This is the
product-specific code that "plugs into" the generic harness framework.

The file is conditionally compiled (only when CONFIG_CONCORD_HARNESS=y)
via CMakeLists.txt. It should include the concord_harness.h header and
any Alpha firmware headers it needs.

HARNESS POINTS TO DECLARE:

=== GETTERS (read-only observation) ===

1. "app.state" — Current heat stress state machine state
   Uses: get_alpha_state() from alpha_state_machine.h
   Needs: alpha_state_to_str() helper (define locally in this file)
   Returns: "off_body_e", "low_heat_risk_e", "increased_heat_risk_e",
            "heat_emergency_e", "off_body_validation_e"

2. "motion.state" — Current motion state machine state
   Uses: get_motion_state() from motion_state_machine.h
   Needs: motion_state_to_str() helper (define locally)
   Returns: "motion_is_stopped", "motion_window_open", "motion_in_motion"

3. "sensor.on_body" — Whether device thinks it's on a body
   Uses: is_device_on_body() from vsm_handler.h (or wherever it's declared)
   Returns: "true" or "false"

4. "sensor.hr" — Current heart rate reading
   Uses: get_vsm_data() which returns a struct with heartrate field
   Returns: numeric string, e.g. "72"

5. "battery.soc" — Battery state of charge percentage
   Uses: get_battery_percent() or equivalent fuel gauge accessor
   Returns: numeric string, e.g. "85"

=== SETTERS (writable configuration) ===

6. "config.motion_start_sec" — Motion detection start threshold
   Uses: set_motion_config() or equivalent
   Validates: integer 1-255
   Returns: "OK" or "ERR:range"

=== INJECTIONS (trigger firmware actions) ===

7. "sensor.touch" — Simulate touch detection/removal
   This is the ADAPTER PATTERN — translates string command to internal mechanism.
   For the current Alpha firmware (polling-based):
   - "detected": Set a harness override flag, wake main loop
   - "removed": Clear the override flag, wake main loop
   Needs: A concord_force_on_body() function in vsm_handler.c (see D1-helper below)
   Returns: "OK" or "ERR:expected detected|removed"

8. "device.reset" — Trigger a software reset
   Uses: sys_reboot(SYS_REBOOT_COLD) from <zephyr/sys/reboot.h>
   Returns: "OK" (though the device will reset before the response is sent)

=== EVENTS (declared here, emitted from state machine .c files) ===

9. CONCORD_EVENT("app.state_changed")
   — Emitted by alpha_state_machine.c at each state transition

10. CONCORD_EVENT("motion.state_changed")
    — Emitted by motion_state_machine.c at each transition

HELPER FUNCTIONS (local to this file):

static const char *alpha_state_to_str(alpha_state_t s)
{
    switch (s) {
    case off_body_e:             return "off_body_e";
    case low_heat_risk_e:        return "low_heat_risk_e";
    case increased_heat_risk_e:  return "increased_heat_risk_e";
    case heat_emergency_e:       return "heat_emergency_e";
    case off_body_validation_e:  return "off_body_validation_e";
    default:                     return "unknown";
    }
}

static const char *motion_state_to_str(motion_state_t s)
{
    switch (s) {
    case motion_is_stopped:  return "motion_is_stopped";
    case motion_window_open: return "motion_window_open";
    case motion_in_motion:   return "motion_in_motion";
    default:                 return "unknown";
    }
}

INJECTION HELPER (requires modification to vsm_handler.c):

For "sensor.touch" injection to work, vsm_handler.c needs:

  #ifdef CONFIG_CONCORD_HARNESS
  static bool _harness_on_body_override = false;
  static bool _harness_on_body_value = false;

  void concord_force_on_body(bool on_body)
  {
      _harness_on_body_override = true;
      _harness_on_body_value = on_body;
  }

  void concord_clear_on_body_override(void)
  {
      _harness_on_body_override = false;
  }
  #endif

And the existing is_device_on_body() function needs a harness check:

  bool is_device_on_body(void)
  {
  #ifdef CONFIG_CONCORD_HARNESS
      if (_harness_on_body_override) return _harness_on_body_value;
  #endif
      return _vsm_flags[is_on_body];  // (original implementation)
  }

Also need a way to wake the main loop after injection. Look for a semaphore,
event flag, or timer tick that the main loop blocks on. If the main loop
polls on a timer, the injection will take effect on the next poll cycle.
If it blocks on a semaphore, you need to give that semaphore to wake it
immediately.

CMAKELISTS.TXT UPDATE:

In src/CMakeLists.txt (or wherever Alpha sources are listed), add:

  if(CONFIG_CONCORD_HARNESS)
    target_sources(app PRIVATE concord_harness.c)
  endif()

IMPORTANT NOTES:
- READ the Alpha firmware source files before writing this. The function
  names, struct names, and patterns above are based on architecture docs
  and may not match exactly. Verify against actual code.
- The to-string helpers should match the EXACT enum value names used in
  the firmware (the enum values from B1).
- All getters that return numeric values should use a static char buffer
  for snprintf (the returned pointer must remain valid after the getter
  returns — static buffer ensures this).
- The touch injection is the most complex part. Study how is_device_on_body()
  is used in the state machine before implementing.
- If any accessor function doesn't exist yet (e.g., get_battery_percent()),
  check what DOES exist and adapt. Document any functions that need to be
  added.

VERIFICATION:
- Compiles with CONFIG_CONCORD_HARNESS=y
- Compiles WITHOUT CONFIG_CONCORD_HARNESS (file is excluded by CMake)
- Production build is bit-identical to before these changes
```

</details>

---

#### Step D2: Add CONCORD_EMIT Calls to State Machines

**Effort:** 3h
**Depends on:** Stream A (CONCORD_EMIT macro exists), B1 (types in headers)
**Produces:** State transition events visible on UART

<details>
<summary><strong>Agent Prompt (click to expand)</strong></summary>

```
TASK: Add CONCORD_EMIT() calls at state transition points in the Alpha
firmware state machines.

REPOSITORY: /home/mateo/work/firmware/alpha_fw/

CONTEXT:
CONCORD_EMIT() is a macro from concord_harness.h that, when
CONFIG_CONCORD_HARNESS=y, calls concord_emit_event() to queue an event
for UART output. When CONFIG_CONCORD_HARNESS=n, it expands to nothing.

We add CONCORD_EMIT() at every state transition so the Python test runner
can observe state changes in real-time without polling.

FILES TO MODIFY:

1. src/app/alpha_state_machine.c:
   Add at the top:
     #include <concord_harness/concord_harness.h>

   At every state transition (where _state is assigned a new value), add
   a CONCORD_EMIT call. For example, if the code looks like:

     case off_body_e:
         if (is_device_on_body()) {
             _state = low_heat_risk_e;
             // ... other logic
         }
         break;

   Add after the state assignment:
     _state = low_heat_risk_e;
     CONCORD_EMIT("app.state_changed", "low_heat_risk_e");

   Do this for EVERY transition in the state machine:
   - off_body_e → low_heat_risk_e
   - off_body_e → off_body_validation_e
   - off_body_validation_e → low_heat_risk_e
   - off_body_validation_e → off_body_e
   - low_heat_risk_e → increased_heat_risk_e
   - low_heat_risk_e → off_body_e (or off_body_validation_e)
   - increased_heat_risk_e → heat_emergency_e
   - increased_heat_risk_e → low_heat_risk_e
   - heat_emergency_e → off_body_e
   (Verify exact transitions by reading the state machine code)

2. src/app/motion_state_machine.c:
   Add at the top:
     #include <concord_harness/concord_harness.h>

   At every state transition:
   - motion_is_stopped → motion_window_open
   - motion_window_open → motion_in_motion
   - motion_in_motion → motion_is_stopped
   - motion_window_open → motion_is_stopped
   (Verify exact transitions by reading the code)

IMPORTANT:
- The event value strings MUST match the enum value names exactly
  (same strings as alpha_state_to_str / motion_state_to_str in D1).
- CONCORD_EMIT is non-blocking and ISR-safe. It's OK to call it from
  any context.
- The include of concord_harness.h is safe even when the module isn't
  enabled — the header has a #else clause where everything is empty.
- Place CONCORD_EMIT immediately AFTER the state assignment, not before.
- Do NOT add CONCORD_EMIT for the "stay in same state" case (no transition).

READ THE ACTUAL STATE MACHINE CODE before making changes. The transition
points described above are from architecture docs and may not exactly match
the actual implementation structure. Adapt as needed.

VERIFICATION:
- Compiles with CONFIG_CONCORD_HARNESS=y
- Compiles with CONFIG_CONCORD_HARNESS=n (EMIT becomes nothing)
- Binary with CONFIG_CONCORD_HARNESS=n is identical to before
```

</details>

---

#### Step D3: Create Alpha B0 Harness Overlay

**Effort:** 2h
**Depends on:** A7 (module build system complete)
**Produces:** Overlay config file that enables harness for Alpha B0 builds

<details>
<summary><strong>Agent Prompt (click to expand)</strong></summary>

```
TASK: Create a Kconfig overlay file for building Alpha firmware with the
concord harness enabled.

REPOSITORY: /home/mateo/work/firmware/alpha_fw/

CONTEXT:
The Alpha firmware's default prj.conf should NOT change — production builds
must remain untouched. Instead, we create an overlay file that enables the
harness and its dependencies when explicitly requested.

The overlay will be used like:
  west build -b alpha_b0 -- -DOVERLAY_CONFIG=boards/alpha_b0_harness.conf

Or it could be in boards/alpha_b0.conf if you want board-specific config
(check how the existing build system handles per-board overlays).

FILE TO CREATE: boards/alpha_b0_harness.conf
(or an appropriate overlay path for the alpha_fw build system)

CONTENT:

# Concord harness for integration testing
CONFIG_CONCORD_HARNESS=y

# Required dependencies
CONFIG_SHELL=y
CONFIG_SHELL_BACKEND_SERIAL=y

# Shell configuration for harness use
CONFIG_SHELL_PROMPT_UART=""
CONFIG_SHELL_VT100_COMMANDS=n
CONFIG_SHELL_WILDCARD=n
CONFIG_SHELL_ECHO_STATUS=n

# Keep logging enabled (useful for debugging during tests)
CONFIG_LOG=y
CONFIG_LOG_MODE_DEFERRED=y

# UART0 must stay active (B3 guard prevents the RX kill)
# No explicit UART config needed — default UART0 at 115200 is correct

# Harness tuning (defaults are fine for proof, but explicit for clarity)
CONFIG_CONCORD_HARNESS_EVENT_QUEUE_SIZE=16
CONFIG_CONCORD_HARNESS_THREAD_STACK_SIZE=2048
CONFIG_CONCORD_HARNESS_THREAD_PRIORITY=14

ALSO CHECK:
- Does the Alpha firmware's west.yml or west manifest need updating to
  include the concord_harness module? It needs a manifest entry like:

  projects:
    - name: concord_harness
      url: <repo-url>
      revision: main
      path: modules/concord_harness

  Or if using a local path for the proof:
    - name: concord_harness
      path: /home/mateo/work/firmware/concord_harness
      # Use local path during development

- Does the Alpha firmware's build_all.sh need a new target for
  instrumented builds? Or is the overlay sufficient?

VERIFICATION:
- west build -b alpha_b0 -- -DOVERLAY_CONFIG=boards/alpha_b0_harness.conf
  succeeds
- The resulting binary has the shell and harness enabled
- west build -b alpha_b0 (without overlay) still builds stock production firmware
- Compare binary sizes: instrumented should be larger (shell + harness thread)
```

</details>

---

#### Step D4: Build & Verify Instrumented Firmware

**Effort:** 4h (includes debugging)
**Depends on:** D1, D2, D3 + Stream A fully complete
**Produces:** Working instrumented firmware binary, ready for flashing

<details>
<summary><strong>Agent Prompt (click to expand)</strong></summary>

```
TASK: Build the harness-instrumented Alpha firmware and verify it works
on real hardware.

REPOSITORY: /home/mateo/work/firmware/alpha_fw/

CONTEXT:
This is the integration checkpoint for the firmware side. All pieces are
in place:
- concord_harness module exists (Stream A)
- alpha_fw has getters, UART fix, harness declarations (Stream B + D1-D3)
- Alpha board is wired to MTIB (Stream C)

STEPS:

1. Build instrumented firmware:
   cd /home/mateo/work/firmware/alpha_fw
   west build -b alpha_b0 -- -DOVERLAY_CONFIG=boards/alpha_b0_harness.conf

   Fix any build errors. Common issues:
   - Missing includes (concord_harness.h not found → check west manifest)
   - Linker errors (section name mismatch between macro and registry)
   - Type errors (wrong function signature in getter/setter/inject)

2. Also build production firmware (regression check):
   west build -b alpha_b0
   Verify this still compiles without errors.

3. Flash instrumented firmware via MTIB:
   Use the MTIB client to flash the instrumented .hex to the Alpha board.

4. Open UART stream via MTIB and verify harness:

   a. Wait for boot to complete (look for shell prompt or boot log)
   b. Send: concord list
      Expected: [CONCORD:RSP] LIST_BEGIN followed by entries for all
      registered points (app.state, motion.state, sensor.on_body, etc.)
      followed by [CONCORD:RSP] LIST_END

   c. Send: concord get app.state
      Expected: [CONCORD:RSP] app.state=off_body_e (or current state)

   d. Send: concord get motion.state
      Expected: [CONCORD:RSP] motion.state=motion_is_stopped

   e. Send: concord get sensor.on_body
      Expected: [CONCORD:RSP] sensor.on_body=false

   f. Send: concord inject sensor.touch detected
      Expected: [CONCORD:RSP] sensor.touch=OK
      Then shortly after: [CONCORD:EVT] app.state_changed=low_heat_risk_e
      (if the state machine transitions from off_body to low_heat_risk)

   g. Send: concord get app.state
      Expected: [CONCORD:RSP] app.state=low_heat_risk_e

   h. Send: concord inject sensor.touch removed
      Expected: [CONCORD:RSP] sensor.touch=OK
      Then: [CONCORD:EVT] app.state_changed=off_body_validation_e
      (or off_body_e, depending on whether validation window triggers)

5. Document any issues, unexpected behavior, or deviations from expected
   responses. These will inform the Python test scripts in Phase 3.

SUCCESS CRITERIA:
- "concord list" returns all expected harness points
- "concord get" returns correct current values
- "concord inject sensor.touch detected" causes a state transition
- State transition emits [CONCORD:EVT] event
- Device remains stable (no crashes, no watchdog resets)
- Production build (without overlay) compiles and is unchanged

THIS IS THE KEY MILESTONE. If this step works, Stage 3 is proven in principle.
Everything after this is wrapping it in Python automation.
```

</details>

---

### Stream E: Python Test Infrastructure

**Total effort:** ~28h
**Dependencies:** Partial — I10 and I14 can start in parallel with Stream A.
I17 (harness_client) needs the protocol specification from Stream A.
**Owner:** Infra engineer

---

#### Step E1: Implement `harness_client.py`

**Effort:** 12h
**Depends on:** Stream A (protocol specification from A5, A6)
**Produces:** Python class that sends harness commands and captures events over UART

<details>
<summary><strong>Agent Prompt (click to expand)</strong></summary>

```
TASK: Implement harness_client.py — the Python client for the concord_harness
UART protocol.

REPOSITORY: /home/mateo/work/concord/concord/
FILE TO CREATE: apps/validation/test-runner/src/harness_client.py

CONTEXT:
This module provides a Python class that communicates with the concord_harness
shell commands over UART (via MTIB's UartStream gRPC). It handles:
- Sending shell commands (get, set, inject, list)
- Parsing [CONCORD:RSP] responses
- Capturing [CONCORD:EVT] events asynchronously
- Demultiplexing UART output into harness responses, events, and device logs

The UART stream is provided by the MTIB client (a gRPC bidirectional stream).
This module wraps that stream with harness-specific protocol logic.

CLASS DESIGN:

class HarnessClient:
    """Client for the concord_harness UART shell protocol."""

    def __init__(self, uart_stream):
        """
        Args:
            uart_stream: An object that provides send(bytes) and
                        receive() -> bytes methods. This is the MTIB
                        UartStream gRPC bidirectional stream.
        """
        self._uart = uart_stream
        self._event_queue = queue.Queue()
        self._response_event = threading.Event()
        self._last_response = None
        self._log_buffer = []
        self._reader_thread = threading.Thread(target=self._reader_loop, daemon=True)
        self._reader_thread.start()

    def _reader_loop(self):
        """Background thread that reads UART and demuxes by prefix."""
        line_buffer = ""
        while True:
            data = self._uart.receive()  # blocks until data available
            if data is None:
                break
            line_buffer += data.decode('utf-8', errors='replace')
            while '\n' in line_buffer:
                line, line_buffer = line_buffer.split('\n', 1)
                line = line.strip()
                if not line:
                    continue
                if line.startswith("[CONCORD:RSP] "):
                    payload = line[len("[CONCORD:RSP] "):]
                    self._last_response = payload
                    self._response_event.set()
                elif line.startswith("[CONCORD:EVT] "):
                    payload = line[len("[CONCORD:EVT] "):]
                    name, _, value = payload.partition('=')
                    self._event_queue.put({"name": name, "value": value})
                else:
                    self._log_buffer.append(line)

    def _send_command(self, cmd: str, timeout: float = 5.0) -> str:
        """Send a shell command and wait for [CONCORD:RSP] response."""
        self._response_event.clear()
        self._last_response = None
        self._uart.send((cmd + "\n").encode('utf-8'))
        if not self._response_event.wait(timeout=timeout):
            raise TimeoutError(f"No response to: {cmd}")
        return self._last_response

    def list_points(self) -> list[dict]:
        """Send 'concord list' and parse the response.
        Returns list of {"type": str, "name": str} dicts.
        """
        # Send command, collect responses until LIST_END
        self._response_event.clear()
        self._uart.send(b"concord list\n")
        points = []
        deadline = time.time() + 5.0
        while time.time() < deadline:
            self._response_event.wait(timeout=1.0)
            self._response_event.clear()
            resp = self._last_response
            if resp == "LIST_BEGIN":
                continue
            elif resp == "LIST_END":
                break
            elif resp:
                parts = resp.split(" ", 1)
                if len(parts) == 2:
                    points.append({"type": parts[0], "name": parts[1]})
        return points

    def get(self, name: str, timeout: float = 5.0) -> str:
        """Send 'concord get <name>' and return the value string."""
        resp = self._send_command(f"concord get {name}", timeout)
        # resp format: "<name>=<value>"
        _, _, value = resp.partition('=')
        return value

    def set(self, name: str, value: str, timeout: float = 5.0) -> str:
        """Send 'concord set <name> <value>' and return result."""
        resp = self._send_command(f"concord set {name} {value}", timeout)
        _, _, result = resp.partition('=')
        return result

    def inject(self, name: str, value: str, timeout: float = 5.0) -> str:
        """Send 'concord inject <name> <value>' and return result."""
        resp = self._send_command(f"concord inject {name} {value}", timeout)
        _, _, result = resp.partition('=')
        return result

    def wait_event(self, name: str, timeout: float = 10.0) -> str | None:
        """Wait for a specific [CONCORD:EVT] event by name.
        Returns the event value, or None on timeout.
        Discards events that don't match the name.
        """
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                remaining = deadline - time.time()
                evt = self._event_queue.get(timeout=max(0.1, remaining))
                if evt["name"] == name:
                    return evt["value"]
                # Non-matching event, continue waiting
            except queue.Empty:
                return None
        return None

    def drain_events(self) -> list[dict]:
        """Drain all pending events from the queue."""
        events = []
        while not self._event_queue.empty():
            try:
                events.append(self._event_queue.get_nowait())
            except queue.Empty:
                break
        return events

    def get_logs(self) -> list[str]:
        """Return and clear the device log buffer."""
        logs = list(self._log_buffer)
        self._log_buffer.clear()
        return logs

IMPORTANT NOTES:
- The UART stream abstraction should be flexible enough to work with
  the actual MTIB UartStream gRPC stream. You may need to adapt the
  interface depending on how the mtib_client exposes UART.
- The reader thread MUST handle partial lines (UART data arrives in
  chunks, not necessarily line-aligned).
- The list command is special: it produces multiple response lines.
  The implementation above collects lines between LIST_BEGIN and LIST_END.
- Thread safety: the event queue is thread-safe (queue.Queue). The
  response mechanism uses threading.Event for signaling.
- Consider edge cases: what if the device resets mid-command? What if
  multiple commands are sent before responses arrive?
- For the proof-of-concept, keep error handling simple. Production
  hardening comes later.

ALSO: Write basic unit tests for the parsing logic (can test with mock
uart_stream that feeds known byte sequences).

VERIFICATION:
- Unit tests pass with mocked UART stream
- Can parse sample UART output:
    "[CONCORD:RSP] app.state=off_body_e"
    "[CONCORD:EVT] app.state_changed=low_heat_risk_e"
    "*** Booting Zephyr OS build v3.4.0 ***"  (→ goes to log buffer)
```

</details>

---

#### Step E2: Implement `fixture_controller.py`

**Effort:** 12h
**Depends on:** E3 (mtib_client updates)
**Produces:** Abstraction layer mapping test actions to MTIB gRPC RPCs

<details>
<summary><strong>Agent Prompt (click to expand)</strong></summary>

```
TASK: Implement fixture_controller.py — the abstraction layer between
integration tests and the MTIB hardware interface.

REPOSITORY: /home/mateo/work/concord/concord/
FILE TO CREATE: apps/validation/test-runner/src/fixture_controller.py

CONTEXT:
Integration tests need to perform hardware actions: flash firmware, open
UART, power cycle, etc. These actions are implemented by MTIB gRPC RPCs.
The fixture controller provides a clean abstraction so test scripts don't
call gRPC directly.

This also allows tests to be written once and run on different fixture
types (dev-kit vs product board) by swapping the fixture controller
configuration.

CLASS DESIGN:

class FixtureController:
    """Controls a test fixture via MTIB gRPC."""

    def __init__(self, mtib_host: str, mtib_port: int = 50052):
        """Connect to the MTIB node."""
        self._client = MtibClient(host=mtib_host, port=mtib_port)
        self._uart_stream = None

    def flash(self, hex_path: str, target: str = "nrf52840") -> bool:
        """Flash firmware to the DUT.
        Args:
            hex_path: Path to .hex file
            target: MCU target identifier
        Returns: True on success
        """
        # Call FlashProgram RPC
        # Handle: erase, program, verify, reset
        pass

    def power_on(self) -> bool:
        """Enable DUT power supply."""
        # Call DutPowerEnable RPC
        pass

    def power_off(self) -> bool:
        """Disable DUT power supply."""
        # Call DutPowerDisable RPC
        pass

    def power_cycle(self, off_duration: float = 1.0) -> bool:
        """Power cycle the DUT."""
        self.power_off()
        time.sleep(off_duration)
        self.power_on()
        return True

    def reset(self) -> bool:
        """Reset the DUT via debug probe."""
        # Call DebugReset RPC
        pass

    def open_uart(self, baud: int = 115200) -> UartStream:
        """Open a UART stream to the DUT.
        Returns: A stream object suitable for HarnessClient.
        """
        # Call UartStream RPC (bidirectional streaming)
        # Return an adapter that provides send(bytes) and receive() -> bytes
        self._uart_stream = self._client.uart_stream(baud=baud)
        return self._uart_stream

    def close_uart(self):
        """Close the UART stream."""
        if self._uart_stream:
            self._uart_stream.close()
            self._uart_stream = None

    def close(self):
        """Clean up all connections."""
        self.close_uart()
        self._client.close()

IMPLEMENTATION NOTES:
- Look at the existing MTIB client v2 at:
  /home/mateo/work/concord/concord/libs/python/corekinect/mtib_client/v2/
  Read the existing code to understand:
  a. How to connect to the MTIB gRPC server
  b. What the FlashProgram, DutPowerEnable, DutPowerDisable, DebugReset,
     and UartStream RPCs look like
  c. What protobuf messages are used
  d. How bidirectional streaming (UartStream) is handled

- The MTIB protobuf definitions are at:
  /home/mateo/work/concord/concord/libs/protocols/mtib_v2/
  Read these to understand the exact RPC signatures and message types.

- The UartStream adapter needs to bridge between gRPC streaming and the
  simple send/receive interface expected by HarnessClient (E1).

- For the proof-of-concept, error handling can be minimal. Log errors,
  raise exceptions on critical failures (flash failed, UART won't open).

- Consider adding a wait_for_boot() method that opens UART and waits
  until it sees recognizable boot output (or the shell prompt, or
  [CONCORD:RSP] from a "concord list" probe).

VERIFICATION:
- Can connect to a real MTIB node
- Can flash firmware
- Can open UART and read device output
- Can power cycle the device
```

</details>

---

#### Step E3: MTIB Client Updates

**Effort:** 4h
**Depends on:** Nothing (existing code)
**Produces:** Any minor fixes/additions needed in the mtib_client for test runner use

<details>
<summary><strong>Agent Prompt (click to expand)</strong></summary>

```
TASK: Review and update the MTIB client v2 Python library for use by the
Stage 3 test runner.

REPOSITORY: /home/mateo/work/concord/concord/

EXISTING CODE:
- MTIB client: libs/python/corekinect/mtib_client/v2/
- MTIB protobufs: libs/protocols/mtib_v2/

CONTEXT:
The MTIB client v2 is an existing Python gRPC wrapper around the MTIB
server's 71 RPCs. It's currently used by manufacturing test steps. We need
to verify it works for our Stage 3 use case and make any minor updates.

REVIEW CHECKLIST:

1. UartStream RPC:
   - Does the client support bidirectional UART streaming?
   - Can we send and receive bytes asynchronously?
   - Is there a clean way to open a stream with configurable baud rate?
   - If the existing API is clunky for our use case, consider adding a
     convenience wrapper (but prefer using existing API if possible).

2. FlashProgram RPC:
   - Does the client support flashing a .hex file?
   - Does it handle erase + program + verify + reset?
   - What's the error reporting like?

3. Power control RPCs:
   - DutPowerEnable / DutPowerDisable — are these exposed in the client?
   - Any voltage configuration needed?

4. DebugReset RPC:
   - Is this exposed? Can we reset the MCU without re-flashing?

5. Connection management:
   - How does the client handle connection lifecycle?
   - Is there proper cleanup / channel shutdown?

DELIVERABLES:
- Document any issues found
- Make minimal fixes if needed (e.g., missing RPC wrappers, broken streaming)
- Do NOT refactor the entire client — only fix what's needed for Stage 3
- If the client works as-is, document that and note the API patterns that
  fixture_controller.py (E2) should use

IMPORTANT:
- Read the existing code thoroughly before making changes
- Check if there are existing tests or usage examples
- The mtib_client is used by manufacturing — don't break existing consumers
```

</details>

---

## Phase 3: End-to-End Proof

Everything comes together. Write and run integration tests on real hardware.

---

### Stream F: Integration Tests

**Total effort:** ~28h
**Dependencies:** Stream C (hardware ready), Stream D (instrumented firmware), Stream E (Python infra)
**Owner:** Infra engineer + firmware engineer (pair recommended)

---

#### Step F1: Write `integration_spec.yaml`

**Effort:** 4h
**Depends on:** D4 (know exactly what harness points are available)
**Produces:** Declarative test specification

<details>
<summary><strong>Agent Prompt (click to expand)</strong></summary>

```
TASK: Create integration_spec.yaml — the declarative specification for
Stage 3 integration tests on Alpha firmware.

REPOSITORY: /home/mateo/work/firmware/alpha_fw/
FILE TO CREATE: .concord/integration_spec.yaml

CONTEXT:
This file declares what integration tests exist, what harness points they
use, and what firmware build they require. It's used by the test runner
to know what to execute.

For the proof-of-concept, we keep it simple: list the test modules and
their requirements.

CONTENT:

version: 1
product: alpha
board: alpha_b0
firmware:
  overlay: boards/alpha_b0_harness.conf

tests:
  - name: test_state_machine_transitions
    module: tests/integration/test_state_machine.py
    description: "Verify heat stress state machine transitions via harness injection"
    harness_points:
      - app.state (GETTER)
      - sensor.touch (INJECT)
      - app.state_changed (EVENT)
    timeout: 120  # seconds

  - name: test_motion_state_machine
    module: tests/integration/test_motion_state_machine.py
    description: "Verify motion state machine basic transitions"
    harness_points:
      - motion.state (GETTER)
      - motion.state_changed (EVENT)
    timeout: 60

  - name: test_harness_discovery
    module: tests/integration/test_harness_discovery.py
    description: "Verify all expected harness points are registered"
    harness_points: []  # uses concord list
    timeout: 30

  - name: test_sensor_on_body
    module: tests/integration/test_sensor_on_body.py
    description: "Verify on-body detection injection and state response"
    harness_points:
      - sensor.on_body (GETTER)
      - sensor.touch (INJECT)
      - app.state (GETTER)
    timeout: 60

  - name: test_off_body_validation_window
    module: tests/integration/test_off_body_validation.py
    description: "Verify 20-second off-body validation timer"
    harness_points:
      - app.state (GETTER)
      - sensor.touch (INJECT)
      - app.state_changed (EVENT)
    timeout: 90  # needs extra time for the 20-sec timer

NOTE: This spec is minimal for the proof. A full spec would include power
budget assertions, timing constraints, and more test scenarios. Keep it
focused on proving the harness works.
```

</details>

---

#### Step F2: Write Integration Test Python Modules

**Effort:** 20h
**Depends on:** E1 (harness_client.py), E2 (fixture_controller.py), D4 (verified harness points)
**Produces:** 5 test modules that exercise the harness on real hardware

<details>
<summary><strong>Agent Prompt (click to expand)</strong></summary>

```
TASK: Write the Python integration test modules for Stage 3 proof-of-concept.

REPOSITORY: /home/mateo/work/firmware/alpha_fw/
DIRECTORY TO CREATE: .concord/tests/integration/

CONTEXT:
These test modules use harness_client.py (from the Concord monorepo) and
fixture_controller.py to interact with Alpha firmware running on real
hardware via MTIB. Each test module is a standalone Python file that:
1. Connects to the MTIB node
2. Flashes instrumented firmware (or assumes it's already flashed)
3. Opens UART and creates a HarnessClient
4. Exercises harness points and asserts expected behavior
5. Reports pass/fail

For the proof-of-concept, use pytest as the test framework.

TEST MODULES TO CREATE:

=== 1. test_harness_discovery.py ===
Purpose: Verify all expected harness points are registered.

def test_harness_list_returns_all_points(harness):
    """Verify 'concord list' returns all expected points."""
    points = harness.list_points()
    names = {p["name"] for p in points}

    # Expected points from D1
    expected = {
        "app.state", "motion.state", "sensor.on_body",
        "sensor.hr", "battery.soc",
        "config.motion_start_sec",
        "sensor.touch", "device.reset",
        "app.state_changed", "motion.state_changed",
    }
    assert expected.issubset(names), f"Missing: {expected - names}"

def test_harness_point_types(harness):
    """Verify each point has the correct type."""
    points = harness.list_points()
    type_map = {p["name"]: p["type"] for p in points}

    assert type_map["app.state"] == "GETTER"
    assert type_map["sensor.touch"] == "INJECT"
    assert type_map["config.motion_start_sec"] == "SETTER"
    assert type_map["app.state_changed"] == "EVENT"


=== 2. test_state_machine.py ===
Purpose: Verify heat stress state machine transitions.

def test_initial_state_is_off_body(harness):
    """After boot, device should be in off_body state."""
    state = harness.get("app.state")
    assert state == "off_body_e"

def test_touch_detected_transitions_to_low_heat_risk(harness):
    """Injecting touch detected should transition to low_heat_risk."""
    # Ensure we start in off_body
    assert harness.get("app.state") == "off_body_e"

    # Drain any pending events
    harness.drain_events()

    # Inject touch
    result = harness.inject("sensor.touch", "detected")
    assert result == "OK"

    # Wait for state change event
    new_state = harness.wait_event("app.state_changed", timeout=5.0)
    assert new_state == "low_heat_risk_e"

    # Verify via getter
    assert harness.get("app.state") == "low_heat_risk_e"

def test_touch_removed_transitions_from_low_heat_risk(harness):
    """Removing touch from low_heat_risk should go to off_body or validation."""
    # Setup: ensure we're in low_heat_risk
    if harness.get("app.state") == "off_body_e":
        harness.inject("sensor.touch", "detected")
        harness.wait_event("app.state_changed", timeout=5.0)
    assert harness.get("app.state") == "low_heat_risk_e"

    # Remove touch
    harness.drain_events()
    result = harness.inject("sensor.touch", "removed")
    assert result == "OK"

    # Wait for transition
    new_state = harness.wait_event("app.state_changed", timeout=5.0)
    # Should go to off_body_validation_e (20-sec timer) or off_body_e
    assert new_state in ("off_body_validation_e", "off_body_e")

def test_invalid_inject_returns_error(harness):
    """Invalid inject value should return error."""
    result = harness.inject("sensor.touch", "invalid_value")
    assert result.startswith("ERR:")


=== 3. test_motion_state_machine.py ===
Purpose: Verify motion state machine basic state.

def test_initial_motion_state(harness):
    """After boot, motion should be stopped."""
    state = harness.get("motion.state")
    assert state == "motion_is_stopped"

# Note: Further motion tests may require physical motion stimulus
# or an injection point for motion data. For the proof, we verify
# the getter works and the initial state is correct.


=== 4. test_sensor_on_body.py ===
Purpose: Verify on-body detection harness interaction.

def test_on_body_initially_false(harness):
    """Device not on body after boot."""
    assert harness.get("sensor.on_body") == "false"

def test_inject_touch_makes_on_body_true(harness):
    """Injecting touch detected makes on_body true."""
    harness.inject("sensor.touch", "detected")
    time.sleep(0.5)  # Allow state machine to process
    assert harness.get("sensor.on_body") == "true"

def test_inject_touch_removed_makes_on_body_false(harness):
    """Injecting touch removed makes on_body false."""
    harness.inject("sensor.touch", "detected")
    time.sleep(0.5)
    harness.inject("sensor.touch", "removed")
    time.sleep(0.5)
    assert harness.get("sensor.on_body") == "false"


=== 5. test_off_body_validation.py ===
Purpose: Verify the 20-second off-body validation timer behavior.

def test_off_body_validation_window(harness):
    """When touch removed from low_heat_risk, device enters validation
    window before returning to off_body."""
    # Get to low_heat_risk
    harness.inject("sensor.touch", "detected")
    harness.wait_event("app.state_changed", timeout=5.0)
    assert harness.get("app.state") == "low_heat_risk_e"

    # Remove touch
    harness.drain_events()
    harness.inject("sensor.touch", "removed")

    # Should enter validation state
    evt = harness.wait_event("app.state_changed", timeout=5.0)
    if evt == "off_body_validation_e":
        # Wait for the validation timer to expire (~20 seconds)
        final_evt = harness.wait_event("app.state_changed", timeout=30.0)
        assert final_evt == "off_body_e"
    elif evt == "off_body_e":
        # Some implementations may skip validation window
        pass
    else:
        pytest.fail(f"Unexpected state after touch removed: {evt}")


PYTEST FIXTURES (conftest.py):

Create .concord/tests/integration/conftest.py:

import pytest
import os

@pytest.fixture(scope="session")
def fixture_controller():
    """Create fixture controller connected to MTIB node."""
    from fixture_controller import FixtureController
    host = os.environ.get("MTIB_HOST", "10.4.45.33")  # default to known node
    port = int(os.environ.get("MTIB_PORT", "50052"))
    fc = FixtureController(mtib_host=host, mtib_port=port)
    yield fc
    fc.close()

@pytest.fixture(scope="session")
def harness(fixture_controller):
    """Flash firmware and create harness client."""
    from harness_client import HarnessClient

    # Flash instrumented firmware
    hex_path = os.environ.get("FIRMWARE_HEX", "build/nrf52840/zephyr/merged.hex")
    fixture_controller.flash(hex_path)
    time.sleep(3)  # Wait for boot

    # Open UART and create harness client
    uart = fixture_controller.open_uart(baud=115200)
    client = HarnessClient(uart)
    time.sleep(2)  # Wait for shell to initialize

    yield client

    fixture_controller.close_uart()

@pytest.fixture(autouse=True)
def reset_device_state(harness):
    """Reset device to known state before each test."""
    # Remove any injected touch
    harness.inject("sensor.touch", "removed")
    time.sleep(1)
    # Drain events
    harness.drain_events()
    yield


RUNNING THE TESTS:

  # From the alpha_fw directory
  MTIB_HOST=10.4.45.33 FIRMWARE_HEX=build/nrf52840/zephyr/merged.hex \
    pytest .concord/tests/integration/ -v

IMPORTANT NOTES:
- These tests run on REAL HARDWARE. They're not mocked. Timing matters.
- Add appropriate sleeps/waits for state machine processing. The firmware
  runs a cooperative main loop — state transitions aren't instant.
- The off-body validation test takes ~20 seconds. Mark it with
  @pytest.mark.slow if you want to skip it in quick runs.
- READ the actual firmware behavior (from D4 results) before finalizing
  test assertions. The exact state transitions and timing may differ from
  the architecture docs.
- Tests should be idempotent and order-independent (the autouse fixture
  resets state before each test).
```

</details>

---

#### Step F3: Run End-to-End and Document Results

**Effort:** 4h
**Depends on:** F2 + all hardware/firmware ready
**Produces:** Documented proof-of-concept results

<details>
<summary><strong>Agent Prompt (click to expand)</strong></summary>

```
TASK: Execute the full Stage 3 proof-of-concept end-to-end and document
the results.

CONTEXT:
Everything is built and ready:
- concord_harness module (Stream A)
- Alpha firmware with harness integration (Streams B + D)
- Hardware fixture (Stream C)
- Python test infrastructure (Stream E)
- Integration test scripts (F1 + F2)

EXECUTION STEPS:

1. Build instrumented firmware:
   cd /home/mateo/work/firmware/alpha_fw
   west build -b alpha_b0 -- -DOVERLAY_CONFIG=boards/alpha_b0_harness.conf

2. Run the test suite:
   MTIB_HOST=<node-ip> FIRMWARE_HEX=build/nrf52840/zephyr/merged.hex \
     pytest .concord/tests/integration/ -v --tb=long

3. Document results:
   - How many tests passed / failed / errored?
   - For failures: what was the actual behavior vs expected?
   - Timing observations: how long did state transitions take?
   - UART reliability: were there any parsing issues, dropped events,
     or garbled output?
   - Device stability: did the Alpha board crash or reset unexpectedly?

4. Fix issues and re-run until all tests pass (or document known issues).

5. Also verify production build is unaffected:
   west build -b alpha_b0  # stock, no overlay
   # Compare binary size to baseline (before any changes)
   # Flash and verify device boots normally

DELIVERABLE:
Create a results document at:
  /home/mateo/work/docs/concord/validation/plans/stage3-proof-results.md

Include:
- Date and environment details
- Test results (pass/fail per test)
- Screenshots or logs of key interactions (concord list output, event capture)
- Performance observations (latency, reliability)
- Known issues / limitations
- Recommendations for next steps (what to build next)
- Updated effort estimates based on actual experience

THIS DOCUMENT IS THE PROOF. It demonstrates that the concord_harness
concept works on real hardware and is the foundation for the full
validation pipeline.
```

</details>

---

## Post-Phase Review Checkpoint

After each phase completes, review and update:

<details>
<summary><strong>Phase 1 Review Prompt (click to expand)</strong></summary>

```
TASK: Phase 1 completion review.

After Streams A, B, and C complete, verify:

1. STREAM A — concord_harness module:
   - Does it compile as a Zephyr module? (test with a minimal app)
   - Are all Kconfig options present?
   - Does the shell command registration work? (test on native_sim if possible)
   - Review all source files for consistency (section names, struct fields,
     function signatures must match between .h, registry.c, shell.c, emit.c)

2. STREAM B — alpha_fw changes:
   - Do both accessor functions work? (compile test)
   - Is the UART0 RX guard in all the right places? (grep for UARTE0)
   - Are the typedefs cleanly in the headers with no duplicates?
   - Does the production build still compile and produce identical output?

3. STREAM C — hardware:
   - Can you flash firmware via MTIB? (use stock firmware)
   - Can you read UART output via MTIB?
   - Can you power cycle?
   - Is the node registered in K3s?

4. UPDATE the plan:
   - Adjust effort estimates for Phase 2 based on Phase 1 learnings
   - Document any surprises (e.g., extra files that need changes, APIs that
     don't match docs, hardware issues)
   - Update the integration_spec.yaml (F1) if the harness point list changed
```

</details>

<details>
<summary><strong>Phase 2 Review Prompt (click to expand)</strong></summary>

```
TASK: Phase 2 completion review.

After Streams D and E complete, verify:

1. STREAM D — instrumented firmware:
   - Does "concord list" on real hardware return all expected points?
   - Does "concord get app.state" return a valid state string?
   - Does "concord inject sensor.touch detected" cause a state transition?
   - Do events appear on UART with correct [CONCORD:EVT] prefix?
   - Does the device remain stable over multiple inject/get cycles?
   - Does the production build (no overlay) still work unchanged?

2. STREAM E — Python infrastructure:
   - Can harness_client.py parse real UART output from the device?
   - Does fixture_controller.py successfully flash and open UART?
   - Are there any MTIB client issues?

3. CRITICAL CHECK: If D4 (build & verify) revealed issues:
   - Update test expectations in F2 scripts
   - Update integration_spec.yaml if harness points changed
   - Document any timing quirks (e.g., "state transition takes 500ms
     after inject, not instant")

4. UPDATE the plan:
   - Refine test scripts based on actual device behavior
   - Note any new harness points that should be added
   - Update effort estimates for Phase 3
```

</details>

---

## 8. Verification Checkpoints

| Checkpoint | When | What to Verify | Pass Criteria |
|-----------|------|---------------|---------------|
| **A-DONE** | Stream A complete | Module compiles as Zephyr external module | `west build` with a test app including the module succeeds |
| **B-DONE** | Stream B complete | alpha_fw compiles with new getters, UART guard | Production build succeeds, binary unchanged |
| **C-DONE** | Stream C complete | Flash + UART work via MTIB on Alpha board | Can flash stock FW and read UART output |
| **D-DONE** | Stream D complete | Instrumented firmware responds to harness commands | `concord list`, `concord get`, `concord inject` work on UART |
| **E-DONE** | Stream E complete | Python client can communicate with device | harness_client successfully parses real UART |
| **PROOF** | Phase 3 complete | Integration tests pass on real hardware | 5+ test scenarios pass, results documented |

---

## 9. Risk Register (Stage 3 Proof Specific)

| # | Risk | Impact | Mitigation |
|---|------|--------|------------|
| R1 | UART0 RX kill has multiple locations | Harness commands not received | Thorough grep for ALL UART0 disable code in B3 |
| R2 | State machine timing doesn't match test expectations | Test failures from race conditions | Add generous timeouts, verify timing in D4 before writing tests |
| R3 | STRUCT_SECTION_ITERABLE not working as expected | No harness points registered | Test on native_sim first if possible (A7 checkpoint) |
| R4 | Alpha board not available (procurement delay) | Can't do hardware testing | Check internal inventory day 1; order multiple sources |
| R5 | MTIB UartStream gRPC has buffering issues | Partial lines, dropped data | Test UART reliability in C3; add retry logic in harness_client |
| R6 | Shell thread competes with app for UART0 bandwidth | Garbled output, missed responses | Use minimal shell config (no VT100, no echo); keep log level low |
| R7 | Injection mechanism doesn't wake main loop fast enough | Delayed state transitions in tests | Study main loop structure in D1; add wakeup mechanism if needed |

---

## 10. Post-Proof: What Comes Next

Once the proof is successful, the path to full Stage 3 is:

1. **Harden harness_client.py** — retry logic, better error handling, connection recovery
2. **Add power profiling** — I12 (power_profiler.py, 12h) for current measurement during tests
3. **Build Stage 3 orchestrator** — I21b (integration_runner.py, 12h) to automate the full flow
4. **Docker image** — I28 (concord-integration-test-runner, 4h)
5. **Pipeline integration** — connect to the pipeline controller (deferred to when I02 is built)
6. **More test scenarios** — expand from 5 to full integration test suite
7. **Stage 1 foundation** — build accel_drv stubs + pipeline infra (the other 650h of the BOM)

The proof de-risks the most novel and impactful part of the entire validation
system. Everything else is known patterns (K8s orchestration, Docker, gRPC)
applied to a proven concept.

---

## Appendix: File Inventory

Every file created or modified by this plan:

### New Files Created

| File | Stream/Step | Repository |
|------|------------|------------|
| `concord_harness/zephyr/module.yml` | A1 | concord_harness (new) |
| `concord_harness/zephyr/CMakeLists.txt` | A1, A7 | concord_harness |
| `concord_harness/zephyr/Kconfig` | A1, A7 | concord_harness |
| `concord_harness/zephyr/include/concord_harness/concord_harness.h` | A2 | concord_harness |
| `concord_harness/zephyr/include/concord_harness/concord_harness_types.h` | A3 | concord_harness |
| `concord_harness/zephyr/src/concord_registry.c` | A4 | concord_harness |
| `concord_harness/zephyr/src/concord_shell.c` | A5 | concord_harness |
| `concord_harness/zephyr/src/concord_emit.c` | A6 | concord_harness |
| `alpha_fw/src/concord_harness.c` | D1 | alpha_fw |
| `alpha_fw/boards/alpha_b0_harness.conf` | D3 | alpha_fw |
| `alpha_fw/.concord/integration_spec.yaml` | F1 | alpha_fw |
| `alpha_fw/.concord/tests/integration/conftest.py` | F2 | alpha_fw |
| `alpha_fw/.concord/tests/integration/test_harness_discovery.py` | F2 | alpha_fw |
| `alpha_fw/.concord/tests/integration/test_state_machine.py` | F2 | alpha_fw |
| `alpha_fw/.concord/tests/integration/test_motion_state_machine.py` | F2 | alpha_fw |
| `alpha_fw/.concord/tests/integration/test_sensor_on_body.py` | F2 | alpha_fw |
| `alpha_fw/.concord/tests/integration/test_off_body_validation.py` | F2 | alpha_fw |
| `concord/apps/validation/test-runner/src/harness_client.py` | E1 | concord monorepo |
| `concord/apps/validation/test-runner/src/fixture_controller.py` | E2 | concord monorepo |

### Existing Files Modified

| File | Stream/Step | Change |
|------|------------|--------|
| `alpha_fw/src/app/alpha_state_machine.h` | B1, B2 | Add alpha_state_t typedef + get_alpha_state() decl |
| `alpha_fw/src/app/alpha_state_machine.c` | B1, B2, D2 | Remove typedef, add accessor, add CONCORD_EMIT |
| `alpha_fw/src/app/motion_state_machine.h` | B1, B2 | Add motion_state_t typedef + get_motion_state() decl |
| `alpha_fw/src/app/motion_state_machine.c` | B1, B2, D2 | Remove typedef, add accessor, add CONCORD_EMIT |
| `alpha_fw/src/app/app.c` | B3 | #ifndef CONFIG_CONCORD_HARNESS around UART0 kill |
| `alpha_fw/src/app/vsm_handler.c` | D1 | Add harness override hook in is_device_on_body() |
| `alpha_fw/src/CMakeLists.txt` | D1 | Add conditional concord_harness.c |
| `alpha_fw/west.yml` (or manifest) | D3 | Add concord_harness module reference |
| `concord/libs/python/corekinect/mtib_client/v2/` | E3 | Minor updates if needed |
