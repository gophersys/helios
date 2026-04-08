---
min_role: DEVELOPER
---
# Unified Platform Specification

## Executive Summary

Manufacturing, Validation, and Build systems must share a common language and infrastructure. This spec defines the work required to unify them, identifying serial dependencies and parallel workstreams.

---

## Phase 0: Serial Prerequisites (MUST COMPLETE FIRST)

These are blocking dependencies that must be resolved before parallel work can begin.

### 0.1 Product Model Enhancement

**Status**: PARTIALLY DONE (types.py updated)

The Product model is the root entity. All systems must reference it consistently.

```
Product
├── id, name, slug (unique identifiers)
├── deviceTypeId, deviceVariantId (CoreCloud identifiers)
├── appIds: { nrf52840: 109, nrf9151: 108 } (firmware app IDs)
├── repoSlug, repoSshUrl, repoBranch (main firmware repo)
├── mfgRepoSlug, mfgRepoSshUrl (manufacturing firmware repo)
├── buildBoard, buildWestDir, buildMfgDir (build configuration)
├── coreCloudEnv (which CoreCloud environment: VAL_1_0, PROD, etc.)
└── metadata (extensible JSON for product-specific config)
```

**Files to update**:
- [x] `prisma/schema.prisma` - Product model already has these fields
- [x] `apps/backend/http-api/src/api/v2/catalog/types.py` - DONE
- [x] `apps/backend/http-api/src/api/v2/catalog/products.py` - DONE
- [ ] `prisma/seed.py` - Ensure Alpha metadata is complete

### 0.2 Test Catalog Schema Standardization

**Status**: EXISTS (catalog.yaml for alpha)

The catalog.yaml format must be standardized and documented. Both manufacturing POST tests and validation tests use this format.

```yaml
# Standard catalog structure
version: "1.0.0"
product: alpha
board: alpha_b0

stages:
  post:           # Manufacturing POST (run on production floor)
  gate:           # PR validation gate (<15 min)
  regression:     # Comprehensive overnight
  integration:    # Instrumented firmware tests

tests:
  - id: "STAGE-PRODUCT-SEQ"
    name: "test_function_name"
    stage: "gate"
    timeout_s: 60
    hardware: [mtib, jlink]
    category: "power"
```

**Files to update**:
- [ ] Create `docs/validation/catalog-schema.md` - Document the standard
- [ ] `apps/validation/alpha/catalog.yaml` - Add POST stage if needed
- [ ] Consider: Should manufacturing have its own catalog or use validation's?

### 0.3 Fixture Profile Schema Standardization

**Status**: EXISTS (alpha_b0.json)

FixtureDesign.profileTemplate must have a standard schema all systems understand.

```json
{
  "product": "alpha",
  "board": "alpha_b0",
  "power": { "battery_installed": true, "dut_voltage": 4.5 },
  "gpio": { "button": { "pin": 2, "active_low": true } },
  "uart": { "app": "/dev/verdin-uart2", "comms": "/dev/verdin-uart1" },
  "jlink": { "app_snr": "821009546", "comms_snr": "821009537" }
}
```

**Files to update**:
- [ ] Create `docs/validation/fixture-profile-schema.md`
- [ ] Validate all existing fixture profiles conform

---

## Phase 1: Parallel Workstreams

After Phase 0 is complete, these can run in parallel.

### Team 1: Manufacturing System Updates

**Goal**: Manufacturing tests use the unified product/catalog infrastructure.

**Current State**:
- Manufacturing tests in `apps/manufacturing/alpha/`
- Uses Session/Test/TestExecution models
- Has its own fixture loading in conftest.py

**Work Required**:

1. **Update manufacturing conftest.py**
   - Load product config from API or DB (not hardcoded)
   - Use FixtureDesign profile template
   - Reference Product.metadata for deviceTypeId, appIds

2. **Update manufacturing test structure**
   - Consider adding POST stage to catalog.yaml
   - Or: Create separate `apps/manufacturing/alpha/catalog.yaml`
   - Tests should have IDs like `POST-ALPHA-001`

3. **Update manufacturing API endpoints**
   - `/v2/manufacturing/sessions` - Link to Product
   - `/v2/manufacturing/devices` - Use consistent device tracking

**Files**:
```
apps/manufacturing/alpha/conftest.py
apps/manufacturing/alpha/src/tests/*/step_*.py
apps/backend/http-api/src/api/v2/validation/tests/run.py
```

### Team 2: Validation System Updates

**Goal**: Validation is fully integrated with unified infrastructure.

**Current State**:
- Validation tests in `apps/validation/alpha/`
- Uses ValidationDesign/ValidationRun/ValidationStep models
- Catalog sync endpoint exists

**Work Required**:

1. **Test Catalog → ValidationDesign sync**
   - [x] Endpoint exists: `POST /v2/validation/catalog/<product>/sync`
   - [ ] Add to seed.py: Auto-sync Alpha catalog on seed
   - [ ] Frontend: Add "Sync Catalog" button

2. **Test Bench → Product linkage**
   - [x] TestBench.productId FK exists
   - [ ] Ensure all benches have correct productId
   - [ ] Validate fixture profile matches product

3. **Validation Run → Product context**
   - ValidationRun should carry full product context
   - Test runner should load product config from API

**Files**:
```
apps/validation/alpha/conftest.py
apps/validation/alpha/run.py
apps/backend/http-api/src/api/v2/validation/runs/trigger.py
apps/backend/http-api/src/api/v2/validation/catalog.py
libs/python/corekinect/test/runner.py
```

### Team 3: Build System Integration

**Goal**: Build system uses Product model for all configuration.

**Current State**:
- BuildJob has `product` (string) and `productId` (FK to Product)
- Build scripts in MinIO
- Webhook triggers builds

**Work Required**:

1. **Build configuration from Product**
   - Build worker should fetch Product.buildBoard, Product.buildWestDir
   - Eliminate hardcoded paths
   - Use Product.repoSshUrl for git clone

2. **Build artifacts → Product linkage**
   - BuildJobArtifact should reference Product and BoardRevision
   - Artifact storage path: `firmware-builds/{product.slug}/{board}/{version}/`

3. **Build triggers**
   - Webhook handler should resolve Product by repo slug
   - [x] `get_product_by_repo()` endpoint exists

**Files**:
```
apps/backend/http-api/src/api/v2/ci/webhook.py
apps/backend/http-api/src/api/v2/ci/builds.py
apps/backend/http-api/src/api/v2/ci/pipelines.py
deploy/helm/concord/templates/build-worker-*.yaml
```

### Team 4: Infrastructure/Hardware Registry

**Goal**: Single source of truth for test hardware.

**Current State**:
- Node (MTIB nodes in K8s)
- FixtureDesign (fixture hardware specs)
- TestBench (MTIB + DUT combo)
- Fixture/FixtureSlot (manufacturing fixtures)

**Work Required**:

1. **Unify bench discovery**
   - `discover_mtibs()` should populate both Node and TestBench
   - Link discovered MTIBs to Products based on label

2. **Fixture profile resolution**
   - `get_bench_profile()` should merge:
     - FixtureDesign.profileTemplate (base)
     - TestBench.profileOverrides (bench-specific)
     - DUT info (device ID, SNR, IMEI)

3. **Health monitoring**
   - All benches should report health status
   - Offline benches excluded from scheduling

**Files**:
```
apps/backend/http-api/src/api/v2/validation/benches/benches.py
apps/backend/http-api/src/api/v2/validation/designs/designs.py
apps/backend/http-api/src/api/v2/nodes/nodes.py
```

### Team 5: Frontend Unified Views

**Goal**: UI reflects unified product-centric model.

**Work Required**:

1. **Product detail page**
   - Show boards, revisions, firmware builds
   - Show available test benches for this product
   - Show validation designs (synced from catalog)
   - Link to CI pipelines

2. **Test bench management**
   - List benches by product
   - Show bench status, DUT info
   - "Sync Catalog" button

3. **Validation run trigger**
   - Select product → select design → select bench → trigger

**Files**:
```
apps/frontend/concord-app-svelte/src/routes/catalog/[productId]/+page.svelte
apps/frontend/concord-app-svelte/src/routes/validation/benches/+page.svelte
apps/frontend/concord-app-svelte/src/routes/validation/designs/+page.svelte
```

---

## Phase 2: Integration Testing

After parallel work completes, verify end-to-end flows:

1. **Manufacturing flow**
   - Create product → create bench → run POST tests → device registered

2. **Validation flow**
   - Trigger CI pipeline → builds complete → validation run triggered → tests execute

3. **Build flow**
   - Webhook received → product resolved → builds queued → artifacts uploaded

---

## Dependency Graph

```
Phase 0 (Serial)
├── 0.1 Product Model ────────┐
├── 0.2 Catalog Schema ───────┼──→ Phase 1 (Parallel)
└── 0.3 Fixture Schema ───────┘      ├── Team 1: Manufacturing
                                      ├── Team 2: Validation
                                      ├── Team 3: Build System
                                      ├── Team 4: Infrastructure
                                      └── Team 5: Frontend
                                              │
                                              ▼
                                      Phase 2 (Integration)
```

---

## Success Criteria

1. **Product is the root entity** - All systems reference Product by ID
2. **Single catalog format** - Same YAML schema for mfg + validation
3. **Unified fixture profiles** - One schema, loaded from API
4. **Build → Test flow** - Pipeline triggers validation automatically
5. **Frontend shows unified view** - Product page shows all related entities

---

## Quick Start Commands

```bash
# Seed database with Alpha product
cd /workspaces/concord
SEED_ADMIN_EMAIL=admin@local npx nx run database:seed

# Sync Alpha catalog to ValidationDesign records
curl -X POST http://localhost:9001/v2/validation/catalog/alpha/sync \
  -H "Authorization: ApiKey ck_ci_admin_x8K2mP9vL4nQ7wR1tY6uI3oA5sD0fG"

# Verify sync status
curl http://localhost:9001/v2/validation/catalog/alpha/sync \
  -H "Authorization: ApiKey ck_ci_admin_x8K2mP9vL4nQ7wR1tY6uI3oA5sD0fG"
```
