# Phase 3: Power & ADC Enhancement

**Status:** ⬜ TODO
**Priority:** P1
**Dependencies:** Phase 2

---

## Objectives

1. Implement high-speed power streaming with timestamps
2. Add duration-based power measurement with statistics
3. Unify power control under `PowerEnable`/`PowerDisable`/`PowerStatus`
4. Add ADC calibration from EEPROM (REV 1.2)
5. Implement GPIO watch streaming for edge detection

---

## Deliverables

### D3.1: PowerStream RPC

**Proto:**
```protobuf
rpc PowerStream(PowerStreamRequest) returns (stream PowerSample);

message PowerStreamRequest {
    string channel = 1;           // "dut" or "charge"
    uint32 sample_rate_hz = 2;    // 1-1000 Hz
}

message PowerSample {
    uint64 timestamp_us = 1;      // Microseconds since epoch
    float voltage_v = 2;
    float current_a = 3;
    float power_w = 4;
}
```

**Implementation:**
```python
def PowerStream(self, request: PowerStreamRequest, context) -> Iterator[PowerSample]:
    """Stream power samples at specified rate."""
    channel = request.channel  # "dut" or "charge"
    interval = 1.0 / request.sample_rate_hz

    ina_path = self.power_ina_path if channel == "dut" else self.chg_power_ina_path

    while context.is_active():
        timestamp = int(time.time() * 1_000_000)

        voltage = self._read_hwmon(ina_path, "in1_input") / 1000.0
        current = self._read_hwmon(ina_path, "curr1_input") / 1000.0
        power = self._read_hwmon(ina_path, "power1_input") / 1_000_000.0

        yield PowerSample(
            timestamp_us=timestamp,
            voltage_v=voltage,
            current_a=current,
            power_w=power,
        )

        time.sleep(interval)
```

**Tests:**
```python
def test_power_stream_returns_samples():
    """Should receive continuous power samples."""
    request = PowerStreamRequest(channel="dut", sample_rate_hz=10)
    samples = list(itertools.islice(stub.PowerStream(request), 10))
    assert len(samples) == 10
    assert all(s.timestamp_us > 0 for s in samples)

def test_power_stream_respects_rate():
    """Samples should arrive at requested rate."""
    request = PowerStreamRequest(channel="dut", sample_rate_hz=100)
    start = time.time()
    samples = list(itertools.islice(stub.PowerStream(request), 100))
    elapsed = time.time() - start
    assert 0.9 < elapsed < 1.2  # ~1 second for 100 samples at 100Hz
```

---

### D3.2: PowerMeasure RPC

**Proto:**
```protobuf
rpc PowerMeasure(PowerMeasureRequest) returns (PowerMeasureResponse);

message PowerMeasureRequest {
    string channel = 1;
    uint32 duration_ms = 2;
    uint32 sample_rate_hz = 3;
}

message PowerMeasureResponse {
    uint32 sample_count = 1;
    float voltage_avg = 2;
    float voltage_min = 3;
    float voltage_max = 4;
    float current_avg = 5;
    float current_min = 6;
    float current_max = 7;
    float power_avg = 8;
    float power_min = 9;
    float power_max = 10;
    float energy_j = 11;         // Joules = Power * Time
}
```

**Implementation:**
```python
def PowerMeasure(self, request: PowerMeasureRequest, context) -> PowerMeasureResponse:
    """Measure power over duration and compute statistics."""
    samples = []
    interval = 1.0 / request.sample_rate_hz
    end_time = time.time() + (request.duration_ms / 1000.0)

    while time.time() < end_time:
        samples.append(self._read_power(request.channel))
        time.sleep(interval)

    voltages = [s.voltage for s in samples]
    currents = [s.current for s in samples]
    powers = [s.power for s in samples]

    return PowerMeasureResponse(
        sample_count=len(samples),
        voltage_avg=statistics.mean(voltages),
        voltage_min=min(voltages),
        voltage_max=max(voltages),
        current_avg=statistics.mean(currents),
        current_min=min(currents),
        current_max=max(currents),
        power_avg=statistics.mean(powers),
        power_min=min(powers),
        power_max=max(powers),
        energy_j=sum(powers) * interval,
    )
```

**Tests:**
```python
def test_power_measure_computes_stats():
    """Should compute min/max/avg over duration."""
    response = stub.PowerMeasure(PowerMeasureRequest(
        channel="dut",
        duration_ms=1000,
        sample_rate_hz=100,
    ))
    assert response.sample_count >= 90  # Allow some timing variance
    assert response.voltage_min <= response.voltage_avg <= response.voltage_max
    assert response.energy_j > 0

def test_power_measure_energy_calculation():
    """Energy should be power * time."""
    # With known load, verify energy calculation
    pass
```

---

### D3.3: Unified Power RPCs

**Mapping V1 → V2:**

| V1 RPC | V2 RPC | Notes |
|--------|--------|-------|
| `DutPowerEnable` | `PowerEnable(channel="dut")` | |
| `DutPowerDisable` | `PowerDisable(channel="dut")` | |
| `DutPowerRead` | `PowerStatus(channel="dut")` | |
| `DutChargePowerEnable` | `PowerEnable(channel="charge")` | |
| `DutChargePowerDisable` | `PowerDisable(channel="charge")` | |
| `DutChargePowerRead` | `PowerStatus(channel="charge")` | |

**Implementation:**
```python
def PowerEnable(self, request: PowerEnableRequest, context) -> PowerEnableResponse:
    """Enable power on specified channel with voltage."""
    if request.channel == "dut":
        self.dut_pwr_en.write(True)
        if request.voltage_v > 0:
            self._set_dut_power_voltage(request.voltage_v)
    elif request.channel == "charge":
        self.dut_chg_en.write(True)
    else:
        return PowerEnableResponse(success=False, message=f"Unknown channel: {request.channel}")

    return PowerEnableResponse(success=True)
```

**Tests:**
```python
def test_power_enable_dut():
    """PowerEnable should enable DUT power."""
    stub.PowerEnable(PowerEnableRequest(channel="dut", voltage_v=3.3))
    status = stub.PowerStatus(PowerStatusRequest(channel="dut"))
    assert status.enabled
    assert 3.2 < status.voltage_v < 3.4
```

---

### D3.4: ADC Calibration (REV 1.2)

**EEPROM Layout:**
```
Offset  Size  Description
0x00    8     Magic "MTIB_CAL"
0x08    4     Calibration version
0x0C    4     ADC0 offset (float)
0x10    4     ADC0 scale (float)
...           (repeat for ADC1-7)
0x4C    4     CRC32
```

**Implementation:**
```python
class AdcHandler:
    def __init__(self, logger, hardware: HardwareContext):
        self.hardware = hardware
        self.calibration = self._load_calibration()

    def _load_calibration(self) -> dict:
        """Load ADC calibration from EEPROM if available."""
        if not self.hardware.has_eeprom:
            return {}  # Use default calibration

        try:
            data = self.hardware.read_eeprom(0x00, 0x50)
            if data[:8] != b'MTIB_CAL':
                return {}
            # Parse calibration data...
        except Exception:
            return {}

    def _apply_calibration(self, channel: int, raw_voltage: float) -> float:
        """Apply channel-specific calibration."""
        cal = self.calibration.get(channel, {'offset': 0, 'scale': 1.0})
        return (raw_voltage + cal['offset']) * cal['scale']
```

**Tests:**
```python
def test_adc_uses_calibration_on_rev_1_2():
    """REV 1.2 should apply EEPROM calibration."""
    # Requires mock EEPROM with known calibration
    pass

def test_adc_uses_defaults_on_rev_1_1():
    """REV 1.1 should use default calibration."""
    pass
```

---

### D3.5: GpioWatch RPC

**Proto:**
```protobuf
rpc GpioWatch(GpioWatchRequest) returns (stream GpioEvent);

message GpioWatchRequest {
    repeated uint32 pins = 1;
    GpioEdge edge = 2;  // RISING, FALLING, BOTH
}

message GpioEvent {
    uint64 timestamp_us = 1;
    uint32 pin = 2;
    bool state = 3;
    GpioEdge edge = 4;
}
```

**Implementation:**
```python
def GpioWatch(self, request: GpioWatchRequest, context) -> Iterator[GpioEvent]:
    """Stream GPIO edge events."""
    lines = []
    for pin in request.pins:
        line = self._gpios[pin].line
        line.request(consumer="mtib-watch", type=gpiod.LINE_REQ_EV_BOTH_EDGES)
        lines.append((pin, line))

    try:
        while context.is_active():
            for pin, line in lines:
                if line.event_wait(timeout=0.1):
                    event = line.event_read()
                    yield GpioEvent(
                        timestamp_us=event.timestamp // 1000,
                        pin=pin,
                        state=event.type == gpiod.LINE_EVENT_RISING_EDGE,
                        edge=GpioEdge.RISING if event.type == gpiod.LINE_EVENT_RISING_EDGE else GpioEdge.FALLING,
                    )
    finally:
        for _, line in lines:
            line.release()
```

**Tests:**
```python
def test_gpio_watch_detects_edges():
    """Should report GPIO edge events."""
    # Toggle GPIO and verify event received
    pass
```

---

## Files Changed

| File | Change Type | Description |
|------|-------------|-------------|
| `src/providers/handlers/power.py` | Modified | Add streaming, measurement, unified RPCs |
| `src/providers/handlers/adc.py` | Modified | Add calibration support |
| `src/providers/handlers/gpio.py` | Modified | Add GpioWatch |
| `src/hardware/eeprom.py` | Created | EEPROM driver for calibration |

---

## Completion Checklist

- [ ] PowerStream RPC implemented
- [ ] PowerMeasure RPC implemented
- [ ] Unified PowerEnable/Disable/Status
- [ ] EEPROM driver created
- [ ] ADC calibration from EEPROM (REV 1.2)
- [ ] GpioWatch RPC implemented
- [ ] Unit tests passing
- [ ] Integration tests with real hardware
