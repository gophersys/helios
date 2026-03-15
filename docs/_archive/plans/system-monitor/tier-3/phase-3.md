# Phase 3 — Backend: API Routes for Resources, RBAC, and Pod Exec

> **Corrections:** See `docs/v2/plans/system-monitor/overview.md` "Critical Corrections" section. In the code below, replace all `return jsonify(ApiResponse.error("...").to_dict()), 500` with `return internal_error("...")` (import from `src.lib.errors`). Route registrations use `v2.add_url_rule("/system/...")` not `server.add_url_rule("/v2/system/...")`.

## Objective

Create REST endpoints for generic resource YAML and RBAC, and add SocketIO handlers for interactive pod exec. Register everything in the router.

---

## 1. Create `src/api/v2/system/resources.py`

```python
from flask import jsonify, request

from src.lib.decorators import require_permissions
from src.lib.errors import bad_request, not_found
from src.lib.permissions import Permissions
from src.lib.types import ApiResponse
from src.services.kubernetes import resources as res_svc


@require_permissions(Permissions.ADMIN_SYSTEM_VIEW)
def get_resource_yaml(kind: str, namespace: str, name: str):
    try:
        data = res_svc.get_resource_yaml(kind, namespace, name)
        if data is None:
            return not_found(f"{kind} not found")
        return jsonify(ApiResponse.ok(data).to_dict()), 200
    except ValueError as e:
        return bad_request(str(e))
    except Exception as e:
        return jsonify(ApiResponse.error(f"Failed to get resource: {str(e)}").to_dict()), 500


@require_permissions(Permissions.ADMIN_SYSTEM_MANAGE)
def apply_resource_yaml(kind: str, namespace: str, name: str):
    body = request.get_json()
    if not body or "yaml" not in body:
        return bad_request("Missing 'yaml' field")

    try:
        data = res_svc.apply_resource_yaml(kind, namespace, name, body["yaml"])
        return jsonify(ApiResponse.ok(data).to_dict()), 200
    except ValueError as e:
        return bad_request(str(e))
    except RuntimeError as e:
        return jsonify(ApiResponse.error(str(e)).to_dict()), 422
    except Exception as e:
        return jsonify(ApiResponse.error(f"Failed to apply resource: {str(e)}").to_dict()), 500


@require_permissions(Permissions.ADMIN_SYSTEM_MANAGE)
def delete_resource(kind: str, namespace: str, name: str):
    try:
        success = res_svc.delete_resource(kind, namespace, name)
        if not success:
            return jsonify(ApiResponse.error("Failed to delete resource").to_dict()), 500
        return jsonify(ApiResponse.ok({"deleted": True}).to_dict()), 200
    except ValueError as e:
        return bad_request(str(e))
    except Exception as e:
        return jsonify(ApiResponse.error(f"Failed to delete resource: {str(e)}").to_dict()), 500
```

---

## 2. Create `src/api/v2/system/rbac.py`

```python
from flask import jsonify, request

from src.lib.decorators import require_permissions
from src.lib.permissions import Permissions
from src.lib.types import ApiResponse
from src.services.kubernetes import rbac as rbac_svc


@require_permissions(Permissions.ADMIN_SYSTEM_VIEW)
def list_roles():
    namespace = request.args.get("namespace", None)
    try:
        data = rbac_svc.list_roles(namespace=namespace)
        return jsonify(ApiResponse.ok(data).to_dict()), 200
    except Exception as e:
        return jsonify(ApiResponse.error(f"Failed to list roles: {str(e)}").to_dict()), 500


@require_permissions(Permissions.ADMIN_SYSTEM_VIEW)
def list_cluster_roles():
    try:
        data = rbac_svc.list_cluster_roles()
        return jsonify(ApiResponse.ok(data).to_dict()), 200
    except Exception as e:
        return jsonify(ApiResponse.error(f"Failed to list cluster roles: {str(e)}").to_dict()), 500


@require_permissions(Permissions.ADMIN_SYSTEM_VIEW)
def list_role_bindings():
    namespace = request.args.get("namespace", None)
    try:
        data = rbac_svc.list_role_bindings(namespace=namespace)
        return jsonify(ApiResponse.ok(data).to_dict()), 200
    except Exception as e:
        return jsonify(ApiResponse.error(f"Failed to list role bindings: {str(e)}").to_dict()), 500


@require_permissions(Permissions.ADMIN_SYSTEM_VIEW)
def list_cluster_role_bindings():
    try:
        data = rbac_svc.list_cluster_role_bindings()
        return jsonify(ApiResponse.ok(data).to_dict()), 200
    except Exception as e:
        return jsonify(ApiResponse.error(f"Failed to list cluster role bindings: {str(e)}").to_dict()), 500


@require_permissions(Permissions.ADMIN_SYSTEM_VIEW)
def list_service_accounts():
    namespace = request.args.get("namespace", None)
    try:
        data = rbac_svc.list_service_accounts(namespace=namespace)
        return jsonify(ApiResponse.ok(data).to_dict()), 200
    except Exception as e:
        return jsonify(ApiResponse.error(f"Failed to list service accounts: {str(e)}").to_dict()), 500
```

---

## 3. Create `src/api/v2/system/exec.py`

SocketIO handlers for interactive pod exec using the K8s WebSocket stream API.

```python
import threading

from flask import request
from flask_socketio import SocketIO, emit
from kubernetes.stream import stream as k8s_stream

from src.services.kubernetes.client import get_core_v1_api


# Track active exec sessions
_active_sessions: dict[str, threading.Event] = {}


def register_exec_handlers(socketio: SocketIO):
    """Register SocketIO event handlers for pod exec."""

    @socketio.on("exec_start", namespace="/system")
    def handle_exec_start(data):
        """
        Start an interactive exec session.
        Client sends: { namespace, pod, container, command? }
        """
        ns = data.get("namespace")
        pod = data.get("pod")
        container = data.get("container")
        command = data.get("command", ["/bin/sh"])

        if not ns or not pod or not container:
            emit("exec_error", {"message": "Missing namespace, pod, or container"})
            return

        sid = request.sid
        stop_event = threading.Event()
        _active_sessions[sid] = stop_event

        def run_exec():
            try:
                core = get_core_v1_api()

                # Create the exec stream
                exec_stream = k8s_stream(
                    core.connect_get_namespaced_pod_exec,
                    pod,
                    ns,
                    container=container,
                    command=command if isinstance(command, list) else [command],
                    stderr=True,
                    stdin=True,
                    stdout=True,
                    tty=True,
                    _preload_content=False,
                )

                # Store the stream so input events can write to it
                _active_sessions[f"{sid}:stream"] = exec_stream

                # Read output from the stream
                while exec_stream.is_open() and not stop_event.is_set():
                    exec_stream.update(timeout=1)
                    if exec_stream.peek_stdout():
                        output = exec_stream.read_stdout()
                        socketio.emit("exec_output", {"data": output}, room=sid, namespace="/system")
                    if exec_stream.peek_stderr():
                        output = exec_stream.read_stderr()
                        socketio.emit("exec_output", {"data": output}, room=sid, namespace="/system")

                exec_stream.close()
                socketio.emit("exec_exit", {"code": exec_stream.returncode or 0}, room=sid, namespace="/system")

            except Exception as e:
                socketio.emit("exec_error", {"message": f"Exec error: {str(e)}"}, room=sid, namespace="/system")
            finally:
                _active_sessions.pop(sid, None)
                _active_sessions.pop(f"{sid}:stream", None)

        socketio.start_background_task(run_exec)

    @socketio.on("exec_input", namespace="/system")
    def handle_exec_input(data):
        """Forward keyboard input to the exec stream."""
        sid = request.sid
        exec_stream = _active_sessions.get(f"{sid}:stream")
        if exec_stream and exec_stream.is_open():
            try:
                exec_stream.write_stdin(data.get("data", ""))
            except Exception:
                pass

    @socketio.on("exec_resize", namespace="/system")
    def handle_exec_resize(data):
        """Resize the exec terminal."""
        sid = request.sid
        exec_stream = _active_sessions.get(f"{sid}:stream")
        if exec_stream and exec_stream.is_open():
            try:
                cols = data.get("cols", 80)
                rows = data.get("rows", 24)
                exec_stream.write_channel(4, f'{{"Width":{cols},"Height":{rows}}}')
            except Exception:
                pass

    @socketio.on("exec_stop", namespace="/system")
    def handle_exec_stop():
        """Stop the exec session."""
        sid = request.sid
        stop_event = _active_sessions.get(sid)
        if stop_event:
            stop_event.set()

    # Also handle disconnect for exec cleanup (extends the existing /system disconnect handler)
    # Note: The disconnect handler from logs.py already handles /system namespace disconnect.
    # We add exec cleanup there. If logs.py disconnect isn't registered yet, register our own.
    # Best approach: in router.py, register a combined disconnect handler.
```

**Important note on disconnect handling:** The `/system` SocketIO namespace now has handlers from both `logs.py` (Tier 2) and `exec.py` (Tier 3). The disconnect handler in `logs.py` should be updated to also clean up exec sessions, or a combined handler should be created in `router.py`. The simplest approach is to add exec cleanup to the existing disconnect handler in `logs.py`:

```python
# Add to the disconnect handler in logs.py:
from .exec import _active_sessions as exec_sessions

@socketio.on("disconnect", namespace="/system")
def handle_disconnect():
    """Clean up all streams and exec sessions for this client."""
    sid = request.sid

    # Clean up log streams
    keys_to_remove = [k for k in _active_streams if k.startswith(f"{sid}:")]
    for key in keys_to_remove:
        stop_event = _active_streams.pop(key, None)
        if stop_event:
            stop_event.set()

    # Clean up exec sessions
    stop_event = exec_sessions.pop(sid, None)
    if stop_event:
        stop_event.set()
    exec_sessions.pop(f"{sid}:stream", None)
```

---

## 4. Modify `src/api/v2/router.py`

Add imports and route registrations.

**Imports:**

```python
from .system.resources import get_resource_yaml, apply_resource_yaml, delete_resource
from .system.rbac import list_roles, list_cluster_roles, list_role_bindings, list_cluster_role_bindings, list_service_accounts
from .system.exec import register_exec_handlers
```

**Route registrations** (add before `server.register_blueprint(v2)`):

```python
# ── System Monitor: Resource YAML ──────────────────────────
v2.add_url_rule("/system/resources/<kind>/<namespace>/<name>", view_func=get_resource_yaml, methods=["GET"])
v2.add_url_rule("/system/resources/<kind>/<namespace>/<name>", view_func=apply_resource_yaml, methods=["PUT"])
v2.add_url_rule("/system/resources/<kind>/<namespace>/<name>", view_func=delete_resource, methods=["DELETE"])

# ── System Monitor: RBAC ───────────────────────────────────
v2.add_url_rule("/system/rbac/roles", view_func=list_roles, methods=["GET"])
v2.add_url_rule("/system/rbac/clusterroles", view_func=list_cluster_roles, methods=["GET"])
v2.add_url_rule("/system/rbac/bindings", view_func=list_role_bindings, methods=["GET"])
v2.add_url_rule("/system/rbac/clusterrolebindings", view_func=list_cluster_role_bindings, methods=["GET"])
v2.add_url_rule("/system/rbac/serviceaccounts", view_func=list_service_accounts, methods=["GET"])

# ── System Monitor: Pod Exec ──────────────────────────────
register_exec_handlers(socketio)
```

---

## Verification

1. `python3 -m py_compile` on all new files
2. Backend starts without error
3. Test resource YAML endpoint:
   ```bash
   curl -H "Authorization: Bearer $TOKEN" http://localhost:9001/v2/system/resources/deployment/default/my-app
   ```
4. Test RBAC endpoints:
   ```bash
   curl -H "Authorization: Bearer $TOKEN" http://localhost:9001/v2/system/rbac/roles
   curl -H "Authorization: Bearer $TOKEN" http://localhost:9001/v2/system/rbac/clusterroles
   curl -H "Authorization: Bearer $TOKEN" http://localhost:9001/v2/system/rbac/serviceaccounts
   ```
5. Test exec SocketIO connection (manual test with socket.io client)

---

## Overview Update

```
- [x] Phase 3 — Backend: API routes for resources + RBAC, pod exec SocketIO
```
