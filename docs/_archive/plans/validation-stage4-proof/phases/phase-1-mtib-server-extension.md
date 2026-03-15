# Phase 1: MTIB Server Updates

> **When:** Weeks 1-2
> **Effort:** ~48h
> **Approach:** Peripheral-by-peripheral. The user works with Claude on each
>   handler in focused sessions — one peripheral at a time, improving and
>   updating the V1 server until it covers everything Stage 4 needs.
> **Hardware state at start:** V1 server deployed (26 RPCs, port 50053)
> **Hardware state at end:** Updated V1 server deployed with Stage 4 capabilities

---

## Engineering Protocol for Phase 1

Each work unit (M1-M10) is a focused session where the engineer works with
Claude on one peripheral. Before writing any code in a work unit:

1. **Read the V1 handler** being modified (`apps/edge/mtib-server/src/`)
2. **Read the equivalent V2 handler** (`apps/edge/mtib-server-v2/src/`) —
   V2 already implements most of what Phase 1 adds to V1. It is the
   reference implementation for TCA9534A, auto-detection, per-revision
   voltage calculation, and feature gating. Do not reinvent — adapt.
3. **Read the V1 proto** (`libs/protocols/mtib/mtib.proto`) and the V2
   proto (if separate) to understand current message shapes
4. **Check the manufacturing code** (`apps/manufacturing/alpha/`) for
   anything that calls the RPCs being modified — ensure backward
   compatibility
5. **Query the live MTIB server** (`grpcurl`) to verify current behavior
   before modifying it
6. **Search Confluence** for hardware specs relevant to the peripheral
   (INA219 datasheet refs, MCP4017 formulas, TCA9534A register map, etc.)
7. **Call out any inconsistencies** between code, docs, and this plan

**V2 Reference Files (read before each work unit):**

| V1 Handler | V2 Equivalent | Key V2 Features to Adapt |
|-----------|---------------|-------------------------|
| `providers/mtib.py` (power) | `providers/handlers/power.py` | Per-revision MCP4017 voltage calc, INA219 streaming |
| `providers/mtib.py` (GPIO) | `providers/handlers/gpio.py` | Edge event monitoring |
| `handlers/adc.py` | `providers/handlers/adc.py` | ADC streaming |
| `handlers/firmware.py` | `providers/handlers/target.py` | J-Link mux via TCA9534A, streaming flash |
| `services/fluidnc.py` | `providers/handlers/motion.py` | Motor power switch (VMM_EN) |
| — | `hardware/revision.py` | Auto-detection via TCA9534A/EEPROM probe |
| — | `hardware/tca9534a.py` | TCA9534A I2C driver (P0=J-Link, P2=VMM_EN) |
| — | `hardware/context.py` | Feature gating (`has_motor_power_switch`, etc.) |

---

## Why Extend V1 Instead of Using V2

V2 (77 RPCs, 19 handlers, 4,579 lines) is overcomplicated. It adds debug
probe sessions, logic analyzers, BLE, RTT/SWO, I2C/SPI/CAN bus masters,
Zephyr-specific RPCs, and MQTT metrics — none of which Stage 4 uses. The
complexity makes it harder to reason about and slower to iterate on.

V1 (26 RPCs, 7 handlers, 2,202 lines) is simple, flat, and proven in
manufacturing. It needs targeted updates — not a rewrite.

| Property | V1 (current) | V2 (avoid) | V1 (target) |
|----------|-------------|-----------|------------|
| RPCs | 26 | 77 | ~23 |
| Handlers | 7 | 19 | 8 |
| Lines of code | ~2,200 | ~4,600 | ~3,000 (est.) |
| Sessions/state | None | Debug probe sessions | None |
| Middleware | None | MQTT, protocol decoders | None |
| Streaming | UartStream only | 8 streaming RPCs | 5 streaming RPCs |
| REV 1.2 support | No | Yes | Yes |
| Observability | No | Yes (background engine) | Yes (simpler) |

---

## What Changes

### RPCs Removed (4 removed)

| RPC | Why |
|-----|-----|
| `AltimeterRead` | Onboard MTIB sensor, not DUT — not needed |
| `AccelRead` | Onboard MTIB sensor, not DUT — not needed |
| `EnableAppProtect` | Not needed for validation workflow |
| File management (`ListFwFiles`, `UploadFwFile`, `DeleteFwFile`) | Stream firmware directly, no server-side storage |

### RPCs Consolidated (6 → 5)

| Before (V1) | After (Extended) | Change |
|-------------|-----------------|--------|
| `DutPowerEnable` | `PowerEnable(channel)` | Unified with channel enum |
| `DutPowerDisable` | `PowerDisable(channel)` | Unified with channel enum |
| `DutPowerRead` | `PowerRead(channel)` | Unified with channel enum |
| `DutChargePowerEnable` | (merged into PowerEnable) | Channel=CHARGER |
| `DutChargePowerDisable` | (merged into PowerDisable) | Channel=CHARGER |
| `DutChargePowerRead` | (merged into PowerRead) | Channel=CHARGER |

### RPCs Added (5 new)

| RPC | Category | Purpose |
|-----|----------|---------|
| `PowerMeasure` | Power | High-frequency sampling for power budget tests |
| `PowerStream` | Power | Continuous power streaming for long-duration tests |
| `GpioWatch` | GPIO | Streaming edge detection (button release timing, etc.) |
| `AdcStream` | ADC | Continuous ADC streaming (LED pattern analysis) |
| `GetSnapshot` | Observability | One-shot system state snapshot |

### Target RPC List (23 total)

| Category | RPCs | Status |
|----------|------|--------|
| Health | `HealthCheck` | Extend (add HW revision, capabilities) |
| UART | `UartStream` | Keep (cleanup broadcast model) |
| Flash | `ListProgrammers`, `FlashProgram`, `FlashErase` | Keep + add REV 1.2 J-Link mux |
| GPIO | `GpioConfig`, `GpioWrite`, `GpioRead`, `GpioWatch` | Keep 3 + add Watch |
| Power | `PowerEnable`, `PowerDisable`, `PowerRead`, `PowerMeasure`, `PowerStream` | Consolidate 6→3, add 2 |
| ADC | `AdcRead`, `AdcReadAll`, `AdcStream` | Keep 2 + add Stream |
| Motion | `GetMotionStatus`, `MotionStart`, `MotionHome`, `MotionStop` | Keep + add REV 1.2 motor switch |
| Observability | `GetSnapshot` | New |

---

## Work Units

Each unit is an independent, focused session. The user works with Claude on
one peripheral at a time. Units can be done in any order, though M1 (proto)
should come first and M10 (deploy) last.

### M1: Proto + Health — 4h

Update `libs/protocols/mtib/mtib.proto` to the target 23-RPC definition.
Extend `HealthCheck` response with hardware revision and capabilities.

**Investigate first:**
- Read the current V1 proto (`libs/protocols/mtib/mtib.proto`, 339 lines)
- Read the V2 proto (if separate) to see how V2 defines equivalent RPCs
- Search manufacturing code (`apps/manufacturing/alpha/`) for all proto
  imports — every `from protocols.mtib.mtib_pb2 import ...` line tells
  you what manufacturing depends on and what must not break
- Check V2's `HealthCheckResponse` (`hardware/context.py:system.py`) for
  the capabilities pattern — adapt it, don't reinvent

**Changes:**
- Remove: `AltimeterRead`, `AccelRead`, `EnableAppProtect`, file management RPCs
- Add: `PowerMeasure`, `PowerStream`, `GpioWatch`, `AdcStream`, `GetSnapshot`
- Consolidate: `DutPower*` + `DutChargePower*` → `Power*` with `PowerChannel` enum
- Extend: `HealthCheckResponse` with `hw_revision`, `capabilities` list
- **Keep old RPC names as aliases** — manufacturing imports
  `DutPowerRequest`, `DutPowerResponse` directly
- Regenerate Python bindings: `python -m grpc_tools.protoc ...`

**Produces:** Updated `.proto`, regenerated `_pb2.py` + `_pb2_grpc.py`

**Verification:** Bindings import without error; manufacturing code still imports cleanly

---

### M2: Power Handler — 8h

The largest handler change. Consolidate 6 RPCs into 5 with a channel enum,
add high-frequency sampling (`PowerMeasure`) and continuous streaming
(`PowerStream`).

**Investigate first:**
- Read V1's `services/mcp4017.py` — understand the voltage calculation
  formula. It currently assumes 100kΩ pot (REV 1.1). REV 1.2 uses 10kΩ
  pot with 3kΩ fixed resistor — the formula must branch on revision.
  Compare with V2's `hardware/revision.py:121-147` for correct values.
- Read V1's INA219 code — where does it live? What sample rate does it
  achieve? V2's `providers/handlers/power.py` has streaming — reference it.
- Read V1's `providers/mtib.py:185-234` to understand current power
  handler init and revision branching.
- Query the live MTIB server: `grpcurl -plaintext <ip>:50053
  mtib.MtibV1/DutPowerRead` to see current response shape.

**Current (V1):**
```
DutPowerEnable(voltage_v)     → PowerEnable(channel, voltage_v)
DutPowerDisable()             → PowerDisable(channel)
DutPowerRead()                → PowerRead(channel)
DutChargePowerEnable()        → (merged: channel=CHARGER)
DutChargePowerDisable()       → (merged: channel=CHARGER)
DutChargePowerRead()          → (merged: channel=CHARGER)
                              + PowerMeasure(channel, duration_s)  NEW
                              + PowerStream(channel)               NEW
```

**New RPCs:**
- `PowerMeasure(channel, duration_s)` → returns `avg_ma`, `peak_ma`,
  `min_ma`, `avg_mv`, `sample_count` — runs INA219 at max sample rate
  for the specified duration
- `PowerStream(channel)` → server-streaming, sends
  `(timestamp_ms, voltage_mv, current_ma)` samples continuously until
  client cancels

**Implementation notes:**
- INA219 sample rate: ~100 samples/sec at max resolution
- V1 already has `services/mcp4017.py` for voltage control — reuse it
- REV 1.2 uses 10kΩ pot (vs 100kΩ on REV 1.1) — different voltage
  calculation, detect revision and branch

**Verification:** `PowerEnable(DUT, 4.5)` → device boots, `PowerMeasure(DUT, 5)` → `avg_ma > 50`

---

### M3: GPIO Handler — 3h

Add `GpioWatch` — a server-streaming RPC that reports GPIO edge events.
Useful for detecting button release timing, charger detection edges, etc.

**Investigate first:**
- Read V1's `providers/mtib.py:35-68` — the GPIO pin maps for REV 1.1
  and REV 1.2 are **identical**. Is this intentional? Check the MTIB
  carrier board schematic on Confluence to see if the DUT-facing GPIO
  pin assignments actually differ between revisions. If they don't, the
  separate maps are unnecessary dead code.
- Read V1's existing GPIO handlers to understand the `gpiod` usage and
  how pins are mapped from logical DUT pin numbers to physical GPIO lines.
- Read V2's `providers/handlers/gpio.py` for the edge event streaming
  pattern — how does it use `gpiod.LineRequest.read_edge_events()`?

**Current (V1):** `GpioConfig`, `GpioWrite`, `GpioRead` — all kept as-is.

**New RPC:**
- `GpioWatch(pin, edge)` → server-streaming, sends `(timestamp_ms, pin, value)`
  on rising/falling/both edges

**Implementation notes:**
- V1 uses `gpiod` library for GPIO access — `gpiod` supports edge event
  monitoring natively via `LineRequest.read_edge_events()`
- Watch runs in a background thread, pushes events to the gRPC stream
- Multiple clients can watch the same pin (broadcast pattern)

**Verification:** `GpioWatch(pin=0, edge=BOTH)` while toggling button GPIO → events arrive

---

### M4: ADC Handler — 3h

Add `AdcStream` — continuous ADC streaming for LED pattern analysis and
long-duration temperature monitoring.

**Investigate first:**
- Read V1's `handlers/adc.py` (226 lines) — understand the IIO sysfs
  paths it uses for ADC reads. Are these paths the same on both
  revisions? Verify on live hardware: `ls /sys/bus/iio/devices/`.
- Read V2's `providers/handlers/adc.py` for the streaming pattern.
- Check: what sample rate can the IIO ADC sustain? The 100ms default
  interval (10 Hz) may be conservative — V2 may reveal actual limits.

**Current (V1):** `AdcRead(channel)`, `AdcReadAll` — both kept as-is.

**New RPC:**
- `AdcStream(channels, interval_ms)` → server-streaming, sends
  `(timestamp_ms, channel, value)` at the specified interval

**Implementation notes:**
- V1 already has `handlers/adc.py` (226 lines) with ADC read logic
- Stream is a simple loop: read channels, yield, sleep interval_ms
- Default interval: 100ms (10 Hz)

**Verification:** `AdcStream([0,1,3], 100)` → continuous RGB photodiode values

---

### M5: UART Handler — 3h

Cleanup the existing `UartStream` handler. V1's implementation works but
could be improved for reliability.

**Investigate first:**
- Read V1's UART handler code — find the broadcast model implementation,
  understand the threading model
- Read V2's UART handler for comparison — does it solve backpressure
  differently? Does it add timestamps?
- Check UART port paths on live hardware — V1 uses `/dev/ttyUSB0` but
  the CLAUDE.md hardware rules say `uart0=/dev/verdin-uart1` and
  `uart1=/dev/verdin-uart2`. Are these the same physical ports? Verify
  with `ls -la /dev/ttyUSB* /dev/verdin-uart*` on a live node.
- Check: how does V1 handle the two UART ports (one per MCU)? Does it
  multiplex, or only use one?

**What to review:**
- Multi-client broadcast model (one RX thread → fan out to per-client queues)
- Backpressure handling (what happens when a client reads slowly?)
- Port lifecycle (when does the serial port open/close?)
- Error recovery (what happens on USB disconnect/reconnect?)
- Timestamp injection (add receive timestamps to responses)

**No new RPCs.** This is a cleanup/hardening pass.

**Verification:** Two clients subscribe simultaneously, both receive same
UART data without loss or corruption

---

### M6: Flash Handler — 6h

Remove server-side file management. Add firmware streaming (client sends
hex data, server flashes directly). Add REV 1.2 J-Link mux support.

**Investigate first:**
- Read V1's `handlers/firmware.py` (674 lines) — understand the file
  management code being removed vs the flash logic being kept
- Read V2's `providers/handlers/target.py:144-146, 232-242` — this is
  exactly how V2 controls the J-Link mux before flashing. The TCA9534A
  P0 pin selects the target MCU. Adapt this, don't guess the register
  values.
- Read V2's `hardware/tca9534a.py` — understand the full TCA9534A driver
  (pin definitions, I2C register map, bus number). The I2C bus number
  may be 1 or 3 depending on the Verdin BSP version — V2 uses bus 3.
  Verify on the live hardware: `i2cdetect -y 1` and `i2cdetect -y 3`.
- Check if `smbus2` is already a dependency in V1's requirements.txt

**Removed RPCs:** `ListFwFiles`, `UploadFwFile`, `DeleteFwFile`

**Kept RPCs:** `ListProgrammers`, `FlashProgram`, `FlashErase`

**Changes to FlashProgram:**
- Accept hex data as streaming chunks (client sends, server writes to
  temp file, runs nrfjprog)
- Add `--recover` before `--program` (always, per hardware rules)
- Add `--speed 4000` (always, per hardware rules)
- For REV 1.2: control J-Link mux via TCA9534A P0 before flash
  - P0=LOW → nRF52840, P0=HIGH → nRF9151

**Implementation notes:**
- V1's `handlers/firmware.py` (674 lines) is the largest handler — much
  of this is file management code that gets removed
- nrfjprog is only available inside the K8s pod
- J-Link mux control: Use `smbus2` library (same as V2's approach).
  Do not shell out to `i2cset` — use the same programmatic pattern as V2.

**Verification:** Flash nRF52840 hex via streaming → device boots

---

### M7: Motion Handler — 3h

Add REV 1.2 motor power switch support. The motor power MOSFET
(TCA9534A P2 / `VMM_EN`) keeps the motor off at startup on REV 1.2. It
must be enabled before FluidNC commands work. On REV 1.1, there is no
MOSFET — the motor is always powered when the system is powered.

**Investigate first:**
- Read V1's `services/fluidnc.py` — understand the G-code serial
  communication, port lifecycle, and existing motion handler flow
- Read V2's `providers/handlers/motion.py` — see how V2 handles
  VMM_EN enable/disable around motion commands
- Read V2's `hardware/context.py:has_motor_power_switch` — the feature
  gate pattern. On REV 1.1, `set_motor_power()` is a no-op with a
  warning log. Adapt the same graceful degradation.
- **Important:** `MOTION_ENABLED` is about whether a motion scaffold is
  attached (deployment config), NOT about the hardware revision. Both
  revisions can do motion. The VMM_EN MOSFET is a startup safety feature
  on REV 1.2 only.

**Current (V1):** `GetMotionStatus`, `MotionStart`, `MotionHome`, `MotionStop`
— all kept as-is.

**Changes:**
- On REV 1.2: enable `VMM_EN` (TCA9534A P2) before any motion command
- Disable `VMM_EN` after `MotionStop` or `MotionHome` completes (power saving)
- Auto-detect revision and skip TCA9534A access on REV 1.1 (graceful no-op)

**Implementation notes:**
- V1's `services/fluidnc.py` handles serial G-code communication
- Motor power switch is a single I2C write to TCA9534A

**Verification:** `MotionStart` → actuator moves, `MotionStop` → actuator stops,
`VMM_EN` toggles (verify with I2C read)

---

### M8: Observability — 10h

New subsystem. A background polling engine that samples power, GPIO, ADC,
UART activity, and motion state. Exposed via a single `GetSnapshot` RPC
that returns all current values in one response.

**Investigate first:**
- Read V2's observability engine (`providers/handlers/system.py`,
  `hardware/context.py`) — V2 exposes hardware capabilities and state in
  `HealthCheck`. Understand what V2 includes in its system snapshot and
  adapt the useful parts.
- Check: does V1 have any existing health/status reporting beyond
  `HealthCheck`? Search for any metrics, MQTT publishing, or status
  endpoints already in V1's code.
- Consider: the `METRICS_ENABLED` and `METRICS_BROKER_URL` env vars in
  the deployment manifests suggest V1 has some MQTT metrics code. Read
  it — if it exists, can it be repurposed or does it conflict?

**New RPC:**
- `GetSnapshot` → returns `(power: {v, ma}, gpio: {pin: val}, adc: {ch: val},
  uart: {rx_bytes, tx_bytes}, motion: {state, position})`

**Implementation:**
```
observability/
├── engine.py      # Background thread, polls all peripherals at 1Hz
└── snapshot.py    # Snapshot data model + GetSnapshot handler
```

**Design:**
- Single background thread polls power, GPIO state, ADC channels at 1Hz
- Stores latest values in a thread-safe snapshot object
- `GetSnapshot` returns the latest snapshot (no hardware access in the RPC
  itself — just reads cached values)
- Lightweight: 1 I2C read (INA219) + 1 gpiod read + 1 ADC read per second

**What this is NOT:**
- Not a streaming RPC (the redesign spec had `ObservabilityStream` — defer
  that until proven needed. `GetSnapshot` polling from the client is simpler
  and sufficient for dashboards.)
- Not a full V2 observability engine (no UART observer, no motion tracker)

**Verification:** `GetSnapshot` → returns populated values matching current hardware state

---

### M9: Cleanup + Client — 4h

Remove dead code, update the V1 Python client to match the new proto.

**Investigate first:**
- Read V2's `hardware/revision.py:214-262` — the auto-detection logic
  probes TCA9534A and AT24C02C with `force=True` because the kernel
  `gpio-pca953x` driver claims address 0x38. Verify this is still the
  case on the live nodes: `ls /sys/bus/i2c/devices/` and check what
  driver owns 0x38. If the driver is present, you must use `force=True`
  in `smbus2` calls.
- Read V1's client (`libs/python/corekinect/mtib_client/v1/client/core.py`)
  — understand the existing `(value, error)` tuple pattern, method
  signatures, and how streaming RPCs (like `UartStream`) are wrapped.
- Read manufacturing code imports (`apps/manufacturing/alpha/src/tests/
  shared/rpcs.py`) — verify the full list of proto imports that must
  remain working after the proto update. This is the backward
  compatibility boundary.
- Check the V1 naming convention: `HARDWARE_VERSION` (string "REV1.1")
  vs V2's `MTIB_HARDWARE_REVISION` (numeric "1.2"). Decide which to
  standardize on and document the decision.

**Server cleanup:**
- Remove `handlers/sensors.py` (onboard sensor RPCs removed)
- Remove file management code from `handlers/firmware.py`
- Remove `EnableAppProtect` handler
- Add hardware revision detection in `main.py` startup (probe TCA9534A at
  0x38 — present = REV 1.2, absent = REV 1.1)
- Update `providers/mtib.py` to wire new RPCs to handlers

**Client update (`libs/python/corekinect/mtib_client/v1/`):**
- Add methods for new RPCs: `power_measure()`, `power_stream()`,
  `gpio_watch()`, `adc_stream()`, `get_snapshot()`
- Update `power_enable()` / `power_disable()` / `power_read()` to accept
  `channel` parameter (default: DUT for backward compat)
- Remove methods for removed RPCs
- Keep Go-like error handling pattern: `(value, error)` tuples

**Verification:** All client methods work against the running server

---

### M10: Deploy + Verify — 4h

Containerize, deploy to K3s on **both** MTIB nodes, verify all 23 RPCs on
real hardware with both revisions.

**Prerequisites:** Phase 0 K8s node onboarding complete — both validation
nodes in cluster, labeled with `mtib-revision`, per-revision deployment
manifests created (`validation-rev11.yaml`, `validation-rev12.yaml`).

**Nodes (verified 2026-03-01):**
- REV 1.2: `verdin-imx8mm-15005665` at 10.4.45.33 — in cluster, labeled
- REV 1.1: `verdin-imx8mm-15702161` at 10.4.45.32 — in cluster, labeled

**Steps:**
1. Build Docker image (ARM64, same Dockerfile pattern as V1)
2. Push to `containers.ad.corekinect.com`
3. Update `validation-rev11.yaml` + `validation-rev12.yaml` image tag
4. `kubectl apply` both manifests — pods roll out on correct nodes
5. (Optional) Consolidate back to single `validation.yaml` with `replicas: 2`
   now that auto-detection works (Phase 1 M9 added TCA9534A probe)
6. Run verification script against **both** nodes

**Verification script covers (run on each node):**
- `HealthCheck` → returns correct HW revision (1.1 or 1.2)
- `PowerEnable(DUT, 4.5)` → device boots (>50mA)
- `PowerMeasure(DUT, 5)` → returns stats
- `GpioWrite(0, LOW)` / `GpioRead(0)` → round-trip
- `GpioWatch(0, BOTH)` → events on edge
- `UartStream` → bidirectional data (using correct firmware for MTIB rev)
- `AdcReadAll` → values from all channels
- `AdcStream([0,1,3], 100)` → continuous values
- `FlashProgram` → stream hex (using correct firmware for MTIB rev), device boots
- `MotionStart` / `MotionStop` → actuator moves on **both** revisions (REV 1.2: VMM_EN toggles; REV 1.1: motor always powered, no switch to verify)
- `GetSnapshot` → all fields populated

**REV 1.1-specific:** No TCA9534A, so J-Link mux and motor power switch
RPCs should gracefully degrade (return "not supported" or skip internal
TCA9534A calls). The server detects revision at startup and branches.

**Manufacturing compatibility:** Existing manufacturing code uses V1 RPCs
directly. The power consolidation (`DutPowerEnable` → `PowerEnable`) is a
breaking change. Options:
1. **Keep old RPCs as aliases** (add `DutPowerEnable` that delegates to
   `PowerEnable(channel=DUT)`) — backward compatible, zero manufacturing changes
2. **Update manufacturing code** — small change, but requires coordination

Decision: **Option 1 (aliases)** for this proof. Migrate manufacturing later.

---

## Effort Summary

| Unit | Peripheral | Effort | Dependencies |
|------|-----------|--------|-------------|
| M1 | Proto + health | 4h | None |
| M2 | Power | 8h | M1 |
| M3 | GPIO | 3h | M1 |
| M4 | ADC | 3h | M1 |
| M5 | UART | 3h | None (cleanup only) |
| M6 | Flash | 6h | M1 |
| M7 | Motion | 3h | M1 |
| M8 | Observability | 10h | M1 |
| M9 | Cleanup + client | 4h | M2-M8 |
| M10 | Deploy + verify | 4h | M9 |
| **Total** | | **48h** | |

**Order:** M1 first → M2-M8 in any order → M9 → M10

M2-M8 are independent of each other — the user picks whichever peripheral
they want to work on next. Each is a self-contained session with Claude.

---

## Phase 1 Checkpoint

| Check | Status |
|-------|--------|
| Proto updated to 23 RPCs, bindings regenerated | |
| Power handler: channel enum, PowerMeasure, PowerStream | |
| GPIO handler: GpioWatch streaming | |
| ADC handler: AdcStream | |
| UART handler: cleaned up, multi-client verified | |
| Flash handler: streaming, no file mgmt, REV 1.2 mux | |
| Motion handler: REV 1.2 motor power switch | |
| Observability: GetSnapshot returns populated data | |
| HW revision auto-detection works (TCA9534A probe) | |
| REV 1.1 graceful degradation (no TCA9534A features) | |
| Client updated with new methods | |
| Server deployed to K3s on **REV 1.2 node**, all RPCs verified | |
| Server deployed to K3s on **REV 1.1 node**, all RPCs verified | |
| Manufacturing backward compatibility confirmed | |
