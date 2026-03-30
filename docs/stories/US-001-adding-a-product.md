**Last reviewed:** 2026-03-30
**Status:** Draft

# US-001: Adding a Product to Concord

## Story

> As a **hardware engineer or product owner**, I want to **add a new product to Concord by selecting a board from the ck_boards repository**, so that **the platform can automatically derive the build, manufacturing, and validation configuration from the Zephyr board definition**.

## Context

When CK designs a new product (e.g., "Sigma X"), the hardware team creates a board definition in the `ck_boards` repository under a feature branch. The board definition follows the Zephyr board format (`board.yml`, DTS files, Kconfig). Once the board is pushed to origin, a Concord user should be able to create a product from it — the platform parses the board definition, extracts hardware topology (SoCs, peripherals, revisions), and sets up the build, manufacturing, and validation pipelines automatically.

**Concord only supports Zephyr boards from ck_boards.** There is no manual product creation path. Every product is derived from a board definition.

## Personas

| Persona | Role | Actions |
|---------|------|---------|
| **Hardware Engineer** | Creates board definition in ck_boards | Pushes board.yml + DTS to feature branch |
| **Product Owner** | Adds product to Concord | Selects branch → board → confirms config → creates product |
| **Build Engineer** | Configures build pipeline | Sets AppIDs, release tracks, trigger branches |
| **Validation Engineer** | Runs tests against product builds | Uses product config to select fixtures and test suites |

## User Flow

```
┌─────────────────────────────────────────────────────────────┐
│ 1. HW Engineer pushes board to ck_boards (feature branch)   │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│ 2. User opens Concord → Products → "New Product"            │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│ 3. Select ck_boards branch                                   │
│    - Staging/Dev: all branches visible                       │
│    - Production: only 'main' branch                          │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│ 4. Select board from branch                                  │
│    - Platform scans ck_boards for board.yml files             │
│    - Shows board name, SoCs, revisions, variants             │
│    - Flags boards with DTS parse errors or format issues     │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│ 5. Review board details                                      │
│    - SoC topology (single/dual processor)                    │
│    - Peripherals extracted from DTS (accelerometer, charger) │
│    - Hardware revisions from board.yml                        │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│ 6. Configure product identity                                │
│    - Product name (human-readable, auto-derived from board)  │
│    - Per-target AppID (required, per CK firmware spec)        │
│    - Device Type + Device Variant (CoreCloud identifiers)     │
│    - Release track defaults (Bench for dev, Production)       │
│    - Trigger branches for CI/CD                               │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│ 7. Create product                                            │
│    - Prisma record created with full config                  │
│    - Board + chipsets + revisions + peripherals stored        │
│    - Build pipeline ready to trigger                         │
│    - Product visible in Concord UI                            │
└─────────────────────────────────────────────────────────────┘
```

## Technical Design

### 1. Prisma Schema

The Product model is **foundational** — build, manufacturing, and validation all derive from it. The schema must align with the [CK Device Firmware Versioning Spec](https://corekinect.atlassian.net/wiki/spaces/EN/pages/2604630046/Device+Firmware+Versioning+SS+V1.0).

#### Key Concepts from CK Spec

| Concept | Definition | Concord Mapping |
|---------|-----------|-----------------|
| **AppID** | 2-byte int identifying chipset + software feature set | `ProductTarget.appId` |
| **Chipset** | Hardware config from purview of single MCU (same DTS = same chipset) | `Chipset` model |
| **Flags** | Release track (B/E/P) + manufacturing bit + debug bit | Per-build, not per-product |
| **Version** | Major.Minor.Build — per firmware image | `FirmwareBuild` / `BuildJob` |
| **Device Type** | CoreCloud product type identifier | `Product.deviceType` |
| **Device Variant** | CoreCloud revision variant identifier | `Product.deviceVariant` |

#### Schema Changes: Product (clean up)

**Remove** all legacy fields that duplicate `buildConfig` or can be derived from conventions:

```diff
model Product {
  id          String  @id @default(cuid())
  name        String  @unique
  slug        String? @unique
  description String?
  active      Boolean @default(true)

- repoSlug      String?
- repoSshUrl    String?
- repoBranch    String?
- mfgRepoSlug   String?
- mfgRepoSshUrl String?
- buildBoard    String?
- buildWestDir  String?
- buildMfgDir   String?

  buildConfig   Json?
  metadata      Json?

  createdAt DateTime @default(now())
  updatedAt DateTime @updatedAt

  // Relations (unchanged)
  boards           Board[]
+ targets          ProductTarget[]
  firmwareBuilds   FirmwareBuild[]
  fixtures         Fixture[]
  sessions         Session[]
  buildJobs        BuildJob[]
  pipelineRuns     PipelineRun[]
  // ...
}
```

**Derivation rules** (computed at runtime, not stored):
- Firmware repo SSH URL: `git@bitbucket.org:corekinect/{slug}_fw.git`
- Mfg firmware repo SSH URL: `git@bitbucket.org:corekinect/{slug}_mfg_fw.git`
- West board name: from `buildConfig.board` or `Board.ckBoardsName`
- Build directories: convention-based from product slug

#### Schema Changes: ProductTarget (new model)

Normalizes the `buildConfig.targets` JSON into a queryable, referenceable model. Every downstream system (build, FUOTA, manufacturing, validation) needs to know the AppID → SoC → role mapping.

```prisma
model ProductTarget {
  id        String @id @default(cuid())
  productId String
  role      String   // "app", "comms", "modem"
  soc       String   // "nrf52840", "nrf9151" — references Chipset.name
  appId     Int      // CK AppID (2-byte, per firmware versioning spec)

  product Product @relation(fields: [productId], references: [id], onDelete: Cascade)

  @@unique([productId, role])
  @@unique([productId, appId])
  @@index([appId])
}
```

**Why normalize?**
- AppIDs are referenced by: build artifacts, CFW generation, FUOTA plans, CoreCloud device registration, manufacturing shell personalization
- Storing them in a JSON blob means every consumer must parse JSON and hope the shape hasn't changed
- A proper model enables: `db.producttarget.find_many(where={"appId": 109})` — "which product uses this AppID?"

#### Schema Changes: Board (align with ck_boards)

```prisma
model Board {
  id             String  @id @default(cuid())
  productId      String  @unique  // 1:1 for now (can relax later)
  ckBoardsName   String  // "alpha_b0" — exact directory name in ck_boards
  ckBoardsBranch String  // "main", "feature/sigma-x" — branch it was discovered on
  vendor         String  @default("corekinect")

  product   Product         @relation(fields: [productId], references: [id], onDelete: Cascade)
  revisions BoardRevision[]

  @@unique([ckBoardsName])
}
```

**Changes from current:**
- `productId` becomes `@unique` (1:1 with Product)
- `name` replaced with `ckBoardsName` (exact ck_boards directory name)
- Added `ckBoardsBranch` to track provenance
- Added `vendor` (from board.yml, always "corekinect" for now)
- Removed old `name` field that was ambiguous ("Main Board" vs "alpha_b0")

#### Schema Changes: BoardRevision (hardware revisions)

```prisma
model BoardRevision {
  id             String          @id @default(cuid())
  boardId        String
  version        String          // "A0", "B0", "B1" — PCB hardware revision
  status         LifecycleStatus @default(ACTIVE)
  peripherals    Json?           // Cached DTS peripheral manifest
  notes          String?
  createdAt      DateTime @default(now())
  updatedAt      DateTime @updatedAt

  board    Board                  @relation(fields: [boardId], references: [id], onDelete: Cascade)
  chipsets BoardRevisionChipset[]

  @@unique([boardId, version])
}
```

**Changes:**
- `selectedBuilds` removed (legacy, unused)
- Added `peripherals` JSON (cached DTS parse results — `[{compatible, type, bus}]`)
- `version` stores hardware revision ("A0", "B0"), NOT firmware version

#### Schema Changes: Product.buildConfig (restructured JSON)

`buildConfig` remains JSON but with a cleaner, well-defined structure. Targets are normalized into `ProductTarget` — `buildConfig` stores only build-time configuration:

```jsonc
{
  // Board identity (from ck_boards)
  "board": "alpha_b0",
  "ncsVersion": "v2.9.0",
  "boardRoot": "ck_boards",

  // Device identity (CoreCloud)
  "deviceType": 2,
  "deviceVariant": 3,

  // Build configuration (per-target)
  "confFiles": {
    "app": ["prj.conf"],
    "comms": ["prj.conf"]
  },
  "overlays": {
    "app": [],
    "comms": []
  },

  // Post-build pipeline
  "postBuild": ["sign_mcuboot", "generate_dfu_package"],

  // Trigger configuration
  "triggerBranches": ["main"],

  // Build features
  "hasVsmMerge": false,
  "hasFips": false
}
```

**Removed from buildConfig** (now in proper models):
- `targets` → `ProductTarget` model
- `cfw.deviceType` / `cfw.deviceVariant` → `buildConfig` top-level (simpler)

### 2. HTTP API: Board Discovery

#### Git Clone Lifecycle

The HTTP API maintains a **bare clone** of ck_boards in `/tmp/ck_boards.git`:

```
App Startup:
  1. Clone bare repo if not present: git clone --bare git@bitbucket.org:corekinect/ck_boards.git /tmp/ck_boards.git
  2. Start background fetch timer (every 60 seconds)
  3. Initialize CkBoardsService with bare repo path

Per-Request:
  1. git worktree add --detach /tmp/ck_boards-wt/<uuid> <branch>
  2. Parse board.yml + DTS files
  3. git worktree remove /tmp/ck_boards-wt/<uuid>

Periodic Fetch (every 60s):
  1. git fetch --all --prune
  2. Log new/removed branches
```

#### Environment Gating

| Environment | Allowed Branches | Rationale |
|-------------|-----------------|-----------|
| Development | All | Fast iteration on feature branches |
| Staging | All | Pre-prod validation of new boards |
| Production | `main` only | Only validated boards go to production |

Enforced server-side in `CkBoardsService.list_refs()` — filters branches based on `AppConfig.ENVIRONMENT`.

#### Board Validation

When scanning boards, the service must detect and report:
- Missing `board.yml` (skip board, log warning)
- Invalid `board.yml` format (report error in response, don't crash)
- DTS parse failures (report error per-revision, include partial results)
- Boards that don't follow naming conventions (flag in response)

Response shape includes a `health` field per board:

```json
{
  "board": "sigma_x",
  "socs": ["nrf52840"],
  "revisions": ["A0"],
  "variants": ["sigma_x_a0"],
  "health": "ok"
}
```

```json
{
  "board": "broken_board",
  "socs": [],
  "revisions": [],
  "variants": [],
  "health": "error",
  "errors": ["board.yml missing 'socs' field", "DTS parse failed: syntax error in line 42"]
}
```

#### API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/v2/products/boards/branches` | List available ck_boards branches (env-gated) |
| GET | `/v2/products/boards/discover?branch=main` | List all boards on a branch |
| GET | `/v2/products/boards/discover/{board}?branch=main` | Full board detail with peripherals |
| POST | `/v2/products` | Create product from board discovery data |

#### Product Creation Endpoint

`POST /v2/products` accepts:

```json
{
  "name": "Sigma X",
  "slug": "sigma_x_a0",
  "description": "Next-gen wearable platform",
  "board": {
    "ckBoardsName": "sigma_x_a0",
    "ckBoardsBranch": "feature/sigma-x",
    "revisions": [
      {
        "version": "A0",
        "chipsets": ["nrf52840", "nrf9151"],
        "peripherals": [
          {"compatible": "bosch,bmi270", "type": "accelerometer", "bus": "spi"}
        ]
      }
    ]
  },
  "targets": [
    {"role": "app", "soc": "nrf52840", "appId": 201},
    {"role": "comms", "soc": "nrf9151", "appId": 200}
  ],
  "buildConfig": {
    "board": "sigma_x_a0",
    "ncsVersion": "v2.9.0",
    "boardRoot": "ck_boards",
    "deviceType": 5,
    "deviceVariant": 1,
    "confFiles": {"app": ["prj.conf"], "comms": ["prj.conf"]},
    "overlays": {"app": [], "comms": []},
    "postBuild": ["sign_mcuboot"],
    "triggerBranches": ["main"],
    "hasVsmMerge": false,
    "hasFips": false
  }
}
```

The backend:
1. Creates `Product` record
2. Creates `Board` record with `ckBoardsName` and `ckBoardsBranch`
3. Creates `BoardRevision` records with chipset relations and cached peripherals
4. Creates `ProductTarget` records for each target (app, comms)
5. Ensures `Chipset` records exist (upsert by name)
6. Audit logs the creation

### 3. Frontend

#### Single Creation Flow

Remove the dual-button UI ("New Product" / "New from ck_boards"). Replace with a single **"New Product"** button that always goes through the ck_boards wizard flow. There is no manual product creation path.

#### Wizard Steps (revised)

| Step | Title | Data |
|------|-------|------|
| 1 | Select Branch | Fetch branches from API, user picks one |
| 2 | Select Board | Show boards on branch with health indicators |
| 3 | Review Hardware | SoCs, peripherals, revisions from DTS parsing |
| 4 | Configure Identity | Product name, AppIDs per target, device type/variant, trigger branches |
| 5 | Confirm & Create | Summary → POST /v2/products |

#### Error Handling

- **Board health errors**: Show inline warnings on Step 2 — boards with parse errors are selectable but flagged
- **Branch not found**: Show error state on Step 1 with retry
- **Service unavailable** (git clone not ready): Show loading state with "Syncing board repository..."

### 4. ck_boards Service Initialization

Currently broken — `init_ck_boards_service()` is never called. Fix:

```python
# In main.py, after register_v2_routes()
from services.ck_boards.service import CkBoardsService

ck_boards_svc = CkBoardsService(
    bare_repo_url="git@bitbucket.org:corekinect/ck_boards.git",
    bare_repo_path="/tmp/ck_boards.git",
    worktree_base="/tmp/ck_boards-wt",
    environment=app_config.ENVIRONMENT,  # gates branches
    fetch_interval_seconds=60,
)
ck_boards_svc.start()  # clones + starts background fetch timer
```

Add to `AppConfig`:
```python
CK_BOARDS_REPO_URL: str = "git@bitbucket.org:corekinect/ck_boards.git"
CK_BOARDS_FETCH_INTERVAL: int = 60  # seconds
```

## Firmware Versioning Alignment

Per the [CK Device Firmware Versioning Spec](https://corekinect.atlassian.net/wiki/spaces/EN/pages/2604630046/Device+Firmware+Versioning+SS+V1.0):

### AppID Rules (enforced by Concord)
- AppID is per **chipset + software feature set**, not per product
- Manufacturing firmware **shares the same AppID** as the production image
- AppID is unique within the `ProductTarget` table: `@@unique([productId, appId])`
- If two products share a chipset + feature set, they share an AppID (rare, but valid)

### Build Artifact Requirements
Each build must produce, per target:

| Artifact | Format | Use Case |
|----------|--------|----------|
| Plaintext hex | `.hex` (bootloader + app) | J-Link flashing (validation, manufacturing) |
| Encrypted hex | `.hex` (bootloader + encrypted app) | Prerequisite for CFW |
| Encrypted CFW | `.cfw` (app only, no bootloader) | FUOTA / OTA updates |

### Version String Format
`{AppId}.{Major}.{Minor}.{Build}-{Flags}`

Example: `109.0.5.2-BM` = AppID 109, version 0.5.2, Bench Manufacturing build

### Flags
| Flag | Bit | Values |
|------|-----|--------|
| Release Track | [2:1] | B=Bench, E=Engineering, P=Production |
| Manufacturing | [0] | M=Yes, omit=No |
| Debug | [3] | D=Yes, omit=No |

## Downstream Impact

The Product definition drives everything downstream. Getting it right here means:

| System | What It Reads from Product |
|--------|---------------------------|
| **Build Service** | `buildConfig` (board, confFiles, overlays, postBuild), `ProductTarget` (AppIDs for CFW generation) |
| **Manufacturing** | `ProductTarget` (AppIDs for personalization), `buildConfig.deviceType/deviceVariant` (CoreCloud registration) |
| **Validation** | `ProductTarget` (AppIDs for FUOTA plans), `Board` (fixture design matching), `buildConfig` (stage configs) |
| **Git Poller** | `buildConfig.triggerBranches`, derived repo URLs from `Product.slug` |
| **Frontend** | Everything — product detail, build pages, validation run context |

## Acceptance Criteria

- [ ] Single "New Product" button (no manual creation path)
- [ ] Board discovery works against live ck_boards repo (cloned on startup, fetched every 60s)
- [ ] Environment gating: staging/dev show all branches, production shows only main
- [ ] Boards with DTS parse errors are flagged but don't crash the wizard
- [ ] Product creation stores: Product, Board, BoardRevision, BoardRevisionChipset, ProductTarget
- [ ] Legacy Product fields removed (repoSlug, repoSshUrl, repoBranch, buildBoard, buildWestDir, buildMfgDir, mfgRepoSlug, mfgRepoSshUrl)
- [ ] ProductTarget model stores normalized AppID/SoC/role per target
- [ ] buildConfig JSON follows the restructured format (no targets duplication)
- [ ] Existing products migrated to new schema (Alpha B0 data preserved)
- [ ] All existing tests pass after migration
- [ ] New unit tests for: schema validation, board discovery service, product creation endpoint, wizard component
- [ ] Integration tests for: end-to-end product creation flow (API → DB → query back)

## Test Plan

### Unit Tests
- **Schema**: ProductTarget uniqueness constraints, Board 1:1 with Product, cascade deletes
- **Board Discovery Service**: branch listing, board scanning, DTS parsing, peripheral classification, error handling for malformed boards
- **Product Creation Endpoint**: happy path, validation errors, duplicate product, missing AppIDs, invalid board reference
- **Frontend Wizard**: step navigation, auto-populate from board data, AppID validation, environment branch gating

### Integration Tests
- **End-to-end creation**: POST product → verify DB records (Product, Board, BoardRevision, ProductTarget, Chipset) → GET product back → verify response shape
- **Build pipeline**: create product → trigger build → verify build worker reads correct AppIDs and config
- **Board sync**: verify fetch timer updates branch list, new boards appear in discovery

## Implementation Phases

### Phase 1: Schema Foundation
1. Add `ProductTarget` model to schema.prisma
2. Remove legacy fields from Product
3. Update Board model (ckBoardsName, ckBoardsBranch, vendor, unique productId)
4. Update BoardRevision (add peripherals JSON, remove selectedBuilds)
5. Write migration + seed script for existing Alpha B0 data
6. Run full test suite, fix broken references

### Phase 2: Board Discovery Service
1. Wire up `init_ck_boards_service()` in app startup
2. Add AppConfig fields (CK_BOARDS_REPO_URL, CK_BOARDS_FETCH_INTERVAL)
3. Add environment gating to branch listing
4. Add board health validation + error reporting
5. Add to all environment configs (dev, staging, production)
6. Integration tests with real git operations

### Phase 3: API + Frontend
1. Update product creation endpoint to accept new payload shape
2. Create ProductTarget records during product creation
3. Merge wizard into single "New Product" flow
4. Remove manual product creation form and "New from ck_boards" button
5. Update product detail view to show targets and board info
6. Update TypeScript types to match new API response

### Phase 4: Migration + Verification
1. Migrate existing Alpha B0 product to new schema
2. Verify build pipeline still works with new schema
3. Verify FUOTA can read AppIDs from ProductTarget
4. Deploy to staging, run full validation suite
5. Archive legacy code paths

## Open Questions

1. **AppID registry**: Is there a master list of assigned AppIDs? Or are they ad-hoc? Should Concord enforce global uniqueness across products?
2. **Device Type/Variant registry**: Same question — is there a canonical list, or assigned per-product?
3. **Board revision source of truth**: Should Concord track hardware revisions from ck_boards `board.yml` `revision.revisions` field, or are they manually entered? The team may not keep `board.yml` revisions up to date.
4. **Multi-board products**: The schema supports 1:1 Product→Board. If a future product has multiple PCBs (e.g., main board + sensor board), should this be multiple Products or should we relax to 1:many?
5. **Firmware repo naming convention**: Is `{slug}_fw` / `{slug}_mfg_fw` always the pattern? Any exceptions?

---

## Template Notes

This document follows the Concord user story template. When creating new user stories, copy this structure:

1. **Story**: One-sentence user story (As a..., I want..., so that...)
2. **Context**: Background and motivation
3. **Personas**: Who is involved and their actions
4. **User Flow**: Visual step-by-step flow
5. **Technical Design**: Schema, API, Frontend, Services
6. **Spec Alignment**: Reference to relevant CK specs
7. **Downstream Impact**: What other systems are affected
8. **Acceptance Criteria**: Checkboxes for "done"
9. **Test Plan**: Unit, integration, E2E tests
10. **Implementation Phases**: Ordered work breakdown
11. **Open Questions**: Unresolved design decisions
