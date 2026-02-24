"""ICLE command acknowledgment endpoint."""

import logging

from flask import jsonify

from src.lib.decorators import require_auth
from src.lib.errors import not_found
from src.lib.types import ApiResponse
from src.services.database.prisma import get_db_client

logger = logging.getLogger(__name__)


@require_auth
def acknowledge_command(command_id: str):
    """Mark a pending command as acknowledged.

    POST /v2/icle/commands/:id/ack

    This endpoint requires basic auth but not specific permissions,
    as it's called by devices to acknowledge commands.
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

    return jsonify(ApiResponse.ok({"acknowledged": True}).to_dict()), 200
