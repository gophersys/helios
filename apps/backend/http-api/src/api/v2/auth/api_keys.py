import hashlib
import secrets
from datetime import datetime

from dateutil import parser as dateutil_parser
from flask import g, jsonify, request

from src.lib.audit import log_audit
from src.lib.decorators import require_permissions
from src.lib.errors import bad_request, forbidden, not_found
from src.lib.permissions import Permissions
from src.lib.types import ApiResponse
from src.services.database.prisma import get_db_client

from .types import ApiKeyCreateRequest

KEY_PREFIX_FORMAT = "ck_live_"
KEY_RANDOM_LENGTH = 32


@require_permissions(Permissions.ADMIN_API_KEYS_VIEW)
def list_api_keys():
    """List all API keys (requires ADMIN_API_KEYS_VIEW permission)."""
    db = get_db_client()

    page = max(1, request.args.get("page", 1, type=int))
    limit = min(max(1, request.args.get("limit", 50, type=int)), 100)
    skip = (page - 1) * limit

    total = db.apikey.count()
    keys = db.apikey.find_many(
        skip=skip,
        take=limit,
        order={"createdAt": "desc"},
        include={"user": True},
    )

    return jsonify(ApiResponse.ok({
        "data": [
            {
                "id": k.id,
                "name": k.name,
                "keyPrefix": k.keyPrefix,
                "userId": k.userId,
                "userName": k.user.name if hasattr(k, "user") and k.user is not None else None,
                "expiresAt": k.expiresAt.isoformat() if k.expiresAt else None,
                "lastUsedAt": k.lastUsedAt.isoformat() if k.lastUsedAt else None,
                "createdAt": k.createdAt.isoformat(),
            }
            for k in keys
        ],
        "pagination": {
            "page": page,
            "limit": limit,
            "total": total,
            "pages": (total + limit - 1) // limit if limit > 0 else 0,
        },
    }).to_dict()), 200


@require_permissions(Permissions.ADMIN_API_KEYS_MANAGE)
def create_api_key():
    """Create a new API key for the authenticated user.

    Body: { "name": "...", "expiresAt?": "ISO date" }
    Returns the full key ONCE in the response.
    """
    data, error = ApiKeyCreateRequest.from_json(request.get_json())
    if error:
        return bad_request(error)

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
            return bad_request("Invalid expiresAt date format")

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

    log_audit("apiKey.create", "ApiKey", api_key.id, {"name": data.name})

    return jsonify(ApiResponse.created({
        "key": raw_key,
        "id": api_key.id,
        "name": api_key.name,
        "keyPrefix": key_prefix,
        "expiresAt": api_key.expiresAt.isoformat() if api_key.expiresAt else None,
        "createdAt": api_key.createdAt.isoformat(),
    }).to_dict()), 201


@require_permissions(Permissions.ADMIN_API_KEYS_MANAGE)
def delete_api_key(key_id: str):
    """Delete an API key (requires ADMIN_API_KEYS_MANAGE permission)."""
    db = get_db_client()

    api_key = db.apikey.find_unique(where={"id": key_id})
    if not api_key:
        return not_found("API key not found")

    db.apikey.delete(where={"id": key_id})
    log_audit("apiKey.delete", "ApiKey", key_id, {"name": api_key.name})
    return jsonify(ApiResponse.deleted().to_dict()), 200
