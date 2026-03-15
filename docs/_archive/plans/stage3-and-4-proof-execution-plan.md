# Stage 3 & 4 Proof Execution Plan (Monolithic — Superseded)

> **This file has been superseded by the structured plan at
> [`stage3-and-4/`](stage3-and-4/overview.md).**
> Kept as a single-file reference. For active tracking, use the folder structure.

> **Goal:** Prove end-to-end firmware validation on real Alpha B0 hardware:
> - **Stage 3 (Integration):** Instrumented firmware with `concord_harness`
>   shell commands — software-driven stimulus and internal state observation
> - **Stage 4 (Product Validation):** Production firmware (debug + release)
>   with black-box verification via CoreCloud, MTIB GPIO/ADC physical stimulus,
>   and power measurement — zero instrumentation
>
> **Total Estimated Effort:** ~284h engineering + ~$700–2,400 hardware
>
> **Date:** 2026-02-25

---

## Table of Contents

1. [Repositories & Branch Strategy](#1-repositories--branch-strategy)
2. [Hardware Topology & Setup](#2-hardware-topology--setup)
3. [Three Firmware Builds](#3-three-firmware-builds)
4. [BOM Components — Interfaces & System Requirements](#4-bom-components--interfaces--system-requirements)
5. [Work Streams & Dependency Graph](#5-work-streams--dependency-graph)
6. [Phase 0: Prerequisites](#phase-0-prerequisites)
7. [Phase 1: Parallel Foundation](#phase-1-parallel-foundation)
8. [Phase 2: Harness Integration](#phase-2-harness-integration)
9. [Phase 3: Stage 3 E2E Proof](#phase-3-stage-3-end-to-end-proof)
10. [Phase 4–5: Stage 4 E2E Proof](#phase-4-5-stage-4-end-to-end-proof)
11. [Phase 6: Debug vs Release Comparison](#phase-6-debug-vs-release-comparison)
12. [Fixture GPIO/ADC Mapping](#7-fixture-gpioadc-mapping)
13. [Verification Checkpoints](#8-verification-checkpoints)
14. [Risk Register](#9-risk-register)
15. [Known Limitations](#10-known-limitations)

---

## 1. Repositories & Branch Strategy

### 1.1 Repository Map

| Repository | Hosting | Location | Purpose |
|-----------|---------|----------|---------|
| **concord** | Bitbucket | `~/work/concord/concord/` | Monorepo: MTIB server, Python test framework, protos, HTTP API |
| **concord_harness** | GitHub | `https://github.com/MateoSegura/concord_harness` | Standalone Zephyr module for firmware instrumentation |
| **alpha_fw** | Bitbucket | `~/work/firmware/alpha_fw/` | Alpha B0 firmware (nRF52840 app + nRF9151 comms) |

### 1.2 Branch Strategy

| Repo | Base Branch | Feature Branches From | Merge Target |
|------|------------|----------------------|-------------|
| concord | `v2/init` | `v2/init` | `v2/init` via PR |
| concord_harness | `main` | `main` | `main` via PR |
| alpha_fw | `feat/concord_integration_pod` | `feat/concord_integration_pod` | `feat/concord_integration_pod` via PR |

### 1.3 Branch Naming Convention

All repos follow: `<type>/<description>`

Valid types: `feat`, `fix`, `chore`, `docs`, `test`, `refactor`

Example branches per repo:

**concord (from `v2/init`):**
```
feat/mtib-server-redesign        # MTIB server rewrite
feat/mtib-proto-redesign         # Proto definition update
feat/test-framework-init         # Python test framework scaffold
feat/test-framework-stage3       # Stage 3 test modules
feat/test-framework-stage4       # Stage 4 test modules + cloud client
```

**concord_harness (from `main`):**
```
feat/core-module                 # Macros, registry, shell, emit
feat/kconfig-cmake               # Build system integration
```

**alpha_fw (from `feat/concord_integration_pod`):**
```
feat/public-typedefs             # Move types to public headers
feat/state-accessors             # Add getter functions
feat/harness-integration         # concord_harness.c + EMIT calls
feat/build-overlays              # Stage 3 + Stage 4 overlay configs
```

### 1.4 Merge Flow

```
Feature branch ──► PR (human-reviewed) ──► Base branch
                      │
                      ├── Author writes PR description
                      ├── Human reviewer approves
                      └── Human merges (squash or merge commit)
```

**Rules:**
- Never auto-commit or auto-merge. A human always initiates.
- No AI references in commits, PRs, or code comments.
- PR descriptions explain the *why*, not just the *what*.
- One logical change per PR. Don't bundle unrelated work.

### 1.5 Paths Within Concord Monorepo

```
~/work/concord/concord/
├── apps/
│   ├── edge/
│   │   ├── mtib-server/              # ◄ MTIB server (redesigned, replaces v1)
│   │   └── mtib-server-v2/           #   (untouched — v2 preserved as reference)
│   └── backend/
│       └── http-api/                 #   Concord HTTP API (queries MTIB observability)
├── libs/
│   ├── protocols/
│   │   └── mtib/
│   │       └── mtib.proto            # ◄ Redesigned proto (23 RPCs)
│   ├── corekinect/
│   │   └── test/                     # ◄ Python test framework (NEW)
│   │       ├── validation/           #   Validation library
│   │       └── manufacturing/        #   Manufacturing library (future)
│   └── python/
│       └── corekinect/
│           └── core_cloud/           #   CoreCloud SDK (EXISTS, used by Stage 4)
└── deploy/
    └── edge/
        └── mtib-server/              # ◄ K8s manifests for MTIB deployment
```

---

## 2. Hardware Topology & Setup

### 2.1 Physical Topology

```
┌─────────────────────────────────────────────────────────────────────┐
│  LINEAR RAIL SCAFFOLD (single X axis, 500mm travel)                │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  Verdin iMX8M Mini + Mallow Carrier                        │   │
│  │  K3s node: verdin-imx8mm-15702160                          │   │
│  │  OS: Torizon (Yocto-based, containerized)                  │   │
│  │  ┌───────────────────────────────────────────────────────┐ │   │
│  │  │  MTIB Server Pod (gRPC :50052, privileged)            │ │   │
│  │  └───────────────────────────────────────────────────────┘ │   │
│  └─────────────────────┬───────────────────────────────────────┘   │
│                        │                                           │
│  ┌─────────────────────┴───────────────────────────────────────┐   │
│  │  MTIB Carrier Board REV 1.2                                 │   │
│  │  48-pin DUT connector + USB hub + FluidNC ESP32             │   │
│  └─────────────────────┬───────────────────────────────────────┘   │
│                        │ 48-pin pogo / flex cable                  │
│  ┌─────────────────────┴───────────────────────────────────────┐   │
│  │  FIXTURE BOARD (custom PCB or hand-wired)                   │   │
│  │  Routes 48-pin signals to Alpha B0 test points              │   │
│  │  ┌───────────────────────────────────────────────────────┐ │   │
│  │  │  Alpha B0 Board                                       │ │   │
│  │  │  nRF52840 (app) + nRF9151 (comms)                    │ │   │
│  │  │  LSM6DSO IMU, PAH8151 PPG, BME280, BQ25622           │ │   │
│  │  └───────────────────────────────────────────────────────┘ │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  [Stepper motor + A4988 driver]──────[FluidNC ESP32 on MTIB]      │
│  Moves entire scaffold on rail for accelerometer stimulus          │
└─────────────────────────────────────────────────────────────────────┘
```

### 2.2 MTIB Capabilities (REV 1.2)

| Resource | Count | Resolution | Used For |
|----------|-------|-----------|----------|
| GPIO (DUT-facing) | 7 pins (0-6) | Digital, level-shifted | Button sim, on-skin, charger relay |
| ADC | 8 channels (0-7) | 16-bit, 0-14V range | Photodiode, thermistor, signal tapping |
| Power output (DUT) | 1 channel | 0.8-5.5V, mA current sense | Main device power |
| Power output (CHG) | 1 channel | 5V, mA current sense | Charger simulation (limited) |
| SWD | 2 J-Link (muxed) | — | Firmware flashing |
| UART | 2 ports | 115200 baud | Shell/harness/logs |
| Motion | 1 axis (X) | 500mm, 80 steps/mm | Accelerometer stimulus |

### 2.3 Known Hardware Limitations

| Limitation | Impact | Workaround |
|-----------|--------|-----------|
| CHG and DUT power from same source | Cannot test real charging behavior | Skip charge-dependent PRDTST tests (29 tests) |
| INA219 resolution ~mA | Cannot measure µA sleep current | Accept mA-level measurement, note in results |
| 1 Alpha B0 unit | Cannot parallelize hardware testing | Serialize on-device tests, parallelize dev work |
| 7 DUT GPIO pins | May not reach all Alpha test points | Prioritize highest-impact signals in fixture design |

### 2.4 Hardware Setup By Phase

| Phase | Hardware State Expected |
|-------|----------------------|
| **Phase 0** | Bare: Verdin + MTIB carrier v1.2, K3s node online, no Alpha connected |
| **Phase 1** | Core wiring: Alpha B0 connected via SWD + UART + Power. Scaffold rail assembled. MTIB server pod deployed. |
| **Phase 2** | Full fixture: GPIO wired to button/on-skin/charger relay. ADC wired to signal taps. Motion actuator mounted. All channels verified. |
| **Phase 3** | Same as Phase 2. Integration firmware flashed. Shell commands working over UART. |
| **Phase 4–5** | Same as Phase 2. Production firmware (debug + release) flashed. CoreCloud environment accessible. |
| **Phase 6** | Same. Side-by-side comparison runs. |

---

## 3. Three Firmware Builds

| Build | `CONFIG_CONCORD_HARNESS` | `CONFIG_LOG` | `CONFIG_SHELL` | UART Output | Stage |
|-------|-------------------------|-------------|---------------|-------------|-------|
| **Integration** | `y` | `y` | `y` | Shell + logs + harness events | Stage 3 |
| **Production Debug** | `n` | `y` | `n` | Logs only | Stage 4 |
| **Production Release** | `n` | `n` | `n` | Silent | Stage 4 |

**Overlay files in alpha_fw:**

```
alpha_fw/
└── boards/
    ├── alpha_b0_harness.conf     # Integration build (Stage 3)
    ├── alpha_b0_debug.conf       # Production debug (Stage 4)
    └── alpha_b0_release.conf     # Production release (Stage 4)
```

**Build commands:**
```bash
# Stage 3: Integration
west build -b alpha_b0_nrf52840 -- -DOVERLAY_CONFIG=boards/alpha_b0_harness.conf

# Stage 4: Debug
west build -b alpha_b0_nrf52840 -- -DOVERLAY_CONFIG=boards/alpha_b0_debug.conf

# Stage 4: Release
west build -b alpha_b0_nrf52840 -- -DOVERLAY_CONFIG=boards/alpha_b0_release.conf
```

**Note:** The alpha_fw main app does NOT currently use `CONFIG_SHELL`. The
integration overlay enables it specifically for concord_harness. There are
zero existing shell commands in the main app — the `concord` shell namespace
will be the only set of commands.

---

## 4. BOM Components — Interfaces & System Requirements

Each BOM component is defined by its **interface** (what it exposes) and
**system requirements** (what it needs). Implementation details are left
to the coding agent with the appropriate `claude-kit` kit loaded.

### 4.1 Firmware Components

#### F-01: `concord_harness` Zephyr Module

| Property | Value |
|----------|-------|
| **What** | External Zephyr module providing compile-time firmware instrumentation |
| **Repo** | `https://github.com/MateoSegura/concord_harness` |
| **Branch** | `main` → `feat/core-module` |
| **claude-kit** | `embedded-zephyr` |
| **Effort** | ~29.5h |

**Interface — Firmware API (C macros):**

```c
// Registration macros — expand to STRUCT_SECTION_ITERABLE entries
CONCORD_GETTER(name, getter_fn)         // Read-only observable point
CONCORD_SETTER(name, setter_fn)         // Writable control point
CONCORD_INJECT(name, inject_fn)         // Event injection point
CONCORD_EVENT(name)                     // Async event declaration

// Runtime emission — queues event for background print
CONCORD_EMIT(name, value_str)
```

**Interface — Shell Protocol (UART):**

| Command | TX (host → device) | RX (device → host) |
|---------|-------------------|-------------------|
| Get | `concord get <name>\n` | `[CONCORD:RSP] <name>=<value>\n` |
| Set | `concord set <name> <value>\n` | `[CONCORD:RSP] <name>=OK\n` |
| Inject | `concord inject <name> <value>\n` | `[CONCORD:RSP] <name>=OK\n` |
| List | `concord list\n` | `[CONCORD:RSP] LIST_BEGIN\n` ... `[CONCORD:RSP] LIST_END\n` |
| Event | — (firmware-initiated) | `[CONCORD:EVT] <name>=<value>\n` |

**System Requirements:**

- Zephyr RTOS (NCS compatible)
- `CONFIG_SHELL=y`, `CONFIG_SHELL_BACKEND_SERIAL=y`
- Dedicated event thread (lowest priority, ~256 byte stack)
- `k_msgq` for event queuing (non-blocking emission from app threads)
- All macros compile to nothing when `CONFIG_CONCORD_HARNESS=n`

**Dependencies:** None (standalone Zephyr module)

---

#### F-02: Alpha FW Integration (getters, overlays, EMIT calls)

| Property | Value |
|----------|-------|
| **What** | Alpha firmware changes: public typedefs, state accessors, harness point registration, EMIT calls, build overlays |
| **Repo** | `~/work/firmware/alpha_fw/` |
| **Branch** | `feat/concord_integration_pod` |
| **claude-kit** | `embedded-zephyr` |
| **Effort** | ~34h (30h Stage 3 + 4h Stage 4 overlays) |

**Interface — Harness Points Registered:**

```c
// In alpha_fw/src/concord_harness.c
CONCORD_GETTER("app.state",           get_alpha_state);
CONCORD_GETTER("motion.state",        get_motion_state);
CONCORD_GETTER("batt.percent",        get_battery_percent);
CONCORD_GETTER("batt.voltage",        get_battery_voltage);
CONCORD_GETTER("sensor.on_body",      get_on_body_state);

CONCORD_SETTER("config.pd",           set_position_delivery_period);

CONCORD_INJECT("sensor.touch",        inject_touch_event);
CONCORD_INJECT("sensor.motion",       inject_motion_event);

CONCORD_EVENT("app.state_changed");
CONCORD_EVENT("motion.state_changed");
```

**Interface — Build Overlays:**

| Overlay | Key Configs |
|---------|------------|
| `alpha_b0_harness.conf` | `CONFIG_CONCORD_HARNESS=y`, `CONFIG_SHELL=y`, `CONFIG_LOG=y` |
| `alpha_b0_debug.conf` | `CONFIG_CONCORD_HARNESS=n`, `CONFIG_SHELL=n`, `CONFIG_LOG=y` |
| `alpha_b0_release.conf` | `CONFIG_CONCORD_HARNESS=n`, `CONFIG_SHELL=n`, `CONFIG_LOG=n` |

**System Requirements:**

- Alpha B0 board definition at `ck_boards/current/boards/corekinect/alpha_b0/`
- West workspace with concord_harness as external module
- Both MCUs buildable: nRF52840 (app) and nRF9151 (comms)

**Dependencies:** F-01 (concord_harness module must exist first)

---

### 4.2 Infrastructure Components

#### I-01: MTIB Server (Redesigned)

| Property | Value |
|----------|-------|
| **What** | gRPC hardware abstraction server for MTIB carrier board REV 1.2 |
| **Repo** | `~/work/concord/concord/` at `apps/edge/mtib-server/` |
| **Branch** | `v2/init` → `feat/mtib-server-redesign` |
| **claude-kit** | `cloud-python` |
| **Effort** | ~40h (new estimate — full rewrite with v1 patterns) |
| **Spec** | `plans/mtib-server-redesign.md` |

**Interface:** 23 gRPC RPCs as defined in `plans/mtib-server-redesign.md` §2

| Category | RPCs | Key Capability |
|----------|------|---------------|
| Health | 1 | Server ready, hw revision, capabilities |
| UART | 1 | Bidirectional streaming, multi-client broadcast |
| Flash | 3 | nrfjprog flash/erase, list probes |
| GPIO | 4 | Config/write/read + streaming watch |
| Power | 5 | Enable/disable/read/measure/stream per channel |
| ADC | 3 | Read/read-all/stream 8 channels |
| Motion | 4 | Start (streaming)/home/stop/status |
| Observability | 2 | Snapshot + continuous stream |

**System Requirements:**

- Python 3.10+, grpcio-aio
- Privileged container on ARM64 K3s node
- Hardware: MTIB carrier REV 1.2 with I2C auto-detection
- nrfjprog CLI for J-Link flash operations
- FluidNC ESP32 for motion control
- Container registry: `containers.ad.corekinect.com`
- Nx build targets: containerize, push

**Dependencies:** Proto file (I-02) must be defined first

---

#### I-02: MTIB Proto Definition

| Property | Value |
|----------|-------|
| **What** | Protobuf service + message definitions for the redesigned MTIB server |
| **Repo** | `~/work/concord/concord/` at `libs/protocols/mtib/mtib.proto` |
| **Branch** | `v2/init` → `feat/mtib-proto-redesign` |
| **claude-kit** | `cloud-python` (proto compilation) |
| **Effort** | ~4h |

**Interface:** Full proto as defined in `plans/mtib-server-redesign.md` §2.1–2.3

**System Requirements:**

- protoc compiler
- grpcio-tools (Python codegen)
- protoc-gen-go (Go codegen, if needed by other services)

**Dependencies:** None (defines the contract everything else implements against)

---

#### I-03: Python Test Framework — Validation Library

| Property | Value |
|----------|-------|
| **What** | Python library providing TestContext, UartDemuxer, HarnessTransport, MtibClient |
| **Repo** | `~/work/concord/concord/` at `libs/corekinect/test/validation/` |
| **Branch** | `v2/init` → `feat/test-framework-init` |
| **claude-kit** | `cloud-python` |
| **Effort** | ~52h |

**Interface — Core Classes:**

```python
# TestContext — unified entry point for all test types
class TestContext:
    harness: HarnessTransport   # Stage 3: shell commands (get/set/inject/wait_event)
    mtib: MtibClient            # All stages: raw MTIB gRPC calls
    cloud: CloudClient          # Stage 4: CoreCloud message verification
    logs: LogBuffer             # All stages: device log collection
    fixture: FixtureProfile     # Pin assignments for this hardware setup

# HarnessTransport — concord shell protocol over UART
class HarnessTransport:
    async def get(name: str, timeout_s: float) -> str
    async def set(name: str, value: str) -> None
    async def inject(name: str, value: str) -> None
    async def wait_event(name: str, timeout_s: float) -> str
    async def list() -> list[HarnessPoint]

# UartDemuxer — prefix-based line routing
class UartDemuxer:
    async def feed(chunk: bytes) -> None
    # Routes: [CONCORD:RSP] → response_queue
    #         [CONCORD:EVT] → event_queue
    #         everything else → log_buffer

# MtibClient — thin gRPC client wrapper
class MtibClient:
    async def flash(firmware_path: str, target: HostType) -> None
    async def gpio_write(pin: int, value: bool) -> None
    async def gpio_read(pin: int) -> bool
    async def power_enable(channel: PowerChannel, voltage: float) -> None
    async def power_disable(channel: PowerChannel) -> None
    async def power_measure(channel: PowerChannel, duration_s: float) -> PowerMeasurement
    async def adc_read(channel: int) -> float
    async def motion_start(duration_s: float, speed_mm_s: float) -> None
    async def motion_home() -> None
    def uart_stream(target: HostType) -> UartStream

# CloudClient — CoreCloud integration (wraps existing SDK)
class CloudClient:
    async def wait_for_position(predicate, timeout_s: float) -> PositionMsgV6
    async def wait_for_biometric(predicate, timeout_s: float) -> BiometricDataMsg
    async def wait_for_boot(timeout_s: float) -> BootMsgV2
    async def push_gps_config(**kwargs) -> None
```

**System Requirements:**

- Python 3.10+, asyncio
- grpcio for MTIB client
- Existing CoreCloud SDK at `libs/python/corekinect/core_cloud/`
- Access to CoreCloud `VAL_1_0` environment (Stage 4)
- MTIB server running and reachable (for integration tests)

**Architecture Note:** The `validation/` directory is designed so that a
future `manufacturing/` directory can share common base classes (MtibClient,
TestContext base) while providing its own test logic.

**Dependencies:** I-02 (proto for MtibClient), I-01 (MTIB server for integration testing)

---

#### I-04: Fixture Profile

| Property | Value |
|----------|-------|
| **What** | JSON configuration mapping MTIB pins to Alpha B0 test points |
| **Repo** | `~/work/concord/concord/` at `libs/corekinect/test/validation/fixtures/` |
| **Branch** | `v2/init` → `feat/test-framework-init` |
| **Effort** | ~4h (design) + hardware wiring time |

**Interface:**

```json
{
  "product": "alpha",
  "board": "alpha_b0",
  "mtib_revision": "1.2",
  "pin_mapping": {
    "button": { "gpio_pin": 0, "active_low": true },
    "on_skin": { "gpio_pin": 1, "active_high": true },
    "charger_relay": { "gpio_pin": 5, "active_high": true }
  },
  "adc_mapping": {
    "photodiode_red": { "channel": 0 },
    "photodiode_green": { "channel": 1 },
    "thermistor": { "channel": 2 },
    "photodiode_blue": { "channel": 3 }
  },
  "power": {
    "dut_voltage": 3.3,
    "charger_voltage": 5.0
  },
  "uart": {
    "app_mcu": "uart1",
    "comms_mcu": "uart0"
  }
}
```

**System Requirements:** Hardware fixture physically wired and verified

**Dependencies:** Fixture GPIO/ADC mapping design (see §7)

---

### 4.3 Hardware Components

#### H-01: Alpha B0 Board

| Property | Value |
|----------|-------|
| **What** | CoreKinect Alpha B0 wearable device (nRF52840 + nRF9151) |
| **Status** | Check internal inventory — may already be available |
| **Est. Cost** | $200-400 |
| **Qty** | 1 (development unit) |

**Interface:**

- SWD pads for nRF52840 + nRF9151
- UART0 pads (P0.06 TX, P0.08 RX on nRF52840)
- Test points for GPIO signals (button, on-skin, charger detect)
- Antenna for LTE + GPS (nRF9151 → CoreCloud)

---

#### H-02: Test Fixture Board / Wiring

| Property | Value |
|----------|-------|
| **What** | Physical connection between MTIB 48-pin connector and Alpha B0 test points |
| **Status** | NEW — design + build |
| **Est. Cost** | $50-200 (PCB or hand-wired) |
| **Effort** | ~32h total (design, wire, verify all channels) |

**Interface:** Maps MTIB 48-pin to Alpha B0 signals per fixture profile JSON

**System Requirements:**

- MTIB 48-pin mating connector
- Level-shifting handled by MTIB TXS0108 (DUT_VIO from Alpha)
- Relay modules for charger and button simulation
- Secure mechanical mounting on scaffold

---

#### H-03: Motion Scaffold

| Property | Value |
|----------|-------|
| **What** | Linear rail with stepper motor for accelerometer stimulus |
| **Status** | CHECK — may already be assembled from previous MTIB work |
| **Est. Cost** | $200-1,000 if new |

**Interface:** FluidNC ESP32 controls stepper via A4988 driver. MotionStart RPC
moves the scaffold. Alpha's LSM6DSO detects the acceleration.

---

### 4.4 BOM Summary Table

| ID | Component | Repo | Branch | Kit | Effort | Status |
|----|-----------|------|--------|-----|--------|--------|
| F-01 | concord_harness module | concord_harness | main | embedded-zephyr | 29.5h | NEW |
| F-02 | alpha_fw integration | alpha_fw | feat/concord_integration_pod | embedded-zephyr | 34h | UPDATE |
| I-01 | MTIB server (redesigned) | concord | v2/init | cloud-python | 40h | REWRITE |
| I-02 | MTIB proto | concord | v2/init | cloud-python | 4h | REWRITE |
| I-03 | Python test framework | concord | v2/init | cloud-python | 52h | NEW |
| I-04 | Fixture profile | concord | v2/init | cloud-python | 4h | NEW |
| H-01 | Alpha B0 board | — | — | — | $200-400 | PROCURE |
| H-02 | Fixture wiring | — | — | — | 32h + $50-200 | NEW |
| H-03 | Motion scaffold | — | — | — | $200-1,000 | CHECK |
| — | Stage 3 test modules | concord | v2/init | cloud-python | 28h | NEW |
| — | Stage 4 test modules | concord | v2/init | cloud-python | 70h | NEW |
| **TOTAL** | | | | | **~294h + $450-1,600** | |

---

## 5. Work Streams & Dependency Graph

```
PHASE 0 (Day 1)
═══════════════════════════════════════════════════════════════

  Procure hardware (H-01, H-03 if needed)
  Verify K3s cluster access
  Verify CoreCloud VAL_1_0 environment

PHASE 1 (Week 1-2): PARALLEL FOUNDATION
═══════════════════════════════════════════════════════════════

  Stream A              Stream B             Stream C            Stream D
  (concord_harness)     (alpha_fw changes)   (HW fixture)        (MTIB server)
  ───────────────────   ──────────────────   ─────────────────   ────────────────
  A1: Core macros       B1: Public typedefs  C1: SWD+UART+Pwr   D1: Proto definition
  A2: Registry          B2: State accessors  C2: GPIO wiring     D2: Server rewrite
  A3: Shell commands    B3: UART0 guard      C3: ADC wiring      D3: Deploy to K3s
  A4: Event system      B4: Build overlays   C4: Motion mount    D4: Verify all RPCs
  A5: Kconfig/CMake                          C5: Verify channels
                        (B: ~34h)            (C: ~32h)           (D: ~44h)
  (A: ~29.5h)

  Stream G (parallel — no FW dependency)
  (Stage 4 Python infra)
  ──────────────────────────────────────
  G1: cloud_client.py (wraps existing CoreCloud SDK)
  G2: test_context.py (unified API design)
  G3: alpha_validation_spec.yaml (PRDTST mapping)
  G4: Vault creds + env setup
  (G: ~36h)

PHASE 2 (Week 2-3): HARNESS INTEGRATION
═══════════════════════════════════════════════════════════════

  Stream E                          Stream F
  (alpha_fw harness integration)    (Python test infra)
  ──────────────────────────────    ───────────────────────
  E1: concord_harness.c             F1: harness_client.py
  E2: CONCORD_EMIT calls            F2: uart_demuxer.py
  E3: Harness overlay config        F3: mtib_client.py
  E4: Build + flash via MTIB        F4: fixture_controller.py (full)
  E5: Verify shell over UART        F5: nfc_client.py (Stage 4)
                                    F6: validation_runner.py (Stage 4)
  (E: ~30h)                         (F: ~52h)

  ► E depends on: A (harness module), B (alpha_fw getters), D (MTIB server running)
  ► F depends on: D (MTIB proto + server for client testing)

PHASE 3 (Week 3-4): STAGE 3 E2E PROOF
═══════════════════════════════════════════════════════════════

  Stream H (Stage 3 integration tests)
  ────────────────────────────────────
  H1: Write integration test modules (5 test files)
  H2: Run E2E on real Alpha B0 via MTIB
  H3: Debug, fix, iterate until all pass
  (H: ~28h)

  ► H depends on: E (alpha_fw with harness flashed), F (Python framework working)

PHASE 4-5 (Week 4-6): STAGE 4 E2E PROOF
═══════════════════════════════════════════════════════════════

  Stream J (Stage 4 test modules — can start when G+F are done)
  ──────────────────────────────────────────────────────────────
  J1: test_boot.py
  J2: test_motion.py (5 motion tests)
  J3: test_biometric.py (3 on-skin tests)
  J4: test_button.py (9 button/SOS tests)
  J5: test_environmental.py (7 env sensor tests)
  J6: test_gnss.py (7 GNSS tests)
  J7: test_power.py (7 power budget tests)
  J8: test_nfc.py (1 NFC test)
  J9: Run debug build E2E → fix → iterate
  J10: Run release build E2E → fix → iterate
  (J: ~70h)

  ► J depends on: G (cloud client, spec), F (fixture controller, MTIB client)
  ► J9/J10 depend on: C (fixture fully wired), CoreCloud env accessible

PHASE 6 (Week 6-7): DEBUG vs RELEASE COMPARISON
═══════════════════════════════════════════════════════════════

  Compare debug and release results. Document discrepancies.
  Any test that passes on debug but fails on release is a CRITICAL bug.
```

**Key parallelism:** Streams A, B, C, D, G all start Day 1 — completely independent.
Stream D (MTIB server redesign) is new and critical-path for Phase 2.

---

## Phase 0: Prerequisites

### Step 0.1: Procure Hardware

| Item | Action | Lead Time |
|------|--------|-----------|
| Alpha B0 board | Check internal inventory first | 0-2 weeks |
| NFC reader (I2C, NT3H2111 compatible) | Order from Adafruit/Mouser | 1-2 weeks |
| Linear actuator (if not already assembled) | Check existing scaffold | 0-2 weeks |
| Relay modules (2×, charger + button) | Amazon/Mouser | 1 week |
| Photodiode breakout (3-channel RGB) | Adafruit | 1 week |
| Thermistor NTC 10K + Peltier module | Amazon/Mouser | 1 week |
| Conductive electrode pad material | Specialty supplier | 1 week |

### Step 0.2: Verify Infrastructure

```bash
# K3s cluster access
kubectl get nodes
kubectl get pods -A

# Verify Verdin node is online
kubectl get node verdin-imx8mm-15702160

# Container registry access
docker login containers.ad.corekinect.com

# CoreCloud (when URL is known)
# python -c "from corekinect.core_cloud.db_interface import ..."
```

### Step 0.3: Verify Repository Access

```bash
# Concord repo on v2/init
cd ~/work/concord/concord && git checkout v2/init && git pull

# Alpha firmware
cd ~/work/firmware/alpha_fw && git checkout feat/concord_integration_pod

# concord_harness (create if needed)
git clone https://github.com/MateoSegura/concord_harness ~/work/concord_harness
```

---

## Phase 1: Parallel Foundation

### Stream A: `concord_harness` Zephyr Module

**Repo:** `https://github.com/MateoSegura/concord_harness`
**Branch:** `main` → `feat/core-module`
**Kit:** `claude-kit --kit embedded-zephyr`
**Effort:** ~29.5h
**Hardware needed:** None (develop on native_sim, then nRF52840 DK)

| Step | Task | Effort | Produces |
|------|------|--------|----------|
| A1 | Core macros (CONCORD_GETTER/SETTER/INJECT/EVENT) | 8h | `concord_harness.h`, `concord_harness_types.h` |
| A2 | Registry (STRUCT_SECTION_ITERABLE iteration) | 4h | `concord_registry.c` |
| A3 | Shell commands (get/set/inject/list) | 8h | `concord_shell.c` |
| A4 | Event system (k_msgq + background thread, CONCORD_EMIT) | 4h | `concord_emit.c` |
| A5 | Kconfig, CMakeLists.txt, module.yml | 3.5h | Build system files |

**Verification checkpoint:** Build for native_sim, register dummy harness
points, send shell commands over simulated UART, verify `[CONCORD:RSP]`
and `[CONCORD:EVT]` output.

---

### Stream B: Alpha Firmware Changes

**Repo:** `~/work/firmware/alpha_fw/`
**Branch:** `feat/concord_integration_pod` → feature branches
**Kit:** `claude-kit --kit embedded-zephyr`
**Effort:** ~34h
**Hardware needed:** None initially (build verification only)

| Step | Task | Effort | Produces |
|------|------|--------|----------|
| B1 | Move alpha_state_t, motion_state_t to public headers | 2h | Public typedefs |
| B2 | Add accessor functions (get_alpha_state, get_motion_state, etc.) | 3h | State accessors |
| B3 | UART0 RX guard (#ifdef CONFIG_CONCORD_HARNESS) | 4h | Shell-safe UART |
| B4 | Build overlay configs (harness, debug, release) | 2h | 3 overlay .conf files |

**B3 is critical:** The Alpha firmware may currently use UART0 for output-only.
The integration build needs UART0 in bidirectional mode for the shell. This
step ensures the firmware doesn't interfere with shell RX when harness is enabled.

**Verification checkpoint:** All three builds compile without errors.
Release build size matches (or is very close to) stock build.

---

### Stream C: Hardware Fixture

**Repo:** N/A (physical hardware)
**Effort:** ~32h + parts
**Dependencies:** Hardware from Step 0.1

| Step | Task | Effort | MTIB Resource |
|------|------|--------|--------------|
| C1 | Wire SWD + UART + Power (core connections) | 8h | SWD pins 3-5, UART pins 7-8, Power pin 1 |
| C2 | Wire charger relay | 4h | GPIO pin 5 → relay → CHG rail |
| C3 | Wire button GPIO | 2h | GPIO pin 0 → transistor → Alpha button |
| C4 | Wire on-skin electrode | 2h | GPIO pin 1 → conductive pad |
| C5 | Mount motion actuator on scaffold | 4h | FluidNC motor output |
| C6 | Mount LED photodiodes | 2h | ADC channels 0, 1, 3 |
| C7 | Wire NFC reader | 1h | I2C bus 1 (pins 24-25) |
| C8 | Wire Peltier + thermistor | 2h | GPIO pin 3 + ADC channel 2 |
| C9 | Register MTIB node labels in K3s | 1h | kubectl label node |
| C10 | Verify ALL channels end-to-end | 6h | Every RPC against real hardware |

**Verification checkpoint (C10):** Every channel produces expected results.
Document results per channel. This is the hardware acceptance test.

---

### Stream D: MTIB Server Redesign

**Repo:** `~/work/concord/concord/` at `apps/edge/mtib-server/`
**Branch:** `v2/init` → `feat/mtib-server-redesign`
**Kit:** `claude-kit --kit cloud-python`
**Effort:** ~44h (4h proto + 40h server)
**Hardware needed:** Verdin node for deployment testing
**Spec:** `plans/mtib-server-redesign.md`

| Step | Task | Effort | Produces |
|------|------|--------|----------|
| D1 | Define proto (mtib.proto — 23 RPCs) | 4h | Proto file + generated bindings |
| D2 | Implement server (7 handlers + observability) | 32h | Full server codebase |
| D3 | Containerize + deploy to K3s | 4h | Docker image, K8s manifests |
| D4 | Verify all RPCs against real hardware | 4h | Verification report |

**D2 agent prompt guidance:** The agent should:
- Start from v1's handler patterns (flat, no sessions)
- Use `grpcio-aio` for async parallel streaming
- Implement REV 1.2 auto-detection from v2's hardware/revision.py
- Port FluidNC service from v1 (serial G-code interface)
- Implement observability engine with background polling threads
- UART handler must support multi-client broadcast with < 10ms latency
- Refer to `plans/mtib-server-redesign.md` for complete interface spec

**Verification checkpoint:** Deploy to Verdin, call every RPC, verify
responses match expected hardware behavior. Test UART multi-client
by subscribing from two terminals simultaneously.

---

### Stream G: Stage 4 Python Infrastructure

**Repo:** `~/work/concord/concord/` at `libs/corekinect/test/validation/`
**Branch:** `v2/init` → `feat/test-framework-stage4`
**Kit:** `claude-kit --kit cloud-python`
**Effort:** ~36h
**Hardware needed:** None (CoreCloud access only)

| Step | Task | Effort | Produces |
|------|------|--------|----------|
| G1 | cloud_client.py (wrap existing CoreCloud SDK) | 8h | CloudClient class |
| G2 | test_context.py (unified API) | 4h | TestContext class |
| G3 | alpha_validation_spec.yaml (71 PRDTST test definitions) | 16h | Declarative test spec |
| G4 | Vault creds + environment setup | 8h | Credentials config |

**Dependencies:** CoreCloud VAL_1_0 environment must be accessible for G1 testing.

**Verification checkpoint:** CloudClient can query the DB and receive real
messages from a known test device. TestContext can be instantiated with
mock sub-clients.

---

## Phase 2: Harness Integration

### Stream E: Alpha FW Harness Integration

**Repo:** `~/work/firmware/alpha_fw/`
**Branch:** `feat/concord_integration_pod` → `feat/harness-integration`
**Kit:** `claude-kit --kit embedded-zephyr`
**Effort:** ~30h
**Hardware needed:** Alpha B0 + MTIB (SWD + UART)
**Depends on:** Stream A (concord_harness module), Stream B (getters), Stream D (MTIB server for flashing)

| Step | Task | Effort |
|------|------|--------|
| E1 | Create `alpha_fw/src/concord_harness.c` with all harness point registrations | 16h |
| E2 | Add `CONCORD_EMIT()` calls in state machine transition handlers | 3h |
| E3 | Finalize harness overlay config (west module inclusion) | 4h |
| E4 | Build integration firmware, flash to Alpha B0 via MTIB FlashProgram | 3h |
| E5 | Verify shell commands work over MTIB UartStream | 4h |

**E5 verification:** From a Python script, open UartStream to the MTIB,
send `concord list\n`, verify `[CONCORD:RSP] LIST_BEGIN` ... `LIST_END`
comes back with all registered harness points.

---

### Stream F: Python Test Framework

**Repo:** `~/work/concord/concord/` at `libs/corekinect/test/validation/`
**Branch:** `v2/init` → `feat/test-framework-init`
**Kit:** `claude-kit --kit cloud-python`
**Effort:** ~52h
**Depends on:** Stream D (MTIB server running for client testing)

| Step | Task | Effort | Produces |
|------|------|--------|----------|
| F1 | harness_client.py (HarnessTransport) | 12h | Shell command API |
| F2 | uart_demuxer.py (UartDemuxer) | 8h | Prefix-based line routing |
| F3 | mtib_client.py (MtibClient wrapper) | 4h | Thin gRPC client |
| F4 | fixture_controller.py (full — GPIO, power, ADC, motion) | 24h | Hardware abstraction |
| F5 | nfc_client.py (NFC reader via MTIB I2C) | 2h | NFC tag reader |
| F6 | validation_runner.py (tag filter, dual-build, comparison) | 8h | Test orchestrator |

**F1 + F2 are tightly coupled:** The HarnessTransport uses UartDemuxer
internally. The demuxer feeds raw UART bytes into three queues (response,
event, log). The transport awaits specific responses correlated to sent commands.

**F4 fixture_controller.py:** This is the most complex piece. It wraps MtibClient
calls into test-friendly methods:

```python
class FixtureController:
    async def flash(firmware_path, target) -> None
    async def power_on(voltage=3.3) -> None
    async def power_off() -> None
    async def power_cycle(off_duration=2.0) -> None
    async def press_button(duration_s=0.5) -> None
    async def simulate_on_skin(on=True) -> None
    async def connect_charger() -> None
    async def disconnect_charger() -> None
    async def shake(duration_s, intensity) -> None
    async def read_adc(channel) -> float
    async def measure_power(channel, duration_s) -> PowerMeasurement
```

---

## Phase 3: Stage 3 End-to-End Proof

### Stream H: Stage 3 Integration Tests

**Repo:** `~/work/concord/concord/` at `libs/corekinect/test/validation/tests/stage3/`
**Branch:** `v2/init` → `feat/test-framework-stage3`
**Kit:** `claude-kit --kit cloud-python`
**Effort:** ~28h
**Hardware needed:** Full MTIB + Alpha B0 setup, integration firmware flashed
**Depends on:** Stream E (firmware), Stream F (Python framework)

| Step | Task | Effort |
|------|------|--------|
| H1 | Write integration test modules (5 files, ~25 tests total) | 20h |
| H2 | Run E2E on real hardware, debug failures | 8h |

**Test modules:**

| File | Tests | What It Proves |
|------|-------|---------------|
| `test_harness_basic.py` | List points, get/set values | Shell protocol works over MTIB UART |
| `test_state_observation.py` | Read app.state, motion.state | Internal state is observable |
| `test_event_emission.py` | Trigger state change, wait for event | Async events work |
| `test_stimulus_injection.py` | Inject touch/motion, verify state change | Software stimulus drives real transitions |
| `test_concurrent.py` | Multiple rapid commands, interleaved events | Protocol is robust under load |

**Verification checkpoint:** All 25 tests pass on real Alpha B0 hardware
connected via MTIB. Shell commands round-trip in < 100ms. Events arrive
within 1 second of the triggering state change.

**THIS IS THE STAGE 3 PROOF.** If these tests pass, we have proven that:
1. `concord_harness` works on real hardware
2. The UART shell protocol is reliable over MTIB
3. Internal firmware state is observable and controllable
4. The Python test framework can drive tests programmatically

---

## Phase 4–5: Stage 4 End-to-End Proof

### Stream J: Stage 4 Test Modules

**Repo:** `~/work/concord/concord/` at `libs/corekinect/test/validation/tests/stage4/`
**Branch:** `v2/init` → `feat/test-framework-stage4`
**Kit:** `claude-kit --kit cloud-python`
**Effort:** ~70h
**Hardware needed:** Full MTIB + Alpha B0 + CoreCloud env
**Depends on:** Stream G (cloud client, spec), Stream F (fixture controller)

| Step | Module | Tests | What It Proves |
|------|--------|-------|---------------|
| J1 | `test_boot.py` | Boot msg verification | Device boots cleanly, BootMsgV2 arrives at CoreCloud |
| J2 | `test_motion.py` | 5 motion tests | Scaffold motion → LSM6DSO → is_in_motion in PositionMsgV6 |
| J3 | `test_biometric.py` | 3 on-skin tests | Electrode sim → on_body flag in BiometricDataMsg |
| J4 | `test_button.py` | 9 button/SOS tests | GPIO button sim → correct device behavior |
| J5 | `test_environmental.py` | 7 env sensor tests | BME280 readings → BiometricDataMsg fields |
| J6 | `test_gnss.py` | 7 GNSS tests | GPS config push → PositionMsgV6 with fix |
| J7 | `test_power.py` | 7 power tests | INA219 measurement → current within budget |
| J8 | `test_nfc.py` | 1 NFC test | NFC reader → device ID read |
| J9 | Debug build E2E | All above | 71 tests pass on production debug firmware |
| J10 | Release build E2E | All above | 71 tests pass on silent shipping binary |

**Dual-build execution pattern:**

```python
# conftest.py
@pytest.fixture(scope="session")
def ctx():
    with TestContext(...) as ctx:
        yield ctx

@pytest.fixture(params=["debug", "release"])
def firmware_build(ctx, request):
    if request.param == "debug":
        ctx.flash_debug()
    else:
        ctx.flash_release()
    yield request.param
```

Each test runs twice — once with debug firmware, once with release.

---

## Phase 6: Debug vs Release Comparison

After both builds complete their E2E runs:

| Scenario | Meaning | Action |
|----------|---------|--------|
| Debug passes, Release fails | **CRITICAL** — log overhead was masking a timing/power bug | File critical firmware bug |
| Release passes, Debug fails | Log system interference (UART TX blocking time-critical path) | File firmware bug, lower priority |
| Both pass | Normal | Record results |
| Both fail | Standard firmware defect | File firmware bug |

**Power comparison:** Compare `test_power.py` results between builds.
The release build is authoritative for power budget. If debug build shows
significantly higher current (expected due to UART TX), document the delta.

---

## 7. Fixture GPIO/ADC Mapping

The fixture design maps MTIB pins to Alpha B0 test points. This mapping
is NOT finalized — it requires analyzing the Alpha B0 DTS and schematic
to identify accessible test points.

### 7.1 Approach

1. Read Alpha B0 DTS files at `alpha_fw/ck_boards/current/boards/corekinect/alpha_b0/`
2. Identify nRF52840 GPIO assignments for: button, on-skin detection, charger
   status, LED control, IMU interrupt
3. Trace these GPIOs to physical test points or pads on the Alpha B0 PCB
4. Map each test point to an MTIB 48-pin connector pin
5. Document the mapping in the fixture profile JSON

### 7.2 Signals of Interest

| Alpha Signal | nRF52840 GPIO | MTIB Resource | Purpose |
|-------------|--------------|--------------|---------|
| Button | P0.12 (active low, pull-up) | GPIO pin 0 | Simulate press via NPN transistor |
| On-skin electrode | TBD (investigate firmware) | GPIO pin 1 | Simulate skin contact |
| Charger detect | BQ25622 INT on P1.15 or similar | GPIO pin 5 via relay | Charger connect/disconnect |
| LSM6DSO INT1 | P0.14 | — (triggered by physical motion) | Motion detection |
| PAH8151 LEDs | TBD | ADC channels 0, 1, 3 via photodiodes | LED activity measurement |
| NTC thermistor | TBD | ADC channel 2 | Temperature measurement |

### 7.3 What's Deferred

- Exact pin assignments: Need Alpha B0 schematic (not just DTS)
- Peltier PID control: Basic heat/cool only for POC, full PID is stretch goal
- PPG simulation: Complex optical, may defer to future iteration

---

## 8. Verification Checkpoints

Each phase has a clear pass/fail checkpoint:

| Phase | Checkpoint | Pass Criteria |
|-------|-----------|--------------|
| 0 | Infrastructure ready | K3s accessible, container registry accessible, repos cloned |
| 1A | concord_harness builds | Shell commands work on native_sim |
| 1B | Alpha firmware builds | All 3 overlays compile, sizes reasonable |
| 1C | Fixture wired | All channels verified per C10 |
| 1D | MTIB server deployed | All 23 RPCs respond correctly on Verdin |
| 1G | Stage 4 infra ready | CloudClient queries return real data |
| 2E | Harness integration | `concord list` returns registered points over MTIB UART |
| 2F | Python framework | TestContext can flash, send harness commands, read GPIO/ADC |
| 3 | **STAGE 3 PROOF** | All 25 integration tests pass on real hardware |
| 4-5 | **STAGE 4 PROOF** | 71 PRDTST tests pass on both debug and release builds |
| 6 | Comparison complete | Debug/release discrepancies documented |

---

## 9. Risk Register

| Risk | Impact | Likelihood | Mitigation |
|------|--------|-----------|-----------|
| Alpha B0 not available internally | Blocks all on-device testing | Medium | Order early (Day 1), check multiple inventory sources |
| UART latency over gRPC too high | Harness commands unreliable | Low | v2 server already achieves < 10ms with keepalive mechanism |
| concord_harness conflicts with existing UART usage | Shell doesn't work | Low | Alpha main app has no shell — clean integration |
| CoreCloud environment unavailable | Blocks Stage 4 tests | Medium | Stage 3 is independent of CoreCloud, proceed with that first |
| Fixture wiring unreliable | Flaky tests | Medium | Verify each channel individually in C10 before integration |
| MTIB server redesign takes longer than estimated | Delays Phase 2 | Medium | Can fall back to v1 server for basic UART+flash+power while redesign continues |
| Sleep current too low for INA219 resolution | Power tests inaccurate | High | Accept mA resolution, note limitation, plan for dedicated current sense in future |
| Charging tests cannot work (same power source) | 29 PRDTST tests blocked | Certain | Defer charging tests, document as known limitation |

---

## 10. Known Limitations

1. **Single hardware unit** — All on-device testing serializes. Development
   parallelizes across repos, but only one person can flash/test at a time.

2. **Charging not testable** — DUT power and charger power share the same
   MTIB source. No battery sync. 29 PRDTST charging/BMS tests are deferred.

3. **Power resolution** — INA219 with 100mΩ shunt provides mA resolution.
   Sleep current (µA range) measurements will be approximate.

4. **Fixture mapping incomplete** — GPIO/ADC pin assignments need Alpha B0
   schematic analysis. The fixture profile JSON will be finalized during
   Phase 1 Stream C.

5. **CoreCloud URL TBD** — The VAL_1_0 environment URL is not yet known.
   Stage 4 tests cannot run until this is resolved.

6. **18 Config Value tests deferred** — Require GroundModeConfigV2 REST
   endpoint from CoreCloud C# team. Not blocked by our work.

7. **No BLE testing** — BLE scan/connect deferred from this POC.

8. **No NFC guarantee** — NFC reader may not work through fixture mounting.
   Test deferred if reader cannot establish connection.

---

## Appendix A: claude-kit Usage Per Stream

Every stream's agent prompt should include the appropriate kit launch:

| Stream | Kit Command | Why |
|--------|------------|-----|
| A (concord_harness) | `claude-kit --kit embedded-zephyr` | Zephyr module development |
| B (alpha_fw) | `claude-kit --kit embedded-zephyr` | Zephyr firmware, DTS, Kconfig |
| C (fixture) | Manual | Physical hardware wiring |
| D (MTIB server) | `claude-kit --kit cloud-python` | Python gRPC server, Docker, K8s |
| E (FW integration) | `claude-kit --kit embedded-zephyr` | Zephyr firmware with west build |
| F (Python framework) | `claude-kit --kit cloud-python` | Python asyncio, gRPC client |
| G (Stage 4 infra) | `claude-kit --kit cloud-python` | Python, CoreCloud SDK |
| H (Stage 3 tests) | `claude-kit --kit cloud-python` | Python test authoring |
| J (Stage 4 tests) | `claude-kit --kit cloud-python` | Python test authoring |

The claude-kit plugins provide:
- **Domain knowledge** (skills) injected into agent context
- **Behavioral enforcement** (hooks) preventing anti-patterns
- **Specialized subagents** for build, test, debug workflows

Implementation details (thread pools, queue sizes, error recovery patterns,
async patterns, Zephyr coding standards) are the responsibility of the coding
agent with the appropriate kit loaded. This plan defines **what** to build
and **how pieces connect**, not the internal implementation of each piece.

---

## Appendix B: Document Cross-References

| Document | Relationship |
|----------|-------------|
| `plans/mtib-server-redesign.md` | MTIB server interface spec — referenced by I-01, Stream D |
| `plans/stage3-proof-execution-plan.md` | Previous Stage 3-only plan (superseded by this document) |
| `architecture/stage3-integration-tests.md` | concord_harness design spec — referenced by F-01, Stream A |
| `architecture/stage4-product-tests.md` | Stage 4 requirements — referenced by Stream G, J |
| `architecture/09-final-architecture.md` | K8s-native system architecture |
| `research/02-alpha-firmware-analysis.md` | Alpha firmware structure — referenced by Stream B |
| `project/bom-validation-pipeline.md` | Full BOM — this plan extracts Stage 3+4 subset |
| `libs/protocols/mtib_v2/DESIGN.md` | MTIB carrier board hardware reference |
