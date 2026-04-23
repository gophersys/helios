# Critical Path E2E Test Specification

**Last reviewed:** 2026-04-13
**Status:** Draft

Step-by-step test plan covering every configuration combination through the product lifecycle. Each scenario starts clean, builds up state, and verifies every transition.

---

## Test Matrix

The system has 3 asset source types × 2 stage types × 5 validation stages = 30 possible configurations. Not all are valid. The meaningful combinations are:

| # | Scenario | Asset Source | Stage Type | Stage | What It Tests |
|---|----------|-------------|------------|-------|---------------|
| 1 | Build Service → Smoke | BUILD_SERVICE | VALIDATION | 1 | Git poller → build → auto asset set → validation queue |
| 2 | Manual Upload → Driver | MANUAL_UPLOAD | VALIDATION | 2 | Zip upload → parse → asset set → validation |
| 3 | External CI → Integration | EXTERNAL_CI | VALIDATION | 3 | Webhook ingest → asset set → validation |
| 4 | Build Service → Regression (matrix) | BUILD_SERVICE | VALIDATION | 4 | Stage 4 has 8 builds instead of 4. Tests matrix mode. |
| 5 | Build Service → FUOTA | BUILD_SERVICE | VALIDATION | 5 | Firmware update test with version bumps |
| 6 | Manufacturing | BUILD_SERVICE | MANUFACTURING | 1 | Manufacturing session with multi-DUT fixture |

Each scenario is independent — creates its own product, board, revision, and stage config from scratch.

---

## Scenario 1: Build Service → Smoke Validation

The golden path. Product with firmware repo → git push detected → build triggered → artifacts uploaded → asset set created → validation queued → tests run → results visible.

### Phase 1: Product Setup

```
Step 1.1: Create product
  POST /v2/products
  Body: {
    name: "E2E-Smoke-${timestamp}",
    slug: "e2e-smoke-${timestamp}",
    description: "Critical path E2E test",
    fwRepoSlug: "alpha_fw"
  }
  Assert: HTTP 201
  Assert: response.data.id exists
  Assert: response.data.status == "ACTIVE"
  Assert: response.data.fwRepoSlug == "alpha_fw"
  Save: productId = response.data.id

Step 1.2: Create board
  POST /v2/products/${productId}/boards
  Body: {
    name: "E2E Board",
    ckBoardsFamily: "e2e-smoke-${timestamp}",
    vendor: "corekinect"
  }
  Assert: HTTP 201
  Save: boardId = response.data.id

Step 1.3: Create board revision
  POST /v2/products/${productId}/boards/${boardId}/revisions
  Body: {
    version: "B0",
    ckBoardsName: "e2e_smoke_b0_${timestamp}",
    socs: ["nrf52840", "nrf9151"],
    deviceType: 2,
    deviceVariant: 3
  }
  Assert: HTTP 201
  Assert: response.data.socs contains "nrf52840" and "nrf9151"
  Save: revisionId = response.data.id

Step 1.4: Create product targets
  POST /v2/products/${productId}/boards/${boardId}/revisions/${revisionId}/targets
  Body: { role: "app", soc: "nrf52840", appId: 109 }
  Assert: HTTP 201
  Save: appTargetId

  POST /v2/products/${productId}/boards/${boardId}/revisions/${revisionId}/targets
  Body: { role: "comms", soc: "nrf9151", appId: 108 }
  Assert: HTTP 201
  Save: commsTargetId

Step 1.5: Verify product state
  GET /v2/products/${productId}?include=boards,revisions,targets
  Assert: product has 1 board
  Assert: board has 1 revision
  Assert: revision has 2 targets
  Assert: targets have roles ["app", "comms"]
```

### Phase 2: Stage Configuration

```
Step 2.1: Initialize default stages
  POST /v2/products/${productId}/initialize-stages
  Body: { boardRevisionId: "${revisionId}" }
  Assert: HTTP 200
  Assert: 5 stage configs created (stages 1-5, all VALIDATION, all disabled)

Step 2.2: Enable Stage 1 (Smoke) with BUILD_SERVICE
  PATCH /v2/products/${productId}/stages/${stage1ConfigId}
  Body: {
    enabled: true,
    watchBranch: "main",
    triggerTypes: ["manual", "pr_push"],
    assetSources: ["BUILD_SERVICE"]
  }
  Assert: HTTP 200
  Assert: response.data.enabled == true
  Assert: response.data.watchBranch == "main"
  Assert: response.data.assetSources == ["BUILD_SERVICE"]

Step 2.3: Verify build matrix populated
  GET /v2/products/${productId}/stages/${stage1ConfigId}
  Assert: response.data.buildMatrix exists
  Assert: buildMatrix has entries with labels (mfg_base, etc.)
  Assert: each entry has fwType, variant, processor
```

### Phase 3: Build Trigger & Execution

```
Step 3.1: Trigger build manually
  POST /v2/products/${productId}/stages/1?configId=${stage1ConfigId}&buildNow=true
  Assert: HTTP 200 or 201
  Save: buildRunId

Step 3.2: Verify BuildRun created
  GET /v2/builds/runs/${buildRunId}
  Assert: status in ["PENDING", "BUILDING"]
  Assert: expectedBuilds > 0
  Assert: stageConfigId == stage1ConfigId
  Save: expectedBuilds count

Step 3.3: Wait for builds to complete (poll every 5s, timeout 300s)
  POLL: GET /v2/builds/runs/${buildRunId}
  Until: status in ["SUCCESS", "BUILD_FAILED", "CANCELLED"]
  Assert: status == "SUCCESS" (or "VALIDATING")
  Assert: completedBuilds == expectedBuilds
  
Step 3.4: Verify BuildJobs all succeeded
  GET /v2/builds/runs/${buildRunId}?include=builds
  For each BuildJob:
    Assert: status in ["SUCCESS", "CACHED"]
    Assert: artifacts exist (at least 1 per job)
    Assert: storageKey is non-empty (file is in MinIO)
    Assert: checksum is non-empty
```

### Phase 4: Asset Set Verification

```
Step 4.1: Verify AssetSet auto-created
  GET /v2/products/${productId}/asset-sets
  Assert: at least 1 asset set exists
  Assert: latest asset set has buildRunId == buildRunId
  Assert: source == "BUILD_SERVICE"
  Save: assetSetId

Step 4.2: Verify assets within set
  GET /v2/products/${productId}/asset-sets/${assetSetId}
  Assert: status in ["PENDING", "COMPLETE"]
  Assert: assets array is non-empty
  For each asset:
    Assert: storageKey exists
    Assert: filename exists
    Assert: sizeBytes > 0
    Assert: checksum is non-empty

Step 4.3: Complete asset set (if still PENDING)
  If status == "PENDING":
    POST /v2/asset-sets/${assetSetId}/complete
    Assert: HTTP 200
    Assert: response.data.status == "COMPLETE"
```

### Phase 5: Validation (if fixtures are available)

```
Step 5.1: Queue validation
  POST /v2/runs/queue
  Body: {
    assetSetId: "${assetSetId}",
    stageConfigId: "${stage1ConfigId}",
    reason: "E2E critical path test"
  }
  Assert: HTTP 201
  Save: queueEntryId

Step 5.2: Check queue status
  GET /v2/runs/queue/${queueEntryId}
  Assert: status in ["QUEUED", "ASSIGNED", "RUNNING"]

  Note: If no fixtures available, status stays QUEUED — this is valid.
  The test should not fail if no hardware is connected. Record the
  status and continue.

Step 5.3: If RUNNING — wait for completion (poll, timeout 600s)
  POLL: GET /v2/runs/queue/${queueEntryId}
  Until: status in ["COMPLETED", "FAILED", "CANCELLED"]
  
Step 5.4: Verify TestRun results (if completed)
  GET /v2/runs/${testRunId}
  Assert: status == "COMPLETED"
  Assert: targetCount > 0
  Assert: passedCount + failedCount == completedCount
  
  For each RunTarget:
    Assert: status in ["PASSED", "FAILED"]
    Assert: executionCount > 0
```

### Phase 6: Cleanup

```
Step 6.1: Cancel any active queue entries
  POST /v2/runs/queue/${queueEntryId}/cancel (if still active)

Step 6.2: Archive product
  PATCH /v2/products/${productId}
  Body: { status: "ARCHIVED" }

Step 6.3: Delete product (cascades boards, revisions, targets, stage configs)
  DELETE /v2/products/${productId}
  Assert: HTTP 200
```

---

## Scenario 2: Manual Upload → Driver Validation

Tests the manual firmware upload flow — no git integration needed.

### Phase 1: Product Setup (same as Scenario 1 but without fwRepoSlug)

```
Step 1.1: Create product WITHOUT firmware repo
  POST /v2/products
  Body: {
    name: "E2E-Manual-${timestamp}",
    slug: "e2e-manual-${timestamp}",
    description: "Manual upload E2E test"
    // No fwRepoSlug — this product uses manual uploads
  }
  Assert: response.data.fwRepoSlug == null

Steps 1.2-1.5: Same as Scenario 1 (board, revision, targets)
```

### Phase 2: Stage Config for Manual Upload

```
Step 2.1: Initialize stages
  Same as Scenario 1

Step 2.2: Enable Stage 2 (Driver) with MANUAL_UPLOAD
  PATCH /v2/products/${productId}/stages/${stage2ConfigId}
  Body: {
    enabled: true,
    assetSources: ["MANUAL_UPLOAD"],
    triggerTypes: ["manual"]
  }
  Assert: watchBranch is null (cleared because no BUILD_SERVICE)
  Assert: assetSources == ["MANUAL_UPLOAD"]
```

### Phase 3: Upload Firmware

```
Step 3.1: Create asset set
  POST /v2/products/${productId}/asset-sets
  Body: {
    version: "0.1.0",
    variant: "debug",
    source: "MANUAL_UPLOAD",
    stage: 2,
    stageConfigId: "${stage2ConfigId}",
    boardRevisionId: "${revisionId}"
  }
  Assert: HTTP 201
  Assert: source == "MANUAL_UPLOAD"
  Save: assetSetId

Step 3.2: Upload firmware zip
  POST /v2/products/${productId}/asset-sets/upload-zip
  Body: multipart/form-data with test firmware zip
  Assert: HTTP 200
  Assert: files extracted and stored in MinIO

Step 3.3: Complete asset set
  POST /v2/asset-sets/${assetSetId}/complete
  Assert: status == "COMPLETE"
```

### Phase 4-6: Validation + Cleanup (same as Scenario 1)

---

## Scenario 3: External CI → Integration

Tests the external CI webhook flow — firmware comes from TeamCity/Jenkins.

### Phase 2: Stage Config for External CI

```
Step 2.2: Enable Stage 3 (Integration) with EXTERNAL_CI
  PATCH /v2/products/${productId}/stages/${stage3ConfigId}
  Body: {
    enabled: true,
    assetSources: ["EXTERNAL_CI"],
    triggerTypes: ["manual"]
  }
  Assert: assetSources == ["EXTERNAL_CI"]
```

### Phase 3: External CI Webhook

```
Step 3.1: Create asset set via external webhook
  POST /v2/products/${productId}/asset-sets
  Body: {
    version: "1.0.0-rc1",
    variant: "release",
    source: "EXTERNAL_CI",
    externalBuildId: "TC-12345",
    stage: 3,
    stageConfigId: "${stage3ConfigId}",
    boardRevisionId: "${revisionId}",
    commitSha: "abc1234",
    branch: "main"
  }
  Assert: HTTP 201
  Assert: source == "EXTERNAL_CI"
  Assert: externalBuildId == "TC-12345"
```

---

## Scenario 4: Build Service → Stage 4 Regression (Matrix Mode)

Stage 4 uses an expanded build matrix (8 builds instead of 4). Tests matrix handling.

### Phase 2: Stage Config

```
Step 2.2: Enable Stage 4 (Regression)
  PATCH /v2/products/${productId}/stages/${stage4ConfigId}
  Body: {
    enabled: true,
    watchBranch: "main",
    assetSources: ["BUILD_SERVICE"]
  }

Step 2.3: Verify expanded build matrix
  GET /v2/products/${productId}/stages/${stage4ConfigId}
  Assert: buildMatrix has 8 entries (stage 4 regression matrix)
  Assert: some entries have versionBump == true
  Assert: some entries have baseLabel pointing to another entry
```

### Phase 3: Build with Matrix

```
Step 3.1: Trigger build
  POST /v2/products/${productId}/stages/4?configId=${stage4ConfigId}&buildNow=true

Step 3.2: Verify more BuildJobs created
  GET /v2/builds/runs/${buildRunId}
  Assert: expectedBuilds == 8 (or matrix count from stage defs)

Step 3.3: Wait and verify all 8 builds
  Same polling logic as Scenario 1 but with higher expectedBuilds count
```

---

## Scenario 6: Manufacturing Stage

Manufacturing has a different flow — sessions with multi-DUT fixtures.

### Phase 2: Stage Config

```
Step 2.2: Enable Manufacturing Stage 1
  POST /v2/products/${productId}/stages
  Body: {
    type: "MANUFACTURING",
    stage: 1,
    boardRevisionId: "${revisionId}",
    enabled: true,
    assetSources: ["BUILD_SERVICE"]
  }
  Assert: type == "MANUFACTURING"
```

### Phase 3-4: Build + Asset Set (same flow)

### Phase 5: Manufacturing Session

```
Step 5.1: Create manufacturing session
  POST /v2/manufacturing/sessions
  Body: {
    productId: "${productId}",
    fixtureId: "${fixtureId}",
    assetSetId: "${assetSetId}"
  }
  Assert: HTTP 201
  Save: sessionId

Step 5.2: Each DUT goes through POST (power-on self test)
  The manufacturing-runner executes step-by-step:
    flash firmware → power cycle → lock shell → personalize → upload keys → verify

Step 5.3: Verify session results
  GET /v2/manufacturing/sessions/${sessionId}
  Assert: status == "COMPLETED"
  Assert: deviceCount > 0
  Assert: passedCount + failedCount == deviceCount
```

---

## Verification Checkpoints (Every Scenario)

After each phase, verify before proceeding:

| Phase | Check | How |
|-------|-------|-----|
| Product setup | Product exists with correct fields | GET /v2/products/${id} |
| Board setup | Board + revision + targets created | GET /v2/products/${id}?include=boards |
| Stage config | Config enabled with correct assetSources | GET /v2/products/${id}/stages |
| Build trigger | BuildRun created with correct metadata | GET /v2/builds/runs/${id} |
| Build complete | All BuildJobs succeeded or cached | GET /v2/builds/runs/${id}?include=builds |
| Asset set | AssetSet created with correct source | GET /v2/products/${id}/asset-sets |
| Assets | Individual files exist with checksums | GET /v2/products/${id}/asset-sets/${id} |
| Queue | Entry created with correct references | GET /v2/runs/queue/${id} |
| Validation | TestRun completed with counts | GET /v2/runs/${id} |
| Cleanup | Product deleted, no orphan data | GET /v2/products/${id} returns 404 |

---

## Frontend Verification (Playwright)

Each API scenario above should also have a Playwright counterpart that verifies the UI reflects the state:

| After | UI Check |
|-------|----------|
| Product created | Product appears in /products list |
| Board + revision | Board tab shows revision with targets |
| Stage enabled | Stage toggle is ON in stages panel |
| Build triggered | Build appears in /builds with PENDING/BUILDING status |
| Build complete | Status badge changes to SUCCESS (green) |
| Assets created | Asset set appears in revision assets panel |
| Queue entry | Entry visible in /validation/queue |
| Validation done | Results visible in /validation/runs/${id} |
| Product archived | Product shows ARCHIVED badge |

---

## Test Data Isolation

Each scenario creates its own product with a unique timestamp suffix. This ensures:

1. **No shared state** — scenarios can run in parallel
2. **No leftover data** — cleanup phase deletes everything
3. **Repeatable** — same scenario can run N times without conflicts
4. **Clean assertions** — no interference from seed data or other tests

Unique fields per scenario:
- `product.name`: `E2E-{scenario}-{timestamp}`
- `product.slug`: `e2e-{scenario}-{timestamp}`
- `board.ckBoardsFamily`: `e2e-{scenario}-{timestamp}`
- `revision.ckBoardsName`: `e2e_{scenario}_b0_{timestamp}`

---

## Prerequisites

| Requirement | Why | How to verify |
|---|---|---|
| Platform running | API endpoints available | `curl /v2/docs` returns 200 |
| Database migrated | Schema exists | Platform startup auto-migrates |
| MinIO accessible | Artifact storage works | `mc ls` succeeds |
| Auth enabled or disabled | Test can authenticate | Check AUTH_ENABLED config |
| Test user exists | API calls need auth | Seeded admin user or dev bypass |

If AUTH_ENABLED=true, tests must first obtain a JWT via `POST /v2/auth/login` and include it in all requests.

If AUTH_ENABLED=false, all endpoints are accessible without auth (dev bypass).

---

## Implementation Notes

- Build these as pytest tests (API layer) AND Playwright tests (UI layer)
- The pytest version is faster and tests the API contract directly
- The Playwright version tests what users actually see
- Both use the same scenario structure and assertions
- Run pytest version in integration tests (compose stack)
- Run Playwright version in E2E tests (full platform)
- Each scenario should take <5 minutes (builds are the bottleneck)
- If no fixtures are available, validation scenarios should PASS with a "skipped — no fixtures" note, not FAIL
