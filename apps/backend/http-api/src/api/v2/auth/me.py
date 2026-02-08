from flask import g, jsonify

from config import env_config
from src.lib.decorators import require_permissions
from src.lib.errors import not_found
from src.lib.types import ApiResponse
from src.services.database.prisma import get_db_client


@require_permissions()
def me():
    """Return the full profile of the authenticated user."""
    if not env_config.AUTH_ENABLED:
        return jsonify(ApiResponse.ok(
            {
                "id": "00000000-0000-0000-0000-000000000000",
                "email": "admin@concord.local",
                "name": "Admin (auth disabled)",
                "permissionSetId": None,
                "permissionSetName": "Full Access",
                "permissions": ["Concord.Admin.All.Manage"],
                "active": True,
                "lastSeenAt": None,
                "createdAt": "2026-01-01T00:00:00",
            }
        ).to_dict()), 200

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
