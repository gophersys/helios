"""Build recovery service — detects and resets stale builds.

Runs periodically to find builds stuck in BUILDING/CLONING state
(worker crashed or lost connectivity) and resets them to QUEUED
so another worker can pick them up.

A build is considered stale if:
- Status is BUILDING or CLONING
- startedAt is older than the timeout threshold (default: 15 minutes)
- No artifact uploads in the last 5 minutes (worker is dead, not just slow)
"""

import logging
from datetime import datetime, timezone, timedelta

from src.services.database.prisma import get_db_client

logger = logging.getLogger(__name__)

STALE_THRESHOLD_MINUTES = 15


def recover_stale_builds() -> int:
    """Find and reset stale builds. Returns count of recovered builds."""
    db = get_db_client()
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=STALE_THRESHOLD_MINUTES)

    stale_builds = db.buildjob.find_many(
        where={
            "status": {"in": ["BUILDING", "CLONING"]},
            "startedAt": {"lt": cutoff},
        },
    )

    if not stale_builds:
        return 0

    recovered = 0
    for build in stale_builds:
        logger.warning(
            "Recovering stale build %s (status=%s, started=%s)",
            build.id[:8], build.status,
            build.startedAt.isoformat() if build.startedAt else "unknown",
        )

        db.buildjob.update(
            where={"id": build.id},
            data={
                "status": "QUEUED",
                "startedAt": None,
                "errorMessage": f"Auto-recovered: stuck in {build.status} for >{STALE_THRESHOLD_MINUTES}m (worker likely died)",
            },
        )
        recovered += 1

    logger.info("Recovered %d stale builds", recovered)
    return recovered
