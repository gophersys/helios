"""ICLE device heartbeat endpoint - NO AUTH required for device discovery."""

import logging
from datetime import datetime, timezone

from database import Json
from flask import jsonify, request

from src.lib.types import ApiResponse
from src.lib.errors import bad_request
from src.services.database.prisma import get_db_client

from .types import HeartbeatRequest

logger = logging.getLogger(__name__)

# Map string status to enum value
STATUS_MAP = {
    "online": "ONLINE",
    "offline": "OFFLINE",
    "logging": "LOGGING",
    "config": "CONFIG",
    "boot": "BOOT",
    "ota": "OTA",
}

# Global reference to SocketIO for emitting events (set by router)
_socketio = None


def set_socketio(socketio):
    """Set the SocketIO instance for emitting events."""
    global _socketio
    _socketio = socketio


def emit_icle_update(device_data: dict):
    """Emit an icle_update event to subscribed WebSocket clients."""
    if _socketio:
        try:
            _socketio.emit("icle_update", device_data, namespace="/kubernetes")
        except Exception as e:
            logger.warning("Failed to emit icle_update: %s", e)


def heartbeat():
    """Handle ICLE device heartbeat.

    POST /v2/icle/heartbeat

    This endpoint does NOT require authentication - devices discover themselves
    by sending heartbeats with their device_id.

    Request body:
        {
            "device_id": "ICLE-001",
            "firmware_version": "1.0.0",
            "ip_address": "192.168.1.100",
            "mac_address": "AA:BB:CC:DD:EE:FF",
            "status": "online",
            "uptime_seconds": 3600,
            "free_heap_bytes": 123456,
            "wifi_rssi": -65,
            "sd_card_free_mb": 1024,
            "current_log_file": "log_001.bin",
            "power_readings": [
                {"channel": 0, "voltage_mv": 3300, "current_ma": 150, "power_mw": 495}
            ]
        }

    Response:
        {
            "acknowledged": true,
            "registered": false,
            "server_time": "2024-01-01T12:00:00Z",
            "heartbeat_interval_ms": 5000,
            "pending_commands": [
                {"id": "cmd-1", "type": "config_update", "payload": {...}}
            ]
        }
    """
    req, error = HeartbeatRequest.from_json(request.get_json())
    if error:
        return bad_request(error)

    db = get_db_client()
    now = datetime.now(timezone.utc)

    # Build status data
    status_data = req.to_status_data()

    # Map status string to enum
    db_status = STATUS_MAP.get(req.status, "ONLINE")

    # Upsert device
    device = db.icledevice.upsert(
        where={"deviceId": req.device_id},
        data={
            "create": {
                "deviceId": req.device_id,
                "firmwareVersion": req.firmware_version,
                "ipAddress": req.ip_address,
                "macAddress": req.mac_address,
                "status": db_status,
                "lastHeartbeat": now,
                "lastStatusData": Json(status_data),
            },
            "update": {
                "firmwareVersion": req.firmware_version,
                "ipAddress": req.ip_address,
                "macAddress": req.mac_address,
                "status": db_status,
                "lastHeartbeat": now,
                "lastStatusData": Json(status_data),
            },
        },
    )

    # Fetch pending commands (unacknowledged, not expired, ordered by priority desc)
    pending_commands = db.iclependingcommand.find_many(
        where={
            "deviceId": device.id,
            "acknowledged": False,
            "OR": [
                {"expiresAt": None},
                {"expiresAt": {"gt": now}},
            ],
        },
        order={"priority": "desc"},
    )

    # Format pending commands for response
    commands_response = [
        {
            "id": cmd.id,
            "type": cmd.commandType,
            "payload": cmd.payload,
        }
        for cmd in pending_commands
    ]

    # Emit WebSocket event for frontend updates
    device_update = {
        "id": device.id,
        "deviceId": device.deviceId,
        "name": device.name,
        "ipAddress": device.ipAddress,
        "macAddress": device.macAddress,
        "firmwareVersion": device.firmwareVersion,
        "status": device.status,
        "registered": device.registered,
        "lastHeartbeat": device.lastHeartbeat.isoformat() if device.lastHeartbeat else None,
        "lastStatusData": status_data,
    }
    emit_icle_update(device_update)

    response = {
        "acknowledged": True,
        "registered": device.registered,
        "server_time": now.isoformat(),
        "heartbeat_interval_ms": 5000,
        "pending_commands": commands_response,
    }

    return jsonify(ApiResponse.ok(response).to_dict()), 200
