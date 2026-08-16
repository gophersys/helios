"""Notification creation helpers.

Thin wrappers around Prisma to create Notification rows and emit them
via WebSocket for real-time delivery. Checks per-user preferences before
creating — users who disabled a type won't get a row or a push.
"""

import logging

from src.services.database.prisma import get_db_client

logger = logging.getLogger(__name__)

_socketio = None


def init_socketio(sio) -> None:
    """Called once at startup to give the notifier access to SocketIO."""
    global _socketio
    _socketio = sio


def _user_has_type_enabled(user_id: str, notification_type: str) -> bool:
    """Check if a user has this notification type enabled (default: yes)."""
    try:
        db = get_db_client()
        pref = db.notificationpreference.find_unique(
            where={"userId_type": {"userId": user_id, "type": notification_type}},
        )
        if pref is None:
            return True
        return pref.enabled
    except Exception:
        return True


def _emit_realtime(user_id: str, notification) -> None:
    """Push a notification to the user's WebSocket room."""
    if _socketio is None:
        return
    try:
        _socketio.emit(
            "notification",
            {
                "id": notification.id,
                "type": notification.type,
                "title": notification.title,
                "message": notification.message,
                "userId": getattr(notification, "userId", None),
                "releaseId": getattr(notification, "releaseId", None),
                "errorReportId": getattr(notification, "errorReportId", None),
                "readAt": None,
                "createdAt": notification.createdAt.isoformat()
                if hasattr(notification, "createdAt")
                else None,
            },
            room=f"user:{user_id}",
            namespace="/notifications",
        )
    except Exception as e:
        logger.debug("Failed to emit notification via WS: %s", e)


def notify_user(
    user_id: str,
    notification_type: str,
    title: str,
    message: str,
    release_id: str | None = None,
    error_report_id: str | None = None,
) -> None:
    """Create a notification for a specific user (if they haven't disabled the type)."""
    try:
        if not _user_has_type_enabled(user_id, notification_type):
            return

        db = get_db_client()
        data: dict = {
            "type": notification_type,
            "title": title,
            "message": message,
            "userId": user_id,
        }
        if release_id:
            data["releaseId"] = release_id
        if error_report_id:
            data["errorReportId"] = error_report_id
        notification = db.notification.create(data=data)
        _emit_realtime(user_id, notification)
    except Exception as e:
        logger.warning("Failed to create notification for user %s: %s", user_id, e)


def notify_all(
    notification_type: str,
    title: str,
    message: str,
    release_id: str | None = None,
) -> int:
    """Create broadcast notification for all active users who have the type enabled."""
    try:
        db = get_db_client()
        users = db.user.find_many(where={"active": True})
        if not users:
            return 0

        count = 0
        for user in users:
            if not _user_has_type_enabled(user.id, notification_type):
                continue
            entry: dict = {
                "type": notification_type,
                "title": title,
                "message": message,
                "userId": user.id,
            }
            if release_id:
                entry["releaseId"] = release_id
            notification = db.notification.create(data=entry)
            _emit_realtime(user.id, notification)
            count += 1
        return count
    except Exception as e:
        logger.warning("Failed to create broadcast notification: %s", e)
        return 0


def notify_bug_status_change(
    error_report_id: str,
    new_status: str,
    admin_notes: str | None = None,
) -> None:
    """Notify the bug reporter when their bug status changes."""
    try:
        db = get_db_client()
        report = db.errorreport.find_unique(where={"id": error_report_id})
        if not report or not report.userId:
            return

        status_messages = {
            "ACKNOWLEDGED": "Your bug report has been acknowledged by the team.",
            "RESOLVED": "Your bug report has been resolved.",
            "DISMISSED": "Your bug report has been reviewed and dismissed.",
        }

        msg = status_messages.get(new_status)
        if not msg:
            return

        if admin_notes:
            msg = f"{msg}\n\nAdmin notes: {admin_notes}"

        type_map = {
            "ACKNOWLEDGED": "BUG_ACKNOWLEDGED",
            "RESOLVED": "BUG_RESOLVED",
            "DISMISSED": "BUG_DISMISSED",
        }

        notify_user(
            user_id=report.userId,
            notification_type=type_map[new_status],
            title=f"Bug report {new_status.lower()}: {report.message[:80]}",
            message=msg,
            error_report_id=error_report_id,
        )
    except Exception as e:
        logger.warning(
            "Failed to notify bug status change for %s: %s",
            error_report_id, e,
        )
