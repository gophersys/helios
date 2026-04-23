# MAINTAINER User Story — Deep Specification

**Role level:** 3 (of 4)
**Permission count:** 19 (of 24 total)
**Login:** Click "Maintainer" card on dev-login page -> `POST /v2/auth/dev-login` with `maintainer@concord.dev`

---

## Permission Inventory

**HAS (19):**
products:view, products:manage, builds:view, builds:trigger, builds:manage,
validation:view, validation:run, validation:manage,
manufacturing:view, manufacturing:run, manufacturing:manage,
fixtures:view, fixtures:manage, devices:view, devices:manage,
kubernetes:view, users:view, api-keys:view, api-keys:manage, system:view

**DOES NOT HAVE (5):**
users:manage, permissions:manage, kubernetes:manage, system:manage

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
| Kubernetes | Yes | `system:view` (line 96) | System section (expandable) |
| Users | Yes | `users:view` (line 85) | Admin section (expandable) |
| View-As toggle | Yes | `canViewAs` = true for MAINTAINER (auth.svelte.ts line 39) | Footer |
| Settings | Yes | (none — always visible) | Footer |

**Key finding:** The Admin section (Users link) IS visible to Maintainer because it gates on `users:view`, which Maintainer has. The SPEC section 4.3 says "Users: MAINT = -" but the actual sidebar code gates on `users:view`, not `users:manage`. Maintainer CAN see the Users link and navigate to `/users`.

**Playwright assertions:**
```
- expect(page.getByRole('link', { name: 'Products' })).toBeVisible()
- expect(page.getByRole('link', { name: 'Builds' })).toBeVisible()
- expect(page.getByRole('link', { name: 'Validation' })).toBeVisible()
- expect(page.getByRole('link', { name: 'Manufacturing' })).toBeVisible()
- expect(page.getByRole('link', { name: 'Fixtures' })).toBeVisible()
- Click "System" toggle -> expect Kubernetes link visible
- Click "Admin" toggle -> expect Users link visible
- expect View-As button visible (text "View as...")
```

---

## PHASE 1: LOGIN AND NAVIGATION VERIFICATION

### Step 1.1 — Login as Maintainer
- **Action:** Navigate to `/login`. Wait for dev-user cards to load. Click card labeled "Maintainer".
- **UI State:** Page redirects to `/` (dashboard). Sidebar shows user avatar with "M", name, and "Maintainer" permission set label.
- **Backend:** `POST /v2/auth/dev-login` body `{"email":"maintainer@concord.dev"}` -> 200 with JWT. `GET /v2/auth/me` returns `role: "MAINTAINER"`, permissions array with 19 entries.
- **Assertion:** `auth.user.role === 'MAINTAINER'`, `auth.user.permissions.length === 19`.

### Step 1.2 — Verify complete sidebar
- **Action:** Observe sidebar. Click "System" toggle in footer. Click "Admin" toggle in footer.
- **UI State:** All 6 primary nav items visible. Kubernetes link visible under System. Users link visible under Admin.
- **Assertion:** Count all nav links = 8 (Dashboard, Products, Builds, Validation, Manufacturing, Fixtures, Kubernetes, Users).

### Step 1.3 — Verify View-As toggle available
- **Action:** Observe sidebar footer area (below Settings).
- **UI State:** "View as..." button visible. Click it -> dropdown shows: Your View (Maintainer), Maintainer, Developer, Operator.
- **Assertion:** `page.getByText('View as...').toBeVisible()`. Dropdown has 4 options.

---

## PHASE 2: PRODUCT MANAGEMENT (products:manage — ALLOWED)

### Step 2.1 — Navigate to Products (empty state)
- **Action:** Click "Products" in sidebar.
- **UI State:** Products list page loads. If empty, shows empty state message. "Create Product" button is visible (gated on `products:manage`).
- **Backend:** `GET /v2/products` with `products:view` -> 200.
- **Assertion:** `page.getByRole('button', { name: /create product/i }).toBeVisible()`.

### Step 2.2 — Create product via wizard
- **Action:** Click "Create Product". Complete 4-step wizard:
  - Step 1: Select `main` branch from ck_boards dropdown
  - Step 2: Select "alpha" board family from discovered boards
  - Step 3: Fill board revision details (revision "B0", SoCs, AppIDs 109/108, repos `alpha_fw`/`alpha_mfg_fw`)
  - Step 4: Click "Create"
- **UI State:** Wizard modal progresses through steps. On step 4, confirm button enabled. After creation, redirect to product detail or list with new product.
- **Backend:** `POST /v2/products` with `products:manage` -> 201. Board discovery calls use `products:view`.
- **Permission boundary:** This exact operation would return 403 for DEVELOPER (no `products:manage`).
- **Assertion:** Product appears in list. Navigate to detail page, 5 tabs present (Overview, Hardware, Assets, Manufacturing, Validation).

### Step 2.3 — Edit product
- **Action:** Navigate to product detail. Click edit icon/button. Change product name to "Alpha E2E Maintainer". Save.
- **UI State:** Edit form/modal appears (gated on `canManage`). Save button enabled.
- **Backend:** `PATCH /v2/products/<id>` with `products:manage` -> 200.
- **Assertion:** Updated name visible on detail page.

### Step 2.4 — Configure validation stages
- **Action:** Go to Validation tab on product detail. For each stage (1-5):
  - Click stage card/button to open Stage Config Wizard
  - Select board revision: Alpha B0
  - Set watch branch: `concord-main`
  - Set trigger: `pr_push` + `manual`
  - Edit build recipe (load template)
  - Configure build matrix
  - Save
- **UI State:** Stage configuration UI is accessible. Save succeeds for each stage. Stage pills show "enabled" state.
- **Backend:** Stage config endpoints use `builds:manage` (Maintainer has this). Recipe endpoints use `builds:manage`.
- **Assertion:** All 5 stages show enabled status indicators.

---

## PHASE 3: BUILD MANAGEMENT (builds:trigger, builds:manage — ALLOWED)

### Step 3.1 — Trigger manual build
- **Action:** Navigate to Builds page. Click "Trigger Build" or equivalent action button.
- **UI State:** Build trigger form/dialog appears. Select product, branch/commit. Submit.
- **Backend:** `POST /v2/builds/trigger` with `builds:trigger` -> 200/201.
- **Assertion:** New BuildRun appears in list with PENDING/QUEUED status.

### Step 3.2 — Monitor build progress
- **Action:** Click on build run to view detail page.
- **UI State:** Build detail shows job matrix, status transitions (QUEUED -> CLONING -> BUILDING -> SUCCESS), live log streaming.
- **Backend:** `GET /v2/builds/runs/<id>` with `builds:view` -> 200.
- **Assertion:** Status badges update. Artifacts section populated after completion.

### Step 3.3 — Manage build configuration
- **Action:** Edit stage config, modify recipe, update build matrix.
- **Backend:** `PATCH /v2/builds/stage-config/<id>` with `builds:manage` -> 200. `PUT /v2/builds/recipes/<id>` with `builds:manage` -> 200.
- **Assertion:** Changes persist on page reload.

### Step 3.4 — Cancel build
- **Action:** On a running build, click "Cancel" button.
- **Backend:** `POST /v2/builds/runs/<id>/cancel` with `builds:manage` -> 200.
- **Assertion:** Build status transitions to CANCELLED.

---

## PHASE 4: VALIDATION MANAGEMENT (validation:manage — ALLOWED)

### Step 4.1 — View validation hub
- **Action:** Navigate to Validation in sidebar.
- **UI State:** Validation hub loads with queue stats, recent runs. Manage controls visible (canManage = true).
- **Backend:** `GET /v2/sessions/queue` with `validation:view` -> 200.
- **Assertion:** Queue list loads. "Create" or manage buttons visible.

### Step 4.2 — Manage validation queue
- **Action:** Reorder queue entries. Cancel a queued entry. Retry a failed entry.
- **Backend:**
  - Reorder: `PATCH /v2/sessions/queue/<id>` with `validation:manage` -> 200
  - Cancel: `POST /v2/sessions/queue/<id>/cancel` with `validation:manage` -> 200
  - Retry: `POST /v2/sessions/queue/<id>/retry` with `validation:manage` -> 200
- **Permission boundary:** DEVELOPER has `validation:run` but NOT `validation:manage` — queue reorder/cancel/retry would 403.
- **Assertion:** Queue entry statuses update correctly.

### Step 4.3 — Trigger validation run
- **Action:** Click "Run Validation" or equivalent. Select product and configuration.
- **Backend:** `POST /v2/sessions/runs` with `validation:run` -> 201.
- **Assertion:** New run appears with QUEUED or ASSIGNED status.

### Step 4.4 — View run detail with real-time updates
- **Action:** Click into an active or completed run.
- **UI State:** Run detail page: RunHeader (status, duration), StageSidebar, TestList, ChartPanel (power), UartPanel (UART terminal).
- **Backend:** `GET /v2/sessions/runs/<id>` with `validation:view` -> 200. WebSocket connection for real-time updates.
- **Assertion:** Test results visible. If active run, WebSocket events arrive.

### Step 4.5 — Manage validation designs
- **Action:** Navigate to Validation > Designs. Create a new design, edit it, delete it.
- **Backend:**
  - Create: with `validation:manage` -> 201
  - Edit: with `validation:manage` -> 200
  - Delete: with `validation:manage` -> 200
- **Assertion:** CRUD operations succeed. DEVELOPER attempting same gets 403.

---

## PHASE 5: FIXTURE MANAGEMENT (fixtures:manage — ALLOWED)

### Step 5.1 — Create fixture design
- **Action:** Navigate to Fixtures page (Designs tab). Click "Create Design".
- **UI State:** Form: name, board revision, revision string, capabilities checkboxes, profile template JSON editor. "Create Design" button visible (canManage).
- **Backend:** `POST /v2/fixtures/designs` with `fixtures:manage` -> 201.
- **Assertion:** New design in list with correct details.

### Step 5.2 — Create fixture instance
- **Action:** Switch to Fixtures tab. Click "Create Fixture".
- **UI State:** Form: name, product, type (VALIDATION/MANUFACTURING), design, station ID.
- **Backend:** `POST /v2/fixtures` with `fixtures:manage` -> 201.
- **Assertion:** Fixture appears with AVAILABLE status.

### Step 5.3 — Assign node to fixture slot
- **Action:** Open fixture detail. Click on empty slot. Select/create node. Assign.
- **Backend:**
  - Create node: `POST /v2/nodes` with `devices:manage` -> 201
  - Assign to slot: `POST /v2/fixtures/<id>/slots/<slotId>/assign` with `fixtures:manage` -> 200
- **Permission boundary:** DEVELOPER cannot create fixtures (no `fixtures:manage`) or nodes (no `devices:manage`).
- **Assertion:** Slot shows assigned node. MTIB deployment triggered.

### Step 5.4 — Delete fixture design (blocked if referenced)
- **Action:** Try to delete a design that has fixture instances.
- **Backend:** `DELETE /v2/fixtures/designs/<id>` with `fixtures:manage` -> 409 Conflict.
- **Assertion:** Error message about referenced instances. Delete succeeds after removing instances.

---

## PHASE 6: DEVICE MANAGEMENT (devices:manage — ALLOWED)

### Step 6.1 — Create and manage nodes
- **Action:** Create MTIB node with hostname, type, IP, hardware revision.
- **Backend:** `POST /v2/nodes` with `devices:manage` -> 201.
- **Assertion:** Node appears in list.

### Step 6.2 — Update node
- **Action:** Edit node properties (hostname, IP).
- **Backend:** `PATCH /v2/nodes/<id>` with `devices:manage` -> 200.
- **Assertion:** Updated values persist.

### Step 6.3 — Deploy/undeploy MTIB
- **Action:** Trigger MTIB deployment action on node.
- **Backend:** `POST /v2/nodes/<id>/deploy` with `devices:manage` -> 200.
- **Permission boundary:** DEVELOPER can view nodes (`devices:view`) but cannot deploy/manage.
- **Assertion:** Deployment status updates.

---

## PHASE 7: MANUFACTURING (manufacturing:manage — ALLOWED)

### Step 7.1 — Create manufacturing fixture
- **Action:** Create fixture with type=MANUFACTURING (uses `fixtures:manage`).
- **Backend:** `POST /v2/fixtures` with `fixtures:manage` -> 201.
- **Assertion:** Manufacturing fixture visible on Manufacturing page.

### Step 7.2 — Start manufacturing session
- **Action:** Navigate to Manufacturing. Click "New Session" on a manufacturing fixture.
- **Backend:** `POST /v2/manufacturing/sessions` with `manufacturing:run` -> 201. Fixture locked.
- **Assertion:** Session created, fixture status = LOCKED.

### Step 7.3 — Run manufacturing panel
- **Action:** Enter QR code. Click "Run Panel".
- **Backend:** `POST /v2/manufacturing/sessions/<id>/panels` with `manufacturing:run` -> 201.
- **Assertion:** Panel results stream back. Per-unit pass/fail visible.

### Step 7.4 — End session
- **Action:** Click "End Session".
- **Backend:** `POST /v2/manufacturing/sessions/<id>/end` with `manufacturing:manage` -> 200.
- **Assertion:** Fixture released (AVAILABLE).

---

## PHASE 8: KUBERNETES (kubernetes:view — ALLOWED, kubernetes:manage — DENIED)

### Step 8.1 — View Kubernetes dashboard
- **Action:** Click "System" toggle in sidebar. Click "Kubernetes".
- **UI State:** Kubernetes page loads. Shows cluster status, pods, deployments, services. All data is read-only.
- **Backend:** `GET /v2/kubernetes/cluster` with `kubernetes:view` -> 200.
- **Assertion:** Cluster info, pods, deployments, services all render.

### Step 8.2 — Verify manage actions are hidden or disabled
- **Action:** Look for "Scale", "Delete Pod", "Restart" buttons on Kubernetes page.
- **UI State:** Manage action buttons should be hidden or disabled (gated on `kubernetes:manage`).
- **Assertion:** No manage-action buttons visible. If buttons exist, they are disabled.

### Step 8.3 — API boundary: kubernetes:manage returns 403
- **Action (API only):** Attempt `POST /v2/kubernetes/deployments/<name>/scale` directly.
- **Backend:** `kubernetes:manage` required -> 403 Forbidden.
- **Assertion:** Response status 403.

### Step 8.4 — API boundary: more kubernetes:manage operations
- **API:** `DELETE /v2/kubernetes/pods/<name>` -> 403 (requires `kubernetes:manage`)
- **API:** `POST /v2/kubernetes/deployments/<name>/restart` -> 403
- **API:** `DELETE /v2/kubernetes/jobs/<name>` -> 403
- **Assertion:** All return 403.

---

## PHASE 9: USERS PAGE (users:view — ALLOWED, users:manage — DENIED)

### Step 9.1 — Navigate to Users page
- **Action:** Click "Admin" toggle. Click "Users".
- **UI State:** Users page loads. User list visible. Permission Sets tab visible.
- **Backend:** `GET /v2/auth/users` with `users:view` -> 200.
- **Assertion:** User list renders with names, emails, roles.

### Step 9.2 — Verify manage actions are hidden
- **Action:** Look for "Create User", "Edit", "Deactivate" buttons.
- **UI State:** `canManage` derived from `users:manage` (line 32 of users/+page.svelte) is false. Create/Edit/Delete buttons hidden.
- **Assertion:** `page.getByRole('button', { name: /create user/i }).not.toBeVisible()`.

### Step 9.3 — API boundary: users:manage returns 403
- **API:** `POST /v2/auth/users` body `{"email":"test@test.com","name":"Test"}` -> 403
- **API:** `PATCH /v2/auth/users/<id>` -> 403
- **API:** `DELETE /v2/auth/users/<id>` -> 403
- **API:** `POST /v2/auth/users/<id>/deactivate` -> 403
- **Assertion:** All return 403 with permission error.

### Step 9.4 — API boundary: permissions:manage returns 403
- **API:** `POST /v2/auth/permission-sets` -> 403
- **API:** `PATCH /v2/auth/permission-sets/<id>` -> 403
- **API:** `DELETE /v2/auth/permission-sets/<id>` -> 403
- **Assertion:** All return 403. Maintainer can VIEW permission sets (`users:view`) but not manage them.

---

## PHASE 10: SYSTEM (system:view — ALLOWED, system:manage — DENIED)

### Step 10.1 — View system info
- **Backend:** `GET /v2/system/info` with `system:view` -> 200.
- **Assertion:** System info (version, uptime, etc.) returned.

### Step 10.2 — View audit history
- **Backend:** `GET /v2/system/history` with `system:view` -> 200.
- **Assertion:** Audit log entries returned.

### Step 10.3 — API boundary: system:manage returns 403
- **API:** `POST /v2/system/secrets` -> 403 (requires `system:manage`)
- **API:** `PATCH /v2/system/secrets/<id>` -> 403
- **API:** `DELETE /v2/system/secrets/<id>` -> 403
- **API:** `POST /v2/system/poller-state/reset` -> 403
- **API:** `PUT /v2/system/retention` -> 403
- **Assertion:** All return 403.

---

## PHASE 11: API KEYS (api-keys:manage — ALLOWED)

### Step 11.1 — Create API key
- **Action:** Navigate to API key management (Settings or profile section).
- **Backend:** `POST /v2/auth/api-keys` with `api-keys:manage` -> 201. Response includes plaintext key (shown once).
- **Assertion:** Key created. Plaintext displayed. On subsequent list, only prefix visible.

### Step 11.2 — List API keys
- **Backend:** `GET /v2/auth/api-keys` with `api-keys:view` -> 200.
- **Assertion:** Keys listed with name, prefix, created date. No full key shown.

### Step 11.3 — Revoke API key
- **Backend:** `DELETE /v2/auth/api-keys/<id>` with `api-keys:manage` -> 200.
- **Assertion:** Key removed from list.

---

## PHASE 12: VIEW-AS-ROLE TESTING

### Step 12.1 — View as Developer
- **Action:** Click "View as..." button. Select "Developer" from dropdown.
- **UI State:** Page reloads (`window.location.reload()`). After reload, sidebar updates: Kubernetes and Users links disappear. View-As button shows "Viewing as Developer" in warning color.
- **Backend:** `GET /v2/auth/me` with `X-View-As-Role: DEVELOPER` header -> returns Developer permission set.
- **Assertion:** Sidebar has 6 items (Dashboard, Products, Builds, Validation, Manufacturing, Fixtures). No System section. No Admin section. View-As button still visible (because real role is still Maintainer).

### Step 12.2 — Verify Developer restrictions while viewing as Developer
- **Action:** Navigate to Products. Look for "Create Product" button.
- **UI State:** No create button (Developer lacks `products:manage`).
- **Assertion:** `page.getByRole('button', { name: /create product/i }).not.toBeVisible()`.

### Step 12.3 — View as Operator
- **Action:** Click "View as..." Select "Operator".
- **UI State:** Page reloads. Sidebar shows only Dashboard + Manufacturing. View-As button still visible.
- **Assertion:** Only 2 nav items. Products, Builds, Validation, Fixtures, Kubernetes, Users all hidden.

### Step 12.4 — Reset to own view
- **Action:** Click "View as..." Select "Your View (Maintainer)".
- **UI State:** Page reloads. Full Maintainer sidebar restored.
- **Assertion:** All 8 nav items visible again.

---

## PHASE 13: COMPREHENSIVE PERMISSION BOUNDARY MATRIX

### Operations that MUST succeed (200/201):

| Operation | Endpoint | Permission |
|-----------|----------|------------|
| List products | `GET /v2/products` | products:view |
| Create product | `POST /v2/products` | products:manage |
| Update product | `PATCH /v2/products/<id>` | products:manage |
| Delete product | `DELETE /v2/products/<id>` | products:manage |
| List builds | `GET /v2/builds` | builds:view |
| Trigger build | `POST /v2/builds/trigger` | builds:trigger |
| Cancel build | `POST /v2/builds/runs/<id>/cancel` | builds:manage |
| List queue | `GET /v2/sessions/queue` | validation:view |
| Run validation | `POST /v2/sessions/runs` | validation:run |
| Manage queue | `PATCH /v2/sessions/queue/<id>` | validation:manage |
| List fixtures | `GET /v2/fixtures` | fixtures:view |
| Create fixture | `POST /v2/fixtures` | fixtures:manage |
| Delete fixture | `DELETE /v2/fixtures/<id>` | fixtures:manage |
| List nodes | `GET /v2/nodes` | devices:view |
| Create node | `POST /v2/nodes` | devices:manage |
| View K8s cluster | `GET /v2/kubernetes/cluster` | kubernetes:view |
| View users | `GET /v2/auth/users` | users:view |
| View system info | `GET /v2/system/info` | system:view |
| Create API key | `POST /v2/auth/api-keys` | api-keys:manage |
| Mfg session start | `POST /v2/manufacturing/sessions` | manufacturing:run |

### Operations that MUST return 403:

| Operation | Endpoint | Missing Permission |
|-----------|----------|--------------------|
| Create user | `POST /v2/auth/users` | users:manage |
| Update user | `PATCH /v2/auth/users/<id>` | users:manage |
| Delete user | `DELETE /v2/auth/users/<id>` | users:manage |
| Create perm set | `POST /v2/auth/permission-sets` | permissions:manage |
| Update perm set | `PATCH /v2/auth/permission-sets/<id>` | permissions:manage |
| Delete perm set | `DELETE /v2/auth/permission-sets/<id>` | permissions:manage |
| Scale deployment | `POST /v2/kubernetes/deployments/<n>/scale` | kubernetes:manage |
| Delete pod | `DELETE /v2/kubernetes/pods/<n>` | kubernetes:manage |
| Restart deployment | `POST /v2/kubernetes/deployments/<n>/restart` | kubernetes:manage |
| Delete K8s job | `DELETE /v2/kubernetes/jobs/<n>` | kubernetes:manage |
| Create secret | `POST /v2/system/secrets` | system:manage |
| Update secret | `PATCH /v2/system/secrets/<id>` | system:manage |
| Delete secret | `DELETE /v2/system/secrets/<id>` | system:manage |
| Reset poller | `POST /v2/system/poller-state/reset` | system:manage |
| Set retention | `PUT /v2/system/retention` | system:manage |

---

## PHASE 14: CLEANUP

### Step 14.1 — Delete created resources (reverse order)
- Delete manufacturing sessions/fixtures
- Delete validation runs/queue entries
- Unassign nodes from fixture slots
- Delete fixture instances, then designs
- Delete nodes
- Delete product (cascades boards, stages, builds)
- Delete API keys

### Step 14.2 — Bitbucket cleanup
- **API:** Delete any branches/PRs created during test.

### Step 14.3 — Verify zero-data state
- `GET /v2/products` -> empty list
- `GET /v2/fixtures` -> empty list
- `GET /v2/nodes` -> empty list
- **Assertion:** System back to clean state (audit logs excluded from check).
