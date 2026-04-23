"""Background scheduler for periodic tasks."""

import logging
import threading
from datetime import datetime, timedelta, timezone

from src.services.database.prisma import get_db_client
from src.services.log.logger import get_logger

logger = logging.getLogger(__name__)

_CLEANUP_INTERVAL_HOURS = 24
_RETENTION_DAYS = 30
_BUILD_RECOVERY_INTERVAL_SECONDS = 60


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


def _recover_stale_builds():
    """Find and reset builds stuck in BUILDING/CLONING (worker died)."""
    try:
        from src.services.builds.recovery import recover_stale_builds
        recover_stale_builds()
    except Exception as e:
        logger.error("Build recovery failed: %s", e)


def _audit_cleanup_loop():
    """Run audit cleanup periodically."""
    import time
    while True:
        time.sleep(_CLEANUP_INTERVAL_HOURS * 3600)
        _cleanup_old_audit_logs()


def _build_recovery_loop():
    """Check for stale builds every 60 seconds."""
    import time
    # Wait 30s after startup before first check (let builds claim)
    time.sleep(30)
    while True:
        _recover_stale_builds()
        time.sleep(_BUILD_RECOVERY_INTERVAL_SECONDS)


def start_scheduler():
    """Start background scheduler threads."""
    # Audit log cleanup
    _cleanup_old_audit_logs()
    t1 = threading.Thread(target=_audit_cleanup_loop, daemon=True, name="audit-cleanup")
    t1.start()

    # Build recovery (stale build detection)
    t2 = threading.Thread(target=_build_recovery_loop, daemon=True, name="build-recovery")
    t2.start()
    logger.info("Build recovery scheduler started (interval=%ds)", _BUILD_RECOVERY_INTERVAL_SECONDS)

    # Bitbucket poller — polls repos for new commits to trigger stage builds
    from config.env import env_config
    if env_config.BITBUCKET_POLLER_ENABLED:
        def _poller_loop():
            """Background loop that polls Bitbucket for new commits."""
            import time
            interval = env_config.BITBUCKET_POLLER_INTERVAL_S
            time.sleep(30)  # Initial delay to let services start
            while True:
                try:
                    from src.services.integrations.webhook_trigger import poll_for_changes
                    results = poll_for_changes()
                    if results:
                        logger.info("Bitbucket poller triggered %d stage build(s)", len(results))
                except Exception as e:
                    logger.warning("Bitbucket poller error: %s", e)
                time.sleep(interval)

        t3 = threading.Thread(target=_poller_loop, daemon=True, name="git-poller")
        t3.start()
        logger.info("Bitbucket poller started (interval=%ds)", env_config.BITBUCKET_POLLER_INTERVAL_S)
    else:
        logger.info("Bitbucket poller disabled (BITBUCKET_POLLER_ENABLED=false)")

    # Queue scheduler (build + validation dispatch, stuck job reconciliation)
    from src.services.scheduling.queue_scheduler import start_queue_scheduler
    start_queue_scheduler()
