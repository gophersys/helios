# Phase 4: Debug vs Release Comparison

> **When:** Week 7
> **Hardware state:** Same as Phase 3
> **Dependencies:** Phase 3 complete (both builds tested, all 128 test runs done)

---

## Purpose

Compare debug and release build test results to catch bugs that only
manifest in one build variant. This is unique to Stage 4 and catches
real production issues that instrumented testing (Stage 3) cannot find.

---

## Comparison Matrix

| Scenario | Meaning | Severity | Action |
|----------|---------|----------|--------|
| Debug passes, Release fails | Log overhead was masking a timing/power bug | **CRITICAL** | File firmware bug, highest priority |
| Release passes, Debug fails | Log system interference (UART TX blocking) | **HIGH** | File firmware bug |
| Both pass | Normal | — | Record results |
| Both fail | Standard firmware defect | **MEDIUM** | File firmware bug |

---

## Analysis Areas

### 1. Functional Comparison

For each of the 64 tests:
- Did it pass on both builds?
- If different, what was the failure mode?
- Is the difference timing-related or state-related?

Produce a pass/fail matrix:

```
Test                              Debug    Release
─────────────────────────────────────────────────
test_boot_produces_bootmsg         PASS     PASS
test_boot_reports_fw_version       PASS     PASS
test_motion_above_threshold        PASS     FAIL  ← CRITICAL
test_on_skin_detected              PASS     PASS
...
```

### 2. Power Budget Comparison

| Metric | Debug Build | Release Build | Delta | Notes |
|--------|-----------|--------------|-------|-------|
| Boot peak current | — mA | — mA | — | |
| Active mode (avg) | — mA | — mA | — | Debug higher due to UART TX |
| Sleep mode (avg) | — mA | — mA | — | Release is authoritative |
| Motion mode (avg) | — mA | — mA | — | |
| Peak current | — mA | — mA | — | |

Expected: Debug build draws more current due to UART TX activity. The
release build is authoritative for power budget compliance.

### 3. Timing Comparison

For tests with timing requirements:
- **Motion detection latency:** How long between actuator start and
  PositionMsgV6.is_in_motion at CoreCloud?
- **Button response:** Time from GPIO press to LED response (ADC) or
  CoreCloud message?
- **Cloud message delivery:** Time from stimulus to message arrival at
  CoreCloud? Is it consistently within the uplink interval?

Compare timing measurements between builds. Log overhead in the debug
build may introduce measurable delays — document these.

### 4. UART Log Analysis (Debug Build Only)

Review the `debug_uart_log.txt` artifact from the debug E2E run:
- Any error-level log messages during passing tests?
- Warning patterns that suggest latent issues?
- Log messages that correlate with timing differences vs release?

---

## Deliverables

1. **Comparison report** — pass/fail matrix per test per build
2. **Power budget table** — debug vs release measurements with delta
3. **Timing comparison** — latency measurements for time-sensitive tests
4. **Bug reports** — filed for any discrepancies between builds
5. **Recommendation** — which tests should be release-only vs both,
   which power thresholds are authoritative

---

## Phase 3 Checkpoint

| Check | Status |
|-------|--------|
| All 64 tests compared across builds | |
| Power measurements compared | |
| Timing comparison documented | |
| Discrepancies documented as bug reports | |
| UART log analysis complete | |
| Final recommendation written | |
