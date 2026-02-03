from flask import Blueprint, g, jsonify

from src.middleware.auth import require_auth
from src.services.database.prisma import get_db_client

v2_auth_me_bp = Blueprint("v2_auth_me", __name__)


@v2_auth_me_bp.route("/v2/auth/me", methods=["GET"])
@require_auth
def v2_auth_me():
    """Return the full profile of the authenticated user."""
    db = get_db_client()
    user = db.user.find_unique(where={"id": g.current_user["sub"]})

    if not user:
        return jsonify({"error": "User not found"}), 404

    return jsonify(
        {
            "user": {
                "id": user.id,
                "email": user.email,
                "name": user.name,
                "role": user.role,
                "active": user.active,
                "lastSeenAt": user.lastSeenAt.isoformat() if user.lastSeenAt else None,
                "createdAt": user.createdAt.isoformat(),
            }
        }
    ), 200
