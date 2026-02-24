import logging

from flask import request
from flask_socketio import SocketIO, emit

from src.services.database.prisma import get_db_client
from src.services.mtib_observability import get_observability_service

logger = logging.getLogger(__name__)

# Resource limits to prevent DoS
MAX_CONCURRENT_SUBSCRIBERS = 50  # Maximum number of concurrent observability subscriptions
MAX_FEATURES = 10  # Maximum number of features per subscription
VALID_FEATURES = {"power", "gpio", "adc", "uart", "system", "clients"}
MAX_NODE_ID_LENGTH = 255  # Maximum length for node ID


def register_observability_handlers(socketio: SocketIO):
    """Register Socket.IO event handlers for MTIB observability streaming.

    NOTE: Authentication is handled by the shared /kubernetes namespace connect handler
    in logs.py, which validates JWT tokens and checks ADMIN_SYSTEM_VIEW permission.
    This handler must be registered AFTER register_log_handlers() in router.py to
    inherit the authentication."""

    @socketio.on("subscribe_observability", namespace="/kubernetes")
    def handle_subscribe_observability(data):
        """Subscribe to real-time observability updates for a node.

        Expected data:
            {
                "nodeId": "mtib-node-1",
                "features": ["power", "gpio", "adc", "system"]  # optional, defaults to all
            }

        Emits:
            - observability_update: {"nodeId", "timestamp", "powerReadings"?, "gpioStates"?, ...}
            - observability_error: {"nodeId", "message"}
        """
        node_id = None
        try:
            # Input validation: nodeId
            node_id = data.get("nodeId")
            if not node_id or not isinstance(node_id, str):
                emit("observability_error", {"nodeId": "", "message": "Missing or invalid nodeId"})
                return
            if len(node_id) > MAX_NODE_ID_LENGTH:
                emit("observability_error", {"nodeId": "", "message": "nodeId too long"})
                return

            # Input validation: features
            features = data.get("features")
            if not features or not isinstance(features, list):
                # Default to all features if not specified
                features = ["power", "gpio", "adc", "uart", "system", "clients"]
            else:
                # Validate features list
                if len(features) > MAX_FEATURES:
                    emit("observability_error", {"nodeId": node_id, "message": "Too many features requested"})
                    return
                # Validate each feature is a valid string
                if not all(isinstance(f, str) and f in VALID_FEATURES for f in features):
                    emit("observability_error", {"nodeId": node_id, "message": "Invalid feature name"})
                    return

            # Validate node exists
            db = get_db_client()
            node = db.node.find_unique(where={"id": node_id})
            if not node:
                emit("observability_error", {"nodeId": node_id, "message": "Node not found"})
                return

            # Get observability service
            svc = get_observability_service()
            if not svc:
                emit("observability_error", {"nodeId": node_id, "message": "Observability service not available"})
                return

            # Check subscriber count limit
            if svc.get_subscriber_count() >= MAX_CONCURRENT_SUBSCRIBERS:
                emit("observability_error", {"nodeId": node_id, "message": "Too many active subscriptions"})
                logger.warning("Observability subscriber limit reached (%d)", MAX_CONCURRENT_SUBSCRIBERS)
                return

            sid = request.sid

            # Define emit function to send updates to this client
            def emit_update(filtered_snapshot: dict):
                try:
                    socketio.emit("observability_update", filtered_snapshot, room=sid, namespace="/kubernetes")
                except Exception as e:
                    logger.error("Failed to emit observability update to %s: %s", sid, e)

            # Register subscriber
            svc.register_subscriber(sid, node_id, features, emit_update)
            logger.info("Client %s subscribed to observability for node %s (features: %s)", sid, node_id, features)

        except Exception as e:
            logger.error("Observability subscribe error for node %s: %s", node_id or "unknown", e)
            emit("observability_error", {"nodeId": node_id or "", "message": "Subscription failed"})

    @socketio.on("unsubscribe_observability", namespace="/kubernetes")
    def handle_unsubscribe_observability(data):
        """Unsubscribe from observability updates for a node.

        Expected data:
            {
                "nodeId": "mtib-node-1"
            }
        """
        try:
            node_id = data.get("nodeId", "")
            sid = request.sid

            svc = get_observability_service()
            if svc:
                svc.unregister_subscriber(sid, node_id)
                logger.info("Client %s unsubscribed from observability for node %s", sid, node_id)
        except Exception as e:
            logger.error("Observability unsubscribe error: %s", e)


def cleanup_observability_sessions(sid: str):
    """Clean up all observability subscriptions for a disconnected client."""
    try:
        svc = get_observability_service()
        if svc:
            svc.cleanup_subscribers(sid)
            logger.debug("Cleaned up observability subscriptions for client %s", sid)
    except Exception as e:
        logger.error("Observability cleanup error for %s: %s", sid, e)


# ─────────────────────────────────────────────────────────────────────────────
#                                                      ICLE Device Subscriptions
# ─────────────────────────────────────────────────────────────────────────────

# Track ICLE subscriptions: {sid: set of device_ids}
_icle_subscribers: dict[str, set[str]] = {}


def register_icle_handlers(socketio: SocketIO):
    """Register Socket.IO event handlers for ICLE device updates.

    NOTE: Authentication is handled by the shared /kubernetes namespace connect handler
    in logs.py, which validates JWT tokens and checks ADMIN_SYSTEM_VIEW permission.
    This handler must be registered AFTER register_log_handlers() in router.py to
    inherit the authentication."""

    @socketio.on("subscribe_icle", namespace="/kubernetes")
    def handle_subscribe_icle(data):
        """Subscribe to real-time ICLE device updates.

        Expected data:
            {
                "deviceId": "device-id-1"  # optional, if omitted subscribes to all
            }

        Emits:
            - icle_update: {"id", "deviceId", "name", "status", ...}
            - icle_error: {"deviceId", "message"}
        """
        try:
            device_id = data.get("deviceId", "*")  # "*" means all devices
            if not isinstance(device_id, str):
                emit("icle_error", {"deviceId": "", "message": "Invalid deviceId"})
                return
            if len(device_id) > 255:
                emit("icle_error", {"deviceId": "", "message": "deviceId too long"})
                return

            # If subscribing to specific device, validate it exists
            if device_id != "*":
                db = get_db_client()
                device = db.icledevice.find_unique(where={"id": device_id})
                if not device:
                    emit("icle_error", {"deviceId": device_id, "message": "Device not found"})
                    return

            sid = request.sid

            # Track subscription
            if sid not in _icle_subscribers:
                _icle_subscribers[sid] = set()
            _icle_subscribers[sid].add(device_id)

            logger.info("Client %s subscribed to ICLE updates for device %s", sid, device_id)
            emit("icle_subscribed", {"deviceId": device_id, "subscribed": True})

        except Exception as e:
            logger.error("ICLE subscribe error: %s", e)
            emit("icle_error", {"deviceId": "", "message": "Subscription failed"})

    @socketio.on("unsubscribe_icle", namespace="/kubernetes")
    def handle_unsubscribe_icle(data):
        """Unsubscribe from ICLE device updates.

        Expected data:
            {
                "deviceId": "device-id-1"  # optional, if omitted unsubscribes from all
            }
        """
        try:
            device_id = data.get("deviceId", "*")
            sid = request.sid

            if sid in _icle_subscribers:
                if device_id == "*":
                    _icle_subscribers[sid].clear()
                else:
                    _icle_subscribers[sid].discard(device_id)
                if not _icle_subscribers[sid]:
                    del _icle_subscribers[sid]

            logger.info("Client %s unsubscribed from ICLE updates for device %s", sid, device_id)
        except Exception as e:
            logger.error("ICLE unsubscribe error: %s", e)


def cleanup_icle_sessions(sid: str):
    """Clean up ICLE subscriptions for a disconnected client."""
    try:
        if sid in _icle_subscribers:
            del _icle_subscribers[sid]
            logger.debug("Cleaned up ICLE subscriptions for client %s", sid)
    except Exception as e:
        logger.error("ICLE cleanup error for %s: %s", sid, e)


def get_icle_subscribers() -> dict[str, set[str]]:
    """Get all ICLE subscribers (for broadcasting updates)."""
    return _icle_subscribers
