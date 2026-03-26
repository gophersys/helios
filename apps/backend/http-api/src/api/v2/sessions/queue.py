"""Validation queue — manages PENDING entries waiting for fixture availability.

When a pipeline triggers validation but all fixtures are locked, a queue entry
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
    data = {
        "id": entry.id,
        "pipelineRunId": entry.pipelineRunId,
        "stageConfigId": entry.stageConfigId,
        "stage": entry.stage,
        "priority": entry.priority,
        "status": entry.status,
        "fixtureId": entry.fixtureId,
        "sessionId": entry.sessionId,
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
    if hasattr(entry, "pipelineRun") and entry.pipelineRun is not None:
        p = entry.pipelineRun
        data["pipelineRun"] = {
            "id": p.id,
            "name": p.name,
            "product": p.product,
            "branch": p.branch,
            "status": p.status,
        }
    if hasattr(entry, "fixture") and entry.fixture is not None:
        f = entry.fixture
        data["fixture"] = {"id": f.id, "name": f.name, "status": f.status}
    if hasattr(entry, "session") and entry.session is not None:
        s = entry.session
        data["session"] = {"id": s.id, "name": s.name, "status": s.status}
    return data


# -------------------------------------------------------------------
#                        Internal: process_queue
# -------------------------------------------------------------------

def process_queue(db=None) -> dict:
    """Try to start the next PENDING queue entry.

    Finds the highest-priority oldest PENDING entry and attempts to
    trigger validation via ``trigger_pipeline_validation``.

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
        include={"pipelineRun": {"include": {"builds": True}}},
    )

    if not entry:
        return {"processed": False, "reason": "No pending entries"}

    # Verify the pipeline still exists and has builds
    pipeline = entry.pipelineRun
    if not pipeline:
        db.validationqueueentry.update(
            where={"id": entry.id},
            data={
                "status": "FAILED",
                "errorMessage": "Pipeline no longer exists",
                "completedAt": datetime.now(timezone.utc),
            },
        )
        return {"processed": False, "reason": "Pipeline deleted", "entryId": entry.id}

    builds = pipeline.builds or []
    if not builds:
        db.validationqueueentry.update(
            where={"id": entry.id},
            data={
                "status": "FAILED",
                "errorMessage": "Pipeline has no builds",
                "completedAt": datetime.now(timezone.utc),
            },
        )
        return {"processed": False, "reason": "No builds", "entryId": entry.id}

    # Re-fetch pipeline with full includes needed by trigger_pipeline_validation
    pipeline = db.pipelinerun.find_unique(
        where={"id": entry.pipelineRunId},
        include={"builds": {"include": {"product": True}}, "product": True},
    )
    if not pipeline:
        db.validationqueueentry.update(
            where={"id": entry.id},
            data={
                "status": "FAILED",
                "errorMessage": "Pipeline not found on re-fetch",
                "completedAt": datetime.now(timezone.utc),
            },
        )
        return {"processed": False, "reason": "Pipeline not found", "entryId": entry.id}

    builds = pipeline.builds or []

    # Mark as RUNNING *before* triggering to prevent re-entry from the same entry
    db.validationqueueentry.update(
        where={"id": entry.id},
        data={"status": "RUNNING", "startedAt": datetime.now(timezone.utc)},
    )

    # Attempt to trigger — this will find an available fixture (or return None/queued)
    from src.services.pipeline_service import trigger_pipeline_validation

    result = trigger_pipeline_validation(entry.pipelineRunId, pipeline, builds)

    if result is None or (isinstance(result, dict) and result.get("queued")):
        # Still no fixture available — revert to QUEUED
        db.validationqueueentry.update(
            where={"id": entry.id},
            data={"status": "QUEUED", "startedAt": None},
        )
        return {"processed": False, "reason": "No fixture available", "entryId": entry.id}

    # Extract sessionId from result dict
    session_id = result.get("sessionId") if isinstance(result, dict) else result

    # Success — update queue entry with session
    now = datetime.now(timezone.utc)
    db.validationqueueentry.update(
        where={"id": entry.id},
        data={
            "status": "RUNNING",
            "sessionId": session_id,
            "startedAt": now,
        },
    )

    # Update pipeline status
    db.pipelinerun.update(
        where={"id": entry.pipelineRunId},
        data={"status": "VALIDATING", "validationRunId": run_id},
    )

    logger.info(
        "Queue entry %s started: pipeline=%s session=%s",
        entry.id[:8], entry.pipelineRunId[:8], run_id[:8],
    )

    return {
        "processed": True,
        "entryId": entry.id,
        "sessionId": run_id,
        "pipelineRunId": entry.pipelineRunId,
    }


# -------------------------------------------------------------------
#                          HTTP Endpoints
# -------------------------------------------------------------------

@require_permissions(Permissions.VALIDATION_VIEW)
def list_queue():
    """GET /v2/sessions/queue — List queue entries ordered by priority then requestedAt."""
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
            "pipelineRun": True,
            "fixture": True,
            "session": True,
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
    """GET /v2/sessions/queue/<id> — Get a single queue entry."""
    db = get_db_client()

    entry = db.validationqueueentry.find_unique(
        where={"id": entry_id},
        include={
            "pipelineRun": True,
            "fixture": True,
            "session": True,
        },
    )
    if not entry:
        return not_found("Queue entry not found")

    return jsonify(ApiResponse.ok(_serialize_queue_entry(entry)).to_dict()), 200


@require_permissions(Permissions.VALIDATION_MANAGE)
def create_queue_entry():
    """POST /v2/sessions/queue — Manually enqueue a pipeline for validation."""
    db = get_db_client()

    data = request.get_json()
    if not data:
        return bad_request("Request body required")

    pipeline_run_id = (data.get("pipelineRunId") or "").strip()
    if not pipeline_run_id:
        return bad_request("pipelineRunId is required")

    pipeline = db.pipelinerun.find_unique(where={"id": pipeline_run_id})
    if not pipeline:
        return not_found("Pipeline not found")

    # Check for existing QUEUED entry for this pipeline
    existing = db.validationqueueentry.find_first(
        where={"pipelineRunId": pipeline_run_id, "status": "QUEUED"},
    )
    if existing:
        return conflict("Pipeline already has a pending queue entry")

    stage = data.get("stage", 4)
    priority = data.get("priority", 0)
    reason = data.get("reason")

    entry = db.validationqueueentry.create(
        data={
            "pipelineRunId": pipeline_run_id,
            "stage": stage,
            "priority": priority,
            "status": "QUEUED",
            "reason": reason,
            "requestedAt": datetime.now(timezone.utc),
        },
        include={"pipelineRun": True},
    )

    log_audit("validation.queue.create", "ValidationQueueEntry", entry.id, {
        "pipelineRunId": pipeline_run_id,
        "stage": stage,
        "priority": priority,
        "reason": reason,
    })

    return jsonify(ApiResponse.created(_serialize_queue_entry(entry)).to_dict()), 201


@require_permissions(Permissions.VALIDATION_MANAGE)
def update_queue_entry(entry_id: str):
    """PATCH /v2/sessions/queue/<id> — Update priority or reason."""
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
        include={"pipelineRun": True, "fixture": True, "session": True},
    )

    log_audit("validation.queue.update", "ValidationQueueEntry", entry_id, update_data)

    return jsonify(ApiResponse.ok(_serialize_queue_entry(entry)).to_dict()), 200


@require_permissions(Permissions.VALIDATION_MANAGE)
def cancel_queue_entry(entry_id: str):
    """POST /v2/sessions/queue/<id>/cancel — Cancel a pending queue entry."""
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
        include={"pipelineRun": True, "fixture": True, "session": True},
    )

    log_audit("validation.queue.cancel", "ValidationQueueEntry", entry_id, {
        "pipelineRunId": entry.pipelineRunId,
    })

    return jsonify(ApiResponse.ok(_serialize_queue_entry(entry)).to_dict()), 200


@require_permissions(Permissions.VALIDATION_MANAGE)
def promote_queue_entry(entry_id: str):
    """POST /v2/sessions/queue/<id>/promote — Bump priority to maximum + 1."""
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
        include={"pipelineRun": True, "fixture": True, "session": True},
    )

    log_audit("validation.queue.promote", "ValidationQueueEntry", entry_id, {
        "newPriority": new_priority,
    })

    return jsonify(ApiResponse.ok(_serialize_queue_entry(entry)).to_dict()), 200


@require_permissions(Permissions.VALIDATION_VIEW)
def get_queue_stats():
    """GET /v2/sessions/queue/stats — Summary counts by status."""
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
    """POST /v2/sessions/queue/schedule — Manually process the queue."""
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
