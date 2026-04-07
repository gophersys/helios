import logging
import queue
import threading
import traceback

import warnings
with warnings.catch_warnings():
    warnings.simplefilter("ignore", DeprecationWarning)
    import eventlet
    from eventlet import tpool
from flask import request
from flask_socketio import SocketIO, emit
from kubernetes.stream import stream as k8s_stream

from src.lib.audit import log_audit
from src.lib.permissions import Permissions
from src.services.auth.jwt import verify_token
from src.services.database.prisma import get_db_client
from src.services.kubernetes.client import get_core_v1_api

logger = logging.getLogger(__name__)


# Track active exec sessions: sid -> stop_event, "{sid}:stream" -> exec_stream
_active_sessions: dict[str, object] = {}
_lock = threading.Lock()

MAX_CONCURRENT_EXEC = 10


def register_exec_handlers(socketio: SocketIO):
    """Register SocketIO event handlers for pod exec."""

    @socketio.on("exec_start", namespace="/kubernetes")
    def handle_exec_start(data):
        """
        Start an interactive exec session.
        Client sends: { namespace, pod, container, command?, token? }

        SECURITY: Exec requires system:manage permission (more privileged than
        system:view which is sufficient for logs). The token must be passed
        in the data payload for per-operation authorization.
        """
        # SECURITY: Verify token and require system:manage for exec operations
        # Exec is a privileged operation (shell access) — stricter than log viewing
        token = data.get("token")
        if not token:
            emit("exec_error", {"message": "Authentication required"})
            return

        payload, error = verify_token(token)
        if error:
            emit("exec_error", {"message": "Invalid or expired token"})
            return

        # Check for system:manage permission (exec is privileged)
        perm_set_id = payload.get("permissionSetId")
        if not perm_set_id:
            emit("exec_error", {"message": "Authorization required"})
            return

        db = get_db_client()
        perm_set = db.permissionset.find_unique(where={"id": perm_set_id})
        if not perm_set:
            emit("exec_error", {"message": "Authorization required"})
            return

        user_permissions = perm_set.permissions or []
        if Permissions.SYSTEM_MANAGE not in user_permissions:
            emit("exec_error", {"message": "Insufficient permissions — system:manage required"})
            return

        ns = data.get("namespace")
        pod = data.get("pod")
        container = data.get("container")
        command = data.get("command", ["/bin/sh"])

        if not ns or not pod or not container:
            emit("exec_error", {"message": "Missing namespace, pod, or container"})
            return

        sid = request.sid

        log_audit("system.exec.start", "Pod", f"{ns}/{pod}/{container}", {"command": command, "user": payload.get("email", "unknown")})

        with _lock:
            active_count = sum(1 for k in _active_sessions if not k.endswith(":stream"))
            if active_count >= MAX_CONCURRENT_EXEC:
                emit("exec_error", {"message": "Too many concurrent exec sessions"})
                return

            stop_event = threading.Event()
            _active_sessions[sid] = stop_event

        # Thread-safe queue: native reader thread puts data, green thread emits
        output_q = queue.Queue()

        def _blocking_reader():
            """
            Run in a native OS thread to avoid conflicts between eventlet's
            green threading and websocket-client's use of select.select()
            (which is not monkey-patched).
            """
            try:
                core = get_core_v1_api()

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

                with _lock:
                    _active_sessions[f"{sid}:stream"] = exec_stream

                while exec_stream.is_open() and not stop_event.is_set():
                    exec_stream.update(timeout=1)
                    if exec_stream.peek_stdout():
                        output_q.put(("output", exec_stream.read_stdout()))
                    if exec_stream.peek_stderr():
                        output_q.put(("output", exec_stream.read_stderr()))

                exec_stream.close()
                try:
                    code = exec_stream.returncode or 0
                except Exception:
                    code = 0
                output_q.put(("exit", code))

            except Exception as e:
                logger.error("Exec read error: %s", e)
                output_q.put(("error", "Exec stream error occurred"))
                traceback.print_exc()

        def run_exec():
            """Background task that reads K8s exec output and emits via WebSocket."""
            # Start blocking K8s websocket reader in a real OS thread
            reader = threading.Thread(target=_blocking_reader, daemon=True)
            reader.start()

            try:
                # Green thread: drain queue and emit via SocketIO (must stay in green thread).
                # Use get_nowait + eventlet.sleep to avoid blocking the eventlet hub
                # (queue.Queue.get with timeout uses threading.Condition which isn't patched).
                while True:
                    try:
                        msg_type, data = output_q.get_nowait()
                    except queue.Empty:
                        if not reader.is_alive():
                            break
                        eventlet.sleep(0.05)
                        continue

                    if msg_type == "output":
                        socketio.emit("exec_output", {"data": data}, room=sid, namespace="/kubernetes")
                    elif msg_type == "exit":
                        socketio.emit("exec_exit", {"code": data}, room=sid, namespace="/kubernetes")
                        break
                    elif msg_type == "error":
                        socketio.emit("exec_error", {"message": "Exec error occurred"}, room=sid, namespace="/kubernetes")
                        break
            except Exception as e:
                logger.error("Exec error: %s", e)
                traceback.print_exc()
                socketio.emit("exec_error", {"message": "Exec error occurred"}, room=sid, namespace="/kubernetes")
            finally:
                stop_event.set()
                reader.join(timeout=5)
                with _lock:
                    _active_sessions.pop(sid, None)
                    _active_sessions.pop(f"{sid}:stream", None)

        socketio.start_background_task(run_exec)

    @socketio.on("exec_input", namespace="/kubernetes")
    def handle_exec_input(data):
        """Forward keyboard input to the exec stream."""
        sid = request.sid
        with _lock:
            exec_stream = _active_sessions.get(f"{sid}:stream")
        if exec_stream and exec_stream.is_open():
            try:
                # Run in native thread — the stream's websocket isn't safe under eventlet
                tpool.execute(exec_stream.write_stdin, data.get("data", ""))
            except Exception:
                pass

    @socketio.on("exec_resize", namespace="/kubernetes")
    def handle_exec_resize(data):
        """Resize the exec terminal."""
        sid = request.sid
        with _lock:
            exec_stream = _active_sessions.get(f"{sid}:stream")
        if exec_stream and exec_stream.is_open():
            try:
                cols = data.get("cols", 80)
                rows = data.get("rows", 24)
                # Run in native thread — the stream's websocket isn't safe under eventlet
                tpool.execute(
                    exec_stream.write_channel, 4, f'{{"Width":{cols},"Height":{rows}}}'
                )
            except Exception:
                pass

    @socketio.on("exec_stop", namespace="/kubernetes")
    def handle_exec_stop():
        """Stop the exec session."""
        sid = request.sid
        with _lock:
            stop_event = _active_sessions.get(sid)
        if stop_event:
            stop_event.set()


def cleanup_exec_session(sid: str):
    """Clean up exec sessions for a disconnected client. Called from logs.py disconnect handler."""
    with _lock:
        stop_event = _active_sessions.pop(sid, None)
        _active_sessions.pop(f"{sid}:stream", None)
    if stop_event and hasattr(stop_event, "set"):
        stop_event.set()
