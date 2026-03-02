import logging
import math

from flask import jsonify, request

from src.lib.decorators import require_permissions
from src.lib.errors import not_found
from src.lib.permissions import Permissions
from src.lib.types import ApiResponse
from src.services.database.prisma import get_db_client

from .runs import _serialize_execution, _serialize_result

logger = logging.getLogger(__name__)


@require_permissions(Permissions.ADMIN_VALIDATION_VIEW)
def list_executions(run_id: str):
    """GET /v2/validation/runs/<id>/executions — All test executions for a run."""
    db = get_db_client()

    # Verify the session exists
    session = db.session.find_unique(where={"id": run_id})
    if not session:
        return not_found("Validation run not found")

    page = max(1, request.args.get("page", 1, type=int))
    limit = min(max(1, request.args.get("limit", 50, type=int)), 100)
    skip = (page - 1) * limit

    # Filter executions that belong to devices in this session
    where = {"device": {"sessionId": run_id}}

    status = request.args.get("status")
    if status:
        where["status"] = status.upper()

    total = db.testexecution.count(where=where)
    executions = db.testexecution.find_many(
        where=where,
        skip=skip,
        take=limit,
        order={"createdAt": "asc"},
        include={
            "test": True,
            "results": True,
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


@require_permissions(Permissions.ADMIN_VALIDATION_VIEW)
def list_execution_results(run_id: str, execution_id: str):
    """GET /v2/validation/runs/<id>/executions/<eid>/results — Results for one execution."""
    db = get_db_client()

    # Verify the execution exists and belongs to this run
    execution = db.testexecution.find_unique(
        where={"id": execution_id},
        include={
            "test": True,
            "device": True,
        },
    )

    if not execution:
        return not_found("Test execution not found")

    if not execution.device or execution.device.sessionId != run_id:
        return not_found("Test execution not found in this run")

    results = db.testresult.find_many(
        where={"executionId": execution_id},
        order={"stepIndex": "asc"},
    )

    return jsonify(ApiResponse.ok({
        "execution": _serialize_execution(execution),
        "results": [_serialize_result(r) for r in results],
    }).to_dict()), 200
