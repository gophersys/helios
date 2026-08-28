from typing import Any

from flask import g

from config.env import env_config
from src.services.storage.client import presigned_get_url

ALLOWED_FIRMWARE_EXTENSIONS = {"zip", "hex", "ckbin", "bin"}

# Roles that bypass per-product access checks. Only system administrators
# see every product implicitly; Maintainers, Developers, and Operators must
# be granted access through a ProductAccess entry. Newly created products
# therefore start invisible to everyone except admins until access is
# explicitly granted via /v2/products/<id>/access.
PRODUCT_ACCESS_BYPASS_ROLES = ("ADMIN",)


def user_bypasses_product_access() -> bool:
    """Return True when the current request should skip ProductAccess checks.

    Bypass applies in two cases:
      * AUTH_ENABLED is false (dev/test bypass — whole auth layer is off).
      * The caller's effective role is in PRODUCT_ACCESS_BYPASS_ROLES.

    The effective role is set by ``require_permissions`` /
    ``_resolve_effective_role`` so the X-View-As-Role header is honoured.
    """
    if not env_config.AUTH_ENABLED:
        return True
    user = getattr(g, "current_user", None)
    if not user:
        return False
    effective_role = getattr(g, "effective_role", user.get("role", "DEVELOPER"))
    return effective_role in PRODUCT_ACCESS_BYPASS_ROLES


def user_has_product_access(db: Any, product_id: str) -> bool:
    """Return True when the current user has any ProductAccess entry for this product."""
    if user_bypasses_product_access():
        return True
    user = getattr(g, "current_user", None)
    if not user:
        return False
    entry = db.productaccess.find_first(
        where={"userId": user["sub"], "productId": product_id},
    )
    return entry is not None


def serialize_target(t: Any) -> dict:
    """Serialize a ProductTarget for API responses."""
    return {
        "id": t.id,
        "role": t.role,
        "soc": t.soc,
        "appId": t.appId,
    }

MIME_TYPES = {
    "zip": "application/zip",
    "hex": "application/octet-stream",
    "ckbin": "application/octet-stream",
    "bin": "application/octet-stream",
}


def presigned_url(key: str | None, download_filename: str | None = None) -> str | None:
    """Generate a presigned download URL for a storage object."""
    return presigned_get_url(key, download_filename=download_filename)
