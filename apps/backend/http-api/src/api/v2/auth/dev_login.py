"""Development-only auth endpoints.

These ONLY work when AUTH_ENABLED=false. They show a login picker
with one sample user per role — no passwords, no OAuth.
"""

import logging

from flask import jsonify, request

from config import env_config
from src.lib.types import ApiResponse
from src.services.auth.jwt import create_token
from src.services.database.prisma import get_db_client

logger = logging.getLogger(__name__)

# Dev sample user emails — one per role, created by seed.py
DEV_USER_EMAILS = [
    "admin@concord.dev",
    "maintainer@concord.dev",
    "developer@concord.dev",
    "operator@concord.dev",
]


def dev_users():
    """Return dev sample users for the login picker.

    GET /v2/auth/dev-users
    Only available when AUTH_ENABLED=false.
    """
    if env_config.AUTH_ENABLED:
        return jsonify(ApiResponse.error("Not available in this environment").to_dict()), 403

    db = get_db_client()
    users = db.user.find_many(
        where={"email": {"in": DEV_USER_EMAILS}, "active": True},
        include={"permissionSet": True},
    )

    # Sort by role hierarchy
    role_order = {"ADMIN": 0, "MAINTAINER": 1, "DEVELOPER": 2, "OPERATOR": 3}
    users.sort(key=lambda u: role_order.get(getattr(u, "role", "DEVELOPER"), 99))

    data = {
        "environment": env_config.ENVIRONMENT,
        "users": [
            {
                "email": u.email,
                "name": u.name,
                "role": getattr(u, "role", "DEVELOPER") or "DEVELOPER",
                "permissionSet": u.permissionSet.name if u.permissionSet else None,
            }
            for u in users
        ],
    }

    return jsonify(ApiResponse.ok(data).to_dict()), 200


def dev_login():
    """Instantly log in as a dev sample user.

    POST /v2/auth/dev-login
    Body: { "email": "admin@concord.dev" }
    Only available when AUTH_ENABLED=false.
    """
    if env_config.AUTH_ENABLED:
        return jsonify(ApiResponse.error("Dev login disabled in this environment").to_dict()), 403

    body = request.get_json()
    if not body or not body.get("email"):
        return jsonify(ApiResponse.error("Email is required").to_dict()), 400

    email = body["email"].strip().lower()

    db = get_db_client()
    user = db.user.find_unique(
        where={"email": email},
        include={"permissionSet": True},
    )

    if not user:
        return jsonify(ApiResponse.error(f"User '{email}' not found. Run: python3 prisma/seed.py").to_dict()), 404

    if not user.active:
        return jsonify(ApiResponse.error("User account is deactivated").to_dict()), 403

    user_role = getattr(user, "role", "DEVELOPER") or "DEVELOPER"
    token = create_token(user.id, user.email, user.name, user.permissionSetId, role=user_role)

    logger.info("Dev login: %s (%s)", user.email, user_role)

    return jsonify(ApiResponse.ok({
        "token": token,
        "user": {
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "role": user_role,
        },
    }).to_dict()), 200
