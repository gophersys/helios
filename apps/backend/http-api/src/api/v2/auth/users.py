import logging
import math

from flask import g, jsonify, request

from src.lib.audit import log_audit
from src.lib.decorators import require_permissions
from src.lib.errors import bad_request, conflict, not_found
from src.lib.permissions import Permissions
from src.lib.types import ApiResponse
from src.services.database.prisma import get_db_client

from .types import (
    ProductAccessSetRequest,
    UserCreateRequest,
    UserResponse,
    UserUpdateRequest,
)

logger = logging.getLogger(__name__)

VALID_ROLES = {"ADMIN", "MAINTAINER", "DEVELOPER", "OPERATOR"}


def _user_to_dict(user) -> dict:
    """Convert a User DB record to a serializable dict via UserResponse."""
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

    Body: { "email": "...", "name": "...", "role?": "...", "permissionSetId": "..." }
    """
    data, error = UserCreateRequest.from_json(request.get_json())
    if error or data is None:
        return bad_request(error)

    db = get_db_client()

    existing = db.user.find_unique(where={"email": data.email})
    if existing:
        return conflict(f"User with email {data.email} already exists")

    # Validate role if provided
    if data.role and data.role not in VALID_ROLES:
        return bad_request(f"Invalid role. Must be one of: {', '.join(sorted(VALID_ROLES))}")

    # Validate permission set exists if provided
    if data.permissionSetId:
        perm_set = db.permissionset.find_unique(where={"id": data.permissionSetId})
        if not perm_set:
            return bad_request("Permission set not found")

    create_data = {"email": data.email, "name": data.name, "active": True}
    if data.role:
        create_data["role"] = data.role
    if data.permissionSetId:
        create_data["permissionSetId"] = data.permissionSetId

    user = db.user.create(
        data=create_data,
        include={"permissionSet": True},
    )
    log_audit("user.create", "User", user.id, {"name": data.name, "email": data.email, "role": data.role})
    return jsonify(ApiResponse.created(_user_to_dict(user)).to_dict()), 201


@require_permissions(Permissions.USERS_MANAGE)
def users_update(user_id: str):
    """Update a user's name, role, permission set, or active status.

    Body: { "name?": "...", "role?": "...", "permissionSetId?": "...", "active?": bool }
    """
    data, error = UserUpdateRequest.from_json(request.get_json())
    if error or data is None:
        return bad_request(error)

    db = get_db_client()
    user = db.user.find_unique(where={"id": user_id})
    if not user:
        return not_found("User not found")

    # Prevent admins from deactivating themselves
    if user_id == g.current_user["sub"] and data.active is False:
        return bad_request("Cannot deactivate your own account")

    # Validate role if provided
    if data._has_role and data.role and data.role not in VALID_ROLES:
        return bad_request(f"Invalid role. Must be one of: {', '.join(sorted(VALID_ROLES))}")

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
def users_set_role(user_id: str):
    """PUT /v2/users/<user_id>/role -- Set a user's role.

    Body: { "role": "ADMIN" | "MAINTAINER" | "DEVELOPER" | "OPERATOR" }
    """
    data = request.get_json()
    if not data:
        return bad_request("Request body must contain JSON data")

    role = data.get("role")
    if not role or not isinstance(role, str):
        return bad_request("Role is required")
    role = role.strip().upper()
    if role not in VALID_ROLES:
        return bad_request(f"Invalid role. Must be one of: {', '.join(sorted(VALID_ROLES))}")

    db = get_db_client()
    user = db.user.find_unique(where={"id": user_id})
    if not user:
        return not_found("User not found")

    # Prevent admins from demoting themselves
    if user_id == g.current_user["sub"] and role != user.role:
        return bad_request("Cannot change your own role")

    old_role = getattr(user, "role", "DEVELOPER")
    updated = db.user.update(
        where={"id": user_id},
        data={"role": role},
        include={"permissionSet": True},
    )
    log_audit("user.role.update", "User", user_id, {"before": old_role, "after": role})
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


@require_permissions(Permissions.USERS_VIEW)
def users_get_product_access(user_id: str):
    """GET /v2/users/<user_id>/product-access -- List a user's product access entries."""
    db = get_db_client()
    user = db.user.find_unique(where={"id": user_id})
    if not user:
        return not_found("User not found")

    access_entries = db.productaccess.find_many(
        where={"userId": user_id},
        include={"product": True},
        order={"createdAt": "asc"},
    )

    data = []
    for pa in access_entries:
        entry = {
            "id": pa.id,
            "userId": pa.userId,
            "productId": pa.productId,
            "level": pa.level,
            "createdAt": pa.createdAt.isoformat(),
            "updatedAt": pa.updatedAt.isoformat(),
        }
        if hasattr(pa, "product") and pa.product:
            entry["productName"] = pa.product.name
            entry["productSlug"] = getattr(pa.product, "slug", None)
        data.append(entry)

    return jsonify(ApiResponse.ok(data).to_dict()), 200


@require_permissions(Permissions.USERS_MANAGE)
def users_set_product_access(user_id: str):
    """PUT /v2/users/<user_id>/product-access -- Set product access for a user.

    Body: { "access": [{ "productId": "...", "level": "view|operate|develop|admin" }, ...] }
    Replaces all existing product access entries for this user.
    """
    req_data, error = ProductAccessSetRequest.from_json(request.get_json())
    if error or req_data is None:
        return bad_request(error)

    db = get_db_client()
    user = db.user.find_unique(where={"id": user_id})
    if not user:
        return not_found("User not found")

    # Validate all product IDs exist
    for entry in req_data.access:
        product = db.product.find_unique(where={"id": entry["productId"]})
        if not product:
            return bad_request(f"Product not found: {entry['productId']}")

    # Delete all existing access for this user
    db.productaccess.delete_many(where={"userId": user_id})

    # Create new access entries
    created = []
    for entry in req_data.access:
        pa = db.productaccess.create(
            data={
                "userId": user_id,
                "productId": entry["productId"],
                "level": entry["level"],
            },
            include={"product": True},
        )
        result = {
            "id": pa.id,
            "userId": pa.userId,
            "productId": pa.productId,
            "level": pa.level,
            "createdAt": pa.createdAt.isoformat(),
            "updatedAt": pa.updatedAt.isoformat(),
        }
        if hasattr(pa, "product") and pa.product:
            result["productName"] = pa.product.name
        created.append(result)

    log_audit(
        "user.product_access.set", "User", user_id,
        {"access": [{"productId": e["productId"], "level": e["level"]} for e in req_data.access]},
    )

    return jsonify(ApiResponse.ok(created).to_dict()), 200
