"""Notification creation helpers.

Thin wrappers around Prisma to create Notification rows. Used by release
management and error report status change handlers.
"""

import logging

from src.services.database.prisma import get_db_client

logger = logging.getLogger(__name__)


def notify_user(
    user_id: str,
    notification_type: str,
    title: str,
    message: str,
    release_id: str | None = None,
    error_report_id: str | None = None,
) -> None:
    """Create a notification for a specific user."""
    try:
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
        db.notification.create(data=data)
    except Exception as e:
        logger.warning("Failed to create notification for user %s: %s", user_id, e)


def notify_all(
    notification_type: str,
    title: str,
    message: str,
    release_id: str | None = None,
) -> int:
    """Create broadcast notification for all active users.

    Returns:
        Number of notifications created.
    """
    try:
        db = get_db_client()
        users = db.user.find_many(where={"active": True})
        if not users:
            return 0

        records = []
        for user in users:
            entry: dict = {
                "type": notification_type,
                "title": title,
                "message": message,
                "userId": user.id,
            }
            if release_id:
                entry["releaseId"] = release_id
            records.append(entry)

        result = db.notification.create_many(data=records)
        count = getattr(result, "count", len(records))
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
