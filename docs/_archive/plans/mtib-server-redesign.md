# MTIB Server Redesign Specification

> **Goal:** Replace the current MTIB server with a clean, v1-style implementation
> that supports REV 1.2 hardware and adds observability for live monitoring —
> without the complexity of v2's 71-RPC surface area.
>
> **Design principle:** Simple hardware pipe. No protocol awareness, no debug
> sessions, no logic analyzers. The MTIB exposes raw hardware — clients decide
> what to do with it.
>
> **Date:** 2026-02-25

---

## Table of Contents

1. [Design Philosophy](#1-design-philosophy)
2. [Proto Service Definition](#2-proto-service-definition)
3. [Hardware Interface — REV 1.2](#3-hardware-interface--rev-12)
4. [UART Architecture](#4-uart-architecture)
5. [Observability](#5-observability)
6. [Deployment Model](#6-deployment-model)
7. [System Requirements](#7-system-requirements)
8. [Implementation Guidance](#8-implementation-guidance)

---

## 1. Design Philosophy

### What v1 got right

- 26 RPCs, 7 handlers, flat structure
- Call an RPC, hardware does the thing, get a response
- No sessions, no abstractions, no middleware
- Single proto file, single service, single process

### What v2 got wrong

- 71 RPCs across 14 categories — most unused
- Debug probe session management (15 RPCs) for a capability we use `nrfjprog` for
- Digital signal analyzer, bus master interfaces, BLE, Zephyr-specific RPCs
- Speculative generalization for use cases that don't exist

### What the redesign keeps from v2

- **Observability engine** — background polling of power, GPIO, ADC state. Exposed
  via gRPC for the Concord HTTP API backend to query and surface in live dashboards
- **REV 1.2 hardware support** — TCA9534A GPIO expander, J-Link multiplexer,
  switchable motor power, EEPROM
- **Streaming variants** — `GpioWatch`, `PowerStream`, `AdcStream` for
  continuous monitoring during test execution
- **Hardware revision auto-detection** at startup via I2C probing

### What gets cut entirely

- Debug probe sessions (DebugConnect/Halt/Resume/Step/Registers/Memory/Breakpoints)
- RTT streaming
- SWO/ITM trace
- Digital signal analyzer (Saleae)
- Bus master interfaces (I2C/SPI/CAN master)
- BLE scan/connect
- Zephyr-specific RPCs (ZephyrShell, ZephyrLogStream, TwisterRun)
- MQTT metrics publishing
- File management RPCs (ListFiles/UploadFile/DownloadFile/DeleteFile)

### Concord protocol awareness

**None.** The MTIB server streams raw UART bytes. It does not know about
`[CONCORD:RSP]`, `[CONCORD:EVT]`, or Zephyr shell commands. Protocol parsing
happens client-side in the Python test framework's `UartDemuxer`. This keeps
the MTIB generic and reusable for manufacturing, validation, and any future
use case.

---

## 2. Proto Service Definition

Package: `mtib`
Service: `Mtib`
Port: `50052`
File: `concord/libs/protocols/mtib/mtib.proto`

Replaces the existing v1 proto at the same path.

### 2.1 Service — 23 RPCs

```protobuf
syntax = "proto3";

package mtib;

option go_package = "bitbucket.org/corekinect/concord/libs/protocols/mtib";

service Mtib {
  // ═══ Health ═══
  rpc HealthCheck(HealthCheckRequest) returns (HealthCheckResponse);

  // ═══ UART ═══
  rpc UartStream(stream UartRequest) returns (stream UartResponse);

  // ═══ Flash Programming (via nrfjprog / J-Link) ═══
  rpc ListProgrammers(ListProgrammersRequest) returns (ListProgrammersResponse);
  rpc FlashProgram(stream FlashProgramRequest) returns (FlashProgramResponse);
  rpc FlashErase(FlashEraseRequest) returns (FlashEraseResponse);

  // ═══ GPIO ═══
  rpc GpioConfig(GpioConfigRequest) returns (GpioConfigResponse);
  rpc GpioWrite(GpioWriteRequest) returns (GpioWriteResponse);
  rpc GpioRead(GpioReadRequest) returns (GpioReadResponse);
  rpc GpioWatch(GpioWatchRequest) returns (stream GpioEvent);

  // ═══ Power ═══
  rpc PowerEnable(PowerEnableRequest) returns (PowerEnableResponse);
  rpc PowerDisable(PowerDisableRequest) returns (PowerDisableResponse);
  rpc PowerRead(PowerReadRequest) returns (PowerReadResponse);
  rpc PowerMeasure(PowerMeasureRequest) returns (PowerMeasureResponse);
  rpc PowerStream(PowerStreamRequest) returns (stream PowerSample);

  // ═══ ADC ═══
  rpc AdcRead(AdcReadRequest) returns (AdcReadResponse);
  rpc AdcReadAll(AdcReadAllRequest) returns (AdcReadAllResponse);
  rpc AdcStream(AdcStreamRequest) returns (stream AdcSample);

  // ═══ Motion (FluidNC) ═══
  rpc GetMotionStatus(GetMotionStatusRequest) returns (GetMotionStatusResponse);
  rpc MotionStart(MotionStartRequest) returns (stream MotionProgress);
  rpc MotionHome(MotionHomeRequest) returns (MotionHomeResponse);
  rpc MotionStop(MotionStopRequest) returns (MotionStopResponse);

  // ═══ Observability ═══
  rpc GetSnapshot(GetSnapshotRequest) returns (Snapshot);
  rpc ObservabilityStream(ObservabilityStreamRequest) returns (stream Snapshot);
}
```

### 2.2 RPC comparison: v1 → redesign

| v1 RPC | Redesign RPC | Change |
|--------|-------------|--------|
| `HealthCheck` | `HealthCheck` | Added hw revision, capabilities |
| `GpioConfig` | `GpioConfig` | Same |
| `GpioWrite` | `GpioWrite` | Same |
| `GpioRead` | `GpioRead` | Same |
| — | `GpioWatch` | **NEW** — streaming edge events |
| `AdcRead` | `AdcRead` | Same |
| `AdcReadAll` | `AdcReadAll` | Same |
| — | `AdcStream` | **NEW** — continuous sampling |
| `DutPowerEnable` | `PowerEnable(channel=DUT)` | Unified with channel param |
| `DutPowerDisable` | `PowerDisable(channel=DUT)` | Unified |
| `DutPowerRead` | `PowerRead(channel=DUT)` | Unified |
| `DutChargePowerEnable` | `PowerEnable(channel=CHARGER)` | Unified |
| `DutChargePowerDisable` | `PowerDisable(channel=CHARGER)` | Unified |
| `DutChargePowerRead` | `PowerRead(channel=CHARGER)` | Unified |
| — | `PowerMeasure` | **NEW** — duration-based stats |
| — | `PowerStream` | **NEW** — continuous sampling |
| `AltimeterRead` | — | **REMOVED** — onboard sensor, not DUT |
| `AccelRead` | — | **REMOVED** — onboard sensor, not DUT |
| `GetMotionStatus` | `GetMotionStatus` | Same |
| `MotionStart` | `MotionStart` | Same (streaming progress) |
| `MotionHome` | `MotionHome` | Same |
| `MotionStop` | `MotionStop` | Same |
| `ListProgrammers` | `ListProgrammers` | Same |
| `ListFwFiles` | — | **REMOVED** — FlashProgram streams directly |
| `UploadFwFile` | — | **REMOVED** — FlashProgram streams directly |
| `DeleteFwFile` | — | **REMOVED** — no file management |
| `FlashFwFile` | `FlashProgram` | Combined upload + flash |
| `EraseFlash` | `FlashErase` | Renamed |
| `EnableAppProtect` | — | **REMOVED** — not needed for validation |
| `UartStream` | `UartStream` | Same (bidir streaming) |
| — | `GetSnapshot` | **NEW** — observability |
| — | `ObservabilityStream` | **NEW** — observability |

**Net:** 26 → 23 RPCs. Removed 8 (file management, sensors, app protect, redundant power). Added 5 (streaming variants, observability).

### 2.3 Key Message Types

```protobuf
// ─── Shared ───

message Empty {}

// ─── Health ───

message HealthCheckRequest {}

message HealthCheckResponse {
  bool ready = 1;
  string hardware_revision = 2;        // "1.1" or "1.2"
  repeated string capabilities = 3;    // ["gpio_expander", "jlink_mux", "motor_power_switch"]
  repeated string errors = 4;
}

// ─── UART ───
// First request in the stream specifies which UART device to open.
// Subsequent requests carry TX data. Responses carry RX data.
// Multiple clients can subscribe to the same UART — all receive
// the same RX bytes (broadcast architecture).

message UartRequest {
  HostType target = 1;    // Which UART device (maps to /dev/verdin-uartN)
  bytes data = 2;         // TX data (empty on first request to just subscribe)
}

message UartResponse {
  HostType source = 1;
  bytes data = 2;
}

// ─── Flash ───

enum HostType {
  HOST_TYPE_UNDEFINED = 0;
  HOST_TYPE_NRF9160 = 1;
  HOST_TYPE_NRF52840 = 3;
  HOST_TYPE_NRF5340 = 4;
  HOST_TYPE_NRF9151 = 5;
}

message ListProgrammersRequest {}

message Programmer {
  string serial_number = 1;
  HostType detected_target = 2;
}

message ListProgrammersResponse {
  bool success = 1;
  string message = 2;
  repeated Programmer programmers = 3;
}

// FlashProgram: client streams firmware file chunks, server flashes.
// First message: metadata (target, options). Subsequent: file chunks.
message FlashProgramRequest {
  HostType target = 1;
  bytes firmware_chunk = 2;     // Binary firmware data (chunked)
  bool recover = 3;             // Attempt recovery before flash
  bool sector_erase = 4;        // Sector erase before write
  bool is_last_chunk = 5;       // Signals end of firmware stream
}

message FlashProgramResponse {
  bool success = 1;
  string message = 2;
  int32 flash_time_ms = 3;
}

message FlashEraseRequest {
  HostType target = 1;
  bool recover = 2;             // Full recovery erase
}

message FlashEraseResponse {
  bool success = 1;
  string message = 2;
}

// ─── GPIO ───

enum GpioDirection {
  GPIO_DIRECTION_UNDEFINED = 0;
  GPIO_DIRECTION_INPUT = 1;
  GPIO_DIRECTION_OUTPUT = 2;
}

enum GpioResistor {
  GPIO_RESISTOR_UNDEFINED = 0;
  GPIO_RESISTOR_PULL_UP = 1;
  GPIO_RESISTOR_PULL_DOWN = 2;
  GPIO_RESISTOR_NONE = 3;
}

message GpioConfigRequest {
  int32 pin = 1;                // Logical pin 0-7
  GpioDirection direction = 2;
  GpioResistor resistor = 3;
}

message GpioConfigResponse {
  bool success = 1;
  string message = 2;
}

message GpioWriteRequest {
  int32 pin = 1;
  bool value = 2;
}

message GpioWriteResponse {
  bool success = 1;
  string message = 2;
}

message GpioReadRequest {
  int32 pin = 1;
}

message GpioReadResponse {
  bool success = 1;
  string message = 2;
  bool value = 3;
}

message GpioWatchRequest {
  int32 pin = 1;                // Pin to watch (-1 for all configured inputs)
  bool rising_edge = 2;
  bool falling_edge = 3;
}

message GpioEvent {
  int32 pin = 1;
  bool value = 2;
  int64 timestamp_ns = 3;      // Monotonic nanosecond timestamp
}

// ─── Power ───

enum PowerChannel {
  POWER_CHANNEL_DUT = 0;        // Main DUT power (INA219 @ 0x40)
  POWER_CHANNEL_CHARGER = 1;    // Charger power (INA219 @ 0x41)
}

message PowerEnableRequest {
  PowerChannel channel = 1;
  double voltage_v = 2;         // Target voltage (0.8-5.5V for DUT, 5V for charger)
}

message PowerEnableResponse {
  bool success = 1;
  string message = 2;
  double actual_voltage_v = 3;  // Measured voltage after settling
}

message PowerDisableRequest {
  PowerChannel channel = 1;
}

message PowerDisableResponse {
  bool success = 1;
  string message = 2;
}

message PowerReadRequest {
  PowerChannel channel = 1;
}

message PowerReadResponse {
  bool success = 1;
  string message = 2;
  double current_a = 3;
  double voltage_v = 4;
  double power_w = 5;
}

message PowerMeasureRequest {
  PowerChannel channel = 1;
  double duration_s = 2;        // Measurement duration
  double sample_rate_hz = 3;    // Samples per second (max ~10Hz via hwmon)
}

message PowerMeasureResponse {
  bool success = 1;
  string message = 2;
  double avg_current_a = 3;
  double min_current_a = 4;
  double max_current_a = 5;
  double avg_voltage_v = 6;
  double avg_power_w = 7;
  double energy_j = 8;          // Total energy (power × time)
  int32 sample_count = 9;
  double duration_s = 10;
}

message PowerStreamRequest {
  PowerChannel channel = 1;
  double sample_rate_hz = 2;    // Target rate (best-effort, max ~10Hz)
}

message PowerSample {
  double current_a = 1;
  double voltage_v = 2;
  double power_w = 3;
  int64 timestamp_ns = 4;       // Monotonic nanosecond timestamp
}

// ─── ADC ───

message AdcReadRequest {
  int32 channel = 1;            // Channel 0-7
}

message AdcReadResponse {
  bool success = 1;
  string message = 2;
  double voltage_v = 3;
}

message AdcReadAllRequest {}

message AdcReadAllResponse {
  bool success = 1;
  string message = 2;
  repeated double voltages_v = 3;   // 8 values, index = channel
}

message AdcStreamRequest {
  repeated int32 channels = 1;  // Which channels to stream (empty = all)
  double sample_rate_hz = 2;    // Target rate per channel
}

message AdcSample {
  int32 channel = 1;
  double voltage_v = 2;
  int64 timestamp_ns = 3;
}

// ─── Motion ───

enum MotionStatus {
  MOTION_STATUS_UNDEFINED = 0;
  MOTION_STATUS_IDLE = 1;
  MOTION_STATUS_MOVING = 2;
  MOTION_STATUS_ERRORED = 3;
}

message GetMotionStatusRequest {}

message GetMotionStatusResponse {
  bool success = 1;
  string message = 2;
  MotionStatus status = 3;
  optional double time_elapsed_s = 4;
  optional double distance_covered_mm = 5;
  optional double distance_remaining_mm = 6;
  optional double time_remaining_s = 7;
}

message MotionStartRequest {
  float dwell_seconds = 1;      // Dwell at each end
  float speed_mm_s = 2;
  float accel_mm_s2 = 3;
  oneof move_type {
    float duration_seconds = 4; // Move back and forth for duration
    float distance_mm = 5;      // Move a specific distance
  }
}

message MotionProgress {
  bool success = 1;
  string message = 2;
  MotionStatus status = 3;
  double time_elapsed_s = 4;
  double distance_covered_mm = 5;
  double distance_remaining_mm = 6;
  double time_remaining_s = 7;
}

message MotionHomeRequest {}
message MotionHomeResponse {
  bool success = 1;
  string message = 2;
}

message MotionStopRequest {}
message MotionStopResponse {
  bool success = 1;
  string message = 2;
}

// ─── Observability ───

message GetSnapshotRequest {
  bool include_power = 1;
  bool include_gpio = 2;
  bool include_adc = 3;
  bool include_uart = 4;
  bool include_motion = 5;
  bool include_system = 6;
}

message ObservabilityStreamRequest {
  double interval_s = 1;        // Min 0.1s between snapshots
  bool include_power = 2;
  bool include_gpio = 3;
  bool include_adc = 4;
  bool include_uart = 5;
  bool include_motion = 6;
  bool include_system = 7;
}

message Snapshot {
  int64 timestamp_ns = 1;
  string hardware_revision = 2;

  // Power state
  optional PowerReadResponse dut_power = 10;
  optional PowerReadResponse charger_power = 11;
  optional bool dut_power_enabled = 12;
  optional bool charger_power_enabled = 13;

  // GPIO state
  repeated GpioPin gpio_pins = 20;

  // ADC readings
  repeated double adc_voltages_v = 30;   // 8 values

  // UART state (no content — just statistics)
  repeated UartPortStatus uart_ports = 40;

  // Motion
  optional MotionStatus motion_status = 50;

  // System
  optional SystemInfo system = 60;
}

message GpioPin {
  int32 pin = 1;
  GpioDirection direction = 2;
  bool value = 3;
}

message UartPortStatus {
  string device = 1;            // e.g. "/dev/verdin-uart1"
  bool connected = 2;
  int64 bytes_rx = 3;
  int64 bytes_tx = 4;
  int32 active_clients = 5;
}

message SystemInfo {
  string hostname = 1;
  double cpu_percent = 2;
  double memory_percent = 3;
  double disk_percent = 4;
  int64 uptime_s = 5;
}
```

---

## 3. Hardware Interface — REV 1.2

### 3.1 Physical topology

```
┌──────────────────────────────────────────────────────────────────────┐
│  Verdin iMX8M Mini (K3s node: verdin-imx8mm-15702160)              │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │  MTIB Server Pod (privileged, port 50052)                     │ │
│  │  ┌──────┐ ┌──────┐ ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐ ┌──────┐│ │
│  │  │Power │ │ GPIO │ │ ADC │ │UART │ │Flash│ │Obsrv│ │Motion││ │
│  │  └──┬───┘ └──┬───┘ └──┬──┘ └──┬──┘ └──┬──┘ └──┬──┘ └──┬───┘│ │
│  └─────┼────────┼────────┼───────┼───────┼───────┼───────┼─────┘ │
│        │        │        │       │       │       │       │       │
│  ┌─────┼────────┼────────┼───────┼───────┼───────┼───────┼─────┐ │
│  │  MTIB Carrier Board REV 1.2                                  │ │
│  │                                                              │ │
│  │  INA219×2   TXS0108   ADS1115×2  UART    J-Link×2  TCA9534A │ │
│  │  MCP4017    7 DUT I/O  8 ch ADC  2 port  SN74CBT   ESP32    │ │
│  │  TPS63802                                 (mux)     FluidNC  │ │
│  └──────────────────────────────┬───────────────────────────────┘ │
└─────────────────────────────────┼─────────────────────────────────┘
                                  │ 48-pin DUT connector
                                  │
                    ┌─────────────┴─────────────┐
                    │  Alpha B0 (fixture board)  │
                    │  nRF52840 app + nRF9151    │
                    │  comms on scaffold rail    │
                    └───────────────────────────┘
```

### 3.2 48-pin DUT connector signals used

| Pin(s) | Signal | MTIB Resource | Alpha B0 Connection |
|--------|--------|---------------|---------------------|
| 1 | DUT_VDD | Power handler (MCP4017 + TPS63802) | Main power rail |
| 2 | GND | Common ground | — |
| 3-5 | SWDIO, SWCLK, nRESET | Flash handler (J-Link via nrfjprog) | nRF52840 SWD |
| 7-8 | UART_TX, UART_RX | UART handler (pyserial) | nRF52840 UART0 (P0.06/P0.08) |
| 9-15 | GPIO0-6 | GPIO handler (gpiod, level-shifted via TXS0108) | See fixture mapping |
| 16-23 | ADC0-7 | ADC handler (ADS1115 via IIO sysfs) | See fixture mapping |
| 30 | DUT_VIO | Level-shifter reference | 1.8V from Alpha |

### 3.3 I2C device map (I2C bus 1)

| Address | Device | Handler | Notes |
|---------|--------|---------|-------|
| 0x2F | MCP4017 digital pot | Power | REV 1.2: 10kΩ, REV 1.1: 100kΩ |
| 0x38 | TCA9534A GPIO expander | GPIO (internal) | REV 1.2 only — J-Link mux, motor power |
| 0x40 | INA219 current monitor | Power (DUT) | 100mΩ shunt, 0-3.2A |
| 0x41 | INA219 current monitor | Power (charger) | 100mΩ shunt |
| 0x48 | ADS1115 16-bit ADC | ADC (ch 0-3) | 82k/33k divider, ±6.144V range |
| 0x49 | ADS1115 16-bit ADC | ADC (ch 4-7) | Same |
| 0x50 | AT24C02C EEPROM | Health (board ID) | REV 1.2 only |

### 3.4 UART device mapping

| Logical Name | Device Path | Alpha B0 MCU | Baud | Purpose |
|-------------|-------------|-------------|------|---------|
| `uart0` | `/dev/verdin-uart1` | nRF9151 (comms) | 115200 | Comms MCU logs |
| `uart1` | `/dev/verdin-uart2` | nRF52840 (app) | 115200 | Shell + harness + logs |

> **Critical:** `uart1` (nRF52840) carries ALL traffic for Stage 3:
> shell commands, `[CONCORD:RSP]` responses, `[CONCORD:EVT]` events,
> and Zephyr log lines — all interleaved on one 115200 8N1 link. The MTIB
> streams raw bytes; the Python-side `UartDemuxer` does prefix-based routing.

### 3.5 Motion system

| Component | Details |
|-----------|---------|
| Controller | ESP32-U4WDH running FluidNC |
| Connection | USB-serial via CP2102N on USB2514B hub |
| Drivers | 2× A4988 stepper drivers |
| Axis | X only — 500mm travel, 80 steps/mm |
| Homing | Limit switches (negative and positive ends) |
| Motor power | REV 1.2: switchable via TCA9534A P2 (VMM_EN) |
| | REV 1.1: always on when EXT_VMM supplied |

The scaffold moves the Alpha+MTIB assembly on a linear rail. Motion
triggers the Alpha's LSM6DSO accelerometer. Intensity and duration
are controlled via `MotionStart` parameters.

### 3.6 REV 1.2 internal control (TCA9534A @ 0x38)

These are NOT exposed as user-facing GPIO. They are managed internally
by the server for hardware control:

| Pin | Signal | Purpose | Managed By |
|-----|--------|---------|-----------|
| P0 | JLINK_MUL | J-Link multiplexer select | Flash handler |
| P1 | EEPROM_WP | EEPROM write protect | Health handler |
| P2 | VMM_EN | Motor power enable | Motion handler |
| P3-P7 | Reserved | — | — |

---

## 4. UART Architecture

### 4.1 Multi-client broadcast

The UART handler maintains a single physical connection per device path.
When a client opens a `UartStream`, it subscribes to the RX broadcast:

```
                    ┌─────────────────────┐
Physical UART ────► │  RX Thread          │
  (pyserial)        │  reads continuously │
                    └─────────┬───────────┘
                              │ broadcast
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
        ┌──────────┐   ┌──────────┐   ┌──────────┐
        │ Client 1 │   │ Client 2 │   │ Client 3 │
        │ (test    │   │ (live    │   │ (artifact│
        │ runner)  │   │ monitor) │   │ saver)   │
        └──────────┘   └──────────┘   └──────────┘
```

- Every RX byte is delivered to every subscribed client
- TX from any client goes to the physical UART immediately
- Clients subscribe/unsubscribe dynamically by opening/closing streams
- RX latency target: < 10ms from physical byte to gRPC delivery

### 4.2 What the MTIB does NOT do

- Parse `[CONCORD:RSP]` or `[CONCORD:EVT]` prefixes
- Understand Zephyr shell commands
- Filter or route based on content
- Buffer lines or add framing

### 4.3 What the client (Python test framework) does

The `UartDemuxer` in `concord/libs/corekinect/test/validation/` reads
raw bytes from the UART gRPC stream and splits each line by prefix:

| Line starts with | Routed to | Purpose |
|-----------------|-----------|---------|
| `[CONCORD:RSP] ` | `response_queue` | Shell command responses |
| `[CONCORD:EVT] ` | `event_queue` | Async firmware events |
| Everything else | `log_buffer` | Zephyr log lines, shell prompts |

---

## 5. Observability

### 5.1 Purpose

The observability system runs background polling threads that continuously
sample hardware state. This serves two purposes:

1. **Live monitoring** — The Concord HTTP API backend queries the MTIB
   server's `GetSnapshot` RPC to display real-time node status in dashboards
2. **Test artifact enrichment** — Tests can capture power/ADC traces alongside
   test execution without adding measurement RPCs to the test logic itself

### 5.2 Background monitors

| Monitor | Source | Poll Rate | Data |
|---------|--------|-----------|------|
| Power | INA219 via hwmon sysfs | ~10Hz | Voltage, current, power per channel |
| GPIO | gpiod pin state | On-change | Pin direction, value |
| ADC | ADS1115 via IIO sysfs | ~1Hz | 8 channel voltages |
| UART | Internal counters | On-demand | Bytes rx/tx, client count |
| System | `/proc` | ~0.5Hz | CPU, memory, disk, uptime |
| Motion | FluidNC status | ~2Hz | Status, position |

### 5.3 Snapshot structure

A `GetSnapshot` call returns a point-in-time view of all (or selected)
subsystems. The `ObservabilityStream` yields snapshots at a configurable
interval (minimum 100ms).

### 5.4 Integration with Concord HTTP API

The Concord HTTP API backend (`concord/apps/backend/http-api/`) already has
infrastructure for querying MTIB nodes. The redesigned server maintains the
same gRPC interface pattern, so the backend can call `GetSnapshot` on each
registered node and surface results via REST for dashboard consumption.

---

## 6. Deployment Model

### 6.1 Container

| Property | Value |
|----------|-------|
| Base image | Ubuntu 22.04 (ARM64) |
| Runtime | Python 3.10+ |
| Dependencies | grpcio, pyserial, gpiod, smbus2, PyYAML |
| J-Link tools | nrf-command-line-tools (nrfjprog) |
| FluidNC assets | ESP32 firmware + config.yaml |
| Privileged | Yes (device access: /dev, /sys) |
| Exposed port | 50052 (gRPC) |
| Image | `containers.ad.corekinect.com/concord-mtib-server:latest` |

### 6.2 Nx build targets

Located in `concord/apps/edge/mtib-server/project.json`:

```json
{
  "containerize": {
    "executor": "@nx-tools/nx-container:build",
    "options": {
      "file": "apps/edge/mtib-server/deploy/Dockerfile",
      "context": "{workspaceRoot}",
      "push": false,
      "load": true
    },
    "configurations": {
      "development": {
        "tags": ["concord-mtib-server:development"],
        "platforms": ["linux/arm64"]
      },
      "production": {
        "tags": ["containers.ad.corekinect.com/concord-mtib-server:latest"],
        "platforms": ["linux/arm64"]
      }
    }
  },
  "push": {
    "executor": "nx:run-commands",
    "dependsOn": ["containerize"],
    "configurations": {
      "production": {
        "command": "docker push containers.ad.corekinect.com/concord-mtib-server:latest"
      }
    }
  }
}
```

### 6.3 K8s deployment

Deployed as a `Deployment` (replicas=1) on the Verdin node:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: mtib-server-dev
  labels:
    corekinect.com/managed-by: concord
    corekinect.com/purpose: validation
spec:
  replicas: 1
  strategy:
    type: Recreate
  selector:
    matchLabels:
      app: mtib-server
  template:
    spec:
      nodeSelector:
        kubernetes.io/hostname: verdin-imx8mm-15702160
      tolerations:
        - key: corekinect.com/role
          value: edge
          effect: NoSchedule
      containers:
        - name: mtib-server
          image: containers.ad.corekinect.com/concord-mtib-server:latest
          imagePullPolicy: Always
          ports:
            - containerPort: 50052
              hostPort: 50052
          env:
            - name: LOG_LEVEL
              value: "4"
            - name: MOTION_ENABLED
              value: "true"
          securityContext:
            privileged: true
          volumeMounts:
            - name: dev
              mountPath: /dev
            - name: hwmon
              mountPath: /sys/class/hwmon
            - name: gpio
              mountPath: /sys/class/gpio
            - name: iio
              mountPath: /sys/bus/iio
      volumes:
        - name: dev
          hostPath: { path: /dev }
        - name: hwmon
          hostPath: { path: /sys/class/hwmon }
        - name: gpio
          hostPath: { path: /sys/class/gpio }
        - name: iio
          hostPath: { path: /sys/bus/iio }
```

### 6.4 Development workflow

```
Developer machine                  K3s Cluster (Verdin)
─────────────────                  ─────────────────────
Edit code in concord/apps/
  edge/mtib-server/
        │
        ▼
nx run mtib-server:containerize
  -c production
        │
        ▼
nx run mtib-server:push
  -c production
        │                          kubectl rollout restart
        └─────────────────────────► deployment/mtib-server-dev
                                          │
                                          ▼
                                   Pull new image
                                   Start container
                                   gRPC ready on :50052
```

---

## 7. System Requirements

### 7.1 Server requirements

| Requirement | Specification |
|-------------|--------------|
| Python | 3.10+ |
| Concurrency model | Async gRPC (grpcio-aio) for parallel observability + request serving |
| UART latency | < 10ms raw byte to gRPC delivery |
| UART broadcast | Multiple simultaneous gRPC clients on same physical port |
| Power measurement | INA219 via hwmon, ~10Hz sample rate, mA resolution |
| ADC resolution | ADS1115 16-bit, 82k/33k voltage divider (ratio 3.48) |
| GPIO | 7 DUT-facing pins (0-6) via gpiod, level-shifted to DUT_VIO |
| Flash | nrfjprog CLI with J-Link, 4MHz clock, per-probe locking |
| Motion | FluidNC G-code over USB-serial, auto-home on startup |
| Hardware detection | Auto-detect REV 1.1 vs 1.2 via I2C probing at startup |
| Startup time | < 10s from container start to gRPC ready |
| No MQTT | Zero external messaging dependencies |

### 7.2 Hardware requirements

| Component | Required |
|-----------|----------|
| Verdin iMX8M Mini (SoM) | Already provisioned |
| Toradex Mallow carrier | Already provisioned |
| CoreKinect MTIB Board REV 1.2 | Already provisioned |
| J-Link Mini programmer(s) | At least 1 (2 for dual-MCU flash) |
| ESP32 FluidNC controller | Already on MTIB board |
| Stepper motor + rail | Already assembled in scaffold |

### 7.3 Network requirements

| Connection | Details |
|-----------|---------|
| Verdin → K3s control plane | Cluster network |
| Developer → Verdin gRPC | Port 50052, hostPort exposed |
| Developer → container registry | `containers.ad.corekinect.com` |
| Test runner pods → Verdin gRPC | Cluster network, port 50052 |

---

## 8. Implementation Guidance

### 8.1 claude-kit integration

The MTIB server implementation should be done using:

```bash
claude-kit --kit cloud-python
```

This loads the `cloud-python-engineer` with gRPC, asyncio, Docker, and
Kubernetes domain knowledge. The engineer agent will:

- Implement handlers following v1's flat pattern (no sessions, no middleware)
- Use `grpcio-aio` for async server with parallel streaming support
- Implement the observability engine with background polling threads
- Handle hardware revision detection and conditional behavior
- Build the Dockerfile and K8s manifests

### 8.2 Handler architecture (guidance, not prescription)

The implementation should follow v1's flat handler pattern:

```
src/
├── main.py                     # Entry point, gRPC server startup
├── hardware/
│   ├── revision.py             # Auto-detect REV 1.1 vs 1.2
│   └── context.py              # Hardware context (revision, capabilities)
├── handlers/
│   ├── uart.py                 # UartStream (broadcast RX, multi-client)
│   ├── flash.py                # FlashProgram, FlashErase, ListProgrammers
│   ├── gpio.py                 # GpioConfig/Write/Read/Watch
│   ├── power.py                # PowerEnable/Disable/Read/Measure/Stream
│   ├── adc.py                  # AdcRead/ReadAll/Stream
│   ├── motion.py               # MotionStart/Home/Stop/Status
│   └── observability.py        # GetSnapshot, ObservabilityStream
├── services/
│   ├── fluidnc.py              # FluidNC G-code interface (from v1)
│   └── mcp4017.py              # Voltage control (from v1, rev-aware)
└── provider.py                 # gRPC service provider (wires handlers)
```

Exact implementation details — thread pools, queue sizes, error recovery
patterns, logging levels — are the responsibility of the coding agent
with `cloud-python` kit loaded. This spec defines **what** the server
does, not **how** it does it.

### 8.3 Testing strategy

- Unit tests with mocked hardware (smbus2, gpiod, serial)
- Integration tests on the Verdin node (deploy, call each RPC, verify)
- UART latency test: measure round-trip time from TX to RX echo
- Power accuracy test: measure known load, compare to expected
- Observability test: start stream, verify snapshots arrive at configured rate

### 8.4 Migration from v1

1. New code replaces `concord/apps/edge/mtib-server/src/`
2. New proto replaces `concord/libs/protocols/mtib/mtib.proto`
3. Service name changes: `MtibV1` → `Mtib`
4. **Port changes: 50053 → 50052** — update all clients, K8s manifests, firewall rules
5. Generated Python bindings regenerated (`mtib_pb2.py`, `mtib_pb2_grpc.py`)
6. Go bindings regenerated (if used by other services)
7. Dockerfile updated for any new dependencies
8. project.json updated with v2-style Nx targets
9. K8s manifests updated (port 50052, image name)
10. v2 server at `concord/apps/edge/mtib-server-v2/` is not modified

---

## Appendix A: Known Limitations

1. **Charging test limitation** — DUT power and charger power come from
   the same MTIB source. No battery sync exists. Charge behavior cannot
   be tested accurately at this stage. This affects 29 PRDTST charging tests.

2. **ADC sample rate** — ADS1115 via IIO sysfs is limited to ~100 SPS max
   per channel. For high-speed signal capture, external instrumentation
   would be needed.

3. **Single DUT** — One Alpha B0 unit for development. Dev work parallelizes
   across repos, testing serializes on the hardware.

4. **Power resolution** — INA219 with 100mΩ shunt gives ~mA resolution.
   Sleep current (µA range) cannot be accurately measured. Would need
   a high-resolution current sense amplifier for sub-mA measurements.

## Appendix B: Document Cross-References

| Document | Relationship |
|----------|-------------|
| `plans/stage3-and-4-proof-execution-plan.md` | References this spec for MTIB server BOM component |
| `architecture/stage3-integration-tests.md` | Defines concord_harness protocol that rides on MTIB UART |
| `architecture/stage4-product-tests.md` | Defines physical stimulus requirements fulfilled by MTIB |
| `libs/protocols/mtib_v2/DESIGN.md` | Hardware reference for REV 1.1/1.2 carrier board |
| `libs/protocols/mtib/mtib.proto` | Proto file replaced by this redesign |
