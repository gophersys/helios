# build-service — knowledge

The firmware build worker. Single-process Python service that pulls QUEUED `BuildJob` rows off the HTTP API, clones the product's firmware repo over SSH, compiles inside a per-product Docker container (nRF Connect SDK / Zephyr), signs the resulting image with the appropriate MCUboot key, and uploads the artifacts back through the HTTP API. Its only responsibility is producing signed firmware binaries from a Git revision plus a build recipe. Everything outside that — scheduling, persistence, queueing semantics — belongs to the HTTP API.

Refresh this file when: a new pipeline stage is added under `src/worker/stages/`, the worker's push/poll delivery shape changes, the Docker runner contract changes (image resolution, volumes, network), the signing-key plumbing changes, a new env var is added to `BuildServiceConfig`, or the small Flask management API gains/loses an endpoint.

## Location

- Code: `apps/backend/build-service/`
- Entry point: `src/main.py`
- Tests: `tests/` (suite per stage under `tests/stages/`, plus end-to-end loop/runner tests)
- Container: `deploy/Dockerfile`
- Config: `src/config.py` (`BuildServiceConfig` extends `corekinect.utils.EnvConfig`)

## Responsibilities

Owns:

- The build worker loop (`src/worker/loop.py`) — claim → process → finalize.
- The build pipeline (`src/worker/pipeline.py`) and its stages: Clone → Recipe → Signing → Build → Artifacts.
- The Docker build runner (`src/worker/docker_runner.py`) — image pull/run, volume + network management, orphan-container cleanup.
- SSH-key materialisation (decode `BITBUCKET_SSH_KEY` → file at `SSH_KEY_PATH`).
- Signing-key materialisation per release track (bench / engineering / production).
- A small Flask management API on `BUILD_SERVICE_PORT` (default 9002) for push-job delivery, health, queue depth, and worker state.

Does not own:

- Job scheduling or concurrency limits (HTTP API's `queue_scheduler` enforces `MAX_CONCURRENT_BUILDS`).
- Persistence — all state changes go through the HTTP API (`PATCH /v2/builds/<id>`).
- BuildRun creation — that happens in HTTP API when the git-poller or webhook fires a `RepoEvent`.
- Artifact storage — the HTTP API owns MinIO; the worker uploads via presigned URLs returned from the API.
- Local Prisma access (intentionally dropped — the in-memory `WorkerState` replaced a broken local DB).

## Internal structure

```
apps/backend/build-service/
├── src/
│   ├── main.py                  # Entry: banner, SSH key, Flask thread, signal handlers,
│   │                            #   worker loop
│   ├── app.py                   # Flask app factory; registers health/workers/queue/
│   │                            #   metrics/jobs blueprints
│   ├── config.py                # BuildServiceConfig — env-var schema and property aliases
│   ├── clients/
│   │   └── concord.py           # ConcordClient — GET/POST/PATCH/DELETE wrapper with
│   │                            #   ApiKey auth and verify=False (self-signed certs)
│   ├── api/
│   │   ├── health.py            # /health
│   │   ├── workers.py           # /workers — state + active job
│   │   ├── queue.py             # /queue  — JobQueue depth and seen-set
│   │   ├── metrics.py           # /metrics (Prometheus)
│   │   └── jobs.py              # /jobs/notify (push delivery) + /jobs/cancel
│   └── worker/
│       ├── loop.py              # BuildWorkerLoop — push+poll loop, claim_job, update_job
│       ├── queue.py             # JobQueue — in-process priority queue with dedup
│       ├── state.py             # WorkerState — in-memory worker status (busy / current job)
│       ├── executor.py          # BuildJob dataclass + version-override extraction
│       ├── pipeline.py          # BuildPipeline + BuildContext + Stage protocol +
│       │                        #   StageResult
│       ├── docker_runner.py     # DockerBuildRunner — image management, run, cleanup
│       ├── git_ops.py           # GitOps — SSH clone, build-script + overlay fetch
│       └── stages/
│           ├── clone.py         # CloneStage     — repo + secondary repo checkout
│           ├── recipe.py        # RecipeStage    — fetch + render recipe to disk
│           ├── signing.py       # SigningStage   — deploy signing key for release track
│           ├── build.py         # BuildStage     — invoke build script inside container
│           └── artifacts.py     # ArtifactStage  — collect + upload outputs
└── tests/
    ├── conftest.py
    ├── stages/                  # one test file per stage
    └── test_*.py                # loop, queue, state, docker_runner, executor,
                                 #   flask_endpoints, drain, orphan_cleanup, manifest, ...
```

## Key patterns

### Main loop

`BuildWorkerLoop.run()` in `src/worker/loop.py`:

1. **Delivery**: if a `JobQueue` is wired (push mode), call `job_queue.dequeue(timeout=poll_interval)` and treat a notified ID as the next candidate. On timeout, fall back to `fetch_queued_job()` which does `GET /v2/builds?status=QUEUED&limit=20` and takes the first item. If no queue is wired (legacy poll-only mode), only the polling path runs.
2. **Claim**: `PATCH /v2/builds/<id>` with `{status: CLONING, workerId, startedAt}`. If the response carries `errors` or 4xx, the job was taken by another worker — skip.
3. **Process**: build a `BuildContext` rooted at `<workspace>/<job_id>/` and run `BuildPipeline` with stages `[CloneStage, RecipeStage, SigningStage, BuildStage, ArtifactStage]`.
4. **Finalize**: pipeline reports terminal status (`SUCCESS` / `FAILED`) via `update_job(...)` which `PATCH`es the same endpoint with `finishedAt`, `durationSeconds`, and any `errorMessage` (truncated to 2000 chars). On success, also `versionString`.
5. **Clear seen** on `JobQueue` so the same ID can be re-delivered if it re-enters QUEUED.

On any exception the loop logs and waits 5 s before retrying — no exponential backoff, by design (the loop should keep trying; transient API outages shouldn't wedge the worker).

### Pipeline stages

Each stage implements the `Stage` protocol in `src/worker/pipeline.py`:

```python
class Stage(Protocol):
    name: str
    def execute(self, ctx: BuildContext) -> StageResult: ...
```

`BuildContext` is mutable and threaded through every stage — earlier stages populate fields (`primary_dir`, `recipe_path`, `builder_image`, `version_string`, `artifacts`) for later stages to consume. On `StageResult.fail(...)` the pipeline stops, reports the error via `update_job(status=FAILED, error=...)`, and the workspace is removed.

To add a new stage, add a file under `src/worker/stages/`, write a class with `name` and `execute(ctx)`, then insert it into the `stages=[...]` list in `BuildWorkerLoop.process_job`.

### Docker runner

`DockerBuildRunner` (in `src/worker/docker_runner.py`) is the executor when `BUILDER_MODE=docker` (default). It resolves the builder image per product (devcontainer-based) with `DEFAULT_BUILDER_IMAGE` (`containers.ad.corekinect.com/ncs-fw-dev:2.7.0`) as the fallback. Workspace and ccache directories can be backed by named volumes (`WORKSPACE_VOLUME`, `CCACHE_VOLUME`); network is set by `BUILDER_NETWORK` (default `host`). Each container has a hard timeout of `BUILDER_TIMEOUT` seconds (default 1800).

`DockerBuildRunner.cleanup_orphaned_containers()` runs at process start to kill any builder containers left over from a previous instance (typical after a rolling update mid-build). `worker.docker_runner.cleanup()` runs in the `finally` of the worker loop only on abnormal exit — the normal-exit path lets the current build finish.

### SSH key

`_setup_ssh_key()` in `src/main.py` handles two cases. In K8s the SSH key is volume-mounted at `SSH_KEY_PATH` from a `Secret` — the file (or its parent directory) already exists and the function logs and returns. In docker-compose / local the key is decoded from base64 `BITBUCKET_SSH_KEY` to `SSH_KEY_PATH` with mode `0600`. If neither path applies, the worker logs a warning and clones will fail.

### Signing keys

`BuildServiceConfig.signing_key_for_track(track)` maps `bench | engineering | production` to the matching base64-encoded private key env var (`BENCH_SIGNING_KEY`, `ENGINEERING_SIGNING_KEY`, `PRODUCTION_SIGNING_KEY`). `SigningStage` materialises the key file inside the build container for the duration of one job.

### Push delivery + fallback poll

The HTTP API's `services/builds/notifier.py` POSTs `{jobId, priority}` to `<BUILD_SERVICE_URL>/jobs/notify`. The endpoint (`src/api/jobs.py`) returns `202 Accepted` and pushes the ID onto the in-process `JobQueue` (`src/worker/queue.py`). The worker loop's `dequeue(timeout=POLL_INTERVAL)` reacts in milliseconds; if the push was dropped (network, build-service down), the same loop's fallback polling path picks it up within `POLL_INTERVAL` seconds (default 60).

The `JobQueue` has its own dedup (`_seen` set) so a re-enqueued ID does not run twice while one is in flight. `clear_seen(job_id)` runs after the pipeline finishes.

### Management API

Flask + `waitress` on `BUILD_SERVICE_PORT` (default 9002), started in a daemon thread before the worker loop blocks:

| Endpoint | Purpose |
|---|---|
| `GET /health` | Liveness probe |
| `GET /workers` | Current worker state (`worker_id`, `is_busy`, `current_job_id`, `current_product`) |
| `GET /queue` | Job queue depth + `_seen` set |
| `GET /metrics` | Prometheus exposition (when `METRICS_ENABLED=true`) |
| `POST /jobs/notify` | Push-job notification from HTTP API |
| `POST /jobs/cancel` | Real cancellation. Body: `{"reason": "<text>"}` (optional, capped at 64 chars, default `"user"`). Flips `WorkerState.cancel_event`; the subprocess streaming loop in both `executor.py` and `docker_runner.py` checks the event on every line and tears the build down. Returns 200 with `no_active_build` if idle, 202 with `cancel_requested` if a job is running. The pipeline then patches the job status to `CANCELLED` (not `FAILED`) via `_report_failure`. |

### Cancellation mechanics

`WorkerState.cancel_event` (a `threading.Event`) is the single cancellation primitive. Flow:

1. `POST /jobs/cancel` (Flask thread) → `state.request_cancel(reason)` → `cancel_event.set()`.
2. The build subprocess streaming loops in `executor.py` and `docker_runner.py` check `ws.cancel_event.is_set()` before each `stdout.readline()`. On set:
   - **local subprocess** (`executor.py`): `process.terminate()` (SIGTERM) → `wait(timeout=5)` → `process.kill()` (SIGKILL) if still alive → return `(False, "...\n[CANCELLED]")`.
   - **docker container** (`docker_runner.py`): `_kill_container(container_name)` (`docker kill <name>`) → `process.kill()` on the host `docker run` process → return `(False, "...\n[CANCELLED]")`.
3. `pipeline._report_failure` detects `cancel_event.is_set()` and patches the job as `status=CANCELLED` (not `FAILED`), with `errorMessage = "Build cancelled by <reason>"`.
4. `state.finish_job(False)` then counts the outcome into `jobs_cancelled` (separate from `jobs_failed`).
5. The next `state.start_job(...)` calls `clear_cancel()` so a fresh job never inherits the previous job's signal.

Cancellation is best-effort. Latency between the flip and the kill is bounded by the time until the next stdout line (typically <1s on a healthy build, longer if the build is wedged silently). Cancellation does not abort a stage transition that's already running — only the build subprocess itself.

## External dependencies

| Dep | Env var(s) | Notes |
|---|---|---|
| HTTP API | `CONCORD_API_URL`, `CONCORD_API_KEY` | All state goes through `ConcordClient` with `Authorization: ApiKey <key>`. TLS verification is disabled (`verify=False`) for self-signed dev/staging certs. |
| Bitbucket Cloud (SSH) | `BITBUCKET_SSH_KEY`, `SSH_KEY_PATH` | SSH-only — the worker does not talk to the Bitbucket REST API directly; the HTTP API mediates anything that needs a token |
| Docker daemon | `DOCKER_SOCKET` (default `/var/run/docker.sock`), `BUILDER_MODE` (`docker` or `local`) | The pod mounts the host docker socket in K8s; in compose the socket is shared |
| Builder image | `DEFAULT_BUILDER_IMAGE`, per-product `builderImage` from the `Product` model | Pulled on first use; cached by Docker |
| Workspace + ccache | `WORKSPACE_DIR`, `WORKSPACE_VOLUME`, `CCACHE_VOLUME` | `WORKSPACE_DIR` is the host-side root; the named volumes (when set) are mounted into the build container |
| Signing keys | `BENCH_SIGNING_KEY`, `ENGINEERING_SIGNING_KEY`, `PRODUCTION_SIGNING_KEY` | Base64-encoded MCUboot private keys, one per release track |

Credentials and secret rotation — see [`../../deploy/secrets.md`](../../deploy/secrets.md). All env values must exist in `deploy/development/docker-compose.yaml`, `deploy/production/helm/values-staging.yaml`, and `deploy/production/helm/values-production.yaml` (see [`../../../rules/all-three-envs.md`](../../../rules/all-three-envs.md)).

## How to add common things

### Add a new firmware variant

A "variant" is a `FirmwareVariant` enum value (`smoke | debug | release | mfg`) consumed by `BuildStage`. The worker does not own the enum — adding a new one means:

1. Add the value to the Prisma enum (`prisma/schema.prisma` → `FirmwareVariant`), generate the client, mirror the Python schema and the frontend types. See [`../../../rules/prisma-flow.md`](../../../rules/prisma-flow.md).
2. Update the relevant product recipe(s) and build scripts to honour the variant flag (compiler flags, optimisation level).
3. If the variant changes the build script invocation, update `src/worker/stages/build.py` and the per-stage tests under `tests/stages/test_build.py`.
4. Update [`../../product-domains/builds.md`](../../product-domains/builds.md).

### Tune build concurrency

Concurrency is enforced upstream in the HTTP API's `queue_scheduler`. The worker honours it implicitly by only claiming when notified or when fewer than the cap are `BUILDING`/`CLONING`. To raise the cap:

1. Bump `MAX_CONCURRENT_BUILDS` on the HTTP API (env var → `config/env.py`).
2. Scale the build-service Deployment replicas (`deploy/production/helm/values-{staging,production}.yaml`) — one worker = one concurrent build.
3. Verify the cluster has enough capacity. Each builder container is heavy (nRF Connect SDK ≈ multi-GB).

### Add a new pipeline stage

1. Add `src/worker/stages/<name>.py` exporting a class with `name: str` and `execute(ctx: BuildContext) -> StageResult`.
2. Add it to the `stages=[...]` list in `BuildWorkerLoop.process_job` in the right position.
3. Add the new context fields it writes to `BuildContext` (in `src/worker/pipeline.py`).
4. Write `tests/stages/test_<name>.py` mirroring the existing ones.

### Add a new env var

1. Add the field to `BuildServiceConfig` in `src/config.py` with a default; add the `@property` alias.
2. Update `deploy/development/docker-compose.yaml`, `values-staging.yaml`, `values-production.yaml` (see [`../../../rules/all-three-envs.md`](../../../rules/all-three-envs.md)).
3. If the var is a secret, add to the K8s `Secret` manifest plumbing and to [`../../deploy/secrets.md`](../../deploy/secrets.md).

## Common failure modes

- **`git clone` fails with permission denied.** SSH key not materialised — check the startup logs for `SSH key written to ...` or `volume mount`. In K8s the `Secret` projection can be slow; the code waits but emits a warning if neither the file nor the parent mount is present. Confirm the `Secret` is bound and the `subPath` mount is correct.
- **Build claimed but never finishes.** Worker died mid-build (pod OOM, host kernel kill, rolling update). The HTTP API's `build-recovery` scheduler (runs every 60 s) detects stale `BUILDING`/`CLONING` rows via heartbeat or `startedAt` timeout and resets them to `QUEUED`. Look for the `Build recovery` log line in the HTTP API.
- **Orphan builder containers on host.** A previous worker exited abnormally before its `cleanup()` could run. `DockerBuildRunner.cleanup_orphaned_containers()` runs at startup precisely for this case — if you still see them, the label filter in that function may not match. Inspect with `docker ps -a --filter label=concord.build-service=true`.
- **Push notifications never arrive.** Either `BUILD_SERVICE_URL` is unset on the HTTP API side (check `kubectl -n <env> get deploy concord-http-api -o yaml | grep BUILD_SERVICE_URL`) or the Service / DNS isn't reachable from the API pod. Worker still picks jobs up via fallback polling within `POLL_INTERVAL` seconds — observe latency to confirm.
- **`Failed to fetch repo configs from API` in `git_ops.py`.** The worker calls `GET /v2/builds/settings/repos` once at startup. If the HTTP API is not ready yet (init container still running migrations) the call fails. The worker retries on each job; check that the API's `/ready` probe is green.
- **Signing failures on a release track.** `signing_key_for_track(track)` returns the empty string when the env var is missing. `SigningStage` will then fail clearly. Verify the correct `<TRACK>_SIGNING_KEY` is present in the K8s `Secret` for the deployed environment.

## Related knowledge

- [`../../architecture.md`](../../architecture.md) — where build-service sits in the system.
- [`../../glossary.md`](../../glossary.md) — `BuildRun`, `BuildJob`, `FirmwareVariant`, `ReleaseTrack`, `Codebase`.
- [`http-api.md`](http-api.md) — the API this worker talks to; see "How to add common things → Add a v2 endpoint" if you need a new HTTP surface for the worker.
- [`git-poller.md`](git-poller.md) — the upstream watcher that produces the `RepoEvent` rows that turn into BuildJobs.
- [`../../product-domains/builds.md`](../../product-domains/builds.md) — the full builds product domain.
- [`../../deploy/secrets.md`](../../deploy/secrets.md) — credentials for SSH, API key, signing keys.
- [`../../libs/python-corekinect.md`](../../libs/python-corekinect.md) — `EnvConfig`, `Logger`, `print_banner` used here.
- [`../../../rules/all-three-envs.md`](../../../rules/all-three-envs.md), [`../../../rules/nx-only.md`](../../../rules/nx-only.md).
