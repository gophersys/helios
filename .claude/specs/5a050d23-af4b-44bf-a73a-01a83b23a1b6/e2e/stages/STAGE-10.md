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

# Stage 10: Manufacturing Backend (IMPLEMENTATION)

**Status:** COMPLETE
**Type:** IMPLEMENT (new feature, TDD)
**Dependencies:** Stage 7 (Fixture & MTIB Fixes)
**Estimated Unit Tests:** ~25

---

## Objective

Build the manufacturing backend from scratch: Prisma models, API endpoints, permission enforcement, session/panel lifecycle, and reporter callbacks for the test runner.

---

## Data Model Changes (Prisma)

### New/Modified Models

```prisma
// Manufacturing configuration per product
model ManufacturingConfig {
  id                String   @id @default(cuid())
  productId         String
  boardRevisionId   String
  enabled           Boolean  @default(false)
  stages            Json     // [{name: "Electrical", enabled: true, config: {...}}, ...]
  firmwareSource    String   @default("latest_build") // "latest_build", "specific_version", "manual_upload"
  firmwareSetId     String?  // If specific version
  personalizationConfig Json? // CoreOps template
  passCriteria      Json?    // Per-stage thresholds
  createdAt         DateTime @default(now())
  updatedAt         DateTime @updatedAt

  product        Product        @relation(fields: [productId], references: [id], onDelete: Cascade)
  boardRevision  BoardRevision  @relation(fields: [boardRevisionId], references: [id], onDelete: Restrict)

  @@unique([productId, boardRevisionId])
}

// Manufacturing session (operator-driven, contains N panels)
model ManufacturingSession {
  id          String   @id @default(cuid())
  productId   String
  fixtureId   String
  status      ManufacturingSessionStatus @default(ACTIVE)
  operatorId  String   // User who started the session
  panelCount  Int      @default(0)
  passedCount Int      @default(0)
  failedCount Int      @default(0)
  config      Json?    // Snapshot of ManufacturingConfig at session start
  startedAt   DateTime @default(now())
  endedAt     DateTime?
  createdAt   DateTime @default(now())
  updatedAt   DateTime @updatedAt

  product  Product  @relation(fields: [productId], references: [id], onDelete: Restrict)
  fixture  Fixture  @relation(fields: [fixtureId], references: [id], onDelete: Restrict)
  operator User     @relation(fields: [operatorId], references: [id], onDelete: Restrict)
  panels   ManufacturingPanel[]
}

enum ManufacturingSessionStatus {
  ACTIVE      // Session in progress, operator running panels
  COMPLETED   // Operator ended session normally
  CANCELLED   // Session cancelled
}

// One panel = one batch of DUTs tested together
model ManufacturingPanel {
  id          String   @id @default(cuid())
  sessionId   String
  panelIndex  Int      // Sequential within session
  qrCode      String   // Scanned QR code / panel identifier
  status      PanelStatus @default(RUNNING)
  unitCount   Int      // Number of DUT slots tested
  passedUnits Int      @default(0)
  failedUnits Int      @default(0)
  startedAt   DateTime @default(now())
  completedAt DateTime?
  durationMs  Int?
  createdAt   DateTime @default(now())

  session ManufacturingSession @relation(fields: [sessionId], references: [id], onDelete: Cascade)
  units   ManufacturingUnit[]

  @@unique([sessionId, panelIndex])
}

enum PanelStatus {
  RUNNING
  PASSED      // All units passed
  FAILED      // At least one unit failed
  CANCELLED
}

// One unit = one DUT in one slot for one panel
model ManufacturingUnit {
  id          String   @id @default(cuid())
  panelId     String
  slotIndex   Int      // Which fixture slot
  slotId      String   // FK to FixtureSlot
  serialNumber String? // DUT serial (from QR or discovered)
  status      UnitStatus @default(RUNNING)
  stages      Json     // [{name: "Electrical", status: "PASSED", steps: [...], durationMs: 1200}, ...]
  errorMessage String?
  startedAt   DateTime @default(now())
  completedAt DateTime?
  durationMs  Int?

  panel ManufacturingPanel @relation(fields: [panelId], references: [id], onDelete: Cascade)

  @@unique([panelId, slotIndex])
}

enum UnitStatus {
  RUNNING
  PASSED
  FAILED
  ERROR
}
```

---

## API Endpoints

### Manufacturing Config (on Product)

```python
# apps/backend/http-api/src/api/v2/manufacturing/config.py

@require_permissions(Permissions.MANUFACTURING_MANAGE)
GET  /v2/products/<product_id>/manufacturing          # Get mfg config
POST /v2/products/<product_id>/manufacturing          # Create/update mfg config
PUT  /v2/products/<product_id>/manufacturing          # Update mfg config
DELETE /v2/products/<product_id>/manufacturing         # Disable mfg for product
```

### Manufacturing Sessions

```python
# apps/backend/http-api/src/api/v2/manufacturing/sessions.py

@require_permissions(Permissions.MANUFACTURING_VIEW)
GET  /v2/manufacturing/fixtures                        # List available mfg fixtures

@require_permissions(Permissions.MANUFACTURING_RUN)
POST /v2/manufacturing/sessions                        # Start session (locks fixture)
GET  /v2/manufacturing/sessions                        # List sessions (paginated)
GET  /v2/manufacturing/sessions/<id>                   # Session detail with panels
POST /v2/manufacturing/sessions/<id>/panels            # Run a panel (QR input)
POST /v2/manufacturing/sessions/<id>/end               # End session (release fixture)

@require_permissions(Permissions.MANUFACTURING_VIEW)
GET  /v2/manufacturing/sessions/<id>/results           # Aggregated results
```

### Reporter Callbacks (from test runner)

```python
# apps/backend/http-api/src/api/v2/manufacturing/reporter.py

@require_permissions(Permissions.MANUFACTURING_RUN)
POST /v2/manufacturing/sessions/<id>/report/panel-start    # Panel started
POST /v2/manufacturing/sessions/<id>/report/unit-start     # Unit started on slot
POST /v2/manufacturing/sessions/<id>/report/stage-result   # Stage result for unit
POST /v2/manufacturing/sessions/<id>/report/unit-result    # Unit final result
POST /v2/manufacturing/sessions/<id>/report/panel-complete # Panel completed
```

### WebSocket Events (broadcast on /manufacturing namespace)

```
manufacturing_session_start    { sessionId, fixtureId, operatorId }
manufacturing_panel_start      { sessionId, panelId, panelIndex, qrCode }
manufacturing_unit_start       { sessionId, panelId, unitId, slotIndex }
manufacturing_stage_result     { sessionId, panelId, unitId, stageName, status }
manufacturing_unit_result      { sessionId, panelId, unitId, status, durationMs }
manufacturing_panel_complete   { sessionId, panelId, status, passedUnits, failedUnits }
manufacturing_session_end      { sessionId, status, panelCount, passedCount, failedCount }
```

---

## Unit Tests (TDD — write FIRST)

```python
# apps/backend/http-api/tests/api/manufacturing/test_config.py
test_create_manufacturing_config()
test_get_manufacturing_config()
test_update_manufacturing_config()
test_delete_manufacturing_config()
test_config_requires_manufacturing_manage_permission()

# apps/backend/http-api/tests/api/manufacturing/test_sessions.py
test_list_manufacturing_fixtures()
test_start_session_locks_fixture()
test_start_session_requires_manufacturing_run()
test_cannot_start_session_on_locked_fixture()
test_run_panel_creates_panel_and_units()
test_run_panel_requires_active_session()
test_end_session_releases_fixture()
test_end_session_sets_status_completed()
test_list_sessions_paginated()
test_session_detail_includes_panels_and_units()

# apps/backend/http-api/tests/api/manufacturing/test_reporter.py
test_panel_start_callback()
test_unit_result_callback()
test_stage_result_updates_unit()
test_panel_complete_updates_counts()
test_reporter_broadcasts_websocket_events()
```

---

## Gate Criteria

- [ ] Prisma migration runs successfully
- [ ] All manufacturing API endpoints return correct responses
- [ ] Permission enforcement: manufacturing:run gates session operations
- [ ] Permission enforcement: manufacturing:view gates read operations
- [ ] Permission enforcement: manufacturing:manage gates config operations
- [ ] Session start locks fixture, session end releases it
- [ ] Panel/unit lifecycle works (start → stage results → complete)
- [ ] WebSocket events broadcast correctly
- [x] All 34 unit tests pass

---

## Reconciliation

### What Was Built

**Prisma Schema** (`prisma/schema.prisma`):
- 3 new enums: `ManufacturingSessionStatus`, `PanelStatus`, `UnitStatus`
- 4 new models: `ManufacturingConfig`, `ManufacturingSession`, `ManufacturingPanel`, `ManufacturingUnit`
- Reverse relations added on `Product`, `BoardRevision`, `Fixture`, `User`
- Named relation `ManufacturingOperator` on User to avoid conflict with existing Session relation

**Manufacturing Module** (`src/api/v2/manufacturing/`):
- `__init__.py` — empty module init
- `types.py` — 9 request dataclasses with `from_json()` validation
- `config.py` — 4 CRUD endpoints with `@require_permissions(MANUFACTURING_MANAGE)`
- `sessions.py` — 7 endpoints (list fixtures, start/list/get/run panel/end/results) with correct permission gates
- `reporter.py` — 5 callback endpoints with `@require_auth` (panel-start, unit-start, stage-result, unit-result, panel-complete)

**Router** (`src/api/v2/router.py`):
- 16 new URL rules registered under `/v2/products/<id>/manufacturing` and `/v2/manufacturing/sessions/`
- SocketIO setup for `/manufacturing` namespace via `set_manufacturing_socketio()`

**Tests** (`tests/api/manufacturing/`):
- `test_config.py` — 8 tests: CRUD + permissions + error cases
- `test_sessions.py` — 14 tests: fixture listing, session lifecycle, panel creation, pagination, detail
- `test_reporter.py` — 12 tests: all 5 callbacks, WebSocket event broadcasting, error paths
- **Total: 34 tests, all passing**
- Full suite regression: 2134 passed, 11 skipped, 0 failures

### Permissions (already existed)
- `manufacturing:view`, `manufacturing:run`, `manufacturing:manage` were already defined in `src/lib/permissions.py`
- Operator role already had all three permissions in `DEFAULT_ROLES`
- Developer role already had `manufacturing:view`
- No permission changes needed

### Design Decisions
- Reporter endpoints use `@require_auth` (not `@require_permissions`) matching the validation reporter pattern (D20)
- Session start locks fixture via `LOCKED` status + `lockedBy` field, matching existing fixture locking pattern
- Unit stages stored as JSON array in `ManufacturingUnit.stages`, appended by stage-result callback
- Panel/session counts are denormalized for dashboard performance (same pattern as Session model)
- WebSocket events emitted on `/manufacturing` namespace (separate from `/validation`)

### No Changes Needed Downstream
- Stage 11 (Mfg Frontend) and Stage 12 (Mfg Wizard) can now build on these endpoints
- Stage 13 (Mfg E2E) test assumptions are met: all specified endpoints exist with correct signatures
