import logging
import math

from flask import g, jsonify, request

from src.lib.audit import log_audit
from src.lib.decorators import require_permissions
from src.lib.errors import bad_request, conflict, not_found
from src.lib.permissions import Permissions
from src.lib.types import ApiResponse
from src.services.database.prisma import get_db_client

from .types import UserCreateRequest, UserResponse, UserUpdateRequest

logger = logging.getLogger(__name__)


def _user_to_dict(user) -> dict:
    return UserResponse.from_user(user).to_dict()


@require_permissions(Permissions.USERS_VIEW)
def users_list():
    """List all users."""
    db = get_db_client()

    page = max(1, request.args.get("page", 1, type=int))
    limit = min(max(1, request.args.get("limit", 50, type=int)), 100)
    skip = (page - 1) * limit

    total = db.user.count()
    users = db.user.find_many(
        skip=skip,
        take=limit,
        order={"createdAt": "asc"},
        include={"permissionSet": True},
    )
    return jsonify(ApiResponse.ok({
        "data": [_user_to_dict(u) for u in users],
        "pagination": {
            "page": page,
            "limit": limit,
            "total": total,
            "pages": math.ceil(total / limit) if limit > 0 else 0,
        },
    }).to_dict()), 200


@require_permissions(Permissions.USERS_MANAGE)
def users_create():
    """Pre-register a new user.

    Body: { "email": "...", "name": "...", "permissionSetId": "..." }
    """
    data, error = UserCreateRequest.from_json(request.get_json())
    if error:
        return bad_request(error)

    db = get_db_client()

    existing = db.user.find_unique(where={"email": data.email})
    if existing:
        return conflict(f"User with email {data.email} already exists")

    # Validate permission set exists if provided
    if data.permissionSetId:
        perm_set = db.permissionset.find_unique(where={"id": data.permissionSetId})
        if not perm_set:
            return bad_request("Permission set not found")

    create_data = {"email": data.email, "name": data.name, "active": True}
    if data.permissionSetId:
        create_data["permissionSetId"] = data.permissionSetId

    user = db.user.create(
        data=create_data,
        include={"permissionSet": True},
    )
    log_audit("user.create", "User", user.id, {"name": data.name, "email": data.email})
    return jsonify(ApiResponse.created(_user_to_dict(user)).to_dict()), 201


@require_permissions(Permissions.USERS_MANAGE)
def users_update(user_id: str):
    """Update a user's name, permission set, or active status.

    Body: { "name?": "...", "permissionSetId?": "...", "active?": bool }
    """
    data, error = UserUpdateRequest.from_json(request.get_json())
    if error:
        return bad_request(error)

    db = get_db_client()
    user = db.user.find_unique(where={"id": user_id})
    if not user:
        return not_found("User not found")

    # Prevent admins from deactivating themselves
    if user_id == g.current_user["sub"] and data.active is False:
        return bad_request("Cannot deactivate your own account")

    # Validate permission set exists if provided
    if data._has_permission_set_id and data.permissionSetId:
        perm_set = db.permissionset.find_unique(where={"id": data.permissionSetId})
        if not perm_set:
            return bad_request("Permission set not found")

    update_data = data.to_update_data()
    updated = db.user.update(
        where={"id": user_id},
        data=update_data,
        include={"permissionSet": True},
    )
    log_audit("user.update", "User", user_id, {"before": {"name": user.name, "email": user.email, "active": user.active, "permissionSetId": user.permissionSetId}, "after": update_data})
    return jsonify(ApiResponse.ok(_user_to_dict(updated)).to_dict()), 200


@require_permissions(Permissions.USERS_MANAGE)
def users_delete(user_id: str):
    """Deactivate a user (soft delete)."""
    db = get_db_client()
    user = db.user.find_unique(where={"id": user_id})
    if not user:
        return not_found("User not found")

    if user_id == g.current_user["sub"]:
        return bad_request("Cannot deactivate your own account")

    db.user.update(where={"id": user_id}, data={"active": False})
    log_audit("user.deactivate", "User", user_id, {"name": user.name, "email": user.email})
    return jsonify(ApiResponse.deleted().to_dict()), 200
