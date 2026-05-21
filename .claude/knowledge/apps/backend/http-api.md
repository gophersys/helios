# http-api — knowledge

The Flask + Flask-SocketIO service that sits at the centre of the platform. Every state change in Concord — product CRUD, builds, validation, manufacturing, fixtures, devices, users, releases, notifications — passes through here. The frontend, the build-service worker, the git-poller, and the MTIB observability service all talk to this app over REST and WebSocket. It owns the Prisma database client, the MinIO storage client, the Kubernetes client, the JWT/API-key auth pipeline, the audit log, and the SocketIO push channel.

Refresh this file when: a new route module is added under `src/api/v2/<domain>/`, a service in `src/services/` is added or removed, the handler shape changes (decorator order, response envelope, audit shape), a new permission constant is added to `src/lib/permissions.py`, a new background scheduler thread is added in `src/services/scheduling/`, a new auth bypass appears (webhook or runner secret), or the SocketIO namespace surface changes.

## Location

- Code: `apps/backend/http-api/`
- Entry point: `src/main.py`
- Tests: `tests/` (subtrees: `unit/`, `integration/`, `contracts/`, `api/`, `services/`, `auth/`, `websocket/`, `lib/`)
- Container: `deploy/Dockerfile`
- Env config: `config/env.py` (`AppConfig` extends `corekinect.utils.EnvConfig`)

## Responsibilities

Owns:

- All `/v2/*` HTTP routes and the `/notifications` SocketIO namespace.
- Authentication (JWT HS256, API-key SHA-256) and authorization (`PermissionSet` + per-`Product` `AccessLevel`).
- Prisma client lifecycle (`src/services/database/prisma.py`) and schema-drift gating on `/ready`.
- MinIO storage client and presigned URLs (`src/services/storage/`).
- Kubernetes client and runner-job dispatch (`src/services/kubernetes/`, `src/services/executors/`).
- MTIB observability polling (`src/services/devices/mtib_observability.py`) — gRPC client to every fixture node.
- Audit log (`src/lib/audit.py` → `auditlog` table).
- Notifications (`src/services/notifications/notifier.py` → `Notification` row + SocketIO emit).
- Background schedulers: audit cleanup, stale-build recovery, Bitbucket poller, queue dispatch.

Does not own:

- Firmware compilation (`build-service`).
- Branch/PR change detection (`git-poller`).
- Hardware control RPCs (`mtib-server`, gRPC port 50053).
- Test execution inside runner pods (`validation/`, `manufacturing/` runner images; called via K8s Jobs).
- Frontend rendering or type generation (`apps/frontend/app/` — type mirror is hand-synced).

## Internal structure

```
apps/backend/http-api/
├── config/
│   └── env.py                       # AppConfig — env-var schema for the service
├── src/
│   ├── main.py                      # Flask + SocketIO bootstrap, signal handlers
│   ├── api/v2/
│   │   ├── router.py                # register_v2_routes() composes all domain routes
│   │   ├── docs.py                  # OpenAPI spec + Swagger UI at /v2/docs
│   │   ├── assets/                  # asset sets, zip upload + validator, storage download
│   │   ├── auth/                    # login, dev login, sessions, API keys, users,
│   │   │                            #   permission sets, permissions list, /me
│   │   ├── builds/                  # build runs, build jobs, PR builds, manifests,
│   │   │                            #   stage configs, stage triggers, recipes, scripts,
│   │   │                            #   overlays, queue priority, webhook, build cache
│   │   ├── devices/                 # ICLE + MTIB device CRUD (devices/routes.py is
│   │   │                            #   the thin wrapper; ICLE handlers live in v2/icle/)
│   │   ├── fixtures/                # fixtures, benches, designs
│   │   ├── fixture_claims/          # DEV_HOLD claims — create/heartbeat/release/list/get
│   │   ├── icle/                    # ICLE device commands, config, heartbeat, logs, OTA
│   │   ├── kubernetes/              # cluster info, deployments, jobs, pods, events,
│   │   │                            #   nodes, services, RBAC, configmaps
│   │   ├── manufacturing/           # manufacturing sessions, runner control
│   │   ├── nodes/                   # K8s node metadata + fixture binding
│   │   ├── products/                # products, boards, board revisions, targets,
│   │   │                            #   firmware sets, test packages, board discovery,
│   │   │                            #   product access, manufacturing config
│   │   ├── runs/                    # test runs, executions, queue, scheduler,
│   │   │                            #   artifacts, logs, telemetry, ws, reporter,
│   │   │                            #   manual triggers, guard patches, demo
│   │   └── system/                  # healthcheck, info, history, releases, retention,
│   │                                #   secrets, observability WS, poller state,
│   │                                #   error reports, notifications WS, user reports
│   ├── services/
│   │   ├── auth/                    # JWT issue/verify, CoreCloud OAuth bridge
│   │   ├── builds/                  # job runner glue, recovery, run service, promotion,
│   │   │                            #   trigger, artifact validator, notifier
│   │   ├── ck_boards/               # CkBoards repo cache (board definitions)
│   │   ├── database/                # Prisma client init, schema-drift report
│   │   ├── devices/                 # MTIB observability poller (gRPC to fixtures)
│   │   ├── executors/               # docker_executor + kubernetes_executor + factory
│   │   ├── fixtures/                # reservation gate (is_fixture_busy / are_nodes_busy)
│   │   ├── integrations/            # Bitbucket REST client, webhook trigger
│   │   ├── kubernetes/              # K8s client, deployments, jobs, pods, nodes,
│   │   │                            #   events, configmaps, RBAC, MTIB deployments,
│   │   │                            #   runner env, runner_dispatch (pytest|ztest),
│   │   │                            #   address_resolver (nodeId → MTIB host),
│   │   │                            #   serializers
│   │   ├── log/                     # Logger init + LogFilter for /healthcheck noise
│   │   ├── mfg_session_reaper.py    # Mid-stage manufacturing-session reaper
│   │   ├── notifications/           # notify_user() + SocketIO emit
│   │   ├── retention.py             # Retention policy enforcement
│   │   ├── scheduling/              # scheduler + queue_scheduler (build/val/mfg dispatch)
│   │   └── storage/                 # MinIO client (init + presigned URLs)
│   └── lib/
│       ├── decorators.py            # @require_auth, @require_permissions,
│       │                            #   @require_role, @require_product_access
│       ├── permissions.py           # Permissions class + PERMISSION_REGISTRY + DEFAULT_ROLES
│       ├── audit.py                 # log_audit() — writes AuditLog row
│       ├── errors.py                # bad_request / unauthorized / forbidden / not_found / conflict
│       ├── types.py                 # ApiResponse + ErrorDetail (response envelope)
│       └── validation.py            # Input validators
└── assets/templates/                # Static HTML templates (Swagger UI, etc.)
```

The `src/api/v2/<domain>/` modules each export a `register_<domain>_routes(api_blueprint, [socketio])` function called from `src/api/v2/router.py`. The Blueprint is mounted at `/v2`.

## Key patterns

### Handler shape

The canonical order — followed by every v2 handler — is:

1. `@require_permissions(Permissions.<DOMAIN>_<VIEW|MANAGE>)`. Always first. Reads use `_VIEW`, mutations use `_MANAGE` (manufacturing/validation also have `_RUN` and `_TRIGGER`).
2. Parse the request via `<Type>.from_json(request.json)`. Invalid input → `bad_request(...)`.
3. Read/compute. `db = get_db_client()`; use enum constants (`enums.TestRunStatus.ACTIVE`), never raw strings.
4. Mutate. `db.<model>.<create|update|delete>(...)`. Wrap multi-step writes in `async with db.tx():` when atomicity matters.
5. `log_audit("<dot.verb>", "<EntityType>", entity_id, {"before": ..., "after": ...})`. Required on every mutation.
6. Side effects: `notify_user(...)`, `socketio.emit(...)`, K8s job creation, `wake_scheduler()`.
7. Return `jsonify(ApiResponse.ok(<payload>).to_dict()), 200` (or `.created()`/`.deleted()`/`.paginated()`).

See [`conventions.md`](../../conventions.md) for the rules-form of this and [`../../rules/auth-defaults.md`](../../../rules/auth-defaults.md) for the auth contract.

### Response envelope

`ApiResponse` (in `src/lib/types.py`) is the only response shape in the v2 surface:

```json
{ "data": <T> | null, "errors": [{"message": "..."}], "page": ..., "totalPages": ..., "totalResults": ..., "resultsPerPage": ... }
```

`errors` is always serialized (empty list on success). Pagination fields are omitted when `None`. Status codes: `200` GET/PUT/DELETE success, `201` POST create (use `ApiResponse.created`), `400/401/403/404/409/500` for failures.

### Route registration

Each domain has a `routes.py` that exports `register_<domain>_routes(api, [socketio])`. Handler functions are imported at the top of that file, then bound via `api.add_url_rule(path, view_func=handler, methods=[...])`. The top-level `src/api/v2/router.py` calls every domain's register function and registers the Blueprint on the Flask server.

To add a new endpoint in an existing domain: write the handler in the matching `<domain>/<entity>.py`, import it in `<domain>/routes.py`, then add the `api.add_url_rule(...)` line. To add a new domain: create `src/api/v2/<domain>/{routes.py,<entity>.py,types.py}`, then add `register_<domain>_routes(...)` to `src/api/v2/router.py`'s `register_v2_routes`.

### Auth

`@require_permissions` calls `@require_auth` internally and then checks the user's `PermissionSet`. ADMIN and MAINTAINER roles bypass permission-set checks; OPERATOR and DEVELOPER must have the explicit permission. `@require_auth` accepts `Authorization: Bearer <jwt>` and `Authorization: ApiKey <raw-key>` (SHA-256 hashed and compared against `apiKey.keyHash`). When `AUTH_ENABLED=false` and no header is present, the dev-admin identity (`admin@concord.local`, `sub=00000000-…`) is injected.

`X-View-As-Role` lets ADMIN/MAINTAINER preview a lower role for permission checks. `g.effective_role` is populated for the handler.

The three documented bypasses are `/health` + `/ready` + `/v2/healthcheck`, the Bitbucket webhook (`/v2/builds/webhook` — HMAC-SHA256 with `BITBUCKET_WEBHOOK_SECRET`, fail-closed), and runner heartbeats (shared API-key under `ApiKey` scheme).

### Audit

`log_audit(action, entity_type, entity_id, details)` — action is `<domain>.<verb>` lowercase, entity_type is the PascalCase Prisma model. Captures the current user from `g.current_user` and the client IP from `X-Forwarded-For` (or `request.remote_addr`). Errors are swallowed — audit logging never breaks a request.

### Notifications

`notify_user(user_id, type, title, message, release_id=None, error_report_id=None)` writes a `Notification` row and (if SocketIO is initialised via `init_socketio`) emits `"notification"` to `room=user:<user_id>` on the `/notifications` namespace. Per-user preference (`NotificationPreference`) is checked first — disabled types produce no row and no push.

### Background scheduler threads

Started from `src/main.py` after the clients are initialised:

| Thread | Source | Cadence | What it does |
|---|---|---|---|
| `audit-cleanup` | `scheduling/scheduler.py` | every 24 h | Deletes `auditlog` rows older than 30 days |
| `build-recovery` | `scheduling/scheduler.py` → `services/builds/recovery.py` | every 60 s (30 s startup delay) | Resets builds stuck in `CLONING`/`BUILDING` after worker death |
| `git-poller` (in-process) | `scheduling/scheduler.py` → `integrations/webhook_trigger.poll_for_changes` | `BITBUCKET_POLLER_INTERVAL_S` (default 300 s) | Triggers stage builds when a watched branch advances. Gated by `BITBUCKET_POLLER_ENABLED` — runs in addition to the separate `git-poller` service. |
| `queue-scheduler` | `scheduling/queue_scheduler.py` | `SCHEDULER_INTERVAL_S` (15 s) plus wake events | Dispatches QUEUED build/validation/mfg jobs respecting concurrency caps; notifies build-service via `/jobs/notify` when slots open |
| `claim-expiry-sweep` | `scheduling/scheduler.py` → `api/v2/fixture_claims/service.sweep_expired_claims` | every 60 s (30 s startup delay) | Transitions ACTIVE `FixtureClaim` rows: → `EXPIRED` past `expiresAt`, → `ABANDONED` past `hardCeilingAt`. Writes one `fixture.claim.release` audit row per transition (reason `expired` or `abandoned`). |
| MTIB observability | `services/devices/mtib_observability.py` | 5 s (polled in `init_observability_service`) | gRPC poll of every fixture node for power, GPIO, ADC, motion state |

Graceful shutdown (SIGTERM/SIGINT) stops the schedulers first, sleeps 2 s for in-flight queries, then closes MTIB observability, Prisma, MinIO, and the K8s client.


### TestBed extraction on test package upload

`src/api/v2/products/test_packages.py::_extract_testbed_designs` reads the uploaded test package's `concord.yaml`, walks the user's Python `TestBed` subclass via `corekinect.testbed.extractor.extract_testbed` (AST-only — no import), and writes a `TestBedDesign` row in Concord linking back to the parent `TestPackage`. The user-Python class is called **TestBed** (since 2026-05); Concord's storage row remains **TestBedDesign**. The two names are deliberately different: the user declares a TestBed (DUT-side wiring), Concord stores a TestBedDesign (the platform-side row that powers fixture creation + slot binding).

### Runner framework dispatch (pytest vs ztest)

`src/services/kubernetes/runner_dispatch.py` is the single source of truth for converting a `TestPackage.framework` value (`PYTEST` / `ZTEST` / None) into:

- the container `command` array for the K8s Job (`runner_command_for_framework`), and
- the `TEST_FRAMEWORK` env-var value injected into the runner pod (`framework_env_var`).

`normalize_framework(value)` is the boundary helper — accepts `None`, `""`, `"pytest"`, `"PYTEST"`, `"ztest"`, `"ZTEST"` and returns canonical `"PYTEST"` / `"ZTEST"`. Anything else raises `ValueError` so the upload handler can surface a 400 with a useful message.

Back-compat invariant: every test package created before this dispatch existed has `framework=NULL` in old DB rows (default `PYTEST` post-migration) and no `framework` field in concord.yaml. All three paths — DB NULL, missing manifest field, `framework=None` kwarg — collapse to PYTEST, and PYTEST leaves the container `command` unset so the existing image ENTRYPOINT (`/app/entrypoint.sh`) runs unchanged.

Flow:

1. Upload (`api/v2/products/test_packages.py::_upload_test_package_impl`) reads `manifest.framework` (also accepts `manifest.testFramework`), calls `normalize_framework`, persists to `TestPackage.framework`. Invalid framework values → 400 with the allowed set in the error body. Missing / empty / None all default to PYTEST.
2. Scheduler (`api/v2/runs/scheduler.py::_trigger_validation_job`) reads `tp.framework`, passes it as `framework=` to:
   - `create_kubernetes_job` (staging/prod path in `api/v2/runs/manual.py`) — substitutes `{{TEST_FRAMEWORK}}` in `validation_job.yaml` AND overrides `container.command` when ZTEST,
   - `KubernetesExecutor.submit` / Docker fallback (dev path) — passes `TEST_FRAMEWORK` env + framework-specific `command` list.
3. Runner pod entrypoint (`deploy/runner/entrypoint.sh`) branches on `TEST_FRAMEWORK` as a safety net: PYTEST → existing `run.py` / `pytest` path; ZTEST → `exec python3 -m corekinect.test.ztest_runner ...` (only reached when running through the entrypoint — the K8s/Docker dispatch already bypasses it for ZTEST by overriding command). Unknown values exit 2.

`validation_job.yaml` carries `TEST_FRAMEWORK` directly so the runner pod can log + verify the dispatch. The `_serialize_test_package` helper exposes `framework` in the v2 API response.

The ZTEST module lives in `libs/python/corekinect/test/ztest_runner.py` — see `libs/python-corekinect.md` for the runner's internals, CLI, and replay mode. Regression coverage for both dispatch paths lives in `tests/api/runs/test_manual_framework.py` (real-template render) and `tests/services/test_runner_framework_dispatch.py` (pure dispatch unit tests).

### DEV_HOLD fixture claims (`/v2/fixture-claims/`)

Local-dev TDD lets a developer lease a real fixture or a set of raw nodes for the duration of a development session. The lease is honored against concurrent scheduled work via the shared reservation gate at `services/fixtures/reservation.py`.

Endpoints (all routed through `api/v2/fixture_claims/routes.py`):

| Method + path | What it does | Permission gate | Audit |
|---|---|---|---|
| `POST /v2/fixture-claims` | Create. Body is XOR `fixtureId` vs `nodes[]` (`CreateClaimRequest` in `validators.py`). `ttlSeconds` defaults to 3600, clamped to 8h. Refuses 409 if the gate reports busy. | `VALIDATION_RUN` for validation-typed targets, `MANUFACTURING_MANAGE` otherwise — classified by `service.is_validation_target`. | `fixture.claim.create` |
| `POST /v2/fixture-claims/<id>/heartbeat` | Bump `lastHeartbeatAt = now`, recompute `expiresAt = min(now + 5min, hardCeilingAt)`. Returns 410 when the row is not ACTIVE. | Owner OR `SYSTEM_VIEW` OR Admin/Maintainer | *(none — too hot)* |
| `POST /v2/fixture-claims/<id>/release` | Idempotent: ACTIVE → RELEASED, anything else passes through. | Same as heartbeat. | `fixture.claim.release` with `reason="explicit"` |
| `GET /v2/fixture-claims` | List filtered by `userId` (default: caller), `status` (default: ACTIVE), `fixtureId`. List omits `slotBindings` to avoid one K8s call per row — call the detail endpoint for those. | `VALIDATION_VIEW` OR `MANUFACTURING_MANAGE` | *(read)* |
| `GET /v2/fixture-claims/<id>` | Fetch one with `slotBindings` resolved live. | `VALIDATION_VIEW` OR `MANUFACTURING_MANAGE` | *(read)* |

Internals:

- `service.create_claim` writes `acquiredAt`, `lastHeartbeatAt`, `expiresAt = now + ttl`, `hardCeilingAt = now + 8h` (immutable). `expiresAt` is clamped to the ceiling on every write.
- `service.serialize_claim` calls `services/kubernetes/address_resolver.resolve_node_addresses` to build `slotBindings[*].mtibHost`. Same helper is used by `api/v2/runs/scheduler._resolve_all_slot_info` so the K8s lookup + `Node.ipAddress` fallback live in one place.
- `service.sweep_expired_claims` is the background lifecycle driver — see the `claim-expiry-sweep` row in the scheduler table above. Called from `scheduling/scheduler._claim_expiry_sweep_loop` every 60 s.
- The reservation gate (`services/fixtures/reservation.is_fixture_busy` + `are_nodes_busy`) is the single source of truth for "is this hardware busy?". It unions ACTIVE `TestRun`, `ManufacturingSession`, and `FixtureClaim` rows — plus, for node-mode claims, the transitive case where a node is wired into a slot whose fixture has an active run/session. Consulted by:
  - `api/v2/runs/scheduler.schedule_queue` (pre-filter — excludes claim-held fixtures from the eligible set)
  - `api/v2/manufacturing/sessions.create_manufacturing_session` (refuses 409 when a `CLAIM_ACTIVE` reason is returned)
  - `api/v2/fixture_claims/routes.create` (refuses 409 for any of the three reasons)

Permission peculiarity: `@require_permissions(*perms)` requires ALL listed permissions, but the claim endpoints want ANY-of (a developer with only `VALIDATION_RUN` should be able to claim a validation fixture). So the routes use `@require_auth` for JWT plumbing and call `_user_has_permission_any` inline. The create endpoint additionally re-gates on the precise permission once the target type is parsed.

Tests live in `tests/api/fixture_claims/test_routes.py` and exercise every endpoint plus the sweeper (which is called directly with a mock `db` — the scheduler thread itself is not under test).

## External dependencies

| Dep | Where | Env var(s) | Notes |
|---|---|---|---|
| PostgreSQL (via Prisma) | `services/database/prisma.py` | inherited via Prisma's `DATABASE_URL` | Schema authority is `prisma/schema.prisma`. `/ready` runs a drift check (`schema_drift.py`) and returns 503 on mismatch. `PROBES` list tracks post-rename table names (e.g., `test_bed_designs`, not the legacy `fixture_designs`) — update when a column is renamed or a table replaced. `/ready` ALSO returns 503 with `reason=ckboards_unavailable` when `init_ck_boards_service` couldn't authenticate to Bitbucket at startup (caught after v0.10.5 surfaced the failure mode where a stale `BITBUCKET_API_TOKEN` would silently disable board discovery and only 500 when an operator opened the product wizard). |
| MinIO | `services/storage/client.py` | `STORAGE_URL`, `STORAGE_ACCESS_KEY`, `STORAGE_SECRET_ACCESS_KEY`, `STORAGE_BUCKET_NAME` | Buckets: `firmware`, `test-packages`, `artifacts` |
| Kubernetes API | `services/kubernetes/client.py` | in-cluster or kubeconfig | Used for runner Jobs, deployment status, MTIB deployments. `VALIDATION_NAMESPACE` (default `validation`) is privileged. |
| Bitbucket Cloud | `services/integrations/bitbucket_client.py` | `BITBUCKET_SSH_KEY` (base64, written to disk), `BITBUCKET_API_TOKEN`, `BITBUCKET_EMAIL`, `BITBUCKET_WORKSPACE`, `BITBUCKET_WEBHOOK_SECRET` | SSH for clone-equivalents; API token (Basic auth) for PR + branch REST queries |
| CkBoards repo | `services/ck_boards/service.py` | `CK_BOARDS_REPO_URL`, `CK_BOARDS_FETCH_INTERVAL` | Pulled via Bitbucket REST, cached in-memory |
| CoreOps | `corekinect.core_ops` (SDK) | `COREOPS_SERVER_URL`, `COREOPS_API_KEY`, `COREOPS_AUTH_*`, `COREOPS_VERIFY_SSL` | Device personalisation post-manufacturing |
| build-service | `services/builds/notifier.py` | `BUILD_SERVICE_URL` | Fire-and-forget POST to `<url>/jobs/notify` when a `BuildJob` is created. If unset or unreachable, the worker's 60 s fallback poll catches it. |
| MTIB nodes (gRPC :50053) | `services/devices/mtib_observability.py` | `MTIB_PORT` (default 50053) | One channel per fixture node, target resolved via `Node.mtib_host` |
| Frontend / corectl | inbound REST + WS | `CORS_ORIGINS` | Comma-separated allowed origins |
| Self-reference (for K8s jobs) | runner-env generation | `CONCORD_API_URL`, `CONCORD_API_HOST` | The runner pod needs to call back into the API; `CONCORD_API_HOST` provides the Host header for ingress routing in K8s |

Credentials — see [`../../deploy/secrets.md`](../../deploy/secrets.md). Don't duplicate values here.

JWT: `JWT_SECRET_KEY` is validated on startup. In `production` or `staging` it must differ from the default and be ≥ 32 chars; `config/env.py` raises at import.

## How to add common things

### Add a v2 endpoint in an existing domain

1. Pick the right module under `src/api/v2/<domain>/` (one file per resource). Add the handler.
2. Apply `@require_permissions(Permissions.<DOMAIN>_<VIEW|MANAGE>)` first, then parse via `from_json`, mutate via `db.<model>.<action>`, call `log_audit(...)`, fire side effects, return `jsonify(ApiResponse.ok(...).to_dict()), <status>`.
3. Import the handler in `src/api/v2/<domain>/routes.py` and add an `api.add_url_rule(...)` line.
4. Add a test under `tests/api/v2/<domain>/`.
5. If a new permission constant is needed, see below.
6. Mirror response types in `apps/frontend/app/src/lib/types/models.ts` (hand-synced — there is no codegen).

### Add a new domain (new `src/api/v2/<domain>/`)

1. Create `<domain>/{__init__.py, routes.py, <entity>.py, types.py}`.
2. Export `register_<domain>_routes(api: Blueprint)` (add a `socketio: SocketIO` parameter if the domain needs realtime).
3. Import it in `src/api/v2/router.py` and call it from `register_v2_routes(...)`.
4. Add tests under `tests/api/v2/<domain>/` and a contract test under `tests/contracts/` if the frontend consumes the responses.

### Add a permission constant

1. Add `Permissions.<DOMAIN>_<VERB> = "<domain>:<verb>"` in `src/lib/permissions.py`.
2. Add a matching `PERMISSION_REGISTRY` row with `module`, `label`, `description` (used by the UI for grouping).
3. Update `DEFAULT_ROLES` in the same file so seeded roles get the new permission appropriately.
4. Update the frontend permissions list (`apps/frontend/app/src/lib/types/models.ts` / `permissions.ts`) so the UI gates correctly.

### Add a new audit action

No code change required — just call `log_audit("<domain>.<verb>", "<EntityType>", entity_id, {...})` from inside the handler. Use dotted lowercase verbs (`product.create`, `build.trigger`, `test.stage.complete`). `entity_type` matches the Prisma model name in PascalCase. Put before/after diffs in `details`.

### Add a new env var

1. Add the field to `AppConfig` in `config/env.py` with a default.
2. Read it via `env_config.<NAME>`.
3. Add to all three environment configs in the same commit: `deploy/development/docker-compose.yaml`, `deploy/production/helm/values-staging.yaml`, `deploy/production/helm/values-production.yaml`. See [`../../../rules/all-three-envs.md`](../../../rules/all-three-envs.md).
4. If it's a credential, also add it to the K8s Secret manifest plumbing and update [`../../deploy/secrets.md`](../../deploy/secrets.md).

### Add a background scheduler

Add the thread inside `start_scheduler()` in `src/services/scheduling/scheduler.py`. Keep the inner loop in a private function (`_<name>_loop`), use `time.sleep(...)` or the shutdown event for cadence, and gate behind an env-config flag if it could be undesired. Update the graceful-shutdown stop path in `src/main.py` if the thread holds resources beyond the DB.

## Common failure modes

- **`/ready` returns 503 with `reason=schema_drift`.** The Prisma client embedded in this pod was generated against a different schema than the live DB. Usually a transitional state during a deploy where the http-api image and the migration init-container don't agree. The mismatched pod is yanked from rotation — wait for the rollout to complete, or check `kubectl -n <env> logs <pod> -c migrate-and-seed` for migration failures (`P3009`).
- **`/ready` returns 503 with `reason=ckboards_unavailable`.** CkBoards (board discovery via Bitbucket REST) failed to initialize. Almost always means the `BITBUCKET_API_TOKEN` in the running K8s Secret is revoked/expired. Rotate the Secret and restart the deployment; the next pod will pass /ready if Bitbucket accepts the new token.
- **MTIB observability stuck on a Verdin's old IP after it rotates DHCP leases.** Resolved in v0.10.7: `sync_nodes_from_k8s` writes the live K8s `InternalIP` back into `Node.ipAddress` whenever it drifts. The observability poller + grpc health-check both read this DB cache, so before the fix a rebooted Verdin with a new lease stayed unprobeable until manual backfill (the comment at `nodes.py::register_node` flagged this). Bindings are unaffected — `FixtureSlot.nodeId` keys on Concord's cuid (resolved by K8s hostname → same row), not on IP. The write is conditional: skip when K8s reports no IP (don't clobber last-known-good with empty), skip when the live IP equals the cached one (no audit noise on stable nodes). v0.10.8 makes the refresh autonomous: a `node-ip-refresh` scheduler thread (60 s cadence) calls `services/kubernetes/node_sync.refresh_node_ips_from_k8s()` so a rebooted Verdin is reachable within one cycle without anyone opening the fixtures page. The HTTP endpoint still runs the same logic for on-demand refresh.
- **`AUTH_ENABLED` mismatch.** In staging/production `AUTH_ENABLED` must be `true`; the dev-admin bypass (`sub=00000000-…`) silently grants ADMIN if a request reaches the API without a token while auth is disabled. If you see ADMIN actions from `admin@concord.local` in audit logs of a deployed env, auth got disabled by accident.
- **JWT startup failure: `JWT_SECRET_KEY must be changed from the default value`.** `AppConfig._validate()` raises at import time in `staging`/`production` if the secret is the dev default or shorter than 32 chars. Fix the K8s secret; rolling restart.
- **Build never starts after creation.** The fire-and-forget POST to `BUILD_SERVICE_URL/jobs/notify` is best-effort. If `BUILD_SERVICE_URL` is unset, only the build-service's 60 s fallback poll picks it up — expect up to a minute of latency. Check `nx logs build-service` for connection errors.
- **MTIB observability slow / `/v2/system/mtib-observability` returns empty.** The poller runs every 5 s but a stuck gRPC channel (fixture node offline or wedged) blocks one slot. Look for `Error stopping observability service` logs and for the `mtibHost` value on the affected `Node` row.
- **Stuck `BUILDING` / `CLONING` jobs.** The build-recovery scheduler (every 60 s) resets jobs whose heartbeat is stale or whose `startedAt` exceeds the 5-minute clone timeout. If recoveries aren't firing, check that `start_scheduler()` ran — the `Build recovery scheduler started` log line should appear on startup.

## Related knowledge

- [`../../architecture.md`](../../architecture.md) — system diagram and full request lifecycle.
- [`../../conventions.md`](../../conventions.md) — handler-shape conventions in rule form.
- [`../../glossary.md`](../../glossary.md) — domain terms (`BuildRun`, `TestRun`, `MTIB`, etc.).
- [`build-service.md`](build-service.md) — the firmware worker on the other end of `BUILD_SERVICE_URL`.
- [`git-poller.md`](git-poller.md) — the branch/PR watcher that triggers builds via this API.
- [`../edge/mtib-server.md`](../edge/mtib-server.md) — the gRPC server polled by `services/devices/mtib_observability.py`.
- [`../../prisma/schema-overview.md`](../../prisma/schema-overview.md) — DB models referenced by the handlers.
- [`../../deploy/secrets.md`](../../deploy/secrets.md) — credential names + sources for the env vars above.
- [`../../product-domains/builds.md`](../../product-domains/builds.md) — end-to-end build flow.
- [`../../product-domains/validation.md`](../../product-domains/validation.md), [`../../product-domains/manufacturing.md`](../../product-domains/manufacturing.md), [`../../product-domains/fixtures.md`](../../product-domains/fixtures.md), [`../../product-domains/users-rbac.md`](../../product-domains/users-rbac.md) — concept-oriented views of the routes here.
- [`../../../rules/auth-defaults.md`](../../../rules/auth-defaults.md), [`../../../rules/audit-logging.md`](../../../rules/audit-logging.md), [`../../../rules/all-three-envs.md`](../../../rules/all-three-envs.md), [`../../../rules/prisma-flow.md`](../../../rules/prisma-flow.md).

**v0.10.2** (2026-05-14): backend log + error strings that referenced 'fixture design' (lowercase) were renamed to 'TestBed design' for consistency. Includes `Fixture design not found` 404 message and the CRUD-handler docstrings/log lines in `api/v2/fixtures/designs.py` and `api/v2/products/test_packages.py`.
