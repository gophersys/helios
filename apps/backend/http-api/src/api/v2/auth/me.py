import logging

from flask import g, jsonify, request

from src.lib.decorators import require_permissions, ROLE_HIERARCHY
from src.lib.errors import not_found
from src.lib.types import ApiResponse
from src.services.database.prisma import get_db_client

logger = logging.getLogger(__name__)


@require_permissions()
def me():
    """Return the full profile of the authenticated user.

    Supports X-View-As-Role header for Admin/Maintainer users. When present,
    the response includes `viewAsRole` so the frontend can adjust its UI.
    """
    db = get_db_client()
    user = db.user.find_unique(
        where={"id": g.current_user["sub"]},
        include={
            "permissionSet": True,
            "productAccess": {"include": {"product": True}},
        },
    )

    if not user:
        return not_found("User not found")

    product_access = []
    if hasattr(user, "productAccess") and user.productAccess:
        for pa in user.productAccess:
            entry = {
                "id": pa.id,
                "productId": pa.productId,
                "level": pa.level,
            }
            if hasattr(pa, "product") and pa.product:
                entry["productName"] = pa.product.name
                entry["productSlug"] = pa.product.slug
            product_access.append(entry)

    user_role = getattr(user, "role", "DEVELOPER") or "DEVELOPER"

    # View As support: Admin/Maintainer can simulate another role's permissions
    view_as_role = request.headers.get("X-View-As-Role")
    effective_view_as = None
    effective_permissions = user.permissionSet.permissions if user.permissionSet else []
    effective_permission_set_name = user.permissionSet.name if user.permissionSet else None

    if view_as_role and user_role in ("ADMIN", "MAINTAINER"):
        if view_as_role in ROLE_HIERARCHY:
            effective_view_as = view_as_role
            # Look up the target role's permission set
            target_ps = db.permissionset.find_first(
                where={"name": view_as_role.capitalize()},
            )
            if target_ps:
                effective_permissions = target_ps.permissions
                effective_permission_set_name = target_ps.name

    return jsonify(ApiResponse.ok(
        {
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "role": user_role,
            "viewAsRole": effective_view_as,
            "permissionSetId": user.permissionSetId,
            "permissionSetName": effective_permission_set_name,
            "permissions": effective_permissions,
            "productAccess": product_access,
            "active": user.active,
            "lastSeenAt": user.lastSeenAt.isoformat() if user.lastSeenAt else None,
            "createdAt": user.createdAt.isoformat(),
        }
    ).to_dict()), 200
