# Phase 2: Test Infrastructure

> **When:** Weeks 3-4
> **Streams:** A (Python framework), B (fixture wiring) — independent, run in parallel
> **Hardware state at start:** V1 server updated and deployed, device personalized, CoreCloud accessible
> **Hardware state at end:** Test framework operational, all fixture channels wired
> **Dependencies:** Phase 1 (MTIB server updates) complete

---

## Engineering Protocol for Phase 2

Phase 2 builds the test framework that talks to production systems —
MTIB servers, CoreCloud, real hardware. Every component must work with
existing APIs, not assumed ones.

1. **Read the CoreCloud SDK** (`libs/python/corekinect/core_cloud/`) before
   building CloudClient. Understand the actual query patterns, message
   class hierarchy, DB interface, and REST client. Build on top of what
   exists — do not create a parallel abstraction.
2. **Read the updated V1 client** (`libs/python/corekinect/mtib_client/v1/`)
   — Phase 1 updated it. The FixtureController wraps this client.
   Understand the method signatures, error handling pattern, and streaming
   API before designing the controller interface.
3. **Query CoreCloud** to verify message schemas. Before writing CloudClient
   polling methods, fetch a real `BootMsgV2`, `MotionEventV1`, etc. from
   the validation environment. Validate that the fields you plan to assert
   on actually exist in production messages.
4. **Test against live hardware** early. Don't build the entire framework
   in isolation then try to connect it. Build one component (e.g.,
   FixtureController.gpio_write), test it against a real MTIB node, then
   move on.
5. **Check the manufacturing test patterns** (`apps/manufacturing/alpha/
   src/tests/`) — these are proven patterns for MTIB + CoreCloud testing.
   Adapt their structure and conventions, don't reinvent.

---

## Stream A: Python Test Framework

**Repo:** `~/work/concord/concord/` at `libs/corekinect/test/validation/`
**Branch:** `v2/init` → `feat/stage4-test-framework`
**Effort:** ~54h
**Hardware needed:** MTIB V1 server (for integration testing of FixtureController)
**Dependencies:** CoreCloud VAL_1_0 accessible, DEVICE_ID from Phase 0

### What This Produces

Complete Python test framework for Stage 4: CloudClient, FixtureController,
UartDemuxer, PowerProfiler, TestContext, and pytest conftest — everything
needed to write and run black-box product tests.

### Directory Structure

```
libs/corekinect/test/
├── __init__.py
├── validation/
│   ├── __init__.py
│   ├── cloud_client.py         # CloudClient (polling wrappers over SDK)
│   ├── fixture_controller.py   # FixtureController (GPIO/ADC/motion abstraction)
│   ├── uart_demuxer.py         # UartDemuxer (log capture + prefix routing)
│   ├── power_profiler.py       # PowerProfiler (measurement + stats)
│   ├── test_context.py         # TestContext (unified composition)
│   ├── conftest.py             # pytest fixtures (ctx, firmware_build)
│   ├── fixtures/
│   │   └── alpha_b0.json       # Fixture profile (pin mapping)
│   └── tests/
│       └── stage4/             # Phase 3 test modules go here
│           └── __init__.py
```

### Step A1: CloudClient — 8h

Polling wrappers over the existing CoreCloud SDK. Each method polls the
backend with a predicate and timeout, returning the first matching message
or raising `TimeoutError`.

```python
class CloudClient:
    """CoreCloud message polling for Stage 4 verification.

    Wraps existing corekinect.core_cloud SDK with timeout-based
    polling suitable for black-box test verification.
    """

    def __init__(self, device_id: str, db_env: str = "VAL_1_0"):
        self._device_id = device_id
        self._db_env = db_env
        self._test_start: datetime | None = None

    def mark_test_start(self) -> None:
        """Record timestamp — subsequent queries only return messages after this point."""
        self._test_start = datetime.now(timezone.utc)

    async def wait_for_boot(self, timeout_s: float = 120) -> BootMsgV2:
        """Poll for BootMsgV2 after test_start."""

    async def wait_for_position(
        self,
        predicate: Callable[[PositionMsgV6], bool] | None = None,
        timeout_s: float = 120,
    ) -> PositionMsgV6:
        """Poll for PositionMsgV6 matching predicate after test_start."""

    async def wait_for_biometric(
        self,
        predicate: Callable[[BiometricDataMsg], bool] | None = None,
        timeout_s: float = 120,
    ) -> BiometricDataMsg:
        """Poll for BiometricDataMsg matching predicate after test_start."""

    async def wait_for_network_status(
        self, timeout_s: float = 120
    ) -> NetworkStatusMsgV4:
        """Poll for NetworkStatusMsgV4 after test_start."""

    async def push_gps_config(self, **kwargs) -> None:
        """Send GPSConfMsg to device via REST."""
```

**Implementation notes:**
- Uses `msg_def_v1_0.XxxMsg.since_server_time(device_id, since, db_env)`
  for time-bounded queries
- Poll interval: 2s (CoreCloud uplink ~60s, so no need to poll faster)
- `mark_test_start()` captures UTC timestamp used by all subsequent queries
- All `wait_for_*` methods are async (use `asyncio.sleep` between polls)

### Step A2: FixtureController — 24h

Hardware abstraction layer that maps high-level test actions to MTIB V1
client calls. Pin assignments come from the fixture profile JSON.

```python
class FixtureController:
    """Physical stimulus controller for Stage 4 black-box tests.

    Translates test-level actions (press button, shake, apply contact)
    into MTIB V1 GPIO/ADC/power/motion RPCs using pin mappings from
    the fixture profile.
    """

    def __init__(self, mtib: MtibV1Client, profile_path: str): ...

    # --- Power ---
    async def power_on(self, voltage: float = 4.5) -> None:
        """Enable DUT power at specified voltage (default 4.5V for BQ25180 UVLO)."""

    async def power_off(self) -> None:
        """Disable DUT power."""

    async def power_cycle(self, off_duration_s: float = 2.0) -> None:
        """Power off, wait, power on. Blocks until boot settle time elapses."""

    # --- Button ---
    async def press_button(self, duration_s: float = 0.5) -> None:
        """Simulate button press via GPIO pulse."""

    async def long_press_button(self, duration_s: float = 5.0) -> None:
        """Simulate long button press (SOS, power off, etc.)."""

    # --- Sensors ---
    async def simulate_on_skin(self, on: bool = True) -> None:
        """Drive on-skin electrode GPIO (HIGH = skin contact)."""

    async def connect_charger(self) -> None:
        """Close charger relay (connect 5V USB rail)."""

    async def disconnect_charger(self) -> None:
        """Open charger relay."""

    # --- Motion ---
    async def shake(self, duration_s: float, speed_mm_s: float = 50) -> None:
        """Drive linear actuator for motion simulation."""

    async def stop_motion(self) -> None:
        """Stop linear actuator."""

    # --- ADC ---
    async def read_led_color(self) -> dict[str, float]:
        """Read RGB photodiode ADC channels. Returns {'red': v, 'green': v, 'blue': v}."""

    async def read_temperature(self) -> float:
        """Read thermistor ADC channel. Returns temperature in °C."""

    # --- Flash ---
    async def flash_firmware(self, hex_path: str, target: str = "nrf52840") -> None:
        """Flash firmware via MTIB V1 FlashProgram RPC.

        Always uses --recover then --program --chiperase --verify --reset
        at speed 4000. Target is 'nrf52840' or 'nrf9151'.
        """
```

**Implementation notes:**
- All GPIO operations use `mtib.gpio_write(pin, value)` with pin numbers
  from the fixture profile JSON
- Button press: write active, sleep duration, write inactive
- Power on: `mtib.power_enable(channel=0, voltage_v=4.5)` then sleep 3s
  for boot settle (BQ25180 UVLO requirement)
- Flash: calls `mtib.flash_program()` with `--recover` then `--program`
  at speed 4000 (see CLAUDE.md MTIB hardware rules)
- Motion: calls FluidNC motor control RPCs

### Step A3: UartDemuxer — 4h

UART log capture for debug builds. In Stage 4, there are no `[CONCORD:RSP]`
or `[CONCORD:EVT]` prefixes (no harness). The demuxer captures all UART
output to a log buffer for post-failure diagnosis.

```python
class UartDemuxer:
    """UART line router for debug build log capture.

    Stage 4 mode: all lines go to log_buffer (no harness prefixes).
    Designed for Stage 3 extensibility: adding CONCORD prefix routing
    is a future upgrade that adds response_queue and event_queue.
    """

    CONCORD_RSP_PREFIX = "[CONCORD:RSP] "
    CONCORD_EVT_PREFIX = "[CONCORD:EVT] "

    def __init__(self, enable_harness_routing: bool = False):
        self._log_buffer: list[tuple[float, str]] = []
        self._enable_harness = enable_harness_routing
        # Stage 3 extension points (unused in Stage 4):
        # self._response_queue: asyncio.Queue
        # self._event_queue: asyncio.Queue

    async def feed(self, chunk: bytes) -> None:
        """Process incoming UART bytes. Split into lines, route by prefix."""

    def get_logs(self, since: float | None = None) -> list[str]:
        """Return captured log lines, optionally filtered by timestamp."""

    async def wait_for_log(self, pattern: str, timeout_s: float = 10) -> str:
        """Wait for a log line matching the pattern (debug build only)."""

    def dump_to_file(self, path: str) -> None:
        """Write all captured logs to file (debug_uart_log.txt artifact)."""
```

**Implementation notes:**
- Subscribes to MTIB V1 `UartStream` RPC (UART1 = nRF52840 app processor)
- Lines are timestamped with monotonic time on receipt
- `wait_for_log()` is for diagnostic assertions on debug builds only —
  never used for pass/fail in release builds (no UART output)
- Harness routing is structurally present but disabled
  (`enable_harness_routing=False`). Stage 3 sets it to `True` and adds
  queue consumers.

### Step A4: PowerProfiler — 4h

Wraps MTIB V1 power measurement RPCs with per-test statistics and artifact
storage.

```python
class PowerProfiler:
    """Power measurement wrapper for Stage 4 power budget tests.

    Records high-frequency power samples via MTIB V1 PowerMeasure RPC
    and computes per-test statistics (avg, peak, energy).
    """

    def __init__(self, mtib: MtibV1Client): ...

    async def measure(
        self, channel: int = 0, duration_s: float = 10
    ) -> PowerMeasurement:
        """Take a power measurement. Returns statistics."""

    async def start_continuous(self, channel: int = 0) -> None:
        """Start continuous power sampling (background)."""

    async def stop_continuous(self) -> PowerTrace:
        """Stop continuous sampling, return full trace."""

@dataclass
class PowerMeasurement:
    avg_current_ma: float
    peak_current_ma: float
    min_current_ma: float
    avg_voltage_mv: float
    energy_mwh: float
    duration_s: float
    samples: int

@dataclass
class PowerTrace:
    samples: list[tuple[float, float, float]]  # (timestamp_s, voltage_mv, current_ma)
    measurement: PowerMeasurement               # Aggregated stats
```

**Implementation notes:**
- `measure()` calls `mtib.power_measure(channel, duration_s)` and parses
  the response into `PowerMeasurement`
- `start_continuous()` / `stop_continuous()` use `PowerStream` RPC for
  long-duration measurements (sleep mode current tests)
- Release build power measurements are authoritative; debug build
  measurements are informational (log overhead affects current)

### Step A5: TestContext + conftest — 10h

Composition layer that wires all components together, plus pytest fixtures
for test modules.

```python
class TestContext:
    """Unified test context for Stage 4 product validation.

    Composes MTIB client, CloudClient, FixtureController, UartDemuxer,
    and PowerProfiler into a single object passed to every test.
    """

    def __init__(
        self,
        mtib: MtibV1Client,
        cloud: CloudClient,
        fixture: FixtureController,
        uart: UartDemuxer,
        power: PowerProfiler,
    ):
        self.mtib = mtib
        self.cloud = cloud
        self.fixture = fixture
        self.uart = uart
        self.power = power

    @classmethod
    def from_env(cls) -> "TestContext":
        """Create TestContext from environment variables.

        Required env vars:
          MTIB_HOST, MTIB_PORT
          DEVICE_ID
          CORECLOUD_DB_ENV (default: VAL_1_0)
          FIXTURE_PROFILE_PATH (path to alpha_b0.json)
        """
```

**conftest.py:**
```python
@pytest.fixture(scope="session")
async def ctx() -> AsyncGenerator[TestContext, None]:
    """Session-scoped test context — connects once, reused across all tests."""
    context = TestContext.from_env()
    await context.connect()
    yield context
    await context.disconnect()

@pytest.fixture(params=["debug", "release"])
async def firmware_build(ctx: TestContext, request) -> str:
    """Parametrize every test on debug + release firmware.

    Flashes the appropriate firmware before the first test of each
    variant. Subsequent tests in the same variant reuse the running
    firmware (no re-flash).
    """
    variant = request.param
    await ctx.fixture.flash_firmware(
        hex_path=os.environ[f"FW_{variant.upper()}_HEX"],
        target="nrf52840",
    )
    await ctx.fixture.power_cycle()
    # Wait for boot and LTE attach
    await ctx.cloud.wait_for_boot(timeout_s=120)
    yield variant
```

### Step A6: Fixture Profile — 4h

JSON hardware mapping for the Alpha B0 fixture. Decouples test logic from
physical wiring. Same format as defined in `stage4-product-tests.md`.

```json
{
  "product": "alpha",
  "board": "alpha_b0",
  "button": {
    "gpio_pin": 0,
    "active_low": true
  },
  "on_skin": {
    "gpio_pin": 1,
    "active_high": true
  },
  "peltier": {
    "gpio_pin": 3,
    "sensor_adc_channel": 2
  },
  "charger_relay": {
    "gpio_pin": 5,
    "active_high": true
  },
  "led_sensor": {
    "red_adc_channel": 0,
    "green_adc_channel": 1,
    "blue_adc_channel": 3
  },
  "nfc_reader": {
    "interface": "i2c",
    "bus": 1
  },
  "motion": {},
  "power": {
    "dut_voltage": 4.5,
    "charger_voltage": 5.0,
    "boot_settle_s": 3
  }
}
```

**Note:** GPIO pin assignments are TBD pending Alpha B0 schematic
verification against MTIB REV 1.2 DUT connector. The values above match
the architecture spec and will be validated during fixture wiring (Stream B).

### Verification

| Check | How |
|-------|-----|
| CloudClient polls CoreCloud | `wait_for_boot()` returns a real BootMsgV2 from the personalized device |
| FixtureController drives hardware | `press_button()` → GPIO toggles (verify with oscilloscope or MTIB GPIO read-back) |
| UartDemuxer captures logs | Flash debug build, boot device, verify UART lines appear in log buffer |
| PowerProfiler records data | `measure(duration_s=5)` returns non-zero avg_current_ma |
| TestContext composes correctly | `TestContext.from_env()` instantiates, `ctx.cloud` and `ctx.fixture` are usable |

---

## Stream B: Hardware Fixture Wiring

**Effort:** ~20h + parts (reduced from 32h — manufacturing wiring exists)
**Dependencies:** Hardware from Phase 0 procurement
**Owner:** Hardware engineer

### Already Wired (Manufacturing Fixture — Available Now)

Both validation nodes have Alpha B0 connected in the manufacturing fixture
configuration. These channels are verified in manufacturing and available
immediately for TDD and test framework development:

| Interface | Details | Manufacturing Verification |
|-----------|---------|---------------------------|
| **Power (DUT)** | Ch 0, INA219 @ 0x40, MCP4017 @ 0x2F, 4.5V | Electrical test steps 1-5 |
| **Power (CHG)** | Ch 1, INA219 @ 0x41, 5V | Electrical test step 5 (load sharing) |
| **ADC (4 rails)** | Ch 0: +3.3V, Ch 1: +BATT_SYS, Ch 2: +VBCKP, Ch 3: +SYS | Electrical test voltage checks |
| **UART (app MCU)** | nRF52840, 115200 baud | POST steps 1-10 (shell commands) |
| **UART (comms MCU)** | nRF9151, 115200 baud | POST modem FW check, IMEI/ICCID |
| **SWD/J-Link** | Both MCUs, 4000 kHz, `--recover` first | FW flash test steps 1-3 |
| **GPIO** | 9 pins (SODIMM 206/208/210/212 + I2S + PWM) | Level shifter control for SWD |
| **Accelerometer** | Via UART `read_accel` on app MCU (LSM6DSO) | POST (sensor readback) |

**Fixture profile for Stream A can be bootstrapped from what manufacturing
already uses.** Read `apps/manufacturing/alpha/src/tests/shared/rpcs.py`
for the exact RPC wrappers, pin assignments, and ADC channel mappings.

### Stage 4 Additions (New Wiring Required)

These physical stimulus channels go beyond manufacturing and enable the
full Stage 4 product test suite:

| Step | Task | Effort | MTIB Resource | Tests Enabled |
|------|------|--------|--------------|---------------|
| B1 | Wire button press relay | 2h | GPIO → relay → Alpha button | Button tests (short/long press, emergency) |
| B2 | Wire charger insertion relay | 4h | GPIO → relay → CHG rail | Charger detection tests |
| B3 | Wire on-skin electrode pad | 2h | GPIO → conductive pad | Biometric skin contact tests |
| B4 | Mount LED photodiodes (RGB) | 2h | ADC 4, 5, 6 (or remap) | LED pattern verification |
| B5 | Wire Peltier + thermistor | 2h | GPIO (relay/MOSFET) + ADC | Environmental temperature tests |
| B6 | Wire NFC reader (I2C) | 1h | I2C bus | NFC tap simulation |
| B7 | Mount motion actuator | 4h | FluidNC motor output | Motion detection tests |
| B8 | **Verify ALL new channels** | 3h | End-to-end for B1-B7 | — |

### B8 Acceptance Test Checklist

**Manufacturing baseline (should already pass):**
1. Flash firmware via SWD → device boots
2. Read UART output → recognizable boot/shell messages
3. Power cycle (off 2s, on) → device reboots
4. `PowerMeasure(DUT, 1s)` → current >50mA
5. `AdcReadAll` → channels 0-3 return valid voltage rail readings

**Stage 4 additions (verify new wiring):**
6. GpioWrite button relay → device responds (LED change or UART event)
7. GpioWrite charger relay → current on CHG changes
8. GpioWrite on-skin → verify via debug UART output
9. MotionStart → physical motion occurs, `read_accel` shows change
10. AdcRead photodiode channels → values change with LED state
11. Peltier + thermistor → ADC temperature reading changes
12. NFC read → returns bytes

Document results per channel. Update fixture profile JSON with verified
pin assignments.

---

## Phase 1 Checkpoint

| Check | Status |
|-------|--------|
| Stream A: CloudClient returns real CoreCloud data | |
| Stream A: FixtureController drives GPIO, reads ADC | |
| Stream A: UartDemuxer captures debug UART logs | |
| Stream A: PowerProfiler records measurements | |
| Stream A: TestContext.from_env() works end-to-end | |
| Stream B: All fixture channels wired (B10 acceptance) | |
| Stream B: Fixture profile JSON updated with verified pins | |
