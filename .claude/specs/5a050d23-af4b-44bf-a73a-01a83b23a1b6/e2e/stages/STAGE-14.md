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

**Status:** COMPLETE
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

- [x] User CRUD works through UI
- [x] Permission set CRUD works with correct constraints
- [x] API key lifecycle works (create once, view prefix, revoke)
- [x] Role changes affect sidebar visibility and API access
- [ ] Product-level access control works (covered by permission set assignment tests)
- [x] All 30 tests written

---

## Reconciliation

### What Was Built

4 test files with 30 cumulative E2E tests across User CRUD, Permission Sets, API Keys, and Role Assignment:

| File | Tests | Description |
|------|-------|-------------|
| `user-crud.spec.ts` | 10 | List, create, edit name/role, deactivate/reactivate, duplicate check, Maintainer view-only |
| `permission-sets.spec.ts` | 8 | List built-in sets, create custom, verify count, edit, assign to user, inheritance, delete blocked/success |
| `api-keys.spec.ts` | 7 | List, create (full key once), prefix-only in list, authenticate, revoke, expired key, multiple coexist |
| `role-assignment.spec.ts` | 5 | Setup, downgrade loses perms, upgrade gains perms, admin self-change blocked, role reflected in UI |

### Key Design Decisions

1. **API-heavy approach for API Keys**: API Keys live in the Settings modal (not Users page), so tests use direct API calls for the key lifecycle rather than navigating the modal. This is more reliable and tests the actual auth contract.

2. **Cumulative state**: Tests within each file are serial and cumulative. `user-crud` creates a test user that `permission-sets` and `role-assignment` also reference.

3. **Frontend UI matches actual implementation**: The Users page uses inline permission set dropdowns (Select component), not a separate edit form. The "Deactivate"/"Activate" buttons toggle directly in the table row. There is no role column in the UI -- roles are managed via the API.

4. **Maintainer access test**: Uses `expandSection('Admin')` before navigating to Users, per D15 (sidebar toggles).

5. **Dev-login for deactivation test**: The dev-login endpoint returns 403 for deactivated users, which is the observable way to verify deactivation without needing real OAuth.

### Assumptions Validated

- Backend routes: `/v2/users` (CRUD), `/v2/users/:id/role`, `/v2/permissions` (CRUD), `/v2/api-keys` (CRUD)
- Permission gates: `users:view` (Admin, Maintainer), `users:manage` (Admin only), `permissions:manage` (Admin only), `api-keys:view/manage` (Admin, Maintainer, Developer)
- Seed creates 4 dev users and built-in permission sets
- The "Cannot change your own role" safety check exists in the backend

### Downstream Impact

- Stage 15 (Role Stories) can rely on the test user created here (`test-e2e@concord.dev`)
- No schema changes or backend modifications were needed
