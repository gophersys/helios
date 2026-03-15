# Phase 6: Debug vs Release Comparison

> **When:** Weeks 6-7
> **Hardware state:** Same as Phase 4-5
> **Dependencies:** Phase 4-5 complete (both builds tested)

---

## Purpose

Compare debug and release build test results to catch bugs that only
manifest in one build variant. This is unique to Stage 4 and catches
real production issues.

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

### 2. Power Budget Comparison

| Metric | Debug Build | Release Build | Delta |
|--------|-----------|--------------|-------|
| Sleep current (avg) | — mA | — mA | — |
| Active current (avg) | — mA | — mA | — |
| Motion current (avg) | — mA | — mA | — |
| Peak current | — mA | — mA | — |

Expected: Debug build draws more current due to UART TX activity. The
release build is authoritative for power budget compliance.

### 3. Timing Comparison

For tests with timing requirements (motion detection latency, button
response, cloud message delivery):
- Are there measurable timing differences between builds?
- Do debug logs introduce sufficient delay to change behavior?

---

## Deliverables

1. **Comparison report** documenting pass/fail per test per build
2. **Power budget table** with debug vs release measurements
3. **Bug reports** for any discrepancies
4. **Recommendation** on which tests should be release-only vs both

---

## Phase 6 Checkpoint

| Check | Status |
|-------|--------|
| All 64 tests compared across builds | |
| Power measurements compared | |
| Discrepancies documented as bug reports | |
| Final recommendation written | |
