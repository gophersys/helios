"""ICLE device OTA trigger endpoint."""

import logging

from database import Json
from flask import jsonify, request

from src.lib.audit import log_audit
from src.lib.decorators import require_permissions
from src.lib.errors import bad_request, not_found
from src.lib.permissions import Permissions
from src.lib.types import ApiResponse
from src.services.database.prisma import get_db_client

from .types import OtaTriggerRequest

logger = logging.getLogger(__name__)


@require_permissions(Permissions.DEVICES_MANAGE)
def trigger_ota(device_id: str):
    """Queue an OTA update command for an ICLE device.

    POST /v2/icle/devices/:id/ota

    Request body:
        {
            "url": "https://example.com/firmware/icle-v1.1.0.bin",
            "version": "1.1.0",
            "checksum": "abc123..."
        }

    The OTA command will be delivered to the device on its next heartbeat.
    """
    req, error = OtaTriggerRequest.from_json(request.get_json())
    if error or req is None:
        return bad_request(error)

    db = get_db_client()

    # Check device exists
    device = db.icledevice.find_unique(where={"id": device_id})
    if not device:
        return not_found("ICLE device not found")

    # Build OTA payload
    payload = {
        "url": req.url,
        "version": req.version,
    }
    if req.checksum:
        payload["checksum"] = req.checksum

    # Create pending command with high priority
    command = db.iclependingcommand.create(
        data={
            "deviceId": device_id,
            "commandType": "ota_trigger",
            "payload": Json(payload),
            "priority": 100,  # OTA commands have highest priority
        },
    )

    log_audit("icle.ota.trigger", "IcleDevice", device_id, payload)

    return jsonify(ApiResponse.ok({
        "commandId": command.id,
        "commandType": command.commandType,
        "queued": True,
        "version": req.version,
    }).to_dict()), 200
