import logging
import threading

from flask import request
from flask_socketio import SocketIO, emit, join_room, leave_room

from src.lib.permissions import Permissions
from src.services.auth.jwt import verify_token
from src.services.database.prisma import get_db_client
from src.services.kubernetes.client import get_core_v1_api

logger = logging.getLogger(__name__)

_active_streams: dict[str, threading.Event] = {}
_lock = threading.Lock()

MAX_CONCURRENT_STREAMS = 20
MAX_TAIL_LINES = 10000


def register_log_handlers(socketio: SocketIO):

    @socketio.on("connect", namespace="/kubernetes")
    def handle_system_connect(auth):
        """Validate JWT token and permissions at connection time. Reject unauthorized clients."""
        if not auth or not auth.get("token"):
            return False
        token = auth["token"]
        payload, error = verify_token(token)
        if error:
            return False

        # Check that the user has ADMIN_SYSTEM_VIEW or ADMIN_SYSTEM_MANAGE permission
        perm_set_id = payload.get("permissionSetId")
        if not perm_set_id:
            return False
        db = get_db_client()
        perm_set = db.permissionset.find_unique(where={"id": perm_set_id})
        if not perm_set:
            return False
        user_permissions = perm_set.permissions or []
        if (Permissions.ADMIN_SYSTEM_VIEW not in user_permissions
                and Permissions.ADMIN_SYSTEM_MANAGE not in user_permissions):
            return False
        # Connection accepted — socket is authenticated and authorized

    @socketio.on("subscribe_logs", namespace="/kubernetes")
    def handle_subscribe_logs(data):
        ns = data.get("namespace")
        pod = data.get("pod")
        container = data.get("container")
        tail_lines = data.get("tailLines", 100)

        if not ns or not pod or not container:
            emit("log_error", {"message": "Missing namespace, pod, or container"})
            return

        # Validate tailLines
        if not isinstance(tail_lines, int) or tail_lines < 1:
            tail_lines = 100
        tail_lines = min(tail_lines, MAX_TAIL_LINES)

        # Enforce concurrent stream limit
        with _lock:
            if len(_active_streams) >= MAX_CONCURRENT_STREAMS:
                emit("log_error", {"message": "Too many active log streams"})
                return

        room = f"pod-logs:{ns}:{pod}:{container}"
        sid = request.sid
        join_room(room)

        stop_event = threading.Event()
        stream_key = f"{sid}:{room}"

        with _lock:
            _active_streams[stream_key] = stop_event

        def stream_logs():
            log_stream = None
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
                        namespace="/kubernetes",
                    )
            except Exception as e:
                logger.error("Log stream error: %s", e)
                socketio.emit(
                    "log_error",
                    {"message": "Log stream error occurred"},
                    room=room,
                    namespace="/kubernetes",
                )
            finally:
                if log_stream is not None:
                    try:
                        log_stream.release_conn()
                    except Exception:
                        pass
                with _lock:
                    _active_streams.pop(stream_key, None)

        socketio.start_background_task(stream_logs)

    @socketio.on("unsubscribe_logs", namespace="/kubernetes")
    def handle_unsubscribe_logs(data):
        ns = data.get("namespace", "")
        pod = data.get("pod", "")
        container = data.get("container", "")
        room = f"pod-logs:{ns}:{pod}:{container}"
        sid = request.sid

        stream_key = f"{sid}:{room}"
        with _lock:
            stop_event = _active_streams.pop(stream_key, None)
        if stop_event:
            stop_event.set()

        leave_room(room)

    @socketio.on("disconnect", namespace="/kubernetes")
    def handle_disconnect():
        sid = request.sid
        # Clean up log streams
        with _lock:
            keys_to_remove = [k for k in _active_streams if k.startswith(f"{sid}:")]
            for key in keys_to_remove:
                stop_event = _active_streams.pop(key, None)
                if stop_event:
                    stop_event.set()
        # Clean up exec sessions
        from .exec import cleanup_exec_session
        cleanup_exec_session(sid)
        # Clean up UART sessions
        from .uart import cleanup_uart_sessions
        cleanup_uart_sessions(sid)
