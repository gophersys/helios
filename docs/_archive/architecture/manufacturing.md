# Manufacturing Architecture

> **Status:** Work-in-progress. Captures current manufacturing test infrastructure and intended direction.

## Overview

Manufacturing testing runs newly assembled PCB panels through automated test fixtures. Each product (Sigma5, Theta, Alpha) has dedicated fixtures, and each fixture has multiple MTIB nodes -- one per panel slot plus one or two stand-alone nodes for depaneled boards.

The goal is to validate every unit coming off the production line: electrical characteristics, firmware flashing, and power-on self-test (POST).

## Physical Layout

```
Manufacturing Floor
|
+-- Theta Fixture
|   +-- Slot 1: MTIB (verdin-imx8mm-15005658, .35) -- Panel position 1
|   +-- Slot 2: MTIB (verdin-imx8mm-15005689, .36) -- Panel position 2
|   +-- Slot 3: MTIB (verdin-imx8mm-15005816, .33) -- Panel position 3
|   +-- Slot 4: MTIB (verdin-imx8mm-15005817, .34) -- Panel position 4
|   +-- Stand Alone: MTIB (verdin-imx8mm-15005679, .32) -- Depaneled boards
|
+-- Sigma5 Fixture
|   +-- (Similar layout, nodes on concordagent02)
|
+-- Alpha Fixture
    +-- (Similar layout, charge fixture)
```

### Terminology

- **Panel** -- A mounted PCB (or array of PCBs) in a test fixture slot
- **Slot** -- A physical position in the fixture that holds one panel. Each slot has a dedicated MTIB node
- **Fixture** -- The complete test apparatus for a product. Contains N slots + stand-alone positions
- **Depaneled** -- Individual boards removed from a panel array, tested on stand-alone MTIB nodes
- **DUT** -- Device Under Test. The board being tested
- **SNR** -- Serial Number. Unique identifier assigned to each DUT

## MTIB Hardware

Each MTIB node is a single-board computer with a custom test interface board:

**Hardware Stack:**
- Toradex Verdin iMX8M Mini (Quad A53, 2GB RAM, Torizon OS)
- Toradex Mallow carrier board
- CoreKinect MTIB carrier board (REV 1.1 or REV 1.2)

**Test Capabilities per Node:**

| Subsystem | Hardware | Function |
|-----------|----------|----------|
| **Power** | TPS63802 + MCP4017 + INA219 x2 | Regulated DUT power (0.8-5.5V), current monitoring (0-3.2A) |
| **Debug** | J-Link Mini x2, SN74CBT3257C mux (REV 1.2) | SWD firmware flashing via nrfjprog |
| **ADC** | ADS1115 x2 (8 channels) | Voltage measurement 0-14V |
| **GPIO** | 7 DUT pins + TCA9534A expander (REV 1.2) | Digital I/O, level-shifted 1.8V <-> DUT_VIO |
| **Serial** | USB2514B hub, CP2102N | UART to DUT and to ESP32 motion controller |
| **Sensors** | BME280, BMP390L, LIS2DE12 | Pressure, humidity, temperature, acceleration |
| **Motion** | ESP32 + FluidNC + A4988 x2 | X/Y stepper positioning with limit switches (G-code) |

**I2C Device Map:**
```
0x19: LIS2DE12 (accelerometer)       0x40: INA219 (DUT current)
0x2F: MCP4017 (voltage control)      0x41: INA219 (charge current)
0x48: ADS1115 (ADC ch 0-3)           0x76: BMP390L (pressure)
0x49: ADS1115 (ADC ch 4-7)           0x77: BME280 (environment)

REV 1.2 only:
0x38: TCA9534A (GPIO expander)       0x50: AT24C02C (EEPROM)
```

## Software Architecture

### MTIB Server

Each MTIB node runs a containerized gRPC server that abstracts the hardware:

- **Location:** `apps/edge/mtib-server-v2/`
- **Protocol:** `libs/protocols/mtib/` (V1 on port 50053, V2 on port 50054)
- **Runtime:** Python, privileged container with `/dev`, `/sys` mounts
- **Auto-detection:** Detects hardware revision (REV 1.1 vs 1.2) and adjusts voltage calculations

**V1 gRPC API:** GPIO, ADC, power control, sensors, motion, firmware programming, UART streaming

**V2 gRPC API (extended):** Debug probes (halt/resume/breakpoints), power profiling with timestamps, logic analyzer, bus interfaces (I2C/SPI/CAN), BLE/Thread capture, Zephyr shell integration

### Test Runners

Each product has dedicated test runner containers, one per test type:

| Port | Test Type | Description |
|------|-----------|-------------|
| 50060 | Electrical | Power supply, voltage regulation, current draw, UVLO |
| 50061 | Firmware Flash | nRF9151 modem + app firmware, nRF52840 app firmware |
| 50062 | POST | Power-on self-test, external flash, IMEI/ICCID, personalization |

Test runners implement the `ClusterTestService` gRPC interface and register dynamically with the Cluster Operator.

### Cluster Operator

One operator per product cluster. Manages:
- Test runner registration and discovery
- Deployment lifecycle on the cluster
- Test execution orchestration (dispatches to runners, streams results)
- Health monitoring

### Test Execution Flow

```
1. Operator places DUT in fixture slot
2. UI: Select test, configure parameters, click Execute
3. HTTP API -> gRPC ExecuteTest() to Cluster Operator
4. Operator dispatches to registered Test Runner
5. Test Runner communicates with MTIB Server via gRPC
6. MTIB Server controls hardware (power, flash, measure, etc.)
7. Results stream back: MTIB -> Runner -> Operator -> API -> WebSocket -> UI
8. Results persisted to database
```

### Theta Fixture Configuration

Example from `deploy/manufacturing/theta_fixture/`:

```
Slot Configuration (4-panel fixture):
  slot-1: SNR 000A
  slot-2: SNR 000B
  slot-3: SNR 000C
  slot-4: SNR 000D

Electrical Tests:
  UVLO @ 3.4V, Nominal @ 3.7V, High @ 4.5V, Charge @ 5.0V, Load sharing

Firmware Flash:
  nRF9151 modem, nRF9151 application, nRF52840 application

POST:
  External flash pattern, IMEI/ICCID validation, device personalization
```

### Kubernetes Deployment

**MTIB Servers** (`deploy/edge/mtib-server/manufacturing.yaml`):
- 5 replicas, each pinned to a specific Verdin host via node selector
- Privileged containers with hardware device mounts
- Resource limits: 1-2 CPU cores, 1-2 GB RAM per node

**Test Runners** (`deploy/manufacturing/{product}/deployment.yaml`):
- 1 replica per product, pinned to a specific agent node
- Exposes 3 ports (one per test type)
- Connects to MTIB servers and operator via gRPC

**Operator** (`deploy/manufacturing/{product}/operator-deployment.yaml`):
- 1 replica per product, host networking
- Has kubeconfig and Docker socket access for managing deployments

## Manufacturing Test Step Flow (per DUT)

```
1. Panel loaded into fixture slot
2. Electrical Test
   a. Apply UVLO voltage (3.4V), measure current
   b. Apply nominal voltage (3.7V), measure current + voltages
   c. Apply high voltage (4.5V), verify regulation
   d. Apply charge voltage (5.0V), verify charge circuit
   e. Verify load sharing
3. Firmware Flash
   a. Flash nRF9151 modem firmware via J-Link
   b. Flash nRF9151 application firmware via J-Link
   c. Flash nRF52840 application firmware via J-Link
4. POST (Power-On Self-Test)
   a. Verify external flash pattern
   b. Read and validate IMEI
   c. Read and validate ICCID
   d. Personalize device (assign keys, serial number)
5. Panel removed from fixture
```

## Data Model

Manufacturing concepts map to Prisma models as follows:

```
Product ("Theta")
  └─ Fixture ("Theta MFG Fixture 1", type=MANUFACTURING)
       └─ FixtureSlot (slotIndex=0, label="Slot 1") ─── Node (verdin-imx8mm-15005658)
       └─ FixtureSlot (slotIndex=1, label="Slot 2") ─── Node (verdin-imx8mm-15005689)
       └─ FixtureSlot (slotIndex=2, label="Slot 3") ─── Node (verdin-imx8mm-15005816)
       └─ FixtureSlot (slotIndex=3, label="Slot 4") ─── Node (verdin-imx8mm-15005817)
       └─ FixtureSlot (slotIndex=4, label="Stand Alone") ─── Node (verdin-imx8mm-15005679)

Session ("Theta MFG Run - Jan 15", target=100, fixture=above)
  └─ Device (serialNumber="THT-00142", status=PASSED)
       └─ TestExecution (test=Electrical, node=slot-2, status=PASSED)
       └─ TestExecution (test=FW Flash, node=slot-2, status=PASSED)
       └─ TestExecution (test=POST, node=slot-2, status=PASSED)
  └─ Device (serialNumber="THT-00143", status=IN_PROGRESS)
       └─ TestExecution (test=Electrical, node=slot-3, status=PASSED)
       └─ TestExecution (test=FW Flash, node=slot-3, status=RUNNING)
```

### Session Workflow

1. **Admin** creates Product and Fixture (one-time setup via Settings UI)
2. **Operator** starts a Session: selects product, fixture, target count, firmware config
3. As boards are loaded into slots:
   - Device record created with serial number
   - Test executions dispatched automatically (electrical → firmware → POST)
   - Results stream in real-time to the UI
   - Device status updated: PENDING → IN_PROGRESS → PASSED/FAILED
   - Session counters updated (completed/passed/failed)
4. **Operator** pauses session (lunch break) or completes it when target reached
5. Session report available: pass rate, failure breakdown, per-device history

### Session Lifecycle

```
ACTIVE ──pause──► PAUSED ──resume──► ACTIVE
ACTIVE ──complete──► COMPLETED
ACTIVE ──cancel──► CANCELLED
PAUSED ──cancel──► CANCELLED
```

## Current State and Gaps

**Working:**
- MTIB hardware + server (V1 protocol)
- Basic test execution flow (Operator -> Runner -> MTIB)
- Theta and Sigma5 manufacturing deployments
- gRPC streaming of results
- Product, Fixture, Session, Device data model in Prisma

**In Progress / Needs Work:**
- [ ] MTIB V2 protocol integration
- [ ] Manufacturing dashboard in the frontend
- [ ] Session workflow UI (start/pause/complete, device scanning)
- [ ] Test result history and analytics
- [ ] Automated panel tracking (which DUT in which slot)
- [ ] Pass/fail aggregation and reporting
- [ ] Firmware version management per product
- [ ] Multi-fixture orchestration (run all slots in parallel, aggregate results)
- [ ] Audit trail for all session operations
