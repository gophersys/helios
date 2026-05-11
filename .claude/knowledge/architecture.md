# Concord — System architecture

The top-level view of how the platform is organized, what talks to what, and how a request flows end-to-end.

Refresh this file when: a new service is added or removed, a service moves between tiers, or a cross-service contract changes shape.

## Three tiers

```
                       ┌─────────────────────────────────────┐
                       │              FRONTEND                │
                       │  app (SvelteKit) · docs (MkDocs) ·   │
                       │  ci-admin (SvelteKit)                │
                       └──────────────────┬──────────────────┘
                                          │ REST + WebSocket
                                          ▼
                       ┌─────────────────────────────────────┐
                       │              BACKEND                 │
                       │  http-api ◀─── hub                   │
                       │      ▲              ▲               │
                       │      │              │               │
                       │  build-service   git-poller         │
                       └──────────────────┬──────────────────┘
                                          │ gRPC :50053
                                          ▼
                       ┌─────────────────────────────────────┐
                       │              EDGE                    │
                       │  mtib-server (per fixture node)      │
                       │  — controls DUT power, GPIO, UART,   │
                       │    J-Link, ADC, motion               │
                       └─────────────────────────────────────┘
```

**Three deployment environments**:

- **development** — `docker-compose` under `deploy/development/`. Every service runs locally in a container.
- **staging** — Kubernetes `staging` namespace. Helm chart from `deploy/production/helm/` + `values-staging.yaml`.
- **production** — Kubernetes `production` namespace. Same chart + `values-production.yaml`.

The cluster is a 3-control-plane / N-agent K3s install in the office (`concordserver01-03`, `concordagent01-03`), plus edge Verdin iMX8MM nodes for fixtures. See [`knowledge/deploy/overview.md`](deploy/overview.md).

## Apps and what they do

| App | Path | What it does | Talks to |
|---|---|---|---|
| `http-api` | `apps/backend/http-api/` | Flask + Flask-SocketIO. The hub. Owns Prisma DB, K8s scheduling, MinIO storage, MTIB observability, audit log, notifications. | DB, MinIO, K8s, MTIBs, CoreOps |
| `build-service` | `apps/backend/build-service/` | Worker. Polls http-api for queued firmware build jobs; clones repos via SSH; runs nRF Connect SDK / Zephyr builds; uploads artifacts. | http-api, Bitbucket, MinIO |
| `git-poller` | `apps/backend/git-poller/` | Watches Bitbucket branches for new commits; triggers builds via http-api. | http-api, Bitbucket |
| `app` (frontend) | `apps/frontend/app/` | SvelteKit. Primary user UI. Login, products, builds, validation, manufacturing, fixtures, users. | http-api (REST + WebSocket) |
| `docs` | `apps/frontend/docs/` | MkDocs Material. Product documentation with role-based visibility. | (static, no runtime deps) |
| `ci-admin` | `apps/frontend/ci-admin/` | SvelteKit. Independent dashboard for nightly/weekly E2E pipeline. | K8s API, MinIO |
| `mtib-server` | `apps/edge/mtib-server/` | gRPC server on each fixture node. Power, GPIO, UART, J-Link, ADC, motion (FluidNC). ARM64-only. | (called by validation/mfg runners + http-api) |
| `icle` | `apps/firmware/icle/` | Zephyr/ESP32 firmware for the ICLE power monitor. Separate world from the platform. | (standalone) |

Per-app deep knowledge lives under `knowledge/apps/<tier>/<name>.md`.

## Shared libraries

| Library | Path | Used by | Distribution |
|---|---|---|---|
| `corekinect` (Python SDK) | `libs/python/` | build-service, git-poller, validation runners, manufacturing runners, corectl | Wheel published to internal PyPI |
| `protocols` | `libs/protocols/` | mtib-server, http-api (MTIB client), all Python services | Code-generated; bundled into corekinect wheel |
| `embedded` | `libs/embedded/` | firmware projects (icle, alpha, sigma5, theta) | Zephyr modules / board overlays |
| `bash` | `libs/bash/` | deploy/ctl.sh, infra scripts | sourced |

Per-lib deep knowledge under `knowledge/libs/`.

## Data layer

- **Database**: PostgreSQL, single `concord` database per environment.
- **Schema authority**: `prisma/schema.prisma`. Mirrored to `libs/python/database/schema.prisma` for the generated Python client.
- **Migrations**: Prisma. Applied automatically by a K8s init container before http-api starts. See [`knowledge/prisma/migrations.md`](prisma/migrations.md).
- **Domain enums**: Defined in Prisma. Backend imports from `database.enums`. Frontend keeps a hand-synced copy in `apps/frontend/app/src/lib/types/models.ts`.

## API surface

- **HTTP API**: Flask Blueprint mounted at `/v2/`. Every route uses `@require_permissions(...)`. Standard response envelope `{ data, errors?, pagination? }`.
- **WebSocket**: Flask-SocketIO. `/notifications` namespace. Server emits to `room=user:<user_id>`.
- **gRPC (MTIB)**: `MtibV1` service defined in `libs/protocols/mtib/mtib.proto`. Hardware control RPCs (power, GPIO, UART, programming, sensors, motion). Port 50053.
- **Edge → API**: MTIB nodes don't push directly; the http-api polls them via gRPC for observability and pod-side runners call MTIB methods during tests.

Deep references: [`knowledge/apps/backend/http-api.md`](apps/backend/http-api.md), [`knowledge/apps/edge/mtib-server.md`](apps/edge/mtib-server.md).

## A complete request lifecycle

Tracing **"manufacturing test stage completes"** to make the contracts concrete:

1. **Hardware/runner**: Manufacturing runner pod on the fixture node executes a stage against the DUT. It calls MTIB gRPC methods (`PowerEnable`, `UartStream`, etc.) on the local `mtib-server` and parses results.
2. **Result POST**: Runner calls `POST /v2/runs/<run_id>/target/<target_id>/stage/<stage_id>/complete` with `{ status: PASSED|FAILED, results: {...} }`.
3. **http-api handler** (`src/api/v2/runs/...`):
   - Validates the request via `<Type>.from_json()`.
   - `@require_permissions(Permissions.MFG_RUNS_MANAGE)` checks JWT + permission set.
   - Updates `Execution` row in Postgres via the Prisma client (`db.execution.update(...)`).
   - Recomputes parent `TestRun.status`.
   - Calls `log_audit("test.stage.complete", "Execution", stage_id, {...})`.
   - Calls `notify_user(owner_id, "manufacturing_complete", ...)` which writes a `Notification` row **and** emits `socketio.emit("notification", payload, room=f"user:{owner_id}")`.
4. **Frontend** subscribed to the SocketIO `/notifications` namespace receives the event, updates a Svelte store, and re-renders the relevant view.
5. **Response**: 200 with `ApiResponse.ok(updated_run)`.

Three things to notice that recur everywhere:

- **`@require_permissions` first, `from_json()` second, side effects last** — that ordering is the standard handler shape.
- **Audit logs on every mutation** — non-optional. See [`rules/audit-logging.md`](../rules/audit-logging.md).
- **Notifications are dual-writes** — DB row + SocketIO emit. The DB row is the source of truth; the emit is a courtesy.

## Cross-cutting concerns

- **Authentication** — Google OAuth → JWT (HS256). Token in `Authorization: Bearer` for REST, in `auth` payload for SocketIO. Bypass mode (`AUTH_ENABLED=false`) injects a default admin in dev. See [`rules/auth-defaults.md`](../rules/auth-defaults.md).
- **Authorization** — `User.role` (global) + per-`Product` `AccessLevel`. Permission constants in `apps/backend/http-api/src/lib/permissions.py`. Decorator checks user's `PermissionSet`.
- **Audit** — `log_audit(action, entity_type, entity_id, details)` writes to `AuditLog`. Required on every state mutation.
- **Notifications** — `notify_user(user_id, type, title, message, **refs)` writes `Notification` and pushes via SocketIO.
- **Storage** — MinIO. Buckets: `firmware`, `test-packages`, `artifacts`. Service uses presigned URLs for client uploads.
- **K8s scheduling** — http-api creates K8s Jobs (validation runner, manufacturing runner) using the `kubernetes` Python client. Pod observability flows back via gRPC + heartbeat.

## Where to go next

- [`apps/backend/http-api.md`](apps/backend/http-api.md) — backend internals
- [`apps/frontend/app.md`](apps/frontend/app.md) — frontend internals
- [`apps/edge/mtib-server.md`](apps/edge/mtib-server.md) — hardware control protocol
- [`prisma/schema-overview.md`](prisma/schema-overview.md) — data model
- [`deploy/overview.md`](deploy/overview.md) — how this gets shipped
- [`workflows/local-dev.md`](workflows/local-dev.md) — clone → green
- [`product-domains/`](product-domains/) — concept-oriented docs (builds, validation, manufacturing, fixtures, products, users-rbac)
- [`glossary.md`](glossary.md) — domain terms
- [`conventions.md`](conventions.md) — code-shape conventions
