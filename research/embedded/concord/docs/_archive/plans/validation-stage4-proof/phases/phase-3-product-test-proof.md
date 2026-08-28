# Phase 3: Product Test Proof

> **When:** Weeks 5-6
> **Stream:** C
> **Hardware state:** Full fixture (GPIO, ADC, motion all wired and verified),
>   test framework operational, CloudClient returning real data
> **Dependencies:** Stream A (test framework), Stream B (fixture wired),
>   CoreCloud env accessible

---

## Stream C: Stage 4 Test Modules + E2E

**Repo:** `~/work/concord/concord/` at `libs/corekinect/test/validation/tests/stage4/`
**Branch:** `v2/init` → `feat/stage4-test-modules`
**Effort:** ~64h
**Hardware needed:** Full MTIB + Alpha B0 + CoreCloud env

### What This Proves

1. Production firmware (no instrumentation) behaves correctly on real hardware
2. Physical stimulus (GPIO, motion) triggers expected device behavior
3. Device correctly reports to CoreCloud (PositionMsgV6, BiometricDataMsg, BootMsgV2)
4. Power budgets are within spec
5. Debug and release builds produce equivalent functional results
6. The shipping binary works end-to-end

### Test Modules

| Step | Module | Tests | Stimulus | Verification |
|------|--------|-------|----------|-------------|
| C1 | `test_boot.py` | ~3 | Power cycle | BootMsgV2 at CoreCloud |
| C2 | `test_motion.py` | 5 | MotionStart (scaffold shake) | PositionMsgV6.is_in_motion |
| C3 | `test_biometric.py` | 3 | GPIO on-skin electrode | BiometricDataMsg.on_body |
| C4 | `test_button.py` | 9 | GPIO button press | Device response (LED, CoreCloud) |
| C5 | `test_environmental.py` | 7 | Ambient conditions | BiometricDataMsg fields |
| ~~C6~~ | ~~`test_gnss.py`~~ | ~~7~~ | ~~GPS config push~~ | **DEFERRED — indoor scaffold, no GPS signal** |
| C7 | `test_power.py` | 7 | PowerMeasure over time | Current within budget |
| C8 | `test_nfc.py` | 1 | NFC reader scan | Device ID read |
| C9 | **Debug build E2E** | All above | Flash debug FW → run all | All pass |
| C10 | **Release build E2E** | All above | Flash release FW → run all | All pass |

**Total:** 64 active PRDTST tests, run on both builds = **128 test executions**.

### Dual-Build Execution

Each test runs twice — once with debug firmware, once with release:

```python
# conftest.py (from Phase 1 Stream A)
@pytest.fixture(params=["debug", "release"])
async def firmware_build(ctx, request):
    variant = request.param
    await ctx.fixture.flash_firmware(
        hex_path=os.environ[f"FW_{variant.upper()}_HEX"],
        target="nrf52840",
    )
    await ctx.fixture.power_cycle()
    await ctx.cloud.wait_for_boot(timeout_s=120)
    yield variant
```

### Deferred Tests

| Category | Count | Reason |
|----------|-------|--------|
| Charging/BMS | 29 | Same MTIB power source for DUT + CHG |
| Config Values | 18 | GroundModeConfigV2 endpoint unavailable |
| GNSS | 7 | Indoor scaffold, no GPS signal source |

### Steps

| Step | Task | Effort |
|------|------|--------|
| C1-C5, C7-C8 | Write 7 test modules | 48h |
| C9 | Debug build E2E run + debug | 8h |
| C10 | Release build E2E run + debug | 8h |

---

## Test Module Details

### C1: test_boot.py (~3 tests)

Verifies that power cycling produces a valid BootMsgV2 at CoreCloud with
correct fields. This is the most fundamental test — if boot doesn't work,
nothing else can run.

```python
async def test_boot_produces_bootmsg(ctx, firmware_build):
    """Power cycle device, verify BootMsgV2 arrives at CoreCloud."""
    ctx.cloud.mark_test_start()
    await ctx.fixture.power_cycle()
    msg = await ctx.cloud.wait_for_boot(timeout_s=120)
    assert msg is not None, "No BootMsgV2 received after power cycle"
    assert msg.boot_reason == 1  # Normal boot (power cycle)

async def test_boot_reports_correct_firmware_version(ctx, firmware_build):
    """BootMsgV2 firmware version matches the flashed binary."""
    ctx.cloud.mark_test_start()
    await ctx.fixture.power_cycle()
    msg = await ctx.cloud.wait_for_boot(timeout_s=120)
    expected = os.environ[f"FW_{firmware_build.upper()}_VERSION"]
    assert msg.fw_version == expected

async def test_boot_current_within_budget(ctx, firmware_build):
    """Boot sequence current draw is within spec."""
    result = await ctx.power.measure(channel=0, duration_s=10)
    assert result.peak_current_ma < 200, f"Boot peak current {result.peak_current_ma}mA exceeds 200mA"
```

### C2: test_motion.py (5 tests)

Verifies motion detection via linear actuator stimulus.

```python
async def test_motion_above_threshold(ctx, firmware_build):
    """Shaking device triggers PositionMsgV6 with is_in_motion=True."""
    ctx.cloud.mark_test_start()
    await ctx.fixture.shake(duration_s=30, speed_mm_s=50)
    msg = await ctx.cloud.wait_for_position(
        predicate=lambda m: m.is_in_motion,
        timeout_s=120,
    )
    assert msg is not None, "No motion-flagged PositionMsgV6 received"
    assert msg.is_in_motion is True

async def test_no_motion_when_stationary(ctx, firmware_build):
    """Stationary device does not falsely trigger motion."""
    ctx.cloud.mark_test_start()
    await ctx.fixture.stop_motion()
    await asyncio.sleep(120)  # Wait for next position report
    msg = await ctx.cloud.wait_for_position(timeout_s=120)
    assert msg.is_in_motion is False
```

### C3: test_biometric.py (3 tests)

Verifies on-skin detection and biometric data reporting.

```python
async def test_on_skin_detected(ctx, firmware_build):
    """On-skin electrode triggers BiometricDataMsg with on_body=True."""
    ctx.cloud.mark_test_start()
    await ctx.fixture.simulate_on_skin(on=True)
    msg = await ctx.cloud.wait_for_biometric(
        predicate=lambda m: m.on_body,
        timeout_s=120,
    )
    assert msg is not None, "No on-body BiometricDataMsg received"
    assert msg.on_body is True

async def test_off_skin_detected(ctx, firmware_build):
    """Removing on-skin electrode triggers on_body=False."""
    await ctx.fixture.simulate_on_skin(on=True)
    await asyncio.sleep(30)  # Let device detect on-body
    ctx.cloud.mark_test_start()
    await ctx.fixture.simulate_on_skin(on=False)
    msg = await ctx.cloud.wait_for_biometric(
        predicate=lambda m: not m.on_body,
        timeout_s=120,
    )
    assert msg.on_body is False
```

### C4: test_button.py (9 tests)

Verifies button press responses: short press (status LED), long press
(SOS), very long press (power off). Verification via CoreCloud messages
and ADC photodiode reads (LED color).

```python
async def test_short_press_status_led(ctx, firmware_build):
    """Short button press triggers status LED."""
    ctx.cloud.mark_test_start()
    await ctx.fixture.press_button(duration_s=0.5)
    await asyncio.sleep(1)
    led = await ctx.fixture.read_led_color()
    # At least one LED channel should be active after short press
    assert any(v > 0.1 for v in led.values()), "No LED response to short press"
```

### C5: test_environmental.py (7 tests)

Verifies environmental sensor data (temperature, pressure, humidity) in
BiometricDataMsg. Uses ambient conditions — no active stimulus needed
for most tests.

```python
async def test_temperature_within_range(ctx, firmware_build):
    """Environmental temperature reading is plausible (10-40°C indoor)."""
    ctx.cloud.mark_test_start()
    msg = await ctx.cloud.wait_for_biometric(timeout_s=120)
    assert 10 <= msg.temperature <= 40, f"Temperature {msg.temperature}°C out of range"
```

### C7: test_power.py (7 tests)

Verifies power budgets. Release build measurements are authoritative;
debug build measurements are informational.

```python
async def test_active_mode_current(ctx, firmware_build):
    """Active mode current draw is within budget."""
    result = await ctx.power.measure(channel=0, duration_s=60)
    if firmware_build == "release":
        assert result.avg_current_ma < 15, (
            f"Active current {result.avg_current_ma}mA exceeds 15mA budget"
        )

async def test_sleep_mode_current(ctx, firmware_build):
    """Sleep mode current is below threshold."""
    if firmware_build == "debug":
        pytest.skip("Power tests authoritative on release only")
    # Wait for device to enter sleep (5 min idle)
    await asyncio.sleep(300)
    result = await ctx.power.measure(channel=0, duration_s=60)
    assert result.avg_current_ma < 0.5, (
        f"Sleep current {result.avg_current_ma}mA exceeds 500µA"
    )
```

### C8: test_nfc.py (1 test)

Verifies NFC tag contains correct device ID.

```python
async def test_nfc_device_id(ctx, firmware_build):
    """NFC tag read returns correct device ID."""
    tag_data = await ctx.mtib.nfc_read(bus=1)
    expected_device_id = os.environ["DEVICE_ID"]
    assert expected_device_id in tag_data.decode(), "Device ID not found in NFC tag"
```

---

## Execution Strategy

### Order of Execution

1. **Write all 7 test modules** (C1-C5, C7-C8) — 48h
2. **Debug E2E run (C9):**
   - Flash debug firmware to nRF52840
   - Run `pytest tests/stage4/ -k "debug"` — all 64 tests
   - Capture UART logs → `debug_uart_log.txt`
   - Debug failures using UART output
   - Iterate until all 64 pass
3. **Release E2E run (C10):**
   - Flash release firmware to nRF52840
   - Run `pytest tests/stage4/ -k "release"` — all 64 tests
   - No UART logs available (silent build)
   - Debug failures by re-running on debug build for diagnostics
   - Iterate until all 64 pass

### Debug Strategy

When a release test fails but debug passes:
- This is a **CRITICAL** finding — timing or power bug exposed by removing log overhead
- File firmware bug with highest priority
- Compare power measurements between builds for the failing test

When both builds fail:
- Debug using UART logs from the debug run
- Check CloudClient polling (is the message arriving late or not at all?)
- Check FixtureController (is the GPIO actually toggling? Use MTIB read-back)

---

## Re-personalization Rule

**After every firmware flash (debug or release), the device must be
re-personalized before tests that depend on CoreCloud.** See
`.claude/rules/repersonalization-workflow.md`.

The `firmware_build` fixture in conftest.py calls `ctx.fixture.flash_firmware()`
followed by `ctx.fixture.power_cycle()` and `ctx.cloud.wait_for_boot()`. The
re-personalization step must be integrated into this flow — either inside
`flash_firmware()` or as an explicit call between flash and boot verification.

Without re-personalization, the device will boot but cannot authenticate with
CoreCloud → all `wait_for_boot()`, `wait_for_position()`, etc. calls will
timeout because no messages are delivered.

---

## Validation Devices

| Device | SNR | Device ID | MTIB Rev | MTIB Node |
|--------|-----|-----------|----------|-----------|
| Alpha B0 #1 | 0964 | `70B3D584C01E1FCC` | REV 1.2 | 10.4.45.33 |
| Alpha B0 #2 | 097D | `70B3D584C01E20A2` | REV 1.1 | 10.4.45.32 |

Tests should run on **both devices** to verify REV 1.1 vs REV 1.2 compatibility.

---

## Phase 2 Checkpoint (updated 2026-03-01)

| Check | Status |
|-------|--------|
| All 7 test modules written (C6 GNSS deferred) | **DONE** (37 tests: 36 active + 1 NFC skipped) |
| Debug build: tests pass | Not started (MTIB not deployed, fixture not wired) |
| Release build: tests pass | Not started |
| CoreCloud receives expected messages for all tests | Not started |
| Power measurements recorded for all power tests | Not started |
| UART logs captured for debug run | Not started |
| Re-personalization automated in flash cycle | **TODO** — critical for test execution |
