from flask import Blueprint, g, jsonify, request

from src.middleware.auth import require_auth, require_role
from src.services.database.prisma import get_db_client

v2_auth_users_bp = Blueprint("v2_auth_users", __name__)


def _user_to_dict(user) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "role": user.role,
        "active": user.active,
        "lastSeenAt": user.lastSeenAt.isoformat() if user.lastSeenAt else None,
        "createdAt": user.createdAt.isoformat(),
        "updatedAt": user.updatedAt.isoformat(),
    }


@v2_auth_users_bp.route("/v2/auth/users", methods=["GET"])
@require_auth
@require_role("ADMIN")
def v2_auth_users_list():
    """List all users. Admin only."""
    db = get_db_client()
    users = db.user.find_many(order={"createdAt": "asc"})
    return jsonify({"users": [_user_to_dict(u) for u in users]}), 200


@v2_auth_users_bp.route("/v2/auth/users", methods=["POST"])
@require_auth
@require_role("ADMIN")
def v2_auth_users_create():
    """Pre-register a new user. Admin only.

    Body: { "email": "...", "name": "...", "role": "VIEWER"|"OPERATOR"|"ADMIN" }
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body required"}), 400

    email = data.get("email", "").strip().lower()
    name = data.get("name", "").strip()
    role = data.get("role", "VIEWER").upper()

    if not email:
        return jsonify({"error": "Email is required"}), 400
    if not name:
        return jsonify({"error": "Name is required"}), 400
    if role not in ("ADMIN", "OPERATOR", "VIEWER"):
        return jsonify({"error": "Role must be ADMIN, OPERATOR, or VIEWER"}), 400

    db = get_db_client()

    existing = db.user.find_unique(where={"email": email})
    if existing:
        return jsonify({"error": f"User with email {email} already exists"}), 409

    user = db.user.create(data={"email": email, "name": name, "role": role, "active": True})
    return jsonify({"user": _user_to_dict(user)}), 201


@v2_auth_users_bp.route("/v2/auth/users/<user_id>", methods=["PUT"])
@require_auth
@require_role("ADMIN")
def v2_auth_users_update(user_id: str):
    """Update a user's role or active status. Admin only.

    Body: { "name?": "...", "role?": "...", "active?": bool }
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body required"}), 400

    db = get_db_client()
    user = db.user.find_unique(where={"id": user_id})
    if not user:
        return jsonify({"error": "User not found"}), 404

    # Prevent admins from deactivating themselves
    if user_id == g.current_user["sub"] and data.get("active") is False:
        return jsonify({"error": "Cannot deactivate your own account"}), 400

    update_data = {}
    if "name" in data:
        update_data["name"] = data["name"].strip()
    if "role" in data:
        role = data["role"].upper()
        if role not in ("ADMIN", "OPERATOR", "VIEWER"):
            return jsonify({"error": "Role must be ADMIN, OPERATOR, or VIEWER"}), 400
        update_data["role"] = role
    if "active" in data:
        update_data["active"] = bool(data["active"])

    if not update_data:
        return jsonify({"error": "No fields to update"}), 400

    updated = db.user.update(where={"id": user_id}, data=update_data)
    return jsonify({"user": _user_to_dict(updated)}), 200


@v2_auth_users_bp.route("/v2/auth/users/<user_id>", methods=["DELETE"])
@require_auth
@require_role("ADMIN")
def v2_auth_users_delete(user_id: str):
    """Deactivate a user (soft delete). Admin only."""
    db = get_db_client()
    user = db.user.find_unique(where={"id": user_id})
    if not user:
        return jsonify({"error": "User not found"}), 404

    if user_id == g.current_user["sub"]:
        return jsonify({"error": "Cannot deactivate your own account"}), 400

    db.user.update(where={"id": user_id}, data={"active": False})
    return jsonify({"message": "User deactivated"}), 200
