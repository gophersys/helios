# Build Service Architecture

**Last reviewed:** 2026-04-07
**Status:** Active

> Standalone firmware build worker. Receives jobs from the HTTP-API via push
> notification, executes builds inside Docker containers, uploads artifacts
> to MinIO via the API. Survives rolling updates without losing in-progress builds.

---

## 1. Design Principles

1. **Standalone** — No local database. The HTTP-API owns all state (PostgreSQL).
   The build service is a stateless worker with in-memory tracking only.
2. **Push-based delivery** — The API notifies the build service when a job is
   queued (POST `/jobs/notify`). A 60-second fallback poll catches missed
   notifications. No polling loop hammering the API.
3. **Pipeline architecture** — Each build flows through 5 independently testable
   stages: Clone → Recipe → Signing → Build → Artifacts.
4. **Graceful lifecycle** — PreStop drain hook finishes in-progress builds before
   shutdown. Heartbeat-based recovery detects dead workers.
5. **Docker sibling containers** — Builds run in sibling Docker containers via
   the host Docker socket (not nested DinD). Workspace shared via hostPath volumes.

---

## 2. Repository Layout

```
apps/backend/build-service/
├── src/
│   ├── main.py                    # Entrypoint: Flask API + worker loop
│   ├── config.py                  # EnvConfig (no DB URL)
│   ├── api/
│   │   ├── app.py                 # Flask app factory
│   │   ├── health.py              # GET /health, GET /ready, POST /drain
│   │   ├── jobs.py                # POST /jobs/notify, POST /jobs/cancel
│   │   ├── queue.py               # GET /queue (depth + seen count)
│   │   ├── workers.py             # GET /workers (WorkerState JSON)
│   │   └── metrics.py             # GET /metrics (Prometheus format)
│   ├── worker/
│   │   ├── loop.py                # Main worker loop (push + poll hybrid)
│   │   ├── pipeline.py            # BuildPipeline orchestrator
│   │   ├── state.py               # WorkerState in-memory dataclass
│   │   ├── queue.py               # JobQueue (thread-safe priority queue)
│   │   ├── docker_runner.py       # Docker container lifecycle + devcontainer
│   │   ├── executor.py            # BuildExecutor (streaming Docker exec)
│   │   ├── git_ops.py             # Git clone + checkout
│   │   └── stages/
│   │       ├── clone.py           # CloneStage — git clone + SDK copy
│   │       ├── recipe.py          # RecipeStage — resolve build script
│   │       ├── signing.py         # SigningStage — deploy signing keys
│   │       ├── build.py           # BuildStage — Docker exec + version extraction
│   │       └── artifacts.py       # ArtifactStage — collect + upload artifacts
│   └── clients/
│       └── concord.py             # HTTP client for Concord API
├── tests/                         # 233 tests
└── deploy/
    └── Dockerfile
```

---

## 3. Pipeline Architecture

Every build flows through a `BuildPipeline` with a shared `BuildContext`:

```
BuildContext (mutable state bag)
    │
    ▼
┌─────────┐    ┌────────┐    ┌─────────┐    ┌───────┐    ┌───────────┐
│  Clone   │───▶│ Recipe │───▶│ Signing │───▶│ Build │───▶│ Artifacts │
└─────────┘    └────────┘    └─────────┘    └───────┘    └───────────┘
    │               │             │              │              │
    │  Resolve      │  Find       │  Deploy      │  Docker      │  Collect
    │  repos,       │  build.sh   │  .pem keys   │  exec in     │  hex/cfw,
    │  clone both,  │  or recipe  │  to repos    │  container   │  manifest,
    │  copy SDK     │  script     │              │              │  upload
```

### BuildContext

Mutable dataclass that carries state across stages:

| Field | Set by | Used by |
|-------|--------|---------|
| `job` | Pipeline | All stages |
| `work_dir` | Pipeline | Clone, Build |
| `output_dir` | Pipeline | Artifacts |
| `primary_dir` | Clone | Recipe, Signing, Build |
| `secondary_dir` | Clone | Signing, Build |
| `builder_image` | Build | Build (Docker) |
| `version_string` | Build | Artifacts |

### StageResult

Each stage returns `StageResult.ok()` or `StageResult.fail(error)`. The
pipeline stops at the first failure, reports to the API, and cleans the workspace.

### Stage Details

**CloneStage** — Resolves primary/secondary repos based on `job.target` (app vs mfg).
Clones both, copies the Zephyr SDK into the workspace for DinD access.

**RecipeStage** — Finds the build script. Priority chain:
1. Pinned recipe from build config
2. Stage-specific recipe
3. `build.sh` in repo root
4. `build_all.sh` fallback

**SigningStage** — Deploys signing keys from:
1. `webhookData.signingKeyValue` (base64-encoded, from API)
2. `/keys/{product}/*.pem` (K8s Secret mount)

**BuildStage** — Resolves the Docker builder image (from devcontainer.json or
product config), creates a sibling Docker container, runs the build script,
streams output, extracts version from `Resolved version: X.Y.Z` pattern.

**ArtifactStage** — Collects `.hex` and `.cfw` files from output directory,
generates `build.json` manifest, verifies artifacts exist, uploads everything
via the API.

---

## 4. Work Delivery

### Push + Poll Hybrid

```
                    HTTP-API                          Build Service
                    ────────                          ─────────────
  User creates build ──▶ INSERT QUEUED ──▶ POST /jobs/notify ──▶ JobQueue
  Webhook triggers   ──▶ INSERT QUEUED ──▶ POST /jobs/notify ──▶ JobQueue
                                                                    │
                                              Worker loop ◀─── get(timeout=60s)
                                                   │
                                         GET /v2/ci/builds?status=QUEUED
                                                   │              (fallback)
                                              process_job()
```

1. API inserts a QUEUED build and fires a POST to `/jobs/notify` (fire-and-forget)
2. Build service's `JobQueue` enqueues the notification (priority-ordered, deduped)
3. Worker loop calls `queue.get(timeout=60)` — returns immediately on push, or
   falls back to polling the API after 60 seconds of silence

### Priority Queue

`JobQueue` wraps `queue.PriorityQueue` with:
- Negated priority (higher number = dequeued first)
- Dedup via `_seen` set (same job ID only processed once)
- Thread-safe for concurrent notify + dequeue
- `clear_seen()` called after each job completes

Priority field on `BuildJob` in PostgreSQL (default 50). API sorts by
`priority DESC, createdAt ASC` when the build service polls.

---

## 5. Observability

### Real-time Progress

At each pipeline stage transition, the build service:
1. PATCHes the job status via the API
2. POSTs to `/v2/builds/{id}/progress` with step name + progress percentage
3. The API broadcasts a `ci_build_progress` SocketIO event to connected frontends

### Log Streaming

During Docker exec, stdout/stderr chunks are streamed to the API via
`POST /v2/builds/{id}/log`. The API broadcasts these as SocketIO events
for real-time build log viewing in the UI.

### Heartbeats

During active builds, the worker PATCHes `lastHeartbeat` every 60 seconds.
The recovery service uses this to detect dead workers (see
[Zero-Downtime Updates](../platform/zero-downtime.md)).

### Health Endpoints

| Endpoint | Purpose | During Drain |
|----------|---------|-------------|
| `GET /health` | Liveness probe (always 200) | 200 |
| `GET /ready` | Readiness probe | **503** |
| `POST /drain` | Trigger graceful shutdown | Sets draining |
| `GET /workers` | WorkerState JSON | Shows draining=true |
| `GET /metrics` | Prometheus metrics | Active until exit |

---

## 6. Docker Build Execution

### Sibling Container Model

The build service runs as a K8s pod with the Docker socket mounted. It creates
**sibling containers** (not nested DinD) that share workspace via hostPath:

```
K8s Node
├── /var/run/docker.sock      ← shared
├── /tmp/concord-builds/      ← hostPath, shared between build-service and builders
├── /tmp/concord-ccache/      ← ccache persistence
│
├── Pod: concord-build-service
│   └── Container: build-service (Python worker)
│       ├── mounts docker.sock
│       ├── mounts /tmp/concord-builds → /tmp/builds
│       └── creates sibling containers via Docker API
│
└── Container: concord-build-{job-id} (created by build-service)
    ├── image: from devcontainer.json or product config
    ├── mounts /tmp/concord-builds/{job-id} → /workdir
    ├── mounts /tmp/concord-ccache → /ccache
    └── runs: build.sh inside workspace
```

### Devcontainer Support

The build service parses `.devcontainer/devcontainer.json` from the firmware
repo to resolve the builder image:

```json
{
  "image": "containers.ad.corekinect.com/ncs-fw-dev:2.7.0",
  "containerEnv": {
    "ZEPHYR_BASE": "/opt/nordic/ncs/zephyr",
    "GNUARMEMB_TOOLCHAIN_PATH": "/opt/gnuarmemb"
  },
  "postCreateCommand": "west update"
}
```

Priority for image resolution:
1. `devcontainer.json` in repo (preferred — repo controls its own build env)
2. Product `buildConfig.builderImage` in database
3. `DEFAULT_BUILDER_IMAGE` env var (fallback)

### Orphan Cleanup

On startup, the build service kills any orphaned `concord-build-*` containers
left from a previous crash. On shutdown, the current builder container (if any)
is killed as part of the drain sequence.

---

## 7. Deployment

```yaml
# Key deployment settings
terminationGracePeriodSeconds: 2400    # 40 min (max build = 30 min)
lifecycle:
  preStop:
    httpGet:
      path: /drain
      port: 9002
securityContext:
  privileged: true                      # Docker socket access
```

Environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `CONCORD_API_URL` | — | HTTP-API URL (e.g., `http://concord-http-api:9001`) |
| `CONCORD_API_KEY` | — | API key for authentication |
| `BUILD_SERVICE_PORT` | 9002 | Flask API port |
| `POLL_INTERVAL` | 60 | Fallback poll interval (seconds) |
| `WORKER_ID` | hostname | Identifies this worker in logs |
| `DEFAULT_BUILDER_IMAGE` | `ncs-fw-dev:2.7.0` | Fallback Docker image |
| `BUILDER_TIMEOUT` | 1800 | Max build duration (seconds) |
| `WORKSPACE_DIR` | `/tmp/builds` | Local workspace path |

---

## 8. Database Schema

The build service does **not** have its own database. All state lives in the
shared Concord PostgreSQL database, managed by the HTTP-API:

```prisma
model BuildJob {
  // ... standard fields ...
  priority        Int             @default(50)
  lastHeartbeat   DateTime?       // Updated every 60s during active builds
  // ...
  @@index([status, priority])     // For efficient QUEUED job polling
}
```

See `prisma/schema.prisma` for the full model.

---

## 9. Testing

233 tests covering all components:

| Test file | Count | Coverage |
|-----------|-------|----------|
| `test_pipeline.py` | 15 | Pipeline orchestration, stage ordering, failure handling |
| `stages/test_clone.py` | 10 | Repo resolution, clone success/failure, SDK copy |
| `stages/test_recipe.py` | 6 | Priority chain, fallback, SDK path patching |
| `stages/test_signing.py` | 5 | Webhook key, K8s mount, no key warning |
| `stages/test_build.py` | 11 | Version extraction, Docker image, execution |
| `stages/test_artifacts.py` | 4 | Upload, verification, manifest |
| `test_worker_state.py` | 9 | Lifecycle, counters, draining, serialization |
| `test_queue.py` | 8 | Priority ordering, FIFO, dedup, thread safety |
| `test_drain.py` | 8 | Drain sets draining, ready 503, health stays 200 |
| `test_orphan_cleanup.py` | 6 | Kills orphans, handles failures |
| `test_devcontainer.py` | 11 | Parsing, comments, containerEnv merging |
| Others | 140 | Config, worker loop, API client, Docker runner, etc. |

```bash
cd apps/backend/build-service
PYTHONPATH=.:../../..:../../../libs/python:../../../libs pytest tests/ -v
```
