<!-- AGENT RECOVERY PROTOCOL
If you are reading this after context compaction:
1. You are working on this specific stage
2. Read STATUS.md to find your progress within this stage
3. Read MEMORY.md for all decisions and gotchas
4. Read ORCHESTRATOR.md if you need the overall system or recovery steps
5. Continue from where STATUS.md says you left off
6. UPDATE STATUS.md after every significant action
7. Commit your work with descriptive messages (NO AI attribution)
8. When this stage is COMPLETE:
   a. Run the Post-Stage Reconciliation Protocol (see ORCHESTRATOR.md)
   b. Write a ## Reconciliation section at the bottom of THIS file
   c. Do a Global Coherence Check against SPEC.md
   d. Update any downstream stage files if your work changed assumptions
   e. Update STATUS.md and MEMORY.md
   f. THEN exit
-->

# Stage 9: Validation Execution

**Status:** Pending
**Dependencies:** Stage 8
**Estimated Tests:** ~20
**REQUIRES MTIB ACCESS (office network)**

---

## Preconditions

- Queue entry ASSIGNED to fixture with MTIB node (from Stage 8)
- MTIB 10.4.45.33 reachable and healthy
- DUT Alpha B0 (SNR 0964) powered and responsive

---

## Test Files

### `e2e/stories/validation/execution.spec.ts` (~6 tests)

```
test('session transitions from PENDING to ACTIVE when tests begin')
test('session has correct fixture and build run references')
test('device record created with correct serial number')
test('test executions created for each test in suite')
test('session completes within expected timeout (stage-dependent)')
test('session final status is PASSED or FAILED with correct counts')
```

### `e2e/stories/validation/realtime.spec.ts` (~5 tests)

```
test('validation run detail page shows real-time test timeline')
test('new test cards appear in timeline as tests start (DOM mutation)')
test('test cards update to passed/failed with duration and measurements')
test('run header shows final summary when run completes')
test('progress bar updates as tests complete (observe DOM changes)')
```

**WebSocket Testing Strategy:** Playwright cannot natively subscribe to Socket.IO events. Instead, observe DOM mutations caused by WebSocket events:
- Test timeline cards appearing (`.test-card` elements)
- Status badges changing (`.status-badge` class updates)
- Progress bar width changes
- Use `page.waitForSelector()` and `page.locator().waitFor()` to detect changes.
- For assertions on specific values, use `page.evaluate()` to read the app's reactive state.

### `e2e/stories/validation/results.spec.ts` (~5 tests)

```
test('completed session shows all test results')
test('each test result has status, duration, and measurements')
test('failed tests show error message')
test('session summary shows correct passed/failed/skipped counts')
test('session appears in validation runs list with correct status badge')
```

### `e2e/stories/validation/run-detail.spec.ts` (~4 tests)

```
test('run detail page shows header with status and duration')
test('test list shows expandable test details')
test('UART panel shows device output (if telemetry enabled)')
test('session artifacts downloadable after completion')
```

---

## Hardware Interaction Flow

```
E2E Test (Playwright)
    │
    ├─→ Monitors UI (validation run detail page)
    │     └─→ WebSocket events update test timeline
    │
    └─→ Verifies via API:
          ├─→ Session status transitions
          ├─→ TestExecution records created
          ├─→ TestStep records with measurements
          └─→ Fixture status (LOCKED → AVAILABLE)

Meanwhile (in K8s or local):
    Validation Runner Pod
        │
        ├─→ Connects to MTIB 10.4.45.33:50053 (gRPC)
        │     ├─→ PowerEnable(ch0=4.5V)
        │     ├─→ GpioConfig(0,1 = OUTPUT LOW)
        │     ├─→ UartStream (capture boot output)
        │     └─→ PowerRead (verify >5mA)
        │
        ├─→ Runs pytest test suite
        │
        └─→ Reports results via HTTP callbacks
              └─→ POST /v2/sessions/{id}/report/test-result
```

**Note:** The E2E test does NOT directly interact with the MTIB. It observes the validation runner's work through the Concord API and WebSocket events. The MTIB interaction happens inside the validation runner pod/process.

---

## Timing Considerations

- **Session startup:** 30-60s (K8s job scheduling + pod startup)
- **Test execution:** Varies by stage (1 min for smoke, 15+ min for FUOTA)
- **Total wait:** Up to 30 min for a single validation run

Tests use `waitForSessionComplete()` with stage-appropriate timeouts.

---

## Gate Criteria

- [ ] Validation session runs on real MTIB hardware
- [ ] Real-time WebSocket events appear in UI
- [ ] Test results match expected pass/fail counts
- [ ] Fixture correctly locked during run, released after
- [ ] Session artifacts available after completion
- [ ] All 20 tests pass
