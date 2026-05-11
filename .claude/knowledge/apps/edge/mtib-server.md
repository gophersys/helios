# mtib-server — knowledge

A gRPC server that runs on every fixture node (a Toradex Verdin iMX8MM SoM, ARM64) and is the **only** thing on the platform that drives DUT hardware: turning power on/off, toggling GPIOs, opening UARTs, flashing firmware over J-Link, reading ADC channels, talking to onboard sensors, and (on motion-enabled fixtures) commanding the FluidNC linear-rail controller. Validation runners, manufacturing runners, and the http-api observability poller all reach DUT hardware exclusively through this service.

Refresh this file when: an RPC is added/removed, a driver is added, a handler is restructured, the hardware-version contract changes, or the metrics/MQTT pipeline shifts.

## Location

- Code: `apps/edge/mtib-server/`
- Entry point: `apps/edge/mtib-server/src/main.py`
- Servicer: `apps/edge/mtib-server/src/server.py` (`MtibV1Provider`)
- Proto schema: `libs/protocols/mtib/mtib.proto`
- Python client: `libs/python/corekinect/mtib_client/v1/`
- Tests: `apps/edge/mtib-server/tests/` (pytest, hardware-stubbed)

## Responsibilities

Owns:

- The `mtib.v1.MtibV1` gRPC service on TCP port `50053`.
- All direct hardware I/O on the MTIB carrier board: GPIO (gpiod), I2C bus (`/dev/i2c-3`), SPI, UART, USB programmers.
- Hardware drivers: INA219 (power monitoring), MCP4017 (digital pot for DUT voltage), TCA9534A (GPIO expander, REV 1.2), BME280 (altimeter/temp), LIS2DE12 (accel), ADS1015 (ADC), Joulescope JS220 (optional, nanoamp-resolution).
- The FluidNC motion controller bridge (UART to ESP32 on the linear rail).
- Capability advertisement via `HealthCheck` so callers can branch on what the fixture supports.
- A 10 Hz MQTT metrics publish path (ADC + GPIO state per channel, topic `<hostname>/metrics/...`).
- A point-in-time `GetSnapshot` observability RPC consumed by `http-api`.

Does NOT own:

- Any platform-level concept. It has no idea what a TestRun, Product, BuildJob, or User is. It is hardware-only.
- DUT firmware itself — it can flash binaries but doesn't compile them.
- Cross-fixture coordination — every MTIB instance is independent. The http-api stitches them together.
- Persistent state about runs. The only state it persists is the firmware-file cache under `ASSETS_PATH`.

## Internal structure

```
apps/edge/mtib-server/
├── src/
│   ├── main.py                # Entry: signal handlers, server bootstrap on :SERVER_PORT
│   ├── server.py              # MtibV1Provider — gRPC servicer, routes RPCs to handlers
│   ├── config.py              # MtibEnvConfig (env-var loader), GPIO_PIN_MAP, FluidNC pins
│   ├── handlers/              # One module per RPC category
│   │   ├── gpio.py            # GpioConfig/Write/Read/Watch
│   │   ├── adc.py             # AdcRead/ReadAll/Stream (ADS1015)
│   │   ├── power.py           # PowerEnable/Disable/Read/Measure/Stream (INA219 + MCP4017 + optional Joulescope)
│   │   ├── uart.py            # UartStream (bidirectional, batched broadcaster)
│   │   ├── firmware.py        # ListProgrammers/Fw, Upload/Delete/Flash/Erase/EnableAppProtect (J-Link / Black Magic)
│   │   ├── sensors.py         # AltimeterRead (BME280), AccelRead (LIS2DE12)
│   │   ├── motion.py          # GetMotionStatus, MotionStart (stream), MotionHome, MotionStop (FluidNC)
│   │   ├── nfc.py             # NfcPoll, NfcReadNdef
│   │   └── metrics.py         # MQTT metrics worker support
│   ├── drivers/               # Direct hardware abstractions, one per IC
│   │   ├── gpio.py            # Gpio + Pin enum (Verdin SODIMM pin labels)
│   │   ├── i2c_bus.py         # thread-safe shared bus on /dev/i2c-3
│   │   ├── ina219.py, mcp4017.py, tca9534a.py
│   │   ├── ads1015.py, bme280.py, bme280_iio.py, lis2de12.py
│   │   ├── joulescope.py      # optional USB-attached JS220 (nanoamp)
│   │   └── fluidnc.py         # ESP32 motion controller via serial
│   └── shared/
│       ├── types.py           # protobuf type re-exports
│       └── streaming.py       # StreamBroadcaster + BatchConfig — multi-subscriber fan-out
├── tests/                     # pytest, hardware mocked
├── deploy/
│   ├── Dockerfile             # ARM64 image
│   └── docker-compose.yaml    # dev-host stub
├── docs/
├── project.json               # nx: containerize (linux/arm64), push, deploy
├── setup.py                   # editable install for dev
├── pytest.ini
└── README.md
```

## Key patterns

### gRPC service shape

The proto is at `libs/protocols/mtib/mtib.proto` (`service MtibV1`, package `mtib.v1`). Generated stubs land in `libs/protocols/mtib/mtib_pb2*.py`. The server takes the generated `MtibV1Servicer` base class and implements it as `MtibV1Provider` in `src/server.py`.

Every RPC method on the provider:

1. Is decorated with `@grpc_method` — a per-call logger that records `<method>: Request received from <peer>`, times the call, and logs success/failure.
2. Delegates to the matching handler instance (`self._gpio_handlers`, `self._power_handlers`, …).
3. Returns the protobuf response object directly (or yields for server-streaming RPCs).

Streaming RPCs (`GpioWatch`, `AdcStream`, `PowerStream`, `MotionStart`, `UartStream`) are intentionally **not** decorated with `@grpc_method` — that decorator wraps a unary return value and would consume the iterator. Streaming methods log entry manually then yield from the handler.

`UartStream` is bidirectional (request stream + response stream); `UploadFwFile` is client-streaming (chunked binary uploads).

### Per-RPC categories

The proto groups RPCs into clear categories. Each category maps to a single handler module:

| Category | Proto RPCs | Handler | Hardware involved |
|---|---|---|---|
| Health | `HealthCheck` | inlined on `MtibV1Provider` | none — returns capabilities list |
| Power | `PowerEnable`, `PowerDisable`, `PowerRead`, `PowerMeasure`, `PowerStream` | `PowerHandler` | INA219 (current/voltage), MCP4017 (digital pot for DUT voltage), optional Joulescope JS220 |
| GPIO | `GpioConfig`, `GpioWrite`, `GpioRead`, `GpioWatch` | `GpioHandler` | gpiod via `Gpio` driver; pin map in `config.GPIO_PIN_MAP` |
| ADC | `AdcRead`, `AdcReadAll`, `AdcStream` | `AdcHandler` | ADS1015 8-channel I2C ADC |
| UART | `UartStream` (bidirectional) | `UartHandler` | /dev/ttyUSB* via host-type → port map; broadcaster for multi-subscriber |
| Programming | `ListProgrammers`, `ListFwFiles`, `UploadFwFile`, `DeleteFwFile`, `FlashFwFile`, `EraseFlash`, `EnableAppProtect` | `FirmwareHandler` | J-Link / Black Magic Probe via nrfjprog/JLinkExe; assets cached under `ASSETS_PATH` |
| Sensors | `AltimeterRead`, `AccelRead` | `SensorsHandler` | BME280 (IIO or raw I2C), LIS2DE12 |
| Motion | `GetMotionStatus`, `MotionStart`, `MotionHome`, `MotionStop` | `MotionHandler` | FluidNC ESP32 over `FLUIDNC_SERIAL_PORT` (`/dev/ttyUSB0`); only when `MOTION_ENABLED=true` |
| NFC | `NfcPoll`, `NfcReadNdef` | `NfcHandler` | NFC reader (optional, init may fail) |
| Observability | `GetSnapshot` | inlined; aggregates from `_power_handlers`, `_gpio_handlers`, `_adc_handlers` | all of the above, read-only |

### Capability advertisement

`HealthCheck` returns:

```
ready: bool
errors: [string]
hw_revision: "REV1.2"
capabilities: ["power", "gpio", "adc", "uart", "flash", "motion?", "nfc?", "joulescope?", "observability"]
```

Base capabilities are always present. `motion` is added only when `MOTION_ENABLED=true` (typically validation fixtures, not manufacturing). `nfc` is added only when `NfcHandler` initialized successfully. `joulescope` is added only when a JS220 was detected on USB. Callers branch on this list rather than guessing — e.g., the validation runner only schedules motion stages when `motion` is in capabilities.

### Initialization order

`MtibV1Provider.__init__()` is intentionally sequential and fails closed:

1. `_config_gpio()` — refuses to boot on anything other than `HARDWARE_VERSION=REV1.2`. Initializes all pins in `GPIO_PIN_MAP` as INPUTs by default.
2. Create shared `I2CBus(3)` on `/dev/i2c-3`. Fatal on failure.
3. `_init_hw_extensions()` — TCA9534A GPIO expander. Non-fatal (REV 1.2 feature; logs warning if absent).
4. `_init_handlers()` — instantiate every handler, pass shared `_i2c_bus`, optional `_gpio_expander` to power/firmware/motion handlers, optional `joulescope_driver` to power handler.
5. `_init_metrics()` — connect to MQTT broker and start the 10 Hz worker thread. Only when `METRICS_ENABLED=true`.

If any fatal step fails, the process exits with the error logged. K8s restarts the pod.

### Hardware abstractions

The split between `drivers/` and `handlers/` is firm:

- A **driver** owns one chip or one kernel interface. It exposes raw operations (`read_raw_voltage(channel)`, `set_pot(value)`, `is_present()`). It knows nothing about gRPC.
- A **handler** owns the gRPC method signatures for a category. It composes drivers, applies validation, formats the protobuf response, and emits errors via `response.success=False, response.message=...` rather than gRPC exceptions.

Adding a new chip means a new driver under `drivers/`. Adding a new RPC means a new method on an existing handler (or a new handler module). Don't mix.

### Streaming infrastructure

`src/shared/streaming.py` defines `StreamBroadcaster<T>`: one hardware read thread fans data out to N gRPC subscribers with configurable batching (`NONE`, `NEWLINE_OR_BYTES`, `TIMEOUT_OR_BYTES`). Used by `UartHandler` (many test runners may tail the same UART) and `PowerHandler.power_stream`. Designed for <100 ms latency hardware-to-subscriber.

### MQTT metrics worker

When `METRICS_ENABLED=true`, a daemon thread publishes at 10 Hz:

- `<hostname>/metrics/adc/<channel>` — voltage_v float.
- `<hostname>/metrics/gpio/<num>` — state 0/1.

The broker URL is `METRICS_BROKER_URL` (e.g., `mqtt://broker:1883` or `mqtts://...:8883`). The publisher is fire-and-forget at QoS 0. Used by Grafana dashboards in the office; not consumed by http-api.

### How http-api consumes this

`apps/backend/http-api/src/services/devices/mtib_observability.py` opens a gRPC channel to each fixture node at `<mtib_host>:50053`, calls `GetSnapshot` on a poll interval (default 5 s), and writes the result into the fixture's live state for the frontend. It uses the raw generated `MtibV1Stub` (from `protocols.mtib.mtib_pb2_grpc`) directly because it only needs `GetSnapshot` and `HealthCheck`.

The fuller, ergonomic client is `corekinect.mtib_client.v1.MtibV1Client` (under `libs/python/corekinect/mtib_client/v1/`). It wraps every RPC with input validation, retries, typed result tuples (`Tuple[Optional[T], Optional[str]]` returning `(value, error_message)`), and high-level helpers. It is used by validation runners, manufacturing runners, and the `corekinect.test` framework (see `libs/python/corekinect/test/{slot,context,post,power_profiler,firmware,version_detector,acceleration_profiler}.py` and `libs/python/corekinect/fixture/`).

## External dependencies

| Concern | Where |
|---|---|
| Network | gRPC server on TCP `:50053` (set via `SERVER_PORT`). Insecure channel — relies on cluster network isolation. |
| Hardware bus | `/dev/i2c-3` (shared, thread-safe wrapper in `drivers/i2c_bus.py`). |
| GPIO | Linux gpiod via the `gpiod` Python binding. Pins identified by Verdin SODIMM labels (`Pin.SODIMM_206`, etc.). |
| Programmers | J-Link (`nrfjprog`, `JLinkExe`) and Black Magic Probe over USB. Versions are pinned in the Dockerfile — never bump without coordinating, see the user memory note `feedback_jlink_nrfjprog_fixed.md`. |
| FluidNC | ESP32 motion controller on `FLUIDNC_SERIAL_PORT=/dev/ttyUSB0`, reset pin `FLUIDNC_RESET_PIN=Pin.SODIMM_36`. |
| Metrics broker | MQTT broker reachable at `METRICS_BROKER_URL`. |
| Container | ARM64 only (`platforms: ['linux/arm64']` in `project.json:containerize`). Built via `concord-builder` buildx. |

Env vars (loaded via `corekinect.utils.EnvConfig` in `src/config.py`):

| Var | Purpose |
|---|---|
| `HARDWARE_VERSION` | Must be `REV1.2`. Anything else refuses to boot. |
| `LOG_LEVEL` | int per stdlib `logging`. |
| `LOG_PATH` | directory for the rolled file logger. |
| `SERVER_PORT` | typically `50053`. |
| `ASSETS_PATH` | firmware file cache + FluidNC assets. |
| `METRICS_ENABLED` | bool. |
| `METRICS_BROKER_URL` | `mqtt://host:port` or `mqtts://host:port`. |
| `MOTION_ENABLED` | bool. Derived per fixture at deploy time by `_mtib_env_for_fixture(fixture)` in http-api. |

## How to add common things

### Add a new RPC method

1. **Proto first.** Add the RPC line under `service MtibV1` in `libs/protocols/mtib/mtib.proto`. Add request/response messages following the existing conventions (`success: bool, message: string` are required leading fields for all responses). Bump the proto's `VERSION` file and regenerate stubs.
2. **Re-export the types** in `src/shared/types.py` so handler modules can import them via `from src.shared.types import ...`.
3. **Implement the handler** under `src/handlers/<category>.py`. Validate inputs early; on failure return `Response(success=False, message="...")` — do not raise gRPC exceptions for expected validation failures.
4. **Wire it on the provider** in `src/server.py`: import the request/response types, add a `@grpc_method`-decorated method that delegates to the handler (or, for streaming RPCs, log entry manually and yield from the handler).
5. **Mirror in the client** in `libs/python/corekinect/mtib_client/v1/client/core.py`. Keep the `(value, error) | error_only` return convention. Add a unit test in `libs/python/corekinect/mtib_client/v1/client/tests/test_client.py`.
6. **Update the proto CHANGELOG**, `libs/protocols/mtib/CHANGELOG.md`.
7. **Update this knowledge file** plus `libs/protocols.md` and `libs/python-corekinect.md`.

### Add a new hardware driver

1. Create `src/drivers/<chip>.py` with a class that takes an `i2c_bus`/`spi`/`uart`/`gpio` dependency and a logger. Keep all chip-specific quirks in the driver — handlers should never write register addresses.
2. If the driver is optional (the hardware may be absent), make `__init__` cheap and expose a separate `initialize()` / `scan()` / `find()` method that returns success.
3. In `MtibV1Provider._init_handlers()`, instantiate the driver and pass it to the handler that needs it. Tolerate missing hardware (log a warning, set the relevant capability flag off).
4. Add tests under `apps/edge/mtib-server/tests/test_<chip>.py`. Mock the bus.

### Add a new fixture capability

A capability is a string in the `HealthCheck.capabilities` list. To add one:

1. Decide the predicate (env-var? hardware probe? handler init success?).
2. Add a `_CAPABILITY` constant at the top of `src/server.py` and append it inside `_get_capabilities()` under the predicate.
3. Document it in this knowledge file's capabilities table and in `glossary.md` if it's a new domain concept.
4. Update the http-api logic that branches on capabilities and the frontend code that surfaces fixture features.

## Common failure modes

- **Pod stuck restarting with `Unsupported hardware version`.** `HARDWARE_VERSION` env var is unset or wrong. The fixture node's K8s label/MTIB deploy values didn't include `HARDWARE_VERSION=REV1.2`. Fix at the deploy/values layer; do not relax the check in code.
- **`I2C bus init failed`.** `/dev/i2c-3` isn't mounted into the container, or the kernel module isn't loaded on the host. Container needs `--device /dev/i2c-3` (Helm template should already do this). On the host: `lsmod | grep i2c_imx`.
- **`Joulescope found but failed to open`.** USB permission. The Verdin host udev rules expose the JS220 only to a specific group; verify the container runs as that user, or rebuild the image with the right group membership.
- **`PowerEnable` succeeds but DUT doesn't power on.** Two common causes: the MCP4017 digital pot didn't accept the new voltage (check `_power_handlers` debug log), or the channel mismatch — `POWER_CHANNEL_DUT=0` is the only channel that takes a `voltage_v`; `POWER_CHANNEL_CHARGER` and `POWER_CHANNEL_JOULESCOPE` ignore it.
- **`MotionStart` returns "Motion is not enabled".** `MOTION_ENABLED=false` for this fixture. Manufacturing fixtures intentionally disable motion. If the fixture should support it, update the http-api's per-fixture environment derivation (`_mtib_env_for_fixture(fixture)`) and the helm values for that node.
- **MQTT metrics stop publishing.** The 10 Hz worker logs errors but does not exit on broker disconnect. Check the metrics-worker log; if it's silent, the worker thread died — `metrics_running` will be `True` but the thread `is_alive()` is `False`. Restart the pod.
- **Flash fails with J-Link error 247 / "Could not connect to target".** Programmer wiring, target not powered, or wrong `HostType`. The `FirmwareHandler` does not auto-power-on — runners must call `PowerEnable` first.

## Related knowledge

- [`libs/protocols.md`](../../libs/protocols.md) — proto layout, code generation pipeline.
- [`libs/python-corekinect.md`](../../libs/python-corekinect.md) — the `MtibV1Client` and test framework that consume this server.
- [`apps/backend/http-api.md`](../backend/http-api.md) — the `mtib_observability` service that polls `GetSnapshot` and the fixture-routing logic that decides which MTIB to call.
- [`product-domains/fixtures.md`](../../product-domains/fixtures.md) — Fixture/Slot/Node concepts; `mtib_host` binding.
- [`product-domains/validation.md`](../../product-domains/validation.md), [`product-domains/manufacturing.md`](../../product-domains/manufacturing.md) — the runners that call MTIB RPCs during a TestRun.
- [`deploy/helm.md`](../../deploy/helm.md) — per-node deployment, secrets, MOTION_ENABLED derivation.
- [`glossary.md`](../../glossary.md) — MTIB, Fixture, Node, Verdin, FluidNC.
