"""Build recovery service — detects and resets stale builds.

Runs periodically to find builds stuck in BUILDING/CLONING state
(worker crashed or lost connectivity) and resets them to QUEUED
so another worker can pick them up.

Uses tiered timeouts:
- CLONING: 5 minutes (git clone + submodules should never take this long)
- BUILDING: 10 minutes (firmware builds typically take 5-8 min)

Builds that fail recovery 3+ times are marked FAILED permanently
to avoid infinite retry loops on broken configs.
"""

import logging
from datetime import datetime, timezone, timedelta

from database import Json
from src.services.database.prisma import get_db_client

logger = logging.getLogger(__name__)

# Tiered timeouts — CLONING is fast, BUILDING can take longer
CLONING_TIMEOUT_MINUTES = 5
BUILDING_TIMEOUT_MINUTES = 10
MAX_RECOVERY_ATTEMPTS = 3


def _get_recovery_count(build) -> int:
    """Extract recovery count from webhookData."""
    wd = build.webhookData if isinstance(build.webhookData, dict) else {}
    return wd.get("recoveryCount", 0)


def recover_stale_builds() -> int:
    """Find and reset stale builds. Returns count of recovered builds."""
    db = get_db_client()
    now = datetime.now(timezone.utc)
    cloning_cutoff = now - timedelta(minutes=CLONING_TIMEOUT_MINUTES)
    building_cutoff = now - timedelta(minutes=BUILDING_TIMEOUT_MINUTES)

    # Find stale CLONING builds (5-minute timeout)
    stale_cloning = db.buildjob.find_many(
        where={
            "status": "CLONING",
            "startedAt": {"lt": cloning_cutoff},
        },
    )

    # Find stale BUILDING builds (10-minute timeout)
    stale_building = db.buildjob.find_many(
        where={
            "status": "BUILDING",
            "startedAt": {"lt": building_cutoff},
        },
    )

    stale_builds = stale_cloning + stale_building

    if not stale_builds:
        return 0

    recovered = 0
    for build in stale_builds:
        recovery_count = _get_recovery_count(build) + 1
        timeout = CLONING_TIMEOUT_MINUTES if build.status == "CLONING" else BUILDING_TIMEOUT_MINUTES
        age_min = int((now - build.startedAt).total_seconds() / 60) if build.startedAt else 0
        worker_id = build.webhookData.get("workerId", "unknown") if isinstance(build.webhookData, dict) else "unknown"

        # Update webhookData with recovery count
        webhook_data = dict(build.webhookData) if isinstance(build.webhookData, dict) else {}
        webhook_data["recoveryCount"] = recovery_count
        webhook_data["lastRecovery"] = now.isoformat()

        if recovery_count > MAX_RECOVERY_ATTEMPTS:
            # Too many retries — mark as permanently FAILED
            logger.error(
                "Build %s permanently FAILED after %d recovery attempts "
                "(status=%s, worker=%s, age=%dm)",
                build.id[:8], recovery_count, build.status, worker_id, age_min,
            )
            db.buildjob.update(
                where={"id": build.id},
                data={
                    "status": "FAILED",
                    "finishedAt": now,
                    "webhookData": Json(webhook_data),
                    "errorMessage": (
                        f"Permanently failed: stuck in {build.status} {recovery_count} times "
                        f"(worker={worker_id}). Build may have a configuration issue."
                    ),
                },
            )
            # If this build is part of a pipeline, check completion
            if build.pipelineRunId:
                try:
                    from src.api.v2.builds.pipelines import check_pipeline_completion
                    check_pipeline_completion(build.pipelineRunId)
                except Exception:
                    pass
        else:
            logger.warning(
                "Recovering stale build %s (status=%s, worker=%s, age=%dm, "
                "timeout=%dm, attempt=%d/%d)",
                build.id[:8], build.status, worker_id, age_min,
                timeout, recovery_count, MAX_RECOVERY_ATTEMPTS,
            )
            db.buildjob.update(
                where={"id": build.id},
                data={
                    "status": "QUEUED",
                    "startedAt": None,
                    "webhookData": Json(webhook_data),
                    "errorMessage": (
                        f"Auto-recovered: stuck in {build.status} for {age_min}m "
                        f"(worker={worker_id}, attempt {recovery_count}/{MAX_RECOVERY_ATTEMPTS})"
                    ),
                },
            )
        recovered += 1

    logger.info("Recovered %d stale builds", recovered)
    return recovered
