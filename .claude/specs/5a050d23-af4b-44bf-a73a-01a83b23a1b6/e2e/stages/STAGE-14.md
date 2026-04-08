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

# Stage 14: User Management

**Status:** Pending
**Dependencies:** Stage 2
**Estimated Tests:** ~30

(Same content as previous Stage 11 — User CRUD, permission sets, API keys, role assignment. See STAGE-11.md prior revision for full test list.)

---

## Test Files

### `e2e/stories/users/user-crud.spec.ts` (~10 tests)
### `e2e/stories/users/permission-sets.spec.ts` (~8 tests)
### `e2e/stories/users/api-keys.spec.ts` (~7 tests)
### `e2e/stories/users/role-assignment.spec.ts` (~5 tests)

(Test cases unchanged from original spec — see git history for full details.)

---

## Gate Criteria

- [ ] User CRUD works through UI
- [ ] Permission set CRUD works with correct constraints
- [ ] API key lifecycle works (create once, view prefix, revoke)
- [ ] Role changes affect sidebar visibility and API access
- [ ] Product-level access control works
- [ ] All 30 tests pass
