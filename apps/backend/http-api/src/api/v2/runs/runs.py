import logging
import math
from datetime import datetime, timezone

from database import Json
from flask import g, jsonify, request

from src.lib.audit import log_audit
from src.lib.decorators import require_permissions
from src.lib.errors import bad_request, conflict, internal_error, not_found
from src.lib.permissions import Permissions
from src.lib.types import ApiResponse
from src.services.database.prisma import get_db_client

from .types import CreateRunRequest, _serialize_execution, _serialize_run, _serialize_target
from .ws import emit_to_run, emit_to_mfg_session

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
#  POST /v2/runs — create a new test run
# ---------------------------------------------------------------------------

@require_permissions(Permissions.VALIDATION_RUN)
def create_run():
    """Create a new test run with a single RunTarget."""
    data, error = CreateRunRequest.from_json(request.get_json())
    if error:
        return bad_request(error)

    if data.type == "MANUFACTURING":
        return bad_request(
            "Manufacturing runs must be created through a ManufacturingSession"
        )

    db = get_db_client()

    # Validate product exists
    product = db.product.find_unique(where={"id": data.product_id})
    if not product:
        return not_found("Product not found")

    # Validate fixture — required for TestRun (fixtureId is NOT NULL)
    if not data.fixture_id:
        return bad_request("fixtureId is required")
    fixture = db.fixture.find_unique(where={"id": data.fixture_id})
    if not fixture:
        return not_found("Fixture not found")

    user_id = g.current_user["sub"]

    try:
        board_revision_id = getattr(fixture, "boardRevisionId", None)

        run = db.testrun.create(
            data={
                "type": data.type,
                "name": data.notes or f"Validation run",
                "productId": data.product_id,
                "fixtureId": data.fixture_id,
                "boardRevisionId": board_revision_id,
                "operatorId": user_id,
                "status": "PENDING",
                "targetCount": 1,
                "config": Json(data.config) if data.config else None,
                "notes": data.notes,
            },
            include={"product": True, "operator": True},
        )

        # Create a single RunTarget for the DUT
        target = db.runtarget.create(
            data={
                "runId": run.id,
                "slotIndex": 0,
                "serialNumber": data.serial_number,
                "status": "PENDING",
            },
        )

        log_audit("run.create", "TestRun", run.id, {
            "type": data.type,
            "productId": data.product_id,
            "fixtureId": data.fixture_id,
            "serialNumber": data.serial_number,
        })

        result = _serialize_run(run)
        result["targets"] = [_serialize_target(target)]

        return jsonify(ApiResponse.created(result).to_dict()), 201

    except Exception as e:
        logger.error("Failed to create run: %s", e)
        return internal_error("Failed to create run")


# ---------------------------------------------------------------------------
#  GET /v2/runs — paginated list
# ---------------------------------------------------------------------------

@require_permissions(Permissions.VALIDATION_VIEW)
def list_runs():
    """List test runs with pagination and optional filters."""
    db = get_db_client()

    page = max(1, request.args.get("page", 1, type=int))
    limit = min(max(1, request.args.get("limit", 20, type=int)), 100)
    skip = (page - 1) * limit

    where = {}

    run_type = request.args.get("type")
    if run_type:
        where["type"] = run_type.upper()

    status = request.args.get("status")
    if status:
        where["status"] = status.upper()

    product_id = request.args.get("productId")
    if product_id:
        where["productId"] = product_id

    total = db.testrun.count(where=where)
    runs = db.testrun.find_many(
        where=where,
        skip=skip,
        take=limit,
        order={"createdAt": "desc"},
        include={
            "product": True,
            "operator": True,
        },
    )

    return jsonify(ApiResponse.ok({
        "data": [_serialize_run(r) for r in runs],
        "pagination": {
            "page": page,
            "limit": limit,
            "total": total,
            "pages": math.ceil(total / limit) if limit > 0 else 0,
        },
    }).to_dict()), 200


# ---------------------------------------------------------------------------
#  GET /v2/runs/<run_id> — full detail
# ---------------------------------------------------------------------------

@require_permissions(Permissions.VALIDATION_VIEW)
def get_run(run_id: str):
    """Return a single test run with all nested relations."""
    db = get_db_client()

    run = db.testrun.find_unique(
        where={"id": run_id},
        include={
            "product": True,
            "fixture": True,
            "boardRevision": True,
            "testPackage": True,
            "buildRun": True,
            "assetSet": True,
            "operator": True,
            "targets": {
                "include": {
                    "executions": {
                        "include": {
                            "steps": True,
                        },
                        "order_by": {"executionIndex": "asc"},
                    },
                },
                "order_by": {"slotIndex": "asc"},
            },
        },
    )

    if not run:
        return not_found("Test run not found")

    return jsonify(ApiResponse.ok(_serialize_run(run, include_targets=True)).to_dict()), 200


# ---------------------------------------------------------------------------
#  POST /v2/runs/<run_id>/cancel
# ---------------------------------------------------------------------------

@require_permissions(Permissions.VALIDATION_MANAGE)
def cancel_run(run_id: str):
    """Cancel a pending or active test run."""
    db = get_db_client()

    run = db.testrun.find_unique(where={"id": run_id})
    if not run:
        return not_found("Test run not found")

    if run.status not in ("PENDING", "ACTIVE"):
        return conflict(f"Cannot cancel a run with status {run.status}")

    now = datetime.now(timezone.utc)

    try:
        # Cancel pending/running targets
        db.runtarget.update_many(
            where={
                "runId": run_id,
                "status": {"in": ["PENDING", "RUNNING"]},
            },
            data={"status": "ERROR", "completedAt": now},
        )

        # Cancel pending/running executions
        db.testexecution.update_many(
            where={
                "target": {"runId": run_id},
                "status": {"in": ["PENDING", "RUNNING"]},
            },
            data={"status": "FAILED", "completedAt": now},
        )

        # No fixture-unlocking write — when this run flips to CANCELLED
        # below, its fixture's derived lockState transitions from IN_USE
        # back to FREE automatically.

        # Update the run itself
        run = db.testrun.update(
            where={"id": run_id},
            data={
                "status": "CANCELLED",
                "completedAt": now,
            },
            include={
                "product": True,
                "operator": True,
                "targets": {
                    "include": {
                        "executions": {
                            "include": {"steps": True},
                            "order_by": {"executionIndex": "asc"},
                        },
                    },
                    "order_by": {"slotIndex": "asc"},
                },
            },
        )

        log_audit("run.cancel", "TestRun", run_id, {"previousStatus": "ACTIVE"})

        # Emit cancel events so the runner can kill the pytest subprocess
        emit_to_run("run_cancelled", {"runId": run_id}, run_id)

        # Also emit to the manufacturing session room if this is a mfg run
        if run.manufacturingSessionId:
            emit_to_mfg_session(
                "manufacturing_run_cancelled",
                {"runId": run_id, "sessionId": run.manufacturingSessionId},
                run.manufacturingSessionId,
            )

        return jsonify(ApiResponse.ok(_serialize_run(run, include_targets=True)).to_dict()), 200

    except Exception as e:
        logger.error("Failed to cancel run %s: %s", run_id, e)
        return internal_error("Failed to cancel run")


# ---------------------------------------------------------------------------
#  POST /v2/runs/<run_id>/rerun
# ---------------------------------------------------------------------------

@require_permissions(Permissions.VALIDATION_RUN)
def rerun_run(run_id: str):
    """Clone an existing run into a new PENDING run."""
    db = get_db_client()

    original = db.testrun.find_unique(
        where={"id": run_id},
        include={"product": True},
    )
    if not original:
        return not_found("Test run not found")

    user_id = g.current_user["sub"]

    try:
        original_config = original.config if isinstance(original.config, dict) else {}
        new_config = {**original_config, "rerunOf": run_id}

        new_run = db.testrun.create(
            data={
                "type": original.type,
                "name": f"Rerun of {original.name}" if original.name else "Rerun",
                "productId": original.productId,
                "fixtureId": original.fixtureId,
                "boardRevisionId": getattr(original, "boardRevisionId", None),
                "testPackageId": original.testPackageId,
                "buildRunId": original.buildRunId,
                "assetSetId": original.assetSetId,
                "operatorId": user_id,
                "status": "PENDING",
                "config": Json(new_config) if new_config else None,
                "notes": f"Rerun of {run_id}",
            },
            include={"product": True, "operator": True},
        )

        log_audit("run.rerun", "TestRun", new_run.id, {
            "originalRunId": run_id,
            "productId": original.productId,
        })

        return jsonify(ApiResponse.created(_serialize_run(new_run)).to_dict()), 201

    except Exception as e:
        logger.error("Failed to rerun run %s: %s", run_id, e)
        return internal_error("Failed to rerun run")


# ---------------------------------------------------------------------------
#  GET /v2/runs/<run_id>/targets
# ---------------------------------------------------------------------------

@require_permissions(Permissions.VALIDATION_VIEW)
def list_targets(run_id: str):
    """Return all RunTarget records for a given run."""
    db = get_db_client()

    run = db.testrun.find_unique(where={"id": run_id})
    if not run:
        return not_found("Test run not found")

    targets = db.runtarget.find_many(
        where={"runId": run_id},
        order={"slotIndex": "asc"},
        include={
            "executions": {
                "include": {"steps": True},
                "order_by": {"executionIndex": "asc"},
            },
        },
    )

    return jsonify(ApiResponse.ok({
        "data": [_serialize_target(t) for t in targets],
    }).to_dict()), 200


# ---------------------------------------------------------------------------
#  GET /v2/runs/<run_id>/executions
# ---------------------------------------------------------------------------

@require_permissions(Permissions.VALIDATION_VIEW)
def list_executions(run_id: str):
    """Return all TestExecution records across all targets in a run."""
    db = get_db_client()

    run = db.testrun.find_unique(where={"id": run_id})
    if not run:
        return not_found("Test run not found")

    page = max(1, request.args.get("page", 1, type=int))
    limit = min(max(1, request.args.get("limit", 50, type=int)), 100)
    skip = (page - 1) * limit

    where = {"target": {"runId": run_id}}

    total = db.testexecution.count(where=where)
    executions = db.testexecution.find_many(
        where=where,
        skip=skip,
        take=limit,
        order={"executionIndex": "asc"},
        include={"steps": True},
    )

    return jsonify(ApiResponse.ok({
        "data": [_serialize_execution(ex) for ex in executions],
        "pagination": {
            "page": page,
            "limit": limit,
            "total": total,
            "pages": math.ceil(total / limit) if limit > 0 else 0,
        },
    }).to_dict()), 200


# ---------------------------------------------------------------------------
#  POST /v2/runs/batch — batch action on multiple validation runs
# ---------------------------------------------------------------------------


@require_permissions(Permissions.VALIDATION_MANAGE)
def batch_runs_action():
    """Apply an action to multiple validation runs at once."""
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

    for rid in ids:
        run = db.testrun.find_unique(where={"id": rid})
        if not run:
            failed.append({"id": rid, "reason": "Not found"})
            continue

        if run.status not in ("PENDING", "ACTIVE"):
            failed.append({"id": rid, "reason": f"Cannot cancel run with status {run.status}"})
            continue

        now = datetime.now(timezone.utc)
        db.testrun.update(
            where={"id": rid},
            data={"status": "CANCELLED", "completedAt": now},
        )
        log_audit("validation.run.cancel", "TestRun", rid, {"batch": True})
        succeeded.append(rid)

    return jsonify(ApiResponse.ok({
        "action": action,
        "succeeded": succeeded,
        "failed": failed,
    }).to_dict()), 200
