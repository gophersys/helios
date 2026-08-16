# Validation — knowledge

The validation domain models running a test package against a firmware AssetSet on a real fixture. It exists to gate firmware promotion — a `BuildRun` doesn't flip from `VALIDATING → SUCCESS` until at least one validation `TestRun` against its AssetSet passes. Distinct from manufacturing in three ways: it runs on `VALIDATION`-type fixtures (with motion hardware), it consumes `VALIDATION`-type test packages, and the DUTs are not personalized at the end.

Refresh this file when: a new `TestRunStatus` value is added, the runner deployment shape changes, the queue scheduler changes its admission/concurrency policy, motion gating changes, or a new validation stage is introduced.

## Entities

| Model | Role |
|---|---|
| `TestRun` (`type=VALIDATION`) | One end-to-end validation execution. The atomic unit of the domain. |
| `RunTarget` | One DUT (i.e. one fixture slot) within a TestRun. Panel runs have many; bench runs have one. |
| `TestExecution` | One pytest test function executed against one RunTarget. |
| `TestStep` | A sub-step inside a TestExecution, created by `with report.step("name"):` in test code. |
| `TestPackage` (`type=VALIDATION`) | The Python test suite uploaded for a product. Status: `UPLOADING → DEVELOPMENT → RELEASED`. |
| `TestPackageStage` | Structured metadata extracted from `concord.yaml` at upload (the named stages and their directories). |
| `ProductStageConfig` | Per-product, per-stage config — points at the blessed test package version for that stage. |
| `ValidationQueueEntry` | A queued TestRun waiting for a fixture. Owned by the scheduler. |
| `Fixture` (`type=VALIDATION`) | The hardware rig. `MOTION_ENABLED=true` env on the MTIB pod. Usually single-slot. |

Schema: `prisma/schema.prisma:1435-1589` (TestRun → RunTarget → TestExecution → TestStep), `:524-573` (ValidationQueueEntry).

## Lifecycle

```
            (queue)               (deploy)              (run)
PENDING ────────────► ACTIVE ──────────────► COMPLETED ─► (terminal)
   │                    │                       │
   │                    │                       └──► FAILED
   └──► CANCELLED       └──► FAILED  (runner died, deploy failed, etc.)
```

End-to-end:

1. **Trigger** — `POST /v2/runs` from the UI or a `BuildRun` finishing with `autoRunStage=true`. Handler at `apps/backend/http-api/src/api/v2/runs/runs.py`. Creates `TestRun` row in `PENDING`, plus a `ValidationQueueEntry`.
2. **Schedule** — the queue scheduler (`apps/backend/http-api/src/api/v2/runs/scheduler.py`, ticks every `SCHEDULER_INTERVAL_S` = 15s) walks `PENDING` entries, picks the highest-priority one whose fixture is `FREE`, and deploys the runner.
3. **Deploy runner** — http-api creates a K8s `Job` on the fixture's node, scheduled via the `kubernetes` Python client (`apps/backend/http-api/src/services/kubernetes/jobs.py`). The job pod image is the test package's framework image; the test package itself is downloaded from MinIO at pod startup.
4. **Pair targets** — each `RunTarget` (one per fixture slot) is bound to a physical DUT. For validation this is usually trivial (one slot, one DUT). The runner reads the slot's `dutDeviceId`, `dutSnr`, `dutImei` from `FixtureSlot`.
5. **Flash + execute** — the runner uses MTIB gRPC (`apps/edge/mtib-server/`) to power-cycle, flash firmware (`Program*` RPCs), and drive the DUT (GPIO, UART, ADC, optionally `MOTION_*` RPCs for vibration / IMU sweeps). For each pytest test it discovers, it writes a `TestExecution` row and streams sub-steps as `TestStep` rows.
6. **Report results** — runner POSTs `POST /v2/runs/<id>/target/<tid>/stage/<sid>/complete` per execution (handler at `apps/backend/http-api/src/api/v2/runs/reporter.py`). The handler updates the `TestExecution`, recomputes parent aggregates (`TestRun.passedCount`, `completedCount`, etc.), writes an `AuditLog`, and emits a Notification.
7. **Terminate** — runner POSTs the final status. http-api updates `TestRun.status` to `COMPLETED|FAILED`, tears down the K8s Job, frees the fixture, and (if this was an `autoRunStage` run) flips the parent `BuildRun` to `SUCCESS|FAILED`. If the run validated an AssetSet, the AssetSet flips to `VALIDATED`.

### State transitions, by service

| Transition | Owner | File |
|---|---|---|
| `PENDING → ACTIVE` | scheduler | `apps/backend/http-api/src/api/v2/runs/scheduler.py` |
| `ACTIVE → COMPLETED|FAILED` (test results) | runner POST → reporter handler | `apps/backend/http-api/src/api/v2/runs/reporter.py` |
| `ACTIVE → FAILED` (timeout) | watchdog tick in scheduler | same scheduler.py — checks `VALIDATION_TIMEOUT_MINUTES` |
| `ACTIVE → CANCELLED` | user-initiated | `apps/backend/http-api/src/api/v2/runs/runs.py:cancel_run` |

## Where the code lives

| Concern | Path |
|---|---|
| HTTP handlers | `apps/backend/http-api/src/api/v2/runs/` (trigger, scheduler, reporter, queue, ws, executions) |
| Runner pod deployment | `apps/backend/http-api/src/services/kubernetes/jobs.py`, `runner_env.py` |
| Test package upload + manifest parsing | `apps/backend/http-api/src/api/v2/products/test_packages*.py` |
| Validation test suites (per product) | `apps/validation/<product>/` — submodule per product. Validation runners pull from these. |
| MTIB gRPC client (Python) | `libs/python/corekinect/mtib/` — wraps `libs/protocols/mtib/mtib.proto`. |
| WebSocket updates | `apps/backend/http-api/src/api/v2/runs/ws.py` — emits `run.update`, `execution.update` events on the SocketIO `/notifications` namespace. |
| Frontend list/detail | `apps/frontend/app/src/routes/runs/`, `apps/frontend/app/src/routes/validation/` |
| Prisma models | `prisma/schema.prisma:1435-1589` |

## Key invariants

- **A `TestRun` has exactly one `Fixture`.** Set at creation, immutable. Cancelling and re-running creates a new TestRun.
- **`TestExecution` is unique per (target, executionIndex) AND per (target, name).** Enforced at the DB level (`@@unique([targetId, executionIndex])`, `@@unique([targetId, name])`). A reporter regression that dropped slotIndex once duplicated rows silently; the constraint surfaces it as a 409 now.
- **`MOTION_ENABLED` is derived from fixture type.** The MTIB pod env is set by http-api's `_mtib_env_for_fixture(fixture)` (`apps/backend/http-api/src/api/v2/fixtures/fixtures.py:1129`). Validation fixtures get `MOTION_ENABLED=true`, manufacturing fixtures get `false`. Never override per pod.
- **Fixture purpose gates test package status.** `FixturePurpose.RELEASE` fixtures only accept `TestPackageStatus.RELEASED` packages. `FixturePurpose.DEV` accepts `DEVELOPMENT` and `RELEASED`. Enforced when creating the TestRun.
- **AssetSet promotion is validation-only.** A successful manufacturing run does **not** flip `AssetSet.status → VALIDATED`. Only validation runs do. Manufacturing assumes the firmware is already validated.
- **`runnerLastHeartbeat` is the liveness signal.** The runner pod posts every 30s. If `now - lastHeartbeat > 3 * heartbeat_interval`, the scheduler kills the runner and marks the run `FAILED`.

## Validation stages

A product's validation flow has up to five named stages, configured per-product in `ProductStageConfig`:

| Stage | Purpose |
|---|---|
| 1 | Smoke — quick post-build sanity, runs on every commit |
| 2 | Regression — broader coverage, runs on PRs |
| 3 | Performance — measurements, motion-driven, slower |
| 4 | Hardware matrix — runs the stage-4 build matrix across labelled targets |
| 5 | Release qualification — released packages only |

A `BuildRun` may target a specific stage (`BuildRun.stage`). The stage's `ProductStageConfig` points at the released test package version that's "blessed" for that stage. Dev fixtures with a `DEVELOPMENT` package can run any stage; release fixtures only run their blessed version.

## How to extend

### Adding a new stage type to a product

1. Add a `ProductStageConfig` row via `POST /v2/products/<id>/stages` (handler at `apps/backend/http-api/src/api/v2/builds/stage_config.py`).
2. Set `releasedTestPackageId` to the package version that should run for that stage.
3. Update the product's validation submodule (`apps/validation/<product>/`) with the actual test code under the matching directory.

### Adding a new MTIB capability used by validation

1. Add the gRPC RPC to `libs/protocols/mtib/mtib.proto`.
2. Implement on the edge server (`apps/edge/mtib-server/`).
3. Wrap in the Python client (`libs/python/corekinect/mtib/`).
4. Call from the validation test suite (`apps/validation/<product>/tests/`).
5. Update `.claude/knowledge/libs/protocols.md` and `.claude/knowledge/apps/edge/mtib-server.md`.

### Adding a per-execution measurement

The `TestExecution.measurements` JSON blob is freeform — any structured data the test wants to capture. The frontend rendering at `apps/frontend/app/src/routes/runs/[id]/+page.svelte` introspects known keys but tolerates unknown ones.

## Common failure modes

**Runner deploys but never sends a heartbeat** — image pull failure or the runner can't reach the http-api. `kubectl describe pod <runner-pod>`; usual culprits are an expired registry CA cert or a NetworkPolicy that blocks the runner from `concord-http-api`.

**Test passes locally but fails on the fixture with no useful log** — the MTIB UART buffer overflowed and dropped the failure window. Check `UART_*` measurements in `TestExecution.measurements`; if `dropped_bytes > 0`, raise the buffer in the fixture's profile.

**Run stuck at `ACTIVE` with `completedCount = 0`** — runner crashed before posting any result. Pod logs (`kubectl logs job/<job-name>`) usually show a Python traceback from test discovery. Most often: the test package's `concord.yaml` doesn't match the framework version. Re-upload the package against the right `frameworkVersion`.

**`TestExecution` 409 conflict** — the reporter sent the same execution twice. This is the schema invariant catching a bug. Usually a stage-rerun without clearing the prior executions; check the reporter logs for the trace.

**Motion test silently no-ops** — `MOTION_ENABLED=false` on the MTIB pod. The fixture type was wrong at deploy time. Redeploy the MTIB with `nx update mtib-deployment` (the env is computed from `fixture.type` at deploy time).

**Stage-4 matrix only runs 4 jobs instead of 8** — `BuildRun.matrixMode` is `legacy` not `stage4`. The frontend's "Run Stage 4" button must set `matrixMode=stage4` and populate `buildMatrix`. Check `BuildRun.matrixMode` directly.

## Related knowledge

- [`builds.md`](builds.md) — BuildRun/AssetSet that drives a validation run
- [`manufacturing.md`](manufacturing.md) — same TestRun/RunTarget/TestExecution hierarchy, different lifecycle
- [`fixtures.md`](fixtures.md) — Fixture, FixtureSlot, TestBedDesign, FixturePurpose
- [`products.md`](products.md) — Product, ProductVariant, TestPackage status flow
- [`../apps/backend/http-api.md`](../apps/backend/http-api.md) — runs handler internals
- [`../apps/edge/mtib-server.md`](../apps/edge/mtib-server.md) — gRPC API the runner drives
- [`../libs/protocols.md`](../libs/protocols.md) — the MTIB protobuf
- [`../prisma/schema-overview.md`](../prisma/schema-overview.md) — full data model
