# Products — knowledge

The products domain anchors everything else: a `Product` is the canonical hardware identity (Alpha, Sigma5, Theta) from which builds, fixtures, validation, and manufacturing all derive. The full chain is `Product → Board → BoardRevision → ProductTarget` (firmware addressing) plus `TestPackage` (the test suite for a given board revision). `Codebase` is the logical name for the firmware repo backing a product (`alpha_fw`, `sigma5_mfg_fw`, etc.) — captured on the Product via `fwRepoSlug` and `mfgFwRepoSlug`.

Refresh this file when: a new `TestPackageStatus` value is added, the Product/Board/BoardRevision hierarchy changes shape, the `ProductTarget` SoC/AppID schema changes, or the upload/release flow for test packages changes.

## Entities

| Model | Role |
|---|---|
| `Product` | The top-level hardware product (Alpha B0, Sigma5 C0, Theta). Names firmware repos, builder image, and metadata. |
| `Board` | A PCB design within a product. Typically 1:1 (`@unique productId`), but the schema allows for future multi-board products. Names the `ck_boards` family. |
| `BoardRevision` | A revision of a Board (A0, B0, C1). The unit firmware actually targets. Names the `ck_boards` directory, SoCs, modem version. |
| `ProductTarget` | A firmware target within a board revision — one per role/SoC (`comms` on nRF9151, `app` on nRF52840). Carries the CoreCloud `appId`. |
| `Codebase` | Conceptual: the firmware repo. Stored as `Product.fwRepoSlug` (production FW) and `Product.mfgFwRepoSlug` (manufacturing FW). Bitbucket slugs in the `corekinect` workspace. |
| `TestPackage` | A versioned bundle of test code uploaded for a product. Type `VALIDATION` or `MANUFACTURING`. Status `UPLOADING → DEVELOPMENT → RELEASED`. |
| `ModemFirmware` | Nordic modem firmware version per board revision. Referenced by `AssetSet`. |
| `FirmwareSet` | A versioned bundle of compiled firmware (one set spans multiple builds — e.g. "Alpha B0 v0.5.2-BM"). Pre-AssetSet model; still used for release tracking. |
| `ProductStageConfig` | Per-product, per-stage validation config — names the blessed test package version for each stage. |

Schema: `prisma/schema.prisma:198-360` (Product, Board, BoardRevision, ProductTarget), `:241-301` (TestPackage), `:241` (TestPackageStatus enum at `:115-119`).

## Lifecycle

### Product

```
created ──► ACTIVE ──► ARCHIVED
```

`ProductStatus` is binary: `ACTIVE` or `ARCHIVED`. Archive when a product line ends; no destructive delete (foreign keys would orphan).

### BoardRevision

```
DRAFT ──► ACTIVE ──► DEPRECATED ──► EOL
```

`LifecycleStatus` values from the shared enum. `ACTIVE` revisions accept new builds; `DEPRECATED` block new builds but accept existing assets; `EOL` is read-only.

### TestPackage

```
UPLOADING ──► DEVELOPMENT ──► RELEASED
    │             │
    │             └─► (re-uploaded; overwrites in-place on same branch)
    │
    └─► reaped after retention if upload never completes
```

- `UPLOADING` — placeholder row created before the MinIO put. Two-phase commit: the row is created so the upload URL can reference an id, the MinIO put streams up, then status flips. Stale UPLOADING rows are swept by retention.
- `DEVELOPMENT` — mutable. Versions named `dev-<sha>-<timestamp>`. Re-uploading the same branch overwrites in place.
- `RELEASED` — immutable. Versions named with semver (`1.2.0`). Promotion via `POST /v2/test-packages/<id>/release` stamps `releasedAt` and `releasedById`.

`FixturePurpose.RELEASE` fixtures only accept `RELEASED` packages; `DEV` fixtures accept either status.

### Codebase ↔ build flow

```
Bitbucket commit on Product.fwRepoSlug
        │
        ▼
   git-poller observes (BITBUCKET_POLLER_INTERVAL_S = 300s) or webhook fires
        │
        ▼
   POST /v2/builds/runs → BuildRun PENDING
        │
        ▼
   build-service worker → BuildJob CLONING → BUILDING → SUCCESS
        │
        ▼
   AssetSet PENDING → COMPLETE → VALIDATED (after a passing validation run)
        │
        ▼
   Used by validation TestRun or manufacturing ManufacturingSession
```

The same flow applies to `mfgFwRepoSlug` for manufacturing firmware, but those builds target `FirmwareVariant.mfg` and feed manufacturing sessions specifically.

## Where the code lives

| Concern | Path |
|---|---|
| Product CRUD | `apps/backend/http-api/src/api/v2/products/products.py` |
| Board / BoardRevision / ProductTarget CRUD | `apps/backend/http-api/src/api/v2/products/boards.py`, `board_revisions.py` |
| TestPackage upload + release | `apps/backend/http-api/src/api/v2/products/test_packages*.py` |
| ProductStageConfig | `apps/backend/http-api/src/api/v2/builds/stage_config.py` |
| Manifest (`concord.yaml`) parsing | `apps/backend/http-api/src/api/v2/builds/manifest.py` |
| Frontend product views | `apps/frontend/app/src/routes/products/`, `apps/frontend/app/src/routes/test-packages/` |
| Permission gating | `PRODUCTS_VIEW`, `PRODUCTS_MANAGE` (`apps/backend/http-api/src/lib/permissions.py`) |
| Prisma models | `prisma/schema.prisma:198-360`, `:241-301`, `:1191-1276` |
| `ck_boards` repo (board definitions) | external; cloned at `CK_BOARDS_REPO_URL`, fetched every `CK_BOARDS_FETCH_INTERVAL` seconds |

## Key invariants

- **`Product.name` and `Product.slug` are both unique.** Slug is URL-safe (`alpha_b0`); name is display (`Alpha B0`).
- **A `Board` has exactly one `Product`.** `@unique productId` on `Board`. The schema reserves room for a future multi-board product but no current product uses it.
- **`BoardRevision.ckBoardsName` is globally unique.** It's the west build-target name (`alpha_b0`, `sigma5_c0`). Build-service uses it to construct the build command.
- **`ProductTarget` is `(boardRevisionId, role)` unique AND `(boardRevisionId, appId)` unique.** A given board revision has exactly one `comms` and exactly one `app` target; appIds don't collide within a revision.
- **TestPackage `(productId, version, type)` is unique.** Re-uploading bumps the version; you can't have two `1.2.0` validation packages for the same product.
- **`releasedVersion` is set only when status flips to `RELEASED`.** Useful for the `(productId, releasedVersion, type)` unique constraint that lets you look up "the released 1.2.0 of Alpha validation" without ambiguity.
- **TestPackage release is one-way.** No `unrelease` endpoint. To replace a released version, upload a new one.
- **The frontend `models.ts` mirror is hand-maintained.** There's no codegen between backend and frontend; type drift is caught in review and contract tests. See [`../conventions.md`](../conventions.md#frontend-↔-backend-contract).

## ck_boards integration

Concord doesn't own the canonical board definitions. They live in a separate Bitbucket repo (`ck_boards`) — Zephyr board overlays, DTS files, BOMs. The http-api clones it periodically (`CK_BOARDS_REPO_URL` / `CK_BOARDS_FETCH_INTERVAL`) and references it by:

- `Board.ckBoardsFamily` — the family prefix (`alpha`, `sigma5`).
- `BoardRevision.ckBoardsName` — the specific board target (`alpha_b0`).
- `BoardRevision.socs` — parsed from `board.yml` in that directory.

Build-service uses `ckBoardsName` as the west build target. Validation/manufacturing test code references it indirectly via the test package's manifest.

## How to extend

### Adding a new Product

1. `POST /v2/products` — `{name, slug, fwRepoSlug, mfgFwRepoSlug, builderImage}`.
2. `POST /v2/products/<id>/boards` — at least one `Board`.
3. `POST /v2/boards/<id>/revisions` — at least one `BoardRevision`. Verify the `ckBoardsName` exists in the `ck_boards` repo (the API checks at creation time).
4. `POST /v2/board-revisions/<id>/targets` — one `ProductTarget` per SoC/role. Allocate appIds in coordination with CoreCloud.
5. Upload a `TestPackage` (validation, manufacturing, or both) via the SvelteKit UI.
6. Create a `Fixture` of the appropriate type.

### Adding a new BoardRevision

1. Add the directory under `ck_boards` repo. Push to Bitbucket.
2. Wait for the http-api's `ck_boards` poller to fetch (or trigger via `POST /v2/system/refresh-ck-boards`).
3. `POST /v2/boards/<id>/revisions` — the API validates `ckBoardsName` resolves.
4. Add a `BoardRevision`-specific `ManufacturingConfig` if manufacturing differs from existing revisions.

### Adding a new TestPackageStatus

1. Add to `prisma/schema.prisma:115-119` + migration + python client regen.
2. Update `apps/backend/http-api/src/api/v2/products/test_packages*.py` — the release/upload flow's allowed-transition table.
3. Update gating logic in `apps/backend/http-api/src/api/v2/manufacturing/sessions.py` (fixture purpose check) and `apps/backend/http-api/src/api/v2/runs/runs.py`.
4. Update `apps/frontend/app/src/lib/types/models.ts` and status pills.
5. Update `.claude/knowledge/prisma/enums.md`.

## Common failure modes

**Upload stuck `UPLOADING`** — the MinIO put never completed (network blip, browser closed). The retention sweeper reaps these after the configured window. To recover immediately, `DELETE /v2/test-packages/<id>` from the UI.

**`POST /v2/board-revisions/<id>/targets` 409 conflict** — an existing target already has that role or appId for the revision. Either reuse the existing one or pick a different appId. CoreCloud appId allocations live in a spreadsheet owned by the firmware team.

**`build-service` can't find `ckBoardsName`** — the local `ck_boards` clone is stale or you typed the name wrong. Trigger `POST /v2/system/refresh-ck-boards`, then retry. If the path still doesn't resolve, check the actual `ck_boards` directory listing.

**Frontend shows the wrong number of build matrix targets** — `BoardRevision.socs` is wrong. Re-parse from `board.yml` (the http-api caches; force a refresh via the API).

**TestPackage release fails with `manifest mismatch`** — the `concord.yaml` in the uploaded tarball declares a `frameworkVersion` the runner can't satisfy. Either bump the runner image or pin to an older `corekinect` SDK version.

**Cross-product asset pollution** — an AssetSet with the wrong `productId` was created (manual upload misconfigured). The `@@unique([productId, version, type])` constraint on `TestPackage` prevents the same on packages, but AssetSet has only an index, not a unique. Catch in review.

## Related knowledge

- [`builds.md`](builds.md) — BuildRun/BuildJob/AssetSet flow rooted on a Product
- [`validation.md`](validation.md) — validation TestPackages and stage configs
- [`manufacturing.md`](manufacturing.md) — manufacturing TestPackages and personalization
- [`fixtures.md`](fixtures.md) — fixtures bound to board revisions
- [`users-rbac.md`](users-rbac.md) — `PRODUCTS_VIEW`/`PRODUCTS_MANAGE` and per-product `AccessLevel`
- [`../apps/backend/http-api.md`](../apps/backend/http-api.md) — handler internals
- [`../prisma/schema-overview.md`](../prisma/schema-overview.md) — full data model
- [`../../rules/prisma-flow.md`](../../rules/prisma-flow.md) — schema-change procedure
