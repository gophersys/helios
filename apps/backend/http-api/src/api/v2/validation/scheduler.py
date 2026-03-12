"""Validation queue scheduler.

Assigns queued validation entries to available test benches.
Called periodically or on events (build complete, bench freed).
Automatically triggers K8s validation jobs after assignment.
"""

import hashlib
import logging
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from database import Json
from config.env import env_config
from src.lib.audit import log_audit
from src.services.database.prisma import get_db_client

logger = logging.getLogger(__name__)

# Stage number to name mapping for K8s job
STAGE_NAMES = {1: "smoke", 2: "silicon", 3: "integration", 4: "nightly", 5: "fuota"}


def _create_job_api_key(db, entry_id: str) -> str:
    """Create a database-backed API key for the validation K8s job.

    Returns the raw key string to be injected into the K8s Job env.
    Key expires after 24 hours.
    """
    raw_key = f"ck_queue_{secrets.token_urlsafe(32)}"
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()

    # Get a system user ID for scheduler-created keys
    system_user = db.user.find_first(where={"email": "system@concord.local"})
    if not system_user:
        # Fallback: try any user if system user doesn't exist
        system_user = db.user.find_first()
    user_id = system_user.id if system_user else None

    db.apikey.create(
        data={
            "name": f"Queue entry {entry_id}",
            "keyHash": key_hash,
            "keyPrefix": raw_key[:14],
            "userId": user_id,
            "expiresAt": datetime.now(timezone.utc) + timedelta(hours=24),
        },
    )

    return raw_key


def _create_validation_run(
    db,
    entry_id: str,
    pipeline,
    bench,
    stage: int,
    stage_name: str,
) -> Optional[str]:
    """Create a ValidationRun (Session) and Device record for the queue entry.

    Returns the session ID if successful, None otherwise.
    """
    # Look up product by slug
    product_obj = db.product.find_first(where={"slug": pipeline.product})
    if not product_obj:
        logger.error(f"Product not found for slug: {pipeline.product}")
        return None

    # Get system user ID
    system_user = db.user.find_first(where={"email": "system@concord.local"})
    if not system_user:
        system_user = db.user.find_first()
    if not system_user:
        logger.error("No users found in database for session creation")
        return None

    # Build session name
    session_name = f"Queue {entry_id[:8]} - Stage {stage_name}"

    # Create session (ValidationRun)
    session = db.session.create(
        data={
            "name": session_name,
            "productId": product_obj.id,
            "pipelineRunId": pipeline.id,
            "createdById": system_user.id,
            "status": "ACTIVE",
            "targetCount": 1,
            "config": Json({
                "benchId": bench.id,
                "stationId": bench.stationId,
                "queueEntryId": entry_id,
                "stage": stage,
                "stageName": stage_name,
            }),
        },
    )

    # Create device record linked to session
    device_snr = bench.dutSnr or "UNKNOWN"
    db.device.create(
        data={
            "serialNumber": device_snr,
            "sessionId": session.id,
            "status": "PENDING",
            "metadata": Json({
                "deviceId": bench.dutDeviceId,
                "benchId": bench.id,
                "mtibAddress": bench.mtibAddress,
            }),
        },
    )

    logger.info(f"Created validation run {session.id} for queue entry {entry_id}")
    return session.id


def _trigger_validation_job(
    db,
    entry_id: str,
    bench_id: str,
    stage: int,
    product: str,
) -> Optional[str]:
    """Create a K8s validation job for an assigned queue entry.

    Returns the job name if successful, None otherwise.
    """
    # Import here to avoid circular imports
    from src.api.v2.validation.tests.run import create_kubernetes_job

    # Get full entry with relations
    entry = db.validationqueueentry.find_unique(
        where={"id": entry_id},
        include={
            "pipelineRun": True,
            "bench": True,
        },
    )

    if not entry or not entry.pipelineRun:
        logger.error(f"Queue entry {entry_id} not found or missing pipeline")
        return None

    bench = entry.bench
    if not bench:
        logger.error(f"Queue entry {entry_id} has no bench assigned")
        return None

    pipeline = entry.pipelineRun

    # Stage name for K8s job (needed for session creation too)
    stage_name = STAGE_NAMES.get(stage, "validation")

    # Create ValidationRun (Session) record first
    run_id = _create_validation_run(db, entry_id, pipeline, bench, stage, stage_name)
    if not run_id:
        logger.error(f"Failed to create validation run for queue entry {entry_id}")
        return None

    # Create API key for the job
    api_key = _create_job_api_key(db, entry_id)

    # Concord API URL for reporter callbacks
    api_url = os.environ.get(
        "CONCORD_API_URL",
        "http://concord-http-api.staging.svc.cluster.local:9001"
    )

    # Extract MTIB address (strip port if present)
    mtib_addr_full = bench.mtibAddress or ""
    mtib_host = mtib_addr_full.split(":")[0] if mtib_addr_full else ""

    # Product slug for catalog lookup (pipeline.product is a string like "alpha_b0")
    product_slug = pipeline.product if hasattr(pipeline, "product") else None

    # Compute fixture profile path from bench product/revision
    fixture_profile_path = f"/app/fixtures/{bench.dutProduct}_{bench.dutRevision}.json"

    # Create the K8s job
    job_name = create_kubernetes_job(
        product=product,
        job_id=entry_id,
        firmware_path="",  # Pipeline-based tests fetch from MinIO
        test_type="validation",
        test_enable={},
        firmware_version="",
        run_id=run_id,  # Use Session ID, not entry_id
        api_key=api_key,
        api_url=api_url,
        mtib_address=mtib_host,
        bench_id=bench.id,
        device_id=bench.dutDeviceId,
        device_snr=bench.dutSnr,
        fixture_profile_path=fixture_profile_path,
        pipeline_id=pipeline.id,
        product_slug=product_slug,
        stage=stage_name,
    )

    if not job_name:
        logger.error(f"Failed to create K8s job for queue entry {entry_id}")
        return None

    # Update entry status to RUNNING with job name
    # Note: validationRunId FK points to ValidationRun table, not Session
    # The run_id here is a Session ID, which the reporter uses
    now = datetime.now(timezone.utc)
    db.validationqueueentry.update(
        where={"id": entry_id},
        data={
            "status": "RUNNING",
            "startedAt": now,
            "jobName": job_name,
        },
    )

    log_audit(
        "queue.trigger",
        "ValidationQueueEntry",
        entry_id,
        {"jobName": job_name, "stage": stage_name, "pipelineId": pipeline.id, "sessionId": run_id},
    )

    return job_name


def schedule_queue() -> List[Dict[str, Any]]:
    """Process the validation queue and assign entries to available benches.

    Algorithm:
    1. Find all QUEUED entries, sorted by priority DESC, requestedAt ASC
    2. Find all AVAILABLE benches
    3. For each queued entry, find a compatible bench (matching product)
    4. Assign entry to bench, update statuses

    Returns list of assignments made: [{"entryId": ..., "benchId": ..., "stage": ...}]
    """
    db = get_db_client()
    assignments = []

    # Get all queued entries, highest priority first
    queued = db.validationqueueentry.find_many(
        where={"status": "QUEUED"},
        order=[
            {"priority": "desc"},
            {"requestedAt": "asc"},
        ],
        include={
            "pipelineRun": True,
            "stageConfig": True,
        },
    )

    if not queued:
        return assignments

    # Get all available benches
    available_benches = db.testbench.find_many(
        where={"status": "AVAILABLE"},
    )

    if not available_benches:
        return assignments

    # Track which benches we've assigned in this round
    assigned_bench_ids: set = set()

    for entry in queued:
        if not entry.pipelineRun:
            continue

        product = entry.pipelineRun.product

        # Find a compatible bench (matches product, not already assigned this round)
        bench = None
        for b in available_benches:
            if b.id in assigned_bench_ids:
                continue
            if b.dutProduct == product:
                bench = b
                break

        if not bench:
            continue

        # Assign
        now = datetime.now(timezone.utc)
        try:
            db.validationqueueentry.update(
                where={"id": entry.id},
                data={
                    "status": "ASSIGNED",
                    "benchId": bench.id,
                    "assignedAt": now,
                },
            )

            # Lock the bench
            db.testbench.update(
                where={"id": bench.id},
                data={
                    "status": "LOCKED",
                    "lockedBy": f"queue:{entry.id}",
                    "lockedAt": now,
                },
            )

            assigned_bench_ids.add(bench.id)
            assignments.append({
                "entryId": entry.id,
                "benchId": bench.id,
                "stage": entry.stage,
                "product": product,
            })

            log_audit(
                "queue.assign",
                "ValidationQueueEntry",
                entry.id,
                {"benchId": bench.id, "stage": entry.stage, "priority": entry.priority},
            )

        except Exception as e:
            logger.error(f"Failed to assign queue entry {entry.id} to bench {bench.id}: {e}")
            continue

    if assignments:
        logger.info(f"Scheduler assigned {len(assignments)} queue entries to benches")

        # Auto-trigger K8s jobs for assignments
        for assignment in assignments:
            try:
                job_name = _trigger_validation_job(
                    db,
                    entry_id=assignment["entryId"],
                    bench_id=assignment["benchId"],
                    stage=assignment["stage"],
                    product=assignment["product"],
                )
                if job_name:
                    assignment["jobName"] = job_name
                    logger.info(f"Triggered K8s job {job_name} for queue entry {assignment['entryId']}")
            except Exception as e:
                logger.error(f"Failed to trigger K8s job for entry {assignment['entryId']}: {e}")

    return assignments


def on_build_complete(pipeline_run_id: str) -> Optional[str]:
    """Called when builds complete for a pipeline. Creates queue entry if ready.

    Returns the queue entry ID if created, None otherwise.
    """
    db = get_db_client()

    pipeline = db.pipelinerun.find_unique(
        where={"id": pipeline_run_id},
        include={
            "builds": True,
            "stageConfig": True,
        },
    )

    if not pipeline:
        return None

    # Check if all non-cancelled builds are complete
    builds = pipeline.builds or []
    active_builds = [b for b in builds if b.status not in ("CANCELLED",)]
    failed = [b for b in active_builds if b.status == "FAILED"]

    if failed:
        # Don't queue validation if any build failed
        return None

    # Check if we have pending builds still in progress
    pending = [b for b in active_builds if b.status in ("QUEUED", "BLOCKED", "BUILDING")]
    if pending:
        return None  # Still building

    # All builds done and successful -- check if stage needs a bench
    stage_config = pipeline.stageConfig if hasattr(pipeline, "stageConfig") else None
    if stage_config and not stage_config.requiresBench:
        return None  # Stage 1 (Smoke) doesn't need queue

    # Check if already queued
    existing = db.validationqueueentry.find_first(
        where={
            "pipelineRunId": pipeline_run_id,
            "status": {"in": ["QUEUED", "ASSIGNED", "RUNNING"]},
        },
    )
    if existing:
        return existing.id

    # Create queue entry
    priority = stage_config.priority if stage_config else 50
    stage = pipeline.stage or 4

    try:
        entry = db.validationqueueentry.create(
            data={
                "pipelineRunId": pipeline_run_id,
                "stageConfigId": pipeline.stageConfigId,
                "stage": stage,
                "priority": priority,
                "reason": f"Pipeline {pipeline.name or pipeline.id} builds complete",
            },
        )

        log_audit(
            "queue.create",
            "ValidationQueueEntry",
            entry.id,
            {"pipelineRunId": pipeline_run_id, "stage": stage, "priority": priority},
        )

        # Try to immediately assign
        schedule_queue()

        return entry.id

    except Exception as e:
        logger.error(f"Failed to create queue entry for pipeline {pipeline_run_id}: {e}")
        return None


def on_bench_freed(bench_id: str):
    """Called when a bench becomes available. Tries to assign next queued entry."""
    db = get_db_client()

    # Ensure bench is actually available
    bench = db.testbench.find_unique(where={"id": bench_id})
    if not bench or bench.status != "AVAILABLE":
        return

    # Run scheduler
    schedule_queue()
