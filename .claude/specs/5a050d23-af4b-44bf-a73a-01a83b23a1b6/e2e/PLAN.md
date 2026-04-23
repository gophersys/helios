# E2E Implementation Plan

**Last updated:** 2026-04-08

---

## Stage Overview

| # | Name | Description | Dependencies | Est. Tests | Est. Duration |
|---|------|-------------|--------------|------------|---------------|
| 1 | **Foundation** | Playwright infrastructure, page objects, helpers, docker-compose test config | None | 0 (infra only) | 2-3 hours |
| 2 | **Auth & Navigation** | Login flows for all 4 roles, sidebar visibility, route guards, View-As-Role | Stage 1 | ~40 | 1-2 hours |
| 3 | **Product CRUD** | Product creation wizard, detail page tabs, edit, delete, board management | Stage 2 | ~50 | 2-3 hours |
| 4 | **Stage Configuration** | Stage config wizard, recipe editor, build matrix, signing keys | Stage 3 | ~30 | 2 hours |
| 5 | **Bitbucket Integration** | Branch/PR helpers, concord-main sync, git-poller trigger verification | Stage 1 | ~15 | 1-2 hours |
| 6 | **Build Pipeline** | Build triggering, status monitoring, artifact download, caching verification | Stages 4, 5 | ~35 | 2-3 hours |
| 7 | **Fixture & MTIB Fixes** | IMPL+TEST: Fix MTIB deploy/undeploy (Docker+K8s), fixture CRUD, slot assignment | Stage 2 | ~45 | 3-4 hours |
| 8 | **Validation Queue** | Queue creation, priority ordering, fixture assignment, scheduler verification | Stages 6, 7 | ~25 | 2 hours |
| 9 | **Validation Execution** | Real MTIB test execution, WebSocket monitoring, result verification | Stage 8 | ~20 | 2-3 hours |
| 10 | **Manufacturing Backend** | IMPL: API endpoints, permissions, session/panel/unit models, reporter callbacks | Stage 7 | ~25 | 4-6 hours |
| 11 | **Manufacturing Frontend** | IMPL: Fixture list, session runner, QR input, live panel results, history | Stage 10 | ~20 | 4-6 hours |
| 12 | **Manufacturing Setup Wizard** | IMPL: Product mfg tab, stage config wizard, firmware selection, pass criteria | Stages 10, 11 | ~15 | 3-4 hours |
| 13 | **Manufacturing E2E** | Full Playwright E2E: setup → create fixture → start session → run panels → results | Stages 11, 12 | ~30 | 2-3 hours |
| 14 | **User Management** | User CRUD, permission sets, API keys, role assignment | Stage 2 | ~30 | 1-2 hours |
| 15 | **Role Stories** | Complete user stories for all 4 roles, permission denial verification | All above | ~80 | 3-4 hours |
| 16 | **Cleanup & Orchestration** | Suite runner, cleanup utilities, data reset, Bitbucket/CoreCloud cleanup | All above | ~18 | 2 hours |

**Total Estimated Tests:** ~485 (E2E + unit tests for new features)
**Total Estimated Duration:** 36-50 hours of development

---

## Stage Dependency Graph

```
Stage 1 (Foundation)
    |
    +---> Stage 2 (Auth & Nav)
    |        |
    |        +---> Stage 3 (Product CRUD)
    |        |        |
    |        |        +---> Stage 4 (Stage Config)
    |        |                 |
    |        |                 +---> Stage 6 (Builds) <--- Stage 5
    |        |                          |
    |        |                          +---> Stage 8 (Val Queue) <--- Stage 7
    |        |                                   |
    |        |                                   +---> Stage 9 (Val Execution)
    |        |
    |        +---> Stage 7 (Fixture + MTIB Fixes) [IMPLEMENT]
    |        |        |
    |        |        +---> Stage 10 (Mfg Backend) [IMPLEMENT]
    |        |                 |
    |        |                 +---> Stage 11 (Mfg Frontend) [IMPLEMENT]
    |        |                          |
    |        |                          +---> Stage 12 (Mfg Wizard) [IMPLEMENT]
    |        |                                    |
    |        |                                    +---> Stage 13 (Mfg E2E)
    |        |
    |        +---> Stage 14 (User Management)
    |
    +---> Stage 5 (Bitbucket Integration)

All stages 1-14 --> Stage 15 (Role Stories)
All stages --> Stage 16 (Cleanup & Orchestration)

PARALLELISM (wave-based):

WAVE 1: Stage 1 + Stage 5                  [2 worktrees]
WAVE 2: Stage 2 + Stage 7 + Stage 10 + Stage 14  [4 worktrees]
WAVE 3: Stage 3 + Stage 11 + Stage 12      [3 worktrees]
WAVE 4: Stage 4 -> 6 -> 8 -> 9 + Stage 13  [sequential + 1 worktree]
WAVE 5: Stage 15 -> Stage 16               [sequential]
```

---

## Stage Details

### Stage 1: Foundation

**Goal:** Set up Playwright infrastructure that all tests build on.

**Deliverables:**
- Extended Playwright config for E2E suite (separate from existing unit E2E)
- Page Object base class
- Page objects for: Login, Dashboard, Sidebar, Products, ProductDetail, Builds, BuildDetail, Validation, ValidationRunDetail, Fixtures, Manufacturing, Users
- API helper extensions (Bitbucket, CoreCloud, MTIB health check)
- Test data factories (product config, fixture config, user config)
- Fresh DB helper (migrate + reset, no seed)
- Global setup/teardown (docker-compose lifecycle)
- Environment config loader (MTIB address, CoreCloud creds, Bitbucket creds)

**Gate:** All page objects instantiate without error against running dev stack.

### Stage 2: Auth & Navigation

**Goal:** Verify login for all 4 roles and correct sidebar/route behavior.

**Test Files:**
- `e2e/stories/auth/login.spec.ts` — Dev login buttons, JWT storage, logout
- `e2e/stories/auth/sidebar.spec.ts` — Per-role sidebar visibility
- `e2e/stories/auth/route-guards.spec.ts` — Unauthorized route access redirects
- `e2e/stories/auth/view-as-role.spec.ts` — Admin/Maintainer can simulate lower roles

**Gate:** All 4 roles can log in, see correct sidebar items, and get blocked from unauthorized routes.

### Stage 3: Product CRUD

**Goal:** Full product lifecycle through the UI.

**Test Files:**
- `e2e/stories/products/creation-wizard.spec.ts` — 4-step wizard with ck_boards discovery
- `e2e/stories/products/detail-tabs.spec.ts` — All 5 tabs render and display data
- `e2e/stories/products/edit.spec.ts` — Inline edit on detail page
- `e2e/stories/products/delete.spec.ts` — Delete with cascade, blocked when has history
- `e2e/stories/products/board-management.spec.ts` — Board revisions, targets, modem firmware

**Gate:** Product created via wizard, all tabs populated, edit saves, delete works.

### Stage 4: Stage Configuration

**Goal:** Configure all 5 validation stages for a product.

**Test Files:**
- `e2e/stories/products/stage-config-wizard.spec.ts` — 4-step wizard per stage
- `e2e/stories/products/recipe-editor.spec.ts` — Recipe YAML editing, validation, history
- `e2e/stories/products/build-matrix.spec.ts` — Matrix configuration per stage

**Gate:** All 5 stages enabled with correct config, recipe saved, matrix defined.

### Stage 5: Bitbucket Integration

**Goal:** Helpers for branch/PR management, concord-main sync.

**Test Files:**
- `e2e/stories/bitbucket/sync.spec.ts` — Sync concord-main with main
- `e2e/stories/bitbucket/branch-pr.spec.ts` — Create branch, open PR, verify detection

**Gate:** concord-main synced, PR created, git-poller detects it.

### Stage 6: Build Pipeline

**Goal:** End-to-end build execution with real firmware compilation.

**Test Files:**
- `e2e/stories/builds/auto-trigger.spec.ts` — Git-poller triggers build from PR
- `e2e/stories/builds/monitoring.spec.ts` — Status transitions in UI, log streaming
- `e2e/stories/builds/artifacts.spec.ts` — Artifact listing, download
- `e2e/stories/builds/caching.spec.ts` — Duplicate build returns CACHED
- `e2e/stories/builds/pr-pipeline.spec.ts` — PR pipeline view with matrix

**Gate:** Build completes successfully, artifacts downloadable, caching verified.

### Stage 7: Fixture Management

**Goal:** Full fixture lifecycle through the UI.

**Test Files:**
- `e2e/stories/fixtures/designs.spec.ts` — Design CRUD
- `e2e/stories/fixtures/instances.spec.ts` — Fixture CRUD with type selection
- `e2e/stories/fixtures/slots.spec.ts` — Slot management, node assignment
- `e2e/stories/fixtures/deployment.spec.ts` — MTIB deploy/undeploy via slot assign
- `e2e/stories/fixtures/deletion.spec.ts` — Deletion constraints

**Gate:** Fixture created, node assigned, MTIB deployed, fixture AVAILABLE.

### Stage 8: Validation Queue

**Goal:** Queue management and automatic fixture assignment.

**Test Files:**
- `e2e/stories/validation/queue-creation.spec.ts` — Auto-queue from builds
- `e2e/stories/validation/queue-assignment.spec.ts` — Fixture auto-assignment
- `e2e/stories/validation/queue-priority.spec.ts` — Priority ordering
- `e2e/stories/validation/queue-ui.spec.ts` — Queue page, stats, promote/cancel

**Gate:** Queue entries created from builds, assigned to fixtures when available.

### Stage 9: Validation Execution

**Goal:** Real test execution on MTIB hardware with result verification.

**Test Files:**
- `e2e/stories/validation/execution.spec.ts` — Session start, MTIB interaction
- `e2e/stories/validation/realtime.spec.ts` — WebSocket test timeline updates
- `e2e/stories/validation/results.spec.ts` — Pass/fail counts, test details
- `e2e/stories/validation/run-detail.spec.ts` — Charts, UART, artifacts

**Gate:** Validation session runs on real MTIB, results appear in UI via WebSocket.

### Stage 10: Manufacturing

**Goal:** Manufacturing workflow (single stage, mirrors validation).

**Test Files:**
- `e2e/stories/manufacturing/fixture.spec.ts` — Manufacturing fixture setup
- `e2e/stories/manufacturing/session.spec.ts` — Trigger and monitor
- `e2e/stories/manufacturing/results.spec.ts` — POST test results

**Gate:** Manufacturing session completes, results visible.

### Stage 11: User Management

**Goal:** Full user lifecycle through the UI.

**Test Files:**
- `e2e/stories/users/user-crud.spec.ts` — Create, edit, deactivate users
- `e2e/stories/users/permission-sets.spec.ts` — Permission set CRUD
- `e2e/stories/users/api-keys.spec.ts` — Key creation, revocation
- `e2e/stories/users/role-assignment.spec.ts` — Role changes, permission set binding

**Gate:** Users created with roles, permission sets assigned, API keys work.

### Stage 12: Role Stories

**Goal:** Complete user stories for each role, including permission denial tests.

**Test Files:**
- `e2e/stories/roles/admin.spec.ts` — Full Admin journey (SPEC section 6.1)
- `e2e/stories/roles/maintainer.spec.ts` — Full Maintainer journey (SPEC section 6.2)
- `e2e/stories/roles/developer.spec.ts` — Full Developer journey (SPEC section 6.3)
- `e2e/stories/roles/operator.spec.ts` — Full Operator journey (SPEC section 6.4)

**Gate:** All 4 role stories pass, permission boundaries verified.

### Stage 13: Cleanup & Orchestration

**Goal:** Suite runner, cleanup utilities, full lifecycle orchestration.

**Test Files:**
- `e2e/stories/cleanup/bitbucket.spec.ts` — Branch/PR cleanup
- `e2e/stories/cleanup/corecloud.spec.ts` — Device state cleanup
- `e2e/stories/cleanup/database.spec.ts` — Data verification (zero state)
- `e2e/stories/cleanup/minio.spec.ts` — Artifact cleanup

**Orchestration:**
- Global setup: Fresh DB, verify external connectivity
- Global teardown: Full cleanup
- Test ordering: Stages execute in dependency order
- Failure handling: Cleanup runs even on test failure

**Gate:** System returns to zero-data state after full suite.
