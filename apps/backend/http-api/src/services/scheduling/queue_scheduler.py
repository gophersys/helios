"""Unified queue scheduler — processes build, validation, and manufacturing queues.

Background thread in http-api that:
1. Dispatches queued builds (priority order, concurrency limit)
2. Assigns queued validation entries to fixtures (priority order, concurrency cap)
3. Gates manufacturing sessions (concurrency limit)
4. Reconciles stuck jobs (exceeded timeout -> FAILED, free resources)

Also event-triggered for low latency via wake_scheduler().
"""

import json
import logging
import threading
import time
import urllib.request
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from config.env import env_config
from src.api.v2.runs.scheduler import schedule_queue
from src.services.database.prisma import get_db_client
from src.services.executors import get_executor

logger = logging.getLogger(__name__)

# Wake event — set() to trigger immediate scheduler run
_wake_event = threading.Event()


def wake_scheduler():
    """Signal the scheduler to run immediately (event-driven dispatch).

    Called by:
    - build_trigger.py after creating QUEUED BuildJobs
    - runs/scheduler.py after on_build_complete creates a queue entry
    - fixture freed handler
    """
    _wake_event.set()


# ---------------------------------------------------------------------------
#  Build queue
# ---------------------------------------------------------------------------

def _schedule_builds(max_concurrent: int) -> int:
    """Dispatch QUEUED BuildJobs respecting priority and concurrency limit.

    The actual execution is handled by build-service (polls /v2/builds?status=QUEUED).
    This function ensures we don't surface more jobs than the concurrency limit
    by notifying build-service only when slots are available.

    Returns number of jobs eligible for dispatch (informational).
    """
    db = get_db_client()

    active_count = db.buildjob.count(
        where={"status": {"in": ["BUILDING", "CLONING"]}}
    )

    if active_count >= max_concurrent:
        return 0

    available_slots = max_concurrent - active_count

    # Count how many QUEUED jobs are waiting — build-service will pick them up
    # in priority order since the list endpoint sorts by priority DESC, createdAt ASC
    queued_count = db.buildjob.count(where={"status": "QUEUED"})

    eligible = min(queued_count, available_slots)

    if eligible > 0 and queued_count > available_slots:
        logger.info(
            "Build queue: %d active, %d queued, %d eligible (limit=%d)",
            active_count, queued_count, eligible, max_concurrent,
        )

    # Notify build-service if it has a push endpoint
    if eligible > 0:
        _notify_build_service(db, eligible)

    return eligible


def _notify_build_service(db, count: int):
    """Push-notify build-service about available jobs (best-effort)."""
    try:
        build_service_url = getattr(env_config, "BUILD_SERVICE_URL", "")
        if not build_service_url:
            return  # No push endpoint — build-service will poll

        req = urllib.request.Request(
            f"{build_service_url}/jobs/notify",
            data=json.dumps({"count": count}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        urllib.request.urlopen(req, timeout=5)
    except Exception as e:
        logger.debug("Failed to notify build-service: %s", e)


# ---------------------------------------------------------------------------
#  Validation queue
# ---------------------------------------------------------------------------

def _schedule_validation(max_concurrent: int) -> List[Dict[str, Any]]:
    """Assign QUEUED validation entries to fixtures, respecting concurrency.

    Delegates to the existing schedule_queue() which handles priority ordering
    and fixture matching. This wrapper enforces the concurrency cap.

    Returns list of assignments made.
    """
    db = get_db_client()

    active_count = db.validationqueueentry.count(
        where={"status": {"in": ["ASSIGNED", "RUNNING"]}}
    )

    if active_count >= max_concurrent:
        return []

    available_slots = max_concurrent - active_count

    try:
        return _run_validation_scheduler(available_slots)
    except Exception as e:
        logger.error("Validation scheduling error: %s", e)
        return []


def _run_validation_scheduler(max_assignments: int) -> list:
    """Wrapper to call schedule_queue — exists for testability."""
    return schedule_queue(max_assignments=max_assignments)


# ---------------------------------------------------------------------------
#  Manufacturing gate
# ---------------------------------------------------------------------------

def get_manufacturing_active_count() -> int:
    """Count active manufacturing sessions. Used by session creation endpoint."""
    db = get_db_client()
    return db.manufacturingsession.count(where={"status": "ACTIVE"})


# ---------------------------------------------------------------------------
#  Stuck job reconciliation
# ---------------------------------------------------------------------------

def _reconcile_stuck_jobs(
    validation_timeout_min: int,
    manufacturing_timeout_min: int,
) -> int:
    """Fail jobs that exceeded their timeout. Returns count of reconciled.

    Builds: handled by existing build_recovery.py (runs on its own thread).
    Validation: RUNNING entries older than timeout → FAILED, free fixture.
    Manufacturing: ACTIVE sessions older than timeout → log warning only
                   (operator might be mid-test; don't auto-kill).
    """
    db = get_db_client()
    now = datetime.now(timezone.utc)
    reconciled = 0

    # --- Validation stuck entries ---
    val_cutoff = now - timedelta(minutes=validation_timeout_min)
    stuck_validation = db.validationqueueentry.find_many(
        where={
            "status": "RUNNING",
            "startedAt": {"lt": val_cutoff},
        },
    )

    for entry in stuck_validation:
        try:
            # Mark entry FAILED
            db.validationqueueentry.update(
                where={"id": entry.id},
                data={
                    "status": "FAILED",
                    "completedAt": now,
                    "errorMessage": f"Timed out after {validation_timeout_min} minutes",
                },
            )
            # Free the fixture
            if entry.fixtureId:
                db.fixture.update(
                    where={"id": entry.fixtureId},
                    data={
                        "status": "AVAILABLE",
                        "lockedBy": None,
                        "lockedAt": None,
                    },
                )
            # Cancel the K8s job / Docker container if possible
            if entry.jobName:
                _try_cancel_job(entry.jobName)

            logger.warning(
                "Reconciled stuck validation entry %s (started=%s, fixture=%s)",
                entry.id[:8],
                entry.startedAt.isoformat() if entry.startedAt else "?",
                entry.fixtureId[:8] if entry.fixtureId else "none",
            )
            reconciled += 1
        except Exception as e:
            logger.error("Failed to reconcile validation entry %s: %s", entry.id[:8], e)

    # --- Manufacturing stuck sessions (warn only) ---
    mfg_cutoff = now - timedelta(minutes=manufacturing_timeout_min)
    stuck_mfg = db.manufacturingsession.find_many(
        where={
            "status": "ACTIVE",
            "createdAt": {"lt": mfg_cutoff},
        },
    )
    for session in stuck_mfg:
        age_min = int((now - session.createdAt).total_seconds() / 60)
        logger.warning(
            "Manufacturing session %s has been ACTIVE for %d minutes (threshold=%d). "
            "May be abandoned — operator should end it.",
            session.id[:8], age_min, manufacturing_timeout_min,
        )

    return reconciled


def _try_cancel_job(job_name: str):
    """Best-effort cancellation of a running job."""
    try:
        executor = get_executor("validation")
        namespace = getattr(env_config, "VALIDATION_NAMESPACE", "validation")
        executor.cancel(job_name, namespace=namespace)
    except Exception as e:
        logger.debug("Could not cancel job %s: %s", job_name, e)


# ---------------------------------------------------------------------------
#  Scheduler loop
# ---------------------------------------------------------------------------

def _get_config():
    """Load scheduler config from env. Called each tick for dynamic updates."""
    return {
        "interval": getattr(env_config, "SCHEDULER_INTERVAL_S", 15),
        "max_builds": getattr(env_config, "MAX_CONCURRENT_BUILDS", 4),
        "max_validation": getattr(env_config, "MAX_CONCURRENT_VALIDATION_RUNS", 8),
        "max_manufacturing": getattr(env_config, "MAX_CONCURRENT_MANUFACTURING_SESSIONS", 4),
        "build_timeout": getattr(env_config, "BUILD_TIMEOUT_MINUTES", 45),
        "validation_timeout": getattr(env_config, "VALIDATION_TIMEOUT_MINUTES", 60),
        "manufacturing_timeout": getattr(env_config, "MANUFACTURING_TIMEOUT_MINUTES", 120),
    }


_shutdown = False


def stop_scheduler():
    """Signal the scheduler to exit its loop."""
    global _shutdown
    _shutdown = True
    _wake_event.set()


def _scheduler_loop():
    """Main scheduler loop — runs every interval or on wake event."""
    time.sleep(15)  # Initial delay to let services start

    while not _shutdown:
        try:
            cfg = _get_config()

            builds = _schedule_builds(cfg["max_builds"])
            validations = _schedule_validation(cfg["max_validation"])
            reconciled = _reconcile_stuck_jobs(
                cfg["validation_timeout"],
                cfg["manufacturing_timeout"],
            )

            if builds or validations or reconciled:
                logger.info(
                    "Scheduler tick: %d build slots, %d validation assignments, %d reconciled",
                    builds, len(validations) if isinstance(validations, list) else 0, reconciled,
                )
        except Exception as e:
            logger.error("Queue scheduler error: %s", e)

        # Wait for interval OR early wake signal
        cfg = _get_config()
        _wake_event.wait(timeout=cfg["interval"])
        _wake_event.clear()


def start_queue_scheduler():
    """Start the queue scheduler background thread.

    Called from start_scheduler() in services/scheduler.py.
    """
    cfg = _get_config()
    t = threading.Thread(target=_scheduler_loop, daemon=True, name="queue-scheduler")
    t.start()
    logger.info(
        "Queue scheduler started (interval=%ds, builds=%d, validation=%d, manufacturing=%d)",
        cfg["interval"],
        cfg["max_builds"],
        cfg["max_validation"],
        cfg["max_manufacturing"],
    )
