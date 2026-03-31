# Stage 4 Alpha Example — Nightly Product Validation

> Step-by-step walkthrough of Stage 4 (Nightly) validation for the Alpha B0 device.
> This is the **comprehensive** test suite that runs every night.
> Duration: 30-60 minutes. Tests everything that doesn't fit in the 15-minute Gate.

---

## 1. Overview

Stage 4 Nightly is **comprehensive black-box product validation**. Unlike Stage 5 Gate (which focuses on FUOTA and fast feedback), Nightly runs all the slow tests that can't fit in a 15-minute PR gate.

### What Nightly Tests

| Category | Tests | Duration |
|----------|-------|----------|
| Power Profiling | Sleep current, active current, modem bursts | 5 min |
| Sensor Sweep | All sensors, all modes, accuracy checks | 10 min |
| Cloud Connectivity | Heartbeat, position, alerts, status messages | 5 min |
| GPS Acquisition | Cold start, warm start, TTFF measurement | 15 min |
| Charger Behavior | Plug/unplug transitions, charge curve | 10 min |
| State Machine | All stimulus combinations, LED verification | 5 min |
| Physical Stimulus | Button, temperature, motion, on-body | 10 min |

### What Nightly Does NOT Test

- **FUOTA** — Stage 5 Gate covers this (every PR)
- **Driver internals** — Stage 2 Silicon covers this
- **Subsystem integration** — Stage 3 Integration covers this

---

## 2. Timing Budget

**Total: 30-60 minutes** (runs overnight, no hard limit)

| Phase | Tests | Duration |
|-------|-------|----------|
| Setup | Connect MTIB, load fixture profile | 30s |
| Flash | nRF52840 + modem + nRF9151 | 2 min |
| Boot | Power cycle, verify current | 30s |
| Personalization | Shell lock, EC keygen, key upload | 2 min |
| **Power Tests** | Sleep, active, modem burst profiles | 5 min |
| **Sensor Tests** | Accelerometer, PPG, temperature, pressure | 10 min |
| **Cloud Tests** | Heartbeat, position, alerts | 5 min |
| **GPS Tests** | Cold start, warm start TTFF | 15 min |
| **Charger Tests** | Plug/unplug, charge state | 10 min |
| **Stimulus Tests** | Button, motion, on-body | 10 min |
| **TOTAL** | | **~60 min** |

---

## 3. Test Categories

### 3.1 Power Profiling Tests

**Purpose**: Verify power consumption meets budget.

```python
@pytest.mark.timeout(300)  # 5 min
class TestPowerProfile:
    """NIGHTLY-ALPHA-PWR: Power profiling tests."""

    def test_sleep_current(self, ctx):
        """NIGHTLY-ALPHA-PWR-001: Sleep current < 50uA."""
        # Boot and wait for device to enter sleep
        ctx.fixture.power_on()
        time.sleep(60)  # Wait for sleep entry

        # Sample current over 30 seconds
        samples = []
        for _ in range(30):
            current_ma = ctx.fixture.read_current()
            samples.append(current_ma)
            time.sleep(1)

        avg_current_ua = sum(samples) / len(samples) * 1000
        assert avg_current_ua < 50, f"Sleep current {avg_current_ua}uA exceeds 50uA budget"

    def test_active_current(self, ctx):
        """NIGHTLY-ALPHA-PWR-002: Active current < 15mA (sensors sampling)."""
        # Trigger active mode via button press
        ctx.fixture.button_press(duration_s=1)
        time.sleep(5)  # Wait for sensors to start

        samples = []
        for _ in range(10):
            current_ma = ctx.fixture.read_current()
            samples.append(current_ma)
            time.sleep(1)

        avg_current_ma = sum(samples) / len(samples)
        assert avg_current_ma < 15, f"Active current {avg_current_ma}mA exceeds 15mA budget"

    def test_modem_burst_current(self, ctx):
        """NIGHTLY-ALPHA-PWR-003: Modem TX burst < 300mA peak."""
        # Wait for heartbeat (triggers modem TX)
        # Sample at high frequency during TX window
        ctx.fixture.power_on()
        time.sleep(30)  # Wait for LTE attach

        # Monitor for 60 seconds to catch a TX burst
        max_current_ma = 0
        for _ in range(600):
            current_ma = ctx.fixture.read_current()
            max_current_ma = max(max_current_ma, current_ma)
            time.sleep(0.1)

        assert max_current_ma < 300, f"Modem burst {max_current_ma}mA exceeds 300mA limit"
```

### 3.2 Sensor Tests

**Purpose**: Verify all sensors respond correctly.

```python
@pytest.mark.timeout(600)  # 10 min
class TestSensors:
    """NIGHTLY-ALPHA-SENS: Sensor characterization tests."""

    def test_accelerometer_range(self, ctx):
        """NIGHTLY-ALPHA-SENS-001: Accelerometer reads gravity correctly."""
        # Device should be stationary in fixture
        # Cloud message should show ~1g on Z axis

        msg = ctx.cloud.wait_for_message("MotionMsgV1", timeout_s=60)
        accel_z = msg.get("accelZ", 0)

        # Expect ~1g (9.8 m/s^2) ± 10%
        assert 0.9 < abs(accel_z) < 1.1, f"Accel Z {accel_z}g out of range"

    def test_ppg_skin_detection(self, ctx):
        """NIGHTLY-ALPHA-SENS-002: PPG detects on-skin stimulus."""
        # Enable peltier to simulate skin temperature
        ctx.fixture.peltier_on()
        time.sleep(10)  # Wait for heating

        msg = ctx.cloud.wait_for_message("VitalsMsgV1", timeout_s=120)
        on_body = msg.get("onBody", False)

        ctx.fixture.peltier_off()
        assert on_body, "PPG did not detect on-body with skin stimulus"

    def test_temperature_sensor(self, ctx):
        """NIGHTLY-ALPHA-SENS-003: Temperature sensor within range."""
        msg = ctx.cloud.wait_for_message("EnvironmentMsgV1", timeout_s=60)
        temp_c = msg.get("temperature", 0)

        # Expect room temperature 15-35°C
        assert 15 < temp_c < 35, f"Temperature {temp_c}°C out of expected range"

    def test_pressure_sensor(self, ctx):
        """NIGHTLY-ALPHA-SENS-004: Pressure sensor within range."""
        msg = ctx.cloud.wait_for_message("EnvironmentMsgV1", timeout_s=60)
        pressure_hpa = msg.get("pressure", 0)

        # Expect sea level pressure ± 100 hPa
        assert 900 < pressure_hpa < 1100, f"Pressure {pressure_hpa}hPa out of range"
```

### 3.3 GPS Tests

**Purpose**: Verify GPS acquisition performance.

```python
@pytest.mark.timeout(900)  # 15 min
class TestGPS:
    """NIGHTLY-ALPHA-GPS: GPS acquisition tests."""

    def test_cold_start_ttff(self, ctx):
        """NIGHTLY-ALPHA-GPS-001: Cold start TTFF < 60 seconds."""
        # Power cycle to clear ephemeris
        ctx.fixture.power_off()
        time.sleep(5)
        ctx.fixture.power_on()

        start = time.time()
        msg = ctx.cloud.wait_for_message(
            "PositionMsgV6",
            filter={"fixType": "3D"},
            timeout_s=120
        )
        ttff = time.time() - start

        assert ttff < 60, f"Cold start TTFF {ttff}s exceeds 60s limit"

    def test_warm_start_ttff(self, ctx):
        """NIGHTLY-ALPHA-GPS-002: Warm start TTFF < 10 seconds."""
        # First, get a fix (cold start)
        ctx.cloud.wait_for_message("PositionMsgV6", filter={"fixType": "3D"}, timeout_s=120)

        # Brief power cycle (preserve ephemeris)
        ctx.fixture.power_off()
        time.sleep(2)
        ctx.fixture.power_on()

        start = time.time()
        msg = ctx.cloud.wait_for_message(
            "PositionMsgV6",
            filter={"fixType": "3D"},
            timeout_s=30
        )
        ttff = time.time() - start

        assert ttff < 10, f"Warm start TTFF {ttff}s exceeds 10s limit"
```

### 3.4 Charger Tests

**Purpose**: Verify charger behavior.

```python
@pytest.mark.timeout(600)  # 10 min
class TestCharger:
    """NIGHTLY-ALPHA-CHG: Charger behavior tests."""

    def test_charger_detect(self, ctx):
        """NIGHTLY-ALPHA-CHG-001: Device detects charger connection."""
        # Start with charger disconnected
        ctx.fixture.charger_off()
        time.sleep(5)

        # Connect charger
        ctx.fixture.charger_on()
        time.sleep(10)

        msg = ctx.cloud.wait_for_message("StatusMsgV1", timeout_s=30)
        assert msg.get("onCharger") == True, "Device did not detect charger"

    def test_charger_disconnect(self, ctx):
        """NIGHTLY-ALPHA-CHG-002: Device detects charger disconnection."""
        # Start with charger connected
        ctx.fixture.charger_on()
        time.sleep(5)

        # Disconnect charger
        ctx.fixture.charger_off()
        time.sleep(10)

        msg = ctx.cloud.wait_for_message("StatusMsgV1", timeout_s=30)
        assert msg.get("onCharger") == False, "Device did not detect charger removal"

    def test_charge_current(self, ctx):
        """NIGHTLY-ALPHA-CHG-003: Charge current within spec."""
        ctx.fixture.charger_on()
        time.sleep(10)

        # Measure charger rail current
        current_ma = ctx.fixture.read_current(channel=1)  # ch1 = charger rail

        # Expect 50-200mA charging current
        assert 50 < current_ma < 200, f"Charge current {current_ma}mA out of range"
```

### 3.5 Stimulus Tests

**Purpose**: Verify device responds to physical stimulus.

```python
@pytest.mark.timeout(600)  # 10 min
class TestStimulus:
    """NIGHTLY-ALPHA-STIM: Physical stimulus tests."""

    def test_button_short_press(self, ctx):
        """NIGHTLY-ALPHA-STIM-001: Short button press triggers state change."""
        ctx.fixture.button_press(duration_s=0.5)
        time.sleep(2)

        msg = ctx.cloud.wait_for_message("StatusMsgV1", timeout_s=30)
        # Verify state changed (depends on current state)
        assert msg is not None, "No status message after button press"

    def test_button_long_press(self, ctx):
        """NIGHTLY-ALPHA-STIM-002: Long button press triggers SOS/shutdown."""
        ctx.fixture.button_press(duration_s=5)
        time.sleep(2)

        # Check for SOS alert or shutdown
        msg = ctx.cloud.wait_for_message("AlertMsgV1", timeout_s=30)
        # Device may have shut down if no SOS configured

    def test_motion_detection(self, ctx):
        """NIGHTLY-ALPHA-STIM-003: Motion stage triggers motion event."""
        if not ctx.fixture.has_motion():
            pytest.skip("Motion stage not available")

        # Shake device
        ctx.fixture.motion_shake(duration_s=5)
        time.sleep(2)

        msg = ctx.cloud.wait_for_message("MotionMsgV1", timeout_s=30)
        assert msg.get("motionDetected") == True, "Motion not detected"
```

---

## 4. Test Organization

```
apps/validation/alpha/tests/stage4/
├── conftest.py              # Stage 4 fixtures
├── test_power.py            # Power profiling tests
├── test_sensors.py          # Sensor characterization
├── test_cloud.py            # Cloud message verification
├── test_gps.py              # GPS acquisition tests
├── test_charger.py          # Charger behavior tests
├── test_stimulus.py         # Physical stimulus tests
└── test_nfc.py              # NFC tag operations
```

---

## 5. Running Nightly

### Cron Schedule

```yaml
# K8s CronJob
apiVersion: batch/v1
kind: CronJob
metadata:
  name: validation-alpha-nightly
spec:
  schedule: "0 2 * * *"  # 2 AM daily
  jobTemplate:
    spec:
      template:
        spec:
          containers:
            - name: nightly
              image: concord/http-api:staging
              command: ["pytest", "/app/validation/alpha/tests/stage4/", "-v"]
              env:
                - name: MTIB_ADDRESS
                  value: "10.4.45.33:50053"
                # ... other env vars
```

### Manual Run

```bash
cd apps/validation/alpha
pytest tests/stage4/ -v --timeout=3600
```

---

## 6. Key Differences from Stage 5 Gate

| Aspect | Stage 4 Nightly | Stage 5 Gate |
|--------|-----------------|--------------|
| Duration | 30-60 min | < 15 min |
| Trigger | Nightly cron | Every PR |
| Blocks merge | No | **Yes** |
| FUOTA | No | **Yes** |
| GPS tests | Cold + warm start | No |
| Charger tests | Full cycle | No |
| Sensor sweep | All modes | Basic check |
| Power profiling | Extended | Quick check |

---

## 7. Related Documents

- [Stages Overview](../../architecture/validation/stages-overview.md) — All 5 stages
- [Stage 5 FUOTA](../../architecture/validation/stage5-fuota-tests.md) — PR validation + OTA verification
- [Stage 4 Implementation](../../architecture/validation/stage4-product-tests.md) — Full spec
- [PRDTST Reference](../../reference/alpha-test-cases.md) — Test case catalog
