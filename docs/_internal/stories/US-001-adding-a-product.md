**Last reviewed:** 2026-03-30
**Status:** Active

# US-001: Adding a Product to Concord

## Story

> As an engineer, I want to add a new product to Concord by selecting a board from the ck_boards repository, so that the platform automatically derives build, manufacturing, and validation configuration from the Zephyr board definition.

## Context

Every Concord product originates from a Zephyr board definition in the `ck_boards` repository. When a new product is designed (e.g., "Sigma X"), an engineer creates a board definition (`board.yml`, DTS files, Kconfig) and pushes it to a branch in ck_boards. From there, any engineer can open Concord, walk through the product creation wizard, and the platform parses the board definition -- extracting SoC topology, peripherals, and hardware revisions -- to set up the build, manufacturing, and validation pipelines automatically.

There is no manual product creation path. Every product is derived from a board definition.

## User Flow

```
┌─────────────────────────────────────────────────────────────┐
│ 1. Engineer pushes board definition to ck_boards             │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│ 2. Open Concord → Products → "New Product"                   │
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
│    - Product name (auto-derived from board, editable)        │
│    - Per-target AppID (required, per CK firmware spec)        │
│    - Device Type + Device Variant (CoreCloud identifiers)     │
│    - NCS version, trigger branches for CI/CD                  │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│ 7. Create product                                            │
│    - Prisma records created: Product, Board, BoardRevision,  │
│      BoardRevisionChipset, ProductTarget                     │
│    - Build pipeline ready to trigger                         │
│    - Product visible across Concord UI                        │
└─────────────────────────────────────────────────────────────┘
```

## Technical Design

### 1. Data Model

The Product model is foundational -- build, manufacturing, and validation all derive from it. The schema aligns with the [CK Device Firmware Versioning Spec](https://corekinect.atlassian.net/wiki/spaces/EN/pages/2604630046/Device+Firmware+Versioning+SS+V1.0).

#### Key Concepts from CK Spec

| Concept | Definition | Concord Mapping |
|---------|-----------|-----------------|
| **AppID** | 2-byte int identifying chipset + software feature set | `ProductTarget.appId` |
| **Chipset** | Hardware config from purview of single MCU (same DTS = same chipset) | `Chipset` model |
| **Flags** | Release track (B/E/P) + manufacturing bit + debug bit | Per-build, not per-product |
| **Version** | Major.Minor.Build -- per firmware image | `FirmwareBuild` / `BuildJob` |
| **Device Type** | CoreCloud product type identifier | `Product.buildConfig.deviceType` |
| **Device Variant** | CoreCloud revision variant identifier | `Product.buildConfig.deviceVariant` |

#### Product

The root entity. Everything flows from here -- fixtures, tests, sessions, builds.

```prisma
model Product {
  id          String  @id @default(cuid())
  name        String  @unique   // "Alpha B0", "Sigma5 C0"
  slug        String? @unique   // "alpha_b0" -- URL-safe identifier
  description String?
  active      Boolean @default(true)
  buildConfig Json?             // Structured build configuration
  metadata    Json?             // Additional product-specific config

  targets        ProductTarget[]
  boards         Board[]
  firmwareBuilds FirmwareBuild[]
  fixtures       Fixture[]
  sessions       Session[]
  buildJobs      BuildJob[]
  pipelineRuns   PipelineRun[]
  // ...
}
```

Repo URLs are derived at runtime from the slug (e.g., `{slug}_fw`, `{slug}_mfg_fw`), not stored as columns.

#### ProductTarget

Every downstream system -- build, FUOTA, manufacturing, validation -- needs to know the AppID-to-SoC-to-role mapping. This is a first-class model, not buried in JSON.

```prisma
model ProductTarget {
  id        String @id @default(cuid())
  productId String
  role      String   // "comms", "app"
  soc       String   // "nRF9151", "nRF52840"
  appId     Int      // CoreCloud application ID (108, 109)

  product Product @relation(fields: [productId], references: [id], onDelete: Cascade)

  @@unique([productId, role])
  @@unique([productId, appId])
}
```

#### Board

Each product has exactly one board, linked to a `ck_boards` definition.

```prisma
model Board {
  id             String  @id @default(cuid())
  productId      String  @unique  // 1:1 with Product
  name           String           // "Main Board"
  ckBoardsName   String           // "alpha_b0" -- exact ck_boards directory name
  ckBoardsBranch String  @default("main")  // Branch it was discovered on
  vendor         String  @default("corekinect")

  product   Product         @relation(...)
  revisions BoardRevision[]

  @@unique([ckBoardsName])
}
```

#### BoardRevision

Hardware revisions (A0, B0, B1) with cached peripheral data from DTS parsing.

```prisma
model BoardRevision {
  id          String          @id @default(cuid())
  boardId     String
  version     String          // "A0", "B0"
  status      LifecycleStatus @default(ACTIVE)
  peripherals Json?           // Cached DTS results: [{compatible, type, bus}]

  board    Board                  @relation(...)
  chipsets BoardRevisionChipset[] // Many-to-many with Chipset

  @@unique([boardId, version])
}
```

#### buildConfig JSON

Stored on Product, contains build-time configuration. Targets are normalized into `ProductTarget` -- `buildConfig` stores only build settings:

```jsonc
{
  "board": "alpha_b0",
  "ncsVersion": "v2.9.0",
  "boardRoot": "ck_boards",
  "deviceType": 2,
  "deviceVariant": 3,
  "confFiles": { "app": ["prj.conf"], "comms": ["prj.conf"] },
  "overlays": { "app": [], "comms": [] },
  "postBuild": ["sign_mcuboot", "generate_dfu_package"],
  "triggerBranches": ["main"],
  "hasVsmMerge": false,
  "hasFips": false
}
```

### 2. Board Discovery Service

The HTTP API maintains a bare clone of `ck_boards` and exposes it through discovery endpoints.

#### Git Clone Lifecycle

```
App Startup:
  1. Clone bare repo: git clone --bare <ck_boards_url> /tmp/ck_boards.git
  2. Start background fetch timer (every 60 seconds)
  3. Initialize CkBoardsService singleton

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

Enforced server-side in `CkBoardsService.list_refs()` based on `AppConfig.ENVIRONMENT`.

#### Board Health Reporting

The service detects and reports issues per board without crashing the wizard:

```json
{
  "board": "sigma_x",
  "socs": ["nrf52840"],
  "revisions": ["A0"],
  "variants": ["sigma_x_a0"],
  "health": "ok"
}
```

Boards with parse errors are selectable but flagged:

```json
{
  "board": "broken_board",
  "socs": [],
  "revisions": [],
  "health": "error",
  "errors": ["board.yml missing 'socs' field", "DTS parse failed: syntax error"]
}
```

#### API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/v2/products/boards/branches` | List available ck_boards branches (env-gated) |
| GET | `/v2/products/boards/discover?branch=main` | List all boards on a branch with health |
| GET | `/v2/products/boards/discover/{board}?branch=main` | Full board detail: SoCs, peripherals, revisions |
| POST | `/v2/products` | Create product from discovery data |

#### Product Creation Payload

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
    "deviceType": 5,
    "deviceVariant": 1,
    "triggerBranches": ["main"]
  }
}
```

The backend creates all records in a single transaction: Product, Board, BoardRevision(s), BoardRevisionChipset(s), ProductTarget(s), and upserts Chipset records. The creation is audit-logged.

### 3. Frontend Wizard

A single "New Product" button opens the five-step wizard (`product-creation-wizard.svelte`). There is no manual creation form.

| Step | Title | What Happens |
|------|-------|-------------|
| 1 | Branch | Fetch branches from API, engineer picks one (defaults to `main`) |
| 2 | Board | Show boards on that branch with health indicators |
| 3 | Review | Display SoC topology, peripherals, and revisions from DTS parsing |
| 4 | Configure | Product name (auto-populated), AppIDs per target, device type/variant, NCS version, trigger branches |
| 5 | Create | Summary review, then POST to create the product |

The wizard auto-populates Step 4 fields from the board discovery data -- product name and slug from the board name, targets from the SoC list, with smart role assignment (nRF52840 = app, nRF9151 = comms).

#### Error Handling

- **Board health errors**: Inline warnings on Step 2 -- boards with parse errors are selectable but flagged
- **Branch not found**: Error state on Step 1 with retry
- **Service unavailable** (git clone not ready): Loading state with "Syncing board repository..."

## Firmware Versioning Alignment

Per the [CK Device Firmware Versioning Spec](https://corekinect.atlassian.net/wiki/spaces/EN/pages/2604630046/Device+Firmware+Versioning+SS+V1.0):

### AppID Rules

- AppID identifies a chipset + software feature set, not a product
- Manufacturing firmware shares the same AppID as the production image for the same target
- AppID is unique within a product: `@@unique([productId, appId])`
- If two products share a chipset + feature set, they can share an AppID (rare, but valid)

### Build Artifacts

Each build produces, per target:

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

## How Product Drives Downstream Systems

The Product definition is the single source of truth for every downstream system:

| System | What It Reads from Product |
|--------|---------------------------|
| **Build Service** | `buildConfig` (board, confFiles, overlays, postBuild), `ProductTarget` (AppIDs for CFW generation) |
| **Manufacturing** | `ProductTarget` (AppIDs for personalization), `buildConfig.deviceType/deviceVariant` (CoreCloud registration) |
| **Validation** | `ProductTarget` (AppIDs for FUOTA plans), `Board` (fixture design matching), `buildConfig` (stage configs) |
| **Git Poller** | `buildConfig.triggerBranches`, derived repo URLs from `Product.slug` |
| **Frontend** | Everything -- product detail, build pages, validation run context |

## Acceptance Criteria

- [ ] Single "New Product" button opens ck_boards wizard (no manual creation path)
- [ ] Board discovery works against live ck_boards repo (cloned on startup, fetched every 60s)
- [ ] Environment gating: staging/dev show all branches, production shows only main
- [ ] Boards with DTS parse errors are flagged but don't crash the wizard
- [ ] Product creation stores: Product, Board, BoardRevision, BoardRevisionChipset, ProductTarget
- [ ] ProductTarget model stores normalized AppID/SoC/role per target
- [ ] buildConfig JSON follows the documented structure (no targets duplication)
- [ ] All existing tests pass
- [ ] New unit tests for: schema validation, board discovery service, product creation endpoint, wizard component
- [ ] Integration tests for: end-to-end product creation flow (API to DB to query back)

## Test Plan

### Unit Tests

- **Schema**: ProductTarget uniqueness constraints, Board 1:1 with Product, cascade deletes
- **Board Discovery Service**: branch listing, board scanning, DTS parsing, peripheral classification, error handling for malformed boards
- **Product Creation Endpoint**: happy path, validation errors, duplicate product, missing AppIDs, invalid board reference
- **Frontend Wizard**: step navigation, auto-populate from board data, AppID validation, environment branch gating

### Integration Tests

- **End-to-end creation**: POST product with full payload, verify all DB records (Product, Board, BoardRevision, ProductTarget, Chipset), GET product back, verify response shape
- **Build pipeline**: create product, trigger build, verify build worker reads correct AppIDs and config
- **Board sync**: verify fetch timer updates branch list, new boards appear in discovery
