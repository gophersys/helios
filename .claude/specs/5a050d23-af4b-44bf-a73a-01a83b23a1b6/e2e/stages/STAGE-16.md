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

# Stage 16: Cleanup & Orchestration

**Status:** Pending
**Dependencies:** All stages 1-15
**Estimated Tests:** ~18

---

## Same as previous Stage 13, updated for 16 stages.

### Test Files

#### `e2e/stories/cleanup/bitbucket.spec.ts` (~4 tests)
#### `e2e/stories/cleanup/corecloud.spec.ts` (~3 tests)
#### `e2e/stories/cleanup/database.spec.ts` (~7 tests)

Updated to include manufacturing models:
```
test('zero ManufacturingConfig records')
test('zero ManufacturingSessions')
test('zero ManufacturingPanels and ManufacturingUnits')
```

#### `e2e/stories/cleanup/minio.spec.ts` (~4 tests)

---

## Expected Total Duration (Updated)

| Phase | Duration |
|-------|----------|
| Global setup | 1-2 min |
| Auth & Navigation | 2-3 min |
| Product CRUD | 3-5 min |
| Stage Configuration | 5-8 min |
| Bitbucket Integration | 1-2 min |
| Build Pipeline | 20-40 min |
| Fixture & MTIB Fixes | 3-5 min |
| Validation Queue | 2-3 min |
| Validation Execution | 15-30 min |
| Manufacturing E2E | 15-25 min |
| User Management | 3-5 min |
| Role Stories (Admin) | 60-90 min |
| Role Stories (Maintainer) | 30-50 min |
| Role Stories (Developer) | 5-10 min |
| Role Stories (Operator) | 15-25 min |
| Cleanup | 2-3 min |
| **TOTAL** | **~3-5 hours** |

---

## Gate Criteria

- [ ] Global setup creates clean environment
- [ ] All 16 stages execute in correct order
- [ ] Manufacturing models cleaned up
- [ ] System returns to zero-data state
- [ ] All 18 tests pass
