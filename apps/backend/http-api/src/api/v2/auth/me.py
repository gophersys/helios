from flask import g, jsonify

from src.lib.decorators import require_auth
from src.services.database.prisma import get_db_client


@require_auth
def me():
    """Return the full profile of the authenticated user."""
    db = get_db_client()
    user = db.user.find_unique(
        where={"id": g.current_user["sub"]},
        include={"permissionSet": True},
    )

    if not user:
        return jsonify({"error": "User not found"}), 404

    return jsonify(
        {
            "user": {
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
        }
    ), 200
