"""Retention policy service for validation run cleanup.

Implements 60-day retention for validation run artifacts stored in MinIO.
Runs as a scheduled task or can be triggered manually via API.
"""

import logging
from datetime import datetime, timedelta, timezone

from src.services.database.prisma import get_db_client
from src.services.storage.client import (
    StoragePrefixes,
    get_bucket_name,
    get_storage_client,
    storage_key,
)

logger = logging.getLogger(__name__)

# Default retention period in days
DEFAULT_RETENTION_DAYS = 60


def cleanup_old_validation_runs(retention_days: int = DEFAULT_RETENTION_DAYS) -> dict:
    """Delete validation runs older than retention period.

    Removes:
    - All MinIO objects under validation/runs/{run_id}/
    - Database records (Session, TestExecution, TestResult cascade)

    Args:
        retention_days: Number of days to retain runs (default: 60)

    Returns:
        Summary dict with counts of deleted runs and objects
    """
    db = get_db_client()
    storage = get_storage_client()
    bucket = get_bucket_name()

    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)

    logger.info(f"Running retention cleanup: deleting runs finished before {cutoff.isoformat()}")

    # Find runs older than cutoff that have finished
    old_runs = db.session.find_many(
        where={
            "finishedAt": {"lt": cutoff},
        },
        include={
            "testExecutions": {"include": {"results": True}},
        },
    )

    if not old_runs:
        logger.info("No runs to clean up")
        return {"runs_deleted": 0, "objects_deleted": 0}

    runs_deleted = 0
    objects_deleted = 0
    errors = []

    for run in old_runs:
        run_id = run.id
        logger.info(f"Cleaning up run {run_id} (finished {run.finishedAt})")

        # Delete MinIO objects
        prefix = storage_key(StoragePrefixes.VALIDATION_RUNS, f"{run_id}/")
        try:
            objects = list(storage.list_objects(bucket, prefix=prefix, recursive=True))
            for obj in objects:
                if not obj.is_dir:
                    storage.remove_object(bucket, obj.object_name)
                    objects_deleted += 1
                    logger.debug(f"Deleted object: {obj.object_name}")
        except Exception as e:
            logger.warning(f"Failed to delete objects for run {run_id}: {e}")
            errors.append({"run_id": run_id, "error": f"MinIO cleanup: {str(e)}"})

        # Delete database records (cascade handles TestExecution, TestResult, Log)
        try:
            db.session.delete(where={"id": run_id})
            runs_deleted += 1
            logger.info(f"Deleted run {run_id} from database")
        except Exception as e:
            logger.error(f"Failed to delete run {run_id} from database: {e}")
            errors.append({"run_id": run_id, "error": f"DB delete: {str(e)}"})

    summary = {
        "runs_deleted": runs_deleted,
        "objects_deleted": objects_deleted,
        "retention_days": retention_days,
        "cutoff_date": cutoff.isoformat(),
    }

    if errors:
        summary["errors"] = errors

    logger.info(f"Retention cleanup complete: {runs_deleted} runs, {objects_deleted} objects deleted")
    return summary


def get_storage_usage() -> dict:
    """Get storage usage statistics for validation runs.

    Returns:
        Dict with total size, object count, and per-run breakdown
    """
    storage = get_storage_client()
    bucket = get_bucket_name()
    prefix = storage_key(StoragePrefixes.VALIDATION_RUNS, "")

    total_size = 0
    total_objects = 0
    runs = {}

    try:
        objects = storage.list_objects(bucket, prefix=prefix, recursive=True)
        for obj in objects:
            if obj.is_dir:
                continue

            total_size += obj.size or 0
            total_objects += 1

            # Extract run_id from path: validation/runs/{run_id}/...
            parts = obj.object_name.split("/")
            if len(parts) >= 3:
                run_id = parts[2]
                if run_id not in runs:
                    runs[run_id] = {"size": 0, "objects": 0}
                runs[run_id]["size"] += obj.size or 0
                runs[run_id]["objects"] += 1

    except Exception as e:
        logger.error(f"Failed to get storage usage: {e}")
        return {"error": str(e)}

    return {
        "total_size_bytes": total_size,
        "total_size_mb": round(total_size / (1024 * 1024), 2),
        "total_objects": total_objects,
        "runs_count": len(runs),
        "runs": runs,
    }
