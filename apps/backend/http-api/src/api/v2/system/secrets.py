"""Secrets management — CRUD for platform secrets (signing keys, credentials).

Secret values are never returned in API responses — only id, name, type, description.
"""

import logging
from flask import jsonify, request

from src.lib.audit import log_audit
from src.lib.decorators import require_permissions
from src.lib.errors import bad_request, conflict, internal_error, not_found
from src.lib.permissions import Permissions
from src.lib.types import ApiResponse
from src.services.database.prisma import get_db_client

logger = logging.getLogger(__name__)

# Never expose secret values in API responses
_SAFE_SELECT = {
    "id": True,
    "name": True,
    "type": True,
    "description": True,
    "createdAt": True,
    "updatedAt": True,
}


def _serialize(s) -> dict:
    return {
        "id": s.id,
        "name": s.name,
        "type": s.type,
        "description": getattr(s, "description", None),
        "createdAt": s.createdAt.isoformat() if hasattr(s.createdAt, 'isoformat') else s.createdAt,
        "updatedAt": s.updatedAt.isoformat() if hasattr(s.updatedAt, 'isoformat') else s.updatedAt,
    }


@require_permissions(Permissions.SYSTEM_VIEW)
def list_secrets():
    """GET /v2/system/secrets"""
    db = get_db_client()
    secrets = db.secret.find_many(order={"name": "asc"})
    return jsonify(ApiResponse.ok([_serialize(s) for s in secrets]).to_dict()), 200


@require_permissions(Permissions.SYSTEM_MANAGE)
def create_secret():
    """POST /v2/system/secrets"""
    db = get_db_client()
    data = request.get_json()
    if not data:
        return bad_request("Request body required")

    name = (data.get("name") or "").strip()
    if not name:
        return bad_request("name is required")

    secret_type = (data.get("type") or "").strip()
    if secret_type not in ("signing_key", "ssh_key", "api_token"):
        return bad_request("type must be signing_key, ssh_key, or api_token")

    value = (data.get("value") or "").strip()
    if not value:
        return bad_request("value is required")

    description = (data.get("description") or "").strip() or None

    existing = db.secret.find_first(where={"name": name})
    if existing:
        return conflict(f"Secret '{name}' already exists")

    from flask import g
    user_id = getattr(g, "current_user", {}).get("sub")

    secret = db.secret.create(data={
        "name": name,
        "type": secret_type,
        "value": value,
        "description": description,
        "createdById": user_id,
    })

    log_audit("secret.create", "Secret", secret.id, {"name": name, "type": secret_type})
    return jsonify(ApiResponse.ok(_serialize(secret)).to_dict()), 201


@require_permissions(Permissions.SYSTEM_MANAGE)
def delete_secret(secret_id: str):
    """DELETE /v2/system/secrets/<id>"""
    db = get_db_client()
    secret = db.secret.find_unique(where={"id": secret_id})
    if not secret:
        return not_found("Secret not found")

    # Check if any stage configs reference this secret
    refs = db.productstageconfig.count(where={"signingKeyId": secret_id})
    if refs > 0:
        return bad_request(f"Cannot delete — {refs} stage config(s) reference this secret")

    db.secret.delete(where={"id": secret_id})
    log_audit("secret.delete", "Secret", secret_id, {"name": secret.name})
    return jsonify(ApiResponse.ok({"deleted": True}).to_dict()), 200
