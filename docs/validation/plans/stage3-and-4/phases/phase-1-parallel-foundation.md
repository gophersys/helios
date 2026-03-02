# Phase 1: Parallel Foundation

> **When:** Weeks 1-2
> **Streams:** A, B, C, D, G (mostly independent — B needs A for harness overlay compile)
> **Hardware state at start:** Bare Verdin + MTIB, hardware arriving
> **Hardware state at end:** MTIB server deployed, Alpha connected, fixture wired

---

## Stream A: `concord_harness` Zephyr Module

**Repo:** `https://github.com/MateoSegura/concord_harness`
**Branch:** `main` → `feat/core-module`
**Kit:** `claude-kit --kit embedded-zephyr`
**Effort:** ~29.5h
**Hardware needed:** None (native_sim, then nRF52840 DK)

### Interface Produced

```c
// Registration macros (STRUCT_SECTION_ITERABLE)
CONCORD_GETTER(name, getter_fn)
CONCORD_SETTER(name, setter_fn)
CONCORD_INJECT(name, inject_fn)
CONCORD_EVENT(name)
CONCORD_EMIT(name, value_str)    // Runtime event emission via k_msgq
```

Shell commands: `concord get|set|inject|list`
Protocol: `[CONCORD:RSP] <name>=<value>`, `[CONCORD:EVT] <name>=<value>`

### System Requirements

- Zephyr RTOS (NCS compatible)
- `CONFIG_SHELL=y`, `CONFIG_SHELL_BACKEND_SERIAL=y`
- Event thread: lowest priority, 2048 byte stack, k_msgq

### Steps

| Step | Task | Effort | Produces |
|------|------|--------|----------|
| A1 | Core macros (`concord_harness.h`, `concord_harness_types.h`) | 8h | Public API header |
| A2 | Registry (`concord_registry.c` — STRUCT_SECTION iterate) | 4h | Point lookup by name |
| A3 | Shell commands (`concord_shell.c` — SHELL_CMD_REGISTER) | 8h | get/set/inject/list |
| A4 | Event system (`concord_emit.c` — k_msgq + background thread) | 4h | Async CONCORD_EMIT |
| A5 | Kconfig, CMakeLists.txt, module.yml | 3.5h | Zephyr module build system |

### Agent Prompt Guidance

The agent receives the full concord_harness design spec from
`architecture/stage3-integration-tests.md`. Key constraints:

- All macros must expand to nothing when `CONFIG_CONCORD_HARNESS=n`
- Shell commands use standard Zephyr `SHELL_CMD_REGISTER`
- Event thread must not block application threads (k_msgq non-blocking put)
- Prefix format is exact: `[CONCORD:RSP] ` and `[CONCORD:EVT] ` (with trailing space)

### Verification

Build for native_sim, register dummy harness points, send shell commands
via simulated UART, verify correct `[CONCORD:RSP]` and `[CONCORD:EVT]` output.

---

## Stream B: Alpha Firmware Changes

**Repo:** `~/work/firmware/alpha_fw/`
**Branch:** `feat/concord_integration_pod` → feature branches
**Kit:** `claude-kit --kit embedded-zephyr`
**Effort:** ~34h
**Hardware needed:** None (build verification only)
**Dependencies:** Stream A must deliver Kconfig symbols before harness overlay can compile

### Interface Produced

State accessor functions + 3 build overlay configs.

### Steps

| Step | Task | Effort | Produces |
|------|------|--------|----------|
| B1 | Move `alpha_state_t`, `motion_state_t` to public headers | 2h | Public typedefs |
| B2 | Add accessor functions (`get_alpha_state()`, `get_motion_state()`, etc.) | 3h | Getter APIs |
| B3 | UART0 RX guard (`#ifdef CONFIG_CONCORD_HARNESS`) | 4h | Shell-safe UART |
| B4 | Build overlay configs (harness, debug, release) | 2h | 3 `.conf` files |

**B3 is critical:** Alpha firmware may use UART0 for output-only. The
integration build needs bidirectional UART for the shell. This step
ensures firmware doesn't interfere with shell RX.

**B4 overlay configs:**

| File | Key Configs |
|------|------------|
| `boards/alpha_b0_harness.conf` | `CONCORD_HARNESS=y`, `SHELL=y`, `LOG=y` |
| `boards/alpha_b0_debug.conf` | `CONCORD_HARNESS=n`, `SHELL=n`, `LOG=y` |
| `boards/alpha_b0_release.conf` | `CONCORD_HARNESS=n`, `SHELL=n`, `LOG=n` |

**Note on nRF9151:** The `comm_coproc_mfg` firmware for nRF9151 is built
separately (`west build --sysbuild` targeting `alpha_b0/nrf9151/ns`). It is
the same binary for all three nRF52840 variants. It is flashed and personalized
in Phase 0. Stream B does not modify comm_coproc — only the nRF52840 app.

### Verification

All three nRF52840 builds compile. The harness overlay requires Stream A's
module to be available in the west manifest (verify after A delivers). Debug
and release overlays can be verified immediately. Board target:
`alpha_b0/nrf52840`. Board definitions at
`ck_boards/current/boards/corekinect/alpha_b0/`.

---

## Stream C: Hardware Fixture

**Effort:** ~32h + parts
**Dependencies:** Hardware from Phase 0 procurement
**Owner:** Hardware engineer

### Steps

| Step | Task | Effort | MTIB Resource |
|------|------|--------|--------------|
| C1 | Wire SWD + UART + Power (core) | 8h | Pins 1-8, power system |
| C2 | Wire charger relay | 4h | GPIO 5 → relay → CHG rail |
| C3 | Wire button GPIO | 2h | GPIO 0 → NPN → Alpha button |
| C4 | Wire on-skin electrode | 2h | GPIO 1 → conductive pad |
| C5 | Mount motion actuator | 4h | FluidNC motor output |
| C6 | Mount LED photodiodes | 2h | ADC 0, 1, 3 |
| C7 | Wire NFC reader (I2C) | 1h | I2C bus 1 |
| C8 | Wire Peltier + thermistor (via relay/MOSFET) | 2h | GPIO 3 + ADC 2 |
| C9 | Register MTIB node labels | 1h | kubectl |
| C10 | **Verify ALL channels** | 6h | End-to-end acceptance test |

### C10 Acceptance Test Checklist

1. Flash stock firmware via SWD → success
2. Read UART output → recognizable boot messages
3. Power cycle (off 2s, on) → device reboots
4. PowerMeasure(DUT, 1s) → reasonable current values
5. GpioWrite charger relay → current on CHG changes
6. GpioWrite button → device responds (LED or UART)
7. GpioWrite on-skin → (verify in Stage 3 or debug UART)
8. MotionStart → physical motion occurs
9. AdcReadAll → channels return values
10. NFC read → returns bytes

Document results per channel.

---

## Stream D: MTIB Server Redesign

**Repo:** `~/work/concord/concord/` at `apps/edge/mtib-server/`
**Branch:** `v2/init` → `feat/mtib-server-redesign`
**Kit:** `claude-kit --kit cloud-python`
**Effort:** ~44h (4h proto + 40h server)
**Hardware needed:** Verdin node for deployment testing
**Spec:** `plans/mtib-server-redesign.md`

### Interface Produced

23 gRPC RPCs: HealthCheck, UartStream, ListProgrammers, FlashProgram,
FlashErase, GpioConfig/Write/Read/Watch, PowerEnable/Disable/Read/Measure/Stream,
AdcRead/ReadAll/Stream, MotionStart/Home/Stop/Status, GetSnapshot, ObservabilityStream.

### System Requirements

- Python 3.10+, grpcio-aio (async)
- Privileged ARM64 container on K3s
- nrfjprog + J-Link for flash, FluidNC for motion
- UART: multi-client broadcast, < 10ms latency
- Observability: background polling, exposed via gRPC
- No MQTT

### Steps

| Step | Task | Effort | Produces |
|------|------|--------|----------|
| D1 | Define proto (`mtib.proto` — 23 RPCs, full messages) + generate Python bindings | 4h | Proto, `mtib_pb2.py`, `mtib_pb2_grpc.py` |
| D2 | Implement server (7 handlers + observability engine) | 32h | Server codebase |
| D3 | Containerize + deploy to K3s | 4h | Docker image, K8s manifests |
| D4 | Verify all RPCs against real hardware | 4h | Verification report |

### Agent Prompt Guidance

The agent receives the full interface spec from `plans/mtib-server-redesign.md`.
Key constraints:

- Start from v1's flat handler pattern (no sessions, no middleware)
- Use grpcio-aio for async parallel streaming
- Port FluidNC service from v1 (serial G-code interface)
- Port hardware revision detection from v2
- UART handler: single RX thread broadcasts to per-client queues
- Nx build targets matching v2 pattern (containerize, push)

### Verification

Deploy to Verdin, call every RPC, verify responses. Test UART multi-client
by subscribing from two terminals simultaneously.

---

## Stream G: Stage 4 Python Infrastructure

**Repo:** `~/work/concord/concord/` at `libs/corekinect/test/validation/`
**Branch:** `v2/init` → `feat/cloud-client-stage4`
**Kit:** `claude-kit --kit cloud-python`
**Effort:** ~36h
**Hardware needed:** None (CoreCloud access only)
**Dependencies:** CoreCloud VAL_1_0 environment accessible, DEVICE_ID from Phase 0

### Interface Produced

```python
class CloudClient:
    def wait_for_position(predicate, timeout_s) -> PositionMsgV6
    def wait_for_biometric(predicate, timeout_s) -> BiometricDataMsg
    def wait_for_boot(timeout_s) -> BootMsgV2
    def push_gps_config(**kwargs) -> None
```

### Steps

| Step | Task | Effort | Produces |
|------|------|--------|----------|
| G1 | cloud_client.py (wraps existing CoreCloud SDK) | 8h | CloudClient |
| G2 | test_context.py (unified API design) | 4h | TestContext |
| G3 | alpha_validation_spec.yaml (64 active PRDTST tests, 7 GNSS deferred) | 16h | Test spec |
| G4 | Vault credentials + env setup | 8h | Credentials config |

### Verification

CloudClient can query the DB and receive real messages from a known device.

---

## Phase 1 Checkpoint

| Check | Status |
|-------|--------|
| Stream A: concord_harness builds on native_sim | |
| Stream B: All 3 firmware overlays compile | |
| Stream C: All fixture channels verified (C10) | |
| Stream D: MTIB server deployed, all RPCs work | |
| Stream G: CloudClient returns real data | |
