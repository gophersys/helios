"""User-facing notifications — list, mark read, unread count, broadcast, preferences.

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
from src.services.notifications.notifier import notify_all
from src.services.notifications.types import get_types_by_group, NOTIFICATION_TYPES

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

    count = notify_all(
        notification_type="SYSTEM_ANNOUNCEMENT",
        title=title,
        message=message,
        release_id=release_id,
    )

    log_audit("notification.broadcast", "Notification", None, {
        "title": title,
        "recipientCount": count,
    })

    return jsonify(ApiResponse.ok({"sent": count}).to_dict()), 201


# ── Notification types registry ─────────────────────────────────

@require_auth
def list_notification_types():
    """GET /v2/notifications/types — return all notification types grouped."""
    return jsonify(ApiResponse.ok(get_types_by_group()).to_dict()), 200


# ── User notification preferences ───────────────────────────────

@require_auth
def get_notification_preferences():
    """GET /v2/notifications/preferences — get current user's notification preferences."""
    user_id = getattr(g, "current_user", {}).get("sub")
    if not user_id:
        return bad_request("User identity not available")

    db = get_db_client()
    prefs = db.notificationpreference.find_many(where={"userId": user_id})

    disabled_types = {p.type for p in prefs if not p.enabled}

    result = {}
    for type_key in NOTIFICATION_TYPES:
        result[type_key] = type_key not in disabled_types

    return jsonify(ApiResponse.ok(result).to_dict()), 200


@require_auth
def update_notification_preferences():
    """PUT /v2/notifications/preferences — bulk update notification preferences.

    Body: { "PLATFORM_RELEASE_PUBLISHED": true, "BUILD_FAILED": false, ... }
    Only keys present in the body are updated.
    """
    user_id = getattr(g, "current_user", {}).get("sub")
    if not user_id:
        return bad_request("User identity not available")

    data = request.get_json()
    if not data or not isinstance(data, dict):
        return bad_request("Request body must be a JSON object of type → enabled pairs")

    db = get_db_client()
    updated = 0

    for type_key, enabled in data.items():
        if type_key not in NOTIFICATION_TYPES:
            continue
        if not isinstance(enabled, bool):
            continue

        db.notificationpreference.upsert(
            where={"userId_type": {"userId": user_id, "type": type_key}},
            create={
                "userId": user_id,
                "type": type_key,
                "enabled": enabled,
            },
            update={"enabled": enabled},
        )
        updated += 1

    return jsonify(ApiResponse.ok({"updated": updated}).to_dict()), 200
