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
    fixture,
    stage: int,
    stage_name: str,
) -> Optional[str]:
    """Create a Session and Device record for the queue entry.

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

    # Get DUT info from fixture's first active slot
    slots = fixture.slots if hasattr(fixture, "slots") and fixture.slots else []
    first_slot = slots[0] if slots else None
    device_snr = (first_slot.dutSnr if first_slot else None) or "UNKNOWN"
    dut_device_id = first_slot.dutDeviceId if first_slot else None

    # Derive MTIB address from slot's node
    mtib_address = None
    if first_slot and hasattr(first_slot, "node") and first_slot.node:
        mtib_address = f"{first_slot.node.ipAddress}:50053" if first_slot.node.ipAddress else None

    # Create session
    session = db.session.create(
        data={
            "name": session_name,
            "type": "VALIDATION",
            "productId": product_obj.id,
            "fixtureId": fixture.id,
            "pipelineRunId": pipeline.id,
            "createdById": system_user.id,
            "status": "ACTIVE",
            "targetCount": 1,
            "config": Json({
                "fixtureId": fixture.id,
                "stationId": fixture.stationId,
                "queueEntryId": entry_id,
                "stage": stage,
                "stageName": stage_name,
            }),
        },
    )

    # Create device record linked to session
    db.device.create(
        data={
            "serialNumber": device_snr,
            "sessionId": session.id,
            "status": "PENDING",
            "metadata": Json({
                "deviceId": dut_device_id,
                "fixtureId": fixture.id,
                "mtibAddress": mtib_address,
            }),
        },
    )

    logger.info(f"Created validation run {session.id} for queue entry {entry_id}")
    return session.id


def _trigger_validation_job(
    db,
    entry_id: str,
    fixture_id: str,
    stage: int,
    product: str,
) -> Optional[str]:
    """Create a K8s validation job for an assigned queue entry.

    Returns the job name if successful, None otherwise.
    """
    # Import here to avoid circular imports
    from src.api.v2.sessions.manual import create_kubernetes_job

    # Get full entry with relations
    entry = db.validationqueueentry.find_unique(
        where={"id": entry_id},
        include={
            "pipelineRun": True,
            "fixture": {
                "include": {
                    "slots": {
                        "where": {"active": True},
                        "order_by": {"slotIndex": "asc"},
                        "include": {"node": True},
                    },
                    "design": True,
                },
            },
        },
    )

    if not entry or not entry.pipelineRun:
        logger.error(f"Queue entry {entry_id} not found or missing pipeline")
        return None

    fixture = entry.fixture
    if not fixture:
        logger.error(f"Queue entry {entry_id} has no fixture assigned")
        return None

    pipeline = entry.pipelineRun

    # Stage name for K8s job (needed for session creation too)
    stage_name = STAGE_NAMES.get(stage, "validation")

    # Create Session record first
    run_id = _create_validation_run(db, entry_id, pipeline, fixture, stage, stage_name)
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

    # Get DUT info from fixture's first active slot
    slots = fixture.slots or []
    first_slot = slots[0] if slots else None

    # Extract MTIB address from slot's node
    mtib_host = ""
    if first_slot and hasattr(first_slot, "node") and first_slot.node:
        mtib_host = first_slot.node.ipAddress or ""

    dut_device_id = first_slot.dutDeviceId if first_slot else None
    dut_snr = first_slot.dutSnr if first_slot else None

    # Product slug for catalog lookup (pipeline.product is a string like "alpha_b0")
    product_slug = pipeline.product if hasattr(pipeline, "product") else None

    # Compute fixture profile path from design
    fixture_profile_path = None
    if hasattr(fixture, "design") and fixture.design:
        fixture_profile_path = f"/app/fixtures/{fixture.design.product}_{fixture.design.revision}.json"

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
        bench_id=fixture.id,
        device_id=dut_device_id,
        device_snr=dut_snr,
        fixture_profile_path=fixture_profile_path,
        pipeline_id=pipeline.id,
        product_slug=product_slug,
        stage=stage_name,
    )

    if not job_name:
        logger.error(f"Failed to create K8s job for queue entry {entry_id}")
        return None

    # Update entry status to RUNNING with job name and link session
    now = datetime.now(timezone.utc)
    db.validationqueueentry.update(
        where={"id": entry_id},
        data={
            "status": "RUNNING",
            "sessionId": run_id,
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

    # Get all available fixtures
    available_fixtures = db.fixture.find_many(
        where={"status": "AVAILABLE", "active": True},
        include={"product": True},
    )

    if not available_fixtures:
        return assignments

    # Track which fixtures we've assigned in this round
    assigned_fixture_ids: set = set()

    for entry in queued:
        if not entry.pipelineRun:
            continue

        product = entry.pipelineRun.product

        # Find a compatible fixture (matches product, not already assigned this round)
        fixture = None
        for f in available_fixtures:
            if f.id in assigned_fixture_ids:
                continue
            # Match by product slug via product relation
            if hasattr(f, "product") and f.product and f.product.slug == product:
                fixture = f
                break

        if not fixture:
            continue

        # Assign
        now = datetime.now(timezone.utc)
        try:
            db.validationqueueentry.update(
                where={"id": entry.id},
                data={
                    "status": "ASSIGNED",
                    "fixtureId": fixture.id,
                    "assignedAt": now,
                },
            )

            # Lock the fixture
            db.fixture.update(
                where={"id": fixture.id},
                data={
                    "status": "LOCKED",
                    "lockedBy": f"queue:{entry.id}",
                    "lockedAt": now,
                },
            )

            assigned_fixture_ids.add(fixture.id)
            assignments.append({
                "entryId": entry.id,
                "fixtureId": fixture.id,
                "stage": entry.stage,
                "product": product,
            })

            log_audit(
                "queue.assign",
                "ValidationQueueEntry",
                entry.id,
                {"fixtureId": fixture.id, "stage": entry.stage, "priority": entry.priority},
            )

        except Exception as e:
            logger.error(f"Failed to assign queue entry {entry.id} to fixture {fixture.id}: {e}")
            continue

    if assignments:
        logger.info(f"Scheduler assigned {len(assignments)} queue entries to fixtures")

        # Auto-trigger K8s jobs for assignments
        for assignment in assignments:
            try:
                job_name = _trigger_validation_job(
                    db,
                    entry_id=assignment["entryId"],
                    fixture_id=assignment["fixtureId"],
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


def on_fixture_freed(fixture_id: str):
    """Called when a fixture becomes available. Tries to assign next queued entry."""
    db = get_db_client()

    # Ensure fixture is actually available
    fixture = db.fixture.find_unique(where={"id": fixture_id})
    if not fixture or fixture.status != "AVAILABLE":
        return

    # Run scheduler
    schedule_queue()
