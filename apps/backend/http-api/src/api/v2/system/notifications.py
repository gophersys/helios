"""User-facing notifications — list, mark read, unread count, broadcast.

User endpoints filter by g.current_user['sub'].
Broadcast restricted to notifications:manage.
"""

import logging
from datetime import datetime, timezone

from flask import g, jsonify, request

from src.lib.audit import log_audit
from src.lib.decorators import require_auth, require_permissions
from src.lib.errors import bad_request, not_found
from src.lib.permissions import Permissions
from src.lib.types import ApiResponse
from src.services.database.prisma import get_db_client

logger = logging.getLogger(__name__)


def _serialize(n) -> dict:
    return {
        "id": n.id,
        "type": n.type,
        "title": n.title,
        "message": n.message,
        "userId": getattr(n, "userId", None),
        "releaseId": getattr(n, "releaseId", None),
        "errorReportId": getattr(n, "errorReportId", None),
        "readAt": n.readAt.isoformat() if hasattr(n, "readAt") and n.readAt else None,
        "createdAt": n.createdAt.isoformat() if hasattr(n, "createdAt") else None,
    }


@require_auth
def list_notifications():
    """GET /v2/notifications — list current user's notifications."""
    user_id = getattr(g, "current_user", {}).get("sub")
    if not user_id:
        return bad_request("User identity not available")

    page = max(1, request.args.get("page", 1, type=int))
    limit = min(max(1, request.args.get("limit", 50, type=int)), 100)
    skip = (page - 1) * limit

    where = {"userId": user_id}

    db = get_db_client()
    total = db.notification.count(where=where)
    notifications = db.notification.find_many(
        where=where,
        order={"createdAt": "desc"},
        skip=skip,
        take=limit,
    )

    pages = (total + limit - 1) // limit if total > 0 else 0
    return jsonify(ApiResponse.ok({
        "data": [_serialize(n) for n in notifications],
        "pagination": {"page": page, "limit": limit, "total": total, "pages": pages},
    }).to_dict()), 200


@require_auth
def unread_count():
    """GET /v2/notifications/unread-count — count of unread notifications."""
    user_id = getattr(g, "current_user", {}).get("sub")
    if not user_id:
        return bad_request("User identity not available")

    db = get_db_client()
    count = db.notification.count(where={
        "userId": user_id,
        "readAt": None,
    })

    return jsonify(ApiResponse.ok({"count": count}).to_dict()), 200


@require_auth
def mark_read(notification_id: str):
    """PATCH /v2/notifications/<id>/read — mark a single notification as read."""
    user_id = getattr(g, "current_user", {}).get("sub")

    db = get_db_client()
    notification = db.notification.find_unique(where={"id": notification_id})
    if not notification or notification.userId != user_id:
        return not_found("Notification not found")

    updated = db.notification.update(
        where={"id": notification_id},
        data={"readAt": datetime.now(timezone.utc)},
    )
    return jsonify(ApiResponse.ok(_serialize(updated)).to_dict()), 200


@require_auth
def mark_all_read():
    """POST /v2/notifications/read-all — mark all as read for current user."""
    user_id = getattr(g, "current_user", {}).get("sub")
    if not user_id:
        return bad_request("User identity not available")

    db = get_db_client()
    result = db.notification.update_many(
        where={"userId": user_id, "readAt": None},
        data={"readAt": datetime.now(timezone.utc)},
    )

    count = getattr(result, "count", 0)
    return jsonify(ApiResponse.ok({"updated": count}).to_dict()), 200


@require_permissions(Permissions.NOTIFICATIONS_MANAGE)
def broadcast_notification():
    """POST /v2/notifications/broadcast — create broadcast notification."""
    data = request.get_json()
    if not data:
        return bad_request("Request body required")

    title = (data.get("title") or "").strip()
    if not title:
        return bad_request("title is required")

    message = (data.get("message") or "").strip()
    if not message:
        return bad_request("message is required")

    release_id = data.get("releaseId")

    db = get_db_client()
    users = db.user.find_many(where={"active": True})
    if not users:
        return jsonify(ApiResponse.ok({"sent": 0}).to_dict()), 201

    records = []
    for user in users:
        entry: dict = {
            "type": "SYSTEM_ANNOUNCEMENT",
            "title": title,
            "message": message,
            "userId": user.id,
        }
        if release_id:
            entry["releaseId"] = release_id
        records.append(entry)

    result = db.notification.create_many(data=records)
    count = getattr(result, "count", len(records))

    log_audit("notification.broadcast", "Notification", None, {
        "title": title,
        "recipientCount": count,
    })

    return jsonify(ApiResponse.ok({"sent": count}).to_dict()), 201
