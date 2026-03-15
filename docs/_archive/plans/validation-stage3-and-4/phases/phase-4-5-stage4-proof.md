# Phase 4-5: Stage 4 End-to-End Proof

> **When:** Weeks 4-6
> **Stream:** J
> **Hardware state:** Full fixture (GPIO, ADC, motion all wired and verified)
> **Dependencies:** Stream G (cloud client, spec), Stream F (fixture controller),
>   Stream C (fixture wired), CoreCloud env accessible

---

## Stream J: Stage 4 Test Modules

**Repo:** `~/work/concord/concord/` at `libs/corekinect/test/validation/tests/stage4/`
**Branch:** `v2/init` → `feat/test-framework-stage4`
**Kit:** `claude-kit --kit cloud-python`
**Effort:** ~64h
**Hardware needed:** Full MTIB + Alpha B0 + CoreCloud env

### What This Proves

1. Production firmware (no instrumentation) behaves correctly
2. Physical stimulus (GPIO, motion) triggers expected device behavior
3. Device correctly reports to CoreCloud (PositionMsgV6, BiometricDataMsg, BootMsgV2)
4. Power budgets are within spec
5. Debug and release builds produce equivalent functional results
6. The shipping binary works end-to-end

### Test Modules

| Step | Module | Tests | Stimulus | Verification |
|------|--------|-------|----------|-------------|
| J1 | `test_boot.py` | ~3 | Power cycle | BootMsgV2 at CoreCloud |
| J2 | `test_motion.py` | 5 | MotionStart (scaffold shake) | PositionMsgV6.is_in_motion |
| J3 | `test_biometric.py` | 3 | GPIO on-skin electrode | BiometricDataMsg.on_body |
| J4 | `test_button.py` | 9 | GPIO button press | Device response (LED, CoreCloud) |
| J5 | `test_environmental.py` | 7 | Ambient conditions | BiometricDataMsg fields |
| ~~J6~~ | ~~`test_gnss.py`~~ | ~~7~~ | ~~GPS config push~~ | **DEFERRED — indoor scaffold, no GPS signal** |
| J7 | `test_power.py` | 7 | PowerMeasure over time | Current within budget |
| J8 | `test_nfc.py` | 1 | NFC reader scan | Device ID read |
| J9 | **Debug build E2E** | All above | Flash debug FW → run all | All pass |
| J10 | **Release build E2E** | All above | Flash release FW → run all | All pass |

**Total:** 64 active PRDTST tests, run on both builds.

### Dual-Build Execution

Each test runs twice — once with debug firmware, once with release:

```python
# conftest.py
@pytest.fixture(params=["debug", "release"])
def firmware_build(ctx, request):
    if request.param == "debug":
        ctx.flash_debug()
    else:
        ctx.flash_release()
    yield request.param
```

### Example Tests

**Motion test (J2):**
```python
async def test_prdtst_326_motion_above_threshold(ctx, firmware_build):
    ctx.cloud.mark_test_start()
    await ctx.fixture.shake(duration_s=30, speed_mm_s=50)
    msg = await ctx.cloud.wait_for_position(
        predicate=lambda m: m.is_in_motion,
        timeout_s=120
    )
    assert msg is not None, "No motion-flagged PositionMsgV6 received"
    assert msg.is_in_motion is True
```

**Power test (J7):**
```python
async def test_prdtst_348_sleep_mode_current(ctx, firmware_build):
    if firmware_build == "debug":
        pytest.skip("Power tests authoritative on release only")
    # Device should be in sleep after 5 min idle
    await asyncio.sleep(300)
    result = await ctx.mtib.power_measure(
        channel=PowerChannel.DUT, duration_s=60
    )
    assert result.avg_current_a * 1000 < 0.5  # < 500µA
```

**Button test (J4):**
```python
async def test_prdtst_button_short_press(ctx, firmware_build):
    ctx.cloud.mark_test_start()
    await ctx.fixture.press_button(duration_s=0.5)
    # Expect battery status LED (verify via ADC photodiode or CloudMsg)
    # If debug build: check UART for button press log
    if firmware_build == "debug":
        await ctx.logs.wait_for("button press", timeout_s=5)
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
| J1-J5,J7-J8 | Write 7 test modules (J6 GNSS deferred) | 48h |
| J9 | Debug build E2E run + debug | 8h |
| J10 | Release build E2E run + debug | 8h |

---

## Phase 4-5 Checkpoint

| Check | Status |
|-------|--------|
| All 7 test modules written (J6 GNSS deferred) | **COMPLETE** — 8 modules + 1 smoke, 112 tests total |
| Mock mode passing | **COMPLETE** — 60/112 pass, 50 skip, 2 xfail |
| Validation container deployed to K8s | **COMPLETE** — one-shot Job on concordagent01 |
| Firmware flash + re-personalize pipeline | **COMPLETE** — debug build personalizes; release build skips (no shell) |
| Flash caching + test reordering | **COMPLETE** — 2 flash cycles per run (was ~70) |
| GPIO stimulus auto-configuration | **COMPLETE** — button/on_skin/peltier/charger_relay as OUTPUT |
| Debug build hardware tests | **24P 23F 67S** — 14 of 23 failures are ch0-only power issue |
| Release build hardware tests | Same pattern — ch0 power + LED/peltier/motion hardware |
| CoreCloud DB integration (42 tests) | **BLOCKED** — needs Jarred for DEV_1_0 DB creds |
| Power measurements recorded | **PARTIAL** — PowerMeasure/PowerStream RPCs work; budget thresholds need review |
| LED/photodiode tests | **BLOCKED** — hardware not wired |
| Motion tests (10) | **BLOCKED** — FluidNC rail not connected |
| NFC tests (2) | **BLOCKED** — NFC reader not wired |

### Remaining Failures (Run 5 — 23 failures)

| Failure Category | Count | Type | Resolution |
|-----------------|-------|------|------------|
| `verify_dut_powered()` ch0-only | 6 | **Code fix** | Use `read_total_current()` (ch0+ch1) instead of ch0 alone |
| Power measurement ch0-only | 5 | **Code fix** | `PowerMeasure` + budget assertions need ch0+ch1 combined |
| Power anomaly min_current | 2 | **Code fix** | ch0 reads -1 to 0mA (normal with charger) — use total |
| ADC rail label mismatch | 2 | **Code fix** | Update `power_rails_stable` ADC→rail mapping |
| Smoke power_measure ch0 | 1 | **Code fix** | Same charger takeover issue |
| LED/photodiode not wired | 2 | **Hardware** | Wire photodiode to ADC channel |
| Peltier delta ~0V | 2 | **Hardware** | Verify peltier wiring + power supply |
| Motion stimulus absent | 2 | **Hardware** | Wire FluidNC rail, set MOTION_ENABLED=true |
| NFC not wired | 0 (skipped) | **Hardware** | Wire NFC reader to I2C |

**16 of 23 failures are code-fixable** (no hardware changes needed).
Fixing `verify_dut_powered()` + power measurement channel logic should
resolve the majority in a single deploy.

### Optimization Achievements

| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| Full run time | ~3 hours | ~15 min | **12x faster** |
| Flash cycles per run | ~70 | 2 | **35x fewer** |
| Cloud test timeout waste | 120s × 42 = 84 min | 0s (auto-skip) | **84 min saved** |
| Re-personalization | Manual | Automatic | **Unblocked debug variant** |
