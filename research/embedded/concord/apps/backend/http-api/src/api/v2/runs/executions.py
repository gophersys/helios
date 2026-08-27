"""Execution listing and detail endpoints for test runs.

Endpoints:
  GET /v2/runs/<id>/executions                — Paginated execution list
  GET /v2/runs/<id>/executions/<eid>/results  — Execution detail with steps
"""
import logging
import math

from flask import jsonify, request

from src.lib.decorators import require_permissions
from src.lib.errors import not_found
from src.lib.permissions import Permissions
from src.lib.types import ApiResponse
from src.services.database.prisma import get_db_client

from .types import _serialize_execution, _serialize_step

logger = logging.getLogger(__name__)


def _get_run_or_404(run_id: str):
    """Look up a TestRun by ID, returning (run, None) or (None, 404 response)."""
    db = get_db_client()
    run = db.testrun.find_unique(where={"id": run_id})
    if not run:
        return None, not_found(f"Run {run_id} not found")
    return run, None


@require_permissions(Permissions.VALIDATION_VIEW)
def list_executions(run_id: str):
    """GET /v2/runs/<id>/executions — All test executions for a run."""
    db = get_db_client()

    run, err = _get_run_or_404(run_id)
    if err:
        return err

    page = max(1, request.args.get("page", 1, type=int))
    limit = min(max(1, request.args.get("limit", 50, type=int)), 100)
    skip = (page - 1) * limit

    # Filter executions that belong to targets in this run
    where = {"target": {"runId": run_id}}

    status = request.args.get("status")
    if status:
        where["status"] = status.upper()

    total = db.testexecution.count(where=where)
    executions = db.testexecution.find_many(
        where=where,
        skip=skip,
        take=limit,
        order={"executionIndex": "asc"},
        include={
            "steps": True,
        },
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


@require_permissions(Permissions.VALIDATION_VIEW)
def list_execution_results(run_id: str, execution_id: str):
    """GET /v2/runs/<id>/executions/<eid>/results — Steps for one execution."""
    db = get_db_client()

    # Verify the execution exists and belongs to this run
    execution = db.testexecution.find_unique(
        where={"id": execution_id},
        include={
            "target": True,
        },
    )

    if not execution:
        return not_found("Test execution not found")

    if not execution.target or execution.target.runId != run_id:
        return not_found("Test execution not found in this run")

    steps = db.teststep.find_many(
        where={"executionId": execution_id},
        order={"stepIndex": "asc"},
    )

    return jsonify(ApiResponse.ok({
        "execution": _serialize_execution(execution),
        "steps": [_serialize_step(s) for s in steps],
    }).to_dict()), 200
