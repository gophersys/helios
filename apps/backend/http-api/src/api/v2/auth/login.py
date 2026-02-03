from datetime import datetime, timezone

from flask import jsonify, request

from src.services.auth.google import verify_google_token
from src.services.auth.jwt import create_token
from src.services.database.prisma import get_db_client

from .types import LoginRequest


def login():
    """Exchange a Google ID token for a Concord JWT.

    Body: { "credential": "<google_id_token>" }
    Returns: { "token": "<jwt>", "user": { ... } }
    """
    data, error = LoginRequest.from_json(request.get_json())
    if error:
        return jsonify({"error": error}), 400

    # Verify the Google ID token
    google_user, error = verify_google_token(data.credential)
    if error:
        return jsonify({"error": error}), 401

    # Look up the user by email
    db = get_db_client()
    user = db.user.find_unique(
        where={"email": google_user["email"]},
        include={"permissionSet": True},
    )

    if not user:
        return jsonify({"error": "Account not registered. Contact an administrator."}), 403

    if not user.active:
        return jsonify({"error": "Account deactivated. Contact an administrator."}), 403

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

    return jsonify(
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
    ), 200
