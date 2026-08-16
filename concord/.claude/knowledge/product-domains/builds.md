# Builds — knowledge

The builds domain models firmware compilation: how a git commit or manual trigger becomes signed, versioned binaries stored in MinIO and ready for validation or manufacturing. Centered on two entities — **BuildRun** (the batch) and **BuildJob** (the individual compilation) — plus their artifacts and the cache that prevents re-doing identical work.

Refresh this file when: a new `BuildJobStatus` or `BuildRunStatus` value is added, the build-service worker loop changes its claim/heartbeat protocol, the artifact storage path changes, a new trigger source is added, or the matrix-mode definitions change.

## Entities

| Model | Role |
|---|---|
| `BuildRun` | A batch triggered by one event (commit, PR webhook, manual click). Tracks aggregate status across N child jobs. |
| `BuildJob` | A single firmware compilation. Owned by the build-service worker. |
| `BuildArtifact` | A produced file (hex, bin, elf, manifest, log) bound to a `BuildJob`, stored in MinIO. |
| `AssetSet` | The promoted output of a successful `BuildRun` — the input that validation/manufacturing actually consume. 1:1 with `BuildRun` when source=`BUILD_SERVICE`. |
| `Asset` | A single binary within an `AssetSet`, role-tagged (`app`, `comms`, `modem`). |
| `FirmwareSet` | Higher-level grouping for releases — a versioned bundle (e.g. "Alpha B0 v0.5.2-BM") spanning multiple builds. Pre-AssetSet model; still used for release tracking. |
| `RecipeVersion` | The build recipe pinned to a BuildRun/BuildJob — captures overlay flags, signing keys, post-build steps. |

The schema authority is `prisma/schema.prisma:575-721` (BuildRun, BuildJob, BuildArtifact) and `:1277-1341` (AssetSet, Asset).

## Lifecycle

### BuildRun

```
PENDING ──► BUILDING ──► VALIDATING ──► SUCCESS
              │             │
              │             └──► FAILED
              └──► BUILD_FAILED
              └──► CANCELLED  (from any non-terminal state)
```

- `PENDING` — created. No child job has claimed yet.
- `BUILDING` — at least one child `BuildJob` flipped to `CLONING` or `BUILDING`. Promotion happens in the `PATCH /v2/builds/<id>` handler (`apps/backend/http-api/src/api/v2/builds/builds.py`) when a worker claims the first job.
- `BUILD_FAILED` — any child `BuildJob` ended `FAILED`. The whole run fails fast unless explicitly told otherwise.
- `VALIDATING` — all `expectedBuilds` succeeded and `autoRunStage=true` triggered a validation `TestRun`.
- `SUCCESS` — all expected builds done, validation (if requested) passed.
- `FAILED` — validation explicitly failed.
- `CANCELLED` — user cancelled, or the parent PR/branch went away.

### BuildJob

```
QUEUED ──► CLONING ──► BUILDING ──► SUCCESS
   │                                  │
   │                                  └──► (eventually rolls up to BuildRun)
   ├──► BLOCKED   (waiting for a base build to finish — version-bump jobs)
   ├──► CACHED    (fingerprint matched a prior SUCCESS — reused artifacts)
   ├──► FAILED    (clone/build/upload failed; errorMessage populated)
   └──► CANCELLED (parent cancelled or worker timed out)
```

Transitions are owned by `build-service`. The worker loop:

1. Polls `GET /v2/builds?status=QUEUED&limit=20` every `SCHEDULER_INTERVAL_S` (default 15s) — see `apps/backend/build-service/src/worker/loop.py:69`.
2. Claims atomically by `PATCH /v2/builds/<id>` with `{status: "CLONING", workerId, startedAt}`. The http-api's `update_build` handler (`builds.py:422`) only accepts the transition from `QUEUED` — concurrent claims get `409 conflict`.
3. Streams updates: `CLONING → BUILDING → SUCCESS|FAILED`. Each transition is a PATCH; the worker also updates `lastHeartbeat` periodically so the scheduler can detect stale workers.
4. Uploads artifacts via `POST /v2/builds/<id>/artifacts` (`builds.py:603`). Each upload writes a `BuildArtifact` row pointing at a MinIO key under `firmware/<product-slug>/<build-id>/<artifact-name>`.

### AssetSet promotion

On `BuildRun` SUCCESS with all child jobs `SUCCESS|CACHED`, the http-api promotes the run's artifacts into an `AssetSet`:

```
PENDING ──► COMPLETE ──► VALIDATED
              │
              └──► FAILED
```

- `PENDING` — created during the build run, no artifacts yet.
- `COMPLETE` — all expected `Asset` rows present.
- `VALIDATED` — a successful validation `TestRun` referenced this AssetSet. Promotion gates real "this is shippable" status.

The 1:1 `AssetSet.buildRunId @unique` constraint means each successful build run has at most one canonical asset set. Other sources (`MANUAL_UPLOAD`, `EXTERNAL_CI`) bypass build-service entirely.

## Where the code lives

| Concern | Path |
|---|---|
| BuildRun + BuildJob HTTP handlers | `apps/backend/http-api/src/api/v2/builds/` (`builds.py`, `build_runs.py`, `webhook.py`, `pr_builds.py`, `stage_trigger.py`) |
| Build cache (fingerprint → reuse) | `apps/backend/http-api/src/api/v2/builds/build_cache.py` |
| Build-service worker loop | `apps/backend/build-service/src/worker/loop.py` |
| Pipeline stages (clone → recipe → sign → build → artifacts) | `apps/backend/build-service/src/worker/pipeline/` |
| Bitbucket polling → BuildRun creation | `apps/backend/git-poller/src/` |
| Frontend list/detail views | `apps/frontend/app/src/routes/builds/`, `apps/frontend/app/src/routes/build-runs/` |
| Prisma models | `prisma/schema.prisma:575-721`, `:1277-1341` |
| Storage | MinIO bucket `firmware`. Key pattern `firmware/<product>/<build-id>/<artifact>`. |

## Key invariants

- **BuildJob.status only moves forward.** Once `SUCCESS|FAILED|CACHED|CANCELLED`, transitions are rejected at the API. The single legitimate "reset" path is `POST /v2/builds/<id>/reset` (`builds.py:556`), which creates a fresh job; it does not overwrite the old row.
- **Atomic claim.** A worker that loses the claim race (the row was already `CLONING`) must accept `409 conflict` and try the next QUEUED job. Never patch back to `QUEUED`.
- **Artifacts are immutable.** Once a `BuildArtifact` row is committed, its storage key is permanent. Re-uploading is an error — bump the version or create a new BuildJob.
- **BuildRun progress is derived.** `BuildRun.completedBuilds` and `BuildRun.status` are computed from the child jobs by the http-api when any child job updates. Don't update them directly.
- **AssetSet uniqueness.** `@@unique([productId, version, type])` on TestPackage and the implicit single-source on `AssetSet.buildRunId` mean each (product, version, source) combination has exactly one asset set.
- **Trigger types.** `BuildRun.triggerType` is one of `manual`, `webhook`, `scheduled`. Webhook also populates `triggerData` with the Bitbucket payload and promotes PR fields (`prNumber`, `prTitle`, `prAuthor`, `sourceBranch`, `targetBranch`, `prUrl`) for indexing.

## Build matrix modes

`BuildRun.matrixMode` controls how many child jobs get created:

| Mode | Jobs | When |
|---|---|---|
| `legacy` | 4 (one per `FirmwareVariant`: smoke/debug/release/mfg) | Default for plain commits |
| `stage4` | 8 (mainRef × {mfg, fut} × {debug, release} × {a, b} replicas) | PR-driven validation stage 4 |

Stage-4 matrix configuration lives in `BuildRun.buildMatrix` JSON: `{mode, labels, mainRef, prRef}`. Each child job gets a `matrixLabel` (`mfg_base`, `fut_debug_a`, etc.) and `matrixIndex` (0-7) so the validator can wire them to the right test slots.

## Build cache

When a job lands, the http-api computes `buildFingerprint = SHA-256(repo + commitSha + board + variant + configFlags)`. If a prior `BuildJob` with the same fingerprint succeeded:

- New job goes to `CACHED`, never claims a worker, never burns CI minutes.
- `BuildJob.reusedFromId` points at the original successful job.
- Artifacts are referenced (not copied) — the storage keys resolve to the original AssetSet.

Stage-4 version-bump jobs (`versionBump=true`) intentionally rebuild with the same source but bumped version — they reference a base job via `baseJobId` and stay `BLOCKED` until the base completes.

## How to extend

### Adding a new trigger source

1. Wire the source to call `POST /v2/builds/runs` with a `triggerType` value (currently `manual | webhook | scheduled`).
2. Add the new string to the allowed set in `apps/backend/http-api/src/api/v2/builds/build_runs.py`.
3. Update `_serialize_build_run` if you want frontend filtering.
4. Update this knowledge file's trigger-types row above.

### Adding a new BuildJobStatus

1. Add to the enum in `prisma/schema.prisma` + migration + python client regen.
2. Add the same value to `apps/frontend/app/src/lib/types/models.ts`.
3. Audit every transition in `apps/backend/http-api/src/api/v2/builds/builds.py:update_build` — the allowed-transition table is hand-written there.
4. Update frontend status pills (`apps/frontend/app/src/lib/components/StatusPill.svelte`).
5. Update `.claude/knowledge/prisma/enums.md`.

### Adding a new artifact type

1. Add to the allowed `artifactType` values in `apps/backend/http-api/src/api/v2/builds/builds.py:_serialize_build_artifact`.
2. Update the build-service pipeline to emit it (`apps/backend/build-service/src/worker/pipeline/`).
3. Update any downstream consumer (validation runner, manufacturing runner) to recognize the new type.

## Common failure modes

**Build stuck at `QUEUED` for >5 minutes** — no worker matches. Inspect `kubectl -n <env> logs deploy/concord-build-service`. Usually `BITBUCKET_SSH_KEY` is empty or the worker filters by an NCS version that no live worker advertises.

**Build flips to `CLONING` and stays there** — worker died mid-clone. `lastHeartbeat` will be stale (>5 min). The scheduler reaper transitions the row back to `FAILED` with `errorMessage="worker timed out"`. Trigger a `reset` from the UI to retry.

**`409 conflict` claiming a build** — another worker won the race. Expected behavior. The losing worker should move on; it is not an error worth logging.

**Stale `CACHED` artifacts** — fingerprint matched but the cached build was tagged with an obsolete recipe. Audit: did the recipe (`RecipeVersion`) actually get pinned into the fingerprint? Recipe-flag changes that don't surface in `configFlags` are the usual source.

**AssetSet stuck at `COMPLETE`, never `VALIDATED`** — the BuildRun never triggered a validation TestRun (`autoRunStage=false`), or the validation run failed. AssetSets only flip to `VALIDATED` when a *validation* TestRun succeeds against them. Manufacturing runs don't promote.

**Artifact upload fails with MinIO 403** — `STORAGE_ACCESS_KEY` / `STORAGE_SECRET_ACCESS_KEY` drift between http-api and build-service. They must match the live MinIO root password. Rolling-restart both after a credential rotation.

## Related knowledge

- [`products.md`](products.md) — Product, ProductVariant (board revision), Codebase, TestPackage flow
- [`validation.md`](validation.md) — what consumes an AssetSet once validated
- [`manufacturing.md`](manufacturing.md) — manufacturing sessions reference the same AssetSets
- [`../apps/backend/http-api.md`](../apps/backend/http-api.md) — request lifecycle for build endpoints
- [`../apps/backend/build-service.md`](../apps/backend/build-service.md) — worker pipeline internals
- [`../apps/backend/git-poller.md`](../apps/backend/git-poller.md) — Bitbucket → BuildRun trigger
- [`../prisma/schema-overview.md`](../prisma/schema-overview.md) — full data model
