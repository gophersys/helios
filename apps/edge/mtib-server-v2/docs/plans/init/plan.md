# MTIB Server V2 - Implementation Plan

## Executive Summary

Upgrade MTIB server from V1 to V2, adding comprehensive debugging, high-speed power profiling, protocol analysis, bus master interfaces, BLE testing, and full Zephyr RTOS integration.

**Timeline:** 12 phases
**Protocol:** `libs/protocols/mtib_v2/mtib_v2.proto` (port 50054)
**Design Doc:** `libs/protocols/mtib_v2/DESIGN.md`
**Hardware:** REV 1.1 and REV 1.2 support with auto-detection

---

## Phase Overview

| Phase | Name | Status | Priority | Dependencies |
|-------|------|--------|----------|--------------|
| [1](phase1.md) | Foundation & Hardware | ✅ DONE | P0 | None |
| [2](phase2.md) | Protocol Migration | ⬜ TODO | P0 | Phase 1 |
| [3](phase3.md) | Power & ADC Enhancement | ⬜ TODO | P1 | Phase 2 |
| [4](phase4.md) | Debug Probe | ⬜ TODO | P1 | Phase 2 |
| [5](phase5.md) | RTT & SWO | ⬜ TODO | P2 | Phase 4 |
| [6](phase6.md) | Motion & GPIO | ⬜ TODO | P1 | Phase 2 |
| [7](phase7.md) | Bus Masters | ⬜ TODO | P2 | Phase 2 |
| [8](phase8.md) | Logic Analyzer | ⬜ TODO | P3 | Phase 2 |
| [9](phase9.md) | BLE Support | ⬜ TODO | P3 | Phase 2 |
| [10](phase10.md) | Zephyr Integration | ⬜ TODO | P2 | Phase 4, 5 |
| [11](phase11.md) | File & System | ⬜ TODO | P1 | Phase 2 |
| [12](phase12.md) | Testing & Deployment | ⬜ TODO | P0 | All |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          mtib-server-v2 (gRPC :50054)                        │
├─────────────────────────────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                      HardwareContext (Phase 1 ✅)                    │    │
│  │  - Revision detection (I2C probing)                                 │    │
│  │  - Revision-aware voltage calculations                              │    │
│  │  - TCA9534A GPIO expander (REV 1.2)                                │    │
│  │  - Feature availability queries                                     │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                    │                                         │
│  ┌─────────────────────────────────┼───────────────────────────────────┐    │
│  │                          gRPC Handlers                              │    │
│  ├──────────┬──────────┬──────────┼──────────┬──────────┬─────────────┤    │
│  │  Debug   │  Power   │   ADC    │   GPIO   │   UART   │   Motion    │    │
│  │ Phase 4  │ Phase 3  │ Phase 3  │ Phase 6  │ Phase 2  │  Phase 6    │    │
│  ├──────────┼──────────┼──────────┼──────────┼──────────┼─────────────┤    │
│  │   RTT    │   SWO    │   I2C    │   SPI    │   CAN    │   Logic     │    │
│  │ Phase 5  │ Phase 5  │ Phase 7  │ Phase 7  │ Phase 7  │  Phase 8    │    │
│  ├──────────┼──────────┼──────────┼──────────┼──────────┼─────────────┤    │
│  │   BLE    │  Zephyr  │  Files   │  System  │ Sensors  │  Firmware   │    │
│  │ Phase 9  │ Phase 10 │ Phase 11 │ Phase 11 │ Phase 2  │  Phase 4    │    │
│  └──────────┴──────────┴──────────┴──────────┴──────────┴─────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## RPC Method Inventory

### From V1 (existing, to migrate)
- `HealthCheck` - Health status
- `GpioConfig`, `GpioWrite`, `GpioRead` - GPIO control
- `AdcRead`, `AdcReadAll` - ADC channels
- `DutPowerEnable`, `DutPowerDisable`, `DutPowerRead` - DUT power
- `DutChargePowerEnable`, `DutChargePowerDisable`, `DutChargePowerRead` - Charge power
- `AltimeterRead`, `AccelRead` - Sensors
- `GetMotionStatus`, `MotionStart`, `MotionHome`, `MotionStop` - Motion
- `ListProgrammers`, `ListFwFiles`, `UploadFwFile`, `DeleteFwFile` - Firmware files
- `FlashFwFile`, `EraseFlash`, `EnableAppProtect` - Flash programming
- `UartStream` - UART I/O

### New in V2 (to implement)
**Debug (12 methods):** `DebugConnect`, `DebugDisconnect`, `DebugStatus`, `DebugHalt`, `DebugResume`, `DebugStep`, `DebugReset`, `ReadMemory`, `WriteMemory`, `ReadRegisters`, `WriteRegister`, `SetBreakpoint`, `ClearBreakpoint`, `SetWatchpoint`, `Backtrace`

**Flash (4 methods):** `FlashInfo`, `FlashErase`, `FlashWrite`, `FlashProgram`

**RTT (3 methods):** `RttStart`, `RttStop`, `RttStream`

**SWO (3 methods):** `SwoStart`, `SwoStop`, `SwoStream`

**Power (2 new):** `PowerStream`, `PowerMeasure`

**Logic (5 methods):** `LogicCaptureStart`, `LogicCaptureStatus`, `LogicCaptureStop`, `AddDecoder`, `GetDecodedData`

**Bus Masters (8 methods):** `I2cConfig`, `I2cTransfer`, `I2cScan`, `SpiConfig`, `SpiTransfer`, `CanConfig`, `CanSend`, `CanSetFilter`, `CanReceive`

**BLE (7 methods):** `BleScan`, `BleConnect`, `BleDisconnect`, `BleDiscoverServices`, `BleRead`, `BleWrite`, `BleNotifications`

**Zephyr (5 methods):** `ZephyrShell`, `ZephyrLogStream`, `ZephyrDevicetree`, `ZephyrThreads`, `TwisterRun`

**Files (4 methods):** `ListFiles`, `UploadFile`, `DownloadFile`, `DeleteFile`

**System (2 methods):** `HealthCheck`, `SystemInfo`

---

## Hardware Reference

### I2C Device Map
| Address | Device | Revision | Handler |
|---------|--------|----------|---------|
| 0x19 | LIS2DE12 | Both | SensorsHandler |
| 0x2F | MCP4017 | Both | PowerHandler |
| 0x38 | TCA9534A | REV 1.2 | HardwareContext |
| 0x40 | INA219 (DUT) | Both | PowerHandler |
| 0x41 | INA219 (CHG) | Both | PowerHandler |
| 0x48 | ADS1115 #1 | Both | ADCHandler |
| 0x49 | ADS1115 #2 | Both | ADCHandler |
| 0x50 | AT24C02C | REV 1.2 | EEPROMHandler |
| 0x76 | BMP390L | Both | SensorsHandler |
| 0x77 | BME280 | Both | SensorsHandler |

### USB Topology
```
Verdin USB Host
└── USB2514B Hub
    ├── Port 1: J-Link Mini #1
    ├── Port 2: J-Link Mini #2
    ├── Port 3: CP2102N → ESP32 FluidNC
    └── Port 4: Auxiliary USB-A
```

### TCA9534A Pin Mapping (REV 1.2)
| Pin | Signal | Function |
|-----|--------|----------|
| P0 | JLINK_MUL | J-Link multiplexer |
| P1 | EEPROM_WP | EEPROM write protect |
| P2 | VMM_EN | Motor power enable |
| P3-P7 | Reserved | Future use |

---

## Implementation Guidelines

### For Each Phase

1. **Read the phase document** - Contains objectives, tasks, tests
2. **Create a feature branch** - `feature/mtib-v2-phase-N`
3. **Implement SERVER handlers** in `src/providers/handlers/`
4. **Implement CLIENT methods** in `libs/python/corekinect/mtib_client/v2/`
5. **Write integration tests** that connect to localhost
6. **Test against running server** - All tests must pass
7. **Update phase status** - Mark tasks complete as you go

### Client-Server Parallel Development

**CRITICAL:** Every RPC must have both sides implemented:

| Component | Location | What to Create |
|-----------|----------|----------------|
| Server | `apps/edge/mtib-server-v2/src/providers/handlers/` | Handler methods |
| Client | `libs/python/corekinect/mtib_client/v2/client/core.py` | Client methods |
| Tests | `apps/edge/mtib-server-v2/test/integration/` | Integration tests |

### Client Structure (to create)

```
libs/python/corekinect/mtib_client/v2/
├── __init__.py              # Exports: MtibV2Client, NetConfig
├── setup.py                 # Package setup
└── client/
    ├── __init__.py
    ├── core.py              # MtibV2Client class
    ├── config.py            # NetConfig, etc.
    └── types.py             # Type definitions
```

Reference the V1 client at `libs/python/corekinect/mtib_client/v1/` for patterns.

### Code Quality Standards

- Type hints on all functions
- Docstrings with Args/Returns/Raises
- Error handling with specific exceptions
- Logging at appropriate levels
- Hardware revision checks where needed
- Unit tests for new code

### Testing Strategy

- **Unit tests:** Pure Python logic, mock hardware
- **Integration tests:** Real hardware on test bench (localhost)
- **Protocol tests:** gRPC client tests
- **Regression tests:** V1 compatibility

### Integration Test Pattern

All integration tests follow this pattern:

```python
# test/integration/test_power.py
import pytest
from corekinect.mtib_client.v2 import MtibV2Client, NetConfig

@pytest.fixture
def client():
    """Create connected client for tests."""
    c = MtibV2Client(config=MtibV2Client.Config(
        net=NetConfig(addr="127.0.0.1", port=50052)
    ))
    error = c.connect()
    assert error is None, f"Connection failed: {error}"
    yield c
    c.disconnect()

def test_power_enable(client):
    """PowerEnable should turn on DUT power."""
    response = client.PowerEnable(voltage_v=3.3)
    assert response.success

def test_power_status(client):
    """PowerStatus should return current readings."""
    response = client.PowerStatus()
    assert response.success
    assert response.voltage_v > 0
```

### Running Tests

```bash
# Start server in background
python -m src.main &

# Run integration tests
pytest test/integration/ -v

# Stop server
pkill -f "python -m src.main"
```

---

## Quick Start

```bash
# Current branch
git checkout feature/mtib-server-v2

# View phase 2 (next to implement)
cat docs/plans/init/phase2.md

# Run existing tests
cd apps/edge/mtib-server-v2
pytest test/
```

---

## File Structure

```
docs/plans/init/
├── plan.md          # This file - overview
├── phase1.md        # Foundation & Hardware ✅
├── phase2.md        # Protocol Migration
├── phase3.md        # Power & ADC
├── phase4.md        # Debug Probe
├── phase5.md        # RTT & SWO
├── phase6.md        # Motion & GPIO
├── phase7.md        # Bus Masters
├── phase8.md        # Logic Analyzer
├── phase9.md        # BLE Support
├── phase10.md       # Zephyr Integration
├── phase11.md       # File & System
└── phase12.md       # Testing & Deployment
```
