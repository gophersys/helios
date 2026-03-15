# System Monitor — Master Overview

## Purpose

This document is the **rebase anchor** for the System Monitor feature. After completing each tier, the implementing agent should re-read this document, compare expected state vs actual state, and update the tier plans if implementation revealed necessary changes.

---

## Critical Corrections (Read First)

The following corrections apply across all tier plan documents. Read these before implementing any phase.

### 1. Frontend paths

All plan documents reference `apps/frontend/concord-app/src/app/...` or short paths like `src/app/...`. The correct frontend root is:
```
apps/frontend/concord-app/src/app/
```
When a plan says "Create `src/app/pages/system/overview.tsx`", the full path is `apps/frontend/concord-app/src/app/pages/system/overview.tsx`.

### 2. Route registration pattern

All backend phase-3 documents use `server.add_url_rule("/v2/system/...")`. This is **wrong**. The router uses a Blueprint with `url_prefix="/v2"`:
```python
v2 = Blueprint("v2", __name__, url_prefix="/v2")
```
The correct pattern is:
```python
v2.add_url_rule("/system/cluster", view_func=get_cluster, methods=["GET"])
```
Note the path is `/system/cluster` (without `/v2` prefix) and the object is `v2` (not `server`).

### 3. Error response pattern

Plan documents use `ApiResponse.error("string message")`. The actual `ApiResponse.error()` expects `ErrorDetail` objects, not strings. Use the helpers from `src/lib/errors.py` instead:
```python
from src.lib.errors import internal_error, bad_request, not_found

# Instead of: return jsonify(ApiResponse.error(f"Failed: {e}").to_dict()), 500
# Use:        return internal_error(f"Failed: {str(e)}")
```
The `ApiResponse.ok(data).to_dict()` pattern for success responses IS correct. Only the error pattern needs this fix.

### 4. API response shape

The API contract examples show `{ "ok": true, "data": {...} }`. The actual response shape is `{ "data": {...}, "errors": [] }`. There is no `"ok"` field. The frontend code in the plans correctly accesses `.data` so this is a documentation-only issue.

### 5. SidebarLink needs `onDoubleClick` prop

The `SidebarLink` component requires an `onDoubleClick` prop. The plan in Tier 1 Phase 4 omits it. The correct usage is:
```tsx
<SidebarLink to="/system" icon={Monitor} label="System" collapsed={collapsed} onDoubleClick={onToggle} />
```

### 6. `get_k8s_client()` already exists

Tier 1 Phase 1 proposes adding `get_client()` to `client.py`. This is redundant — `get_k8s_client()` already exists. Skip creating `get_client()` and use `get_k8s_client()` everywhere (which the Tier 3 code already does).

### 7. `socket.io-client` must be installed

Before Tier 2 Phase 5, install the SocketIO client:
```bash
yarn add socket.io-client
```
Before Tier 3 Phase 4:
```bash
yarn add @xterm/xterm @xterm/addon-fit
```

### 8. SocketIO authentication

The SocketIO handlers in Tier 2 Phase 4 and Tier 3 Phase 3 have no authentication. Add a `connect` handler that validates the token:
```python
@socketio.on("connect", namespace="/system")
def handle_connect(auth):
    token = auth.get("token") if auth else None
    if not token:
        return False  # Reject connection
    # Validate token using your auth service
```

### 9. ResourceTable keyFn signature

Tier 1 Phase 6's `events-list.tsx` passes `(e, i) => ...` to `keyFn`, but `ResourceTable` types `keyFn` as `(item: T) => string`. Either update `ResourceTable`'s type to `(item: T, index: number) => string` and pass `index` in the `.map()`, or use a composite key without the index.

---

## What is the System Monitor?

A web-based Kubernetes cluster viewer embedded in the Concord admin section at `/system`. It gives admins operational visibility and super admins operational control — like k9s, but styled natively with the app's design system and controlled by the app's permission model.

---

## Tier Summary

| Tier | Scope | Backend | Frontend | Status |
|------|-------|---------|----------|--------|
| **Tier 1** | Cluster Overview & Nodes | Permissions, cache, serializers, cluster/node/event services, 5 API endpoints | System page layout, shared components, overview dashboard, node list/detail, events feed | `[ ]` |
| **Tier 2** | Resource Browser & Logs | Pod/deployment/service/job/configmap serializers & services, 17 REST endpoints, SocketIO log streaming | Pod/deployment/service/job/config pages, log viewer, action buttons (scale/restart/delete) | `[ ]` |
| **Tier 3** | Advanced Operations | Generic resource YAML service, RBAC service, pod exec SocketIO, 8 REST endpoints | Terminal (xterm.js), YAML viewer/editor, resource YAML modal, RBAC viewer | `[ ]` |

---

## Architecture Overview

### Backend File Tree (when all tiers are complete)

```
apps/backend/http-api/
  src/
    lib/
      permissions.py                  — MODIFY (add System.View, System.Manage)

    services/kubernetes/
      client.py                       — MODIFY (add get_rbac_v1_api)
      cache.py                        — CREATE (Tier 1)
      serializers.py                  — CREATE (Tier 1), EXTEND (Tier 2, 3)
      cluster.py                      — CREATE (Tier 1)
      nodes.py                        — CREATE (Tier 1)
      events.py                       — CREATE (Tier 1)
      pods.py                         — CREATE (Tier 2)
      deployments.py                  — CREATE (Tier 2)
      services_k8s.py                 — CREATE (Tier 2)
      jobs.py                         — CREATE (Tier 2)
      configmaps.py                   — CREATE (Tier 2)
      resources.py                    — CREATE (Tier 3)
      rbac.py                         — CREATE (Tier 3)

    api/v2/system/
      __init__.py                     — CREATE (Tier 1)
      cluster.py                      — CREATE (Tier 1)
      nodes.py                        — CREATE (Tier 1)
      events.py                       — CREATE (Tier 1)
      pods.py                         — CREATE (Tier 2)
      deployments.py                  — CREATE (Tier 2)
      services_api.py                 — CREATE (Tier 2)
      jobs.py                         — CREATE (Tier 2)
      config.py                       — CREATE (Tier 2)
      logs.py                         — CREATE (Tier 2)
      resources.py                    — CREATE (Tier 3)
      rbac.py                         — CREATE (Tier 3)
      exec.py                         — CREATE (Tier 3)

    api/v2/router.py                  — MODIFY (all tiers)
```

### Frontend File Tree (when all tiers are complete)

```
apps/frontend/concord-app/src/app/
  components/system/
    metric-card.tsx                   — CREATE (Tier 1)
    status-indicator.tsx              — CREATE (Tier 1)
    resource-age.tsx                  — CREATE (Tier 1)
    namespace-selector.tsx            — CREATE (Tier 1)
    resource-table.tsx                — CREATE (Tier 1)
    log-viewer.tsx                    — CREATE (Tier 2)
    action-button.tsx                 — CREATE (Tier 2)
    yaml-viewer.tsx                   — CREATE (Tier 3)
    yaml-editor.tsx                   — CREATE (Tier 3)
    resource-yaml-dialog.tsx          — CREATE (Tier 3)
    terminal.tsx                      — CREATE (Tier 3)

  pages/system/
    system-page.tsx                   — CREATE (Tier 1), MODIFY (Tier 2, 3)
    overview.tsx                      — CREATE (Tier 1)
    nodes-list.tsx                    — CREATE (Tier 1)
    node-detail.tsx                   — CREATE (Tier 1)
    events-list.tsx                   — CREATE (Tier 1)
    pods-list.tsx                     — CREATE (Tier 2)
    pod-detail.tsx                    — CREATE (Tier 2), MODIFY (Tier 3)
    deployments-list.tsx              — CREATE (Tier 2)
    deployment-detail.tsx             — CREATE (Tier 2)
    services-list.tsx                 — CREATE (Tier 2)
    service-detail.tsx                — CREATE (Tier 2)
    jobs-list.tsx                     — CREATE (Tier 2)
    job-detail.tsx                    — CREATE (Tier 2)
    config-list.tsx                   — CREATE (Tier 2)
    rbac.tsx                          — CREATE (Tier 3)

  app.tsx                             — MODIFY (Tier 1, 2, 3)
  components/sidebar.tsx              — MODIFY (Tier 1)
```

---

## Permissions

| Permission | Type | Used by |
|---|---|---|
| `Concord.Admin.System.View` | Read-only | All tiers — list/get resources, stream logs, view YAML, view RBAC |
| `Concord.Admin.System.Manage` | Write | Tier 2+ — scale/restart deployments, delete pods/jobs, pod exec, apply YAML |

Both permissions must be added to `src/lib/permissions.py` in Tier 1 Phase 1.

---

## API Endpoint Summary

### Tier 1 (5 endpoints)

| Method | Path | Permission |
|--------|------|------------|
| GET | `/v2/system/cluster` | View |
| GET | `/v2/system/namespaces` | View |
| GET | `/v2/system/nodes` | View |
| GET | `/v2/system/nodes/<name>` | View |
| GET | `/v2/system/events` | View |

### Tier 2 (17 endpoints + SocketIO)

| Method | Path | Permission |
|--------|------|------------|
| GET | `/v2/system/pods` | View |
| GET | `/v2/system/pods/<ns>/<name>` | View |
| DELETE | `/v2/system/pods/<ns>/<name>` | Manage |
| GET | `/v2/system/pods/<ns>/<name>/containers` | View |
| GET | `/v2/system/deployments` | View |
| GET | `/v2/system/deployments/<ns>/<name>` | View |
| POST | `/v2/system/deployments/<ns>/<name>/scale` | Manage |
| POST | `/v2/system/deployments/<ns>/<name>/restart` | Manage |
| GET | `/v2/system/services` | View |
| GET | `/v2/system/services/<ns>/<name>` | View |
| GET | `/v2/system/jobs` | View |
| GET | `/v2/system/jobs/<ns>/<name>` | View |
| DELETE | `/v2/system/jobs/<ns>/<name>` | Manage |
| GET | `/v2/system/configmaps` | View |
| GET | `/v2/system/configmaps/<ns>/<name>` | View |
| GET | `/v2/system/secrets` | View |
| GET | `/v2/system/secrets/<ns>/<name>` | View |
| SocketIO | `/system` — `subscribe_logs` / `log_line` | View |

### Tier 3 (8 endpoints + SocketIO)

| Method | Path | Permission |
|--------|------|------------|
| GET | `/v2/system/resources/<kind>/<ns>/<name>` | View |
| PUT | `/v2/system/resources/<kind>/<ns>/<name>` | Manage |
| DELETE | `/v2/system/resources/<kind>/<ns>/<name>` | Manage |
| GET | `/v2/system/rbac/roles` | View |
| GET | `/v2/system/rbac/clusterroles` | View |
| GET | `/v2/system/rbac/bindings` | View |
| GET | `/v2/system/rbac/clusterrolebindings` | View |
| GET | `/v2/system/rbac/serviceaccounts` | View |
| SocketIO | `/system` — `exec_start` / `exec_input` / `exec_output` | Manage |

---

## Frontend Navigation

The system page uses a pill-style tab bar with horizontal scroll. The tabs expand as tiers are implemented:

- **After Tier 1:** Overview, Nodes, Events
- **After Tier 2:** Overview, Nodes, Pods, Deployments, Services, Jobs, Config, Events
- **After Tier 3:** Overview, Nodes, Pods, Deployments, Services, Jobs, Config, RBAC, Events

---

## Key Design Decisions

1. **Serializers as the boundary.** All K8s Python objects are converted to plain dicts in `serializers.py`. Nothing else touches K8s object internals. This makes testing and refactoring easy.

2. **TTL cache for read endpoints.** The cache module prevents excessive K8s API calls during polling. Default TTL is 5 seconds — short enough for near-real-time, long enough to avoid hammering the API when multiple clients poll simultaneously.

3. **SocketIO for real-time.** Log streaming and pod exec both use the existing Flask-SocketIO infrastructure under the `/system` namespace. No additional WebSocket libraries needed.

4. **Namespace-scoped URL pattern.** Resources that are namespace-scoped use `/v2/system/<resource>/<namespace>/<name>` instead of query parameters for the detail endpoints. This keeps URLs RESTful and bookmarkable.

5. **Shared components.** `ResourceTable`, `StatusIndicator`, `MetricCard`, `NamespaceSelector`, and `ResourceAge` are used across all system pages. Build them once in Tier 1 Phase 4, reuse everywhere.

6. **Permission-gated actions.** Mutating actions (scale, restart, delete, exec, YAML edit) check `System.Manage` on both backend (via `@require_permissions` decorator) and frontend (via `hasPermission` check hiding the UI elements).

7. **No YAML editing for secrets.** While the generic YAML endpoint supports secrets, the frontend doesn't show decoded secret values — only masked previews. This is intentional for security.

---

## Rebase Protocol

After completing each tier:

1. **Read this document** to understand expected state
2. **Verify all endpoints** listed above are working
3. **Verify all frontend pages** are rendering correctly
4. **Check the tier overview** checklist — all phases should be `[x]`
5. **Update this document** if implementation required changes:
   - New endpoints not in the plan
   - Changed URL patterns
   - Additional components needed
   - Permissions changes
   - Architecture deviations
6. **Mark the tier as complete** in the Tier Summary table above

---

## Plan Locations

```
docs/v2/plans/system-monitor/
  overview.md              ← you are here (master rebase anchor)
  tier-1/
    overview.md            — architecture, API contracts, component tree, phase checklist
    phase-1.md             — backend: permissions, cache, serializers
    phase-2.md             — backend: cluster, node, event services
    phase-3.md             — backend: API routes + router registration
    phase-4.md             — frontend: system page layout, shared components, routing, nav
    phase-5.md             — frontend: cluster overview dashboard
    phase-6.md             — frontend: nodes list/detail + events feed
  tier-2/
    overview.md            — architecture, API contracts, component tree, phase checklist
    phase-1.md             — backend: serializers for all Tier 2 resources
    phase-2.md             — backend: service modules
    phase-3.md             — backend: REST API routes + mutating actions
    phase-4.md             — backend: pod log streaming via SocketIO
    phase-5.md             — frontend: pod pages + log viewer + tab expansion
    phase-6.md             — frontend: deployments, services, jobs, config pages
  tier-3/
    overview.md            — architecture, API contracts, component tree, phase checklist
    phase-1.md             — backend: generic resource YAML get/apply service
    phase-2.md             — backend: RBAC service module
    phase-3.md             — backend: API routes for resources + RBAC, pod exec SocketIO
    phase-4.md             — frontend: YAML viewer/editor components + resource YAML dialog
    phase-5.md             — frontend: terminal component + pod exec integration
    phase-6.md             — frontend: RBAC viewer page + final polish
```
