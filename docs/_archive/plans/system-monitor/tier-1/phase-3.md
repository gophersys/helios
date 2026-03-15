# Phase 3 — Backend: API Routes + Router Registration

## Objective

Create the REST endpoints under `/v2/system/` that expose the service layer from Phase 2, then register them in the main router.

---

## 1. Create `src/api/v2/system/__init__.py`

Empty file.

---

## 2. Create `src/api/v2/system/cluster.py`

```python
from flask import jsonify

from src.lib.decorators import require_permissions
from src.lib.errors import internal_error
from src.lib.permissions import Permissions
from src.lib.types import ApiResponse
from src.services.kubernetes.cluster import get_cluster_info, list_namespaces


@require_permissions(Permissions.ADMIN_SYSTEM_VIEW)
def get_cluster():
    try:
        data = get_cluster_info()
        return jsonify(ApiResponse.ok(data).to_dict()), 200
    except Exception as e:
        return internal_error(f"Failed to get cluster info: {str(e)}")


@require_permissions(Permissions.ADMIN_SYSTEM_VIEW)
def get_namespaces():
    try:
        data = list_namespaces()
        return jsonify(ApiResponse.ok(data).to_dict()), 200
    except Exception as e:
        return internal_error(f"Failed to list namespaces: {str(e)}")
```

---

## 3. Create `src/api/v2/system/nodes.py`

```python
from flask import jsonify

from src.lib.decorators import require_permissions
from src.lib.errors import not_found, internal_error
from src.lib.permissions import Permissions
from src.lib.types import ApiResponse
from src.services.kubernetes import nodes as nodes_svc


@require_permissions(Permissions.ADMIN_SYSTEM_VIEW)
def list_nodes():
    try:
        data = nodes_svc.list_nodes()
        return jsonify(ApiResponse.ok(data).to_dict()), 200
    except Exception as e:
        return internal_error(f"Failed to list nodes: {str(e)}")


@require_permissions(Permissions.ADMIN_SYSTEM_VIEW)
def get_node(node_name: str):
    try:
        data = nodes_svc.get_node(node_name)
        if data is None:
            return not_found("Node not found")
        return jsonify(ApiResponse.ok(data).to_dict()), 200
    except Exception as e:
        return internal_error(f"Failed to get node: {str(e)}")
```

---

## 4. Create `src/api/v2/system/events.py`

```python
from flask import jsonify, request

from src.lib.decorators import require_permissions
from src.lib.errors import internal_error
from src.lib.permissions import Permissions
from src.lib.types import ApiResponse
from src.services.kubernetes.events import list_events


@require_permissions(Permissions.ADMIN_SYSTEM_VIEW)
def get_events():
    namespace = request.args.get("namespace", None)
    limit = request.args.get("limit", 100, type=int)
    limit = min(limit, 500)  # Cap at 500

    try:
        data = list_events(namespace=namespace, limit=limit)
        return jsonify(ApiResponse.ok(data).to_dict()), 200
    except Exception as e:
        return internal_error(f"Failed to list events: {str(e)}")
```

---

## 5. Modify `src/api/v2/router.py`

Add the import block and route registrations. The router uses a `v2` Blueprint with `url_prefix="/v2"`, so paths here omit the `/v2` prefix.

**Imports** (add near the top with other v2 imports):

```python
from .system.cluster import get_cluster, get_namespaces
from .system.nodes import list_nodes, get_node
from .system.events import get_events
```

**Route registrations** (add inside `register_v2_routes` function, before `server.register_blueprint(v2)`):

```python
# ── System Monitor ──────────────────────────────────────────
v2.add_url_rule("/system/cluster", view_func=get_cluster, methods=["GET"])
v2.add_url_rule("/system/namespaces", view_func=get_namespaces, methods=["GET"])
v2.add_url_rule("/system/nodes", view_func=list_nodes, methods=["GET"])
v2.add_url_rule("/system/nodes/<node_name>", view_func=get_node, methods=["GET"])
v2.add_url_rule("/system/events", view_func=get_events, methods=["GET"])
```

---

## Verification

1. All files compile: `python3 -m py_compile` on each
2. Backend starts without error
3. Test endpoints with curl (requires valid auth token):
   - `curl -H "Authorization: Bearer $TOKEN" http://localhost:9001/v2/system/cluster`
   - `curl -H "Authorization: Bearer $TOKEN" http://localhost:9001/v2/system/namespaces`
   - `curl -H "Authorization: Bearer $TOKEN" http://localhost:9001/v2/system/nodes`
   - `curl -H "Authorization: Bearer $TOKEN" http://localhost:9001/v2/system/events`

---

## Overview Update

```
- [x] Phase 3 — Backend: API routes + router registration
```
