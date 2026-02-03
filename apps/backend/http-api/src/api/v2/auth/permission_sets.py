from flask import jsonify, request

from src.lib.decorators import invalidate_permission_set_cache, require_permissions
from src.lib.permissions import Permissions
from src.services.database.prisma import get_db_client

from .types import PermissionSetCreateRequest, PermissionSetUpdateRequest

# All valid permission keys for validation
_VALID_PERMISSIONS = {p["key"] for p in Permissions.all()}


@require_permissions(Permissions.ADMIN_PERMISSION_SETS_VIEW)
def list_permission_sets():
    """List all permission sets."""
    db = get_db_client()
    sets = db.permissionset.find_many(
        order={"createdAt": "asc"},
        include={"users": True},
    )

    return jsonify(
        {
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
            ]
        }
    ), 200


@require_permissions(Permissions.ADMIN_PERMISSION_SETS_MANAGE)
def create_permission_set():
    """Create a new permission set.

    Body: { "name": "...", "description?": "...", "permissions": ["Concord.Firmware.AppID.View", ...] }
    """
    data, error = PermissionSetCreateRequest.from_json(request.get_json())
    if error:
        return jsonify({"error": error}), 400

    # Validate permission strings
    invalid = [p for p in data.permissions if p not in _VALID_PERMISSIONS]
    if invalid:
        return jsonify({"error": f"Invalid permission(s): {', '.join(invalid)}"}), 400

    db = get_db_client()

    # Check for duplicate name
    existing = db.permissionset.find_unique(where={"name": data.name})
    if existing:
        return jsonify({"error": f"Permission set '{data.name}' already exists"}), 409

    create_data = {
        "name": data.name,
        "permissions": data.permissions,
    }
    if data.description is not None:
        create_data["description"] = data.description

    perm_set = db.permissionset.create(data=create_data)

    return jsonify(
        {
            "data": {
                "id": perm_set.id,
                "name": perm_set.name,
                "description": perm_set.description,
                "permissions": perm_set.permissions,
                "createdAt": perm_set.createdAt.isoformat(),
                "updatedAt": perm_set.updatedAt.isoformat(),
            }
        }
    ), 201


@require_permissions(Permissions.ADMIN_PERMISSION_SETS_MANAGE)
def update_permission_set(set_id: str):
    """Update a permission set.

    Body: { "name?": "...", "description?": "...", "permissions?": [...] }
    """
    data, error = PermissionSetUpdateRequest.from_json(request.get_json())
    if error:
        return jsonify({"error": error}), 400

    db = get_db_client()

    existing = db.permissionset.find_unique(where={"id": set_id})
    if not existing:
        return jsonify({"error": "Permission set not found"}), 404

    # Validate permission strings if provided
    if data.permissions is not None:
        invalid = [p for p in data.permissions if p not in _VALID_PERMISSIONS]
        if invalid:
            return jsonify({"error": f"Invalid permission(s): {', '.join(invalid)}"}), 400

    update_data = {}
    if data.name is not None:
        # Check for duplicate name
        if data.name != existing.name:
            dup = db.permissionset.find_unique(where={"name": data.name})
            if dup:
                return jsonify({"error": f"Permission set '{data.name}' already exists"}), 409
        update_data["name"] = data.name
    if data._has_description:
        update_data["description"] = data.description
    if data.permissions is not None:
        update_data["permissions"] = data.permissions

    perm_set = db.permissionset.update(where={"id": set_id}, data=update_data)

    # Invalidate cache
    invalidate_permission_set_cache(set_id)

    return jsonify(
        {
            "data": {
                "id": perm_set.id,
                "name": perm_set.name,
                "description": perm_set.description,
                "permissions": perm_set.permissions,
                "createdAt": perm_set.createdAt.isoformat(),
                "updatedAt": perm_set.updatedAt.isoformat(),
            }
        }
    ), 200


@require_permissions(Permissions.ADMIN_PERMISSION_SETS_MANAGE)
def delete_permission_set(set_id: str):
    """Delete a permission set. Fails if users are still assigned."""
    db = get_db_client()

    existing = db.permissionset.find_unique(
        where={"id": set_id},
        include={"users": True},
    )
    if not existing:
        return jsonify({"error": "Permission set not found"}), 404

    if existing.users and len(existing.users) > 0:
        return jsonify({"error": "Cannot delete permission set with assigned users"}), 409

    db.permissionset.delete(where={"id": set_id})

    # Invalidate cache
    invalidate_permission_set_cache(set_id)

    return jsonify({"message": "Permission set deleted"}), 200
