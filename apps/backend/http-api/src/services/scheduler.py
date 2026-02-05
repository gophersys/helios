"""Background scheduler for periodic tasks."""

import logging
import threading
from datetime import datetime, timedelta, timezone

from src.services.database.prisma import get_db_client
from src.services.log.logger import get_logger

logger = logging.getLogger(__name__)


_CLEANUP_INTERVAL_HOURS = 24
_RETENTION_DAYS = 30


def _cleanup_old_audit_logs():
    """Delete audit log entries older than the retention period."""
    try:
        logger = get_logger()
        db = get_db_client()
        cutoff = datetime.now(timezone.utc) - timedelta(days=_RETENTION_DAYS)

        result = db.auditlog.delete_many(
            where={"createdAt": {"lt": cutoff}}
        )

        if result > 0:
            logger.info(f"Audit log cleanup: deleted {result} entries older than {_RETENTION_DAYS} days")
    except Exception as e:
        logger.error("Audit log cleanup failed: %s", e)


def _scheduler_loop():
    """Run cleanup periodically."""
    import time

    while True:
        time.sleep(_CLEANUP_INTERVAL_HOURS * 3600)
        _cleanup_old_audit_logs()


def start_scheduler():
    """Start the background scheduler thread.

    Runs an initial cleanup, then repeats every 24 hours.
    """
    # Run cleanup immediately on startup
    _cleanup_old_audit_logs()

    # Start background thread for periodic cleanup
    thread = threading.Thread(target=_scheduler_loop, daemon=True, name="audit-cleanup")
    thread.start()
