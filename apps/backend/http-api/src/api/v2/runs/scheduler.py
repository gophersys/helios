"""Validation queue scheduler (TestRun/RunTarget models).

Assigns queued validation entries to available fixtures.
Called periodically or on events (build complete, fixture freed).
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
STAGE_NAMES = {1: "smoke", 2: "driver", 3: "integration", 4: "regression", 5: "fuota"}


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


def _resolve_all_slot_info(fixture):
    """Extract DUT info and node addresses from ALL active fixture slots.

    Returns a list of slot dicts with keys:
        slotIndex, slotId, dutSnr, dutDeviceId, nodeIp, nodeHostname
    """
    slots = fixture.slots if hasattr(fixture, "slots") and fixture.slots else []
    result = []
    for slot in slots:
        if not slot.active or not slot.nodeId:
            continue
        node = slot.node if hasattr(slot, "node") and slot.node else None
        if not node or not node.ipAddress:
            continue
        result.append({
            "slotIndex": slot.slotIndex,
            "slotId": slot.id,
            "dutSnr": slot.dutSnr or f"slot-{slot.slotIndex}",
            "dutDeviceId": slot.dutDeviceId,
            "nodeIp": node.ipAddress,
            "nodeHostname": getattr(node, "hostname", None),
        })
    return result


def _create_validation_run(
    db,
    entry_id: str,
    build_run,
    fixture,
    stage: int,
    stage_name: str,
    test_package_id: Optional[str] = None,
) -> Optional[str]:
    """Create a TestRun and RunTarget records for the queue entry.

    Returns the test run ID if successful, None otherwise.
    """
    # Look up product by slug
    product_obj = db.product.find_first(where={"slug": build_run.product})
    if not product_obj:
        logger.error(f"Product not found for slug: {build_run.product}")
        return None

    # Get system user ID
    system_user = db.user.find_first(where={"email": "system@concord.local"})
    if not system_user:
        system_user = db.user.find_first()
    if not system_user:
        logger.error("No users found in database for run creation")
        return None

    # Get all active slots
    slot_infos = _resolve_all_slot_info(fixture)
    if not slot_infos:
        logger.error(f"Fixture {fixture.id} has no active slots with assigned nodes")
        return None

    # Build run name
    short_id = entry_id[:8]
    run_name = f"Queue {short_id} - Stage {stage_name}"

    # Create TestRun
    run = db.testrun.create(
        data={
            "type": "VALIDATION",
            "name": run_name,
            "productId": product_obj.id,
            "fixtureId": fixture.id,
            "testPackageId": test_package_id,
            "buildRunId": build_run.id,
            "status": "ACTIVE",
            "operatorId": system_user.id,
            "targetCount": len(slot_infos),
            "config": Json({
                "fixtureId": fixture.id,
                "stationId": getattr(fixture, "stationId", None),
                "queueEntryId": entry_id,
                "stage": stage,
                "stageName": stage_name,
            }),
        },
    )

    # Create one RunTarget per active slot
    for slot_info in slot_infos:
        db.runtarget.create(
            data={
                "runId": run.id,
                "slotIndex": slot_info["slotIndex"],
                "slotId": slot_info["slotId"],
                "serialNumber": slot_info["dutSnr"],
                "deviceId": slot_info["dutDeviceId"],
                "status": "PENDING",
                "metadata": Json({
                    "nodeIp": slot_info["nodeIp"],
                    "nodeHostname": slot_info["nodeHostname"],
                    "fixtureSlotId": slot_info["slotId"],
                }),
            },
        )

    logger.info(
        "Created validation run %s with %d targets for queue entry %s",
        run.id, len(slot_infos), entry_id,
    )
    return run.id


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
    from src.api.v2.runs.manual import create_kubernetes_job

    # Get full entry with relations
    entry = db.validationqueueentry.find_unique(
        where={"id": entry_id},
        include={
            "buildRun": True,
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

    if not entry or not entry.buildRun:
        logger.error(f"Queue entry {entry_id} not found or missing build run")
        return None

    fixture = entry.fixture
    if not fixture:
        logger.error(f"Queue entry {entry_id} has no fixture assigned")
        return None

    build_run = entry.buildRun
    stage_name = STAGE_NAMES.get(stage, "validation")

    # Resolve all active slots
    slot_infos = _resolve_all_slot_info(fixture)

    # Look up test package
    test_package_id = None
    test_package_version = "latest"
    product_slug = None
    try:
        product_record = db.product.find_unique(where={"id": build_run.productId})
        if product_record:
            product_slug = product_record.slug or product_record.name.lower()
            latest_tp = db.testpackage.find_first(
                where={
                    "productId": product_record.id,
                    "type": "VALIDATION",
                    "status": "RELEASED",
                },
                order={"createdAt": "desc"},
            )
            if latest_tp:
                test_package_id = latest_tp.id
                test_package_version = latest_tp.version
                logger.info(
                    "Using test package %s@%s",
                    product_slug, test_package_version,
                )
            else:
                if env_config.ENVIRONMENT == "production":
                    logger.warning(
                        "No RELEASED validation test package for %s — refusing to use DEVELOPMENT in production",
                        product_slug,
                    )
                else:
                    dev_tp = db.testpackage.find_first(
                        where={
                            "productId": product_record.id,
                            "type": "VALIDATION",
                        },
                        order={"createdAt": "desc"},
                    )
                    if dev_tp:
                        test_package_id = dev_tp.id
                        test_package_version = dev_tp.version
                        logger.info(
                            "No RELEASED test package — using dev %s@%s",
                            product_slug, test_package_version,
                        )
    except Exception as e:
        logger.warning("Failed to look up test package: %s", e)

    # Create TestRun + RunTargets
    run_id = _create_validation_run(
        db, entry_id, build_run, fixture, stage, stage_name,
        test_package_id=test_package_id,
    )
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

    # Build multi-slot env vars (comma-separated)
    mtib_hosts = ",".join(f"{s['nodeIp']}:50053" for s in slot_infos) if slot_infos else ""
    slot_snrs = ",".join(s["dutSnr"] for s in slot_infos) if slot_infos else ""
    slot_device_ids = ",".join(s.get("dutDeviceId") or "" for s in slot_infos) if slot_infos else ""

    # For backward compat, also pass the first slot as single values
    first_slot = slot_infos[0] if slot_infos else {}
    mtib_host = first_slot.get("nodeIp", "")
    dut_device_id = first_slot.get("dutDeviceId")
    dut_snr = first_slot.get("dutSnr")

    # Use product slug from build_run if available
    if not product_slug and hasattr(build_run, "product") and build_run.product:
        product_slug = build_run.product

    # Compute fixture profile path from design
    fixture_profile_path = None
    if hasattr(fixture, "design") and fixture.design:
        fixture_profile_path = f"/app/fixtures/{fixture.design.product}_{fixture.design.revision}.json"

    # Create the K8s job with multi-slot env vars
    job_name = create_kubernetes_job(
        product=product,
        job_id=entry_id,
        firmware_path="",  # Pipeline-based tests fetch from MinIO
        test_type="validation",
        test_enable={},
        firmware_version="",
        run_id=run_id,
        api_key=api_key,
        api_url=api_url,
        mtib_address=mtib_host,
        bench_id=fixture.id,
        device_id=dut_device_id,
        device_snr=dut_snr,
        fixture_profile_path=fixture_profile_path,
        pipeline_id=build_run.id,
        product_slug=product_slug,
        stage=stage_name,
        test_package_version=test_package_version,
        extra_env={
            "MTIB_HOSTS": mtib_hosts,
            "SLOT_SNRS": slot_snrs,
            "SLOT_DEVICE_IDS": slot_device_ids,
            "CONCORD_SESSION_ID": run_id,
        },
    )

    if not job_name:
        logger.error(f"Failed to create K8s job for queue entry {entry_id}")
        return None

    # Update entry status to RUNNING with job name and link test run
    now = datetime.now(timezone.utc)
    db.validationqueueentry.update(
        where={"id": entry_id},
        data={
            "status": "RUNNING",
            "testRunId": run_id,
            "startedAt": now,
            "jobName": job_name,
        },
    )

    log_audit(
        "queue.trigger",
        "ValidationQueueEntry",
        entry_id,
        {"jobName": job_name, "stage": stage_name, "pipelineId": build_run.id, "testRunId": run_id},
    )

    return job_name


def schedule_queue() -> List[Dict[str, Any]]:
    """Process the validation queue and assign entries to available fixtures.

    Algorithm:
    1. Find all QUEUED entries, sorted by priority DESC, requestedAt ASC
    2. Find all AVAILABLE fixtures
    3. For each queued entry, find a compatible fixture (matching product)
    4. Assign entry to fixture, update statuses

    Returns list of assignments made: [{"entryId": ..., "fixtureId": ..., "stage": ...}]
    """
    db = get_db_client()
    assignments: list = []

    # Get all queued entries, highest priority first
    queued = db.validationqueueentry.find_many(
        where={"status": "QUEUED"},
        order=[
            {"priority": "desc"},
            {"requestedAt": "asc"},
        ],
        include={
            "buildRun": True,
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
        if not entry.buildRun:
            continue

        product = entry.buildRun.product

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


def on_build_complete(build_run_id: str) -> Optional[str]:
    """Called when builds complete for a pipeline. Creates queue entry if ready.

    Returns the queue entry ID if created, None otherwise.
    """
    db = get_db_client()

    build_run = db.buildrun.find_unique(
        where={"id": build_run_id},
        include={
            "builds": True,
            "stageConfig": True,
        },
    )

    if not build_run:
        return None

    # Check if all non-cancelled builds are complete
    builds = build_run.builds or []
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
    stage_config = build_run.stageConfig if hasattr(build_run, "stageConfig") else None
    if stage_config and not stage_config.requiresBench:
        return None  # Stage 1 (Smoke) doesn't need queue

    # Check if already queued
    existing = db.validationqueueentry.find_first(
        where={
            "buildRunId": build_run_id,
            "status": {"in": ["QUEUED", "ASSIGNED", "RUNNING"]},
        },
    )
    if existing:
        return existing.id

    # Create queue entry
    priority = stage_config.priority if stage_config else 50
    stage = getattr(build_run, "stage", None) or (stage_config.stage if stage_config else 4)

    try:
        entry = db.validationqueueentry.create(
            data={
                "buildRunId": build_run_id,
                "stageConfigId": getattr(build_run, "stageConfigId", None),
                "stage": stage,
                "priority": priority,
                "reason": f"Build run {build_run.id} complete — all builds SUCCESS",
            },
        )

        log_audit(
            "queue.create",
            "ValidationQueueEntry",
            entry.id,
            {"buildRunId": build_run_id, "stage": stage, "priority": priority},
        )

        # Try to immediately assign
        schedule_queue()

        return entry.id

    except Exception as e:
        logger.error(f"Failed to create queue entry for build run {build_run_id}: {e}")
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
