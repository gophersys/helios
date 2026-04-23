# OPERATOR User Story — Manufacturing Workflow

**Last reviewed:** 2026-04-08
**Status:** Draft

---

## Overview

The Operator is the only role whose entire workflow is manufacturing. They have exactly 3 permissions: `manufacturing:view`, `manufacturing:run`, `manufacturing:manage`. They cannot see Products, Builds, Validation, Fixtures, Users, or Kubernetes. This story is the blueprint for the entire manufacturing feature — every step documents what the UI shows, what the backend does, what events fire, and how Playwright verifies it.

**Precondition:** Admin has already completed Stages 10-12 setup:
- Product "Alpha B0" exists with ManufacturingConfig (Electrical + Flash + POST stages enabled)
- A MANUFACTURING fixture design and instance exist with MTIB slot(s) assigned
- Operator user (`operator@concord.dev`) exists with OPERATOR role

---

## Phase 1: Login and Navigation Enforcement

### Step 1.1 — Login as Operator

| Dimension | Detail |
|-----------|--------|
| **User Action** | Navigate to `/login`. Click the "Operator" user card in the dev-login grid. |
| **Expected UI** | Dev-login page shows 4 role cards (Admin, Maintainer, Developer, Operator). Clicking Operator card triggers login. Redirect to `/dashboard`. |
| **Backend Required** | `POST /v2/auth/dev-login` with body `{ email: "operator@concord.dev" }`. Returns JWT with role=OPERATOR and permissions `[manufacturing:view, manufacturing:run, manufacturing:manage]`. |
| **Permission Check** | None — login is unauthenticated. |
| **Failure Modes** | Operator user not seeded → 401. Dev-login disabled in production → endpoint 404. |
| **Assertion Strategy** | `await page.getByTestId('role-card-operator').click()` → verify redirect to `/dashboard`. Extract JWT from cookie/localStorage, decode, assert `role === 'OPERATOR'` and permissions array length === 3. |

### Step 1.2 — Verify Sidebar Visibility

| Dimension | Detail |
|-----------|--------|
| **User Action** | Observe the sidebar after login. |
| **Expected UI** | Sidebar shows exactly 2 items: **Dashboard** and **Manufacturing**. No other items visible. |
| **Backend Required** | None — sidebar is rendered client-side based on JWT permissions. |
| **Permission Check** | Sidebar items gated on: Products (`products:view`), Builds (`builds:view`), Validation (`validation:view`), Fixtures (`fixtures:view`), Users (`users:view`), Kubernetes (`system:view`). Operator has none of these. |
| **Assertion Strategy** | Assert `page.getByTestId('sidebar-item-dashboard')` visible. Assert `page.getByTestId('sidebar-item-manufacturing')` visible. Assert the following are NOT in the DOM: `sidebar-item-products`, `sidebar-item-builds`, `sidebar-item-validation`, `sidebar-item-fixtures`, `sidebar-item-users`, `sidebar-item-kubernetes`. |

### Step 1.3 — Verify URL Direct-Access Blocking

| Dimension | Detail |
|-----------|--------|
| **User Action** | Manually type forbidden URLs into the address bar. |
| **Expected UI** | Each URL redirects to `/dashboard` (or shows a 403 page). No flash of forbidden content. |
| **Routes Tested** | `/products`, `/builds`, `/validation`, `/fixtures`, `/users`, `/kubernetes` |
| **Backend Required** | Frontend route guards check permissions before rendering. Server-side load functions return redirect if permission missing. |
| **Permission Check** | Each route's `+page.server.ts` or `+layout.server.ts` checks the required permission. |
| **Assertion Strategy** | For each forbidden route: `await page.goto('/products')` → assert `page.url()` does NOT contain `/products`. Assert either redirected to `/dashboard` or a 403 element is visible. |

### Step 1.4 — Verify API-Level 403 Enforcement

| Dimension | Detail |
|-----------|--------|
| **User Action** | None (programmatic API calls from test). |
| **Backend Required** | Every endpoint's `@require_permissions` decorator returns 403 if JWT lacks the permission. |
| **API Calls Tested** | |

```
GET  /v2/products                    → 403 (needs products:view)
GET  /v2/builds                      → 403 (needs builds:view)
GET  /v2/validation/sessions         → 403 (needs validation:view)
GET  /v2/fixtures                    → 403 (needs fixtures:view)
GET  /v2/users                       → 403 (needs users:view)
GET  /v2/kubernetes/nodes            → 403 (needs kubernetes:view)
POST /v2/validation/sessions         → 403 (needs validation:run)
```

| **Assertion Strategy** | Use `request.get()` with Operator JWT for each endpoint. Assert `response.status() === 403` for every call. |

### Step 1.5 — Verify Manufacturing API Access ALLOWED

| Dimension | Detail |
|-----------|--------|
| **API Calls Tested** | |

```
GET  /v2/manufacturing/fixtures      → 200 (manufacturing:view)
GET  /v2/manufacturing/sessions      → 200 (manufacturing:view)
POST /v2/manufacturing/sessions      → 201 (manufacturing:run) — tested in Phase 2
```

| **Assertion Strategy** | `response.status() === 200` for GET endpoints with Operator JWT. |

---

## Phase 2: Manufacturing Page — Fixture Discovery

### Step 2.1 — Navigate to Manufacturing Page

| Dimension | Detail |
|-----------|--------|
| **User Action** | Click "Manufacturing" in sidebar. |
| **Expected UI** | Page loads with header "Manufacturing". Two tabs: "Fixtures" and "Sessions". Fixtures tab active by default. |
| **Backend Required** | `GET /v2/manufacturing/fixtures` — returns list of MANUFACTURING-type fixtures with status, product info, slot count. |
| **Permission Check** | `manufacturing:view` on the GET endpoint. |
| **Assertion Strategy** | Assert `page.getByRole('heading', { name: 'Manufacturing' })` visible. Assert `page.getByRole('tab', { name: 'Fixtures' })` has `aria-selected=true`. Assert `page.getByRole('tab', { name: 'Sessions' })` visible. |

### Step 2.2 — View Manufacturing Fixtures

| Dimension | Detail |
|-----------|--------|
| **User Action** | Observe the fixtures tab content. |
| **Expected UI** | One or more fixture cards. Each card shows: fixture name, product name ("Alpha B0"), slot count (e.g., "1 slot"), status badge. Available fixtures show green "AVAILABLE" badge and a "New Session" button. |
| **Backend Required** | `GET /v2/manufacturing/fixtures` returns: |

```json
[{
  "id": "fixture-id",
  "name": "MFG-Bench-33",
  "product": { "id": "...", "name": "Alpha B0" },
  "slotCount": 1,
  "status": "AVAILABLE",
  "activeSession": null
}]
```

| **Permission Check** | `manufacturing:view` |
| **Failure Modes** | No manufacturing fixtures configured → empty state with message "No manufacturing fixtures available. Contact an administrator." |
| **Assertion Strategy** | Assert at least one `[data-testid="manufacturing-fixture-card"]` visible. Assert card contains fixture name, "AVAILABLE" badge, "New Session" button. |

---

## Phase 3: Session Lifecycle

### Step 3.1 — Start New Session

| Dimension | Detail |
|-----------|--------|
| **User Action** | Click "New Session" button on an AVAILABLE fixture card. |
| **Expected UI** | Button shows loading spinner. On success, redirect to `/manufacturing/session/[id]`. Fixture card (if visible) updates to LOCKED with yellow badge. |
| **Backend Required** | `POST /v2/manufacturing/sessions` with body `{ fixtureId: "..." }`. Backend: (1) verifies fixture is AVAILABLE, (2) creates ManufacturingSession with status=ACTIVE, operatorId=current user, (3) locks fixture (status=LOCKED, activeSessionId=session.id), (4) snapshots ManufacturingConfig into session.config, (5) returns session object. |
| **WebSocket Events** | `manufacturing_session_start { sessionId, fixtureId, operatorId, productName }` broadcast on `/manufacturing` namespace. |
| **Permission Check** | `manufacturing:run` |
| **Failure Modes** | Fixture already LOCKED → 409 Conflict ("Fixture is currently in use"). Fixture has no ManufacturingConfig → 400 ("Manufacturing not configured for this product"). Race condition (two operators click simultaneously) → DB unique constraint on fixture lock, second request gets 409. |
| **Assertion Strategy** | Assert redirect to URL matching `/manufacturing/session/`. Assert session header shows fixture name, product name, operator name, "ACTIVE" status badge, elapsed timer counting up. |

### Step 3.2 — Session Runner Page Layout

| Dimension | Detail |
|-----------|--------|
| **User Action** | Observe the session runner page after creation. |
| **Expected UI** | Three sections top-to-bottom: (1) **Session Header** — product, fixture, operator, ACTIVE badge, elapsed timer. (2) **Panel Input** — text input with placeholder "Scan or enter panel QR code", "Run Panel" button (enabled), "End Session" button (enabled). (3) **Panel Area** — empty state: "No panels run yet. Scan a QR code to begin." |
| **Backend Required** | `GET /v2/manufacturing/sessions/[id]` returns session with empty `panels` array. |
| **Assertion Strategy** | Assert QR input field visible and empty. Assert "Run Panel" button enabled. Assert "End Session" button visible. Assert empty state message visible. |

### Step 3.3 — Enter QR Code

| Dimension | Detail |
|-----------|--------|
| **User Action** | Click QR code text input. Type "E2E-PANEL-001" (simulating a barcode scanner which types characters). |
| **Expected UI** | Text appears in input field. "Run Panel" button remains enabled. |
| **Backend Required** | None — client-side only until "Run Panel" clicked. |
| **Assertion Strategy** | `await page.getByPlaceholder('Scan or enter panel QR code').fill('E2E-PANEL-001')`. Assert input value equals "E2E-PANEL-001". |

### Step 3.4 — Run Panel (First Panel)

| Dimension | Detail |
|-----------|--------|
| **User Action** | Click "Run Panel" button. |
| **Expected UI** | (1) "Run Panel" button becomes disabled (prevents double-submit). (2) QR input clears and is disabled. (3) Panel area shows active panel with QR code "E2E-PANEL-001" as heading. (4) A grid of unit cards appears — one per fixture slot. Each card shows: slot label, spinner icon, "RUNNING" status, stage progress bar at "Electrical" (first stage). |
| **Backend Required** | `POST /v2/manufacturing/sessions/[id]/panels` with body `{ qrCode: "E2E-PANEL-001" }`. Backend: (1) validates session is ACTIVE, (2) creates ManufacturingPanel with panelIndex=1, qrCode, status=RUNNING, (3) creates ManufacturingUnit for each fixture slot with status=RUNNING, (4) triggers manufacturing test runner (K8s Job or message to persistent runner), (5) returns panel with units. |
| **WebSocket Events** | `manufacturing_panel_start { sessionId, panelId, panelIndex: 1, qrCode: "E2E-PANEL-001", unitCount: N }` |
| **Permission Check** | `manufacturing:run` |
| **Failure Modes** | Empty QR code → client-side validation, button stays disabled until input non-empty. Session not ACTIVE → 400. Panel already running → 409 ("A panel is already running. Wait for it to complete."). |
| **Assertion Strategy** | Assert "Run Panel" button has `disabled` attribute. Assert panel heading contains "E2E-PANEL-001". Assert N unit cards visible (N = fixture slot count). Each card shows "RUNNING" badge and spinner. |

### Step 3.5 — Real-Time Stage Results (Electrical)

| Dimension | Detail |
|-----------|--------|
| **User Action** | Observe the unit cards as the test runner executes. |
| **Expected UI** | For each unit, the Electrical stage indicator transitions: spinner → green checkmark (PASSED) or red X (FAILED). Stage label "Electrical" shows the result. The next stage "Flash" begins (spinner). |
| **Backend Required** | Test runner calls reporter: `POST /v2/manufacturing/sessions/[id]/report/stage-result` with `{ panelId, unitId, stageName: "Electrical", status: "PASSED", durationMs: 1200, steps: [...] }`. Backend updates ManufacturingUnit.stages JSON and broadcasts WebSocket event. |
| **WebSocket Events** | `manufacturing_stage_result { sessionId, panelId, unitId, slotIndex, stageName: "Electrical", status: "PASSED", durationMs: 1200 }` |
| **Assertion Strategy** | Wait for WebSocket event. Assert unit card's Electrical stage indicator changes from spinner to checkmark. Assert stage shows "PASSED" text or green icon. |

### Step 3.6 — Real-Time Stage Results (Flash)

| Dimension | Detail |
|-----------|--------|
| **User Action** | Continue observing. |
| **Expected UI** | Flash stage indicator: spinner → check/X. Includes substeps: J-Link recover, flash app, flash comms, verify. If Flash stage takes ~2 min, a progress indicator or substep list may show intermediate progress. |
| **Backend Required** | Reporter: `POST .../report/stage-result` with `stageName: "Flash"`. |
| **WebSocket Events** | `manufacturing_stage_result { ..., stageName: "Flash", status: "PASSED", durationMs: 120000 }` |
| **Assertion Strategy** | Wait for Flash stage WebSocket event. Assert Flash indicator updates. Assert POST stage spinner begins. |

### Step 3.7 — Real-Time Stage Results (POST)

| Dimension | Detail |
|-----------|--------|
| **User Action** | Continue observing. |
| **Expected UI** | POST stage completes. Unit card shows final overall status: green "PASSED" badge or red "FAILED" badge. Duration shown (e.g., "5m 23s"). If failed, error message text visible below the unit card. |
| **Backend Required** | Reporter: `POST .../report/stage-result` with `stageName: "POST"`, then `POST .../report/unit-result` with `{ panelId, unitId, status: "PASSED", durationMs: 323000 }`. Backend updates ManufacturingUnit.status, completedAt, durationMs. |
| **WebSocket Events** | `manufacturing_stage_result { ..., stageName: "POST", status: "PASSED" }` then `manufacturing_unit_result { sessionId, panelId, unitId, slotIndex, status: "PASSED", durationMs: 323000 }` |
| **Assertion Strategy** | Assert unit card status badge changes to "PASSED". Assert duration text visible. |

### Step 3.8 — Panel Completion

| Dimension | Detail |
|-----------|--------|
| **User Action** | All units in the panel finish (pass or fail). |
| **Expected UI** | Panel summary bar appears: "1/1 units passed" (or "3/4 units passed" for multi-slot). Panel status shows PASSED (all green) or FAILED (any red). "Run Panel" button re-enables. QR input re-enables and clears. The completed panel moves to the "Panel History" section below. |
| **Backend Required** | Reporter: `POST .../report/panel-complete` with `{ panelId, status: "PASSED", passedUnits: 1, failedUnits: 0, durationMs: 330000 }`. Backend updates ManufacturingPanel status, counts, completedAt. Updates ManufacturingSession panelCount, passedCount, failedCount. |
| **WebSocket Events** | `manufacturing_panel_complete { sessionId, panelId, panelIndex: 1, status: "PASSED", passedUnits: 1, failedUnits: 0, durationMs: 330000 }` |
| **Assertion Strategy** | Assert panel summary text matches expected pass/fail. Assert "Run Panel" button no longer has `disabled` attribute. Assert QR input is empty and enabled. Assert panel history section contains one entry with "E2E-PANEL-001". |

### Step 3.9 — Run Second Panel

| Dimension | Detail |
|-----------|--------|
| **User Action** | Type "E2E-PANEL-002" in QR input. Click "Run Panel". |
| **Expected UI** | Same flow as Steps 3.4-3.8 but with panelIndex=2. Active panel shows "E2E-PANEL-002". Panel history now shows "E2E-PANEL-001" as completed. |
| **Backend Required** | `POST .../panels` with `{ qrCode: "E2E-PANEL-002" }`. Creates panel with panelIndex=2. |
| **WebSocket Events** | Same event sequence as first panel, with panelIndex=2. |
| **Assertion Strategy** | Assert active panel heading is "E2E-PANEL-002". Assert panel history has 1 entry ("E2E-PANEL-001"). After completion, panel history has 2 entries. Session header shows updated panel count. |

### Step 3.10 — Panel History Accordion

| Dimension | Detail |
|-----------|--------|
| **User Action** | Click on a completed panel entry in the panel history section. |
| **Expected UI** | Accordion expands to show: QR code, pass/fail count, duration, and unit detail cards with per-stage results. Clicking again collapses it. |
| **Backend Required** | Data already loaded in session detail (or lazy-loaded via `GET /v2/manufacturing/sessions/[id]` which includes panels and units). |
| **Assertion Strategy** | Click panel history entry. Assert unit cards appear within the expanded section. Assert stage results (Electrical, Flash, POST) visible per unit. Click again, assert collapsed. |

---

## Phase 4: End Session

### Step 4.1 — Click End Session

| Dimension | Detail |
|-----------|--------|
| **User Action** | Click "End Session" button. |
| **Expected UI** | Confirmation dialog appears: "End manufacturing session? This will release the fixture and finalize all results. This cannot be undone." Two buttons: "Cancel" and "End Session" (destructive/red). |
| **Backend Required** | None yet — dialog is client-side. |
| **Assertion Strategy** | Assert dialog visible with confirmation text. Assert "Cancel" and "End Session" buttons present. |

### Step 4.2 — Confirm End Session

| Dimension | Detail |
|-----------|--------|
| **User Action** | Click "End Session" in the confirmation dialog. |
| **Expected UI** | Dialog closes. Session header status changes from "ACTIVE" to "COMPLETED" (blue or gray badge). Elapsed timer stops. QR input and "Run Panel" button disappear (or become permanently disabled). "End Session" button disappears. Page becomes read-only — a summary view of the completed session. |
| **Backend Required** | `POST /v2/manufacturing/sessions/[id]/end`. Backend: (1) sets session status=COMPLETED, endedAt=now(), (2) if a panel is RUNNING, cancels it (status=CANCELLED), (3) releases fixture (status=AVAILABLE, activeSessionId=null), (4) returns updated session. |
| **WebSocket Events** | `manufacturing_session_end { sessionId, status: "COMPLETED", panelCount: 2, passedCount: 2, failedCount: 0 }` |
| **Permission Check** | `manufacturing:run` (same as starting — only the operator running the session can end it). |
| **Failure Modes** | Session already COMPLETED → 400 ("Session already ended"). Network error during end → retry button, session remains ACTIVE until confirmed. |
| **Assertion Strategy** | Assert session status badge shows "COMPLETED". Assert QR input not visible (or disabled). Assert "Run Panel" button not visible. Assert "End Session" button not visible. |

### Step 4.3 — Fixture Released

| Dimension | Detail |
|-----------|--------|
| **User Action** | Navigate back to `/manufacturing` (Fixtures tab). |
| **Expected UI** | The fixture that was locked now shows "AVAILABLE" badge (green) and "New Session" button. No active session indicator. |
| **Backend Required** | `GET /v2/manufacturing/fixtures` — fixture status=AVAILABLE. |
| **Assertion Strategy** | Assert fixture card shows "AVAILABLE" badge. Assert "New Session" button is visible and enabled. |

---

## Phase 5: Session History and Results

### Step 5.1 — View Sessions Tab

| Dimension | Detail |
|-----------|--------|
| **User Action** | On `/manufacturing`, click the "Sessions" tab. |
| **Expected UI** | Table/list of manufacturing sessions. The session just completed is visible. Columns: fixture name, product, operator, panel count, passed/failed, status (COMPLETED), start time, duration. |
| **Backend Required** | `GET /v2/manufacturing/sessions?page=1&limit=20` — paginated list. |
| **Permission Check** | `manufacturing:view` |
| **Assertion Strategy** | Assert sessions list contains at least 1 row. Assert the row shows correct fixture name, "COMPLETED" status, panel count = 2. |

### Step 5.2 — View Session Detail from History

| Dimension | Detail |
|-----------|--------|
| **User Action** | Click on the completed session row in the sessions list. |
| **Expected UI** | Navigates to `/manufacturing/session/[id]`. Same page as the runner, but in read-only completed state. Shows: session header with COMPLETED badge, all panels in history section (expandable), aggregate stats (total units, passed, failed, duration). |
| **Backend Required** | `GET /v2/manufacturing/sessions/[id]` — returns full session with panels and units. |
| **Assertion Strategy** | Assert URL matches `/manufacturing/session/`. Assert status = "COMPLETED". Assert 2 panels in history. Assert aggregate counts match. |

### Step 5.3 — Session Results Aggregation

| Dimension | Detail |
|-----------|--------|
| **User Action** | Observe the session summary stats. |
| **Expected UI** | Summary section shows: "2 panels / 2 units tested / 2 passed / 0 failed" (or whatever the actual counts are). Per-stage aggregate: Electrical pass rate, Flash pass rate, POST pass rate. |
| **Backend Required** | `GET /v2/manufacturing/sessions/[id]/results` — aggregated view. |
| **Assertion Strategy** | Assert summary text matches expected counts. Assert per-stage stats render. |

---

## Phase 6: Failure Modes and Edge Cases

### Step 6.1 — Unit Fails a Stage

| Dimension | Detail |
|-----------|--------|
| **Scenario** | During a panel run, one unit fails the Electrical stage. |
| **Expected UI** | Failed unit card: Electrical stage shows red X and "FAILED". Subsequent stages (Flash, POST) show gray "SKIPPED" — not attempted. Unit overall status = "FAILED". Error message displayed (e.g., "Bus scan: I2C device at 0x38 not responding"). Other units in the panel continue independently. |
| **Backend Required** | Reporter sends `stage-result` with `status: "FAILED"` and `errorMessage`. Then `unit-result` with `status: "FAILED"`. Backend does NOT run subsequent stages for a failed unit. |
| **WebSocket Events** | `manufacturing_stage_result { ..., status: "FAILED", errorMessage: "..." }` then `manufacturing_unit_result { ..., status: "FAILED" }` |
| **Assertion Strategy** | Assert failed unit card shows "FAILED" badge. Assert error message text visible. Assert skipped stages show "SKIPPED" indicator. Assert other unit cards still processing independently. |

### Step 6.2 — Panel with Mixed Results

| Dimension | Detail |
|-----------|--------|
| **Scenario** | Multi-slot fixture: slot 1 passes, slot 2 fails. |
| **Expected UI** | Panel summary: "1/2 units passed". Panel status = FAILED (because at least one unit failed). Both unit cards show their individual results. |
| **Assertion Strategy** | Assert panel summary shows mixed results. Assert panel status badge is "FAILED" (red). |

### Step 6.3 — End Session While Panel Running

| Dimension | Detail |
|-----------|--------|
| **Scenario** | Operator clicks "End Session" while a panel is mid-execution. |
| **Expected UI** | Confirmation dialog includes additional warning: "A panel is currently running. Ending the session will cancel it." |
| **Backend Required** | `POST .../end` — backend sets running panel to CANCELLED, running units to ERROR. Releases fixture. |
| **WebSocket Events** | `manufacturing_panel_complete { ..., status: "CANCELLED" }` then `manufacturing_session_end { ..., status: "COMPLETED" }` |
| **Assertion Strategy** | Assert warning text in dialog mentions running panel. After confirm, assert panel shows "CANCELLED" status. |

### Step 6.4 — Duplicate QR Code in Same Session

| Dimension | Detail |
|-----------|--------|
| **Scenario** | Operator enters the same QR code for a second panel. |
| **Expected UI** | Warning dialog: "Panel QR code 'E2E-PANEL-001' was already used in this session (Panel #1). Continue anyway?" with "Cancel" and "Continue" buttons. Allows re-running the same panel (operator may need to re-test). |
| **Backend Required** | Backend checks for duplicate QR within session, returns `{ warning: "duplicate_qr", existingPanelIndex: 1 }` or allows with flag. |
| **Assertion Strategy** | Assert warning dialog appears. Clicking "Continue" creates the panel. Clicking "Cancel" returns to input. |

### Step 6.5 — Network Disconnection During Panel

| Dimension | Detail |
|-----------|--------|
| **Scenario** | WebSocket disconnects mid-panel. |
| **Expected UI** | Connection status indicator turns red/yellow. Banner: "Connection lost. Reconnecting..." Unit cards freeze at last known state. On reconnect, full state is fetched via `GET /v2/manufacturing/sessions/[id]` and UI reconciles. |
| **Backend Required** | Test runner continues regardless of frontend connection. Results are persisted in DB. Frontend fetches full state on reconnect. |
| **Assertion Strategy** | Simulate disconnect (close WebSocket). Assert reconnection banner. Simulate reconnect. Assert unit cards update to final state. |

### Step 6.6 — MTIB Unreachable

| Dimension | Detail |
|-----------|--------|
| **Scenario** | Manufacturing test runner cannot connect to MTIB hardware. |
| **Expected UI** | All units in the panel show "ERROR" status. Error message: "MTIB connection failed: <MTIB_HOST> unreachable". Panel status = FAILED. |
| **Backend Required** | Test runner reports error via `unit-result` with `status: "ERROR"` and error message. |
| **Assertion Strategy** | Assert all unit cards show "ERROR". Assert error message mentions MTIB. |

---

## Phase 7: Things the Operator CANNOT Do

These are negative tests that verify the permission boundary is airtight.

### 7.1 — Cannot Navigate to Restricted Pages

| Route | Expected Behavior |
|-------|-------------------|
| `/products` | Redirect to `/dashboard` or 403 page |
| `/products/[any-id]` | Redirect to `/dashboard` or 403 page |
| `/builds` | Redirect to `/dashboard` or 403 page |
| `/validation` | Redirect to `/dashboard` or 403 page |
| `/fixtures` | Redirect to `/dashboard` or 403 page |
| `/users` | Redirect to `/dashboard` or 403 page |
| `/kubernetes` | Redirect to `/dashboard` or 403 page |

### 7.2 — Cannot Call Restricted API Endpoints

| Endpoint | Method | Expected |
|----------|--------|----------|
| `/v2/products` | GET | 403 |
| `/v2/products/[id]` | GET | 403 |
| `/v2/products/[id]/manufacturing` | GET | 403 (requires products:view context) |
| `/v2/builds` | GET | 403 |
| `/v2/builds/[id]` | GET | 403 |
| `/v2/validation/sessions` | GET | 403 |
| `/v2/validation/sessions` | POST | 403 |
| `/v2/fixtures` | GET | 403 |
| `/v2/fixtures` | POST | 403 |
| `/v2/users` | GET | 403 |
| `/v2/users` | POST | 403 |
| `/v2/kubernetes/nodes` | GET | 403 |

### 7.3 — Cannot Access Manufacturing Config (Indirectly Blocked)

The Operator has `manufacturing:manage` but the config wizard lives on the product detail page (`/products/[id]` → Manufacturing tab). Since Operator lacks `products:view`, they cannot reach the config page. This is by design — manufacturing configuration is an Admin/Maintainer task.

| Test | Expected |
|------|----------|
| `GET /v2/products/[id]/manufacturing` | 403 (endpoint requires `products:view` or `manufacturing:manage` scoped to product routes) |
| Navigate to `/products/[id]` | Redirect/403 |

**Design decision (from Stage 13):** Even though Operator has `manufacturing:manage`, the ManufacturingConfig endpoints live under `/v2/products/` which requires `products:view`. The permission exists for future use (e.g., a dedicated manufacturing admin page), but currently the Operator cannot reach it.

### 7.4 — Cannot Start Session on Another Operator's Active Session

| Test | Expected |
|------|----------|
| Operator A starts session on fixture → Operator B tries to start session on same fixture | 409 Conflict |
| Operator B tries to end Operator A's session | 403 or 400 (ownership check) |

---

## Playwright Test Structure

### File: `e2e/stories/operator/01-login-navigation.spec.ts`

```
test('login as Operator via dev-login card')
test('sidebar shows only Dashboard and Manufacturing')
test('sidebar does NOT show Products, Builds, Validation, Fixtures, Users, Kubernetes')
test('direct navigation to /products redirects')
test('direct navigation to /builds redirects')
test('direct navigation to /validation redirects')
test('direct navigation to /fixtures redirects')
test('direct navigation to /users redirects')
test('direct navigation to /kubernetes redirects')
test('API: GET /v2/products returns 403')
test('API: GET /v2/builds returns 403')
test('API: GET /v2/validation/sessions returns 403')
test('API: GET /v2/fixtures returns 403')
test('API: GET /v2/users returns 403')
test('API: GET /v2/kubernetes/nodes returns 403')
test('API: GET /v2/manufacturing/fixtures returns 200')
test('API: GET /v2/manufacturing/sessions returns 200')
```

### File: `e2e/stories/operator/02-manufacturing-fixtures.spec.ts`

```
test('manufacturing page loads with Fixtures and Sessions tabs')
test('fixtures tab shows available manufacturing fixtures')
test('fixture card displays name, product, slot count, AVAILABLE badge')
test('fixture card shows "New Session" button')
test('empty state when no manufacturing fixtures')
```

### File: `e2e/stories/operator/03-session-lifecycle.spec.ts`

```
test('click "New Session" creates session and redirects to runner')
test('fixture becomes LOCKED after session start')
test('session runner page shows QR input, Run Panel, End Session')
test('enter QR code in text input')
test('click "Run Panel" creates panel with unit cards')
test('Run Panel button disabled while panel running')
test('unit cards show stage progress via WebSocket (Electrical)')
test('unit cards show stage progress via WebSocket (Flash)')
test('unit cards show stage progress via WebSocket (POST)')
test('unit completion shows PASSED/FAILED badge and duration')
test('panel completion re-enables Run Panel button')
test('panel moves to history section after completion')
test('run second panel with different QR code')
test('panel history shows both completed panels')
```

### File: `e2e/stories/operator/04-end-session.spec.ts`

```
test('End Session shows confirmation dialog')
test('Cancel in dialog keeps session ACTIVE')
test('Confirm ends session — status COMPLETED')
test('QR input and Run Panel disappear after session end')
test('fixture released to AVAILABLE after session end')
```

### File: `e2e/stories/operator/05-session-history.spec.ts`

```
test('Sessions tab shows completed session')
test('click session row navigates to detail')
test('completed session detail is read-only')
test('session shows all panels in history')
test('session results aggregation matches panel data')
```

### File: `e2e/stories/operator/06-failure-modes.spec.ts`

```
test('unit failure shows FAILED badge with error message')
test('failed unit skips subsequent stages')
test('mixed panel results show correct summary')
test('end session while panel running shows warning')
test('duplicate QR code shows warning dialog')
test('MTIB unreachable shows ERROR on all units')
```

**Total: ~44 Playwright tests**

---

## Backend Implementation Reference

Full model definitions, endpoint signatures, unit test lists, and gate criteria are in:
- **Stage 10** (`STAGE-10.md`) — Prisma models, API endpoints, reporter callbacks, WebSocket events, 25 unit tests
- **Stage 11** (`STAGE-11.md`) — Frontend pages, components, real-time WebSocket subscriptions, 20 vitest tests
- **Stage 12** (`STAGE-12.md`) — Manufacturing config wizard on product detail page, 15 vitest tests
- **Stage 13** (`STAGE-13.md`) — Playwright E2E tests, 30 tests

This story specifies the Operator's interaction with all of that infrastructure.

---

## Data Flow Summary

```
Operator clicks "New Session"
    │
    ▼
POST /v2/manufacturing/sessions
    │ creates ManufacturingSession (ACTIVE)
    │ locks Fixture (LOCKED)
    │ broadcasts: manufacturing_session_start
    ▼
Operator enters QR, clicks "Run Panel"
    │
    ▼
POST /v2/manufacturing/sessions/:id/panels
    │ creates ManufacturingPanel (RUNNING) + ManufacturingUnit per slot (RUNNING)
    │ triggers test runner (K8s Job or message queue)
    │ broadcasts: manufacturing_panel_start
    ▼
Test runner executes per unit:
    │
    ├─ Electrical stage
    │   └─ POST .../report/stage-result → broadcasts: manufacturing_stage_result
    ├─ Flash stage
    │   └─ POST .../report/stage-result → broadcasts: manufacturing_stage_result
    ├─ POST stage
    │   └─ POST .../report/stage-result → broadcasts: manufacturing_stage_result
    └─ Unit complete
        └─ POST .../report/unit-result → broadcasts: manufacturing_unit_result
    │
    ▼ (all units done)
POST .../report/panel-complete
    │ updates ManufacturingPanel (PASSED/FAILED)
    │ updates ManufacturingSession counts
    │ broadcasts: manufacturing_panel_complete
    ▼
Operator clicks "End Session"
    │
    ▼
POST /v2/manufacturing/sessions/:id/end
    │ sets ManufacturingSession status=COMPLETED
    │ releases Fixture (AVAILABLE)
    │ broadcasts: manufacturing_session_end
```
