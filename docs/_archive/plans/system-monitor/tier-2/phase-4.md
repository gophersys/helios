# Phase 4 — Backend: Pod Log Streaming via SocketIO

## Objective

Add real-time pod log streaming using the existing Flask-SocketIO infrastructure. Clients subscribe to a pod's container logs and receive lines as they're written.

---

## 1. Create `src/api/v2/system/logs.py`

```python
import threading

from flask import request
from flask_socketio import SocketIO, emit, join_room, leave_room

from src.services.kubernetes.client import get_core_v1_api

# Track active log streams so we can stop them
_active_streams: dict[str, threading.Event] = {}


def register_log_handlers(socketio: SocketIO):
    """Register SocketIO event handlers for pod log streaming."""

    @socketio.on("subscribe_logs", namespace="/system")
    def handle_subscribe_logs(data):
        """
        Client sends: { namespace, pod, container, tailLines? }
        Server joins client to a room and starts streaming.
        """
        ns = data.get("namespace")
        pod = data.get("pod")
        container = data.get("container")
        tail_lines = data.get("tailLines", 100)

        if not ns or not pod or not container:
            emit("log_error", {"message": "Missing namespace, pod, or container"})
            return

        room = f"pod-logs:{ns}:{pod}:{container}"
        sid = request.sid
        join_room(room)

        # Create a stop event for this stream
        stop_event = threading.Event()
        stream_key = f"{sid}:{room}"
        _active_streams[stream_key] = stop_event

        # Start streaming in a background thread
        def stream_logs():
            try:
                core = get_core_v1_api()
                log_stream = core.read_namespaced_pod_log(
                    name=pod,
                    namespace=ns,
                    container=container,
                    follow=True,
                    tail_lines=tail_lines,
                    _preload_content=False,
                )

                for line in log_stream.stream():
                    if stop_event.is_set():
                        break
                    decoded = line.decode("utf-8", errors="replace").rstrip("\n")
                    socketio.emit(
                        "log_line",
                        {"line": decoded},
                        room=room,
                        namespace="/system",
                    )

                log_stream.release_conn()
            except Exception as e:
                socketio.emit(
                    "log_error",
                    {"message": f"Log stream error: {str(e)}"},
                    room=room,
                    namespace="/system",
                )
            finally:
                _active_streams.pop(stream_key, None)

        socketio.start_background_task(stream_logs)

    @socketio.on("unsubscribe_logs", namespace="/system")
    def handle_unsubscribe_logs(data):
        """Stop streaming and leave the room."""
        ns = data.get("namespace", "")
        pod = data.get("pod", "")
        container = data.get("container", "")
        room = f"pod-logs:{ns}:{pod}:{container}"
        sid = request.sid

        # Signal the stream to stop
        stream_key = f"{sid}:{room}"
        stop_event = _active_streams.pop(stream_key, None)
        if stop_event:
            stop_event.set()

        leave_room(room)

    @socketio.on("disconnect", namespace="/system")
    def handle_disconnect():
        """Clean up all streams for this client."""
        sid = request.sid
        keys_to_remove = [k for k in _active_streams if k.startswith(f"{sid}:")]
        for key in keys_to_remove:
            stop_event = _active_streams.pop(key, None)
            if stop_event:
                stop_event.set()
```

---

## 2. Modify `src/api/v2/router.py`

Add the log handler registration. The `socketio` instance is already passed to `register_v2_routes`.

**Import** (add near system imports):

```python
from .system.logs import register_log_handlers
```

**Registration** (add at the end of `register_v2_routes`, after all URL rules):

```python
# ── System Monitor: Log Streaming ───────────────────────────
register_log_handlers(socketio)
```

---

## 3. Create `src/api/v2/system/pods.py` — Add container list endpoint

Add a helper endpoint to get the container names for a pod (used by the log viewer dropdown):

**Add to existing `src/api/v2/system/pods.py`:**

```python
@require_permissions(Permissions.ADMIN_SYSTEM_VIEW)
def get_pod_containers(namespace: str, name: str):
    """Return list of container names for log viewer dropdown."""
    try:
        data = pods_svc.get_pod(namespace, name)
        if data is None:
            return not_found("Pod not found")
        containers = [c["name"] for c in data.get("containers", [])]
        return jsonify(ApiResponse.ok(containers).to_dict()), 200
    except Exception as e:
        return jsonify(ApiResponse.error(f"Failed to get containers: {str(e)}").to_dict()), 500
```

**Add route in router.py:**

```python
from .system.pods import list_pods, get_pod, delete_pod, get_pod_containers

server.add_url_rule("/v2/system/pods/<namespace>/<name>/containers", view_func=get_pod_containers, methods=["GET"])
```

---

## Verification

1. `python3 -m py_compile src/api/v2/system/logs.py` — passes
2. Backend starts without error
3. Test SocketIO connection:
   ```javascript
   const socket = io("http://localhost:9001/system");
   socket.emit("subscribe_logs", {
     namespace: "default",
     pod: "my-pod",
     container: "main",
     tailLines: 50
   });
   socket.on("log_line", (data) => console.log(data.line));
   socket.on("log_error", (data) => console.error(data.message));
   ```
4. Disconnecting the client cleanly stops the K8s log stream

---

## Overview Update

```
- [x] Phase 4 — Backend: pod log streaming via SocketIO
```
