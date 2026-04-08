# E2E Spec Deep Gap Analysis

**Date:** 2026-04-08
**Method:** Cross-referenced every stage file against the actual codebase.

---

## Stage 1: Foundation

### VERIFIED
- **Playwright config exists at `apps/frontend/app/playwright.config.ts`** — current config uses `testDir: './e2e'` and `fullyParallel: true`. The spec correctly proposes a separate `e2e.config.ts` for the sequential full-stack suite.
- **`docker-compose.test.yaml` already exists** at `deploy/development/docker-compose.test.yaml`. Includes `test-db` (port 5434), `test-minio` (port 8677), `test-api` (port 9010), `test-poller`, and `test-build-service`. AUTH_ENABLED is already `false`.
- **Existing E2E fixtures work** — `e2e/fixtures.ts` provides a custom `test` fixture that collects JS errors. All spec tests should extend this.
- **Existing API helpers are consistent** — `e2e/helpers/api.ts` uses `ApiKey ck_ci_admin_x8K2mP9vL4nQ7wR1tY6uI3oA5sD0fG` for direct API calls. The spec's proposed extensions match this pattern correctly.
- **Existing auth helper uses different endpoint** — `e2e/helpers/auth.ts` uses `POST /v2/auth/login` with `admin@concord.local`/`admin`. This is the production auth flow, not the dev login flow. The spec correctly identifies both flows.

### WRONG
- **Spec says `e2e.config.ts` base URL is `http://localhost:4200`** but `docker-compose.test.yaml` maps test-api to port 9010, not 9001. The test frontend would need to proxy to 9010, or tests should hit the API at `http://localhost:9010` directly. The existing playwright config uses `localhost:4200` for the frontend and `localhost:9001` for the API. The test compose uses different ports. **Resolution needed: either use the dev compose (ports 4200/9001) or update the test compose to match.**
- **Spec proposes a `QueuePage` page object at `pages/queue.page.ts`** but the validation queue UI lives at `/validation/queue/` (route: `apps/frontend/app/src/routes/validation/queue/`), not at a standalone `/queue` route. The page object URL must be `/validation/queue`.

### MISSING
- **Existing test compose has `BITBUCKET_POLLER_ENABLED: "false"`**. For build pipeline tests (Stage 6), this must be `"true"`. The spec doesn't mention toggling this.
- **Existing test compose has `CK_BOARDS_REPO_URL: ""`**. Product creation wizard needs ck_boards discovery, which requires this URL. The spec doesn't address this dependency.
- **The test compose doesn't include a frontend service.** Tests currently rely on `npm run dev -- --port 4200` via `webServer` config. The E2E spec should clarify whether to add a frontend container to the test compose or keep the webServer approach.
- **The existing `e2e/fixtures.ts` filters out common noisy errors** (favicon, .map 404s, net::ERR, etc.). The spec doesn't mention extending this. New E2E tests should import `test` from `e2e/fixtures.ts`, not from `@playwright/test`.

### RISK
- **docker-compose.test.yaml uses `image: concord/http-api:development`** — these images must be pre-built. If running from a fresh checkout, `nx update platform` (or equivalent) must run first to build images. The global setup should verify images exist.

---

## Stage 2: Auth & Navigation

### VERIFIED
- **Dev login returns users with different roles** — `dev_login.py` confirms: `POST /v2/auth/dev-login` with `{"email": "admin@concord.dev"}` returns a JWT. The 4 dev user emails are exactly: `admin@concord.dev`, `maintainer@concord.dev`, `developer@concord.dev`, `operator@concord.dev`. These match the spec.
- **Dev users are seed-dependent** — `dev_login.py` line 85: "User not found. Run: python3 prisma/seed.py". The MEMORY.md learning L2 correctly identifies this gap. Global setup MUST run seed.
- **Login page renders dev user cards** — `login/+page.svelte` fetches `GET /v2/auth/dev-users` on mount, renders a button per user with role badge and permission set name. The spec's `loginAsRoleViaUI()` should click these buttons.
- **View-As triggers `window.location.reload()`** — confirmed at `sidebar.svelte` line 338: `onclick={() => { auth.setViewAs(option.value); viewAsOpen = false; window.location.reload(); }}`.
- **View-As only in dev environment** — confirmed at `sidebar.svelte` line 315: `{#if isDev && auth.canViewAs && !collapsed}`.
- **`canViewAs` check** — `auth.svelte.ts` line 37-39: returns true for ADMIN or MAINTAINER. Matches spec.
- **View-As localStorage key** — `concord-view-as-role` confirmed in both `auth.svelte.ts` and `api.ts`.
- **`X-View-As-Role` header sent on every API call** — confirmed in `api.ts` line 36-39.

### WRONG
- **Spec says "Kubernetes sidebar visibility is gated on `system:view`"** — VERIFIED CORRECT actually. `sidebar.svelte` line 96-98: `systemItems` uses `permission: 'system:view'` for the Kubernetes item.
- **Spec says "Maintainer sees View-As-Role dropdown"** — VERIFIED CORRECT. `canViewAs` returns true for MAINTAINER.
- **Spec test says "Developer does NOT see View-As-Role dropdown"** — VERIFIED CORRECT. Only ADMIN and MAINTAINER pass `canViewAs`.
- **Spec test says "sidebar shows user avatar and email"** — PARTIALLY WRONG. Sidebar shows user initial (first letter) in a circle + user name + permission set name (or email as fallback). It does NOT show a real avatar image. The test should check for the initial letter, not an avatar.

### MISSING
- **Sidebar has collapsible sections** — The Admin section (Users) and System section (Kubernetes) are behind expandable toggles (`adminExpanded`, `systemExpanded`). Tests must click the "Admin" or "System" toggle button to reveal these items before checking visibility. The spec doesn't mention this interaction.
- **Sidebar collapse state** — The sidebar can be collapsed (icon-only mode). When collapsed, View-As is hidden entirely (`!collapsed` check on line 315). Tests should ensure sidebar is expanded before checking View-As.
- **Login page has animated planes background** — The spec test mentions this. Confirmed: `initPlanesAnimation()` creates 8 canvas planes. This is cosmetic and may not need a test, but the canvas element exists.

### RISK
- **Operator's sidebar shows only Dashboard + Manufacturing** — This depends on the Operator permission set having ONLY `manufacturing:view`, `manufacturing:run`, `manufacturing:manage`. The `DEFAULT_ROLES` in `permissions.py` confirms this. But the sidebar only shows items where `auth.hasPermission(permission)` is true. Since Operator lacks `products:view`, `builds:view`, `validation:view`, `fixtures:view`, `system:view`, `users:view` — those items will all be hidden. VERIFIED CORRECT.

---

## Stage 3: Products

### VERIFIED
- **Product creation wizard has 4 steps** — `product-creation-wizard.svelte` line 89: `const stepLabels = ['Branch', 'Board', 'Configure', 'Create'];`. Steps are: (1) Select branch, (2) Select board family, (3) Configure product details, (4) Confirm and create.
- **Product detail page has 5 tabs** — `product-detail.svelte` line 73-79: `overview`, `hardware`, `assets`, `manufacturing`, `stages` (labeled "Validation"). Matches spec.

### WRONG
- **Spec says Step 3 = "Configure board detail (revision, SoCs, AppIDs, repos)" and Step 4 = "Confirm and create"** — The actual wizard is: Step 1 = Branch, Step 2 = Board family, Step 3 = Configure (product name, slug, description, per-revision device type/variant/targets, firmware repos with async validation), Step 4 = Confirm and create (review summary). The spec's description of Steps 3-4 is slightly off. Step 3 includes product name/slug/description fields, not just board detail. Step 3 also includes firmware repo slug validation (async Bitbucket check). The spec tests for Step 3 mention "repo existence indicator shows green check" which is correct but the field is on Step 3, not Step 4.
- **Spec says "Step 4: review page shows all configured values"** — Actually Step 4 is the confirm page with the review summary. But note: Step 4 does NOT have an explicit "review" step separate from the "create" button. It's a combined review+create step.
- **Tab order** — Spec says "5 tabs: Overview, Hardware, Assets, Manufacturing, Validation". The actual order is: Overview, Hardware, Assets, Manufacturing, Validation (labeled "stages" internally). The spec's naming convention says "Validation tab" but the code calls it "stages" tab internally. Tests should match the UI label "Validation".

### MISSING
- **Product wizard Step 3 has `deviceType` and `deviceVariant` fields per revision** — The spec mentions "SoCs" and "appIds" but doesn't mention `deviceType` and `deviceVariant` integer fields that are part of the form. These are required inputs.
- **Firmware repo slug validation uses debounced async check** — `checkRepo()` calls `GET /v2/products/repos/check?slug=...`. There's a 500ms debounce. Tests must wait for the debounce + API response before asserting the check/X indicator.
- **Spec test says "confirmation dialog requires typing product name"** for delete — need to verify this exists in the actual delete UI. The delete endpoint exists but the UI may or may not have a confirmation dialog with name typing.

### RISK
- **ck_boards discovery depends on the backend being able to fetch from the ck_boards git repo** — If `CK_BOARDS_REPO_URL` is not configured in the test environment, Step 1 will return empty branches and Step 2 will return no board families. This would block the entire product creation flow.

---

## Stage 4: Stage Configuration

### VERIFIED
- **Stage config wizard has 4 steps** — Confirmed: `steps = [{num: 1, label: 'Target & Triggers'}, {num: 2, label: 'Signing Key'}, {num: 3, label: 'Build Recipe'}, {num: 4, label: 'Review & Save'}]`.
- **Step 1 fields match spec** — board revision dropdown, watch branch, trigger type checkboxes (pr_push, pr_merge, auto, schedule, manual). Cron expression appears when "schedule" is selected.
- **Step 2: signing key dropdown** — shows secrets filtered by `type === 'signing_key'`. Can create new signing key inline (spec says "can create new signing key inline" which needs verification of whether this inline creation exists).
- **Step 3: recipe editor with syntax highlighting** — Uses `CodeEditor` component. Has recipe validation, recipe checks (shebang, error handling, SDK source, init, finalize), test build with live terminal streaming.
- **Test build with live terminal** — Confirmed: `testBuildRunning`, `testBuildLogs`, terminal with WebSocket subscription via `subscribeCiBuild()`.

### WRONG
- **Spec says Step 1 labels are "board revision, watch branch, trigger types"** — Actual Step 1 label is "Target & Triggers". The spec description is functionally correct but the step names differ.
- **Spec says Step 2 = "signing key dropdown"** — Actual Step 2 label is "Signing Key". Correct.
- **Spec says Step 3 = "recipe editor"** — Actual Step 3 label is "Build Recipe". The spec description matches.
- **Spec says Step 4 = "confirmation shows all configured values"** — Actual Step 4 label is "Review & Save". The spec description matches.
- **Spec test says "recipe history shows previous versions"** — The wizard has `recipeLastSaved` and `recipeSavedVersion` state, but whether a full history view exists in the wizard UI needs verification. The recipe versioning is handled by the backend `RecipeVersion` model. The wizard may show the current version number but not a full history browsing UI within the wizard itself.
- **Spec test says "recipe diff view compares two versions"** — This may not exist in the stage config wizard. The wizard focuses on editing/saving, not comparing versions. This test may need to be moved to a separate recipe management page if one exists.

### MISSING
- **Trigger type options differ from spec** — The actual trigger options include: `pr_push`, `pr_merge`, `auto`, `schedule`, `manual`. The spec mentions "manual, cron, pr_push" but the actual code uses `schedule` (not `cron`) as the trigger type name. The cron expression is a sub-field when `schedule` is selected.
- **Default trigger types per stage** — The wizard has defaults: Stage 1 = `['pr_push']`, Stage 2 = `['auto']`, Stage 3 = `['auto']`, Stage 4 = `['schedule']`, Stage 5 = `['pr_merge', 'manual']`. The spec doesn't mention these defaults but tests should be aware of them.
- **Recipe has checklist-style analysis** — The wizard dynamically checks the recipe content for required elements (shebang, set -eo pipefail, source SDK, concord_init, concord_finalize, etc.). This is a rich feature the spec doesn't mention testing.
- **Build matrix is managed by a separate component** — `BuildMatrixView` is imported in the wizard but the spec treats it as a separate test file. Need to verify if it's within the wizard or a separate page.

---

## Stage 5: Bitbucket Integration

### VERIFIED
- **Bitbucket helpers use API v2** — `https://api.bitbucket.org/2.0`. Workspace is `corekinect`.

### MISSING
- **Authentication method for Bitbucket** — The test compose has `BITBUCKET_SSH_KEY` and `BITBUCKET_API_TOKEN` env vars (sourced from host env). The spec doesn't specify how the E2E Bitbucket helpers will authenticate. They need either the API token from the env or a separate credential config.

---

## Stage 6: Build Pipeline

### VERIFIED
- **Builds page exists** at `/builds` with list view. Build detail at `/builds/[id]`.
- **Build settings page exists** at `/builds/settings/`.
- **PR pipeline view exists** at `/builds/prs/[productId]/` (route: `apps/frontend/app/src/routes/builds/prs/[productId]/`).
- **Build artifacts endpoint** — confirmed per the existing API helpers: `getBuildRuns()` fetches from `/v2/builds/runs`.

### WRONG
- **Spec says PR pipeline page is at `/builds/prs/[productId]/[prNumber]`** — The actual route is `/builds/prs/[productId]/` with the productId as a dynamic segment. There is no `[prNumber]` sub-route visible in the file structure. The PR filtering likely happens via query params or within the page itself.

### MISSING
- **Git poller must be enabled** — The test compose has `BITBUCKET_POLLER_ENABLED: "false"`. For auto-trigger tests, this must be `"true"` and the poll interval needs to be short enough for test timeouts.

### RISK
- **Real build compilation takes 5-20 minutes** — The spec acknowledges this, but the test compose `BUILDER_TIMEOUT` is 1800 (30 min). With multiple builds, total stage duration could exceed 45 min. The test timeout of 600,000ms (10 min) per test may be too short for build monitoring tests.

---

## Stage 7: Fixtures

### VERIFIED
- **Fixture creation form** exists in the backend: `POST /v2/fixtures` takes name, productId, type (MANUFACTURING/VALIDATION), designId, stationId, slots array.
- **MTIB deploy/undeploy code exists** — `_deploy_mtib_for_slot()` and `_undeploy_mtib_for_slot()` in `fixtures.py`. Uses `services/kubernetes/mtib_deployments.py` which creates K8s deployments from a YAML template.
- **Fixture design CRUD** — full CRUD in `apps/backend/http-api/src/api/v2/fixtures/designs.py` with proper permission checks (FIXTURES_VIEW for reads, FIXTURES_MANAGE for writes).
- **Slot assignment triggers MTIB deployment** — Confirmed at `fixtures.py:508`: `deploy_name = _deploy_mtib_for_slot(node, fixture, slot.slotIndex)`.

### WRONG
- **Spec says deploy/undeploy has "TODOs remaining"** — Actually, both deploy and undeploy are implemented:
  - `_deploy_mtib_for_slot()` creates a K8s deployment and stores the name in `Node.metadata["deployment_name"]`.
  - `_undeploy_mtib_for_slot()` calls `delete_mtib_deployment()` and clears the metadata.
  - The fixture-level `deploy_fixture()` and `undeploy_fixture()` endpoints exist.
  - However, undeploy falls back silently if K8s client is unavailable (`ImportError` catch). This is a soft failure, not a TODO.

### MISSING
- **Docker-based MTIB deploy for development** — The MTIB deployment code only handles K8s deployments (`create_namespaced_deployment`). In development (Docker Compose), MTIB deploy may not work. The spec's MEMORY.md (D13) says "Must fix for both Docker (development) and K8s (staging/production)". This is still an open implementation task.
- **Fixture creation requires a design to exist first** — The spec mentions this flow but tests must ensure design creation precedes fixture creation.

### RISK
- **MTIB at 10.4.45.33 may not be reachable** — MEMORY.md D10 notes the dev machine (172.22.x.x codespace) cannot reach 10.4.45.33. MTIB deploy/health checks will fail from the codespace. Tests requiring MTIB must run from the office network.

---

## Stage 8: Validation Queue

### VERIFIED
- **Queue endpoints exist** — `/sessions/queue` (GET/POST), `/sessions/queue/stats`, `/sessions/queue/<id>`, `/sessions/queue/<id>/cancel`, `/sessions/queue/<id>/promote`.
- **Queue permissions** — list/stats use VALIDATION_VIEW, create/update/cancel/promote use VALIDATION_MANAGE.
- **Validation queue UI route** — `/validation/queue/`.

### WRONG
- **Spec says queue URL is `/sessions/queue`** — The API URL is correct (`/v2/sessions/queue`), but the UI page is at `/validation/queue/`, not `/sessions/queue`. The spec page objects should reference the UI path.

---

## Stage 9: Validation Execution

### VERIFIED
- **WebSocket namespace `/validation`** — Confirmed in `validation_ws.py`: events include `subscribe_run`, `unsubscribe_run`. Events are emitted on this namespace.
- **Reporter callbacks** — `reporter.py` uses `@require_auth` (not `@require_permissions`). Endpoints: `/sessions/<run_id>/report/start`, `/report/test-start`, `/report/test-result`, `/report/finish`.
- **Validation run detail routes** — `/validation/runs/` and `/validation/runs/[id]` (inferred from route structure at `apps/frontend/app/src/routes/validation/runs/`).

### WRONG
- **Spec says reporter endpoint is `POST /v2/sessions/{id}/report/test-result`** — The actual route is `/v2/sessions/<run_id>/report/test-result`. Same format, just noting the Flask-style `<run_id>` vs spec's `{id}`.

### MISSING
- **Reporter uses `@require_auth` not `@require_permissions`** — This means any authenticated user (including API key holders) can post results. The spec's Stage 15 permission tests should note that reporter endpoints don't check specific permissions, just authentication.

---

## Stage 10: Manufacturing Backend

### VERIFIED
- **No manufacturing API module exists** — `ls apps/backend/http-api/src/api/v2/` shows no `manufacturing/` directory. Only a single legacy route at `sessions/manual.py` referenced as "Sessions - Legacy manufacturing test run" in the router.
- **Manufacturing permissions already defined** — `permissions.py` has `MANUFACTURING_VIEW`, `MANUFACTURING_RUN`, `MANUFACTURING_MANAGE`. The Operator role gets all three manufacturing permissions.
- **No conflicting Prisma models** — `schema.prisma` has no `ManufacturingConfig`, `ManufacturingSession`, `ManufacturingPanel`, or `ManufacturingUnit` models. The proposed models won't collide with any existing ones.

### WRONG
- **Spec proposes endpoints at `/v2/manufacturing/sessions` etc.** — These paths don't conflict with any existing routes. The existing `/v2/sessions/` routes are for validation sessions. However, the existing `/sessions/manual/run` route IS a legacy manufacturing endpoint. This should be deprecated or removed when the new manufacturing module is built.

### MISSING
- **The spec proposes `ManufacturingConfig` with `firmwareSetId` FK** — The `FirmwareSet` model exists in the schema, so this FK is valid. But the `ManufacturingConfig` model needs a migration. The spec correctly notes this needs a Prisma migration.
- **The spec's `ManufacturingUnit.slotId` FK** — FixtureSlot model exists. The FK to `FixtureSlot` is valid.

### RISK
- **WebSocket namespace `/manufacturing`** — The existing codebase uses two Socket.IO namespaces: `/validation` and `/kubernetes`. Adding `/manufacturing` is straightforward (just register new event handlers on the new namespace in the router/main). No architectural conflict, but it needs to be registered in `main.py` or `router.py`.
- **The existing `Session` model has a `type` field** — The spec proposes using a new `ManufacturingSession` model rather than extending the existing `Session` model with `type=MANUFACTURING`. This is a design choice. The existing `Session` model already has a `type` enum that includes both session types. Using a separate model means manufacturing sessions won't show in the existing session list unless explicitly joined. This is probably correct since manufacturing has a fundamentally different lifecycle (panels, units).

---

## Stage 11: Manufacturing Frontend

### VERIFIED
- **Manufacturing page exists but is a stub** — `/manufacturing/+page.svelte` is just a `PageHeader` + `EmptyState` with "Manufacturing runs will appear here once configured for your products." Permission-gated on `manufacturing:view`.
- **Permission gating pattern is established** — The existing stub already uses `auth.hasPermission('manufacturing:view')` on mount. The spec's proposed permission checks match this pattern.

### MISSING
- **No `/manufacturing/session/[id]` route exists** — This route must be created from scratch. The spec correctly identifies this as a new page.
- **No manufacturing-specific WebSocket service exists** — The frontend currently has WebSocket helpers for validation (`subscribeCiBuild`, etc.) but nothing for manufacturing. New Socket.IO subscription helpers are needed.

---

## Stage 12: Manufacturing Setup Wizard

### VERIFIED
- **Manufacturing tab exists on product detail** — `product-detail.svelte` line 77: `{ key: 'manufacturing', label: 'Manufacturing', icon: Factory }`. The tab renders but likely shows an empty state since no `ManufacturingConfig` model exists yet.
- **Tab is at position 4** — Order: Overview, Hardware, Assets, Manufacturing, Validation.

### MISSING
- **The actual manufacturing tab content** — Need to check what `tabs/manufacturing-tab.svelte` contains (probably a placeholder). The spec proposes a full config wizard component that doesn't exist yet.

---

## Stage 13: Manufacturing E2E

### VERIFIED
- **The spec correctly identifies the Operator access paradox** — Operator has `manufacturing:manage` but NOT `products:view`. So Operator cannot access the product detail page where the Manufacturing tab lives. The spec resolves this by saying config is done by Admin/Maintainer via product detail, while Operator only uses `/manufacturing`.

### RISK
- **MTIB required for real manufacturing test execution** — Same reachability concern as Stage 9. Manufacturing E2E tests that actually run hardware tests will fail from the codespace.

---

## Stage 14: User Management

### VERIFIED
- **Users page exists** at `/users/+page.svelte`. The route exists.
- **User CRUD endpoints exist** — `users:view` and `users:manage` permissions are defined.

### MISSING
- **Stage 14 file is sparse** — "Same content as previous Stage 11" with a note to "see git history for full details". The actual test cases are not detailed in the file. This is a documentation gap that should be filled before implementation.

---

## Stage 15: Role Stories

### VERIFIED
- **Permission decorators cover all endpoints** — Comprehensive `@require_permissions()` usage across all route modules:
  - Products: `PRODUCTS_VIEW`, `PRODUCTS_MANAGE`
  - Builds: `BUILDS_VIEW`, `BUILDS_TRIGGER`, `BUILDS_MANAGE`
  - Validation (sessions): `VALIDATION_VIEW`, `VALIDATION_RUN`, `VALIDATION_MANAGE`
  - Fixtures: `FIXTURES_VIEW`, `FIXTURES_MANAGE`
  - Devices (ICLE): `DEVICES_VIEW`, `DEVICES_MANAGE`
  - Kubernetes: `KUBERNETES_VIEW`, `KUBERNETES_MANAGE`
  - System: (covered by kubernetes module)
- **Operator has correct permissions** — `permissions.py` line 113-115: `["manufacturing:view", "manufacturing:run", "manufacturing:manage"]`.
- **Developer permissions match spec** — `permissions.py` line 107-112: Has `products:view`, `builds:view/trigger/manage`, `validation:view/run`, `manufacturing:view`, `fixtures:view`, `devices:view`, `api-keys:view/manage`. Developer does NOT have `products:manage`, `fixtures:manage`, `validation:manage`, `manufacturing:run`, `manufacturing:manage`, `users:*`, `kubernetes:*`, `system:*`.

### WRONG
- **Spec says Developer does NOT have `builds:manage`** (permission matrix row) — But `permissions.py` line 107 gives Developer `builds:manage`. This is a spec ERROR. The codebase is authoritative. Developer CAN manage builds. The spec's permission matrix needs correction.
- **Spec says Developer has `manufacturing:view` but NOT `manufacturing:run`** — VERIFIED CORRECT per `permissions.py`.
- **Spec section 6.3 test says "Attempt builds:manage operations -> verify succeeds (Developer has this)"** — This is correct per the code, but contradicts the permission matrix in section 4.2 which says Developer doesn't have it. The user story is correct; the matrix is wrong.

### MISSING
- **Session reporter uses `@require_auth` not `@require_permissions`** — The reporter endpoint at `sessions/reporter.py` line 76 uses `@require_auth` (bare authentication, no specific permission check). This means ANY authenticated user (including Operator with no validation permissions) could theoretically post test results if they have the session ID and API key. The spec doesn't test this edge case. Consider whether reporter endpoints should require `VALIDATION_RUN` permission.
- **Session logs endpoint uses `@require_auth`** — `sessions/logs.py` line 171 uses `@require_auth` (not `@require_permissions`). Any authenticated user can access session logs. This may be intentional for K8s runner pods with API keys.
- **Missing Operator manufacturing:manage test** — The spec correctly notes Operator has `manufacturing:manage`, but the Operator user story (section 6.4) doesn't explicitly test `manufacturing:manage` operations (only tests `manufacturing:view` and `manufacturing:run`). The spec note on line 689 says "manufacturing:manage via API -> verify ALLOWED" which is correct, but there should be a concrete test for what `manufacturing:manage` gates (e.g., `ManufacturingConfig` CRUD once it exists).
- **Some endpoints don't match expected permission boundaries**:
  - `builds/manifest.py:10`: `@require_permissions(Permissions.VALIDATION_VIEW)` — a builds endpoint gated on validation:view. This is intentional (manifest is for validation builds) but could confuse permission tests.
  - `sessions/logs.py:171`: `@require_auth` instead of `@require_permissions` — any authenticated user can access.

---

## Stage 16: Cleanup & Orchestration

### VERIFIED
- **No manufacturing models exist to clean** — Since ManufacturingConfig/Session/Panel/Unit don't exist yet, cleanup tests for these are forward-looking (will only matter after Stage 10 implementation).

### MISSING
- **Cleanup for K8s MTIB deployments** — If fixture slot assignment created K8s deployments during the test, cleanup should call undeploy. The spec mentions "K8s Jobs/Pods from validation runs are cleaned up" but doesn't mention MTIB server deployments.
- **DELETE_ALL_KEY** — The test compose sets `DELETE_ALL_KEY: e2e-delete-key`. This is likely used for a bulk-delete or reset endpoint. The spec's `resetDatabase()` helper should use this key.

---

## Cross-Cutting Issues

### WebSocket Testing Architecture
- The spec proposes observing DOM mutations for WebSocket-driven UI updates. This is the correct approach since Playwright cannot natively subscribe to Socket.IO. However, the spec should provide more specific selectors. The actual validation run detail page components would need to be examined for CSS class names and data attributes.

### View-As-Role Implementation Detail
- The `X-View-As-Role` header is sent on EVERY API call when View-As is active (via `api.ts`). This means the backend resolves the effective role on every request. The spec correctly notes this causes a page reload, but it should also note that the `api.ts` module reads from localStorage synchronously — so the header is sent even on API calls made before the page reload completes.

### Seed Dependency
- Multiple stages depend on the seed script having run (dev users, default roles, default permission sets). The global setup MUST run seed. The spec's MEMORY.md (L2) identifies this but the Stage 1 deliverables should make this more explicit.

### Model Count
- The spec says "36 models" but the schema grep shows 36 `model` declarations. This is consistent.

### Frontend Route Structure vs Spec Page Objects
- `/validation/benches/` and `/validation/designs/` routes exist (alongside `/validation/queue/` and `/validation/runs/`). The spec proposes a `FixturesPage` but doesn't mention that validation has its own benches/designs sub-routes. These might be legacy from when fixtures were under validation.

### API Path Discrepancies for Proposed Manufacturing Endpoints
- The spec proposes `/v2/manufacturing/fixtures` — but existing fixture listing is at `/v2/fixtures?type=MANUFACTURING`. The new endpoint could either be a separate route or a filter on the existing fixtures endpoint. Using a filter is simpler; a separate route risks duplicate logic.
- The spec proposes `/v2/products/<id>/manufacturing` for config — this nests under products, which is consistent with how stage config is at `/v2/products/<id>/stages`.
