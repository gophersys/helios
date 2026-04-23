import logging
from datetime import datetime, timezone

from flask import jsonify, request

from config.env import env_config
from src.lib.audit import log_audit
from src.lib.errors import bad_request, forbidden, unauthorized
from src.lib.permissions import Permissions
from src.lib.types import ApiResponse
from src.services.auth.corecloud import authenticate_corecloud
from src.services.auth.jwt import create_token
from src.services.database.prisma import get_db_client

from .types import LoginRequest

logger = logging.getLogger(__name__)


def login():
    """Exchange credentials for a Concord JWT.

    Body: { "email": "...", "password": "..." }
    Returns: { "data": { "token": "<jwt>", "user": { ... } }, "errors": [] }

    In development: admin@concord.local / admin bypasses CoreCloud auth.
    """
    data, error = LoginRequest.from_json(request.get_json())
    if error:
        return bad_request(error)

    # Development-only: admin/admin bypass (never in staging/production)
    is_dev_admin = (
        env_config.ENVIRONMENT == "development"
        and data.email in ("admin@concord.local", "admin")
        and data.password == "admin"
    )

    if is_dev_admin:
        cc_user = {"email": "admin@concord.local"}
        logger.info("Dev admin login bypass (development only)")
    else:
        # Verify credentials against CoreKinect auth server
        cc_user, error = authenticate_corecloud(data.email, data.password)
        if error:
            return unauthorized(error)

    # Look up the user by email — must be pre-registered
    db = get_db_client()
    user = db.user.find_unique(
        where={"email": cc_user["email"]},
        include={"permissionSet": True},
    )

    if not user and is_dev_admin:
        # Auto-create dev admin with all permissions on first login
        all_perms = [v for k, v in vars(Permissions).items() if not k.startswith("_") and isinstance(v, str)]
        perm_set = db.permissionset.upsert(
            where={"name": "Super Admin"},
            data={
                "create": {"name": "Super Admin", "permissions": all_perms},
                "update": {"permissions": all_perms},
            },
        )
        user = db.user.create(
            data={
                "email": "admin@concord.local",
                "name": "Dev Admin",
                "role": "ADMIN",
                "active": True,
                "permissionSetId": perm_set.id,
            },
            include={"permissionSet": True},
        )
        logger.info("Auto-created dev admin user (id: %s)", user.id)
    elif not user:
        return forbidden("Account not registered. Contact an administrator.")

    if not user.active:
        return forbidden("Account deactivated. Contact an administrator.")

    # Update last seen
    db.user.update(
        where={"id": user.id},
        data={"lastSeenAt": datetime.now(timezone.utc)},
    )

    # Issue a Concord JWT
    user_role = getattr(user, "role", "DEVELOPER") or "DEVELOPER"
    token = create_token(user.id, user.email, user.name, user.permissionSetId, role=user_role)

    log_audit("login", "User", user.id, {"email": user.email, "name": user.name})

    return jsonify(ApiResponse.ok(
        {
            "token": token,
            "user": {
                "id": user.id,
                "email": user.email,
                "name": user.name,
                "role": user_role,
                "permissionSetId": user.permissionSetId,
                "permissionSetName": user.permissionSet.name if user.permissionSet else None,
            },
        }
    ).to_dict()), 200
