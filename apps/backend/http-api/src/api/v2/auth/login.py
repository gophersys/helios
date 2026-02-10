import logging
from datetime import datetime, timezone

from flask import jsonify, request

from src.lib.audit import log_audit
from src.lib.errors import bad_request, forbidden, unauthorized
from src.lib.permissions import Permissions
from src.lib.types import ApiResponse
from src.services.auth.corecloud import authenticate_corecloud
from src.services.auth.google import verify_google_token
from src.services.auth.jwt import create_token
from src.services.database.prisma import get_db_client

from .types import CoreCloudLoginRequest, LoginRequest

logger = logging.getLogger(__name__)


def login():
    """Exchange a Google ID token for a Concord JWT.

    Body: { "credential": "<google_id_token>" }
    Returns: { "data": { "token": "<jwt>", "user": { ... } }, "errors": [] }
    """
    data, error = LoginRequest.from_json(request.get_json())
    if error:
        return bad_request(error)

    # Verify the Google ID token
    google_user, error = verify_google_token(data.credential)
    if error:
        return unauthorized(error)

    # Look up the user by email
    db = get_db_client()
    user = db.user.find_unique(
        where={"email": google_user["email"]},
        include={"permissionSet": True},
    )

    if not user:
        return forbidden("Account not registered. Contact an administrator.")

    if not user.active:
        return forbidden("Account deactivated. Contact an administrator.")

    # Link Google sub and update last seen
    db.user.update(
        where={"id": user.id},
        data={
            "externalId": google_user["sub"],
            "lastSeenAt": datetime.now(timezone.utc),
        },
    )

    # Issue a Concord JWT
    token = create_token(user.id, user.email, user.name, user.permissionSetId)

    log_audit("login", "User", user.id, {"email": user.email, "name": user.name})

    return jsonify(ApiResponse.ok(
        {
            "token": token,
            "user": {
                "id": user.id,
                "email": user.email,
                "name": user.name,
                "permissionSetId": user.permissionSetId,
                "permissionSetName": user.permissionSet.name if user.permissionSet else None,
            },
        }
    ).to_dict()), 200


# ---------------------------------------------------------------------------
# Permission sets for auto-provisioned dev users
# TODO (MONDAY): Remove this once real Core Cloud auth is wired up
# ---------------------------------------------------------------------------
_ROLE_PERMISSIONS = {
    "superadmin": [p["key"] for p in Permissions.all()],
    "admin": [
        Permissions.ADMIN_USERS_VIEW,
        Permissions.ADMIN_USERS_MANAGE,
        Permissions.ADMIN_PERMISSION_SETS_VIEW,
        Permissions.ADMIN_PERMISSION_SETS_MANAGE,
        Permissions.ADMIN_API_KEYS_VIEW,
        Permissions.ADMIN_API_KEYS_MANAGE,
        Permissions.ADMIN_INVENTORY_VIEW,
        Permissions.ADMIN_INVENTORY_MANAGE,
        Permissions.ADMIN_CODEBASES_VIEW,
        Permissions.ADMIN_CODEBASES_MANAGE,
        Permissions.ADMIN_CATALOG_VIEW,
        Permissions.ADMIN_CATALOG_MANAGE,
        Permissions.ADMIN_HISTORY_VIEW,
        Permissions.ADMIN_SYSTEM_VIEW,
        Permissions.ADMIN_SYSTEM_MANAGE,
        Permissions.ADMIN_NODES_VIEW,
        Permissions.ADMIN_NODES_MANAGE,
        Permissions.ADMIN_FIXTURES_VIEW,
        Permissions.ADMIN_FIXTURES_MANAGE,
        Permissions.ADMIN_DEPLOYMENTS_VIEW,
        Permissions.ADMIN_DEPLOYMENTS_MANAGE,
        Permissions.MTIB_READ,
        Permissions.MTIB_MANAGE,
        Permissions.VALIDATION_TESTS_RUN,
    ],
    "operator": [
        Permissions.ADMIN_INVENTORY_VIEW,
        Permissions.ADMIN_CODEBASES_VIEW,
        Permissions.ADMIN_CATALOG_VIEW,
        Permissions.ADMIN_HISTORY_VIEW,
        Permissions.ADMIN_NODES_VIEW,
        Permissions.ADMIN_FIXTURES_VIEW,
        Permissions.ADMIN_DEPLOYMENTS_VIEW,
        Permissions.ADMIN_DEPLOYMENTS_MANAGE,
        Permissions.MTIB_READ,
        Permissions.MTIB_MANAGE,
        Permissions.VALIDATION_TESTS_RUN,
    ],
}

_ROLE_NAMES = {
    "superadmin": "Super Admin",
    "admin": "Admin",
    "operator": "Operator",
}


def _ensure_permission_set(db, role: str):
    """Get or create a permission set for the given role. TODO: REMOVE ON MONDAY."""
    name = _ROLE_NAMES.get(role, "User")
    expected_perms = _ROLE_PERMISSIONS.get(role, [])
    perm_set = db.permissionset.find_first(where={"name": name})
    if perm_set:
        # Sync permissions if they've changed (e.g. new modules added)
        if set(perm_set.permissions or []) != set(expected_perms):
            perm_set = db.permissionset.update(
                where={"id": perm_set.id},
                data={"permissions": expected_perms},
            )
        return perm_set
    return db.permissionset.create(
        data={
            "name": name,
            "description": f"Auto-provisioned {name} permission set",
            "permissions": expected_perms,
        }
    )


def _ensure_user(db, email: str, name: str, role: str):
    """Get or create a user with the given email. TODO: REMOVE ON MONDAY."""
    user = db.user.find_unique(
        where={"email": email},
        include={"permissionSet": True},
    )
    if user:
        # Sync permission set on every login (picks up new permissions)
        _ensure_permission_set(db, role)
        return user

    perm_set = _ensure_permission_set(db, role)
    logger.info("Auto-provisioning user %s (%s) with role %s", email, name, role)
    user = db.user.create(
        data={
            "email": email,
            "name": name,
            "permissionSetId": perm_set.id,
            "active": True,
        },
        include={"permissionSet": True},
    )
    return user


def login_corecloud():
    """Exchange Core Cloud email/password credentials for a Concord JWT.

    Body: { "email": "...", "password": "..." }
    Returns: { "data": { "token": "<jwt>", "user": { ... } }, "errors": [] }
    """
    data, error = CoreCloudLoginRequest.from_json(request.get_json())
    if error:
        return bad_request(error)

    # Verify credentials against Core Cloud auth server (or dev users)
    cc_user, error = authenticate_corecloud(data.email, data.password)
    if error:
        return unauthorized(error)

    db = get_db_client()

    # Auto-provision user if they don't exist yet (for dev users)
    # TODO (MONDAY): Remove auto-provisioning, require pre-registered accounts
    role = cc_user.get("role", "user")
    user = _ensure_user(db, cc_user["email"], cc_user.get("name", cc_user["email"]), role)

    if not user.active:
        return forbidden("Account deactivated. Contact an administrator.")

    # Update last seen
    db.user.update(
        where={"id": user.id},
        data={"lastSeenAt": datetime.now(timezone.utc)},
    )

    # Issue a Concord JWT
    token = create_token(user.id, user.email, user.name, user.permissionSetId)

    log_audit("login", "User", user.id, {"email": user.email, "name": user.name, "method": "corecloud"})

    return jsonify(ApiResponse.ok(
        {
            "token": token,
            "user": {
                "id": user.id,
                "email": user.email,
                "name": user.name,
                "permissionSetId": user.permissionSetId,
                "permissionSetName": user.permissionSet.name if user.permissionSet else None,
            },
        }
    ).to_dict()), 200
