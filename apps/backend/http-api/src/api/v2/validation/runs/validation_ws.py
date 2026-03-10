"""WebSocket handlers for the /validation namespace.

Provides room-based subscription for validation run events and log streaming.
Clients subscribe to specific run IDs to receive real-time updates.
"""
import logging

from flask import request
from flask_socketio import SocketIO, emit, join_room, leave_room

from src.lib.permissions import Permissions
from src.services.auth.jwt import verify_token
from src.services.database.prisma import get_db_client

logger = logging.getLogger(__name__)

# Global SocketIO reference for emitting from reporter.py
_validation_socketio: SocketIO | None = None


def get_validation_socketio() -> SocketIO | None:
    """Get the SocketIO instance for validation namespace."""
    return _validation_socketio


def emit_to_run(event: str, data: dict, run_id: str):
    """Emit an event to all clients subscribed to a specific run.

    This is the primary API for reporter.py to send events to interested clients.
    """
    if _validation_socketio:
        _validation_socketio.emit(
            event,
            data,
            namespace="/validation",
            room=f"run:{run_id}"
        )


def register_validation_ws_handlers(socketio: SocketIO):
    """Register Socket.IO event handlers for the /validation namespace.

    This namespace is dedicated to validation run events and log streaming.
    Authentication is handled at connect time via JWT token validation.
    """
    global _validation_socketio
    _validation_socketio = socketio

    @socketio.on("connect", namespace="/validation")
    def handle_validation_connect(auth):
        """Validate JWT token and permissions at connection time."""
        if not auth or not auth.get("token"):
            logger.warning("Validation WS connect rejected: no token")
            return False

        token = auth["token"]
        payload, error = verify_token(token)
        if error:
            logger.warning("Validation WS connect rejected: %s", error)
            return False

        # Check that the user has ADMIN_VALIDATION_VIEW or ADMIN_VALIDATION_MANAGE permission
        perm_set_id = payload.get("permissionSetId")
        if not perm_set_id:
            logger.warning("Validation WS connect rejected: no permissionSetId")
            return False

        db = get_db_client()
        perm_set = db.permissionset.find_unique(where={"id": perm_set_id})
        if not perm_set:
            logger.warning("Validation WS connect rejected: permission set not found")
            return False

        user_permissions = perm_set.permissions or []
        if (Permissions.ADMIN_VALIDATION_VIEW not in user_permissions
                and Permissions.ADMIN_VALIDATION_MANAGE not in user_permissions):
            logger.warning("Validation WS connect rejected: insufficient permissions")
            return False

        logger.debug("Validation WS client connected: %s", request.sid)
        # Connection accepted

    @socketio.on("subscribe_run", namespace="/validation")
    def handle_subscribe_run(data):
        """Subscribe to updates for a specific validation run.

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
        session = db.session.find_unique(where={"id": run_id})
        if not session:
            emit("error", {"message": "Validation run not found"})
            return

        # Join the room for this run
        room = f"run:{run_id}"
        join_room(room)

        logger.info("Client %s subscribed to validation run %s", request.sid, run_id)
        emit("subscribed", {"runId": run_id})

    @socketio.on("unsubscribe_run", namespace="/validation")
    def handle_unsubscribe_run(data):
        """Unsubscribe from a specific validation run.

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

        logger.debug("Client %s unsubscribed from validation run %s", request.sid, run_id)

    @socketio.on("disconnect", namespace="/validation")
    def handle_validation_disconnect():
        """Handle client disconnect — room cleanup is automatic in Flask-SocketIO."""
        logger.debug("Validation WS client disconnected: %s", request.sid)
