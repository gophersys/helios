"""WebSocket namespace for real-time notification delivery.

Each authenticated user joins a room `user:{userId}`. The notifier module
emits to that room when a notification is created.
"""

import logging

from flask import request
from flask_socketio import Namespace, join_room, leave_room

from src.services.auth.jwt import verify_token

logger = logging.getLogger(__name__)


class NotificationNamespace(Namespace):
    """Socket.IO /notifications namespace."""

    def on_connect(self, auth=None):
        token = None
        if auth and isinstance(auth, dict):
            token = auth.get("token")
        if not token:
            token = request.args.get("token")
        if not token:
            logger.debug("Notification WS: no token provided")
            return False

        payload, error = verify_token(token)
        if error or not payload:
            logger.debug("Notification WS: invalid token: %s", error)
            return False

        user_id = payload.get("sub")
        if not user_id:
            return False

        room = f"user:{user_id}"
        join_room(room)
        logger.debug("Notification WS: user %s joined room %s", user_id, room)

    def on_disconnect(self):
        pass


def register_notification_ws(socketio):
    """Register the /notifications namespace."""
    socketio.on_namespace(NotificationNamespace("/notifications"))
