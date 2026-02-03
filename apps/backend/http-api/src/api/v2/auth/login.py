from datetime import datetime, timezone

from flask import Blueprint, jsonify, request

from src.services.auth.google import verify_google_token
from src.services.auth.jwt import create_token
from src.services.database.prisma import get_db_client

v2_auth_login_bp = Blueprint("v2_auth_login", __name__)


@v2_auth_login_bp.route("/v2/auth/login", methods=["POST"])
def v2_auth_login():
    """Exchange a Google ID token for a Concord JWT.

    Body: { "credential": "<google_id_token>" }
    Returns: { "token": "<jwt>", "user": { ... } }
    """
    data = request.get_json()
    if not data or not data.get("credential"):
        return jsonify({"error": "Missing credential"}), 400

    # Verify the Google ID token
    google_user, error = verify_google_token(data["credential"])
    if error:
        return jsonify({"error": error}), 401

    # Look up the user by email
    db = get_db_client()
    user = db.user.find_unique(where={"email": google_user["email"]})

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
    token = create_token(user.id, user.email, user.name, user.role)

    return jsonify(
        {
            "token": token,
            "user": {
                "id": user.id,
                "email": user.email,
                "name": user.name,
                "role": user.role,
            },
        }
    ), 200
