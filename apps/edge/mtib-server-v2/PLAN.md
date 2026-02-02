# MTIB Server V2 - Implementation Plan

> **Detailed Phase Documentation:** See [`docs/plans/init/`](docs/plans/init/plan.md) for comprehensive implementation plans with code examples, tests, and completion checklists.

## Overview

Upgrade the existing MTIB server to V2, implementing the new protocol (`mtib_v2.proto`) with full support for both hardware revisions (REV 1.1 and REV 1.2). The server should auto-detect the hardware revision at startup and adapt its behavior accordingly.

**Key Goals:**
1. Migrate from `protocols.mtib` to `protocols.mtib_v2`
2. Add auto-detection of hardware revision via I2C probing
3. Add REV 1.2-only features (J-Link mux, motor power control, EEPROM)
4. Update MCP4017 voltage calculations for different pot values per revision
5. Maintain full backward compatibility with REV 1.1 hardware

**Design Document:** `libs/protocols/mtib_v2/DESIGN.md`

---

## Quick Navigation

| Phase | Name | Detailed Doc |
|-------|------|--------------|
| 1 | Foundation & Hardware | [phase1.md](docs/plans/init/phase1.md) ✅ |
| 2 | Protocol Migration | [phase2.md](docs/plans/init/phase2.md) |
| 3 | Power & ADC Enhancement | [phase3.md](docs/plans/init/phase3.md) |
| 4 | Debug Probe (J-Link) | [phase4.md](docs/plans/init/phase4.md) |
| 5 | RTT & SWO | [phase5.md](docs/plans/init/phase5.md) |
| 6 | Motion & GPIO | [phase6.md](docs/plans/init/phase6.md) |
| 7 | Bus Masters (I2C/SPI/CAN) | [phase7.md](docs/plans/init/phase7.md) |
| 8 | Logic Analyzer | [phase8.md](docs/plans/init/phase8.md) |
| 9 | BLE Support | [phase9.md](docs/plans/init/phase9.md) |
| 10 | Zephyr Integration | [phase10.md](docs/plans/init/phase10.md) |
| 11 | File & System | [phase11.md](docs/plans/init/phase11.md) |
| 12 | Testing & Deployment | [phase12.md](docs/plans/init/phase12.md) |

---

## Progress Summary

| Phase | Status | Description |
|-------|--------|-------------|
| Phase 1 | ✅ DONE | Foundation & Hardware Abstraction |
| Phase 2 | 🔶 PARTIAL | Power Handler Updates |
| Phase 3 | ✅ DONE | GPIO Handler / TCA9534A |
| Phase 4 | 🔶 PARTIAL | J-Link Multiplexer |
| Phase 5 | 🔶 PARTIAL | Motion Handler Updates |
| Phase 6 | ⬜ TODO | EEPROM Support |
| Phase 7 | ⬜ TODO | ADC Handler Updates |
| Phase 8 | ⬜ TODO | Sensor Handler Updates |
| Phase 9 | ⬜ TODO | Integration & Testing |
| Phase 10 | 🔶 PARTIAL | Documentation & Cleanup |

---

## Phase 1: Foundation & Hardware Abstraction ✅ DONE

### Step 1.1: Update Project Structure ✅
- [x] Create `.env.example` with V2 configuration options
- [x] Update README.md for V2
- [ ] Update `setup.py` to change package name to `mtib_server_v2`
- [ ] Update `project.json` with new project metadata

**Files:**
- `.env.example` ✅
- `README.md` ✅
- `setup.py`
- `project.json`

### Step 1.2: Protocol Import Migration ⬜ TODO
- [ ] Change all imports from `protocols.mtib` to `protocols.mtib_v2`
- [ ] Update `main.py` to use `MtibV2Servicer` and `add_MtibV2Servicer_to_server`
- [ ] Update `src/shared/types.py` to import from new proto

**Files:**
- `src/main.py`
- `src/providers/mtib.py`
- `src/shared/types.py`

**Note:** Currently still using `protocols.mtib` - need mtib_v2.proto to be generated first.

### Step 1.3: Hardware Revision Detection ✅ DONE
- [x] Create hardware abstraction package at `src/hardware/`
- [x] Implement `HardwareRevision` enum with specs attached
- [x] Implement `HardwareSpecs` dataclass with revision-specific parameters
- [x] Implement `HardwareContext` for unified hardware access
- [x] Probe I2C for EEPROM (0x50) and TCA9534A (0x38) to detect REV 1.2
- [x] Fall back to REV 1.1 if neither detected
- [x] Add env var override (`MTIB_HARDWARE_REVISION`)
- [x] Add env var to disable auto-detect (`MTIB_AUTO_DETECT_REVISION`)

**New Files Created:**
```
src/hardware/
├── __init__.py          # Public API exports
├── revision.py          # HardwareRevision enum, HardwareSpecs, I2C detection
├── context.py           # HardwareContext manager
└── tca9534a.py          # TCA9534A GPIO expander driver
```

### Step 1.4: Update Provider Config ✅ DONE
- [x] Rename provider to `MtibV2Provider`
- [x] Replace `HARDWARE_VERSION: str` with `HARDWARE: HardwareContext`
- [x] Store hardware context in provider instance
- [x] Pass hardware context to handlers during initialization
- [x] Log detected revision and available features at startup
- [ ] Add `GetHardwareInfo` RPC that returns detected revision

**Files:**
- `src/main.py` ✅
- `src/providers/mtib.py` ✅

---

## Phase 2: Power Handler Updates 🔶 PARTIAL

### Step 2.1: Revision-Aware MCP4017 Calculations ✅ DONE
- [x] Add `calculate_wiper_position()` method to `HardwareSpecs`
- [x] Separate resistance values per revision:
  - REV 1.1: 100kΩ pot, 30kΩ fixed
  - REV 1.2: 10kΩ pot, 3kΩ fixed
- [x] Update voltage calculation formula

**Implementation:** `src/hardware/revision.py` - `HardwareSpecs.calculate_wiper_position()`

### Step 2.2: Update Power Handler ✅ DONE
- [x] Accept `HardwareContext` in constructor
- [x] Update `_set_dut_power_voltage` to use revision-aware voltage calculation
- [x] Use calculated initial wiper position for faster convergence
- [ ] Add current/voltage/power reading via hwmon sysfs (existing, verify)

**File:** `src/providers/handlers/power.py` ✅

### Step 2.3: Add Power Streaming ⬜ TODO
- [ ] Implement bidirectional streaming RPC for power samples
- [ ] Read INA219 via hwmon at configurable rate (default 10Hz)
- [ ] Return current (mA), voltage (mV), power (µW) per sample

---

## Phase 3: GPIO Handler Updates ✅ DONE

### Step 3.1: Add TCA9534A Support (REV 1.2) ✅ DONE
- [x] Create `src/hardware/tca9534a.py` for GPIO expander control
- [x] Define `TCA9534APin` enum with MTIB-specific pin mappings
- [x] Initialize all pins as outputs, default low
- [x] Add read/write methods for individual pins
- [x] Add convenience methods: `set_jlink_mux()`, `set_motor_power()`, `set_eeprom_write_protect()`

**File:** `src/hardware/tca9534a.py` ✅

### Step 3.2: Update GPIO Handler ⬜ TODO
- [ ] Pass hardware context to GPIOHandler constructor
- [ ] Initialize TCA9534A only on REV 1.2 (handled by HardwareContext)
- [x] Keep existing iMX8 GPIO handling for DUT GPIOs
- [ ] Add RPC methods for PCB control GPIOs (J-Link mux, motor power, etc.)

**File:** `src/providers/handlers/gpio.py`

---

## Phase 4: J-Link Multiplexer (REV 1.2 Only) 🔶 PARTIAL

### Step 4.1: Add J-Link Mux Control ✅ DONE (in HardwareContext)
- [x] Implement `set_jlink_mux()` in `HardwareContext`
- [x] Control via TCA9534A P0 (JLINK_MUL signal)
- [x] Raise `HardwareFeatureNotAvailable` on REV 1.1

**Implementation:** `src/hardware/context.py` - `HardwareContext.set_jlink_mux()`

### Step 4.2: Add J-Link Mux RPC ⬜ TODO
- [ ] Add `SetJlinkMux` RPC handler in gpio or new jlink handler
- [ ] Wire up to `HardwareContext.set_jlink_mux()`

### Step 4.3: Update Firmware Handler ⬜ TODO
- [ ] Add option to select J-Link before flashing (REV 1.2)
- [ ] Ensure mux is set correctly before nrfjprog commands

**File:** `src/providers/handlers/firmware.py`

---

## Phase 5: Motion Handler Updates 🔶 PARTIAL

### Step 5.1: Motor Power Control (REV 1.2) ✅ DONE
- [x] Accept `HardwareContext` in constructor
- [x] Add `_enable_motor_power()` helper method
- [x] Control via `HardwareContext.set_motor_power()` on REV 1.2
- [x] No-op on REV 1.1 (power always on with external supply)

**File:** `src/providers/handlers/motion.py` ✅

### Step 5.2: Add Motor Power RPC ⬜ TODO
- [ ] Add `EnableMotorPower` RPC
- [ ] Wire up to MotionHandler

### Step 5.3: Update Motion Start/Stop ⬜ TODO
- [ ] Auto-enable motor power before motion operations (REV 1.2)
- [ ] Option to leave motors powered after operation completes

---

## Phase 6: EEPROM Support (REV 1.2 Only) ⬜ TODO

### Step 6.1: Add EEPROM Driver
- [ ] Create `src/hardware/eeprom.py` for AT24C02C access
- [ ] Read/write with page-aware writes (8-byte pages)
- [ ] Integrate with `HardwareContext`

**New File:** `src/hardware/eeprom.py`
```python
class AT24C02C:
    ADDRESS = 0x50
    SIZE = 256  # 2Kbit = 256 bytes
    PAGE_SIZE = 8

    def read(self, offset: int, length: int) -> bytes:
        """Read bytes from EEPROM."""
        ...

    def write(self, offset: int, data: bytes) -> None:
        """Write bytes to EEPROM (check write protect!)."""
        ...
```

### Step 6.2: Add EEPROM RPC
- [ ] Add `ReadEeprom` and `WriteEeprom` to proto (if not present)
- [ ] Handle write protect via TCA9534A P1
- [ ] Return error on REV 1.1

### Step 6.3: Board Identification
- [ ] Define EEPROM layout for board ID, serial number, calibration
- [ ] Read board info at startup
- [ ] Include in `GetHardwareInfo` response

---

## Phase 7: ADC Handler Updates ⬜ TODO

### Step 7.1: Update ADC Voltage Calculation
- [ ] Account for REV 1.2 pull-down resistors in floating state detection
- [ ] Document ADC channel mapping (same on both revisions)
- [ ] Add calibration data from EEPROM (REV 1.2)

**File:** `src/providers/handlers/adc.py`

---

## Phase 8: Sensor Handler Updates ⬜ TODO

### Step 8.1: Keep Existing Sensor Support
- [ ] BME280 (0x77), BMP390L (0x76), LIS2DE12 (0x19) - same on both revisions
- [ ] No changes needed unless proto has new sensor RPCs

**File:** `src/providers/handlers/sensors.py`

---

## Phase 9: Integration & Testing ⬜ TODO

### Step 9.1: Update Provider Wire-Up
- [x] Wire all updated handlers in `MtibV2Provider.__init__`
- [x] Pass hardware context to each handler
- [ ] Add health check that reports revision

**File:** `src/providers/mtib.py`

### Step 9.2: Create Mock Mode
- [ ] Add `--mock` flag for testing without hardware
- [ ] Mock I2C responses for both revisions
- [ ] Allow revision override in mock mode

### Step 9.3: Add Integration Tests
- [ ] Test revision detection logic
- [ ] Test MCP4017 voltage calculations for both revisions
- [ ] Test TCA9534A GPIO operations (REV 1.2)
- [ ] Test J-Link mux control (REV 1.2)
- [ ] Test motor power control (REV 1.2)

**Files:**
- `test/test_hardware_revision.py`
- `test/test_hardware_context.py`
- `test/test_power.py`
- `test/test_gpio.py`
- `test/test_motion.py`

---

## Phase 10: Documentation & Cleanup 🔶 PARTIAL

### Step 10.1: Update Documentation ✅ DONE
- [x] Update README.md with V2 features
- [x] Document revision-specific features
- [x] Document environment variables
- [ ] Add hardware setup guide

### Step 10.2: Remove Old Code ⬜ TODO
- [ ] Remove old `HARDWARE_REV_1_1_*` and `HARDWARE_REV_1_2_*` constants from mtib.py
- [ ] Clean up unused imports
- [ ] Update .gitignore

### Step 10.3: Deployment ⬜ TODO
- [ ] Update deploy scripts for V2
- [ ] Test on actual REV 1.1 hardware
- [ ] Test on actual REV 1.2 hardware

---

## File Summary

### New Files Created ✅
| File | Purpose | Status |
|------|---------|--------|
| `src/hardware/__init__.py` | Package exports | ✅ Done |
| `src/hardware/revision.py` | HardwareRevision enum, HardwareSpecs, detection | ✅ Done |
| `src/hardware/context.py` | HardwareContext unified access | ✅ Done |
| `src/hardware/tca9534a.py` | TCA9534A GPIO expander driver | ✅ Done |
| `src/hardware/eeprom.py` | AT24C02C EEPROM driver | ⬜ TODO |

### Files Modified ✅
| File | Changes | Status |
|------|---------|--------|
| `src/main.py` | HardwareContext init, revision logging | ✅ Done |
| `src/providers/mtib.py` | MtibV2Provider, HardwareContext | ✅ Done |
| `src/providers/handlers/power.py` | HardwareContext for voltage calc | ✅ Done |
| `src/providers/handlers/motion.py` | HardwareContext for motor power | ✅ Done |
| `.env.example` | New env vars documented | ✅ Done |
| `README.md` | V2 documentation | ✅ Done |

### Files Still TODO
| File | Changes |
|------|---------|
| `src/shared/types.py` | V2 proto type imports |
| `src/providers/handlers/gpio.py` | HardwareContext, PCB GPIO RPCs |
| `src/providers/handlers/firmware.py` | J-Link selection |
| `src/providers/handlers/adc.py` | Pull-down compensation |
| `setup.py` | Package rename |
| `project.json` | Project metadata |

---

## Implementation Order

**Recommended order for remaining work:**

1. ~~**Phase 1** - Foundation (proto migration, revision detection)~~ ✅
2. ~~**Phase 3** - GPIO (TCA9534A support)~~ ✅
3. ~~**Phase 2.1-2.2** - Power (revision-aware voltage)~~ ✅
4. ~~**Phase 5.1** - Motion (motor power control)~~ ✅
5. **Phase 1.2** - Protocol migration (when mtib_v2.proto ready)
6. **Phase 4.2-4.3** - J-Link mux RPC and firmware handler
7. **Phase 5.2-5.3** - Motor power RPC and auto-enable
8. **Phase 2.3** - Power streaming
9. **Phase 6** - EEPROM support
10. **Phase 7** - ADC updates
11. **Phase 8** - Sensor updates
12. **Phase 9** - Testing
13. **Phase 10** - Final cleanup

---

## Quick Reference

### Environment Variables
```bash
MTIB_HARDWARE_REVISION=1.2      # Override auto-detection
MTIB_AUTO_DETECT_REVISION=false # Disable auto-detection
LOG_LEVEL=20
LOG_PATH=./logs
SERVER_PORT=50052
ASSETS_PATH=./assets
METRICS_ENABLED=true
METRICS_BROKER_URL=mqtt://localhost:1883
MOTION_ENABLED=true
```

### Key I2C Addresses
| Address | Device | Revision |
|---------|--------|----------|
| 0x19 | LIS2DE12 | Both |
| 0x2F | MCP4017 | Both (different resistance values) |
| 0x38 | TCA9534A | REV 1.2 only |
| 0x40 | INA219 (DUT) | Both |
| 0x41 | INA219 (charge) | Both |
| 0x48 | ADS1115 #1 | Both |
| 0x49 | ADS1115 #2 | Both |
| 0x50 | AT24C02C | REV 1.2 only |
| 0x76 | BMP390L | Both |
| 0x77 | BME280 | Both |

### TCA9534A Pin Mapping (REV 1.2)
| Pin | Signal | Function | Default |
|-----|--------|----------|---------|
| P0 | JLINK_MUL | J-Link multiplexer select | LOW (normal) |
| P1 | EEPROM_WP | EEPROM write protect | LOW (writes enabled) |
| P2 | VMM_EN | Motor power enable | LOW (motors off) |
| P3-P7 | Reserved | Future use | LOW |

### HardwareSpecs Differences
| Parameter | REV 1.1 | REV 1.2 |
|-----------|---------|---------|
| `mcp4017_pot_ohms` | 100,000 | 10,000 |
| `mcp4017_fixed_ohms` | 30,000 | 3,000 |
| `has_gpio_expander` | False | True |
| `has_eeprom` | False | True |
| `has_jlink_mux` | False | True |
| `has_motor_power_switch` | False | True |
