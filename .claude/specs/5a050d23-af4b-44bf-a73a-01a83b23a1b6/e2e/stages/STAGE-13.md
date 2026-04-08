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

# Stage 13: Manufacturing E2E Tests

**Status:** Pending
**Type:** TEST (Playwright E2E)
**Dependencies:** Stages 11, 12 (Manufacturing Frontend + Setup Wizard)
**Estimated Tests:** ~30
**REQUIRES MTIB ACCESS (office network)**

---

## Objective

Full Playwright E2E tests for the manufacturing workflow: configure product for manufacturing → create fixture → start session as Operator → scan QR → run panels → verify per-unit results → end session.

---

## Test Files

### `e2e/stories/manufacturing/setup.spec.ts` (~8 tests)

```
test('navigate to product detail → Manufacturing tab exists')
test('Manufacturing tab shows "not configured" initially')
test('open Manufacturing Config Wizard')
test('Step 1: select Alpha B0 board revision')
test('Step 2: configure stages (Electrical + Flash + POST)')
test('Step 2: select firmware source = latest build')
test('Step 3: set pass criteria')
test('Step 4: review and save → config created')
```

### `e2e/stories/manufacturing/fixture.spec.ts` (~6 tests)

```
test('create MANUFACTURING fixture design for Alpha B0')
test('create MANUFACTURING fixture instance')
test('assign MTIB node (10.4.45.33) to fixture slot')
test('fixture shows AVAILABLE on manufacturing page')
test('manufacturing fixtures page shows fixture card with "New Session"')
test('Operator can see manufacturing fixtures (manufacturing:view)')
```

### `e2e/stories/manufacturing/session.spec.ts` (~10 tests)

```
test('Operator clicks "New Session" on fixture → session created')
test('fixture status changes to LOCKED')
test('session runner page loads with QR input')
test('enter QR code "E2E-PANEL-001" in input field')
test('click "Run Panel" → panel created, unit cards appear')
test('unit cards show stage progress in real-time (Electrical → Flash → POST)')
test('unit cards update to PASSED/FAILED via WebSocket')
test('panel completes → summary shows pass/fail count')
test('run second panel with QR "E2E-PANEL-002"')
test('panel history shows first panel results')
```

### `e2e/stories/manufacturing/results.spec.ts` (~6 tests)

```
test('click "End Session" → confirmation dialog')
test('confirm → session status = COMPLETED')
test('fixture released (AVAILABLE)')
test('session appears in Sessions tab with panel count')
test('session detail shows all panels with per-unit results')
test('session results aggregation correct (total passed/failed across panels)')
```

---

## Operator-Specific Tests

These tests run as the Operator role:

```
test('Operator can access /manufacturing')
test('Operator sees "New Session" button (manufacturing:run)')
test('Operator can start session, run panels, end session')
test('Operator can view session results')
test('Operator CANNOT access manufacturing config wizard (no manufacturing:manage)')
```

Wait — Operator HAS `manufacturing:manage`. So:

```
test('Operator can access manufacturing config wizard (has manufacturing:manage)')
```

But Operator does NOT have `products:view` — so they can't navigate to the product detail page where the Manufacturing tab lives. The manufacturing config wizard must be accessible from the manufacturing page itself, or we need to rethink this flow.

**Design Decision:** Manufacturing configuration is done by Admin/Maintainer via the product detail page. The Operator only interacts with the `/manufacturing` page (fixtures + sessions). Even though Operator has `manufacturing:manage`, the config wizard is on the product page which requires `products:view`.

---

## Gate Criteria

- [ ] Manufacturing config wizard creates valid configuration
- [ ] Manufacturing fixture created and deployed
- [ ] Operator can start session, scan QR, run panels
- [ ] Real-time unit results via WebSocket
- [ ] Session end releases fixture
- [ ] Session history and results verification
- [ ] All 30 tests pass
