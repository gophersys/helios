"""Validation queue — manages PENDING entries waiting for fixture availability.

When a build run triggers validation but all fixtures are locked, a queue entry
is created instead of failing silently.  When a run finishes or is cancelled
and the fixture is released, ``process_queue()`` picks the next PENDING entry
and starts it.
"""

import logging
import math
from datetime import datetime, timezone

from flask import jsonify, request

from src.lib.audit import log_audit
from src.lib.decorators import require_permissions
from src.lib.errors import bad_request, conflict, not_found
from src.lib.permissions import Permissions
from src.lib.types import ApiResponse
from src.services.database.prisma import get_db_client

logger = logging.getLogger(__name__)


# -------------------------------------------------------------------
#                            Serializers
# -------------------------------------------------------------------

def _serialize_queue_entry(entry) -> dict:
    """Serialize a ValidationQueueEntry DB record to an API response dict."""
    data = {
        "id": entry.id,
        "assetSetId": entry.assetSetId,
        "stageConfigId": entry.stageConfigId,
        "stage": entry.stage,
        "priority": entry.priority,
        "status": entry.status,
        "fixtureId": entry.fixtureId,
        "testRunId": entry.testRunId,
        "reason": entry.reason,
        "errorMessage": entry.errorMessage,
        "jobName": entry.jobName,
        "requestedAt": entry.requestedAt.isoformat() if entry.requestedAt else None,
        "assignedAt": entry.assignedAt.isoformat() if entry.assignedAt else None,
        "startedAt": entry.startedAt.isoformat() if entry.startedAt else None,
        "completedAt": entry.completedAt.isoformat() if entry.completedAt else None,
        "createdAt": entry.createdAt.isoformat(),
        "updatedAt": entry.updatedAt.isoformat(),
    }
    if hasattr(entry, "assetSet") and entry.assetSet is not None:
        a = entry.assetSet
        product_name = None
        if hasattr(a, "product") and a.product and hasattr(a.product, "name"):
            product_name = a.product.name
        elif hasattr(a, "product") and isinstance(a.product, str):
            product_name = a.product
        data["assetSet"] = {
            "id": a.id,
            "name": getattr(a, "name", None),
            "product": product_name,
            "status": a.status,
        }
    if hasattr(entry, "fixture") and entry.fixture is not None:
        f = entry.fixture
        data["fixture"] = {
            "id": f.id,
            "name": f.name,
            "stationId": getattr(f, "stationId", None),
            "status": f.status,
        }
    if hasattr(entry, "testRun") and entry.testRun is not None:
        r = entry.testRun
        data["testRun"] = {"id": r.id, "name": r.name, "status": r.status}
    return data


# -------------------------------------------------------------------
#                        Internal: process_queue
# -------------------------------------------------------------------

def process_queue(db=None) -> dict:
    """Try to start the next PENDING queue entry.

    Finds the highest-priority oldest PENDING entry and attempts to
    trigger validation via ``trigger_build_run_validation``.

    Returns a summary dict (for logging / HTTP response).
    """
    if db is None:
        db = get_db_client()

    # Find oldest PENDING entry (FIFO within same priority, highest priority first)
    entry = db.validationqueueentry.find_first(
        where={"status": "QUEUED"},
        order=[
            {"priority": "desc"},
            {"requestedAt": "asc"},
        ],
        include={"assetSet": {"include": {"product": True, "buildRun": {"include": {"builds": True}}}}},
    )

    if not entry:
        return {"processed": False, "reason": "No pending entries"}

    # Verify the asset set still exists
    asset_set = entry.assetSet
    if not asset_set:
        db.validationqueueentry.update(
            where={"id": entry.id},
            data={
                "status": "FAILED",
                "errorMessage": "Asset set no longer exists",
                "completedAt": datetime.now(timezone.utc),
            },
        )
        return {"processed": False, "reason": "Asset set not found", "entryId": entry.id}

    if asset_set.status == "PENDING":
        db.validationqueueentry.update(
            where={"id": entry.id},
            data={
                "status": "FAILED",
                "errorMessage": "Asset set is not ready (status: PENDING)",
                "completedAt": datetime.now(timezone.utc),
            },
        )
        return {"processed": False, "reason": "Asset set not ready", "entryId": entry.id}

    # Check if there's a build run attached (build-service origin)
    build_run = asset_set.buildRun if hasattr(asset_set, "buildRun") else None

    if build_run:
        builds = build_run.builds or []
        if not builds:
            db.validationqueueentry.update(
                where={"id": entry.id},
                data={
                    "status": "FAILED",
                    "errorMessage": "Build run has no builds",
                    "completedAt": datetime.now(timezone.utc),
                },
            )
            return {"processed": False, "reason": "No builds", "entryId": entry.id}

        # Re-fetch with full includes needed by trigger_build_run_validation
        build_run = db.buildrun.find_unique(
            where={"id": build_run.id},
            include={"builds": {"include": {"product": True}}, "product": True},
        )
        if not build_run:
            db.validationqueueentry.update(
                where={"id": entry.id},
                data={
                    "status": "FAILED",
                    "errorMessage": "Build run not found on re-fetch",
                    "completedAt": datetime.now(timezone.utc),
                },
            )
            return {"processed": False, "reason": "Build run not found", "entryId": entry.id}

        builds = build_run.builds or []

        # Mark as RUNNING *before* triggering to prevent re-entry from the same entry
        db.validationqueueentry.update(
            where={"id": entry.id},
            data={"status": "RUNNING", "startedAt": datetime.now(timezone.utc)},
        )

        # Attempt to trigger — this will find an available fixture (or return None/queued)
        from src.services.build_run_service import trigger_build_run_validation

        result = trigger_build_run_validation(build_run.id, build_run, builds)
    else:
        # External CI / manual upload — no build run attached
        logger.warning(
            "Queue entry %s has asset set %s with no build run — direct asset-set validation not yet implemented",
            str(entry.id)[:8], str(entry.assetSetId)[:8],
        )
        db.validationqueueentry.update(
            where={"id": entry.id},
            data={
                "status": "FAILED",
                "errorMessage": "Direct asset-set validation triggering not yet implemented",
                "completedAt": datetime.now(timezone.utc),
            },
        )
        return {"processed": False, "reason": "No build run on asset set", "entryId": entry.id}

    if result is None or (isinstance(result, dict) and result.get("queued")):
        # Still no fixture available — revert to QUEUED
        db.validationqueueentry.update(
            where={"id": entry.id},
            data={"status": "QUEUED", "startedAt": None},
        )
        return {"processed": False, "reason": "No fixture available", "entryId": entry.id}

    # Extract testRunId from result dict
    test_run_id: str = str(result.get("testRunId", "") or result.get("sessionId", "")) if isinstance(result, dict) else str(result)

    # Success — update queue entry with test run
    now = datetime.now(timezone.utc)
    db.validationqueueentry.update(
        where={"id": entry.id},
        data={
            "status": "RUNNING",
            "testRunId": test_run_id,
            "startedAt": now,
        },
    )

    # Update build run status (if build run exists)
    if build_run:
        db.buildrun.update(
            where={"id": build_run.id},
            data={"status": "VALIDATING", "validationRunId": test_run_id},
        )

    logger.info(
        "Queue entry %s started: assetSet=%s testRun=%s",
        str(entry.id)[:8], str(entry.assetSetId)[:8], test_run_id[:8],
    )

    return {
        "processed": True,
        "entryId": entry.id,
        "testRunId": test_run_id,
        "assetSetId": entry.assetSetId,
    }


# -------------------------------------------------------------------
#                          HTTP Endpoints
# -------------------------------------------------------------------

@require_permissions(Permissions.VALIDATION_VIEW)
def list_queue():
    """GET /v2/runs/queue — List queue entries ordered by priority then requestedAt."""
    db = get_db_client()

    page = max(1, request.args.get("page", 1, type=int))
    limit = min(max(1, request.args.get("limit", 50, type=int)), 100)
    skip = (page - 1) * limit

    # Optional status filter
    where = {}
    status = request.args.get("status")
    if status:
        where["status"] = status.upper()

    total = db.validationqueueentry.count(where=where)
    entries = db.validationqueueentry.find_many(
        where=where,
        skip=skip,
        take=limit,
        order=[
            {"priority": "desc"},
            {"requestedAt": "asc"},
        ],
        include={
            "assetSet": {"include": {"product": True}},
            "fixture": True,
            "testRun": True,
        },
    )

    return jsonify(ApiResponse.ok({
        "data": [_serialize_queue_entry(e) for e in entries],
        "pagination": {
            "page": page,
            "limit": limit,
            "total": total,
            "pages": math.ceil(total / limit) if limit > 0 else 0,
        },
    }).to_dict()), 200


@require_permissions(Permissions.VALIDATION_VIEW)
def get_queue_entry(entry_id: str):
    """GET /v2/runs/queue/<id> — Get a single queue entry."""
    db = get_db_client()

    entry = db.validationqueueentry.find_unique(
        where={"id": entry_id},
        include={
            "assetSet": {"include": {"product": True}},
            "fixture": True,
            "testRun": True,
        },
    )
    if not entry:
        return not_found("Queue entry not found")

    return jsonify(ApiResponse.ok(_serialize_queue_entry(entry)).to_dict()), 200


@require_permissions(Permissions.VALIDATION_MANAGE)
def create_queue_entry():
    """POST /v2/runs/queue — Manually enqueue a build run for validation."""
    db = get_db_client()

    data = request.get_json()
    if not data:
        return bad_request("Request body required")

    asset_set_id = (data.get("assetSetId") or "").strip()
    if not asset_set_id:
        return bad_request("assetSetId is required")

    asset_set = db.assetset.find_unique(where={"id": asset_set_id})
    if not asset_set:
        return not_found("Asset set not found")

    # Check for existing QUEUED entry for this asset set
    existing = db.validationqueueentry.find_first(
        where={"assetSetId": asset_set_id, "status": "QUEUED"},
    )
    if existing:
        return conflict("Asset set already has a pending queue entry")

    stage = data.get("stage", 4)
    priority = data.get("priority", 0)
    reason = data.get("reason")

    entry = db.validationqueueentry.create(
        data={
            "assetSetId": asset_set_id,
            "stage": stage,
            "priority": priority,
            "status": "QUEUED",
            "reason": reason,
            "requestedAt": datetime.now(timezone.utc),
        },
        include={"assetSet": True},
    )

    log_audit("validation.queue.create", "ValidationQueueEntry", entry.id, {
        "assetSetId": asset_set_id,
        "stage": stage,
        "priority": priority,
        "reason": reason,
    })

    return jsonify(ApiResponse.created(_serialize_queue_entry(entry)).to_dict()), 201


@require_permissions(Permissions.VALIDATION_MANAGE)
def update_queue_entry(entry_id: str):
    """PATCH /v2/runs/queue/<id> — Update priority or reason."""
    db = get_db_client()

    entry = db.validationqueueentry.find_unique(where={"id": entry_id})
    if not entry:
        return not_found("Queue entry not found")

    if entry.status != "QUEUED":
        return conflict(f"Cannot update entry with status {entry.status}")

    data = request.get_json() or {}
    update_data = {}
    if "priority" in data:
        update_data["priority"] = int(data["priority"])
    if "reason" in data:
        update_data["reason"] = data["reason"]

    if not update_data:
        return bad_request("No fields to update")

    entry = db.validationqueueentry.update(
        where={"id": entry_id},
        data=update_data,
        include={"assetSet": True, "fixture": True, "testRun": True},
    )

    log_audit("validation.queue.update", "ValidationQueueEntry", entry_id, update_data)

    return jsonify(ApiResponse.ok(_serialize_queue_entry(entry)).to_dict()), 200


@require_permissions(Permissions.VALIDATION_MANAGE)
def cancel_queue_entry(entry_id: str):
    """POST /v2/runs/queue/<id>/cancel — Cancel a pending queue entry."""
    db = get_db_client()

    entry = db.validationqueueentry.find_unique(where={"id": entry_id})
    if not entry:
        return not_found("Queue entry not found")

    if entry.status not in ("QUEUED",):
        return conflict(f"Cannot cancel entry with status {entry.status}")

    entry = db.validationqueueentry.update(
        where={"id": entry_id},
        data={
            "status": "CANCELLED",
            "completedAt": datetime.now(timezone.utc),
        },
        include={"assetSet": True, "fixture": True, "testRun": True},
    )

    log_audit("validation.queue.cancel", "ValidationQueueEntry", entry_id, {
        "assetSetId": entry.assetSetId,
    })

    return jsonify(ApiResponse.ok(_serialize_queue_entry(entry)).to_dict()), 200


@require_permissions(Permissions.VALIDATION_MANAGE)
def promote_queue_entry(entry_id: str):
    """POST /v2/runs/queue/<id>/promote — Bump priority to maximum + 1."""
    db = get_db_client()

    entry = db.validationqueueentry.find_unique(where={"id": entry_id})
    if not entry:
        return not_found("Queue entry not found")

    if entry.status != "QUEUED":
        return conflict(f"Cannot promote entry with status {entry.status}")

    # Find the current max priority among QUEUED entries
    top = db.validationqueueentry.find_first(
        where={"status": "QUEUED"},
        order={"priority": "desc"},
    )
    new_priority = (top.priority + 1) if top else 1

    entry = db.validationqueueentry.update(
        where={"id": entry_id},
        data={"priority": new_priority},
        include={"assetSet": True, "fixture": True, "testRun": True},
    )

    log_audit("validation.queue.promote", "ValidationQueueEntry", entry_id, {
        "newPriority": new_priority,
    })

    return jsonify(ApiResponse.ok(_serialize_queue_entry(entry)).to_dict()), 200


@require_permissions(Permissions.VALIDATION_MANAGE)
def demote_queue_entry(entry_id: str):
    """POST /v2/runs/queue/<id>/demote — Drop priority to minimum - 1 (floor 0)."""
    db = get_db_client()

    entry = db.validationqueueentry.find_unique(where={"id": entry_id})
    if not entry:
        return not_found("Queue entry not found")

    if entry.status != "QUEUED":
        return conflict(f"Cannot demote entry with status {entry.status}")

    # Find the current min priority among QUEUED entries
    bottom = db.validationqueueentry.find_first(
        where={"status": "QUEUED"},
        order={"priority": "asc"},
    )
    new_priority = max(0, (bottom.priority - 1) if bottom else 0)

    entry = db.validationqueueentry.update(
        where={"id": entry_id},
        data={"priority": new_priority},
        include={"assetSet": True, "fixture": True, "testRun": True},
    )

    log_audit("validation.queue.demote", "ValidationQueueEntry", entry_id, {
        "newPriority": new_priority,
    })

    return jsonify(ApiResponse.ok(_serialize_queue_entry(entry)).to_dict()), 200


@require_permissions(Permissions.VALIDATION_VIEW)
def get_queue_stats():
    """GET /v2/runs/queue/stats — Summary counts by status."""
    db = get_db_client()

    queued = db.validationqueueentry.count(where={"status": "QUEUED"})
    running = db.validationqueueentry.count(where={"status": "RUNNING"})
    completed = db.validationqueueentry.count(where={"status": "COMPLETED"})
    failed = db.validationqueueentry.count(where={"status": "FAILED"})
    cancelled = db.validationqueueentry.count(where={"status": "CANCELLED"})

    return jsonify(ApiResponse.ok({
        "queued": queued,
        "running": running,
        "completed": completed,
        "failed": failed,
        "cancelled": cancelled,
        "total": queued + running + completed + failed + cancelled,
    }).to_dict()), 200


@require_permissions(Permissions.VALIDATION_MANAGE)
def trigger_scheduler():
    """POST /v2/runs/queue/schedule — Manually process the queue."""
    try:
        result = process_queue()
        log_audit("validation.queue.schedule", "ValidationQueueEntry", result.get("entryId"), {
            "result": result,
        })
        return jsonify(ApiResponse.ok(result).to_dict()), 200
    except Exception as e:
        logger.error("Queue scheduler failed: %s", e)
        return jsonify(ApiResponse.ok({
            "processed": False,
            "reason": f"Scheduler error: {e}",
        }).to_dict()), 200


# ---------------------------------------------------------------------------
#  POST /v2/runs/queue/batch — batch action on multiple queue entries
# ---------------------------------------------------------------------------


@require_permissions(Permissions.VALIDATION_MANAGE)
def batch_queue_action():
    """Apply an action to multiple validation queue entries at once."""
    db = get_db_client()
    body = request.get_json()
    if not body:
        return bad_request("Request body required")

    action = (body.get("action") or "").strip().lower()
    ids = body.get("ids", [])

    if action not in ("cancel",):
        return bad_request("action must be 'cancel'")
    if not isinstance(ids, list) or not ids:
        return bad_request("ids must be a non-empty array")

    succeeded = []
    failed = []

    for eid in ids:
        entry = db.validationqueueentry.find_unique(where={"id": eid})
        if not entry:
            failed.append({"id": eid, "reason": "Not found"})
            continue

        if entry.status != "QUEUED":
            failed.append({"id": eid, "reason": f"Cannot cancel entry with status {entry.status}"})
            continue

        db.validationqueueentry.update(
            where={"id": eid},
            data={
                "status": "CANCELLED",
                "completedAt": datetime.now(timezone.utc),
            },
        )
        log_audit("validation.queue.cancel", "ValidationQueueEntry", eid, {"batch": True})
        succeeded.append(eid)

    return jsonify(ApiResponse.ok({
        "action": action,
        "succeeded": succeeded,
        "failed": failed,
    }).to_dict()), 200
