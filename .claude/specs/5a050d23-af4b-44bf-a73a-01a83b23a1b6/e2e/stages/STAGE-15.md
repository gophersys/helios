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

# Stage 15: Role Stories

**Status:** Pending
**Dependencies:** All stages 1-14
**Estimated Tests:** ~80

---

## Overview

4 complete user stories. Same structure as previous Stage 12, but updated to include manufacturing.

### `e2e/stories/roles/admin.spec.ts` (~25 tests)

Full Admin journey now includes:
- All original phases (product, builds, validation, fixtures, users)
- PLUS: Configure manufacturing for product
- PLUS: Create manufacturing fixture
- PLUS: Verify Operator can run manufacturing sessions

### `e2e/stories/roles/maintainer.spec.ts` (~20 tests)

Same as before plus:
- Can configure manufacturing (manufacturing:manage via product page)
- Can create manufacturing fixtures
- Cannot manage users/system/k8s

### `e2e/stories/roles/developer.spec.ts` (~20 tests)

Same as before — Developer has NO manufacturing:run, so:
- Can view manufacturing page
- CANNOT start manufacturing sessions
- CANNOT configure manufacturing

### `e2e/stories/roles/operator.spec.ts` (~15 tests)

Updated Operator story:
- Login → Dashboard + Manufacturing visible ONLY
- Navigate to Manufacturing → see fixtures
- Start manufacturing session
- Scan QR code, run panels
- View per-unit results
- End session
- View session history
- ALL other pages blocked (products, builds, validation, fixtures, users, k8s)
- Has manufacturing:manage + manufacturing:run + manufacturing:view
- Does NOT have products:view → cannot access product config page

---

## Gate Criteria

- [ ] Admin completes full system journey including manufacturing config
- [ ] Maintainer manages manufacturing config and fixtures
- [ ] Developer views manufacturing but cannot operate
- [ ] Operator runs complete manufacturing workflow (session → panels → results)
- [ ] Every permission denial verified in UI and API
- [ ] All 80 tests pass
