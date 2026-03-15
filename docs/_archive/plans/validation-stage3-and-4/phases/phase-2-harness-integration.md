# Phase 2: Harness Integration

> **When:** Weeks 2-3
> **Streams:** E, F
> **Hardware state:** MTIB server deployed, Alpha B0 connected (SWD + UART + Power)
> **Dependencies:** Streams A, B, D must be complete

---

## Stream E: Alpha FW Harness Integration

**Repo:** `~/work/firmware/alpha_fw/`
**Branch:** `feat/concord_integration_pod` → `feat/harness-integration`
**Kit:** `claude-kit --kit embedded-zephyr`
**Effort:** ~30h
**Hardware needed:** Alpha B0 + MTIB (SWD for flash, UART for verification)

### What This Produces

Alpha firmware with concord_harness integrated: harness points registered,
EMIT calls in state machines, buildable with harness overlay.

### Harness Points Registered

```c
// alpha_fw/src/concord_harness.c
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

### Steps

| Step | Task | Effort |
|------|------|--------|
| E1 | Create `concord_harness.c` with all registrations | 16h |
| E2 | Add `CONCORD_EMIT()` calls in state transition handlers | 3h |
| E3 | Finalize harness overlay: add concord_harness to `west.yml` manifest, verify integration build compiles | 4h |
| E4 | Build integration firmware, flash nRF52840 to Alpha B0 via MTIB `FlashProgram` (nRF9151 already flashed in Phase 0) | 3h |
| E5 | Verify shell commands work over MTIB `UartStream` | 4h |

### E5 Verification Script

```python
import grpc
from mtib_pb2 import UartRequest, HostType
from mtib_pb2_grpc import MtibStub

channel = grpc.insecure_channel("verdin-ip:50052")
stub = MtibStub(channel)

# Subscribe to UART
async for response in stub.UartStream(requests()):
    line = response.data.decode()
    if "[CONCORD:RSP] LIST_BEGIN" in line:
        print("Harness is alive!")
```

Send `concord list\n`, verify `[CONCORD:RSP] LIST_BEGIN` ... `LIST_END`
returns with all registered points.

### Agent Prompt Guidance

The agent needs:
- Alpha firmware source at `~/work/firmware/alpha_fw/`
- concord_harness module from Stream A
- Understanding of alpha_state_t, motion_state_t state machines
- UART0 on nRF52840: P0.06 TX, P0.08 RX at 115200 baud
- Board: `alpha_b0_nrf52840` with DTS at `ck_boards/current/boards/corekinect/alpha_b0/`

---

## Stream F: Python Test Framework

**Repo:** `~/work/concord/concord/` at `libs/corekinect/test/validation/`
**Branch:** `v2/init` → `feat/test-framework-init`
**Kit:** `claude-kit --kit cloud-python`
**Effort:** ~58h
**Hardware needed:** MTIB server running (for integration testing)
**Dependencies:** Stream D (MTIB proto + server)

### What This Produces

Complete Python test framework with: HarnessTransport, UartDemuxer,
MtibClient, FixtureController, validation runner.

### Directory Structure

```
libs/corekinect/test/
├── __init__.py
├── validation/
│   ├── __init__.py
│   ├── harness_client.py       # HarnessTransport (shell commands)
│   ├── uart_demuxer.py         # UartDemuxer (prefix-based routing)
│   ├── mtib_client.py          # MtibClient (thin gRPC wrapper)
│   ├── cloud_client.py         # CloudClient (from Stream G)
│   ├── fixture_controller.py   # FixtureController (hardware abstraction)
│   ├── nfc_client.py           # NFC reader via MTIB I2C
│   ├── validation_runner.py    # Test orchestrator (tag filter, dual-build)
│   ├── test_context.py         # TestContext (unified API)
│   ├── fixtures/
│   │   └── alpha_b0.json       # Fixture profile (pin mapping)
│   └── tests/
│       ├── stage3/             # Phase 3 test modules
│       └── stage4/             # Phase 4-5 test modules
└── manufacturing/              # Future — similar structure
```

### Key Interfaces

**UartDemuxer** — prefix-based line routing:

```python
CONCORD_RSP_PREFIX = "[CONCORD:RSP] "
CONCORD_EVT_PREFIX = "[CONCORD:EVT] "

class UartDemuxer:
    async def feed(self, chunk: bytes):
        # Split into lines, classify by prefix:
        # [CONCORD:RSP] → response_queue
        # [CONCORD:EVT] → event_queue
        # everything else → log_buffer
```

**HarnessTransport** — shell command API:

```python
class HarnessTransport:
    async def get(name, timeout_s=5.0) -> str
    async def set(name, value) -> None
    async def inject(name, value) -> None
    async def wait_event(name, timeout_s=30.0) -> str
    async def list() -> list[HarnessPoint]
```

**FixtureController** — hardware abstraction:

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

### Steps

| Step | Task | Effort | Produces |
|------|------|--------|----------|
| F1 | harness_client.py (HarnessTransport) | 12h | Shell command API |
| F2 | uart_demuxer.py (UartDemuxer) | 8h | Line routing |
| F3 | mtib_client.py (MtibClient wrapper) | 4h | gRPC client |
| F4 | fixture_controller.py (full) | 24h | Hardware abstraction |
| F5 | nfc_client.py | 2h | NFC tag reader |
| F6 | validation_runner.py + conftest.py | 8h | Test orchestrator + pytest fixtures (TestContext, firmware_build parametrize) |

**Note on test_context.py:** Stream G (G2) designs the TestContext interface.
Stream F implements it, wiring together HarnessTransport, MtibClient,
FixtureController, and CloudClient. The implementation lives in
`libs/corekinect/test/validation/test_context.py`.

**Note on apps/validation/test-runner/:** The shared library lives under
`libs/corekinect/test/validation/`. The Nx application that imports this
library (env var loading, CLI entry point, Docker image, K8s manifests)
lives under `apps/validation/test-runner/` — same pattern as the manufacturing
app. The app is a thin wrapper; all test logic is in the library.

### F4 Fixture Controller Detail

This is the largest piece (~24h). It wraps MtibClient calls into
test-friendly methods. Pin assignments come from the fixture profile JSON:

```json
{
  "button": { "gpio_pin": 0, "active_low": true },
  "on_skin": { "gpio_pin": 1, "active_high": true },
  "charger_relay": { "gpio_pin": 5, "active_high": true },
  "power": { "dut_voltage": 3.3, "charger_voltage": 5.0 }
}
```

The controller translates high-level calls (`press_button()`) into
MTIB GPIO operations with correct timing and pin mapping.

---

## Phase 2 Checkpoint

| Check | Status |
|-------|--------|
| E5: `concord list` returns points over MTIB UART | |
| F: TestContext instantiates, can flash via MtibClient | |
| F: HarnessTransport sends command, receives response | |
| F: FixtureController toggles GPIO, reads ADC | |
