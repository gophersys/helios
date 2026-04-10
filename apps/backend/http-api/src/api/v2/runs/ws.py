"""WebSocket handlers for the /runs namespace.

Provides room-based subscription for test run events and log streaming.
Clients subscribe to specific run IDs to receive real-time updates.
"""
import logging

from flask import request
from flask_socketio import SocketIO, emit, join_room, leave_room

from src.lib.permissions import Permissions
from src.services.auth.jwt import verify_token
from src.services.database.prisma import get_db_client

logger = logging.getLogger(__name__)

# Global SocketIO reference for emitting from other modules
_runs_socketio: SocketIO | None = None


def get_runs_socketio() -> SocketIO | None:
    """Get the SocketIO instance for runs namespace."""
    return _runs_socketio


def emit_to_run(event: str, data: dict, run_id: str):
    """Emit an event to all clients subscribed to a specific run.

    This is the primary API for reporter and log modules to send events
    to interested clients.
    """
    if _runs_socketio:
        _runs_socketio.emit(
            event,
            data,
            namespace="/runs",
            room=f"run:{run_id}"
        )


def register_runs_ws_handlers(socketio: SocketIO):
    """Register Socket.IO event handlers for the /runs namespace.

    This namespace handles real-time events for both validation and
    manufacturing test runs. Authentication is handled at connect time
    via JWT token validation.
    """
    global _runs_socketio
    _runs_socketio = socketio

    @socketio.on("connect", namespace="/runs")
    def handle_runs_connect(auth):
        """Validate JWT token and permissions at connection time."""
        if not auth or not auth.get("token"):
            logger.warning("Runs WS connect rejected: no token")
            return False

        token = auth["token"]
        payload, error = verify_token(token)
        if error:
            logger.warning("Runs WS connect rejected: %s", error)
            return False

        # Check that the user has validation:view or validation:manage permission
        perm_set_id = payload.get("permissionSetId")
        if not perm_set_id:
            logger.warning("Runs WS connect rejected: no permissionSetId")
            return False

        db = get_db_client()
        perm_set = db.permissionset.find_unique(where={"id": perm_set_id})
        if not perm_set:
            logger.warning("Runs WS connect rejected: permission set not found")
            return False

        user_permissions = perm_set.permissions or []
        if (Permissions.VALIDATION_VIEW not in user_permissions
                and Permissions.VALIDATION_MANAGE not in user_permissions):
            logger.warning("Runs WS connect rejected: insufficient permissions")
            return False

        logger.debug("Runs WS client connected: %s", request.sid)
        # Connection accepted

    @socketio.on("subscribe_run", namespace="/runs")
    def handle_subscribe_run(data):
        """Subscribe to updates for a specific test run.

        Expected data:
            {
                "runId": "cuid-run-id"
            }

        Emits:
            - subscribed: {"runId": "..."}
            - error: {"message": "..."}
        """
        run_id = data.get("runId")
        if not run_id or not isinstance(run_id, str):
            emit("error", {"message": "Missing or invalid runId"})
            return

        if len(run_id) > 255:
            emit("error", {"message": "runId too long"})
            return

        # Validate run exists
        db = get_db_client()
        run = db.testrun.find_unique(where={"id": run_id})
        if not run:
            emit("error", {"message": "Test run not found"})
            return

        # Join the room for this run
        room = f"run:{run_id}"
        join_room(room)

        logger.info("Client %s subscribed to run %s", request.sid, run_id)
        emit("subscribed", {"runId": run_id})

    @socketio.on("unsubscribe_run", namespace="/runs")
    def handle_unsubscribe_run(data):
        """Unsubscribe from a specific test run.

        Expected data:
            {
                "runId": "cuid-run-id"
            }
        """
        run_id = data.get("runId")
        if not run_id or not isinstance(run_id, str):
            return

        room = f"run:{run_id}"
        leave_room(room)

        logger.debug("Client %s unsubscribed from run %s", request.sid, run_id)

    @socketio.on("disconnect", namespace="/runs")
    def handle_runs_disconnect():
        """Handle client disconnect — room cleanup is automatic in Flask-SocketIO."""
        logger.debug("Runs WS client disconnected: %s", request.sid)
