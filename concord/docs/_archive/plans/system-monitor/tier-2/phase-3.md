# Phase 3 — Backend: REST API Routes + Mutating Actions

> **Corrections:** See `docs/v2/plans/system-monitor/overview.md` "Critical Corrections" section. In the code below, replace all `return jsonify(ApiResponse.error("...").to_dict()), 500` with `return internal_error("...")` (import from `src.lib.errors`). Same pattern for bad_request/not_found. Route registrations use `v2.add_url_rule("/system/...")` not `server.add_url_rule("/v2/system/...")`.

## Objective

Create the REST endpoints for all Tier 2 resource types and register them in the router. Read endpoints use `System.View`, mutating endpoints use `System.Manage`.

---

## 1. Create `src/api/v2/system/pods.py`

```python
from flask import jsonify, request

from src.lib.decorators import require_permissions
from src.lib.errors import not_found
from src.lib.permissions import Permissions
from src.lib.types import ApiResponse
from src.services.kubernetes import pods as pods_svc


@require_permissions(Permissions.ADMIN_SYSTEM_VIEW)
def list_pods():
    namespace = request.args.get("namespace", None)
    try:
        data = pods_svc.list_pods(namespace=namespace)
        return jsonify(ApiResponse.ok(data).to_dict()), 200
    except Exception as e:
        return jsonify(ApiResponse.error(f"Failed to list pods: {str(e)}").to_dict()), 500


@require_permissions(Permissions.ADMIN_SYSTEM_VIEW)
def get_pod(namespace: str, name: str):
    try:
        data = pods_svc.get_pod(namespace, name)
        if data is None:
            return not_found("Pod not found")
        return jsonify(ApiResponse.ok(data).to_dict()), 200
    except Exception as e:
        return jsonify(ApiResponse.error(f"Failed to get pod: {str(e)}").to_dict()), 500


@require_permissions(Permissions.ADMIN_SYSTEM_MANAGE)
def delete_pod(namespace: str, name: str):
    try:
        success = pods_svc.delete_pod(namespace, name)
        if not success:
            return jsonify(ApiResponse.error("Failed to delete pod").to_dict()), 500
        return jsonify(ApiResponse.ok({"deleted": True}).to_dict()), 200
    except Exception as e:
        return jsonify(ApiResponse.error(f"Failed to delete pod: {str(e)}").to_dict()), 500
```

---

## 2. Create `src/api/v2/system/deployments.py`

```python
from flask import jsonify, request

from src.lib.decorators import require_permissions
from src.lib.errors import bad_request, not_found
from src.lib.permissions import Permissions
from src.lib.types import ApiResponse
from src.services.kubernetes import deployments as dep_svc


@require_permissions(Permissions.ADMIN_SYSTEM_VIEW)
def list_deployments():
    namespace = request.args.get("namespace", None)
    try:
        data = dep_svc.list_deployments(namespace=namespace)
        return jsonify(ApiResponse.ok(data).to_dict()), 200
    except Exception as e:
        return jsonify(ApiResponse.error(f"Failed to list deployments: {str(e)}").to_dict()), 500


@require_permissions(Permissions.ADMIN_SYSTEM_VIEW)
def get_deployment(namespace: str, name: str):
    try:
        data = dep_svc.get_deployment(namespace, name)
        if data is None:
            return not_found("Deployment not found")
        return jsonify(ApiResponse.ok(data).to_dict()), 200
    except Exception as e:
        return jsonify(ApiResponse.error(f"Failed to get deployment: {str(e)}").to_dict()), 500


@require_permissions(Permissions.ADMIN_SYSTEM_MANAGE)
def scale_deployment(namespace: str, name: str):
    body = request.get_json()
    if not body or "replicas" not in body:
        return bad_request("Missing 'replicas' field")

    replicas = body["replicas"]
    if not isinstance(replicas, int) or replicas < 0:
        return bad_request("'replicas' must be a non-negative integer")

    try:
        success = dep_svc.scale_deployment(namespace, name, replicas)
        if not success:
            return jsonify(ApiResponse.error("Failed to scale deployment").to_dict()), 500
        return jsonify(ApiResponse.ok({"scaled": True, "replicas": replicas}).to_dict()), 200
    except Exception as e:
        return jsonify(ApiResponse.error(f"Failed to scale deployment: {str(e)}").to_dict()), 500


@require_permissions(Permissions.ADMIN_SYSTEM_MANAGE)
def restart_deployment(namespace: str, name: str):
    try:
        success = dep_svc.restart_deployment(namespace, name)
        if not success:
            return jsonify(ApiResponse.error("Failed to restart deployment").to_dict()), 500
        return jsonify(ApiResponse.ok({"restarted": True}).to_dict()), 200
    except Exception as e:
        return jsonify(ApiResponse.error(f"Failed to restart deployment: {str(e)}").to_dict()), 500
```

---

## 3. Create `src/api/v2/system/services_api.py`

```python
from flask import jsonify, request

from src.lib.decorators import require_permissions
from src.lib.errors import not_found
from src.lib.permissions import Permissions
from src.lib.types import ApiResponse
from src.services.kubernetes import services_k8s as svc_svc


@require_permissions(Permissions.ADMIN_SYSTEM_VIEW)
def list_services():
    namespace = request.args.get("namespace", None)
    try:
        data = svc_svc.list_services(namespace=namespace)
        return jsonify(ApiResponse.ok(data).to_dict()), 200
    except Exception as e:
        return jsonify(ApiResponse.error(f"Failed to list services: {str(e)}").to_dict()), 500


@require_permissions(Permissions.ADMIN_SYSTEM_VIEW)
def get_service(namespace: str, name: str):
    try:
        data = svc_svc.get_service(namespace, name)
        if data is None:
            return not_found("Service not found")
        return jsonify(ApiResponse.ok(data).to_dict()), 200
    except Exception as e:
        return jsonify(ApiResponse.error(f"Failed to get service: {str(e)}").to_dict()), 500
```

---

## 4. Create `src/api/v2/system/jobs.py`

```python
from flask import jsonify, request

from src.lib.decorators import require_permissions
from src.lib.errors import not_found
from src.lib.permissions import Permissions
from src.lib.types import ApiResponse
from src.services.kubernetes import jobs as jobs_svc


@require_permissions(Permissions.ADMIN_SYSTEM_VIEW)
def list_system_jobs():
    namespace = request.args.get("namespace", None)
    try:
        data = jobs_svc.list_jobs(namespace=namespace)
        return jsonify(ApiResponse.ok(data).to_dict()), 200
    except Exception as e:
        return jsonify(ApiResponse.error(f"Failed to list jobs: {str(e)}").to_dict()), 500


@require_permissions(Permissions.ADMIN_SYSTEM_VIEW)
def get_system_job(namespace: str, name: str):
    try:
        data = jobs_svc.get_job(namespace, name)
        if data is None:
            return not_found("Job not found")
        return jsonify(ApiResponse.ok(data).to_dict()), 200
    except Exception as e:
        return jsonify(ApiResponse.error(f"Failed to get job: {str(e)}").to_dict()), 500


@require_permissions(Permissions.ADMIN_SYSTEM_MANAGE)
def delete_system_job(namespace: str, name: str):
    try:
        success = jobs_svc.delete_job(namespace, name)
        if not success:
            return jsonify(ApiResponse.error("Failed to delete job").to_dict()), 500
        return jsonify(ApiResponse.ok({"deleted": True}).to_dict()), 200
    except Exception as e:
        return jsonify(ApiResponse.error(f"Failed to delete job: {str(e)}").to_dict()), 500
```

---

## 5. Create `src/api/v2/system/config.py`

```python
from flask import jsonify, request

from src.lib.decorators import require_permissions
from src.lib.errors import not_found
from src.lib.permissions import Permissions
from src.lib.types import ApiResponse
from src.services.kubernetes import configmaps as config_svc


@require_permissions(Permissions.ADMIN_SYSTEM_VIEW)
def list_configmaps():
    namespace = request.args.get("namespace", None)
    try:
        data = config_svc.list_configmaps(namespace=namespace)
        return jsonify(ApiResponse.ok(data).to_dict()), 200
    except Exception as e:
        return jsonify(ApiResponse.error(f"Failed to list configmaps: {str(e)}").to_dict()), 500


@require_permissions(Permissions.ADMIN_SYSTEM_VIEW)
def get_configmap(namespace: str, name: str):
    try:
        data = config_svc.get_configmap(namespace, name)
        if data is None:
            return not_found("ConfigMap not found")
        return jsonify(ApiResponse.ok(data).to_dict()), 200
    except Exception as e:
        return jsonify(ApiResponse.error(f"Failed to get configmap: {str(e)}").to_dict()), 500


@require_permissions(Permissions.ADMIN_SYSTEM_VIEW)
def list_secrets():
    namespace = request.args.get("namespace", None)
    try:
        data = config_svc.list_secrets(namespace=namespace)
        return jsonify(ApiResponse.ok(data).to_dict()), 200
    except Exception as e:
        return jsonify(ApiResponse.error(f"Failed to list secrets: {str(e)}").to_dict()), 500


@require_permissions(Permissions.ADMIN_SYSTEM_VIEW)
def get_secret(namespace: str, name: str):
    try:
        data = config_svc.get_secret(namespace, name)
        if data is None:
            return not_found("Secret not found")
        return jsonify(ApiResponse.ok(data).to_dict()), 200
    except Exception as e:
        return jsonify(ApiResponse.error(f"Failed to get secret: {str(e)}").to_dict()), 500
```

---

## 6. Modify `src/api/v2/router.py`

Add imports and route registrations.

**Imports** (add near existing system imports):

```python
from .system.pods import list_pods, get_pod, delete_pod
from .system.deployments import list_deployments, get_deployment, scale_deployment, restart_deployment
from .system.services_api import list_services, get_service
from .system.jobs import list_system_jobs, get_system_job, delete_system_job
from .system.config import list_configmaps, get_configmap, list_secrets, get_secret
```

**Route registrations** (add after existing system routes, before `server.register_blueprint(v2)`):

```python
# ── System Monitor: Resources ───────────────────────────────
v2.add_url_rule("/system/pods", view_func=list_pods, methods=["GET"])
v2.add_url_rule("/system/pods/<namespace>/<name>", view_func=get_pod, methods=["GET"])
v2.add_url_rule("/system/pods/<namespace>/<name>", view_func=delete_pod, methods=["DELETE"])

v2.add_url_rule("/system/deployments", view_func=list_deployments, methods=["GET"])
v2.add_url_rule("/system/deployments/<namespace>/<name>", view_func=get_deployment, methods=["GET"])
v2.add_url_rule("/system/deployments/<namespace>/<name>/scale", view_func=scale_deployment, methods=["POST"])
v2.add_url_rule("/system/deployments/<namespace>/<name>/restart", view_func=restart_deployment, methods=["POST"])

v2.add_url_rule("/system/services", view_func=list_services, methods=["GET"])
v2.add_url_rule("/system/services/<namespace>/<name>", view_func=get_service, methods=["GET"])

v2.add_url_rule("/system/jobs", view_func=list_system_jobs, methods=["GET"])
v2.add_url_rule("/system/jobs/<namespace>/<name>", view_func=get_system_job, methods=["GET"])
v2.add_url_rule("/system/jobs/<namespace>/<name>", view_func=delete_system_job, methods=["DELETE"])

v2.add_url_rule("/system/configmaps", view_func=list_configmaps, methods=["GET"])
v2.add_url_rule("/system/configmaps/<namespace>/<name>", view_func=get_configmap, methods=["GET"])
v2.add_url_rule("/system/secrets", view_func=list_secrets, methods=["GET"])
v2.add_url_rule("/system/secrets/<namespace>/<name>", view_func=get_secret, methods=["GET"])
```

---

## Verification

1. `python3 -m py_compile` on all new files
2. Backend starts without error
3. Test endpoints with curl:
   - `curl -H "Authorization: Bearer $TOKEN" http://localhost:9001/v2/system/pods`
   - `curl -H "Authorization: Bearer $TOKEN" http://localhost:9001/v2/system/deployments`
   - `curl -H "Authorization: Bearer $TOKEN" http://localhost:9001/v2/system/services`
   - `curl -H "Authorization: Bearer $TOKEN" http://localhost:9001/v2/system/jobs`
   - `curl -H "Authorization: Bearer $TOKEN" http://localhost:9001/v2/system/configmaps`
   - `curl -H "Authorization: Bearer $TOKEN" http://localhost:9001/v2/system/secrets`

---

## Overview Update

```
- [x] Phase 3 — Backend: REST API routes + mutating actions
```
