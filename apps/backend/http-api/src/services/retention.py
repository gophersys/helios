"""Retention policy service for validation run + test package cleanup.

Implements:
  * 60-day retention for validation run artifacts stored in MinIO.
  * 30-day retention for DEVELOPMENT test packages, keeping the last
    N=5 per (product, type) so the most-recent dev iteration is always
    available for re-running. Released packages are immutable and never
    GC'd here — they're product history.

Both run as scheduled tasks or can be triggered manually via API.
"""

import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from src.services.database.prisma import get_db_client
from src.services.storage.client import (
    StoragePrefixes,
    get_bucket_name,
    get_storage_client,
    storage_key,
)

logger = logging.getLogger(__name__)


def _emit_summary(scope: str, **fields) -> None:
    """Emit a single canonical summary line per retention run.

    Loki/Grafana queries pivot on the ``concord_retention_summary``
    prefix and derive operational counters from the structured fields.
    Format is intentionally machine-friendly (`key=value` pairs) so a
    LogQL ``json`` parser pulls everything into labels for free.
    """
    parts = [f"{k}={v}" for k, v in fields.items() if v is not None]
    logger.info("concord_retention_summary scope=%s %s", scope, " ".join(parts))

# Default retention period in days
DEFAULT_RETENTION_DAYS = 60

# Test-package retention defaults — every dev upload now creates a new
# immutable row, so without GC the dev_packages table grows linearly with
# upload frequency. 30 days + last-5-per-product is a reasonable
# floor: a developer can iterate hundreds of times in a sprint without
# anything ageing out, and operators can revert recent dev versions for
# weeks without surprise pruning.
DEV_PACKAGE_RETENTION_DAYS = 30
DEV_PACKAGE_KEEP_LATEST = 5

# UPLOADING placeholders older than this are considered a failed
# two-phase upload and reaped. The window is generous — a slow CI
# upload can take many minutes — but anything past an hour is
# definitively stuck.
UPLOADING_PLACEHOLDER_AGE_MINUTES = 60


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
    old_runs = db.testrun.find_many(
        where={
            "completedAt": {"lt": cutoff},
        },
        include={
            "targets": {"include": {"executions": {"include": {"steps": True}}}},
        },
    )

    if not old_runs:
        logger.info("No runs to clean up")
        _emit_summary(
            "validation_runs",
            deleted=0, objects_deleted=0, errors=0,
            retention_days=retention_days,
        )
        return {"runs_deleted": 0, "objects_deleted": 0}

    runs_deleted = 0
    objects_deleted = 0
    errors = []

    for run in old_runs:
        run_id = run.id
        logger.info(f"Cleaning up run {run_id} (completed {run.completedAt})")

        # Delete MinIO objects
        prefix = storage_key(StoragePrefixes.SESSIONS, f"{run_id}/")
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
            db.testrun.delete(where={"id": run_id})
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
    _emit_summary(
        "validation_runs",
        deleted=runs_deleted,
        objects_deleted=objects_deleted,
        errors=len(errors),
        retention_days=retention_days,
    )
    return summary


def cleanup_old_dev_test_packages(
    retention_days: int = DEV_PACKAGE_RETENTION_DAYS,
    keep_latest: int = DEV_PACKAGE_KEEP_LATEST,
    dry_run: bool = False,
) -> dict:
    """Delete DEVELOPMENT test packages older than the retention window.

    Per-product+type bucket: the most recent ``keep_latest`` dev packages
    survive regardless of age, so a quiet product still has its last few
    iterations available. Older rows are dropped with their MinIO
    tarball; ``FixtureDesign`` is FK-cascaded by the schema.

    RELEASED packages and any package referenced by a TestRun, an
    active manufacturing session, or a stage-config binding are never
    touched here — those are product history and active references.

    Args:
        retention_days: Drop dev packages older than this many days.
        keep_latest: Keep at least this many most-recent dev packages
            per (productId, type), regardless of age.
        dry_run: When True, log what would be deleted without making
            changes. Useful for safe first runs.

    Returns:
        Summary dict with counts and any errors.
    """
    db = get_db_client()
    storage = get_storage_client()
    bucket = get_bucket_name()

    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)

    logger.info(
        "Test-package retention: cutoff %s, keep_latest=%d, dry_run=%s",
        cutoff.isoformat(), keep_latest, dry_run,
    )

    # All DEV packages, ordered newest-first so the keep-latest slice
    # is straightforward. Eager-load the fixture design so the
    # Fixture-reference check below doesn't need an extra round-trip.
    dev_packages = db.testpackage.find_many(
        where={"status": "DEVELOPMENT"},
        order={"createdAt": "desc"},
        include={"fixtureDesign": True},
    )

    # Bucket by (productId, type) so we apply keep_latest per bucket.
    by_bucket: dict[tuple[str, str], list] = defaultdict(list)
    for tp in dev_packages:
        by_bucket[(tp.productId, tp.type)].append(tp)

    deletable = []
    for bucket_key, packages in by_bucket.items():
        # Keep the first N (newest) regardless of age.
        survivors = packages[:keep_latest]
        candidates = packages[keep_latest:]
        for tp in candidates:
            if tp.createdAt < cutoff:
                deletable.append(tp)

    if not deletable:
        logger.info("Test-package retention: nothing to delete")
        return {
            "packages_deleted": 0,
            "objects_deleted": 0,
            "retention_days": retention_days,
            "keep_latest": keep_latest,
            "cutoff_date": cutoff.isoformat(),
            "dry_run": dry_run,
        }

    packages_deleted = 0
    objects_deleted = 0
    skipped_in_use = 0
    errors: list = []

    for tp in deletable:
        # Refuse to delete a package that any TestRun references — runs
        # can outlive their package's retention window and need the
        # version metadata + tarball to stay reachable for their report.
        run_count = db.testrun.count(where={"testPackageId": tp.id})
        if run_count > 0:
            logger.debug(
                "Skipping test package %s — referenced by %d test runs",
                tp.id[:8], run_count,
            )
            skipped_in_use += 1
            continue

        # Same defensive check for active manufacturing sessions and
        # stage-config bindings, even though normal flows should clean
        # those up first. Better skip than orphan an active reference.
        session_count = db.manufacturingsession.count(where={"testPackageId": tp.id})
        stage_count = db.productstageconfig.count(where={"releasedTestPackageId": tp.id})
        if session_count or stage_count:
            logger.debug(
                "Skipping test package %s — referenced by %d sessions, %d stages",
                tp.id[:8], session_count, stage_count,
            )
            skipped_in_use += 1
            continue

        # FixtureDesign cascades from TestPackage (onDelete: Cascade), but
        # Fixture pins its design with onDelete: Restrict — a stale dev
        # rig still pointing at this design would block the cascade with
        # a constraint violation. Detect that here and skip cleanly so
        # the retention run produces a clear "stale fixture is holding
        # this design" log instead of a postgres error.
        if tp.fixtureDesign:
            fixture_count = db.fixture.count(where={"designId": tp.fixtureDesign.id})
            if fixture_count:
                logger.debug(
                    "Skipping test package %s — design %s is in use by %d fixture(s)",
                    tp.id[:8], tp.fixtureDesign.id[:8], fixture_count,
                )
                skipped_in_use += 1
                continue

        if dry_run:
            logger.info(
                "[dry-run] Would delete test package %s@%s (created %s, type=%s)",
                tp.id[:8], tp.version, tp.createdAt, tp.type,
            )
            packages_deleted += 1
            continue

        # Delete the MinIO tarball before the row so a partial failure
        # leaves the row pointing at a real object — easier to retry.
        try:
            if tp.storageKey:
                storage.remove_object(bucket, tp.storageKey)
                objects_deleted += 1
        except Exception as e:
            logger.warning(
                "Failed to delete storage object %s for package %s: %s",
                tp.storageKey, tp.id[:8], e,
            )
            errors.append({"packageId": tp.id, "error": f"MinIO: {e}"})
            # Continue to DB delete — orphan tarballs can be cleaned later.

        try:
            db.testpackage.delete(where={"id": tp.id})
            packages_deleted += 1
            logger.info(
                "Deleted test package %s@%s (type=%s, createdAt=%s)",
                tp.id[:8], tp.version, tp.type, tp.createdAt,
            )
        except Exception as e:
            logger.error("Failed to delete test package %s: %s", tp.id[:8], e)
            errors.append({"packageId": tp.id, "error": f"DB: {e}"})

    summary = {
        "packages_deleted": packages_deleted,
        "objects_deleted": objects_deleted,
        "skipped_in_use": skipped_in_use,
        "retention_days": retention_days,
        "keep_latest": keep_latest,
        "cutoff_date": cutoff.isoformat(),
        "dry_run": dry_run,
    }
    if errors:
        summary["errors"] = errors

    logger.info("Test-package retention complete: %s", summary)
    _emit_summary(
        "test_packages",
        deleted=packages_deleted,
        kept_in_use=skipped_in_use,
        objects_deleted=objects_deleted,
        errors=len(errors),
        retention_days=retention_days,
        keep_latest=keep_latest,
        dry_run=int(bool(dry_run)),
    )
    return summary


def cleanup_stuck_uploading_test_packages(
    age_minutes: int = UPLOADING_PLACEHOLDER_AGE_MINUTES,
    dry_run: bool = False,
) -> dict:
    """Reap stuck ``status=UPLOADING`` test-package placeholders.

    The two-phase upload path creates a placeholder row before the MinIO
    put. On a successful upload the placeholder is flipped to
    DEVELOPMENT/RELEASED. On a failed upload the placeholder stays in
    UPLOADING — those rows are this sweep's target.

    Anything older than ``age_minutes`` is dropped. The placeholder
    holds the (productId, version, type) slot, so leaving them in place
    blocks future re-uploads of the same version.
    """
    db = get_db_client()
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=age_minutes)

    stuck = db.testpackage.find_many(
        where={"status": "UPLOADING", "createdAt": {"lt": cutoff}},
    )

    summary = {
        "stuck_packages": len(stuck),
        "deleted": 0,
        "errors": [],
        "age_minutes": age_minutes,
        "cutoff_date": cutoff.isoformat(),
        "dry_run": dry_run,
    }

    for tp in stuck:
        if dry_run:
            logger.info(
                "[dry-run] Would reap stuck UPLOADING placeholder %s@%s (created %s)",
                tp.id[:8], tp.version, tp.createdAt,
            )
            summary["deleted"] += 1
            continue
        try:
            db.testpackage.delete(where={"id": tp.id})
            summary["deleted"] += 1
            logger.info(
                "Reaped stuck UPLOADING placeholder %s@%s (created %s)",
                tp.id[:8], tp.version, tp.createdAt,
            )
        except Exception as e:  # noqa: BLE001
            logger.error(
                "Failed to delete stuck placeholder %s: %s", tp.id[:8], e,
            )
            summary["errors"].append({"packageId": tp.id, "error": str(e)})

    logger.info("Stuck-upload reaper complete: %s", summary)
    _emit_summary(
        "stuck_uploads",
        deleted=summary["deleted"],
        stuck_total=summary["stuck_packages"],
        errors=len(summary["errors"]),
        age_minutes=age_minutes,
        dry_run=int(bool(dry_run)),
    )
    return summary


def get_storage_usage() -> dict:
    """Get storage usage statistics for validation runs.

    Returns:
        Dict with total size, object count, and per-run breakdown
    """
    storage = get_storage_client()
    bucket = get_bucket_name()
    prefix = storage_key(StoragePrefixes.SESSIONS, "")

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


# CLI entrypoint — invoked by the retention CronJob inside the http-api image.
#
# Usage:
#   python -m src.services.retention test-packages [--dry-run] [--days N] [--keep K]
#   python -m src.services.retention runs [--dry-run] [--days N]
if __name__ == "__main__":
    import argparse
    import json
    import sys

    parser = argparse.ArgumentParser(description="Concord retention CLI")
    sub = parser.add_subparsers(dest="cmd", required=True)

    tp_parser = sub.add_parser("test-packages", help="GC old DEVELOPMENT test packages")
    tp_parser.add_argument("--days", type=int, default=DEV_PACKAGE_RETENTION_DAYS)
    tp_parser.add_argument("--keep", type=int, default=DEV_PACKAGE_KEEP_LATEST)
    tp_parser.add_argument("--dry-run", action="store_true")

    stuck_parser = sub.add_parser(
        "stuck-uploads",
        help="GC stuck UPLOADING test-package placeholders",
    )
    stuck_parser.add_argument(
        "--minutes", type=int, default=UPLOADING_PLACEHOLDER_AGE_MINUTES,
    )
    stuck_parser.add_argument("--dry-run", action="store_true")

    runs_parser = sub.add_parser("runs", help="GC old validation run artifacts")
    runs_parser.add_argument("--days", type=int, default=DEFAULT_RETENTION_DAYS)

    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    if args.cmd == "test-packages":
        result = cleanup_old_dev_test_packages(
            retention_days=args.days,
            keep_latest=args.keep,
            dry_run=args.dry_run,
        )
    elif args.cmd == "stuck-uploads":
        result = cleanup_stuck_uploading_test_packages(
            age_minutes=args.minutes,
            dry_run=args.dry_run,
        )
    else:
        result = cleanup_old_validation_runs(retention_days=args.days)

    print(json.dumps(result, indent=2, default=str))
    if result.get("errors"):
        sys.exit(1)
