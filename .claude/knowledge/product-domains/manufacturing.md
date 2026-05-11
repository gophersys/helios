# Manufacturing — knowledge

The manufacturing domain models running a sequence of test stages against a panel (or standalone unit), repersonalizing devices to CoreOps, and producing per-DUT pass/fail records. It shares the `TestRun → RunTarget → TestExecution → TestStep` hierarchy with validation but adds an operator-managed `ManufacturingSession` parent, a personalization step at the end, and stricter fixture purpose / package status gating.

Refresh this file when: a new `ManufacturingSessionStatus` value is added, a new manufacturing stage is added to the standard sequence, the repersonalization API contract changes, the panel-resolution flow (CoreOps barcode lookup) changes, or the operator wizard flow changes.

## Entities

| Model | Role |
|---|---|
| `ManufacturingSession` | Operator-led batch on a fixture. Groups multiple `TestRun`s, one per panel/unit. Status: `ACTIVE → COMPLETED|CANCELLED|ARCHIVED`. |
| `ManufacturingConfig` | Per-product, per-board-revision config: which stages to run, firmware source, pass criteria, personalization config. |
| `TestRun` (`type=MANUFACTURING`) | One panel scan = one TestRun. Nested inside a session. |
| `RunTarget` | One DUT in a panel slot (or the single slot of a standalone fixture). Carries the discovered `serialNumber`, `deviceId`, IMEI, ICCIDs. |
| `TestExecution` | One sequential step (Electrical → fw_flash → smoke → final → personalize). Order matters; manufacturing stages are not parallel within a target. |
| `TestPackage` (`type=MANUFACTURING`) | Manufacturing-side test bundle. Same `UPLOADING → DEVELOPMENT → RELEASED` lifecycle as validation packages. |
| `Fixture` (`type=MANUFACTURING`) | The hardware rig. `MOTION_ENABLED=false`. Panel fixtures have multiple slots; standalone fixtures have one. |
| `FixturePurpose` | `DEV` or `RELEASE`. Gates which package status the session can run against. |

Schema: `prisma/schema.prisma:1359-1422` (ManufacturingConfig, ManufacturingSession), `:1435-1589` (shared TestRun hierarchy).

## Lifecycle

### Session

```
(operator picks fixture + product + package)
                │
                ▼
            ACTIVE ──────────► COMPLETED
                │                  ▲
                │                  │ (operator clicks "End session")
                │
                ├──────────────► CANCELLED  (operator cancels mid-session)
                │
                └──────────────► ARCHIVED  (admin archives after retention window)
```

A session is **long-lived** — typically a full operator shift. Many TestRuns are nested inside it.

### Per-panel TestRun (within a session)

```
PENDING ─► ACTIVE ──► COMPLETED
    │         │           │
    │         │           └─► FAILED  (any target failed any stage)
    │         └─► FAILED  (runner died, scan resolution failed)
    └─► CANCELLED
```

End-to-end:

1. **Operator opens a session** — `POST /v2/manufacturing/sessions` with `{productId, fixtureId, testPackageId?, assetSetId?}`. Handler at `apps/backend/http-api/src/api/v2/manufacturing/sessions.py:create_manufacturing_session`. If `testPackageId` is null, the server resolves the latest `RELEASED` package at runner-deploy time. The fixture's `purpose` and the package's `status` must agree (a `RELEASE` fixture rejects `DEVELOPMENT` packages and vice-versa).
2. **Runner deploys** — http-api creates a long-lived K8s Deployment (not a Job — manufacturing runners persist for the session). Stored in `ManufacturingSession.runnerDeploymentName`. Status flows `DEPLOYING → READY → RUNNING|ERROR|WAITING`.
3. **Operator scans a panel** — UI calls `POST /v2/manufacturing/sessions/<id>/resolve-panel` with the scanned barcode. The handler calls CoreOps (`apps/backend/http-api/src/api/v2/manufacturing/sessions.py:resolve_panel`, around line 853) to look up the assembly:
   - **Panel**: CoreOps returns each board's serial number and its `panelPosition`. The handler maps positions → fixture slot indices via `Fixture.metadata.panelPositionMap`.
   - **Standalone**: a single board, single slot. The barcode is the slot's DUT SNR directly.
4. **TestRun created** — one `TestRun` per scan. `panelIdentifier` is the barcode. Per-slot `RunTarget` rows are created with the resolved SNRs.
5. **Stages execute serially per target**:
   - **Electrical** — current/voltage checks before firmware flash.
   - **fw_flash** — JTAG flash of all firmware images from the `AssetSet` via MTIB `Program*` RPCs.
   - **smoke** — basic boot + console banner check post-flash.
   - **final** — full manufacturing test sequence (radios, sensors, antennas).
   - **personalize** — assign device identity. Writes CoreOps bindings: `device_id ↔ SNR ↔ SIM ↔ EID ↔ IMEI`. Persists IMEI/ICCID to `RunTarget.metadata`.
6. **Results stream** — runner POSTs results via `apps/backend/http-api/src/api/v2/runs/reporter.py`. Same reporter handler that validation uses. Each step writes an audit log row.
7. **End session** — operator clicks "End session". `POST /v2/manufacturing/sessions/<id>/end` tears down the runner deployment and flips status to `COMPLETED`.

### State transitions, by service

| Transition | Owner | File |
|---|---|---|
| Session `ACTIVE → COMPLETED` | operator via UI | `sessions.py:end_manufacturing_session` (line 1234) |
| Runner deploy | http-api | `sessions.py:deploy_manufacturing_runner` |
| TestRun `PENDING → ACTIVE` | runner picks the next scan | `runs/reporter.py` |
| Per-stage `TestExecution` updates | runner POST | `runs/reporter.py` |
| Personalization writes to CoreOps | http-api during the personalize stage | `sessions.py` via `corekinect.core_ops.client.CoreOpsClient` |

## Where the code lives

| Concern | Path |
|---|---|
| Session CRUD + lifecycle | `apps/backend/http-api/src/api/v2/manufacturing/sessions.py` |
| Runner deploy + teardown | same file, `deploy_manufacturing_runner` / `teardown_manufacturing_runner` |
| Panel barcode resolution (CoreOps) | `sessions.py:resolve_panel`, `_resolve_panel_snrs` |
| Personalization (writes CoreOps bindings) | `sessions.py` + `libs/python/corekinect/core_ops/` |
| Per-product manufacturing test suites | `apps/manufacturing/<product>/` — submodule per product |
| Frontend operator wizard | `apps/frontend/app/src/routes/manufacturing/` |
| Prisma models | `prisma/schema.prisma:1359-1422` |

## Key invariants

- **`Fixture.purpose` and `TestPackage.status` must agree.** `RELEASE` fixtures reject `DEVELOPMENT` packages and vice-versa. Enforced at session creation; the operator wizard prevents the mismatch in the UI.
- **`MOTION_ENABLED=false` on every manufacturing MTIB.** Same `_mtib_env_for_fixture` derivation as validation but inverted. Never override.
- **Stages execute serially per target.** Unlike validation (where pytest can parallelize), manufacturing stages have ordering dependencies — electrical must precede flash, flash must precede smoke, etc.
- **`RunTarget.serialNumber` is discovered, not pre-assigned.** Until the panel barcode is scanned and CoreOps returns the per-position SNRs, the slot's `RunTarget` rows have `serialNumber=null`. Set during `resolve-panel`.
- **Personalization is one-shot per DUT.** Writing the CoreOps binding is idempotent (the API accepts the same input twice) but the operator workflow doesn't re-personalize — if a DUT fails post-personalize, it's pulled and reworked offline.
- **No `MOTION_*` calls.** Manufacturing test packages must not use motion gRPC — the MTIB pod will refuse since `MOTION_ENABLED=false`. Test packages that violate this get caught in CI.
- **Session is the audit unit.** Audit logs are written per stage (`test.stage.complete`), but the session id is recorded in `details` so an admin can reconstruct the full shift from a single query.

## Panel vs standalone

A `Fixture` is one or the other based on its slot layout:

| Layout | Slots | Use |
|---|---|---|
| Panel | N slots in a grid (`panelRows × panelCols`) | Batch manufacturing — multiple DUTs flashed/tested in parallel. |
| Standalone | 1 slot, often labelled "Stand Alone" | Single-unit rework, debug, low-volume products. |

The `resolve_panel` handler distinguishes them by label: slots whose label starts with `standalone` are the standalone slot list, the rest are panel slots. A fixture can have both (e.g. a 4-slot panel plus a "rework" standalone next to it); the operator picks which one they're using at session-start.

## How to extend

### Adding a new manufacturing stage

1. Add the stage name to the product's `ManufacturingConfig.stages` JSON.
2. Implement the stage in the product's manufacturing test suite (`apps/manufacturing/<product>/`).
3. If the stage needs a new MTIB capability, add the RPC to `libs/protocols/mtib/mtib.proto` and update the edge server.
4. Update `.claude/knowledge/product-domains/manufacturing.md` (this file) — the standard stage table.

### Adding a new product to manufacturing

1. Create `Product` row.
2. Create at least one `BoardRevision`.
3. Create `ManufacturingConfig` for that (product, revision) pair via `POST /v2/manufacturing/configs`. Set `stages`, `firmwareSource`, `passCriteria`, `personalizationConfig`.
4. Upload a manufacturing `TestPackage` (`type=MANUFACTURING`).
5. Create a manufacturing-purpose `Fixture` and bind MTIB nodes to its slots.
6. Add a manufacturing submodule under `apps/manufacturing/<product>/`.

### Adding repersonalization (custom binding)

The default personalization writes `device_id ↔ SNR ↔ SIM ↔ IMEI`. To add fields:

1. Extend `ManufacturingConfig.personalizationConfig` schema.
2. Update the personalize stage in `apps/manufacturing/<product>/`.
3. Extend the CoreOps client in `libs/python/corekinect/core_ops/` if the API surface needs new fields.

## Common failure modes

**Operator wizard rejects package** — fixture purpose / package status mismatch. The error toast names the conflict (`RELEASE fixture cannot run DEVELOPMENT package`). Either change the package status to `RELEASED` or use a `DEV` fixture.

**Panel scan returns "Assembly not found"** — CoreOps doesn't have the assembly. The panel was never registered in CoreOps, or it was registered under a different SNR than what's printed on the barcode. Cross-check `corectl boards assemblies search --snr=<value>` against the scan.

**Slot SNRs mapped wrong** — the fixture's `panelPositionMap` metadata doesn't match the physical layout. CoreOps returns positions in assembly order; the map translates to fixture slot indices. This was the root cause of the 2025 Q4 slot-1/standalone-MTIB swap incident — MTIBs were physically swapped between slot 1 and the standalone slot, the position map was correct for the original wiring, so DUT identities were assigned to the wrong slots. Always verify by physically reading the DUT SNR off the silkscreen post-personalize before the run goes to `COMPLETED`.

**Runner stuck at `WAITING`** — runner deployment is up but no heartbeat. Same diagnostic flow as validation: `kubectl describe pod <runner>`. Often an MTIB gRPC reach issue — `MtibV1` not responding because the node went `NotReady`.

**`fw_flash` stage hangs at 99%** — J-Link probe enumeration failure. The slot's `jlinkAppSerial` doesn't match the SNR of the J-Link physically connected to that slot. Verify with `JLinkExe -listemus` on the Verdin.

**Personalize fails with CoreOps 401** — `COREOPS_API_KEY` / `COREOPS_AUTH_USER` / `COREOPS_AUTH_PASS` drift. All three rotate together — see [`../workflows/credentials.md`](../workflows/credentials.md#coreops-device-personalization).

**Session can't be ended** — the runner teardown failed. Inspect `kubectl get deploy -l concord.session=<id>` and clean up manually with `kubectl delete deploy <name>`. Then call `POST /v2/manufacturing/sessions/<id>/end` again.

## Related knowledge

- [`validation.md`](validation.md) — shared TestRun hierarchy, different lifecycle
- [`fixtures.md`](fixtures.md) — Fixture, FixtureSlot, panel layout, MTIB binding
- [`products.md`](products.md) — Product, ProductVariant, TestPackage, AssetSet
- [`builds.md`](builds.md) — where the AssetSet that manufacturing consumes comes from
- [`users-rbac.md`](users-rbac.md) — `MANUFACTURING_RUN` vs `MANUFACTURING_MANAGE` permissions
- [`../apps/backend/http-api.md`](../apps/backend/http-api.md) — handler internals
- [`../libs/python-corekinect.md`](../libs/python-corekinect.md) — CoreOps client wrapper
- `/home/mateo/work/docs/incidents/` — prior manufacturing incident postmortems
