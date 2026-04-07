import logging
from datetime import datetime
from typing import Any

from flask import jsonify, request

from src.lib.decorators import require_permissions
from src.lib.errors import bad_request, not_found
from src.lib.permissions import Permissions
from src.lib.types import ApiResponse
from src.services.database.prisma import get_db_client

logger = logging.getLogger(__name__)


def _serialize_audit_log(entry: Any) -> dict:
    """Serialize an AuditLog DB record to an API response dict."""
    data = {
        "id": entry.id,
        "userId": entry.userId,
        "action": entry.action,
        "entityType": entry.entityType,
        "entityId": entry.entityId,
        "details": entry.details,
        "ipAddress": entry.ipAddress,
        "createdAt": entry.createdAt.isoformat(),
    }
    if hasattr(entry, "user") and entry.user is not None:
        data["user"] = {
            "id": entry.user.id,
            "name": entry.user.name,
            "email": entry.user.email,
        }
    else:
        data["user"] = None
    return data


@require_permissions(Permissions.SYSTEM_VIEW)
def list_history():
    """List audit log entries with filtering and pagination."""
    db = get_db_client()

    # Pagination
    page = max(1, request.args.get("page", 1, type=int))
    limit = min(max(1, request.args.get("limit", 50, type=int)), 100)
    skip = (page - 1) * limit

    # Build where clause
    where = {}

    user_id = request.args.get("userId")
    if user_id:
        where["userId"] = user_id

    entity_type = request.args.get("entityType")
    if entity_type:
        where["entityType"] = entity_type

    action = request.args.get("action")
    if action:
        where["action"] = {"contains": action}

    date_from = request.args.get("from")
    date_to = request.args.get("to")
    if date_from or date_to:
        where["createdAt"] = {}
        if date_from:
            try:
                where["createdAt"]["gte"] = datetime.fromisoformat(date_from)
            except ValueError:
                return bad_request("Invalid date format for 'from'. Use ISO 8601 format.")
        if date_to:
            try:
                where["createdAt"]["lte"] = datetime.fromisoformat(date_to)
            except ValueError:
                return bad_request("Invalid date format for 'to'. Use ISO 8601 format.")

    # Query
    total = db.auditlog.count(where=where)
    entries = db.auditlog.find_many(
        where=where,
        order={"createdAt": "desc"},
        skip=skip,
        take=limit,
        include={"user": True},
    )

    return jsonify(ApiResponse.ok({
        "data": [_serialize_audit_log(e) for e in entries],
        "pagination": {
            "page": page,
            "limit": limit,
            "total": total,
            "pages": (total + limit - 1) // limit if limit > 0 else 0,
        },
    }).to_dict()), 200


@require_permissions(Permissions.SYSTEM_VIEW)
def get_history_entry(entry_id: str):
    """Get a single audit log entry by ID."""
    db = get_db_client()
    entry = db.auditlog.find_unique(
        where={"id": entry_id},
        include={"user": True},
    )
    if not entry:
        return not_found("Audit log entry not found")

    return jsonify(ApiResponse.ok(_serialize_audit_log(entry)).to_dict()), 200
