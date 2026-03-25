# Backend Overhaul Spec

**Status:** In Progress
**Created:** 2026-03-16
**Scope:** Prisma schema, MinIO storage, backend API restructure, reporter protocol, frontend cleanup

---

## Completed Work

- [x] Prisma schema: 22 models, 13 enums (was 31/19)
- [x] Legacy v1 killed: proxy, in-memory DB, cluster operator, cluster_test protos
- [x] Dead modules: codebases, legacy MTIB, catalog sync, flow page, demo endpoint
- [x] Storage prefixes: 12 → 5
- [x] Reporter: sub-step context manager, multi-device support, `report` fixture
- [x] Handler updates: Session/Fixture/TestStep model changes in validation handlers

---

## Remaining Work

### Phase 6: API Directory Restructure

**Goal:** Module directories match URL prefixes. Every module follows the same file structure.

**Standard module structure:**
```
src/api/v2/<module>/
├── __init__.py
├── types.py           # All request dataclasses with from_json()
├── <entity>.py        # One file per entity/resource
└── shared.py          # Optional: serializers, constants
```

**Directory moves:**

| Current Path | New Path | Reason |
|-------------|----------|--------|
| `catalog/` | `products/` | Route is `/v2/products/` |
| `ci/` | `builds/` | Route is `/v2/builds/` |
| `validation/runs/` | `sessions/` | Route is `/v2/sessions/` |
| `validation/benches/` | → merge into `fixtures/` | Unified Fixture model |
| `validation/designs/` | → merge into `fixtures/` | Fixture designs |
| `validation/queue.py` | → `sessions/queue.py` | Queue creates sessions |
| `validation/scheduler.py` | → `sessions/scheduler.py` | Schedules sessions |
| `validation/tests/` | → `sessions/manual.py` | Manual test trigger |
| `system/{cluster,nodes,pods,deployments,...}` | `kubernetes/` | Route is `/v2/kubernetes/` |
| `system/{info,retention,logs,exec}` | stays `system/` | Route is `/v2/system/` |
| `admin/history.py` | → `system/history.py` | Consolidate under system |
| `observability/` | → `devices/observability.py` | Telemetry under devices |
| `validation/` | DELETE (empty after moves) | Everything moved out |
| `admin/` | DELETE (empty after move) | Merged into system |
| `observability/` | DELETE (empty after move) | Merged into devices |

**Router rewrite:** All URL registrations updated to match new structure. Single `router.py` imports from new locations.

### Phase 7: Permissions + Handler Standardization

**Permission changes:**
- Kill: `benches:view`, `benches:manage`
- Rename: `cluster:view` → `kubernetes:view`, `cluster:manage` → `kubernetes:manage`
- Session endpoints check `validation:run` or `manufacturing:run` based on session type

**Handler standardization checklist (every handler):**
1. `@require_permissions(Permissions.MODULE_ACTION)` decorator
2. Parse request: `data, error = Request.from_json(request.get_json())`
3. Return `bad_request(error)` on parse failure
4. DB operations via `get_db_client()`
5. `log_audit()` on every mutation
6. Return `ApiResponse.ok(data).to_dict()` with correct status code
7. Consistent pagination: `page`, `limit`, `total`, `pages`

**Response codes:**
- 200: GET, PUT/PATCH, DELETE
- 201: POST (create)
- 400: Bad request (validation error)
- 404: Not found
- 409: Conflict (duplicate)

### Phase 8: New Endpoints

**Build intelligence:**
- `POST /v2/builds/import` — Register externally-built artifacts
- `GET /v2/builds/cache?fingerprint=X&productId=Y` — Check build cache
- Cache-on-create in pipeline trigger (fingerprint matching)

**Session management:**
- `POST /v2/sessions/<id>/rerun` — Clone session with optional different pipeline
- `GET /v2/builds/pipelines/<id>/sessions` — Sessions spawned by pipeline

**Filter params on list endpoints:**
- `GET /v2/sessions?type=&productId=&pipelineId=&status=&fixtureId=`
- `GET /v2/fixtures?type=&productId=&status=`
- `GET /v2/builds/pipelines?productId=&status=&branch=`

### Phase 9: Fix Tests

24 failing tests need updates:
- `COMPLETED` → `PASSED`/`FAILED` (new SessionStatus values)
- `resultCount` → `stepCount` (TestResult → TestStep)
- `PAUSED` status gone from SessionStatus
- `testresult` → `teststep` model references
- Import path updates for moved modules

### Phase 10: OpenAPI + Deployment

- Update `docs.py` with new route paths, schemas, tags
- Remove dead env vars from all environments
- Add `GIT_POLLER_ENABLED`, `GIT_POLLER_INTERVAL_S` to config
- Update Helm values for staging + production
- Update Docker COPY paths if directory structure changed

---

## Target Route Map

```
/v2/auth/login                          POST
/v2/auth/me                             GET

/v2/users                               GET, POST
/v2/users/<id>                          GET, PUT, DELETE

/v2/permissions                         GET, POST
/v2/permissions/<id>                    GET, PUT, DELETE
/v2/permissions/available               GET

/v2/api-keys                            GET, POST
/v2/api-keys/<id>                       DELETE

/v2/products                            GET, POST
/v2/products/<id>                       GET, PUT, DELETE
/v2/products/by-slug/<slug>             GET
/v2/products/by-repo/<repo>             GET
/v2/products/<id>/boards                GET, POST
/v2/products/<id>/boards/<bid>          GET, PUT, DELETE
/v2/products/<id>/boards/<bid>/revisions         GET, POST
/v2/products/<id>/boards/<bid>/revisions/<rid>   PUT, DELETE
/v2/products/<id>/firmware              GET, POST
/v2/products/<id>/firmware/<fid>        PUT, DELETE
/v2/products/<id>/firmware/<fid>/download GET
/v2/products/<id>/stages                GET, POST
/v2/products/<id>/stages/<sid>          GET, PUT, DELETE

/v2/chipsets                            GET, POST
/v2/chipsets/<id>                       GET, PUT, DELETE

/v2/builds                              GET, POST
/v2/builds/<id>                         GET, PATCH
/v2/builds/<id>/artifacts               GET, POST
/v2/builds/<id>/artifacts/<aid>/download GET
/v2/builds/<id>/log                     GET
/v2/builds/import                       POST        ★ NEW
/v2/builds/cache                        GET         ★ NEW
/v2/builds/trigger                      POST
/v2/builds/webhooks/bitbucket           POST
/v2/builds/pipelines                    GET, POST
/v2/builds/pipelines/<id>              GET, DELETE
/v2/builds/pipelines/<id>/sessions     GET         ★ NEW
/v2/builds/scripts                      GET, POST
/v2/builds/scripts/<id>                GET, DELETE
/v2/builds/overlays                     GET

/v2/sessions                            GET, POST
/v2/sessions/<id>                       GET
/v2/sessions/<id>/cancel                POST
/v2/sessions/<id>/trigger               POST
/v2/sessions/<id>/rerun                 POST        ★ NEW
/v2/sessions/<id>/executions            GET
/v2/sessions/<id>/artifacts             GET
/v2/sessions/<id>/artifacts/<name>      GET
/v2/sessions/<id>/logs/<file>           GET
/v2/sessions/<id>/manifest              GET
/v2/sessions/<id>/report/start          POST
/v2/sessions/<id>/report/test-start     POST
/v2/sessions/<id>/report/test-result    POST
/v2/sessions/<id>/report/step-start     POST        ★ NEW
/v2/sessions/<id>/report/step-result    POST        ★ NEW
/v2/sessions/<id>/report/log-chunk      POST
/v2/sessions/<id>/report/finish         POST
/v2/sessions/queue                      GET, POST
/v2/sessions/queue/<id>                 GET, PATCH, DELETE
/v2/sessions/queue/<id>/promote         POST
/v2/sessions/queue/stats                GET
/v2/sessions/queue/schedule             POST

/v2/fixtures                            GET, POST
/v2/fixtures/<id>                       GET, PATCH, DELETE
/v2/fixtures/<id>/lock                  POST
/v2/fixtures/<id>/unlock                POST
/v2/fixtures/<id>/profile               GET
/v2/fixtures/<id>/slots                 GET, POST
/v2/fixtures/<id>/slots/<sid>           PATCH, DELETE
/v2/fixtures/<id>/slots/<sid>/assign    POST
/v2/fixtures/designs                    GET, POST
/v2/fixtures/designs/<id>               GET, PUT, DELETE
/v2/fixtures/designs/<id>/profile       GET
/v2/fixtures/discover                   POST

/v2/devices/mtibs                       GET, POST
/v2/devices/mtibs/discover              POST
/v2/devices/mtibs/<id>                  GET, PUT, DELETE
/v2/devices/mtibs/<id>/deploy           POST
/v2/devices/mtibs/<id>/undeploy         POST
/v2/devices/mtibs/<id>/health           POST
/v2/devices/mtibs/<id>/power            GET
/v2/devices/mtibs/<id>/gpio             GET
/v2/devices/mtibs/<id>/uart             GET
/v2/devices/mtibs/<id>/system           GET
/v2/devices/icle                        GET
/v2/devices/icle/<id>                   GET, PUT, DELETE
/v2/devices/icle/<id>/heartbeat         POST
/v2/devices/icle/<id>/config            PUT
/v2/devices/icle/<id>/ota               POST
/v2/devices/icle/<id>/logs              GET, POST

/v2/kubernetes/info                     GET
/v2/kubernetes/namespaces               GET
/v2/kubernetes/nodes                    GET
/v2/kubernetes/nodes/<name>             GET
/v2/kubernetes/pods                     GET
/v2/kubernetes/pods/<ns>/<name>         GET, DELETE
/v2/kubernetes/pods/<ns>/<name>/logs    GET
/v2/kubernetes/deployments              GET
/v2/kubernetes/deployments/<ns>/<name>  GET
/v2/kubernetes/deployments/<ns>/<name>/scale    POST
/v2/kubernetes/deployments/<ns>/<name>/restart  POST
/v2/kubernetes/services                 GET
/v2/kubernetes/services/<ns>/<name>     GET
/v2/kubernetes/jobs                     GET
/v2/kubernetes/jobs/<ns>/<name>         GET, DELETE
/v2/kubernetes/configmaps/<ns>          GET
/v2/kubernetes/configmaps/<ns>/<name>   GET
/v2/kubernetes/secrets/<ns>             GET
/v2/kubernetes/secrets/<ns>/<name>      GET
/v2/kubernetes/rbac/roles               GET
/v2/kubernetes/rbac/cluster-roles       GET
/v2/kubernetes/rbac/role-bindings       GET
/v2/kubernetes/rbac/cluster-role-bindings GET
/v2/kubernetes/rbac/service-accounts    GET
/v2/kubernetes/resources/<ns>/<kind>/<name>  GET, PUT, DELETE

/v2/system/info                         GET
/v2/system/history                      GET
/v2/system/history/<id>                 GET
/v2/system/retention/cleanup            POST
/v2/system/retention/storage            GET

/v2/healthcheck                         GET
/v2/docs                                GET
/v2/openapi.json                        GET
```

## Permissions (Final)

```
products:view, products:manage
builds:view, builds:trigger, builds:manage
validation:view, validation:run, validation:manage
manufacturing:view, manufacturing:run, manufacturing:manage
fixtures:view, fixtures:manage
devices:view, devices:manage
kubernetes:view, kubernetes:manage
users:view, users:manage
permissions:manage
api-keys:view, api-keys:manage
system:view, system:manage
```

24 permissions (was 24, 2 killed, 2 renamed).
