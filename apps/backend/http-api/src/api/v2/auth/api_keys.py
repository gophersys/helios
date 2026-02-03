import hashlib
import secrets
from datetime import datetime, timezone

from dateutil import parser as dateutil_parser
from flask import g, jsonify, request

from src.lib.decorators import require_auth, require_permissions
from src.lib.permissions import Permissions
from src.services.database.prisma import get_db_client

from .types import ApiKeyCreateRequest

KEY_PREFIX_FORMAT = "ck_live_"
KEY_RANDOM_LENGTH = 32


@require_auth
def list_api_keys():
    """List API keys. Users see their own; admins with ApiKeys.View see all."""
    db = get_db_client()
    user = g.current_user

    # Check if user has admin view permission
    perm_set_id = user.get("permissionSetId")
    is_admin = False
    if perm_set_id:
        perm_set = db.permissionset.find_unique(where={"id": perm_set_id})
        if perm_set and Permissions.ADMIN_API_KEYS_VIEW in perm_set.permissions:
            is_admin = True

    if is_admin:
        keys = db.apikey.find_many(
            order={"createdAt": "desc"},
            include={"user": True},
        )
    else:
        keys = db.apikey.find_many(
            where={"userId": user["sub"]},
            order={"createdAt": "desc"},
        )

    return jsonify(
        {
            "data": [
                {
                    "id": k.id,
                    "name": k.name,
                    "keyPrefix": k.keyPrefix,
                    "userId": k.userId,
                    "userName": k.user.name if hasattr(k, "user") and k.user else None,
                    "expiresAt": k.expiresAt.isoformat() if k.expiresAt else None,
                    "lastUsedAt": k.lastUsedAt.isoformat() if k.lastUsedAt else None,
                    "createdAt": k.createdAt.isoformat(),
                }
                for k in keys
            ]
        }
    ), 200


@require_auth
def create_api_key():
    """Create a new API key for the authenticated user.

    Body: { "name": "...", "expiresAt?": "ISO date" }
    Returns the full key ONCE in the response.
    """
    data, error = ApiKeyCreateRequest.from_json(request.get_json())
    if error:
        return jsonify({"error": error}), 400

    # Generate the key
    random_part = secrets.token_hex(KEY_RANDOM_LENGTH)
    raw_key = f"{KEY_PREFIX_FORMAT}{random_part}"
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    key_prefix = raw_key[:16]

    # Parse expiresAt if provided
    expires_at = None
    if data.expiresAt:
        try:
            expires_at = dateutil_parser.parse(data.expiresAt)
        except (ValueError, TypeError):
            return jsonify({"error": "Invalid expiresAt date format"}), 400

    db = get_db_client()
    create_data = {
        "name": data.name,
        "keyHash": key_hash,
        "keyPrefix": key_prefix,
        "userId": g.current_user["sub"],
    }
    if expires_at:
        create_data["expiresAt"] = expires_at

    api_key = db.apikey.create(data=create_data)

    return jsonify(
        {
            "data": {
                "key": raw_key,
                "id": api_key.id,
                "name": api_key.name,
                "keyPrefix": key_prefix,
                "expiresAt": api_key.expiresAt.isoformat() if api_key.expiresAt else None,
                "createdAt": api_key.createdAt.isoformat(),
            }
        }
    ), 201


@require_auth
def delete_api_key(key_id: str):
    """Delete an API key. Owner can delete their own; admin can delete any."""
    db = get_db_client()

    api_key = db.apikey.find_unique(where={"id": key_id})
    if not api_key:
        return jsonify({"error": "API key not found"}), 404

    user = g.current_user
    is_owner = api_key.userId == user["sub"]

    if not is_owner:
        # Check if user has admin manage permission
        perm_set_id = user.get("permissionSetId")
        is_admin = False
        if perm_set_id:
            perm_set = db.permissionset.find_unique(where={"id": perm_set_id})
            if perm_set and Permissions.ADMIN_API_KEYS_MANAGE in perm_set.permissions:
                is_admin = True

        if not is_admin:
            return jsonify({"error": "Forbidden"}), 403

    db.apikey.delete(where={"id": key_id})
    return jsonify({"message": "API key deleted"}), 200
