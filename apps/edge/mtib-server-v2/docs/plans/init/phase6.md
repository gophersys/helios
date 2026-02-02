# Phase 6: Motion & GPIO

**Status:** ⬜ TODO
**Priority:** P1
**Dependencies:** Phase 2

---

## Objectives

1. Add motor power control RPC (REV 1.2)
2. Add J-Link multiplexer control RPC (REV 1.2)
3. Enhance motion with auto motor power management
4. Add PCB GPIO control (TCA9534A on REV 1.2)
5. Update existing GPIO/Motion RPCs for V2 proto

---

## Deliverables

### D6.1: Motor Power RPC

**Proto:**
```protobuf
rpc MotorPowerEnable(MotorPowerEnableRequest) returns (MotorPowerEnableResponse);
rpc MotorPowerDisable(Empty) returns (MotorPowerDisableResponse);
rpc MotorPowerStatus(Empty) returns (MotorPowerStatusResponse);
```

**Implementation:**
```python
def MotorPowerEnable(self, request, context) -> MotorPowerEnableResponse:
    """Enable motor power supply (REV 1.2 only)."""
    if not self.hardware.has_motor_power_switch:
        return MotorPowerEnableResponse(
            success=True,
            message="Motor power always on (REV 1.1)",
        )

    try:
        self.hardware.set_motor_power(True)
        return MotorPowerEnableResponse(success=True)
    except Exception as e:
        return MotorPowerEnableResponse(success=False, message=str(e))

def MotorPowerStatus(self, request, context) -> MotorPowerStatusResponse:
    """Get motor power status."""
    if not self.hardware.has_motor_power_switch:
        return MotorPowerStatusResponse(
            enabled=True,
            controllable=False,
            revision="1.1",
        )

    enabled = self.hardware.gpio_expander.get_pin(TCA9534APin.VMM_EN)
    return MotorPowerStatusResponse(
        enabled=enabled,
        controllable=True,
        revision="1.2",
    )
```

**Tests:**
```python
def test_motor_power_enable_rev_1_2():
    """REV 1.2 should enable motor power via GPIO."""
    stub.MotorPowerEnable(MotorPowerEnableRequest())
    status = stub.MotorPowerStatus(Empty())
    assert status.enabled
    assert status.controllable

def test_motor_power_noop_rev_1_1():
    """REV 1.1 should succeed but not control power."""
    response = stub.MotorPowerEnable(MotorPowerEnableRequest())
    assert response.success
    assert "always on" in response.message.lower()
```

---

### D6.2: J-Link Multiplexer RPC

**Proto:**
```protobuf
rpc JlinkMuxSet(JlinkMuxSetRequest) returns (JlinkMuxSetResponse);
rpc JlinkMuxStatus(Empty) returns (JlinkMuxStatusResponse);
```

**Implementation:**
```python
def JlinkMuxSet(self, request, context) -> JlinkMuxSetResponse:
    """Set J-Link multiplexer routing (REV 1.2 only)."""
    if not self.hardware.has_jlink_mux:
        return JlinkMuxSetResponse(
            success=False,
            message="J-Link mux not available (REV 1.1)",
        )

    try:
        self.hardware.set_jlink_mux(swap=request.swap)
        return JlinkMuxSetResponse(
            success=True,
            current_routing="swapped" if request.swap else "normal",
        )
    except Exception as e:
        return JlinkMuxSetResponse(success=False, message=str(e))

def JlinkMuxStatus(self, request, context) -> JlinkMuxStatusResponse:
    """Get J-Link multiplexer status."""
    if not self.hardware.has_jlink_mux:
        return JlinkMuxStatusResponse(available=False)

    swapped = self.hardware.gpio_expander.get_pin(TCA9534APin.JLINK_MUL)
    return JlinkMuxStatusResponse(
        available=True,
        current_routing="swapped" if swapped else "normal",
    )
```

**Tests:**
```python
def test_jlink_mux_swap():
    """Should swap J-Link routing on REV 1.2."""
    stub.JlinkMuxSet(JlinkMuxSetRequest(swap=True))
    status = stub.JlinkMuxStatus(Empty())
    assert status.current_routing == "swapped"

def test_jlink_mux_unavailable_rev_1_1():
    """REV 1.1 should report unavailable."""
    response = stub.JlinkMuxSet(JlinkMuxSetRequest(swap=True))
    assert not response.success
```

---

### D6.3: Auto Motor Power Management

**File:** `src/providers/handlers/motion.py`

```python
def start(self, request, context):
    """Start motion with auto motor power."""
    # Auto-enable motor power on REV 1.2
    if self.hardware.has_motor_power_switch:
        self.hardware.set_motor_power(True)
        self.logger.info("Motor power enabled automatically")

    # Existing motion logic...
    try:
        yield from self._run_motion(request, context)
    finally:
        # Optionally disable motor power after motion
        if request.disable_power_after and self.hardware.has_motor_power_switch:
            self.hardware.set_motor_power(False)
            self.logger.info("Motor power disabled after motion")
```

**Tests:**
```python
def test_motion_auto_enables_power():
    """MotionStart should auto-enable motor power on REV 1.2."""
    # Start with power off
    stub.MotorPowerDisable(Empty())
    # Start motion
    stub.MotionStart(MotionStartRequest(duration_seconds=1))
    # Power should be enabled
    status = stub.MotorPowerStatus(Empty())
    assert status.enabled
```

---

### D6.4: PCB GPIO Control

**Proto:**
```protobuf
rpc PcbGpioWrite(PcbGpioWriteRequest) returns (PcbGpioWriteResponse);
rpc PcbGpioRead(PcbGpioReadRequest) returns (PcbGpioReadResponse);
```

**Implementation:**
```python
def PcbGpioWrite(self, request, context) -> PcbGpioWriteResponse:
    """Write PCB GPIO (TCA9534A P3-P7, REV 1.2 only)."""
    if not self.hardware.has_gpio_expander:
        return PcbGpioWriteResponse(
            success=False,
            message="PCB GPIO not available (REV 1.1)",
        )

    # Only allow P3-P7 (P0-P2 are reserved for mux/motor/eeprom)
    if request.pin < 3 or request.pin > 7:
        return PcbGpioWriteResponse(
            success=False,
            message=f"Pin {request.pin} is reserved or invalid",
        )

    pin = TCA9534APin(request.pin)
    self.hardware.gpio_expander.set_pin(pin, request.value)
    return PcbGpioWriteResponse(success=True)
```

**Tests:**
```python
def test_pcb_gpio_write_reserved_fails():
    """Writing to P0-P2 should fail."""
    response = stub.PcbGpioWrite(PcbGpioWriteRequest(pin=0, value=True))
    assert not response.success
    assert "reserved" in response.message.lower()

def test_pcb_gpio_write_user_pins():
    """Writing to P3-P7 should succeed on REV 1.2."""
    response = stub.PcbGpioWrite(PcbGpioWriteRequest(pin=3, value=True))
    assert response.success
```

---

### D6.5: Motion V2 Proto Updates

**Mapping:**
| V1 | V2 | Notes |
|----|----|----|
| `GetMotionStatus` | `MotionStatus` | Same behavior |
| `MotionStart` | `MotionStart` | Add disable_power_after |
| `MotionHome` | `MotionHome` | Same behavior |
| `MotionStop` | `MotionStop` | Same behavior |

**New Fields:**
```protobuf
message MotionStartRequest {
    // ... existing fields
    bool disable_power_after = 10;  // Auto-disable motor power after motion
}
```

---

## Files Changed

| File | Change Type | Description |
|------|-------------|-------------|
| `src/providers/handlers/motion.py` | Modified | Add motor power RPCs, auto-power |
| `src/providers/handlers/gpio.py` | Modified | Add JlinkMux, PcbGpio RPCs |
| `src/providers/mtib.py` | Modified | Wire new RPCs |

---

## Completion Checklist

- [ ] MotorPowerEnable/Disable/Status implemented
- [ ] JlinkMuxSet/Status implemented
- [ ] Auto motor power in MotionStart
- [ ] PcbGpioWrite/Read implemented
- [ ] Reserved pin protection (P0-P2)
- [ ] V2 proto fields mapped
- [ ] Unit tests passing
- [ ] Integration tests on REV 1.1 and 1.2
