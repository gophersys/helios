# Phase 3: Stage 3 End-to-End Proof

> **When:** Weeks 3-4
> **Stream:** H
> **Hardware state:** Full MTIB + Alpha B0 setup, integration firmware flashed,
>   shell commands working over UART
> **Dependencies:** Stream E (firmware), Stream F (Python framework)

---

## Stream H: Stage 3 Integration Tests

**Repo:** `~/work/concord/concord/` at `libs/corekinect/test/validation/tests/stage3/`
**Branch:** `v2/init` → `feat/test-framework-stage3`
**Kit:** `claude-kit --kit cloud-python`
**Effort:** ~28h
**Hardware needed:** Full MTIB + Alpha B0, integration firmware flashed

### What This Proves

1. `concord_harness` works on real hardware (not just native_sim)
2. UART shell protocol is reliable over MTIB gRPC streaming
3. Internal firmware state is observable and controllable
4. Python test framework can drive tests programmatically
5. Event emission works (firmware → host notification)

### Test Modules

| File | Tests | What It Proves |
|------|-------|---------------|
| `test_harness_basic.py` | ~5 | Shell protocol: list, get, set values |
| `test_state_observation.py` | ~5 | Read app.state, motion.state accurately |
| `test_event_emission.py` | ~5 | Trigger transition → [CONCORD:EVT] arrives |
| `test_stimulus_injection.py` | ~5 | Inject touch/motion → state changes |
| `test_concurrent.py` | ~5 | Rapid commands + interleaved events |

**Total:** ~25 tests

### Steps

| Step | Task | Effort |
|------|------|--------|
| H1 | Write 5 test modules | 20h |
| H2 | Run E2E on real hardware, debug, iterate | 8h |

### Example Test

```python
# test_stimulus_injection.py
async def test_inject_touch_transitions_state(ctx: TestContext):
    """Injecting touch event should transition from off_body to low_heat_risk."""
    # Verify starting state
    state = await ctx.harness.get("app.state")
    assert state == "off_body_e"

    # Inject touch detection
    await ctx.harness.inject("sensor.touch", "detected")

    # Wait for state change event
    event = await ctx.harness.wait_event("app.state_changed", timeout_s=5.0)
    assert event == "low_heat_risk_e"

    # Verify new state
    state = await ctx.harness.get("app.state")
    assert state == "low_heat_risk_e"
```

### Pass Criteria

- All 25 tests pass on real Alpha B0 via MTIB
- Shell command round-trip < 100ms
- Events arrive within 1s of triggering state change
- No UART data corruption over 100+ consecutive commands
- Multiple test runs produce consistent results

---

## THIS IS THE STAGE 3 PROOF

If Phase 3 passes, we have demonstrated:

| Claim | Evidence |
|-------|---------|
| concord_harness works on real hardware | All macros expanded, shell commands respond |
| UART protocol is reliable | 25 tests pass without corruption |
| Internal state is observable | `concord get` returns correct values |
| Internal state is controllable | `concord set` and `inject` drive transitions |
| Events are emitted correctly | `wait_event` receives firmware-initiated events |
| Python framework drives it all | Tests run programmatically, no human interaction |
| MTIB is a reliable hardware pipe | UART streaming, flash, power all work |

---

## Phase 3 Checkpoint

| Check | Status |
|-------|--------|
| All 25 integration tests pass | |
| Shell round-trip < 100ms | |
| Events arrive within 1s | |
| No UART corruption in test run | |
| Results are reproducible (2+ runs) | |
