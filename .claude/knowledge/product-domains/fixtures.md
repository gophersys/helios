# Fixtures — knowledge

The fixtures domain models the physical test rigs Concord drives. A fixture is one or more MTIB-equipped slots wired to mate with DUTs of a specific board revision. The model unifies what used to be two separate concepts ("test bench" for single-slot validation, "manufacturing fixture" for multi-slot panels) into a single `Fixture` with type, purpose, and a derived live lock state.

Refresh this file when: a new `NodeType` or `FixturePurpose` value is added, the live-lock derivation rules change, the MTIB-to-slot binding shape changes, the FixtureDesign profile schema is extended, or new slot fields are added.

## Entities

| Model | Role |
|---|---|
| `FixtureDesign` | The template — a versioned hardware design (PCB/wiring spec) bound 1:1 to a `TestPackage`. Concord stores the `profileTemplate` JSON (power config, GPIO pinout, slot defaults) but never interprets it; product-specific test code does. |
| `Fixture` | A physical instance of a design. Tracks panel layout, purpose, and per-instance profile overrides. |
| `FixtureSlot` | A single position within a fixture. 1:1 with an MTIB `Node`. Carries J-Link SNRs, UART paths, and (during a session) the bound DUT identity. |
| `Node` | The K8s node behind a slot — typically a Verdin iMX8MM running `mtib-server`. Type matches the fixture's type. |
| `FixturePurpose` | `DEV` (accepts development packages) or `RELEASE` (released packages only). Gates which test package status can run on this fixture. |
| `NodeType` | `MANUFACTURING` or `VALIDATION`. Set on both the fixture and the bound nodes; they must agree. |

Schema: `prisma/schema.prisma:740-896` (FixtureDesign, Fixture, FixtureSlot, Node), `:126-130` (FixturePurpose), `:28-31` (NodeType).

## Lifecycle

### FixtureDesign

```
(test package upload with type=MANUFACTURING|VALIDATION + fixture.yaml manifest)
                            │
                            ▼
                    DEVELOPMENT ──► RELEASED
                            │           │
                            └── (mirrored from owner TestPackage.status)
```

A `FixtureDesign` is created when a test package upload includes a `fixture.yaml` manifest. The design's status mirrors the parent package's — denormalized so fixtures can join the design without joining the package.

### Fixture

```
1. (create)
        │
        ▼
   slots empty ────► slots bound to nodes ────► FREE (derived)
                             │
                             ▼
                        IN_USE (derived, while a session/run is ACTIVE)
                             │
                             ▼
                        FREE again

(disabled=true at any point ──► MAINTENANCE, derived live, unconditional)
```

The headline pattern: **lock state is derived, not stored**. The API computes `lockState ∈ {FREE, IN_USE, MAINTENANCE}` at serialize time from:

- `MAINTENANCE` ← `Fixture.disabled = true` (admin override)
- `IN_USE` ← any `ManufacturingSession` or `TestRun` with `status=ACTIVE` referencing this fixture
- `FREE` ← otherwise

The only DB-stamped flag is `disabled`. This kills the stored-state drift class of bug (orphaned locks after a crash or a missed unlock path) — same lesson as the v0.7.0 `Node.status` collapse.

### Slot

```
created with fixture (active=true, nodeId=null)
        │
        ▼
   MTIB registered → assigned to slot (Node.id linked) → ready
        │
        ▼
   (during a session) DUT identity populated (dutDeviceId, dutSnr, dutImei, dutIccids)
        │
        ▼
   (session ends) DUT identity cleared; slot ready for next session
```

The `@unique` constraint on `FixtureSlot.nodeId` means a node can only be bound to one slot at a time. `NULL` is exempt from uniqueness, so multiple empty slots are fine.

## Where the code lives

| Concern | Path |
|---|---|
| Fixture CRUD + slot management | `apps/backend/http-api/src/api/v2/fixtures/fixtures.py` |
| FixtureDesign upload (via TestPackage manifest) | `apps/backend/http-api/src/api/v2/products/test_packages*.py` |
| MTIB deploy/undeploy per slot | `apps/backend/http-api/src/api/v2/fixtures/fixtures.py:_deploy_mtib_for_slot`, `services/kubernetes/mtib_deployments.py` |
| Per-fixture MTIB env derivation | `apps/backend/http-api/src/api/v2/fixtures/fixtures.py:_mtib_env_for_fixture` |
| Node CRUD (MTIB registration) | `apps/backend/http-api/src/api/v2/nodes/nodes.py` |
| Frontend fixture list/detail | `apps/frontend/app/src/routes/fixtures/` |
| Prisma models | `prisma/schema.prisma:740-896` |

## Key invariants

- **Slot ↔ node is 1:1 at any moment.** Enforced by `@unique` on `FixtureSlot.nodeId`. Multiple nulls (empty slots) allowed.
- **`Fixture.type` agrees with every bound slot's `Node.type`.** A `MANUFACTURING` fixture only binds `MANUFACTURING` nodes; same for `VALIDATION`. The bind handler rejects mismatched types.
- **`MOTION_ENABLED` is derived from `Fixture.type`.** `VALIDATION` → `true`, `MANUFACTURING` → `false`. Computed by `_mtib_env_for_fixture(fixture)` and stamped on the MTIB pod at deploy time. Override per-instance only via `Fixture.profileOverrides` and a corresponding code path.
- **Lock state is NEVER stored.** The API computes it live. No code may write a `lockState` column — there is none.
- **`FixturePurpose.RELEASE` only accepts `TestPackageStatus.RELEASED` packages.** Enforced at session/run creation. `DEV` fixtures accept either status.
- **FixtureDesign owns 1:1 of its TestPackage.** Enforced by `@unique` on `FixtureDesign.testPackageId`. A package either ships a fixture profile or it doesn't.
- **Nodes with TestExecution history can't be deleted.** Default Prisma `Restrict` cascade. To decommission: set `Node.disabled=true` and unassign from the slot.
- **The MTIB deployment name lives on the Node.** `Node.metadata["deployment_name"]` is the K8s Deployment for the MTIB server on that slot. Persisted to enable cleanup; not the source of truth for liveness (that's computed from K8s pod readiness + gRPC probe).

## Panel layout

`Fixture.panelRows × Fixture.panelCols` defines the physical grid. Standalone fixtures use `1 × 1`. A panel-and-standalone hybrid (a 4-slot panel + a labelled standalone slot for rework) is modelled as `panelRows × panelCols` for the panel slots plus extra slots whose `label` starts with `standalone`. The manufacturing wizard distinguishes them by label prefix when resolving barcodes; see [`manufacturing.md`](manufacturing.md).

## Slot hardware paths

Each `FixtureSlot` carries the hardware identifiers the MTIB needs to address the DUT:

| Field | Example | Used by |
|---|---|---|
| `jlinkAppSerial` | `"0964"` | MTIB Program* RPCs to flash the app SoC (nRF52840) |
| `jlinkCommsSerial` | `"0972"` | MTIB Program* RPCs to flash the comms SoC (nRF9151) |
| `uartAppPath` | `"/dev/verdin-uart2"` | MTIB UartStream RPC |
| `uartCommsPath` | `"/dev/verdin-uart1"` | MTIB UartStream RPC |
| `dutDeviceId` | `"70B3D584C01E1FCC"` | CoreCloud device ID, set during manufacturing personalization |
| `dutSnr` | `"0964"` | Board serial number, matches J-Link SNR for nRF52840-based DUTs |
| `dutImei` | `"355025931735979"` | LTE IMEI, written to CoreOps during personalize |
| `dutIccids` | `["8914...", "8945..."]` | SIM ICCIDs, ditto |

J-Link SNRs are sticky to the physical probe. UART paths are sticky to the Verdin USB port wiring. Both are set at fixture assembly time and only change when hardware is rewired.

## How to extend

### Adding a new fixture purpose

1. Add to `FixturePurpose` enum in `prisma/schema.prisma` + migration.
2. Update gating logic in `apps/backend/http-api/src/api/v2/manufacturing/sessions.py` and `apps/backend/http-api/src/api/v2/runs/runs.py` — both currently check `RELEASE` vs `DEVELOPMENT`. Extend to the new value.
3. Update frontend purpose selectors (`apps/frontend/app/src/routes/fixtures/`).
4. Update this knowledge file and `.claude/knowledge/prisma/enums.md`.

### Adding a new slot field

1. Add to `FixtureSlot` in `prisma/schema.prisma` + migration.
2. Update `_serialize_slot` in `apps/backend/http-api/src/api/v2/fixtures/fixtures.py`.
3. Update `apps/frontend/app/src/lib/types/models.ts`.
4. Update any consumer (validation/manufacturing test code that reads the slot's hardware paths).

### Binding a new MTIB to a fixture

1. Register the node: `POST /v2/nodes` with `{name, hostname, type, ipAddress, hardwareRevision}`.
2. Assign to a slot: `POST /v2/fixtures/<id>/slots/<index>/bind-node` with `{nodeId}`. Triggers MTIB deployment via `_deploy_mtib_for_slot`.
3. The MTIB deployment polls gRPC :50053 for 60s; if it doesn't come up, the bind fails with a 502.

## Common failure modes

**MTIB deploys but `connection refused` on gRPC 50053** — the pod is up but the server hasn't bound the port. Usual cause: the `MOTION_ENABLED` env was missing, causing the init script to bail. Verify with `kubectl exec <pod> -- printenv | grep MOTION`.

**Slot rejects node binding with "type mismatch"** — the fixture is `MANUFACTURING` but the node was registered as `VALIDATION` (or vice versa). Re-register the node with the correct type or pick a different node.

**Fixture stuck `IN_USE` after a session crashed** — the session's status didn't transition out of `ACTIVE`. Inspect with `kubectl exec deploy/concord-http-api -- python3 -c "from database import db; ..."`. Mark the orphaned session `CANCELLED` to free the fixture. This used to require manual DB surgery; the derived-state model means the lock clears the moment the session row updates.

**`FixtureDesign` won't update** — the parent `TestPackage` is `RELEASED` (immutable). Upload a new test package version; the design is recreated from the new manifest.

**DUT identity sticky across sessions** — the slot's `dutDeviceId`/`dutSnr` weren't cleared at session end. Session teardown should clear them; if it didn't, an admin can null the fields directly. Symptom: the next session creates a `RunTarget` pre-populated with the prior session's DUT.

**MTIB redeploy doesn't pick up new env** — the deployment is using the old ConfigMap. `kubectl rollout restart deploy/<mtib-deploy-name>` or trigger via http-api's redeploy endpoint.

## Related knowledge

- [`validation.md`](validation.md) — `VALIDATION` fixtures and motion gating
- [`manufacturing.md`](manufacturing.md) — `MANUFACTURING` fixtures, panel layout, slot resolution
- [`products.md`](products.md) — board revisions, test packages, fixture purpose interaction
- [`../apps/edge/mtib-server.md`](../apps/edge/mtib-server.md) — the gRPC server bound to each slot
- [`../apps/backend/http-api.md`](../apps/backend/http-api.md) — fixture handler internals
- [`../prisma/schema-overview.md`](../prisma/schema-overview.md) — full data model
- [`../../rules/all-three-envs.md`](../../rules/all-three-envs.md) — why `MOTION_ENABLED` derivation lives in three values files
