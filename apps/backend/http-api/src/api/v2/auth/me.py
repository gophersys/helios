import logging

from flask import g, jsonify

from src.lib.decorators import require_permissions
from src.lib.errors import not_found
from src.lib.types import ApiResponse
from src.services.database.prisma import get_db_client

logger = logging.getLogger(__name__)


@require_permissions()
def me():
    """Return the full profile of the authenticated user."""
    db = get_db_client()
    user = db.user.find_unique(
        where={"id": g.current_user["sub"]},
        include={"permissionSet": True},
    )

    if not user:
        return not_found("User not found")

    return jsonify(ApiResponse.ok(
        {
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "permissionSetId": user.permissionSetId,
            "permissionSetName": user.permissionSet.name if user.permissionSet else None,
            "permissions": user.permissionSet.permissions if user.permissionSet else [],
            "active": user.active,
            "lastSeenAt": user.lastSeenAt.isoformat() if user.lastSeenAt else None,
            "createdAt": user.createdAt.isoformat(),
        }
    ).to_dict()), 200
