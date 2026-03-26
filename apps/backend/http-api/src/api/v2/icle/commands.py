"""ICLE command acknowledgment endpoint."""

import logging

from flask import jsonify

from src.lib.audit import log_audit
from src.lib.decorators import require_permissions
from src.lib.errors import not_found
from src.lib.permissions import Permissions
from src.lib.types import ApiResponse
from src.services.database.prisma import get_db_client

logger = logging.getLogger(__name__)


@require_permissions(Permissions.DEVICES_MANAGE)
def acknowledge_command(command_id: str):
    """Mark a pending command as acknowledged.

    POST /v2/icle/commands/:id/ack
    """
    db = get_db_client()

    # Check command exists
    command = db.iclependingcommand.find_unique(where={"id": command_id})
    if not command:
        return not_found("Command not found")

    # Mark as acknowledged
    db.iclependingcommand.update(
        where={"id": command_id},
        data={"acknowledged": True},
    )

    log_audit("icle.command.acknowledge", "IclePendingCommand", command_id, {})

    return jsonify(ApiResponse.ok({"acknowledged": True}).to_dict()), 200
