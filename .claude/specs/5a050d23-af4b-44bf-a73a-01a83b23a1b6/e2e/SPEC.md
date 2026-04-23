# E2E Test Architecture Specification

**Last reviewed:** 2026-04-08
**Status:** Draft

---

## 1. Purpose

Build a comprehensive, user-story-driven end-to-end test suite for the Concord platform. Tests exercise the entire system — from Playwright UI interactions through the backend API, database, external integrations (Bitbucket, CoreCloud, MinIO), and real hardware (MTIB + DUT) — verifying that every role can complete their full workflow on a fresh system with zero pre-existing data.

---

## 2. Scope

### In Scope

| Domain | What Gets Tested |
|--------|-----------------|
| **Dashboard** | Widgets, fixture cards, mode toggle, navigation links |
| **Products** | Full creation wizard (ck_boards discovery, board revisions, targets, repos), edit, delete, stage configuration wizard, recipe editor, build matrix |
| **Builds** | Trigger via git-poller (real Bitbucket branches/PRs), real firmware compilation, build caching verification, artifact download, PR pipeline view |
| **Validation** | Queue management, fixture assignment, real test execution on MTIB, result collection via WebSocket, run detail viewer (tests, power chart, UART), run comparison |
| **Manufacturing** | Single-stage workflow (similar to validation), build auto-caching from validation builds, POST test execution |
| **Fixtures** | Design CRUD, instance CRUD, slot management, node assignment, MTIB deployment, fixture locking during runs |
| **Users** | User CRUD, role assignment, permission set management, API key management |
| **Roles** | 4 complete user stories (ADMIN, MAINTAINER, DEVELOPER, OPERATOR), permission denial verification, sidebar visibility, View-As-Role |
| **Cleanup** | Full teardown: DB wipe, CoreCloud device cleanup, Bitbucket branch/PR cleanup, MinIO artifact cleanup |

### Out of Scope

| Excluded | Reason |
|----------|--------|
| ICLE device management | Hardware-dependent, not core workflow |
| Waveform analyzer | Specialized tool, not user-story critical |
| Inventory (components/assemblies) | Backend incomplete |
| Kubernetes cluster management | Infrastructure layer, not application E2E |
| Visual regression / screenshot testing | Future enhancement, not in this spec |

---

## 3. System Under Test

### 3.1 Architecture

```
┌── LOCAL (docker-compose) ─────────────────────────────────────┐
│                                                                │
│  Playwright (Chromium)                                         │
│      │                                                         │
│      ├─→ SvelteKit Frontend (:4200)                           │
│      │       └─→ HTTP API (Flask, :9001) ←─── kubeconfig ──┐  │
│      │               ├─→ PostgreSQL (:5433)                 │  │
│      │               ├─→ MinIO (:8675)                      │  │
│      │               ├─→ Bitbucket API (api.bitbucket.org)  │  │
│      │               └─→ CoreCloud (val:2018)               │  │
│      │                                                      │  │
│      ├─→ Git Poller (polls Bitbucket)                       │  │
│      └─→ Build Service (firmware builds in Docker)          │  │
│                                                              │  │
└──────────────────────────────────────────────────────────────┘  │
                                                                  │
┌── K8s CLUSTER (office, 10.4.45.10) ──────────────────────────┐ │
│                                                                │ │
│  development namespace ←────────────────────────────────────── ┘ │
│      │                                                          │
│      └─→ MTIB Server Pod (on verdin-imx8mm-15005665)           │
│              │ gRPC :50053 (hostPort)                            │
│              ├─→ J-Link 821009543 (NRF52) + 821009541 (NRF91)  │
│              ├─→ UART /dev/verdin-uart1, /dev/verdin-uart2      │
│              └─→ DUT: Alpha B0, SNR 0964, no battery, ch0@4.5V │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘

The ONLY K8s interaction from development is MTIB server deployment.
All backend services run locally in docker-compose.
```

### 3.2 External Integrations

| System | Auth Method | Purpose in E2E |
|--------|------------|----------------|
| **Bitbucket** | SSH key + API token (mateo@corekinect.com) | Create/delete branches and PRs in `alpha_fw` and `alpha_mfg_fw` repos. Keep `concord-main` synced with `main`. |
| **CoreCloud** | Basic Auth + X-API-KEY | Device registration, FUOTA plan creation, firmware upload, progress monitoring. Val instance at `val.office.corekinect.cloud:2018`. |
| **CoreOps** | Basic Auth + X-API-KEY | Device personalization (assign device ID, upload EC public key, save SIM info). |
| **MTIB** | None (private network, gRPC) | Power control, GPIO, UART streaming, J-Link flashing. Dev pool MTIB at <MTIB_HOST>:50053. |
| **MinIO** | Access key + secret | Firmware artifact storage, build script storage, session logs. |

### 3.3 Database

- **Engine:** PostgreSQL 16
- **Models:** 36 (see Prisma schema — includes RecipeTemplate, StageBuildMatrix, AssetSet, Asset, TestPackage)
- **Strategy:** Fresh DB per suite run (migrate + NO seed), cumulative within run
- **Key enums:** Role (4), SessionType (2), BuildJobStatus (8), FixtureStatus (4), QueueEntryStatus (6)

---

## 4. Role Specifications

### 4.1 Role Hierarchy

```
ADMIN (level 4)  →  23 permissions  →  Full system access
    │
MAINTAINER (level 3)  →  19 permissions  →  Everything except user/system/k8s management
    │
DEVELOPER (level 2)  →  12 permissions  →  Build, validate, view products/fixtures/devices
    │
OPERATOR (level 1)  →  3 permissions  →  Manufacturing only (view + run + manage)
```

### 4.2 Permission Matrix

| Permission | ADMIN | MAINT | DEV | OPS |
|-----------|:-----:|:-----:|:---:|:---:|
| products:view | Y | Y | Y | - |
| products:manage | Y | Y | - | - |
| builds:view | Y | Y | Y | - |
| builds:trigger | Y | Y | Y | - |
| builds:manage | Y | Y | Y | - |
| validation:view | Y | Y | Y | - |
| validation:run | Y | Y | Y | - |
| validation:manage | Y | Y | - | - |
| manufacturing:view | Y | Y | Y | Y |
| manufacturing:run | Y | Y | - | Y |
| manufacturing:manage | Y | Y | - | Y |
| fixtures:view | Y | Y | Y | - |
| fixtures:manage | Y | Y | - | - |
| devices:view | Y | Y | Y | - |
| devices:manage | Y | Y | - | - |
| kubernetes:view | Y | Y | - | - |
| kubernetes:manage | Y | - | - | - |
| users:view | Y | Y | - | - |
| users:manage | Y | - | - | - |
| permissions:manage | Y | - | - | - |
| api-keys:view | Y | Y | Y | - |
| api-keys:manage | Y | Y | Y | - |
| system:view | Y | Y | - | - |
| system:manage | Y | - | - | - |

### 4.3 Sidebar Visibility Per Role

| Section | ADMIN | MAINT | DEV | OPS |
|---------|:-----:|:-----:|:---:|:---:|
| Dashboard | Y | Y | Y | Y |
| Products | Y | Y | Y | - |
| Builds | Y | Y | Y | - |
| Validation | Y | Y | Y | - |
| Manufacturing | Y | Y | Y | Y |
| Fixtures | Y | Y | Y | - |
| Kubernetes | Y | Y | - | - |
| Users | Y | Y | - | - |
| View-As toggle | Y | Y | - | - |

**Notes:**
- Kubernetes sidebar visibility is gated on `system:view` (not `kubernetes:view`).
- Users sidebar link is gated on `users:view` — Maintainer sees it but cannot manage (needs `users:manage`).
- View-As toggle only shows in development environment (`isDev=true`).
- Admin and System sections are behind expandable toggles — tests must click the toggle before checking visibility of Users/Kubernetes links.

### 4.4 Login Method (Development Mode)

`AUTH_ENABLED=false` — Login page fetches dev users from `GET /v2/auth/dev-users` and renders user cards:
- Click Admin user card → `POST /v2/auth/dev-login` with `admin@concord.dev` → JWT
- Click Maintainer user card → `POST /v2/auth/dev-login` with `maintainer@concord.dev` → JWT
- Click Developer user card → `POST /v2/auth/dev-login` with `developer@concord.dev` → JWT
- Click Operator user card → `POST /v2/auth/dev-login` with `operator@concord.dev` → JWT

Each card shows user name, role, and permission set. No password required.

**Note:** The existing E2E auth helper (`e2e/helpers/auth.ts`) uses `POST /v2/auth/login` with `admin@concord.local`/`admin` — a different auth flow. New role-based tests should use `POST /v2/auth/dev-login` with `@concord.dev` emails. Both flows produce valid JWTs.

**View-As-Role mechanism:** Setting View-As triggers `window.location.reload()`. The reloaded page calls `/v2/auth/me` with `X-View-As-Role` header, which returns the simulated role's permissions. This is NOT a reactive state change — tests must expect a full page navigation cycle.

---

## 5. Feature Domain Specifications

### 5.1 Products

**Models:** Product → Board → BoardRevision → ProductTarget
**Pages:** `/products` (list), `/products/[id]` (detail with 5 tabs)
**Permissions:** `products:view` (read), `products:manage` (write)

**Creation Wizard (4 steps):**
1. Select ck_boards branch (fetches from git)
2. Select board family (async discovery)
3. Configure board detail (revision, SoCs, AppIDs, repos)
4. Confirm and create (validates repo existence via Bitbucket API)

**CRUD Operations:**
- CREATE: Via wizard → creates Product + Board + BoardRevision + ProductTargets
- READ: List with search/filter/pagination; Detail with tabs (Overview, Hardware, Assets, Manufacturing, Validation)
- UPDATE: Inline edit on detail page (name, slug, description, repos)
- DELETE: Hard delete if no test execution history; else 409 Conflict

**Stage Configuration (per product, per stage 1-5):**
- Enable/disable stage for a board revision
- Set watch branch, trigger types (manual, cron, pr_push)
- Assign signing key
- Edit build recipe (YAML editor with syntax highlighting)
- Configure build matrix (N jobs per stage)
- Test build trigger with live terminal log streaming

**Deletion Constraints:**
- Product with BuildRun references → Restrict (409)
- Product with active sessions → Restrict
- Cascades: Board, FirmwareSet, Fixture, Test, ProductStageConfig, RecipeVersion, ProductAccess

### 5.2 Builds

**Models:** BuildRun → BuildJob → BuildArtifact; AssetSet → Asset
**Pages:** `/builds` (list with filters), `/builds/runs/[id]` (detail), `/builds/prs/[productId]/[prNumber]` (PR view)
**Permissions:** `builds:view`, `builds:trigger`, `builds:manage`

**Trigger Flow:**
1. Git Poller detects new commit on watched branch (60s polling interval)
2. Sends RepoEvent to `POST /v2/builds/events`
3. API creates BuildRun with build matrix (2-8 jobs per stage)
4. Build Service picks up QUEUED jobs (push notification + 60s fallback poll)
5. 5-stage pipeline: Clone → Recipe → Signing → Build → Artifact
6. Artifacts uploaded to MinIO, BuildArtifact records created

**Build Caching:**
- `buildFingerprint` = SHA-256(repo + commit + board + variant + configFlags)
- If fingerprint matches existing SUCCESS build → status=CACHED, reusedFromId set
- E2E test: trigger build on same commit twice, verify second is CACHED

**Real Build Duration:** 5-20 minutes for Alpha firmware (this is expected and acceptable)

**BuildJob Lifecycle:** QUEUED → [BLOCKED] → CLONING → BUILDING → SUCCESS/FAILED/CANCELLED/CACHED
**BuildRun Lifecycle:** PENDING → BUILDING → BUILD_FAILED/VALIDATING → SUCCESS/FAILED/CANCELLED

### 5.3 Validation

**Models:** ValidationQueueEntry, Session → Device → TestExecution → TestStep
**Pages:** `/validation` (hub), `/validation/runs` (list), `/validation/runs/[id]` (real-time detail)
**Permissions:** `validation:view`, `validation:run`, `validation:manage`

**5 Stages:**

| Stage | Name | Hardware | Duration | PR Blocking |
|-------|------|----------|----------|-------------|
| 1 | Smoke | None (native_sim) | 1-2 min | Yes |
| 2 | Driver | Dev kit + MTIB | 5-15 min | Yes |
| 3 | Integration | Product board + MTIB | 15-30 min | Yes |
| 4 | Regression | Full fixture + CoreCloud | 30-60 min | No |
| 5 | FUOTA | Full fixture + CoreCloud + OTA | <15 min | Yes |

**Queue Lifecycle:**
1. Build completes → ValidationQueueEntry created (QUEUED)
2. Scheduler polls every 10s
3. Finds AVAILABLE fixture matching product + board revision
4. Assigns fixture → entry.status=ASSIGNED, fixture.status=LOCKED
5. Creates Session + K8s Job (or local execution)
6. Tests run → reporter callbacks update TestExecution/TestStep
7. WebSocket broadcasts real-time updates to frontend
8. Session completes → fixture released → entry.status=COMPLETED

**Real-Time Run Detail Page:**
- RunHeader: status, duration, progress bar
- StageSidebar: stage selector, per-stage counts
- TestList: expandable results with status, duration, error, measurements
- ChartPanel: real-time power consumption + accelerometer graphs
- UartPanel: live UART terminal (app + comms)

### 5.4 Manufacturing (FULL IMPLEMENTATION REQUIRED)

**Status:** Currently a stub — no backend endpoints, no frontend. Must be built from scratch as part of this effort.

**Models:** Session (type=MANUFACTURING), Device, TestExecution, TestStep + new ManufacturingPanel concept
**Pages:** `/manufacturing` (list fixtures + sessions), `/manufacturing/[fixtureId]/session/[sessionId]` (live panel runner)
**Permissions:** `manufacturing:view`, `manufacturing:run`, `manufacturing:manage`

#### How Manufacturing Differs from Validation

| Aspect | Validation | Manufacturing |
|--------|-----------|---------------|
| **Trigger** | Automatic from builds (queue) | Manual — Operator starts session |
| **Unit of work** | Single run = single DUT | Session = many panels, each panel = all DUT slots |
| **Input** | Build artifacts from CI | QR code scanned by Operator |
| **Lifecycle** | Run starts → tests → run ends | Session starts → N panels run → session ends |
| **Fixture usage** | Locked per run, released after | Locked for entire session duration |
| **User** | Any role with validation:run | Operator (manufacturing:run) |

#### Manufacturing Workflow

```
1. Admin/Maintainer creates MANUFACTURING fixture (with design, slots, nodes)
2. Operator opens Manufacturing page → sees available manufacturing fixtures
3. Operator clicks "New Session" on a fixture → Session created, fixture LOCKED
4. Manufacturing test runner deployed (K8s Job or persistent process)
5. REPEAT for each panel:
   a. Operator enters QR code (panel serial / DUT identifiers)
   b. Operator clicks "Run Panel"
   c. System runs manufacturing stages against EACH MTIB slot in fixture:
      - Stage 1: ELECTRICAL — bus integrity, power delivery, connectivity
      - Stage 2: FLASH — firmware flash via J-Link (app + comms processors)
      - Stage 3: POST — boot verify, chip ID, BMS, charger, GPS, modem,
                  IMEI/ICCID, personalization, IPC rekey
   d. Results stream back in real-time (WebSocket)
   e. UI shows pass/fail PER UNIT in the panel (each slot's DUT)
   f. Operator sees which units passed/failed
6. Operator clicks "End Session"
7. All panel results grouped by session
8. Fixture released (AVAILABLE)
```

#### Manufacturing Stages (substeps within each)

| Stage | Name | Substeps | Duration |
|-------|------|----------|----------|
| 1 | **Electrical** | Bus scan, power rail verify, GPIO check, I2C/SPI probe | ~30s |
| 2 | **Flash** | J-Link recover, flash app hex, flash comms hex, verify | ~2 min |
| 3 | **POST** | Boot, chip ID, BMS, charger, GPS, modem FW, IMEI/ICCID validate, ext flash R/W, personalize, IPC rekey | ~3 min |

**Total per panel:** ~5-6 min (all slots in parallel)

#### Manufacturing Setup (Wizard + Configuration — like Validation)

Just as validation has a stage configuration wizard per product, manufacturing needs its own setup flow:

**Product Manufacturing Tab (on product detail page):**
1. Enable/disable manufacturing for a board revision
2. Manufacturing Stage Configuration Wizard:
   a. Select board revision (Alpha B0)
   b. Configure stages (Electrical, Flash, POST) — enable/disable, set params
   c. Assign firmware for flash stage (select from builds or upload)
   d. Configure personalization settings (CoreOps integration)
   e. Set pass/fail criteria per stage
   f. Save manufacturing config
3. Fixture Design creation (tied to board revision)
4. Fixture Instance creation with slot assignment

**Manufacturing configuration stored per product:**
- Which stages are enabled
- Firmware source (latest build, specific version, or manual upload)
- Personalization template (device type, variant, carrier)
- Pass criteria (power thresholds, timing limits)
- Panel size (how many units per panel = slot count in fixture)

This mirrors validation's `ProductStageConfig` but for manufacturing stages. The UI follows the same wizard pattern (multi-step modal with review/confirm).

#### API Endpoints (TO BE BUILT)

```
GET  /v2/manufacturing/fixtures              — List available manufacturing fixtures
POST /v2/manufacturing/sessions              — Start new session (locks fixture)
GET  /v2/manufacturing/sessions              — List sessions (paginated)
GET  /v2/manufacturing/sessions/:id          — Session detail with panels
POST /v2/manufacturing/sessions/:id/panels   — Run a panel (QR code input)
POST /v2/manufacturing/sessions/:id/end      — End session (release fixture)
GET  /v2/manufacturing/sessions/:id/results  — Aggregated results by panel

Reporter callbacks (from test runner):
POST /v2/manufacturing/sessions/:id/report/panel-start
POST /v2/manufacturing/sessions/:id/report/unit-result
POST /v2/manufacturing/sessions/:id/report/panel-complete
```

#### Frontend Pages (TO BE BUILT)

- `/manufacturing` — List manufacturing fixtures with status, active sessions, "New Session" button
- `/manufacturing/session/[id]` — Live session runner:
  - QR code input field (text input, future: camera scanner)
  - "Run Panel" button
  - Real-time panel results grid (one card per slot/unit)
  - Per-unit pass/fail with stage-by-stage breakdown
  - Panel history (previous panels in this session)
  - "End Session" button
- `/manufacturing/sessions` — Session history list with results summary

### 5.5 Fixtures

**Models:** FixtureDesign, Fixture → FixtureSlot → Node
**Pages:** `/fixtures` (tabs: Fixtures, Designs)
**Permissions:** `fixtures:view`, `fixtures:manage`

**Design CRUD:**
- CREATE: name (unique), boardRevisionId, revision, capabilities[], profileTemplate (JSON)
- READ: List with product filter
- UPDATE: Patch fields
- DELETE: Only if no Fixture instances reference it (Restrict)

**Instance CRUD:**
- CREATE: name, productId, type (MANUFACTURING/VALIDATION), designId, stationId (unique), slots
- READ: Detail with slot assignments, node status, deployment status
- UPDATE: Properties, slot configuration
- DELETE: Only if no sessions reference it

**Slot Assignment:**
- Assign Node to FixtureSlot → auto-deploys MTIB K8s Deployment
- Unassign → auto-undeploys MTIB
- Node type must match Fixture type

**Fixture Lifecycle:**
```
AVAILABLE → LOCKED (session running) → AVAILABLE (session done)
            OFFLINE (manual)
            MAINTENANCE (manual)
```

### 5.6 Users & Permissions

**Models:** User, PermissionSet, ProductAccess, ApiKey
**Pages:** `/users` (tabs: Users, Permission Sets)
**Permissions:** `users:view`, `users:manage`, `permissions:manage`

**User CRUD:**
- CREATE: email, name, role, permissionSetId
- READ: List with pagination
- UPDATE: name, role, permissionSet, active status
- DELETE: Deactivate (soft delete — sets active=false)

**Permission Set CRUD:**
- CREATE: name (unique), description, permissions[]
- READ: List with user counts
- UPDATE: description, permissions
- DELETE: Only if no users assigned to it

**API Key Management:**
- CREATE: name, optional expiresAt → returns plaintext key ONCE
- READ: List (shows prefix only, never full key)
- DELETE: Immediate revocation

---

## 6. User Stories

### 6.1 ADMIN User Story (Complete System Journey)

**Precondition:** Fresh system, zero data, logged in as Admin via dev-login button.

```
PHASE 1: SYSTEM SETUP
  1. Login as Admin (click Admin button on dev login page)
  2. Verify dashboard loads (empty state — no fixtures)
  3. Verify all sidebar sections visible (Products, Builds, Validation, Manufacturing, Fixtures, Kubernetes, Users)

PHASE 2: BITBUCKET SETUP
  4. [API] Sync concord-main branch with main in alpha_fw repo
  5. [API] Sync concord-main branch with main in alpha_mfg_fw repo
  6. [API] Create feature branch from concord-main in alpha_fw
  7. [API] Open PR: feature branch → concord-main

PHASE 3: PRODUCT CREATION
  8. Navigate to Products page → verify empty state
  9. Click "Create Product" → Product Creation Wizard opens
  10. Step 1: Select branch from ck_boards (main)
  11. Step 2: Select "alpha" board family
  12. Step 3: Configure Alpha B0 revision
      - SoCs: nrf52840 (app, appId=109), nrf9151 (comms, appId=108)
      - Firmware repo: alpha_fw (verify existence check passes)
      - Mfg firmware repo: alpha_mfg_fw
  13. Step 4: Confirm and create
  14. Verify product appears in list
  15. Navigate to product detail → verify all 5 tabs present

PHASE 4: STAGE CONFIGURATION
  16. Go to Validation tab (product detail)
  17. For each stage (1-5):
      a. Click stage → Stage Config Wizard opens
      b. Select board revision: Alpha B0
      c. Set watch branch: concord-main
      d. Set trigger types: pr_push (and manual)
      e. Select/create signing key
      f. Edit build recipe (load template, customize)
      g. Configure build matrix
      h. Save stage config
  18. Verify all 5 stages show as enabled in stage pills

PHASE 5: BUILD PIPELINE (AUTO-TRIGGERED)
  19. Wait for git-poller to detect the PR (up to 60s polling interval)
  20. Verify BuildRun created (navigate to Builds page)
  21. Monitor build progress:
      a. Status transitions: PENDING → BUILDING
      b. Build jobs appear with correct matrix labels
      c. Live log streaming visible
  22. Wait for all builds to complete (5-20 min per firmware target)
  23. Verify: all jobs SUCCESS, artifacts downloadable

PHASE 6: BUILD CACHING VERIFICATION
  24. [API] Create second branch from concord-main (same commit)
  25. [API] Open second PR
  26. Wait for git-poller to detect second PR
  27. Verify second BuildRun created
  28. Verify build jobs show CACHED status (same fingerprint as previous)
  29. Verify: reusedFromId points to original successful jobs

PHASE 7: VALIDATION QUEUE (NO FIXTURE YET)
  30. Navigate to Validation page
  31. Verify ValidationQueueEntries created (one per enabled stage)
  32. Verify all entries show QUEUED status (no fixture available)
  33. Verify queue stats show correct counts

PHASE 8: FIXTURE CREATION
  34. Navigate to Fixtures page → verify empty state
  35. Create FixtureDesign:
      a. Name: "Alpha E2E Fixture v1.2"
      b. Board revision: Alpha B0
      c. Revision: "1.2"
      d. Capabilities: [power, gpio, uart, jlink]
  36. Create Fixture instance:
      a. Name: "E2E Dev Bench"
      b. Product: Alpha (created in Phase 3)
      c. Type: VALIDATION
      d. Design: "Alpha E2E Fixture v1.2"
      e. Station ID: "e2e-station-33"
  37. Add FixtureSlot:
      a. Slot index: 0, label: "Slot 1"
  38. Create Node (MTIB):
      a. Hostname: "mtib-e2e-dev"
      b. Type: VALIDATION
      c. IP: <MTIB_HOST>
      d. Hardware revision: "REV1.2"
  39. Assign Node to Slot:
      a. Auto-deploys MTIB server (or verify existing deployment)
  40. Verify fixture status: AVAILABLE

PHASE 9: VALIDATION EXECUTION
  41. Verification queue scheduler detects available fixture
  42. Verify: highest-priority queue entry transitions QUEUED → ASSIGNED → RUNNING
  43. Verify: fixture status changes to LOCKED
  44. Navigate to validation run detail page
  45. Verify real-time updates:
      a. Test timeline populates via WebSocket
      b. Power chart shows live readings (if telemetry enabled)
      c. UART panel shows device boot output
  46. Wait for session to complete
  47. Verify: session status = PASSED or FAILED (with correct counts)
  48. Verify: fixture released (status back to AVAILABLE)
  49. Verify: next queued entry starts automatically

PHASE 10: MANUFACTURING (SINGLE STAGE)
  50. Create MANUFACTURING fixture design (same board revision)
  51. Create MANUFACTURING fixture instance
  52. Assign node (same MTIB or second slot)
  53. Trigger manufacturing session
  54. Verify POST test executes
  55. Verify results appear in Manufacturing page

PHASE 11: USER MANAGEMENT
  56. Navigate to Users page
  57. Create new user: test-maintainer@e2e.test, role=MAINTAINER
  58. Create new user: test-developer@e2e.test, role=DEVELOPER
  59. Create new user: test-operator@e2e.test, role=OPERATOR
  60. Verify all 3 users appear in list
  61. Create custom permission set: "E2E Custom" with specific permissions
  62. Assign custom permission set to test-developer
  63. Create API key: "E2E Test Key"
  64. Verify key shown once, prefix visible after

PHASE 12: PERMISSION VERIFICATION
  65. Use View-As-Role to simulate Maintainer → verify sidebar changes
  66. Use View-As-Role to simulate Developer → verify further restrictions
  67. Use View-As-Role to simulate Operator → verify manufacturing-only access
  68. Reset View-As-Role

PHASE 13: CLEANUP
  69. [API] Delete test users
  70. [API] Delete custom permission set
  71. [API] Delete API key
  72. Cancel any running validation/manufacturing sessions
  73. Delete fixtures (instances first, then designs)
  74. Delete product (cascades boards, stages, builds, sessions)
  75. [API] Delete Bitbucket branches and close PRs
  76. [API] Clean up CoreCloud device state (if modified)
  77. Verify: system is back to zero-data state
```

### 6.2 MAINTAINER User Story

**Precondition:** System has product + fixtures from Admin story (or creates own). Logged in as Maintainer.

```
PHASE 1: LOGIN & NAVIGATION
  1. Login as Maintainer (click Maintainer button)
  2. Verify sidebar: Products, Builds, Validation, Manufacturing, Fixtures visible
  3. Verify sidebar: Users NOT visible, Kubernetes visible (view only)
  4. Verify: View-As-Role toggle IS available

PHASE 2: PRODUCT MANAGEMENT
  5. Navigate to Products
  6. Create product via wizard (same flow as Admin)
  7. Edit product details (name, description)
  8. Configure validation stages (all 5)
  9. Verify: all product management operations succeed

PHASE 3: BUILD MANAGEMENT
  10. [API] Create branch + PR in Bitbucket
  11. Wait for builds to trigger
  12. Monitor builds, verify status transitions
  13. Trigger manual build
  14. Verify: builds:trigger, builds:manage operations succeed

PHASE 4: VALIDATION MANAGEMENT
  15. Create fixture design + instance + assign node
  16. Queue validation run
  17. Monitor execution
  18. Verify: validation:manage operations succeed

PHASE 5: MANUFACTURING
  19. Create manufacturing fixture
  20. Trigger manufacturing session
  21. Verify results

PHASE 6: PERMISSION BOUNDARIES
  22. Attempt to navigate to /users → verify redirect/403
  23. Attempt to create user via API → verify 403
  24. Attempt kubernetes:manage operations → verify 403
  25. Attempt system:manage operations → verify 403
  26. Verify: can view kubernetes, cannot modify

PHASE 7: CLEANUP
  27. Delete all created resources
  28. [API] Clean Bitbucket branches
  29. Verify zero-data state
```

### 6.3 DEVELOPER User Story

**Precondition:** Logged in as Developer.

```
PHASE 1: LOGIN & NAVIGATION
  1. Login as Developer
  2. Verify sidebar: Products, Builds, Validation, Manufacturing, Fixtures visible
  3. Verify sidebar: Users NOT visible, Kubernetes NOT visible
  4. Verify: View-As-Role toggle NOT available

PHASE 2: VIEW-ONLY PRODUCTS
  5. Navigate to Products → verify list loads
  6. Navigate to product detail → verify tabs load
  7. Attempt to create product → verify blocked (no manage button or 403)
  8. Attempt to edit product → verify blocked
  9. Attempt to delete product → verify blocked

PHASE 3: BUILD OPERATIONS
  10. Navigate to Builds → verify list loads
  11. Trigger manual build → verify succeeds (builds:trigger)
  12. View build detail, download artifacts → verify succeeds
  13. Attempt builds:manage operations → verify succeeds (Developer has this)

PHASE 4: VALIDATION OPERATIONS
  14. Navigate to Validation → verify list loads
  15. View run details → verify succeeds
  16. Trigger validation run → verify succeeds (validation:run)
  17. Attempt validation:manage → verify blocked

PHASE 5: VIEW-ONLY FIXTURES
  18. Navigate to Fixtures → verify list loads
  19. Attempt to create fixture → verify blocked (no manage permission)
  20. Attempt to create fixture design → verify blocked

PHASE 6: MANUFACTURING (VIEW ONLY)
  21. Navigate to Manufacturing → verify list loads
  22. Attempt manufacturing:run → verify blocked (Developer doesn't have it)

PHASE 7: API KEYS
  23. Navigate to API keys section
  24. Create API key → verify succeeds
  25. Delete API key → verify succeeds

PHASE 8: PERMISSION BOUNDARIES
  26. Attempt /users → verify blocked
  27. Attempt products:manage via API → verify 403
  28. Attempt fixtures:manage via API → verify 403
  29. Attempt validation:manage via API → verify 403

PHASE 9: CLEANUP
  30. Delete created API keys
```

### 6.4 OPERATOR User Story

**Precondition:** Logged in as Operator.

```
PHASE 1: LOGIN & NAVIGATION
  1. Login as Operator
  2. Verify sidebar: ONLY Dashboard and Manufacturing visible
  3. Verify: Products, Builds, Validation, Fixtures, Kubernetes, Users ALL hidden

PHASE 2: MANUFACTURING OPERATIONS
  4. Navigate to Manufacturing → verify page loads
  5. View manufacturing runs → verify list loads (manufacturing:view)
  6. Trigger manufacturing run → verify succeeds (manufacturing:run)
  7. Monitor manufacturing session
  8. View results

PHASE 3: STRICT PERMISSION BOUNDARIES
  9. Navigate to /products → verify redirect/blocked
  10. Navigate to /builds → verify redirect/blocked
  11. Navigate to /validation → verify redirect/blocked
  12. Navigate to /fixtures → verify redirect/blocked
  13. Navigate to /users → verify redirect/blocked
  14. Navigate to /kubernetes → verify redirect/blocked
  15. Attempt products:view via API → verify 403
  16. Attempt builds:view via API → verify 403
  17. Attempt validation:view via API → verify 403
  18. Attempt fixtures:view via API → verify 403
  19. Verify manufacturing:manage via API → verify ALLOWED (Operator has this)

PHASE 4: CLEANUP
  20. No resources to clean (Operator can only run, not create)
```

---

## 7. Acceptance Criteria

### 7.1 Suite-Level Criteria

- [ ] Suite runs from a fresh database (migrate, NO seed) to full system usage and back to clean state
- [ ] All 4 role stories execute completely without manual intervention
- [ ] Real Bitbucket branches/PRs created and cleaned up
- [ ] Real firmware builds compile on Build Service
- [ ] Real validation tests execute on MTIB <MTIB_HOST> with DUT Alpha B0
- [ ] Build caching verified (second identical build returns CACHED)
- [ ] Validation queue correctly assigns runs when fixtures become available
- [ ] WebSocket real-time updates verified (test results stream to UI)
- [ ] All Bitbucket branches/PRs cleaned up after suite
- [ ] CoreCloud device state cleaned up after suite
- [ ] Database contains zero user-created data after cleanup

### 7.2 Per-Domain Criteria

**Products:**
- [ ] Product created via full wizard flow (4 steps with ck_boards discovery)
- [ ] All 5 tabs render correctly on detail page
- [ ] Stage configuration wizard completes for all 5 stages
- [ ] Product deletion blocked when it has build history (409)
- [ ] Product deletion succeeds when clean

**Builds:**
- [ ] Build triggered automatically by git-poller detecting PR
- [ ] Build status transitions visible in UI (QUEUED → CLONING → BUILDING → SUCCESS)
- [ ] Build artifacts downloadable
- [ ] Build caching works (duplicate fingerprint → CACHED)
- [ ] PR pipeline view shows correct build matrix

**Validation:**
- [ ] Queue entries created automatically when builds complete
- [ ] Queue entry waits in QUEUED until fixture available
- [ ] Fixture assignment triggers ASSIGNED → RUNNING transition
- [ ] Real tests execute on MTIB hardware
- [ ] Test results appear in real-time via WebSocket
- [ ] Session completes with correct pass/fail counts
- [ ] Fixture released after session completion

**Fixtures:**
- [ ] Design CRUD with unique name enforcement
- [ ] Instance CRUD with product/board revision binding
- [ ] Slot assignment triggers MTIB deployment
- [ ] Fixture status transitions (AVAILABLE → LOCKED → AVAILABLE)
- [ ] Deletion blocked when fixture has session history

**Users:**
- [ ] User CRUD with role assignment
- [ ] Permission set CRUD
- [ ] API key creation (shown once) and revocation
- [ ] Deactivation (soft delete)

**Roles:**
- [ ] Admin sees all sidebar items, can do everything
- [ ] Maintainer sees all except Users, cannot manage users/system/k8s
- [ ] Developer sees Products through Fixtures, cannot manage products/fixtures/validation
- [ ] Operator sees only Dashboard + Manufacturing, cannot access anything else
- [ ] Permission denials return 403 via API
- [ ] UI correctly hides/shows elements per role

### 7.3 Cleanup Criteria

- [ ] All Bitbucket branches created during tests are deleted
- [ ] All Bitbucket PRs created during tests are declined/closed
- [ ] concord-main branch is synced with main (left in clean state)
- [ ] All CoreCloud FUOTA plans deactivated
- [ ] Database has zero products, builds, sessions, fixtures (beyond system defaults)
- [ ] Database Secrets created during tests are deleted
- [ ] PollCache entries for E2E branches are deleted
- [ ] AuditLog entries are EXCLUDED from zero-state check (append-only by design)
- [ ] MinIO artifacts from test builds are removed
- [ ] K8s Jobs/Pods from validation runs are cleaned up
