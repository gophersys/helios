"""Development-only auth endpoints.

These endpoints ONLY work when AUTH_ENABLED=false. They allow developers
to instantly log in as any seeded user to test role-based UI without
configuring OAuth or entering passwords.
"""

import logging

from flask import jsonify, request

from config import env_config
from src.lib.types import ApiResponse
from src.services.auth.jwt import create_token
from src.services.database.prisma import get_db_client

logger = logging.getLogger(__name__)


def dev_users():
    """Return all active seeded users for the dev login picker.

    GET /v2/auth/dev-users
    Only available when AUTH_ENABLED=false.
    """
    if env_config.AUTH_ENABLED:
        return jsonify({"data": None, "errors": [{"message": "Not available"}]}), 403

    db = get_db_client()
    users = db.user.find_many(
        where={"active": True},
        include={"permissionSet": True},
        order={"name": "asc"},
    )

    data = []
    for u in users:
        user_role = getattr(u, "role", "DEVELOPER") or "DEVELOPER"
        data.append({
            "email": u.email,
            "name": u.name,
            "role": user_role,
            "permissionSet": u.permissionSet.name if u.permissionSet else None,
        })

    return jsonify(ApiResponse.ok(data).to_dict()), 200


def dev_login():
    """Instantly log in as any seeded user without credentials.

    POST /v2/auth/dev-login
    Body: { "email": "user@example.com" }
    Only available when AUTH_ENABLED=false.
    """
    if env_config.AUTH_ENABLED:
        return jsonify({"data": None, "errors": [{"message": "Dev login disabled in this environment"}]}), 403

    body = request.get_json()
    if not body or not body.get("email"):
        return jsonify({"data": None, "errors": [{"message": "Email is required"}]}), 400

    email = body["email"].strip().lower()

    db = get_db_client()
    user = db.user.find_unique(
        where={"email": email},
        include={"permissionSet": True},
    )

    if not user:
        return jsonify({"data": None, "errors": [{"message": f"User '{email}' not found. Run prisma seed."}]}), 404

    if not user.active:
        return jsonify({"data": None, "errors": [{"message": "User account is deactivated"}]}), 403

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
            "permissionSetId": user.permissionSetId,
            "permissionSetName": user.permissionSet.name if user.permissionSet else None,
        },
    }).to_dict()), 200
