# ADMIN User Story — Deep Implementation Spec

**Last reviewed:** 2026-04-08
**Status:** Draft
**Cross-references:** [SPEC.md](../SPEC.md) section 6.1, [STAGE-02](../stages/STAGE-02.md) through [STAGE-16](../stages/STAGE-16.md)

---

## Preconditions

- Fresh database: `prisma migrate deploy` completed, NO seed data
- All backend services running (`nx start platform`)
- Frontend on `:4200` (`npx nx serve app`)
- `AUTH_ENABLED=false` (dev login flow active)
- MTIB at 10.4.45.33:50053 reachable
- Bitbucket API token valid for `corekinect` workspace

---

## PHASE 1: LOGIN AND DASHBOARD (Empty System)

### Step 1.1 — Navigate to Login Page

**User Action:** Open `http://localhost:4200/login` in Playwright Chromium.

**Expected UI State:**
- Page title: `Login — Concord`
- Concord logo visible (`.logo-wrapper` containing `ConcordLogo` SVG)
- Environment badge visible: yellow pill with text `DEVELOPMENT` (class `bg-warning-muted text-warning`)
- Dev mode active: paragraph reads `Pick a role to login as`
- Four user cards rendered, one per role: Admin, Maintainer, Developer, Operator
- Each card is a `button.group.w-full` with role initial in a colored circle:
  - Admin: `text-error` / `bg-error-muted`, initial "A"
  - Maintainer: `text-warning` / `bg-warning-muted`, initial "M"
  - Developer: `text-accent` / `bg-accent-muted`, initial "D"
  - Operator: `text-success` / `bg-success-muted`, initial "O"
- Footer text: `Auth is disabled — click any user to login`

**Backend Verification:**
- `GET /v2/auth/dev-users` returns `{ data: { users: [...], environment: "development" } }`
- Response contains exactly 4 users with emails `admin@concord.dev`, `maintainer@concord.dev`, `developer@concord.dev`, `operator@concord.dev`
- No `@require_permissions` on this endpoint (public in dev mode)

**Assertion Strategy:**
```ts
await page.goto('/login');
await page.waitForSelector('text=Pick a role to login as');
const cards = page.locator('button.group.w-full');
await expect(cards).toHaveCount(4);
await expect(page.locator('text=Admin')).toBeVisible();
```

**Failure Modes:**
- Dev users endpoint returns empty → `isDevMode` stays false, shows email/password form instead. Check `AUTH_ENABLED=false` in backend config.
- Cards don't render → `fetchDevUsers()` failed silently. Intercept network and assert 200.

### Step 1.2 — Login as Admin

**User Action:** Click the first card (Admin row): `button.group.w-full` containing text "Admin".

**Expected UI State:**
- Spinner appears on the clicked card (`.animate-spin` inside the card)
- Page redirects to `/` (dashboard)
- JWT stored in localStorage via auth store

**Backend Verification:**
- `POST /v2/auth/dev-login` with body `{ email: "admin@concord.dev" }` returns JWT
- `GET /v2/auth/me` called after redirect, returns user with `role: "ADMIN"` and all 23+ permissions

**Assertion Strategy:**
```ts
await page.locator('button.group.w-full', { hasText: 'Admin' }).click();
await page.waitForURL('/');
await expect(page).toHaveTitle(/Dashboard/);
```

**Failure Modes:**
- `dev-login` returns error → red error alert appears: `.bg-error-muted` div with error text
- Redirect loop → auth store check fails. Verify JWT is set via `page.evaluate(() => localStorage.getItem('token'))`.

### Step 1.3 — Verify Dashboard Empty State

**Expected UI State:**
- `PageHeader` with title "Dashboard" and description "Overview of your Concord system."
- Empty state div: `div.rounded-xl.border-dashed` with text "No fixtures configured yet. Create fixtures in the Fixtures page to get started."
- No `DashboardFixtureCard` elements visible
- No `DashboardSummary` component rendered

**Backend Verification:**
- `GET /v2/dashboard/overview` returns `{ data: [] }` (no fixtures exist)

**Assertion Strategy:**
```ts
await expect(page.locator('text=No fixtures configured yet')).toBeVisible();
await expect(page.locator('[class*="dashboard-fixture-card"]')).toHaveCount(0);
```

### Step 1.4 — Verify Full Admin Sidebar

**Expected UI State:** All navigation sections visible in sidebar (`sidebar.svelte`):

| Item | Icon | Path | Permission Gate |
|------|------|------|----------------|
| Products | `Package` | `/products` | `products:view` |
| Builds | `Hammer` | `/builds` | `builds:view` |
| Validation | `FlaskConical` | `/validation` | `validation:view` |
| Manufacturing | `Factory` | `/manufacturing` | `manufacturing:view` |
| Fixtures | `Cpu` | `/fixtures` | `fixtures:view` |
| Users (admin section) | `Users` | `/users` | `users:view` |
| Kubernetes (system section) | `KubernetesIcon` | `/kubernetes` | `system:view` |

- Admin section toggle button visible (label "Admin" with `Shield` icon)
- System section toggle button visible (label "System" with `ScanEye` icon)
- View-As-Role toggle available (only in dev environment where `isDev=true`)
- View-As options: "Your View", "Maintainer", "Developer", "Operator"

**Assertion Strategy:**
```ts
const sidebar = page.locator('nav');
for (const label of ['Products', 'Builds', 'Validation', 'Manufacturing', 'Fixtures']) {
  await expect(sidebar.locator(`a[href="/${label.toLowerCase()}"]`)).toBeVisible();
}
// Expand admin section and verify Users link
await sidebar.locator('button', { hasText: 'Admin' }).click();
await expect(sidebar.locator('a[href="/users"]')).toBeVisible();
// Expand system section and verify Kubernetes link
await sidebar.locator('button', { hasText: 'System' }).click();
await expect(sidebar.locator('a[href="/kubernetes"]')).toBeVisible();
```

---

## PHASE 2: BITBUCKET SETUP (API-only, no UI)

### Step 2.1 — Sync concord-main Branch in alpha_fw

**User Action:** None (API call from test harness).

**API Call:** Bitbucket REST API — create or force-update `concord-main` branch to match `main` HEAD in `corekinect/alpha_fw`.

**Assertion Strategy:**
```ts
// Use Bitbucket API via fetch or @atlassian/bitbucket
const res = await bitbucket.refs.createBranch({
  workspace: 'corekinect', repo_slug: 'alpha_fw',
  _body: { name: 'concord-main', target: { hash: mainHeadSha } }
});
expect([200, 201]).toContain(res.status);
```

**Failure Modes:**
- Branch already exists → use `PUT` to update ref. 409 means branch exists; fetch and compare SHA.
- Auth failure → check Bitbucket API token env var.

### Step 2.2 — Sync concord-main Branch in alpha_mfg_fw

Same as 2.1 but for repo `alpha_mfg_fw`.

### Step 2.3 — Create Feature Branch in alpha_fw

**API Call:** Create branch `e2e/admin-test-{timestamp}` from `concord-main` HEAD.

**Cleanup Tag:** Store branch name for Phase 13 deletion.

### Step 2.4 — Open PR: Feature Branch to concord-main

**API Call:** Create PR in `corekinect/alpha_fw`:
- Source: `e2e/admin-test-{timestamp}`
- Destination: `concord-main`
- Title: `[E2E] Admin story test PR`

**Cleanup Tag:** Store PR ID for Phase 13 cleanup.

---

## PHASE 3: PRODUCT CREATION

### Step 3.1 — Navigate to Products Page (Empty State)

**User Action:** Click "Products" in sidebar → navigates to `/products`.

**Expected UI State:**
- `PageHeader` title: "Products", description: "Manage products, firmware stages, and builds."
- "New Product" button visible (class `bg-accent`, contains `Plus` icon and text "New Product") — visible because Admin has `products:manage`
- `EmptyState` component with text "No products yet"
- Filter bar present with search input (placeholder "Search products...") and status filter dropdown

**Backend Verification:**
- `GET /v2/products` returns `{ data: [] }` — permission checked: `products:view`

**Assertion Strategy:**
```ts
await page.locator('a[href="/products"]').click();
await page.waitForURL('/products');
await expect(page.locator('text=No products yet')).toBeVisible();
await expect(page.locator('button', { hasText: 'New Product' })).toBeVisible();
```

### Step 3.2 — Open Product Creation Wizard

**User Action:** Click "New Product" button.

**Expected UI State:**
- `ProductCreationWizard` component appears (replaces/overlays the empty state)
- Step indicator shows 4 steps: "Branch", "Board", "Configure", "Create"
- Step 1 active: branch selection dropdown
- Loading spinner while branches load from `GET /v2/products/boards/branches`
- Branch list populates — "main" auto-selected if present
- Tags list may also appear

**Backend Verification:**
- `GET /v2/products/boards/branches` → returns `{ data: { branches: ["main", ...], tags: [...] } }`
- Permission: `products:view`

**Assertion Strategy:**
```ts
await page.locator('button', { hasText: 'New Product' }).click();
await page.waitForSelector('text=Branch');
// Wait for branches to load
await page.waitForSelector('text=main', { timeout: 10000 });
```

### Step 3.3 — Step 1: Select Branch

**User Action:** Ensure "main" is selected (auto-selected), click "Next" button.

**Expected UI State:**
- Next button (contains `ChevronRight` icon) becomes enabled when branch is selected
- Clicking Next transitions to Step 2

**Assertion Strategy:**
```ts
// "main" should be auto-selected
const nextBtn = page.locator('button', { hasText: /Next|ChevronRight/ });
await expect(nextBtn).toBeEnabled();
await nextBtn.click();
await page.waitForSelector('text=Board'); // Step 2 label active
```

### Step 3.4 — Step 2: Select Board Family

**Expected UI State:**
- Loading spinner while `GET /v2/products/boards/discover?branch=main` loads
- Board family cards appear (e.g., "alpha")
- Each card shows family name, SoC count, revision count

**Backend Verification:**
- `GET /v2/products/boards/discover?branch=main` → returns array of `BoardSummary` objects
- Permission: `products:view`

**User Action:** Click "alpha" board family card, then click "Next".

**Assertion Strategy:**
```ts
await page.waitForSelector('text=alpha', { timeout: 15000 });
await page.locator('button', { hasText: 'alpha' }).click();
await page.locator('button', { hasText: /Next/ }).click();
```

### Step 3.5 — Step 3: Configure Board Detail

**Expected UI State:**
- Loading spinner while `GET /v2/products/boards/discover/alpha?branch=main` loads
- Auto-populated fields:
  - Product name: "Alpha" (capitalized from family)
  - Product slug: "alpha"
  - FW repo: "alpha_fw" with status indicator (checking → exists/not_found)
  - MFG FW repo: "alpha_mfg_fw" with status indicator
- Revision configurations for each board revision (e.g., "b0"):
  - SoCs listed with role assignment (app/comms)
  - AppID fields (initially 0)
  - Device type and variant fields

**Backend Verification:**
- `GET /v2/products/boards/discover/alpha?branch=main` → returns `BoardDetail` with revisions, SoCs
- `GET /v2/products/repos/check?slug=alpha_fw` → `{ data: { exists: true } }`
- `GET /v2/products/repos/check?slug=alpha_mfg_fw` → `{ data: { exists: true } }`

**User Action:**
1. Set AppID for nrf52840 (app): type `109` in the appId input
2. Set AppID for nrf9151 (comms): type `108` in the appId input
3. Verify repo check shows green (exists)
4. Click "Next"

**Assertion Strategy:**
```ts
// Wait for board detail to load
await page.waitForSelector('text=alpha_fw');
// Fill in AppIDs — find inputs near the SoC labels
const appIdInputs = page.locator('input[type="number"]');
// Set app processor AppID to 109
await appIdInputs.nth(0).fill('109');
// Set comms processor AppID to 108
await appIdInputs.nth(1).fill('108');
// Wait for repo check to complete
await page.waitForSelector('text=exists', { timeout: 5000 });
await page.locator('button', { hasText: /Next/ }).click();
```

### Step 3.6 — Step 4: Review and Create

**Expected UI State:**
- Review summary showing: product name, slug, repos, board revisions, SoCs, AppIDs
- "Create" button (primary accent color)

**User Action:** Click "Create" button.

**Backend Verification:**
- `POST /v2/products` with body including:
  - `name`, `slug`, `fwRepoSlug`, `mfgFwRepoSlug`
  - `board` object with family, revisions, SoCs, targets, AppIDs
- Permission: `products:manage`
- Creates: Product + Board + BoardRevision + ProductTarget records
- Audit log entry: `product.create`
- Returns 201 with product ID

**Assertion Strategy:**
```ts
const [response] = await Promise.all([
  page.waitForResponse(res => res.url().includes('/v2/products') && res.request().method() === 'POST'),
  page.locator('button', { hasText: 'Create' }).click(),
]);
expect(response.status()).toBe(201);
```

**Failure Modes:**
- Duplicate slug → 409 Conflict. Error alert shows in wizard.
- Repo check failed → wizard may still allow creation (repo check is advisory, not blocking).

### Step 3.7 — Verify Product in List

**Expected UI State:**
- Wizard closes (`onCreated` callback fires, `showWizard = false`)
- Product list refreshes (`fetchProducts()` called)
- "Alpha" product appears as a row in the product list
- Row shows: name "Alpha", active badge (`bg-success-muted text-success`), repo links
- Stage pills show all 5 stages as disabled (grey `bg-surface-2`) since no config yet
- "No products yet" empty state is gone

**Assertion Strategy:**
```ts
await expect(page.locator('text=Alpha')).toBeVisible();
await expect(page.locator('.bg-success-muted', { hasText: 'Active' })).toBeVisible();
await expect(page.locator('text=No products yet')).not.toBeVisible();
```

### Step 3.8 — Navigate to Product Detail

**User Action:** Click the "Alpha" product row.

**Expected UI State:**
- URL changes to `/products/{productId}`
- `ProductDetail` component renders with tabs
- 5 tabs visible in product detail (defined in `tabs/` directory):
  - Overview, Hardware, Assets, Manufacturing, Validation
- Product name "Alpha" in header
- FW repo and MFG FW repo links visible (Bitbucket external links)

**Backend Verification:**
- `GET /v2/products/{productId}` returns full product with boards, revisions, stageConfigs
- Permission: `products:view`

**Assertion Strategy:**
```ts
await page.locator('text=Alpha').first().click();
await page.waitForURL(/\/products\/.+/);
await expect(page.locator('text=Overview')).toBeVisible();
await expect(page.locator('text=Hardware')).toBeVisible();
await expect(page.locator('text=Validation')).toBeVisible();
```

---

## PHASE 4: DASHBOARD VERIFICATION (Post Product Creation)

### Step 4.1 — Return to Dashboard

**User Action:** Click "Dashboard" link in sidebar (LayoutDashboard icon, path `/`).

**Expected UI State:**
- Dashboard still shows empty state for fixtures: "No fixtures configured yet."
- This confirms dashboard depends on fixtures, not products

**Assertion Strategy:**
```ts
await page.locator('a[href="/"]').click();
await page.waitForURL('/');
await expect(page.locator('text=No fixtures configured yet')).toBeVisible();
```

---

## PHASE 5: STAGE CONFIGURATION

### Step 5.1 — Navigate to Product Validation Tab

**User Action:** Navigate to `/products/{productId}`, click "Validation" tab.

**Expected UI State:**
- Validation tab content loads showing stage configuration UI
- `ProductStages` component renders with 5 stage cards
- Each card shows stage number, name, and status (all "Off" initially)
- Stage names: Smoke (1), Driver (2), Integration (3), Regression (4), FUOTA (5)

**Backend Verification:**
- `GET /v2/products/{productId}/stages` returns empty array or 5 unconfigured stages
- Permission: `builds:view`

### Step 5.2 — Configure Stage 1 (Smoke)

**User Action:** Click on Stage 1 card → opens `StageConfigWizard`.

**Expected UI State:**
- Stage config wizard modal/panel opens
- Fields: board revision selector, watch branch, trigger types, signing key, recipe editor, build matrix

**User Actions (sequential):**
1. Select board revision: "Alpha B0" from dropdown
2. Set watch branch: type `concord-main`
3. Check trigger types: `pr_push` and `manual`
4. Recipe editor: load default template or type build recipe YAML
5. Build matrix: configure jobs (target + variant combinations)
6. Click "Save"

**Backend Verification:**
- `POST /v2/products/{productId}/stages` or `PUT /v2/products/{productId}/stages/1`
- Body includes: `{ stage: 1, enabled: true, boardRevisionId, watchBranch, triggerTypes, ... }`
- Permission: `builds:manage`
- Audit log: `stage_config.create` or `stage_config.update`

**Assertion Strategy:**
```ts
// After save, verify stage card shows as enabled
await expect(page.locator('[title="Smoke: Enabled"]')).toBeVisible();
```

### Step 5.3 through 5.6 — Configure Stages 2-5

Repeat Step 5.2 for stages 2 (Driver), 3 (Integration), 4 (Regression), 5 (FUOTA).

Each stage uses the same wizard flow. Key differences:
- Stage 2-3: hardware-required stages, may need different recipe
- Stage 5: FUOTA stage, requires CoreCloud integration config

### Step 5.7 — Verify All Stages Enabled

**Expected UI State:**
- All 5 stage pills in the product list row show as enabled (colored backgrounds):
  - SM: `bg-blue-400 text-white`
  - DR: `bg-cyan-400 text-white`
  - IN: `bg-amber-400 text-white`
  - RG: `bg-purple-400 text-white`
  - FU: `bg-red-400 text-white`

**Assertion Strategy:**
```ts
await page.goto('/products');
const stagePills = page.locator('.w-5.h-5.text-white');
await expect(stagePills).toHaveCount(5);
```

---

## PHASE 6: BUILD PIPELINE

### Step 6.1 — Wait for Git Poller Detection

**User Action:** None (automated — git-poller runs on 60s interval).

**Backend Process:**
- Git poller detects PR from Phase 2 on `concord-main` branch
- Sends `POST /v2/builds/events` with repo event payload
- API creates BuildRun with build matrix based on stage configs

**Assertion Strategy:**
```ts
// Poll builds API until a BuildRun appears (max 90s for poller cycle + processing)
let buildRun = null;
for (let i = 0; i < 18; i++) {
  const res = await apiRequest('GET', '/v2/builds/runs');
  if (res.data?.length > 0) { buildRun = res.data[0]; break; }
  await page.waitForTimeout(5000);
}
expect(buildRun).not.toBeNull();
```

### Step 6.2 — Navigate to Builds Page

**User Action:** Click "Builds" in sidebar → `/builds`.

**Expected UI State:**
- `PageHeader` title: implied by `builds/+page.svelte`
- Filter bar with: status filter, stage filter, trigger type filter, date range, product filter
- At least one BuildRun row visible
- Row shows: commit hash, branch name, trigger badge (`TriggerBadge` component), stage pills, status badge
- Status badge initially shows `PENDING` or `BUILDING` (`StatusBadge` component)

**Backend Verification:**
- `GET /v2/builds/runs` returns paginated list with the new BuildRun
- Permission: `builds:view`

**Assertion Strategy:**
```ts
await page.locator('a[href="/builds"]').click();
await page.waitForURL('/builds');
await expect(page.locator('[class*="status-badge"]').first()).toBeVisible();
```

### Step 6.3 — Monitor Build Progress

**User Action:** Click on the BuildRun row → navigates to `/builds/runs/{runId}`.

**Expected UI State:**
- Build run detail page loads
- Build jobs listed with matrix labels (one per target/variant combination)
- Each job shows status transitions: QUEUED → CLONING → BUILDING → SUCCESS/FAILED
- Live log streaming visible (if build service is connected)
- Progress indicators update in real-time

**Backend Verification:**
- `GET /v2/builds/runs/{runId}` returns run detail with embedded jobs
- `GET /v2/builds/{buildId}/log` streams build output
- Permission: `builds:view`

### Step 6.4 — Wait for Build Completion

**Assertion Strategy:**
```ts
// Poll until all jobs in the run are terminal (SUCCESS, FAILED, CACHED)
// Timeout: 25 minutes (firmware builds take 5-20 min)
await expect(async () => {
  const res = await apiRequest('GET', `/v2/builds/runs/${runId}`);
  const jobs = res.data.jobs || [];
  const allDone = jobs.every(j => ['SUCCESS', 'FAILED', 'CACHED'].includes(j.status));
  expect(allDone).toBe(true);
}).toPass({ timeout: 25 * 60 * 1000, intervals: [10_000] });
```

**Failure Modes:**
- Build service not running → jobs stay QUEUED forever. Check `nx start platform` includes build service.
- Recipe error → jobs FAILED. Check build log via `GET /v2/builds/{buildId}/log`.

### Step 6.5 — Build Artifact Verification

**User Action:** On build run detail page, locate artifacts section.

**Expected UI State:**
- Artifact list shows compiled `.hex` files for each target
- Download links/buttons present for each artifact

**Backend Verification:**
- `GET /v2/builds/{buildId}/artifacts` returns artifact metadata (name, size, storageKey)
- `GET /v2/builds/{buildId}/artifacts/{name}` returns presigned download URL
- Permission: `builds:view`

**Assertion Strategy:**
```ts
// Verify artifacts exist and have non-zero size
const artifactRes = await apiRequest('GET', `/v2/builds/${buildId}/artifacts`);
expect(artifactRes.data.length).toBeGreaterThan(0);
for (const artifact of artifactRes.data) {
  expect(artifact.size).toBeGreaterThan(0);
  // Download and verify file size matches
  const downloadRes = await apiRequest('GET', `/v2/builds/${buildId}/artifacts/${artifact.name}`);
  expect(downloadRes.status).toBe(200);
}
```

---

## PHASE 7: BUILD CACHING VERIFICATION

### Step 7.1 — Create Second Branch and PR

**API Call:** Create branch `e2e/admin-cache-{timestamp}` from same `concord-main` HEAD. Open PR to `concord-main`.

### Step 7.2 — Wait for Second BuildRun

Same polling as Step 6.1. Second BuildRun should appear.

### Step 7.3 — Verify CACHED Status

**Expected:** Jobs in second BuildRun show `CACHED` status because `buildFingerprint` matches.

**Backend Verification:**
- `GET /v2/builds/runs/{runId2}` → jobs have `status: "CACHED"` and `reusedFromId` pointing to original jobs

**Assertion Strategy:**
```ts
const run2 = await apiRequest('GET', `/v2/builds/runs/${runId2}`);
for (const job of run2.data.jobs) {
  expect(job.status).toBe('CACHED');
  expect(job.reusedFromId).toBeTruthy();
}
```

---

## PHASE 8: FIXTURE CREATION

### Step 8.1 — Navigate to Fixtures (Empty State)

**User Action:** Click "Fixtures" in sidebar → `/fixtures`.

**Expected UI State:**
- Tabs: "Fixtures" (active, `Wrench` icon) and "Designs" (`Ruler` icon)
- `EmptyState` component visible
- "New Fixture" button visible (class `bg-accent`) — Admin has `fixtures:manage`
- Create form hidden initially

**Backend Verification:**
- `GET /v2/fixtures` returns empty array
- Permission: `fixtures:view`

### Step 8.2 — Create Fixture Design

**User Action:** Click "Designs" tab, then click create button.

**Expected UI State:**
- `FixtureDesigns` component renders
- Create form appears with fields: name, board revision, revision string, capabilities

**User Actions:**
1. Name: type "Alpha E2E Fixture v1.2"
2. Board revision: select "Alpha B0" from dropdown
3. Revision: type "1.2"
4. Capabilities: select/add `power`, `gpio`, `uart`, `jlink`
5. Click "Create" / "Save"

**Backend Verification:**
- `POST /v2/fixtures/designs` with body `{ name, boardRevisionId, revision, capabilities }`
- Permission: `fixtures:manage`
- Returns 201 with design ID
- Audit log: `fixture_design.create`

**Assertion Strategy:**
```ts
const [response] = await Promise.all([
  page.waitForResponse(r => r.url().includes('/v2/fixtures/designs') && r.request().method() === 'POST'),
  page.locator('button', { hasText: /Create|Save/ }).click(),
]);
expect(response.status()).toBe(201);
```

### Step 8.3 — Create Fixture Instance

**User Action:** Switch to "Fixtures" tab, click "New Fixture" / create button.

**Expected UI State:**
- Form card appears with fields:
  - Name: text input
  - Product: dropdown (shows "Alpha")
  - Type: dropdown with "MANUFACTURING" and "VALIDATION"
  - Design: dropdown (shows "Alpha E2E Fixture v1.2 (1.2)")
  - Slot count: number input (default 1)
  - Description: text area

**User Actions:**
1. Name: type "E2E Dev Bench"
2. Product: select "Alpha"
3. Type: select "VALIDATION"
4. Board revision: select from dependent dropdown (loads after product selected)
5. Design: select "Alpha E2E Fixture v1.2 (1.2)"
6. Slot count: 1
7. Click "Create"

**Backend Verification:**
- `POST /v2/fixtures` with body including `{ name, productId, type: "VALIDATION", designId, slotCount }`
- Permission: `fixtures:manage`
- Creates Fixture + FixtureSlot records
- Returns 201

### Step 8.4 — Assign Node (MTIB) to Slot

**User Action:** Click on the newly created fixture to open detail panel (`FixtureDetail`), then assign node to slot.

**Expected UI State:**
- `FixtureDetail` component shows fixture name, status, slots
- `SlotAssignment` component shows slot 0 as unassigned
- Node assignment dropdown or button

**Backend Verification:**
- Node may need to be created first: `POST /v2/devices/mtibs` or use existing discovered nodes
- `POST /v2/fixtures/{fixtureId}/slots/{slotId}/assign` with `{ nodeId }`
- Auto-deploys MTIB server to K8s (or verifies existing deployment)
- Permission: `fixtures:manage`

### Step 8.5 — Verify Fixture Status AVAILABLE

**Expected UI State:**
- Fixture card/detail shows status badge: "AVAILABLE"
- Slot shows assigned node with IP 10.4.45.33
- Deploy status indicator (green/active)

**Backend Verification:**
- `GET /v2/fixtures/{fixtureId}` → `{ status: "AVAILABLE", slots: [{ nodeId: ..., node: { ip: "10.4.45.33" } }] }`

---

## PHASE 9: VALIDATION QUEUE AND EXECUTION

### Step 9.1 — Navigate to Validation Page

**User Action:** Click "Validation" in sidebar → `/validation`.

**Expected UI State:**
- Validation hub page loads
- Sub-navigation links: runs list, queue, designs, benches
- Queue section should show entries created by build completion

### Step 9.2 — Verify Queue Entries Created

**User Action:** Navigate to `/validation/queue`.

**Expected UI State:**
- Queue entries visible (one per enabled stage that has matching build artifacts)
- Each entry shows: product name, stage, status (QUEUED initially, then may auto-transition)

**Backend Verification:**
- `GET /v2/sessions/queue` → entries with `status: "QUEUED"` or `"ASSIGNED"`
- Permission: `validation:view`

### Step 9.3 — Wait for Queue Assignment

**Backend Process:**
- Scheduler (10s polling) detects AVAILABLE fixture matching product + board revision
- Highest-priority queue entry transitions: QUEUED → ASSIGNED → RUNNING
- Fixture status changes to LOCKED
- Session created, K8s Job spawned

**Assertion Strategy:**
```ts
await expect(async () => {
  const res = await apiRequest('GET', '/v2/sessions/queue');
  const assigned = res.data.find(e => e.status === 'RUNNING' || e.status === 'ASSIGNED');
  expect(assigned).toBeTruthy();
}).toPass({ timeout: 60_000, intervals: [5_000] });
```

### Step 9.4 — Validation Run Detail Page

**User Action:** Navigate to `/validation/runs/{runId}` (click on running session from queue or runs list).

**Expected UI State (validation run detail components from `lib/components/validation/`):**

1. **RunHeader** (`run-header.svelte`): Status badge (RUNNING), duration timer, progress bar
2. **StageSidebar** (`stage-sidebar.svelte`): Stage selector with per-stage test counts
3. **TestList** (`test-list.svelte`): Expandable test results with:
   - Test name, status (pass/fail/running/skipped), duration
   - Error details for failures
   - Measurement values
4. **ChartPanel** (`chart-panel.svelte`): Contains:
   - `PowerChart` (`power-chart.svelte`): Real-time power consumption graph
   - `AccelChart` (`accel-chart.svelte`): Accelerometer data graph
5. **UartPanel** (`uart-panel.svelte`): Live UART terminal output
   - `UartTerminal` (`uart-terminal.svelte`): Scrollable terminal with device boot logs
6. **ResizeLayout** (`resize-layout.svelte`): Draggable split between test list and charts/UART
7. **CancelDialog** (`cancel-dialog.svelte`): Available via cancel button
8. **TimelineWidget** (`timeline-widget.svelte`): Visual test timeline

**Backend Verification:**
- `GET /v2/sessions/{runId}` → session detail with status, start/end times
- `GET /v2/sessions/{runId}/executions` → test execution list
- `GET /v2/sessions/{runId}/telemetry/manifest` → available telemetry channels
- `GET /v2/sessions/{runId}/telemetry/{channel}` → channel data points
- WebSocket on `/kubernetes` namespace receives events: `validation_test_start`, `validation_test_result`
- Permission: `validation:view`

**Assertion Strategy:**
```ts
await page.goto(`/validation/runs/${runId}`);
// Verify core layout components render
await expect(page.locator('text=RUNNING').or(page.locator('text=PASSED'))).toBeVisible({ timeout: 10_000 });
// Verify test list populates
await expect(page.locator('[class*="test-list"] [class*="test-item"]').first()).toBeVisible({ timeout: 120_000 });
// Verify UART panel has content
await expect(page.locator('[class*="uart-panel"]')).toBeVisible();
```

### Step 9.5 — Wait for Session Completion

**Assertion Strategy:**
```ts
// Real validation can take 5-30 minutes depending on stage
await expect(async () => {
  const res = await apiRequest('GET', `/v2/sessions/${runId}`);
  expect(['PASSED', 'FAILED', 'CANCELLED']).toContain(res.data.status);
}).toPass({ timeout: 35 * 60 * 1000, intervals: [15_000] });
```

### Step 9.6 — Verify Session Results

**Expected UI State:**
- RunHeader status badge: "PASSED" (green) or "FAILED" (red)
- TestList shows all tests with final status
- Duration shown in header
- Charts show complete data range

**Backend Verification:**
- `GET /v2/sessions/{runId}` → `status: "PASSED"` or `"FAILED"`, `endedAt` set
- `GET /v2/sessions/{runId}/executions` → all executions have terminal status
- Fixture status back to AVAILABLE: `GET /v2/fixtures/{fixtureId}` → `status: "AVAILABLE"`

### Step 9.7 — Verify Next Queue Entry Auto-Starts

**Backend Process:** After fixture release, scheduler picks up next QUEUED entry.

**Assertion Strategy:**
```ts
// If more queue entries exist, the next one should start within 20s
const queueRes = await apiRequest('GET', '/v2/sessions/queue');
const nextQueued = queueRes.data.find(e => e.status === 'QUEUED');
if (nextQueued) {
  await expect(async () => {
    const entry = await apiRequest('GET', `/v2/sessions/queue/${nextQueued.id}`);
    expect(['ASSIGNED', 'RUNNING']).toContain(entry.data.status);
  }).toPass({ timeout: 30_000 });
}
```

---

## PHASE 10: MANUFACTURING CONFIG AND SESSION

**Note:** Manufacturing backend does not exist yet (`apps/backend/http-api/src/api/v2/manufacturing/` is missing). This phase documents the target behavior to be built in Stages 10-13.

### Step 10.1 — Create Manufacturing Fixture Design

**User Action:** Navigate to `/fixtures`, "Designs" tab. Create a new design with same board revision but for manufacturing.

**Backend Verification:**
- `POST /v2/fixtures/designs` with manufacturing-appropriate capabilities

### Step 10.2 — Create Manufacturing Fixture Instance

**User Action:** Create fixture with `type: "MANUFACTURING"`.

**Backend Verification:**
- `POST /v2/fixtures` with `{ type: "MANUFACTURING", ... }`

### Step 10.3 — Manufacturing Configuration Wizard

**User Action:** Navigate to product detail → "Manufacturing" tab. Open manufacturing config wizard.

**Expected UI State (TO BE BUILT):**
- Enable manufacturing for Alpha B0 revision
- Stage configuration: Electrical, Flash, POST
- Firmware source selection (from completed builds)
- Personalization settings (CoreOps integration)
- Pass/fail criteria

**Backend Verification (TO BE BUILT):**
- Manufacturing config endpoints (similar to `PUT /v2/products/{productId}/stages/{stage}`)

### Step 10.4 — Start Manufacturing Session

**User Action:** Navigate to `/manufacturing`, click "New Session" on the manufacturing fixture.

**Expected UI State (TO BE BUILT):**
- Session created, fixture locked
- QR code input field
- "Run Panel" button

**Backend Verification (TO BE BUILT):**
- `POST /v2/manufacturing/sessions` → creates session, locks fixture
- Permission: `manufacturing:run`

### Step 10.5 — Run Manufacturing Panel

**User Action:** Enter test QR code, click "Run Panel".

**Expected UI State (TO BE BUILT):**
- Per-unit results grid (one card per slot)
- Stage-by-stage progress: Electrical → Flash → POST
- Real-time status updates via WebSocket
- Pass/fail indication per unit

**Backend Verification (TO BE BUILT):**
- `POST /v2/manufacturing/sessions/{id}/panels`
- Reporter callbacks stream results

### Step 10.6 — End Manufacturing Session

**User Action:** Click "End Session".

**Backend Verification (TO BE BUILT):**
- `POST /v2/manufacturing/sessions/{id}/end`
- Fixture released to AVAILABLE
- Permission: `manufacturing:run`

---

## PHASE 11: USER MANAGEMENT

### Step 11.1 — Navigate to Users Page

**User Action:** Expand "Admin" section in sidebar, click "Users" → `/users`.

**Expected UI State:**
- Page title via `PageHeader`
- Tabs: "Users" (active) and "Permission Sets" (`PermissionSetsTab` component)
- Existing dev users listed (admin, maintainer, developer, operator)
- Create button visible (Admin has `users:manage`)

**Backend Verification:**
- `GET /v2/users` → list of seeded dev users
- Permission: `users:view`

### Step 11.2 — Create Maintainer Test User

**User Action:** Click create user button. Fill form:
- Email: `test-maintainer@e2e.test`
- Name: `E2E Maintainer`
- Permission set: select from dropdown (default or "Maintainer")

**Backend Verification:**
- `POST /v2/users` with `{ email, name, permissionSetId }` → 201
- Permission: `users:manage`
- Audit log: `user.create`

### Step 11.3 — Create Developer Test User

Same as 11.2 with `test-developer@e2e.test`, name `E2E Developer`.

### Step 11.4 — Create Operator Test User

Same as 11.2 with `test-operator@e2e.test`, name `E2E Operator`.

### Step 11.5 — Verify All Users in List

**Assertion Strategy:**
```ts
await expect(page.locator('text=test-maintainer@e2e.test')).toBeVisible();
await expect(page.locator('text=test-developer@e2e.test')).toBeVisible();
await expect(page.locator('text=test-operator@e2e.test')).toBeVisible();
```

### Step 11.6 — Create Custom Permission Set

**User Action:** Click "Permission Sets" tab. Click create button.

**Expected UI State:**
- `PermissionSetsTab` component renders
- Create form with: name, description, permission checkboxes

**User Actions:**
1. Name: `E2E Custom Set`
2. Description: `Custom permission set for E2E testing`
3. Select permissions: `products:view`, `builds:view`, `validation:view`, `fixtures:view`
4. Click "Create"

**Backend Verification:**
- `POST /v2/permissions` with `{ name, description, permissions }` → 201
- Permission: `permissions:manage`

### Step 11.7 — Assign Custom Permission Set to Developer

**User Action:** Return to "Users" tab, click edit on `test-developer@e2e.test`, change permission set to "E2E Custom Set".

**Backend Verification:**
- `PUT /v2/users/{userId}` with `{ permissionSetId: customSetId }`
- Permission: `users:manage`

### Step 11.8 — Create API Key

**User Action:** Navigate to API keys section (may be a tab or separate route).

**Backend Verification:**
- `POST /v2/api-keys` with `{ name: "E2E Test Key" }` → 201
- Response includes `key` field (plaintext, shown only once)
- Permission: `api-keys:manage`

**Assertion Strategy:**
```ts
const res = await apiRequest('POST', '/v2/api-keys', { name: 'E2E Test Key' });
expect(res.status).toBe(201);
expect(res.data.key).toMatch(/^ck_/); // API key prefix
storedApiKey = res.data.key;
// After creation, list shows prefix only
const listRes = await apiRequest('GET', '/v2/api-keys');
const found = listRes.data.find(k => k.name === 'E2E Test Key');
expect(found.keyPrefix).toBeTruthy();
expect(found.key).toBeUndefined(); // Full key never returned on list
```

---

## PHASE 12: PERMISSION VERIFICATION (View-As-Role)

### Step 12.1 — Simulate Maintainer Role

**User Action:** Open View-As dropdown in sidebar, select "Maintainer".

**Expected UI State:**
- Page reloads (View-As triggers `window.location.reload()`)
- Sidebar changes:
  - Products, Builds, Validation, Manufacturing, Fixtures: still visible
  - Users: HIDDEN (Maintainer lacks `users:manage` and `users:view` only gets view)
  - Kubernetes: still visible (Maintainer has `system:view`)
  - View-As toggle still available

**Backend Verification:**
- All subsequent requests include `X-View-As-Role: MAINTAINER` header
- `GET /v2/auth/me` returns effective permissions for MAINTAINER role
- `_resolve_effective_role()` in `decorators.py` returns "MAINTAINER" when header present

**Assertion Strategy:**
```ts
// Select View-As Maintainer
await page.locator('button', { hasText: /View As|Your View/ }).click();
await page.locator('text=Maintainer').click();
await page.waitForLoadState('networkidle');
// Verify Users link is hidden
const sidebar = page.locator('nav');
await expect(sidebar.locator('a[href="/users"]')).not.toBeVisible();
// Verify Products still visible
await expect(sidebar.locator('a[href="/products"]')).toBeVisible();
```

### Step 12.2 — Simulate Developer Role

**User Action:** Select "Developer" from View-As dropdown.

**Expected UI State:**
- Sidebar visible: Products, Builds, Validation, Manufacturing, Fixtures
- Sidebar hidden: Users, Kubernetes
- View-As toggle NOT available for Developer (only Admin/Maintainer get it) — BUT since actual user is Admin using View-As, the toggle persists (backend enforces, UI shows based on actual role)

**Backend Verification:**
- `X-View-As-Role: DEVELOPER` sent on requests
- `POST /v2/users` with this header → 403 (Developer lacks `users:manage`)
- `POST /v2/products` with this header → 403 (Developer lacks `products:manage`)

### Step 12.3 — Simulate Operator Role

**User Action:** Select "Operator" from View-As dropdown.

**Expected UI State:**
- Sidebar visible: Dashboard, Manufacturing ONLY
- Sidebar hidden: Products, Builds, Validation, Fixtures, Users, Kubernetes
- Manufacturing page accessible

**Assertion Strategy:**
```ts
await page.waitForLoadState('networkidle');
const sidebar = page.locator('nav');
await expect(sidebar.locator('a[href="/manufacturing"]')).toBeVisible();
await expect(sidebar.locator('a[href="/products"]')).not.toBeVisible();
await expect(sidebar.locator('a[href="/builds"]')).not.toBeVisible();
await expect(sidebar.locator('a[href="/validation"]')).not.toBeVisible();
await expect(sidebar.locator('a[href="/fixtures"]')).not.toBeVisible();
```

### Step 12.4 — Reset View-As-Role

**User Action:** Select "Your View" from View-As dropdown.

**Expected UI State:**
- Full Admin sidebar restored
- All sections visible again

---

## PHASE 13: CLEANUP

### Step 13.1 — Delete Test Users

**API Calls:**
```ts
await apiRequest('DELETE', `/v2/users/${maintainerUserId}`);
await apiRequest('DELETE', `/v2/users/${developerUserId}`);
await apiRequest('DELETE', `/v2/users/${operatorUserId}`);
```
Permission: `users:manage`. Soft-deletes (sets `active: false`).

### Step 13.2 — Delete Custom Permission Set

**API Call:** `DELETE /v2/permissions/{customSetId}` → Permission: `permissions:manage`

**Failure Modes:**
- Users still assigned → must reassign or delete users first (Step 13.1 handles this).

### Step 13.3 — Delete API Key

**API Call:** `DELETE /v2/api-keys/{keyId}` → Permission: `api-keys:manage`

### Step 13.4 — Cancel Running Sessions

**API Calls:**
```ts
const sessions = await apiRequest('GET', '/v2/sessions?status=RUNNING');
for (const session of sessions.data) {
  await apiRequest('POST', `/v2/sessions/${session.id}/cancel`);
}
```
Permission: `validation:manage`

### Step 13.5 — Delete Fixtures

Order matters: instances before designs, designs only if no instances reference them.

```ts
// Delete fixture instances
const fixtures = await apiRequest('GET', '/v2/fixtures');
for (const f of fixtures.data) {
  await apiRequest('DELETE', `/v2/fixtures/${f.id}`);
}
// Delete designs
const designs = await apiRequest('GET', '/v2/fixtures/designs');
for (const d of designs.data) {
  await apiRequest('DELETE', `/v2/fixtures/designs/${d.id}`);
}
```
Permission: `fixtures:manage`

**Failure Modes:**
- Fixture has session history → 409 Conflict. Must delete sessions first.
- Fixture is LOCKED → cancel session first.

### Step 13.6 — Delete Product

**API Call:** `DELETE /v2/products/{productId}` → Permission: `products:manage`

Cascades: Board, BoardRevision, ProductTarget, ProductStageConfig, RecipeVersion, FirmwareSet, ProductAccess.

**Failure Modes:**
- Product has BuildRun references → 409 Conflict. May need to delete/archive builds first.

### Step 13.7 — Clean Up Bitbucket

```ts
// Close PR
await bitbucket.pullrequests.decline({ workspace: 'corekinect', repo_slug: 'alpha_fw', pull_request_id: prId });
// Delete branches
await bitbucket.refs.deleteBranch({ workspace: 'corekinect', repo_slug: 'alpha_fw', name: featureBranch });
await bitbucket.refs.deleteBranch({ workspace: 'corekinect', repo_slug: 'alpha_fw', name: cacheBranch });
```

### Step 13.8 — Verify Zero-Data State

**Assertion Strategy:**
```ts
const products = await apiRequest('GET', '/v2/products');
expect(products.data).toHaveLength(0);

const fixtures = await apiRequest('GET', '/v2/fixtures');
expect(fixtures.data).toHaveLength(0);

const sessions = await apiRequest('GET', '/v2/sessions');
// Only pre-existing dev users should remain; no test sessions
const testSessions = sessions.data.filter(s => s.product?.name === 'Alpha');
expect(testSessions).toHaveLength(0);

const queue = await apiRequest('GET', '/v2/sessions/queue');
const testEntries = queue.data.filter(e => e.product?.name === 'Alpha');
expect(testEntries).toHaveLength(0);
```

**Excluded from zero-check:**
- AuditLog entries (append-only by design)
- Seeded dev users (part of system, not test data)

---

## Appendix: Key File References

### Frontend Routes
| Route | File |
|-------|------|
| `/login` | `apps/frontend/app/src/routes/login/+page.svelte` |
| `/` (dashboard) | `apps/frontend/app/src/routes/+page.svelte` |
| `/products` | `apps/frontend/app/src/routes/products/+page.svelte` |
| `/products/[id]` | `apps/frontend/app/src/routes/products/[id]/+page.svelte` |
| `/builds` | `apps/frontend/app/src/routes/builds/+page.svelte` |
| `/builds/runs/[id]` | `apps/frontend/app/src/routes/builds/runs/[id]/+page.svelte` |
| `/validation` | `apps/frontend/app/src/routes/validation/+page.svelte` |
| `/validation/runs/[id]` | `apps/frontend/app/src/routes/validation/runs/[id]/+page.svelte` |
| `/validation/queue` | `apps/frontend/app/src/routes/validation/queue/+page.svelte` |
| `/fixtures` | `apps/frontend/app/src/routes/fixtures/+page.svelte` |
| `/manufacturing` | `apps/frontend/app/src/routes/manufacturing/+page.svelte` |
| `/users` | `apps/frontend/app/src/routes/users/+page.svelte` |
| `/kubernetes` | `apps/frontend/app/src/routes/kubernetes/+page.svelte` |

### Backend API Endpoints (key ones)
| Method | Path | Permission | File |
|--------|------|-----------|------|
| GET | `/v2/auth/dev-users` | none | `auth/dev_login.py` |
| POST | `/v2/auth/dev-login` | none | `auth/dev_login.py` |
| GET | `/v2/auth/me` | `@require_permissions()` | `auth/me.py` |
| GET | `/v2/dashboard/overview` | varies | `router.py` |
| GET/POST | `/v2/products` | `products:view` / `products:manage` | `products/products.py` |
| GET | `/v2/products/boards/branches` | `products:view` | `products/board_discovery.py` |
| GET | `/v2/products/boards/discover` | `products:view` | `products/board_discovery.py` |
| GET | `/v2/products/repos/check` | `products:view` | `products/board_discovery.py` |
| GET/PUT | `/v2/products/{id}/stages/{stage}` | `builds:view` / `builds:manage` | `builds/stage_config.py` |
| GET | `/v2/builds/runs` | `builds:view` | `builds/build_runs.py` |
| GET | `/v2/builds/{id}/artifacts` | `builds:view` | `builds/builds.py` |
| GET | `/v2/sessions/queue` | `validation:view` | `sessions/queue.py` |
| GET | `/v2/sessions/{id}` | `validation:view` | `sessions/runs.py` |
| GET/POST | `/v2/fixtures` | `fixtures:view` / `fixtures:manage` | `fixtures/fixtures.py` |
| POST | `/v2/fixtures/designs` | `fixtures:manage` | `fixtures/designs.py` |
| GET/POST | `/v2/users` | `users:view` / `users:manage` | `auth/users.py` |
| GET/POST | `/v2/permissions` | `users:view` / `permissions:manage` | `auth/permission_sets.py` |
| GET/POST/DELETE | `/v2/api-keys` | `api-keys:view` / `api-keys:manage` | `auth/api_keys.py` |

### Component Files (Validation Run Detail)
| Component | File |
|-----------|------|
| RunHeader | `apps/frontend/app/src/lib/components/validation/run-header.svelte` |
| StageSidebar | `apps/frontend/app/src/lib/components/validation/stage-sidebar.svelte` |
| TestList | `apps/frontend/app/src/lib/components/validation/test-list.svelte` |
| ChartPanel | `apps/frontend/app/src/lib/components/validation/chart-panel.svelte` |
| PowerChart | `apps/frontend/app/src/lib/components/validation/power-chart.svelte` |
| UartPanel | `apps/frontend/app/src/lib/components/validation/uart-panel.svelte` |
| UartTerminal | `apps/frontend/app/src/lib/components/validation/uart-terminal.svelte` |
| ResizeLayout | `apps/frontend/app/src/lib/components/validation/resize-layout.svelte` |
| CancelDialog | `apps/frontend/app/src/lib/components/validation/cancel-dialog.svelte` |
| TimelineWidget | `apps/frontend/app/src/lib/components/validation/timeline-widget.svelte` |

### Permission System
| File | Purpose |
|------|---------|
| `apps/backend/http-api/src/lib/permissions.py` | All 24 permission strings + role defaults |
| `apps/backend/http-api/src/lib/decorators.py` | `@require_permissions`, `@require_role`, `_resolve_effective_role` |
| `apps/frontend/app/src/lib/components/sidebar.svelte` | Permission-gated navigation items |
| `apps/frontend/app/src/lib/stores/auth.svelte.ts` | `hasPermission()` client-side check |
