"""ICLE device CRUD endpoints with authentication."""

import logging

from flask import jsonify, request

from src.lib.audit import log_audit
from src.lib.decorators import require_permissions
from src.lib.errors import bad_request, not_found
from src.lib.permissions import Permissions
from src.lib.types import ApiResponse
from src.services.database.prisma import get_db_client

from .types import DeviceUpdateRequest

logger = logging.getLogger(__name__)


def _serialize_device(device, include_commands: bool = False) -> dict:
    """Serialize IcleDevice to JSON-compatible dict."""
    result = {
        "id": device.id,
        "deviceId": device.deviceId,
        "name": device.name,
        "ipAddress": device.ipAddress,
        "macAddress": device.macAddress,
        "firmwareVersion": device.firmwareVersion,
        "status": device.status,
        "registered": device.registered,
        "lastHeartbeat": device.lastHeartbeat.isoformat() if device.lastHeartbeat else None,
        "lastStatusData": device.lastStatusData,
        "pendingConfig": device.pendingConfig,
        "metadata": device.metadata,
        "createdAt": device.createdAt.isoformat() if device.createdAt else None,
        "updatedAt": device.updatedAt.isoformat() if device.updatedAt else None,
    }

    if include_commands and hasattr(device, "commands") and device.commands:
        result["pendingCommands"] = [
            {
                "id": cmd.id,
                "commandType": cmd.commandType,
                "payload": cmd.payload,
                "priority": cmd.priority,
                "createdAt": cmd.createdAt.isoformat() if cmd.createdAt else None,
                "expiresAt": cmd.expiresAt.isoformat() if cmd.expiresAt else None,
                "acknowledged": cmd.acknowledged,
            }
            for cmd in device.commands
        ]

    return result


@require_permissions(Permissions.DEVICES_VIEW)
def list_devices():
    """List all ICLE devices with pagination.

    GET /v2/icle/devices?page=1&limit=50&registered=true&status=ONLINE
    """
    db = get_db_client()

    # Pagination
    page = max(1, request.args.get("page", 1, type=int))
    limit = min(max(1, request.args.get("limit", 50, type=int)), 100)
    skip = (page - 1) * limit

    # Build filter
    where = {}

    # Filter by registered status
    registered = request.args.get("registered")
    if registered is not None:
        where["registered"] = registered.lower() == "true"

    # Filter by device status
    status = request.args.get("status")
    if status:
        where["status"] = status.upper()

    # Get total count
    total = db.icledevice.count(where=where)

    # Fetch devices
    devices = db.icledevice.find_many(
        where=where,
        skip=skip,
        take=limit,
        order={"updatedAt": "desc"},
    )

    pages = (total + limit - 1) // limit if total > 0 else 1

    return jsonify(ApiResponse.paginated(
        data=[_serialize_device(d) for d in devices],
        page=page,
        total_pages=pages,
        total_results=total,
        results_per_page=limit,
    ).to_dict()), 200


@require_permissions(Permissions.DEVICES_VIEW)
def get_device(device_id: str):
    """Get a single ICLE device by ID.

    GET /v2/icle/devices/:id
    """
    db = get_db_client()

    device = db.icledevice.find_unique(
        where={"id": device_id},
        include={
            "commands": {
                "where": {"acknowledged": False},
                "order_by": {"priority": "desc"},
            },
        },
    )

    if not device:
        return not_found("ICLE device not found")

    return jsonify(ApiResponse.ok(_serialize_device(device, include_commands=True)).to_dict()), 200


@require_permissions(Permissions.DEVICES_MANAGE)
def update_device(device_id: str):
    """Update an ICLE device.

    PUT /v2/icle/devices/:id

    Request body:
        {
            "name": "My ICLE Device",
            "registered": true,
            "pendingConfig": {"key": "value"}
        }
    """
    req, error = DeviceUpdateRequest.from_json(request.get_json())
    if error:
        return bad_request(error)

    db = get_db_client()

    # Check device exists
    device = db.icledevice.find_unique(where={"id": device_id})
    if not device:
        return not_found("ICLE device not found")

    # Build update data
    update_data = req.to_update_data()
    if not update_data:
        return bad_request("No fields to update")

    # Update device
    device = db.icledevice.update(
        where={"id": device_id},
        data=update_data,
    )

    log_audit("icle.device.update", "IcleDevice", device_id, update_data)

    return jsonify(ApiResponse.ok(_serialize_device(device)).to_dict()), 200


@require_permissions(Permissions.DEVICES_MANAGE)
def delete_device(device_id: str):
    """Delete an ICLE device.

    DELETE /v2/icle/devices/:id
    """
    db = get_db_client()

    # Check device exists
    device = db.icledevice.find_unique(where={"id": device_id})
    if not device:
        return not_found("ICLE device not found")

    # Delete device (cascades to commands and logs)
    db.icledevice.delete(where={"id": device_id})

    log_audit("icle.device.delete", "IcleDevice", device_id, {"deviceId": device.deviceId})

    return jsonify(ApiResponse.deleted().to_dict()), 200
