# DEVELOPER User Story — Deep Specification

**Role level:** 2 (of 4)
**Permission count:** 12 (of 24 total)
**Login:** Click "Developer" card on dev-login page -> `POST /v2/auth/dev-login` with `developer@concord.dev`

---

## Permission Inventory

**HAS (12):**
products:view, builds:view, builds:trigger, builds:manage,
validation:view, validation:run,
manufacturing:view,
fixtures:view, devices:view,
api-keys:view, api-keys:manage

**DOES NOT HAVE (12):**
products:manage, validation:manage, manufacturing:run, manufacturing:manage,
fixtures:manage, devices:manage, kubernetes:view, kubernetes:manage,
users:view, users:manage, permissions:manage, system:view, system:manage

---

## Sidebar Visibility

Source: `sidebar.svelte` lines 71-103

| Section | Visible | Gate Permission | Sidebar Group |
|---------|---------|-----------------|---------------|
| Dashboard | Yes | (none — always visible) | Primary nav |
| Products | Yes | `products:view` | Primary nav |
| Builds | Yes | `builds:view` | Primary nav |
| Validation | Yes | `validation:view` | Primary nav |
| Manufacturing | Yes | `manufacturing:view` | Primary nav |
| Fixtures | Yes | `fixtures:view` | Primary nav |
| Kubernetes | **No** | `system:view` (line 96) — Developer lacks this | System section |
| Users | **No** | `users:view` (line 85) — Developer lacks this | Admin section |
| View-As toggle | **No** | `canViewAs` = false (auth.svelte.ts line 39: only ADMIN/MAINTAINER) | Footer |
| Settings | Yes | (none — always visible) | Footer |

**Key facts:**
- `hasSystem` (line 103) = false -> System section toggle button hidden entirely
- `hasAdmin` (line 92) = false -> Admin section toggle button hidden entirely
- View-As requires `canViewAs` which checks `role === 'ADMIN' || role === 'MAINTAINER'` -> false for Developer

**Playwright assertions:**
```
- expect(page.getByRole('link', { name: 'Products' })).toBeVisible()
- expect(page.getByRole('link', { name: 'Builds' })).toBeVisible()
- expect(page.getByRole('link', { name: 'Validation' })).toBeVisible()
- expect(page.getByRole('link', { name: 'Manufacturing' })).toBeVisible()
- expect(page.getByRole('link', { name: 'Fixtures' })).toBeVisible()
- expect(page.getByText('System')).not.toBeVisible()   // toggle button hidden
- expect(page.getByText('Admin')).not.toBeVisible()     // toggle button hidden
- expect(page.getByText('View as')).not.toBeVisible()   // View-As hidden
```

---

## PHASE 1: LOGIN AND NAVIGATION VERIFICATION

### Step 1.1 — Login as Developer
- **Action:** Navigate to `/login`. Wait for dev-user cards to load. Click card labeled "Developer".
- **UI State:** Page redirects to `/` (dashboard). Sidebar shows user avatar with first initial, name, and "Developer" permission set label.
- **Backend:** `POST /v2/auth/dev-login` body `{"email":"developer@concord.dev"}` -> 200 with JWT. `GET /v2/auth/me` returns `role: "DEVELOPER"`, permissions array with 12 entries.
- **Assertion:** `auth.user.role === 'DEVELOPER'`, `auth.user.permissions.length === 12`.

### Step 1.2 — Verify sidebar: 6 primary items, no System, no Admin, no View-As
- **Action:** Observe sidebar completely. Scroll footer area.
- **UI State:** Dashboard + 5 primary items (Products, Builds, Validation, Manufacturing, Fixtures). Settings gear visible. NO "System" toggle. NO "Admin" toggle. NO "View as..." button.
- **Assertion:** Exactly 6 nav links total (Dashboard + 5 primary). No expandable sections in footer.

### Step 1.3 — Verify View-As is NOT available
- **Action:** Inspect footer area of sidebar.
- **UI State:** Between Settings button and user info, there is NO "View as..." button.
- **Assertion:** `page.getByText('View as').not.toBeVisible()`.

---

## PHASE 2: PRODUCTS — VIEW ONLY (products:view YES, products:manage NO)

### Step 2.1 — View product list
- **Action:** Click "Products" in sidebar.
- **UI State:** Products list page loads. Product cards/rows visible (if data exists from Admin story).
- **Backend:** `GET /v2/products` with `products:view` -> 200.
- **Assertion:** Page renders without error.

### Step 2.2 — Verify "Create Product" button is HIDDEN
- **Action:** Look for any create/add button on Products page.
- **UI State:** `canManage` (products/+page.svelte line 16) = `auth.hasPermission('products:manage')` = false. Create button is not rendered.
- **Assertion:** `page.getByRole('button', { name: /create product/i }).not.toBeVisible()`.

### Step 2.3 — View product detail
- **Action:** Click on a product in the list to navigate to `/products/[id]`.
- **UI State:** Product detail page loads with 5 tabs. All tabs render in read-only mode. No edit buttons visible.
- **Backend:** `GET /v2/products/<id>` with `products:view` -> 200.
- **Assertion:** Detail page renders. All 5 tabs clickable and display data.

### Step 2.4 — Verify edit controls are HIDDEN on detail page
- **Action:** On product detail page, look for edit/pencil icon, delete button, inline edit fields.
- **UI State:** `canManage` (products/[id]/+page.svelte line 14) = false. Edit and delete controls not rendered.
- **Assertion:** No edit icon, no delete button visible on detail page.

### Step 2.5 — API boundary: products:manage returns 403
- **API:** `POST /v2/products` body `{"name":"test"}` -> 403
- **API:** `PATCH /v2/products/<id>` body `{"name":"changed"}` -> 403
- **API:** `DELETE /v2/products/<id>` -> 403
- **API:** `POST /v2/products/<id>/boards` -> 403
- **API:** `PATCH /v2/products/<id>/boards/<bid>` -> 403
- **API:** `DELETE /v2/products/<id>/boards/<bid>` -> 403
- **API:** `POST /v2/products/<id>/boards/<bid>/revisions` -> 403
- **API:** `PATCH /v2/products/<id>/boards/<bid>/revisions/<rid>` -> 403
- **Assertion:** All return 403 with permission error message.

### Step 2.6 — Verify board discovery endpoints ARE accessible (view-gated)
- **API:** `GET /v2/products/discovery/branches` -> 200 (products:view)
- **API:** `GET /v2/products/discovery/boards?branch=main` -> 200 (products:view)
- **Assertion:** Discovery APIs work (used in wizard read-only context).

---

## PHASE 3: BUILDS — FULL ACCESS (builds:view, builds:trigger, builds:manage)

### Step 3.1 — View build list
- **Action:** Click "Builds" in sidebar.
- **UI State:** Builds list page loads with filters (product, status, branch).
- **Backend:** `GET /v2/builds` with `builds:view` -> 200.
- **Assertion:** Build list renders.

### Step 3.2 — Trigger manual build
- **Action:** Click "Trigger Build" button. Select product, branch. Submit.
- **UI State:** Trigger button IS visible (Developer has `builds:trigger`). Dialog opens. Build created.
- **Backend:** `POST /v2/builds/trigger` with `builds:trigger` -> 201.
- **Assertion:** New build run appears in list.

### Step 3.3 — View build detail
- **Action:** Click on build run to view detail.
- **UI State:** Build detail page: job matrix, status badges, log viewer, artifacts.
- **Backend:** `GET /v2/builds/runs/<id>` with `builds:view` -> 200.
- **Assertion:** All detail sections render.

### Step 3.4 — Download artifact
- **Action:** Click download button on a completed build artifact.
- **Backend:** `GET /v2/builds/runs/<id>/artifacts/<aid>/download` with `builds:view` -> 200 (presigned URL).
- **Assertion:** Download initiates.

### Step 3.5 — Cancel build (builds:manage)
- **Action:** On a running build, click "Cancel" button.
- **Backend:** `POST /v2/builds/runs/<id>/cancel` with `builds:manage` -> 200.
- **Assertion:** Build transitions to CANCELLED.

### Step 3.6 — Manage stage config and recipes (builds:manage)
- **Action:** Edit stage configuration, modify build recipe.
- **Backend:** `PATCH /v2/builds/stage-config/<id>` with `builds:manage` -> 200.
- **Assertion:** Configuration changes persist.

### Step 3.7 — Webhook management (builds:trigger)
- **Backend:** `POST /v2/builds/webhooks/test` with `builds:trigger` -> 200.
- **Assertion:** Webhook test succeeds.

---

## PHASE 4: VALIDATION — RUN BUT NOT MANAGE (validation:view, validation:run YES; validation:manage NO)

### Step 4.1 — View validation hub
- **Action:** Click "Validation" in sidebar.
- **UI State:** Validation hub loads. Queue visible. Recent runs visible. Manage buttons (reorder queue, cancel entry, retry) should be HIDDEN because `canManage` = false (validation/+page.svelte line 41).
- **Backend:** `GET /v2/sessions/queue` with `validation:view` -> 200.
- **Assertion:** Queue data renders. No manage action buttons visible.

### Step 4.2 — Trigger validation run (validation:run — ALLOWED)
- **Action:** Click "Run Validation" or equivalent button (this should be visible with `validation:run`).
- **Backend:** `POST /v2/sessions/runs` with `validation:run` -> 201.
- **Assertion:** New run created. Run appears in list.

### Step 4.3 — View run detail
- **Action:** Click into a validation run.
- **UI State:** Full run detail page: tests, power chart, UART panel, stage sidebar.
- **Backend:** `GET /v2/sessions/runs/<id>` with `validation:view` -> 200.
- **Assertion:** All detail panels render.

### Step 4.4 — Rerun a session (validation:run — ALLOWED)
- **Backend:** `POST /v2/sessions/runs/<id>/rerun` with `validation:run` -> 201.
- **Assertion:** New run created from previous run's config.

### Step 4.5 — View test executions and artifacts
- **Backend:** `GET /v2/sessions/runs/<id>/executions` with `validation:view` -> 200.
- **Backend:** `GET /v2/sessions/runs/<id>/artifacts` with `validation:view` -> 200.
- **Assertion:** Data returned for both.

### Step 4.6 — Verify manage controls are HIDDEN
- **Action:** On validation hub, look for queue management controls (reorder, cancel entry, priority change).
- **UI State:** `canManage` = false. Queue management buttons not rendered.
- **Assertion:** No "Cancel", "Retry", "Reorder" buttons on queue entries.

### Step 4.7 — Verify validation designs page is view-only
- **Action:** Navigate to Validation > Designs.
- **UI State:** Design list loads. canManage = false (validation/designs/+page.svelte line 33). No create/edit/delete buttons.
- **Assertion:** `page.getByRole('button', { name: /create design/i }).not.toBeVisible()`.

### Step 4.8 — API boundary: validation:manage returns 403
- **API:** `PATCH /v2/sessions/queue/<id>` (reorder) -> 403
- **API:** `POST /v2/sessions/queue/<id>/cancel` -> 403
- **API:** `POST /v2/sessions/queue/<id>/retry` -> 403
- **API:** `DELETE /v2/sessions/runs/<id>` -> 403
- **API:** Queue priority update endpoints -> 403
- **Assertion:** All return 403.

---

## PHASE 5: FIXTURES — VIEW ONLY (fixtures:view YES, fixtures:manage NO)

### Step 5.1 — View fixture list
- **Action:** Click "Fixtures" in sidebar.
- **UI State:** Fixtures page loads with tabs (Fixtures, Designs). Data renders.
- **Backend:** `GET /v2/fixtures` with `fixtures:view` -> 200.
- **Assertion:** Fixture list renders.

### Step 5.2 — View fixture detail
- **Action:** Click on a fixture to view detail.
- **UI State:** Detail page: slot assignments, node info, status. All read-only.
- **Backend:** `GET /v2/fixtures/<id>` with `fixtures:view` -> 200.
- **Assertion:** Detail renders. No edit/manage buttons visible.

### Step 5.3 — Verify create/manage buttons are HIDDEN
- **Action:** Look for "Create Fixture", "Create Design", edit icons, delete buttons.
- **UI State:** `canManage` (fixtures/+page.svelte line 16) = false. All manage controls hidden.
- **Assertion:** No create buttons. No edit icons. No delete buttons.

### Step 5.4 — API boundary: fixtures:manage returns 403
- **API:** `POST /v2/fixtures` -> 403
- **API:** `PATCH /v2/fixtures/<id>` -> 403
- **API:** `DELETE /v2/fixtures/<id>` -> 403
- **API:** `POST /v2/fixtures/designs` -> 403
- **API:** `PATCH /v2/fixtures/designs/<id>` -> 403
- **API:** `DELETE /v2/fixtures/designs/<id>` -> 403
- **API:** `POST /v2/fixtures/<id>/slots/<slotId>/assign` -> 403
- **API:** `POST /v2/fixtures/<id>/slots/<slotId>/unassign` -> 403
- **Assertion:** All return 403.

### Step 5.5 — API boundary: devices:manage returns 403
- **API:** `POST /v2/nodes` -> 403
- **API:** `PATCH /v2/nodes/<id>` -> 403
- **API:** `DELETE /v2/nodes/<id>` -> 403
- **API:** `POST /v2/nodes/<id>/deploy` -> 403
- **Assertion:** All return 403. Developer CAN `GET /v2/nodes` (devices:view).

### Step 5.6 — Confirm devices:view works
- **API:** `GET /v2/nodes` -> 200.
- **API:** `GET /v2/nodes/<id>` -> 200.
- **Assertion:** Node data returned read-only.

---

## PHASE 6: MANUFACTURING — VIEW ONLY (manufacturing:view YES; manufacturing:run, manufacturing:manage NO)

### Step 6.1 — View manufacturing page
- **Action:** Click "Manufacturing" in sidebar.
- **UI State:** Manufacturing page loads. Fixture list visible. Session history visible.
- **Backend:** `GET /v2/manufacturing/fixtures` with `manufacturing:view` -> 200.
- **Assertion:** Page renders.

### Step 6.2 — Verify "New Session" button is HIDDEN
- **Action:** Look for session creation controls.
- **UI State:** No "New Session" button (requires `manufacturing:run`).
- **Assertion:** `page.getByRole('button', { name: /new session/i }).not.toBeVisible()`.

### Step 6.3 — View session detail (if sessions exist)
- **Action:** Click on a session in the list.
- **UI State:** Session detail loads read-only. No "Run Panel" or "End Session" buttons.
- **Backend:** `GET /v2/manufacturing/sessions/<id>` with `manufacturing:view` -> 200.
- **Assertion:** Detail page renders. No action buttons.

### Step 6.4 — API boundary: manufacturing:run returns 403
- **API:** `POST /v2/manufacturing/sessions` -> 403
- **API:** `POST /v2/manufacturing/sessions/<id>/panels` -> 403
- **Assertion:** Both return 403.

### Step 6.5 — API boundary: manufacturing:manage returns 403
- **API:** `POST /v2/manufacturing/sessions/<id>/end` -> 403
- **Assertion:** Returns 403.

---

## PHASE 7: API KEYS (api-keys:view, api-keys:manage — ALLOWED)

### Step 7.1 — Create API key
- **Action:** Navigate to API key section (Settings page or profile).
- **UI State:** API key management visible. "Create Key" button available.
- **Backend:** `POST /v2/auth/api-keys` body `{"name":"dev-test-key"}` with `api-keys:manage` -> 201.
- **Assertion:** Key created. Plaintext shown once. Copy button works.

### Step 7.2 — List API keys
- **Backend:** `GET /v2/auth/api-keys` with `api-keys:view` -> 200.
- **Assertion:** Key list shows name, prefix (e.g., `ck_run_...`), created date. Full key NOT shown.

### Step 7.3 — Revoke API key
- **Action:** Click delete/revoke on the created key.
- **Backend:** `DELETE /v2/auth/api-keys/<id>` with `api-keys:manage` -> 200.
- **Assertion:** Key removed from list.

---

## PHASE 8: BLOCKED NAVIGATION — DIRECT URL ACCESS

### Step 8.1 — Navigate directly to /users
- **Action:** Type `/users` in browser URL bar.
- **UI State:** Page either redirects to `/` (dashboard) via `onMount` permission check, or shows a 403/unauthorized message.
- **Assertion:** User does NOT see the Users management page. Either redirected or error shown.

### Step 8.2 — Navigate directly to /kubernetes
- **Action:** Type `/kubernetes` in browser URL bar.
- **UI State:** Page either redirects or shows unauthorized. Developer lacks `system:view` which gates the Kubernetes sidebar item AND likely the page's `onMount` check.
- **Assertion:** Kubernetes page not accessible.

### Step 8.3 — Navigate directly to /validation/designs (view works, but manage hidden)
- **Action:** Type `/validation/designs` in browser URL bar.
- **UI State:** Page loads (Developer has `validation:view`). But all manage controls hidden.
- **Assertion:** Page renders read-only. No create/edit/delete actions available.

---

## PHASE 9: COMPREHENSIVE PERMISSION BOUNDARY MATRIX

### Operations that MUST succeed (200/201):

| Operation | Endpoint | Permission |
|-----------|----------|------------|
| List products | `GET /v2/products` | products:view |
| Get product detail | `GET /v2/products/<id>` | products:view |
| Board discovery | `GET /v2/products/discovery/branches` | products:view |
| List builds | `GET /v2/builds` | builds:view |
| Get build detail | `GET /v2/builds/runs/<id>` | builds:view |
| Trigger build | `POST /v2/builds/trigger` | builds:trigger |
| Cancel build | `POST /v2/builds/runs/<id>/cancel` | builds:manage |
| Manage stage config | `PATCH /v2/builds/stage-config/<id>` | builds:manage |
| Manage recipes | `PUT /v2/builds/recipes/<id>` | builds:manage |
| List queue | `GET /v2/sessions/queue` | validation:view |
| Get run detail | `GET /v2/sessions/runs/<id>` | validation:view |
| Run validation | `POST /v2/sessions/runs` | validation:run |
| Rerun session | `POST /v2/sessions/runs/<id>/rerun` | validation:run |
| View telemetry | `GET /v2/sessions/telemetry/<id>` | validation:view |
| List mfg fixtures | `GET /v2/manufacturing/fixtures` | manufacturing:view |
| List fixtures | `GET /v2/fixtures` | fixtures:view |
| Get fixture detail | `GET /v2/fixtures/<id>` | fixtures:view |
| List designs | `GET /v2/fixtures/designs` | fixtures:view |
| List nodes | `GET /v2/nodes` | devices:view |
| Get node detail | `GET /v2/nodes/<id>` | devices:view |
| List API keys | `GET /v2/auth/api-keys` | api-keys:view |
| Create API key | `POST /v2/auth/api-keys` | api-keys:manage |
| Delete API key | `DELETE /v2/auth/api-keys/<id>` | api-keys:manage |

### Operations that MUST return 403:

| Operation | Endpoint | Missing Permission |
|-----------|----------|--------------------|
| Create product | `POST /v2/products` | products:manage |
| Update product | `PATCH /v2/products/<id>` | products:manage |
| Delete product | `DELETE /v2/products/<id>` | products:manage |
| Create board | `POST /v2/products/<id>/boards` | products:manage |
| Update board | `PATCH /v2/products/<id>/boards/<bid>` | products:manage |
| Create board revision | `POST /v2/products/<id>/boards/<bid>/revisions` | products:manage |
| Update board revision | `PATCH /v2/products/<id>/boards/<bid>/revisions/<rid>` | products:manage |
| Create test package | `POST /v2/products/<id>/test-packages` | validation:manage |
| Reorder queue | `PATCH /v2/sessions/queue/<id>` | validation:manage |
| Cancel queue entry | `POST /v2/sessions/queue/<id>/cancel` | validation:manage |
| Retry queue entry | `POST /v2/sessions/queue/<id>/retry` | validation:manage |
| Delete run | `DELETE /v2/sessions/runs/<id>` | validation:manage |
| Start mfg session | `POST /v2/manufacturing/sessions` | manufacturing:run |
| Run mfg panel | `POST /v2/manufacturing/sessions/<id>/panels` | manufacturing:run |
| End mfg session | `POST /v2/manufacturing/sessions/<id>/end` | manufacturing:manage |
| Create fixture | `POST /v2/fixtures` | fixtures:manage |
| Update fixture | `PATCH /v2/fixtures/<id>` | fixtures:manage |
| Delete fixture | `DELETE /v2/fixtures/<id>` | fixtures:manage |
| Create design | `POST /v2/fixtures/designs` | fixtures:manage |
| Update design | `PATCH /v2/fixtures/designs/<id>` | fixtures:manage |
| Delete design | `DELETE /v2/fixtures/designs/<id>` | fixtures:manage |
| Assign slot | `POST /v2/fixtures/<id>/slots/<s>/assign` | fixtures:manage |
| Unassign slot | `POST /v2/fixtures/<id>/slots/<s>/unassign` | fixtures:manage |
| Create node | `POST /v2/nodes` | devices:manage |
| Update node | `PATCH /v2/nodes/<id>` | devices:manage |
| Delete node | `DELETE /v2/nodes/<id>` | devices:manage |
| Deploy node | `POST /v2/nodes/<id>/deploy` | devices:manage |
| View K8s cluster | `GET /v2/kubernetes/cluster` | kubernetes:view |
| View K8s pods | `GET /v2/kubernetes/pods` | kubernetes:view |
| Scale deployment | `POST /v2/kubernetes/deployments/<n>/scale` | kubernetes:manage |
| List users | `GET /v2/auth/users` | users:view |
| Create user | `POST /v2/auth/users` | users:manage |
| List perm sets | `GET /v2/auth/permission-sets` | users:view |
| Create perm set | `POST /v2/auth/permission-sets` | permissions:manage |
| View system info | `GET /v2/system/info` | system:view |
| View audit log | `GET /v2/system/history` | system:view |
| Create secret | `POST /v2/system/secrets` | system:manage |
| ICLE device config | `POST /v2/icle/config` | devices:manage |
| ICLE OTA | `POST /v2/icle/ota` | devices:manage |

---

## PHASE 10: CLEANUP

### Step 10.1 — Delete created API keys
- **Backend:** `DELETE /v2/auth/api-keys/<id>` for each key created during test.
- **Assertion:** Keys removed.

### Step 10.2 — Verify no other resources to clean
- Developer cannot create products, fixtures, nodes, users, or manufacturing sessions. The only resources a Developer can create are: API keys, build runs (via trigger), and validation runs (via run).
- Build runs and validation runs are cleaned up as part of product deletion in the Admin story.
- **Assertion:** No orphaned resources.

---

## Appendix: UI Element Visibility Summary

| Page | Element | Visible? | Reason |
|------|---------|----------|--------|
| `/products` | "Create Product" button | No | `products:manage` missing |
| `/products/[id]` | Edit icon | No | `products:manage` missing |
| `/products/[id]` | Delete button | No | `products:manage` missing |
| `/builds` | "Trigger Build" button | Yes | `builds:trigger` present |
| `/builds/runs/[id]` | "Cancel" button | Yes | `builds:manage` present |
| `/validation` | Manage queue controls | No | `validation:manage` missing |
| `/validation` | "Run Validation" button | Yes | `validation:run` present |
| `/validation/designs` | "Create Design" button | No | `validation:manage` missing |
| `/validation/queue` | Reorder/cancel/retry | No | `validation:manage` missing |
| `/manufacturing` | "New Session" button | No | `manufacturing:run` missing |
| `/fixtures` | "Create Fixture" button | No | `fixtures:manage` missing |
| `/fixtures` | "Create Design" button | No | `fixtures:manage` missing |
| Sidebar | System section toggle | No | `system:view` missing |
| Sidebar | Admin section toggle | No | `users:view` missing |
| Sidebar | View-As button | No | `canViewAs` = false |
