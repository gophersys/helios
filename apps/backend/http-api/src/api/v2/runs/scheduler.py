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
    asset_set_id: Optional[str] = None,
    product_id: Optional[str] = None,
) -> Optional[str]:
    """Create a TestRun and RunTarget records for the queue entry.

    Returns the test run ID if successful, None otherwise.
    """
    # Look up product — prefer explicit product_id, fall back to build_run.product slug
    product_obj = None
    if product_id:
        product_obj = db.product.find_unique(where={"id": product_id})
    if not product_obj and build_run:
        product_obj = db.product.find_first(where={"slug": build_run.product})
    if not product_obj:
        logger.error("Product not found for validation run (entry %s)", entry_id[:8])
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
    run_data = {
        "type": "VALIDATION",
        "name": run_name,
        "productId": product_obj.id,
        "fixtureId": fixture.id,
        "testPackageId": test_package_id,
        "buildRunId": build_run.id if build_run else None,
        "assetSetId": asset_set_id,
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
    }
    # Populate board revision from the fixture
    if hasattr(fixture, "boardRevisionId") and fixture.boardRevisionId:
        run_data["boardRevisionId"] = fixture.boardRevisionId
    run = db.testrun.create(data=run_data)

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
            "assetSet": {"include": {"product": True, "buildRun": True}},
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

    if not entry or not entry.assetSet:
        logger.error(f"Queue entry {entry_id} not found or missing asset set")
        return None

    fixture = entry.fixture
    if not fixture:
        logger.error(f"Queue entry {entry_id} has no fixture assigned")
        return None

    asset_set = entry.assetSet
    build_run = asset_set.buildRun if hasattr(asset_set, "buildRun") else None
    stage_name = STAGE_NAMES.get(stage, "validation")

    # Resolve all active slots
    slot_infos = _resolve_all_slot_info(fixture)

    # Look up test package
    test_package_id = None
    test_package_version = "latest"
    product_slug = None
    product_id = asset_set.productId
    try:
        product_record = db.product.find_unique(where={"id": product_id})
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

    # AssetSet is already resolved from the queue entry
    asset_set_id = asset_set.id

    # Create TestRun + RunTargets
    run_id = _create_validation_run(
        db, entry_id, build_run, fixture, stage, stage_name,
        test_package_id=test_package_id,
        asset_set_id=asset_set_id,
        product_id=product_id,
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

    # Use product slug from asset set's product relation
    if not product_slug and asset_set.product:
        product_slug = asset_set.product.slug or asset_set.product.name.lower()

    # Compute fixture profile path from design
    fixture_profile_path = None
    if hasattr(fixture, "design") and fixture.design:
        fixture_profile_path = f"/app/fixtures/{fixture.design.product}_{fixture.design.revision}.json"

    # Dispatch via executor interface — DockerExecutor in dev, K8s Job in staging/prod
    from src.services.executors import get_executor
    from src.services.executors.kubernetes_executor import KubernetesExecutor

    executor = get_executor("validation")

    if isinstance(executor, KubernetesExecutor):
        # Staging/production: use existing K8s Job creation with full template
        job_name = create_kubernetes_job(
            product=product_slug,
            job_id=entry_id,
            firmware_path="",
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
            build_run_id=build_run.id if build_run else None,
            product_slug=product_slug,
            stage=stage_name,
            test_package_version=test_package_version,
            extra_env={
                "MTIB_HOSTS": mtib_hosts,
                "SLOT_SNRS": slot_snrs,
                "SLOT_DEVICE_IDS": slot_device_ids,
                "CONCORD_SESSION_ID": run_id,
                **({"ASSET_SET_ID": asset_set_id} if asset_set_id else {}),
            },
        )
    else:
        # Development: spawn test-runner container via Docker
        result = executor.submit(
            image=f"concord/test-runner:{env_config.ENVIRONMENT}",
            job_id=entry_id,
            env={
                "ENVIRONMENT": env_config.ENVIRONMENT,
                "STAGE": stage_name,
                "PRODUCT": product_slug or "",
                "CONCORD_API_URL": api_url,
                "CONCORD_RUN_ID": run_id,
                "CONCORD_SESSION_ID": run_id,
                "CONCORD_API_KEY": api_key,
                "CONCORD_API_HOST": env_config.CONCORD_API_HOST,
                "STORAGE_URL": env_config.STORAGE_URL,
                "STORAGE_ACCESS_KEY": env_config.STORAGE_ACCESS_KEY,
                "STORAGE_SECRET_ACCESS_KEY": env_config.STORAGE_SECRET_ACCESS_KEY,
                "STORAGE_BUCKET_NAME": env_config.STORAGE_BUCKET_NAME,
                "TEST_PACKAGE_VERSION": test_package_version or "latest",
                "MTIB_HOST": mtib_host,
                "MTIB_PORT": str(env_config.MTIB_PORT),
                "MTIB_HOSTS": mtib_hosts,
                "SLOT_SNRS": slot_snrs,
                "SLOT_DEVICE_IDS": slot_device_ids,
                "DEVICE_ID": dut_device_id or "",
                "DEVICE_SNR": dut_snr or "",
                "FIXTURE_ID": fixture.id,
                "BUILD_RUN_ID": build_run.id if build_run else "",
                **({"ASSET_SET_ID": asset_set_id} if asset_set_id else {}),
            },
            command=["/app/entrypoint.sh"],
            labels={"app": f"validation-{product_slug or 'unknown'}"},
            timeout_seconds=3600,
        )
        job_name = result.job_name if result.success else None

    if not job_name:
        logger.error(f"Failed to create job for queue entry {entry_id}")
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
        {"jobName": job_name, "stage": stage_name, "assetSetId": asset_set_id, "testRunId": run_id},
    )

    return job_name


def schedule_queue(max_assignments: Optional[int] = None) -> List[Dict[str, Any]]:
    """Process the validation queue and assign entries to available fixtures.

    Algorithm:
    1. Find all QUEUED entries, sorted by priority DESC, requestedAt ASC
    2. Find all AVAILABLE fixtures
    3. For each queued entry, find a compatible fixture (matching product)
    4. Assign entry to fixture, update statuses

    Args:
        max_assignments: Cap on number of assignments this tick (concurrency gate).
                         None means no cap beyond fixture availability.

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
            "assetSet": {"include": {"product": True}},
            "stageConfig": True,
        },
    )

    if not queued:
        return assignments

    # Get all available fixtures (include boardRevisionId for revision matching)
    available_fixtures = db.fixture.find_many(
        where={"status": "AVAILABLE", "active": True},
        include={"product": True, "boardRevision": True},
    )

    if not available_fixtures:
        return assignments

    # Track which fixtures we've assigned in this round
    assigned_fixture_ids: set = set()

    for entry in queued:
        # Concurrency cap: stop assigning once we hit the limit
        if max_assignments is not None and len(assignments) >= max_assignments:
            break

        if not entry.assetSet:
            continue

        asset_set = entry.assetSet
        product_slug = asset_set.product.slug if asset_set.product else None
        product_id = asset_set.productId

        # Look up the test package for revision matching
        test_package = None
        if product_id:
            test_package = db.testpackage.find_first(
                where={
                    "productId": product_id,
                    "type": "VALIDATION",
                    "status": "RELEASED",
                },
                order={"releasedAt": "desc"},
            )
            if not test_package:
                test_package = db.testpackage.find_first(
                    where={
                        "productId": product_id,
                        "type": "VALIDATION",
                    },
                    order={"createdAt": "desc"},
                )

        # Find a compatible fixture (matches product + board revision, not already assigned)
        fixture = None
        for f in available_fixtures:
            if f.id in assigned_fixture_ids:
                continue
            # Match by product slug via product relation
            if not (hasattr(f, "product") and f.product and f.product.slug == product_slug):
                continue
            # If test package specifies a board revision, ensure fixture matches
            tp_revision_id = getattr(test_package, "boardRevisionId", None) if test_package else None
            if tp_revision_id:
                if f.boardRevisionId != tp_revision_id:
                    continue  # Skip fixture with wrong revision
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
                "product": product_slug,
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
    """Called when builds complete for a build run. Creates queue entry if ready.

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

    # Resolve the AssetSet for this build run
    asset_set = db.assetset.find_first(where={"buildRunId": build_run_id})
    if not asset_set:
        logger.warning("No AssetSet for build run %s, cannot queue", build_run_id[:8])
        return None

    # Check if already queued
    existing = db.validationqueueentry.find_first(
        where={
            "assetSetId": asset_set.id,
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
                "assetSetId": asset_set.id,
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
            {"assetSetId": asset_set.id, "stage": stage, "priority": priority},
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
