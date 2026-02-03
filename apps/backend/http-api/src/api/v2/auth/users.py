from flask import g, jsonify, request

from src.lib.decorators import require_auth, require_permissions
from src.lib.permissions import Permissions
from src.services.database.prisma import get_db_client

from .types import UserCreateRequest, UserResponse, UserUpdateRequest


def _user_to_dict(user) -> dict:
    return UserResponse.from_user(user).to_dict()


@require_permissions(Permissions.ADMIN_USERS_VIEW)
def users_list():
    """List all users."""
    db = get_db_client()
    users = db.user.find_many(
        order={"createdAt": "asc"},
        include={"permissionSet": True},
    )
    return jsonify({"users": [_user_to_dict(u) for u in users]}), 200


@require_permissions(Permissions.ADMIN_USERS_MANAGE)
def users_create():
    """Pre-register a new user.

    Body: { "email": "...", "name": "...", "permissionSetId": "..." }
    """
    data, error = UserCreateRequest.from_json(request.get_json())
    if error:
        return jsonify({"error": error}), 400

    db = get_db_client()

    existing = db.user.find_unique(where={"email": data.email})
    if existing:
        return jsonify({"error": f"User with email {data.email} already exists"}), 409

    # Validate permission set exists if provided
    if data.permissionSetId:
        perm_set = db.permissionset.find_unique(where={"id": data.permissionSetId})
        if not perm_set:
            return jsonify({"error": "Permission set not found"}), 400

    create_data = {"email": data.email, "name": data.name, "active": True}
    if data.permissionSetId:
        create_data["permissionSetId"] = data.permissionSetId

    user = db.user.create(
        data=create_data,
        include={"permissionSet": True},
    )
    return jsonify({"user": _user_to_dict(user)}), 201


@require_permissions(Permissions.ADMIN_USERS_MANAGE)
def users_update(user_id: str):
    """Update a user's name, permission set, or active status.

    Body: { "name?": "...", "permissionSetId?": "...", "active?": bool }
    """
    data, error = UserUpdateRequest.from_json(request.get_json())
    if error:
        return jsonify({"error": error}), 400

    db = get_db_client()
    user = db.user.find_unique(where={"id": user_id})
    if not user:
        return jsonify({"error": "User not found"}), 404

    # Prevent admins from deactivating themselves
    if user_id == g.current_user["sub"] and data.active is False:
        return jsonify({"error": "Cannot deactivate your own account"}), 400

    # Validate permission set exists if provided
    if data._has_permission_set_id and data.permissionSetId:
        perm_set = db.permissionset.find_unique(where={"id": data.permissionSetId})
        if not perm_set:
            return jsonify({"error": "Permission set not found"}), 400

    update_data = data.to_update_data()
    updated = db.user.update(
        where={"id": user_id},
        data=update_data,
        include={"permissionSet": True},
    )
    return jsonify({"user": _user_to_dict(updated)}), 200


@require_permissions(Permissions.ADMIN_USERS_MANAGE)
def users_delete(user_id: str):
    """Deactivate a user (soft delete)."""
    db = get_db_client()
    user = db.user.find_unique(where={"id": user_id})
    if not user:
        return jsonify({"error": "User not found"}), 404

    if user_id == g.current_user["sub"]:
        return jsonify({"error": "Cannot deactivate your own account"}), 400

    db.user.update(where={"id": user_id}, data={"active": False})
    return jsonify({"message": "User deactivated"}), 200
