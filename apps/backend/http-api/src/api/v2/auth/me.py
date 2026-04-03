import logging

from flask import g, jsonify, request

from src.lib.decorators import require_permissions
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

    # View As support: Admin/Maintainer can simulate another role
    view_as_role = request.headers.get("X-View-As-Role")
    effective_view_as = None
    if view_as_role and user_role in ("ADMIN", "MAINTAINER"):
        from src.lib.decorators import ROLE_HIERARCHY
        if view_as_role in ROLE_HIERARCHY:
            effective_view_as = view_as_role

    return jsonify(ApiResponse.ok(
        {
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "role": user_role,
            "viewAsRole": effective_view_as,
            "permissionSetId": user.permissionSetId,
            "permissionSetName": user.permissionSet.name if user.permissionSet else None,
            "permissions": user.permissionSet.permissions if user.permissionSet else [],
            "productAccess": product_access,
            "active": user.active,
            "lastSeenAt": user.lastSeenAt.isoformat() if user.lastSeenAt else None,
            "createdAt": user.createdAt.isoformat(),
        }
    ).to_dict()), 200
