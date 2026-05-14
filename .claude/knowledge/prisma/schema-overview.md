# `prisma/schema.prisma` — schema overview

The data model for the Concord platform. PostgreSQL via Prisma. The schema
file is the single source of truth: the generated Python client lands in
`libs/python/database/`, and the frontend mirrors enum + response shapes
by hand in `apps/frontend/app/src/lib/types/models.ts`.

Refresh this file when: a model is added/removed/renamed; relations between
clusters change; a model moves between clusters; a major status field is
collapsed or split (see the `collapse_status_lockstate` migration as a
pattern).

## Location

```
prisma/
├── schema.prisma                 # the schema — single file, ~1800 lines
├── migrations/                   # generated, hand-curated SQL
│   ├── migration_lock.toml       # provider = "postgresql"
│   └── <ts>_<name>/migration.sql
├── seed/                         # python seed script (dev only)
├── project.json                  # nx targets: generate-client, migrate, …
├── .env / .env.example           # DATABASE_URL for local prisma CLI
```

The `generator python` block in `schema.prisma` outputs to
`../libs/python/database` (synchronous client, recursive depth 5,
`debian-openssl-3.0.x` binary target).

## Reading guide

- **Comments matter.** Many models carry `///` Prisma doc comments
  explaining lifecycle invariants — read them before refactoring.
- **`@@map("snake_case")` everywhere.** Prisma model names are PascalCase;
  the actual table names are snake_case. Use the Prisma name in code,
  the table name in raw SQL.
- **Cascade rules are intentional.** `onDelete: Cascade` on a parent
  wipes children; `Restrict` blocks deletion if children exist;
  `SetNull` keeps the row but nulls the FK. Don't change these without
  walking the dependent UI code.
- **Derived state is not persisted.** Two big examples: `Node.status`
  (computed from k8s + gRPC probe) and `Fixture.lockState` (FREE / IN_USE
  / MAINTENANCE — computed from `disabled` + active sessions). The DB
  stores only `disabled` as the admin override.

## Model graph at a glance

```
Product ─┬─ Board ── BoardRevision ─┬─ ProductTarget ── FirmwareBuild
         │                          ├─ FirmwareSet
         │                          ├─ ModemFirmware
         │                          ├─ ProductStageConfig ─ StageBuildMatrix
         │                          ├─ ManufacturingConfig
         │                          ├─ TestPackage ── TestPackageStage
         │                          │           └─ TestBedDesign ── Fixture ─ FixtureSlot ─ Node
         │                          └─ AssetSet ─ Asset
         │
         ├─ BuildRun ── BuildJob ── BuildArtifact
         │     └─ AssetSet ─ ValidationQueueEntry ─ TestRun
         │                                            └─ RunTarget ── TestExecution ── TestStep
         ├─ ManufacturingSession ── TestRun (same lineage)
         ├─ RecipeVersion ─ RecipeTemplate
         ├─ ProductAccess ──── User
         └─ Secret (via ProductStageConfig.signingKey)

User ─ PermissionSet
     ├─ ApiKey
     ├─ AuthSession ── RefreshToken
     ├─ NotificationPreference
     ├─ Notification ── Release
     ├─ AuditLog
     └─ ErrorReport (resolvedBy + resolvedInRelease)

IcleDevice ─ IclePendingCommand
           └─ IcleLog

PollCache  (standalone — Bitbucket commit-SHA cache)
```

## Domain clusters

### 1. Products & catalog

The catalog every other cluster anchors to.

| Model | Carries | Notable relations |
|---|---|---|
| `Product` | One canonical hardware product. Status `ACTIVE`/`ARCHIVED`. Holds Bitbucket repo slugs (`fwRepoSlug`, `mfgFwRepoSlug`), builder image, build config JSON. | Has many of nearly everything (Board, BuildRun, TestRun, …). `onDelete: Cascade` for Board/TestPackage/FirmwareSet; `Restrict` for the business-logic models (TestRun, BuildJob, AssetSet) so they cannot orphan-cascade. |
| `Board` | A distinct PCB design within a product (1:1 with Product today). Carries `ckBoardsFamily` — the prefix used in firmware repos (`alpha`, `sigma5`). | Owns BoardRevisions. |
| `BoardRevision` | A revision (A0/B0/C1). Carries `ckBoardsName` (`alpha_b0`), parsed `socs` list, CoreCloud `deviceType`/`deviceVariant`, modem version, `snrLength` (manufacturing-scan input enforcement), and `LifecycleStatus`. | Targets, FirmwareSet, AssetSet, TestBedDesign, Fixture, ManufacturingConfig, TestPackage, ModemFirmware, ProductStageConfig, TestRun — everything that needs to be revision-specific points here. |
| `ProductTarget` | A firmware target (`role=comms|app`, SoC, CoreCloud `appId`) inside a revision. | Owns FirmwareBuilds. |

A `Product` always has exactly one `Board` (`@unique` on `Board.productId`).
A `Board` can have many `BoardRevision`s.

### 2. Firmware artifacts & builds

Two parallel artifact stores: the **CI flow** (Build* → AssetSet → Asset)
is the primary new path; the **legacy direct upload** (FirmwareSet →
FirmwareBuild) is kept for uploaded-from-disk binaries.

| Model | Carries |
|---|---|
| `BuildRun` | A batch of `BuildJob`s triggered by one event (commit, webhook, manual). Tracks aggregate status (`BuildRunStatus`), PR metadata, validation linkage (`validationRunId`, `autoRunStage`), build-matrix mode (`legacy` / `stage4`). |
| `BuildJob` | One firmware compilation. Owned by `build-service`. Carries `BuildJobStatus`, `buildFingerprint` (for `CACHED` reuse via `reusedFromId`), priority, worker info, version-bump linkage (`baseJobId`). |
| `BuildArtifact` | A single file produced by a BuildJob, stored in MinIO. |
| `FirmwareSet` | A complete firmware release for a board revision. `FirmwareVariant` × `ReleaseTrack` × manufacturing/debug booleans. May reference a `BuildJob` or be an external upload. |
| `FirmwareBuild` | Per-target binary inside a FirmwareSet (one per `appId`). Tracks plaintext hex, encrypted hex, CFW, manifest keys. |
| `ModemFirmware` | Nordic modem firmware version uploaded per BoardRevision. AssetSets reference one. |
| `AssetSet` | The unified post-build container. `AssetSetSource = BUILD_SERVICE | MANUAL_UPLOAD | EXTERNAL_CI`. 1:1 with a `BuildRun` when produced by CI. Carries `stage`, `stageType`, `version`, `variant`. Validation + manufacturing both link here. |
| `Asset` | Individual artifact within an AssetSet. Carries `label` (build-matrix label), `role`, `processor`, `artifactType`, MinIO `storageKey`. |

```
BuildRun (1) ─ (N) BuildJob ─ (N) BuildArtifact
   └─ (0..1) AssetSet ─ (N) Asset
                  └─ (N) ValidationQueueEntry / TestRun / ManufacturingSession
```

### 3. Stage configuration & build matrix

How CI knows *what* to build for *which* stage.

| Model | Carries |
|---|---|
| `ProductStageConfig` | A per-(product, type, stage, boardRevision) row. `StageType = VALIDATION | MANUFACTURING`, stage number 1–5, watched branch, trigger types, asset sources, optional `signingKey` (FK to `Secret`), optional pinned `recipeVersion`, optional `releasedTestPackageId` (blessed package for auto-runs). |
| `StageBuildMatrix` | Per-stage build defs. One row per build label (`mfg_base`, `fut_verbose_a`, …). Carries fwType, variant, configLog, producesHex/Cfw, gitRef, isVersionBump + baseLabel, processor, filename pattern. Replaces the hardcoded `_STAGE_BUILDS` in `corekinect.stages`. |
| `ValidationQueueEntry` | A queued validation run waiting for a fixture. Priority queue (`@@index([status, priority])`). Carries `assetSet`, optional `stageConfig`, `fixture` assignment, eventual `testRun` link. |
| `RecipeVersion` | Versioned build-script snapshot per product. `RecipeStatus = draft | published`. Pinned by BuildRun/BuildJob/StageConfig/AssetSet. |
| `RecipeTemplate` | Reusable boilerplate for bootstrapping a new product's recipe. |

### 4. Test packages

A `TestPackage` is the validation/manufacturing test code uploaded for a
product — the runner pod downloads it from MinIO at startup.

| Model | Carries |
|---|---|
| `TestPackage` | `TestPackageType = VALIDATION | MANUFACTURING`, `TestPackageStatus = UPLOADING → DEVELOPMENT | RELEASED`. Version string (`1.2.0` or `dev-<sha>-<ts>`), MinIO `storageKey`, `frameworkVersion`, `manifestVersion`, optional `releasedVersion` + `releasedById` + `releasedAt`. |
| `TestPackageStage` | Structured per-stage metadata extracted from the manifest. Replaces the prior `stagesEnabled` JSON blob. Carries `directory`, `module`, `markers`, `hardware`, `timeoutS`. |

Two-phase commit: a row is created with `status=UPLOADING` and `storageKey=NULL`,
then flipped to `DEVELOPMENT`/`RELEASED` once the MinIO PUT completes. Stale
`UPLOADING` rows are reaped by retention.

### 5. Fixtures, slots & nodes

The runtime side — physical rigs and their MTIBs.

| Model | Carries |
|---|---|
| `TestBedDesign` | Versioned design owned 1:1 by a TestPackage. `profileTemplate` JSON is the source of truth for what hardware the design exposes. `type` mirrors the parent package type. |
| `Fixture` | A physical fixture instance. `NodeType` (MANUFACTURING / VALIDATION), `FixturePurpose` (DEV / RELEASE), `panelRows × panelCols`, `disabled` (admin override). **`lockState` is derived live** at serialize time — never stored. |
| `FixtureSlot` | A position on a fixture. `@unique` on `nodeId` (a node can be in at most one slot). Carries J-Link serials, UART paths, current DUT identity. |
| `Node` | A K8s node. `NodeType`, `hostname` (unique), `hardwareRevision`. Reachability **never persisted**; computed from k8s + gRPC probe. Only `disabled` is stored. |

```
TestBedDesign (1) ── (N) Fixture (1) ── (N) FixtureSlot (1) ── (0..1) Node
       ▲
       │ 1:1
       │
TestPackage (uploading product's fixture profile)
```

### 6. Manufacturing & test runs

The shared `TestRun → RunTarget → TestExecution → TestStep` hierarchy is
used by both validation and manufacturing; only the parent differs.

| Model | Carries |
|---|---|
| `ManufacturingConfig` | Per-(product, boardRevision) config: which stages enabled, firmware source, personalization, pass criteria. |
| `ManufacturingSession` | An operator-managed batch on a fixture. `ManufacturingSessionStatus = ACTIVE | COMPLETED | CANCELLED | ARCHIVED`. Wraps the K8s runner deployment lifecycle (`runnerStatus`, `runnerDeploymentName`, `runnerLastHeartbeat`). Owns N `TestRun`s (one per panel scan). |
| `TestRun` | Atomic test execution. `TestRunType = VALIDATION | MANUFACTURING`. Carries aggregate counts, links to Product / Fixture / TestPackage / BuildRun (validation) or ManufacturingSession (mfg) / AssetSet / BoardRevision / operator. |
| `RunTarget` | One DUT in the run. `TargetStatus = PENDING|RUNNING|PASSED|FAILED|ERROR`. Holds discovered DUT identity (`serialNumber`, `deviceId`, IMEI, ICCIDs in metadata). Linked to `FixtureSlot`. |
| `TestExecution` | One test function (validation) or one manufacturing step. `ExecutionStatus = PENDING|RUNNING|PASSED|FAILED|SKIPPED|ERROR`. **`@@unique([targetId, name])`** prevents reporter regressions from creating duplicate rows. |
| `TestStep` | A `with report.step(...)` sub-step inside an execution. |

### 7. Users, RBAC, sessions

| Model | Carries |
|---|---|
| `User` | Google-OAuth-backed account. `Role` (ADMIN/MAINTAINER/DEVELOPER/OPERATOR) — organizational. `permissionSetId` — runtime permission strings. Both should stay in sync via `seed.py`. |
| `PermissionSet` | Named cluster of permission strings (`Concord.Firmware.AppID.Create`, etc.). Many users can share one. |
| `ProductAccess` | Per-(user, product) `AccessLevel` (`view|operate|develop|admin`). ADMIN/MAINTAINER role bypass these checks. |
| `ApiKey` | SHA-256-hashed API key linked to a user. Plaintext is shown once at creation. |
| `AuthSession` | RFC 8628 device-code flow row for CLI logins. `AuthSessionStatus = PENDING|APPROVED|EXPIRED|DENIED`. 10-minute approval window. |
| `RefreshToken` | 30-day rotating refresh tokens. `parentId` records the rotation chain; replayed (revoked) tokens kill the entire chain. |

### 8. Edge — ICLE devices

A separate world from the platform DB (these are power-monitor tools, not
DUTs). Heartbeat-and-pull model.

| Model | Carries |
|---|---|
| `IcleDevice` | ESP32-based device. `IcleDeviceStatus = ONLINE|OFFLINE|LOGGING|CONFIG|BOOT|OTA`. `registered` flips when an operator confirms via the UI. |
| `IclePendingCommand` | Command queued for delivery on the next heartbeat. `acknowledged` flips when the device confirms. |
| `IcleLog` | Log file uploaded from a device, stored in MinIO. |

### 9. Observability — audit, errors, notifications, releases

| Model | Carries |
|---|---|
| `AuditLog` | Append-only mutation log. Action (dotted lowercase), entityType (PascalCase model), entityId, details JSON, optional userId, ipAddress. Required for every mutation. |
| `ErrorReport` | Frontend errors + user-submitted bug reports. `ErrorReportStatus = OPEN|ACKNOWLEDGED|RESOLVED|DISMISSED`. Rich `context` JSON; denormalized currentPath/user/version for filtering. Linkable to a `Release`. |
| `Release` | Platform release record. `ReleaseStatus = DRAFT|STAGED|RELEASED|ROLLED_BACK`. Bundles component versions, changelog, test totals, code-diff stats, gate status. `/concord-release` skill creates these. |
| `Notification` | Per-user (or broadcast when `userId=NULL`) notification. `NotificationType` covers platform/validation/manufacturing/build/bug/system. Read tracking via `readAt`. Linked optionally to `Release` and `errorReportId`. |
| `NotificationPreference` | Per-(user, type) opt-out toggle. Default = enabled; presence means explicit choice. |
| `Secret` | Signing keys, SSH keys, API tokens. Base64 in DB, never exposed in API responses. Referenced by `ProductStageConfig.signingKey`. |
| `PollCache` | Bitbucket commit-SHA cache for the git poller. `(repoSlug, type, refId)` unique. |

## Special invariants worth remembering

- **`Node.status` is computed**, not stored. Migration `collapse_status_lockstate`
  removed the persisted column.
- **`Fixture.lockState` is derived**, not stored. Same migration. The API
  computes `FREE / IN_USE / MAINTENANCE` from `disabled` + presence of
  active sessions.
- **`TestExecution.name` is unique per RunTarget.** Enforced at the DB so
  a reporter regression (drop slotIndex → fall through to wrong target)
  can't silently create duplicate rows.
- **`TestBedDesign` is owned 1:1 by a TestPackage.** This is the contract:
  a package's manifest is the authority for what fixture the test
  expects.
- **`FixturePurpose` gates `TestPackageStatus`.** DEV fixtures accept only
  DEVELOPMENT packages; RELEASE fixtures accept only RELEASED packages.
- **CamelCase enum values vs lowercase.** Most enums are SHOUTY_CAPS,
  but `FirmwareVariant` (`smoke|debug|release|mfg`), `ReleaseTrack`
  (`bench|engineering|production`), `FirmwareSetStatus`
  (`active|deprecated|recalled`), `RecipeStatus` (`draft|published`), and
  `AccessLevel` (`view|operate|develop|admin`) are lowercase. The
  frontend `models.ts` must mirror exactly.

## How to add a new model

1. Add the model in the correct cluster section of `schema.prisma`. Use
   `///` doc comments to capture lifecycle invariants.
2. Add `@@map("snake_case")` and any necessary `@@index` / `@@unique`.
3. Add reverse relations on every related model.
4. Create + apply a migration — see
   [`migrations.md`](migrations.md).
5. Regenerate the Python client: `nx run database:generate-client`.
6. Update this file's structure block + the relevant cluster.
7. If the model introduces a new enum, also update
   [`enums.md`](enums.md).
8. Mirror the response shape into
   `apps/frontend/app/src/lib/types/models.ts` by hand — see
   [`../conventions.md`](../conventions.md).
9. If the model needs an API surface, see `/add-prisma-model` for the
   end-to-end flow (model + endpoint + page).

## How to add a new column

1. Edit the model in `schema.prisma`. Choose a sensible default for any
   `NOT NULL` column on a populated table.
2. Migrate: see [`migrations.md`](migrations.md).
3. Regenerate the client.
4. Update consumers — handlers, response classes, `models.ts`.
5. Add an audit-log call for any write path on the new column.

## Common failure modes

- **Prisma generate fails: `Cannot find module 'prisma'`.** Yarn deps not
  installed in the devcontainer. `yarn install` at the repo root, then
  `nx run database:generate-client`.
- **Migration applies in dev but http-api init container fails at start
  in staging.** The migration was committed without the matching schema
  changes (or vice versa). The init container runs `migrate deploy` which
  is strict about drift. See [`migrations.md`](migrations.md).
- **`P3009: migrate found failed migrations`.** A prior crash left a
  migration half-applied. The http-api init container auto-resolves this
  by calling `migrate resolve --rolled-back <name>` and retrying.
- **Frontend shows enum value as raw string with wrong casing.** The hand-
  maintained `models.ts` drifted from the schema. See
  [`enums.md`](enums.md) for the coordination checklist.
- **`onDelete: Cascade` wipes more than expected.** Walk the relation
  graph before changing cascade rules. The shared `TestRun → RunTarget
  → TestExecution → TestStep` chain cascades all the way down on purpose;
  the parent `Product` does *not* cascade to BuildJob/TestRun because
  Restrict is intentional.

## Related knowledge

- [`enums.md`](enums.md) — every enum, every value, every consumer.
- [`migrations.md`](migrations.md) — how migrations are created, applied,
  rolled back; the init-container flow.
- [`../libs/python-corekinect.md`](../libs/python-corekinect.md) — the
  generated client location.
- [`../conventions.md`](../conventions.md) — backend ↔ frontend contract
  rule (hand-mirrored types).
- [`../../rules/prisma-flow.md`](../../rules/prisma-flow.md) — schema-change
  policy.
