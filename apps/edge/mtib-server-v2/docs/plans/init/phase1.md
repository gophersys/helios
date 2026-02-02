# Phase 1: Foundation & Hardware Abstraction

**Status:** ✅ COMPLETE
**Priority:** P0 (Critical Path)
**Dependencies:** None

---

## Objectives

1. Create hardware abstraction layer for multi-revision support
2. Implement automatic hardware revision detection
3. Provide unified access to revision-specific features
4. Update server entry point to use hardware context

---

## Deliverables

### D1.1: Hardware Package ✅

**Location:** `src/hardware/`

| File | Purpose | Status |
|------|---------|--------|
| `__init__.py` | Public API exports | ✅ Done |
| `revision.py` | HardwareRevision enum, HardwareSpecs dataclass | ✅ Done |
| `context.py` | HardwareContext unified access | ✅ Done |
| `tca9534a.py` | TCA9534A GPIO expander driver | ✅ Done |

### D1.2: HardwareRevision Enum ✅

```python
class HardwareRevision(Enum):
    REV_1_1 = HardwareSpecs(
        revision_id="1.1",
        mcp4017_pot_ohms=100_000,
        mcp4017_fixed_ohms=30_000,
        has_gpio_expander=False,
        has_eeprom=False,
        has_jlink_mux=False,
        has_motor_power_switch=False,
    )
    REV_1_2 = HardwareSpecs(
        revision_id="1.2",
        mcp4017_pot_ohms=10_000,
        mcp4017_fixed_ohms=3_000,
        has_gpio_expander=True,
        has_eeprom=True,
        has_jlink_mux=True,
        has_motor_power_switch=True,
    )
```

### D1.3: Hardware Detection ✅

```python
@classmethod
def detect(cls, bus_num: int = 1) -> HardwareRevision:
    """Auto-detect by probing I2C for REV 1.2 devices."""
    # Check TCA9534A @ 0x38 or EEPROM @ 0x50
    # Return REV_1_2 if found, else REV_1_1
```

### D1.4: Environment Variable Override ✅

| Variable | Description | Example |
|----------|-------------|---------|
| `MTIB_HARDWARE_REVISION` | Override auto-detection | `1.2`, `REV1.1` |
| `MTIB_AUTO_DETECT_REVISION` | Disable detection | `false` |

### D1.5: HardwareContext ✅

```python
class HardwareContext:
    revision: HardwareRevision
    specs: HardwareSpecs

    def calculate_voltage_wiper(self, voltage: float) -> int
    def set_jlink_mux(self, swap: bool) -> None  # REV 1.2 only
    def set_motor_power(self, enable: bool) -> None  # REV 1.2 only
    def set_eeprom_write_protect(self, protect: bool) -> None  # REV 1.2 only
```

### D1.6: TCA9534A Driver ✅

```python
class TCA9534A:
    def init(self) -> None
    def set_pin(self, pin: TCA9534APin, value: bool) -> None
    def get_pin(self, pin: TCA9534APin) -> bool
    def set_jlink_mux(self, swap: bool) -> None
    def set_motor_power(self, enable: bool) -> None
    def set_eeprom_write_protect(self, protect: bool) -> None
```

### D1.7: Provider Updates ✅

- Renamed `MtibV1Provider` → `MtibV2Provider`
- Config now takes `HardwareContext` instead of `HARDWARE_VERSION: str`
- Handlers receive hardware context for revision-aware behavior

### D1.8: Handler Updates ✅

| Handler | Change |
|---------|--------|
| `PowerHandler` | Uses `HardwareContext.calculate_voltage_wiper()` |
| `MotionHandler` | Uses `HardwareContext.set_motor_power()` |

---

## Test Cases

### T1.1: Revision Detection ✅
```python
def test_detect_rev_1_1_when_no_devices():
    """Should return REV_1_1 when TCA9534A and EEPROM not found."""

def test_detect_rev_1_2_when_tca9534a_present():
    """Should return REV_1_2 when TCA9534A responds at 0x38."""

def test_detect_rev_1_2_when_eeprom_present():
    """Should return REV_1_2 when EEPROM responds at 0x50."""
```

### T1.2: Environment Override ✅
```python
def test_from_env_override():
    """MTIB_HARDWARE_REVISION should override detection."""

def test_auto_detect_disabled():
    """MTIB_AUTO_DETECT_REVISION=false should use REV_1_1."""
```

### T1.3: Voltage Calculation ✅
```python
def test_wiper_calculation_rev_1_1():
    """100kΩ pot should give different wiper for same voltage."""

def test_wiper_calculation_rev_1_2():
    """10kΩ pot should give different wiper for same voltage."""
```

### T1.4: Feature Guards ✅
```python
def test_jlink_mux_raises_on_rev_1_1():
    """set_jlink_mux should raise HardwareFeatureNotAvailable on REV 1.1."""

def test_motor_power_noop_on_rev_1_1():
    """set_motor_power should log warning but not raise on REV 1.1."""
```

---

## Files Changed

| File | Change Type |
|------|-------------|
| `src/hardware/__init__.py` | Created |
| `src/hardware/revision.py` | Created |
| `src/hardware/context.py` | Created |
| `src/hardware/tca9534a.py` | Created |
| `src/main.py` | Modified |
| `src/providers/mtib.py` | Modified |
| `src/providers/handlers/power.py` | Modified |
| `src/providers/handlers/motion.py` | Modified |
| `.env.example` | Modified |
| `README.md` | Modified |

---

## Completion Checklist

- [x] Hardware package created
- [x] HardwareRevision enum with specs
- [x] I2C probing detection
- [x] Environment variable override
- [x] HardwareContext manager
- [x] TCA9534A driver
- [x] Provider updated to MtibV2Provider
- [x] PowerHandler uses hardware context
- [x] MotionHandler uses hardware context
- [x] Documentation updated
