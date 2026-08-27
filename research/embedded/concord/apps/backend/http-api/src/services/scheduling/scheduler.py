"""Background scheduler for periodic tasks."""

import logging
import threading
import time
from datetime import datetime, timedelta, timezone

from config.env import env_config
from src.services.builds.recovery import recover_stale_builds
from src.services.database.prisma import get_db_client
from src.services.integrations.webhook_trigger import poll_for_changes
from src.services.log.logger import get_logger
from src.services.scheduling.queue_scheduler import start_queue_scheduler

logger = logging.getLogger(__name__)

_CLEANUP_INTERVAL_HOURS = 24
_RETENTION_DAYS = 30
_BUILD_RECOVERY_INTERVAL_SECONDS = 60
_NODE_IP_REFRESH_INTERVAL_SECONDS = 60
_CLAIM_SWEEP_INTERVAL_SECONDS = 60


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
        recover_stale_builds()
    except Exception as e:
        logger.error("Build recovery failed: %s", e)


def _audit_cleanup_loop():
    """Run audit cleanup periodically."""
    while True:
        time.sleep(_CLEANUP_INTERVAL_HOURS * 3600)
        _cleanup_old_audit_logs()


def _build_recovery_loop():
    """Check for stale builds every 60 seconds."""
    # Wait 30s after startup before first check (let builds claim)
    time.sleep(30)
    while True:
        _recover_stale_builds()
        time.sleep(_BUILD_RECOVERY_INTERVAL_SECONDS)


def _claim_expiry_sweep_loop():
    """Periodically transition expired/abandoned FixtureClaims.

    Background sweep that flips ACTIVE → EXPIRED past expiresAt and
    ACTIVE → ABANDONED past hardCeilingAt. Without this thread a stale
    DEV_HOLD claim would block every scheduling path until manually
    released — defeating the whole point of the sliding TTL.

    Audit rows are written here (instead of inside the sweeper itself)
    so the service module stays HTTP-agnostic and reusable from tests.
    """
    from src.api.v2.fixture_claims.service import sweep_expired_claims
    from src.lib.audit import log_audit

    time.sleep(30)  # initial delay — same convention as the other loops
    while True:
        try:
            result = sweep_expired_claims(get_db_client())
            for cid in result.get("expired", []):
                # No Flask request context here — log_audit gracefully
                # handles a missing g.current_user / request.
                try:
                    log_audit(
                        "fixture.claim.release",
                        "FixtureClaim",
                        cid,
                        {"reason": "expired"},
                    )
                except Exception:
                    pass
            for cid in result.get("abandoned", []):
                try:
                    log_audit(
                        "fixture.claim.release",
                        "FixtureClaim",
                        cid,
                        {"reason": "abandoned"},
                    )
                except Exception:
                    pass
            transitioned = len(result.get("expired", [])) + len(result.get("abandoned", []))
            if transitioned:
                logger.info(
                    "Fixture-claim sweep: %d expired, %d abandoned",
                    len(result.get("expired", [])),
                    len(result.get("abandoned", [])),
                )
        except Exception as e:
            logger.warning("Fixture-claim sweep tick failed: %s", e)
        time.sleep(_CLAIM_SWEEP_INTERVAL_SECONDS)


def _node_ip_refresh_loop():
    """Keep Node.ipAddress in sync with live K8s InternalIPs.

    Verdin edge fixtures get DHCP-assigned IPs that rotate on
    reboot. The MTIB observability poller + per-node fixture health
    check both read Node.ipAddress from the DB cache, so a rebooted
    Verdin with a new lease silently becomes unprobeable until the
    cache is refreshed. Runs every 60 s so a Verdin coming back
    online is reachable within at most one cycle without needing
    anyone to click around in the UI.
    """
    from src.services.kubernetes.node_sync import refresh_node_ips_from_k8s
    time.sleep(60)  # let other init settle before the first sweep
    while True:
        try:
            updated = refresh_node_ips_from_k8s()
            if updated:
                logger.info("node_ip_refresh: updated %d Node.ipAddress row(s)", updated)
        except Exception as e:
            logger.warning("node_ip_refresh tick failed: %s", e)
        time.sleep(_NODE_IP_REFRESH_INTERVAL_SECONDS)


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

    # Node IP refresh (Verdin DHCP self-heal — backstop for the discover endpoint)
    t_nodeip = threading.Thread(target=_node_ip_refresh_loop, daemon=True, name="node-ip-refresh")
    t_nodeip.start()
    logger.info("Node IP refresh scheduler started (interval=%ds)", _NODE_IP_REFRESH_INTERVAL_SECONDS)

    # Fixture-claim expiry sweep (DEV_HOLD lifecycle — see api/v2/fixture_claims/)
    t_claim = threading.Thread(target=_claim_expiry_sweep_loop, daemon=True, name="claim-expiry-sweep")
    t_claim.start()
    logger.info("Fixture-claim expiry sweep started (interval=%ds)", _CLAIM_SWEEP_INTERVAL_SECONDS)

    # Bitbucket poller — polls repos for new commits to trigger stage builds
    if env_config.BITBUCKET_POLLER_ENABLED:
        def _poller_loop():
            """Background loop that polls Bitbucket for new commits."""
            interval = env_config.BITBUCKET_POLLER_INTERVAL_S
            time.sleep(30)  # Initial delay to let services start
            while True:
                try:
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
    start_queue_scheduler()
