"""ICLE device config push endpoint."""

import logging

from database import Json
from flask import jsonify, request

from src.lib.audit import log_audit
from src.lib.decorators import require_permissions
from src.lib.errors import bad_request, not_found
from src.lib.permissions import Permissions
from src.lib.types import ApiResponse
from src.services.database.prisma import get_db_client

from .types import ConfigPushRequest

logger = logging.getLogger(__name__)


@require_permissions(Permissions.DEVICES_MANAGE)
def push_config(device_id: str):
    """Queue a config_update command for an ICLE device.

    PUT /v2/icle/devices/:id/config

    Request body:
        {
            "config": {
                "sample_rate_hz": 10,
                "channels": [0, 1],
                "log_format": "binary"
            }
        }

    The config will be delivered to the device on its next heartbeat.
    """
    req, error = ConfigPushRequest.from_json(request.get_json())
    if error:
        return bad_request(error)

    db = get_db_client()

    # Check device exists
    device = db.icledevice.find_unique(where={"id": device_id})
    if not device:
        return not_found("ICLE device not found")

    # Create pending command
    command = db.iclependingcommand.create(
        data={
            "deviceId": device_id,
            "commandType": "config_update",
            "payload": Json(req.config),
            "priority": 10,  # Config updates have medium priority
        },
    )

    # Also update pendingConfig on device for UI display
    db.icledevice.update(
        where={"id": device_id},
        data={"pendingConfig": Json(req.config)},
    )

    log_audit("icle.config.push", "IcleDevice", device_id, {"config": req.config})

    return jsonify(ApiResponse.ok({
        "commandId": command.id,
        "commandType": command.commandType,
        "queued": True,
    }).to_dict()), 200
