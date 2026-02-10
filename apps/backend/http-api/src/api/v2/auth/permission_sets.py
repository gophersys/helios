import logging
import math

from flask import jsonify, request

from src.lib.audit import log_audit
from src.lib.decorators import invalidate_permission_set_cache, require_permissions
from src.lib.errors import bad_request, conflict, not_found
from src.lib.permissions import Permissions
from src.lib.types import ApiResponse
from src.services.database.prisma import get_db_client

from .types import PermissionSetCreateRequest, PermissionSetUpdateRequest

logger = logging.getLogger(__name__)

# All valid permission keys for validation
_VALID_PERMISSIONS = {p["key"] for p in Permissions.all()}


@require_permissions(Permissions.ADMIN_PERMISSION_SETS_VIEW)
def list_permission_sets():
    """List all permission sets."""
    db = get_db_client()

    page = max(1, request.args.get("page", 1, type=int))
    limit = min(max(1, request.args.get("limit", 50, type=int)), 100)
    skip = (page - 1) * limit

    total = db.permissionset.count()
    sets = db.permissionset.find_many(
        skip=skip,
        take=limit,
        order={"createdAt": "asc"},
        include={"users": True},
    )

    return jsonify(ApiResponse.ok({
        "data": [
            {
                "id": s.id,
                "name": s.name,
                "description": s.description,
                "permissions": s.permissions,
                "userCount": len(s.users) if s.users else 0,
                "users": [
                    {"id": u.id, "name": u.name, "email": u.email}
                    for u in (s.users or [])
                ],
                "createdAt": s.createdAt.isoformat(),
                "updatedAt": s.updatedAt.isoformat(),
            }
            for s in sets
        ],
        "pagination": {
            "page": page,
            "limit": limit,
            "total": total,
            "pages": math.ceil(total / limit) if limit > 0 else 0,
        },
    }).to_dict()), 200


@require_permissions(Permissions.ADMIN_PERMISSION_SETS_MANAGE)
def create_permission_set():
    """Create a new permission set.

    Body: { "name": "...", "description?": "...", "permissions": ["Concord.Cluster.Read", ...] }
    """
    data, error = PermissionSetCreateRequest.from_json(request.get_json())
    if error:
        return bad_request(error)

    # Validate permission strings
    invalid = [p for p in data.permissions if p not in _VALID_PERMISSIONS]
    if invalid:
        return bad_request(f"Invalid permission(s): {', '.join(invalid)}")

    db = get_db_client()

    # Check for duplicate name
    existing = db.permissionset.find_unique(where={"name": data.name})
    if existing:
        return conflict(f"Permission set '{data.name}' already exists")

    create_data = {
        "name": data.name,
        "permissions": data.permissions,
    }
    if data.description is not None:
        create_data["description"] = data.description

    perm_set = db.permissionset.create(data=create_data)
    log_audit("permissionSet.create", "PermissionSet", perm_set.id, {"name": data.name, "permissionCount": len(data.permissions)})

    return jsonify(ApiResponse.created({
        "id": perm_set.id,
        "name": perm_set.name,
        "description": perm_set.description,
        "permissions": perm_set.permissions,
        "createdAt": perm_set.createdAt.isoformat(),
        "updatedAt": perm_set.updatedAt.isoformat(),
    }).to_dict()), 201


@require_permissions(Permissions.ADMIN_PERMISSION_SETS_MANAGE)
def update_permission_set(set_id: str):
    """Update a permission set.

    Body: { "name?": "...", "description?": "...", "permissions?": [...] }
    """
    data, error = PermissionSetUpdateRequest.from_json(request.get_json())
    if error:
        return bad_request(error)

    db = get_db_client()

    existing = db.permissionset.find_unique(where={"id": set_id})
    if not existing:
        return not_found("Permission set not found")

    # Validate permission strings if provided
    if data.permissions is not None:
        invalid = [p for p in data.permissions if p not in _VALID_PERMISSIONS]
        if invalid:
            return bad_request(f"Invalid permission(s): {', '.join(invalid)}")

    # Check for duplicate name
    if data.name is not None and data.name != existing.name:
        dup = db.permissionset.find_unique(where={"name": data.name})
        if dup:
            return conflict(f"Permission set '{data.name}' already exists")

    update_data = data.to_update_data()
    perm_set = db.permissionset.update(where={"id": set_id}, data=update_data)

    # Invalidate cache
    invalidate_permission_set_cache(set_id)

    log_audit("permissionSet.update", "PermissionSet", set_id, {"before": {"name": existing.name, "permissions": existing.permissions}, "after": update_data})

    return jsonify(ApiResponse.ok({
        "id": perm_set.id,
        "name": perm_set.name,
        "description": perm_set.description,
        "permissions": perm_set.permissions,
        "createdAt": perm_set.createdAt.isoformat(),
        "updatedAt": perm_set.updatedAt.isoformat(),
    }).to_dict()), 200


@require_permissions(Permissions.ADMIN_PERMISSION_SETS_MANAGE)
def delete_permission_set(set_id: str):
    """Delete a permission set. Fails if users are still assigned."""
    db = get_db_client()

    existing = db.permissionset.find_unique(
        where={"id": set_id},
        include={"users": True},
    )
    if not existing:
        return not_found("Permission set not found")

    if existing.users and len(existing.users) > 0:
        return conflict("Cannot delete permission set with assigned users")

    db.permissionset.delete(where={"id": set_id})

    # Invalidate cache
    invalidate_permission_set_cache(set_id)

    log_audit("permissionSet.delete", "PermissionSet", set_id, {"name": existing.name})
    return jsonify(ApiResponse.deleted().to_dict()), 200
