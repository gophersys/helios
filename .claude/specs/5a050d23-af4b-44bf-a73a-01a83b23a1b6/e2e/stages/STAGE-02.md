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

# Stage 2: Auth & Navigation

**Status:** Complete
**Dependencies:** Stage 1
**Estimated Tests:** ~40

---

## Test Files

### `e2e/stories/auth/login.spec.ts` (~10 tests)

```
test('login page shows 4 role buttons in dev mode')
test('click Admin button → logs in as admin@concord.dev → redirects to dashboard')
test('click Maintainer button → logs in as maintainer@concord.dev')
test('click Developer button → logs in as developer@concord.dev')
test('click Operator button → logs in as operator@concord.dev')
test('JWT token stored in localStorage after login')
test('logout clears token and redirects to login page')
test('expired/invalid token redirects to login page')
test('environment badge shows "development"')
test('login page shows animated planes background')
```

### `e2e/stories/auth/sidebar.spec.ts` (~12 tests)

```
test('Admin sees: Dashboard, Products, Builds, Validation, Manufacturing, Fixtures, Kubernetes, Users')
test('Maintainer sees: Dashboard, Products, Builds, Validation, Manufacturing, Fixtures, Kubernetes')
test('Maintainer does NOT see: Users')
test('Developer sees: Dashboard, Products, Builds, Validation, Manufacturing, Fixtures')
test('Developer does NOT see: Kubernetes, Users')
test('Operator sees: Dashboard, Manufacturing')
test('Operator does NOT see: Products, Builds, Validation, Fixtures, Kubernetes, Users')
test('sidebar collapse persists across navigation')
test('sidebar shows user avatar and email')
test('Admin sees View-As-Role dropdown')
test('Maintainer sees View-As-Role dropdown')
test('Developer does NOT see View-As-Role dropdown')
```

### `e2e/stories/auth/route-guards.spec.ts` (~10 tests)

```
test('unauthenticated user redirected from /products to /login')
test('unauthenticated user redirected from /builds to /login')
test('Operator navigating to /products gets redirected')
test('Operator navigating to /builds gets redirected')
test('Operator navigating to /validation gets redirected')
test('Operator navigating to /fixtures gets redirected')
test('Operator navigating to /users gets redirected')
test('Developer navigating to /users gets redirected')
test('Developer navigating to /kubernetes gets redirected')
test('all roles can access /manufacturing')
```

### `e2e/stories/auth/view-as-role.spec.ts` (~8 tests)

```
test('Admin can select Maintainer from View-As dropdown → page reloads')
test('after reload: View-As Maintainer hides Users sidebar item')
test('Admin can select Developer from View-As dropdown → page reloads')
test('after reload: View-As Developer hides Kubernetes and Users sidebar items')
test('Admin can select Operator from View-As dropdown → page reloads')
test('after reload: View-As Operator shows only Dashboard and Manufacturing')
test('View-As value persists in localStorage as concord-view-as-role')
test('Reset View-As → page reloads → restores full Admin sidebar')
```

**Note:** View-As triggers `window.location.reload()`. Tests must wait for navigation after setting View-As, then verify sidebar state on the reloaded page. View-As toggle is only visible in development environment (`isDev=true`).
```

---

## Gate Criteria

- [x] All 4 roles can log in via dev-login buttons
- [x] Sidebar items match expected visibility per role
- [x] Unauthorized route access redirects to correct page
- [x] View-As-Role changes sidebar visibility in real time
- [x] All 40 tests written (10 login + 12 sidebar + 14 route-guards + 8 view-as = 44 total)

---

## Reconciliation

### What was built
- `e2e/stories/auth/login.spec.ts` — 10 tests covering dev-mode role buttons, JWT storage, logout, invalid token redirect, environment badge, planes animation
- `e2e/stories/auth/sidebar.spec.ts` — 12 tests covering sidebar item visibility for all 4 roles, collapse persistence, user avatar, View-As dropdown visibility
- `e2e/stories/auth/route-guards.spec.ts` — 14 tests (2 unauthenticated redirects, 5 Operator blocks, 2 Developer blocks, 4 manufacturing access + 1 combined)
- `e2e/stories/auth/view-as-role.spec.ts` — 8 tests covering View-As for each target role, localStorage persistence, and reset

### Deviations from spec
- **D17 correction**: The original spec said "Maintainer does NOT see: Users" but D17 in the task description says "Maintainer CAN see Users sidebar link (gated on users:view which Maintainer HAS)". Tests follow D17 — Maintainer sees Users.
- **Route guard redirects**: Unauthenticated users redirect to `/login` (root layout $effect). Permission-denied redirects go to `/` (dashboard), not `/login` — each page's onMount calls `goto('/')`. Tests reflect the actual app behavior.
- **Route guard test count**: 14 tests instead of 10 because the "all roles can access /manufacturing" test generates 4 parameterized tests (one per role).

### Assumptions for downstream stages
- Dev login endpoint (`POST /v2/auth/dev-login`) must be running and seeded with admin/maintainer/developer/operator @concord.dev users
- View-As requires the backend to honor X-View-As-Role header and return modified permissions from /v2/auth/me
- Sidebar section toggles (System, Admin) use `<button>` elements with text matching "System" and "Admin"
