"""Product-centric access management endpoints.

Provides CRUD operations for managing which users have access to a specific product
and at what level (view, operate, develop, admin).
"""

import logging

from flask import jsonify, request

from src.lib.audit import log_audit
from src.lib.decorators import require_permissions
from src.lib.errors import bad_request, conflict, not_found
from src.lib.permissions import Permissions
from src.lib.types import ApiResponse
from src.services.database.prisma import get_db_client

logger = logging.getLogger(__name__)

VALID_ACCESS_LEVELS = {"view", "operate", "develop", "admin"}
# Roles that bypass per-product access checks. Only the ADMIN role sees every
# product implicitly — granting ProductAccess to an admin is harmless but
# adds nothing. Maintainers, Developers and Operators all need an explicit
# entry to see a product.
BYPASS_ROLES = {"ADMIN"}


@require_permissions(Permissions.PRODUCTS_MANAGE)
def list_product_access(product_id: str):
    """List all users who have access to this product."""
    db = get_db_client()
    product = db.product.find_unique(where={"id": product_id})
    if not product:
        return not_found("Product not found")

    access_entries = db.productaccess.find_many(
        where={"productId": product_id},
        include={"user": True},
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
        if hasattr(pa, "user") and pa.user:
            entry["userName"] = pa.user.name
            entry["userEmail"] = pa.user.email
            entry["userRole"] = pa.user.role
        data.append(entry)

    return jsonify(ApiResponse.ok(data).to_dict()), 200


@require_permissions(Permissions.PRODUCTS_MANAGE)
def grant_product_access(product_id: str):
    """Grant a user access to this product.

    Body: { "userId": "...", "level": "view|operate|develop|admin" }
    """
    body = request.get_json()
    if not body:
        return bad_request("Request body must contain JSON data")

    user_id = (body.get("userId") or "").strip()
    if not user_id:
        return bad_request("userId is required")

    level = (body.get("level") or "").strip().lower()
    if not level:
        return bad_request("level is required")
    if level not in VALID_ACCESS_LEVELS:
        return bad_request(
            f"Invalid access level. Must be one of: {', '.join(sorted(VALID_ACCESS_LEVELS))}"
        )

    db = get_db_client()

    product = db.product.find_unique(where={"id": product_id})
    if not product:
        return not_found("Product not found")

    user = db.user.find_unique(where={"id": user_id})
    if not user:
        return not_found("User not found")

    # Check for duplicate
    existing = db.productaccess.find_first(
        where={"userId": user_id, "productId": product_id}
    )
    if existing:
        return conflict("User already has access to this product")

    # Warn if user role bypasses product access (but still allow)
    warning = None
    user_role = getattr(user, "role", None)
    if user_role and user_role in BYPASS_ROLES:
        warning = (
            f"User has role {user_role} which bypasses product access checks. "
            "This entry will have no practical effect."
        )

    pa = db.productaccess.create(
        data={
            "userId": user_id,
            "productId": product_id,
            "level": level,
        },
        include={"user": True},
    )

    result = {
        "id": pa.id,
        "userId": pa.userId,
        "productId": pa.productId,
        "level": pa.level,
        "createdAt": pa.createdAt.isoformat(),
        "updatedAt": pa.updatedAt.isoformat(),
    }
    if hasattr(pa, "user") and pa.user:
        result["userName"] = pa.user.name
        result["userEmail"] = pa.user.email
        result["userRole"] = pa.user.role
    if warning:
        result["warning"] = warning

    log_audit(
        "product.access.grant", "ProductAccess", pa.id,
        {"productId": product_id, "userId": user_id, "level": level},
    )

    return jsonify(ApiResponse.created(result).to_dict()), 201


@require_permissions(Permissions.PRODUCTS_MANAGE)
def update_product_access(product_id: str, access_id: str):
    """Update the access level for an existing product access entry.

    Body: { "level": "view|operate|develop|admin" }
    """
    body = request.get_json()
    if not body:
        return bad_request("Request body must contain JSON data")

    level = (body.get("level") or "").strip().lower()
    if not level:
        return bad_request("level is required")
    if level not in VALID_ACCESS_LEVELS:
        return bad_request(
            f"Invalid access level. Must be one of: {', '.join(sorted(VALID_ACCESS_LEVELS))}"
        )

    db = get_db_client()

    product = db.product.find_unique(where={"id": product_id})
    if not product:
        return not_found("Product not found")

    access_entry = db.productaccess.find_unique(where={"id": access_id})
    if not access_entry:
        return not_found("Access entry not found")

    if access_entry.productId != product_id:
        return not_found("Access entry not found for this product")

    old_level = access_entry.level
    updated = db.productaccess.update(
        where={"id": access_id},
        data={"level": level},
        include={"user": True},
    )

    result = {
        "id": updated.id,
        "userId": updated.userId,
        "productId": updated.productId,
        "level": updated.level,
        "createdAt": updated.createdAt.isoformat(),
        "updatedAt": updated.updatedAt.isoformat(),
    }
    if hasattr(updated, "user") and updated.user:
        result["userName"] = updated.user.name
        result["userEmail"] = updated.user.email
        result["userRole"] = updated.user.role

    log_audit(
        "product.access.update", "ProductAccess", access_id,
        {"productId": product_id, "before": old_level, "after": level},
    )

    return jsonify(ApiResponse.ok(result).to_dict()), 200


@require_permissions(Permissions.PRODUCTS_MANAGE)
def revoke_product_access(product_id: str, access_id: str):
    """Revoke a user's access to this product."""
    db = get_db_client()

    product = db.product.find_unique(where={"id": product_id})
    if not product:
        return not_found("Product not found")

    access_entry = db.productaccess.find_unique(
        where={"id": access_id},
        include={"user": True},
    )
    if not access_entry:
        return not_found("Access entry not found")

    if access_entry.productId != product_id:
        return not_found("Access entry not found for this product")

    details = {
        "productId": product_id,
        "userId": access_entry.userId,
        "level": access_entry.level,
    }
    if hasattr(access_entry, "user") and access_entry.user:
        details["userEmail"] = access_entry.user.email

    db.productaccess.delete(where={"id": access_id})

    log_audit("product.access.revoke", "ProductAccess", access_id, details)

    return jsonify(ApiResponse.deleted().to_dict()), 200
