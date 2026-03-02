"""Internal callback endpoints for the pytest reporter plugin.

These endpoints are called by the ConcordReporter running inside K8s Jobs.
They use the standard auth (API key or JWT) — the K8s job template injects
a CONCORD_API_KEY env var.
"""
import logging
from datetime import datetime, timezone

from database import Json
from flask import jsonify, request

from src.lib.decorators import require_auth
from src.lib.errors import bad_request, conflict, internal_error, not_found
from src.lib.types import ApiResponse
from src.services.database.prisma import get_db_client

from .types import (
    ReportFinishRequest,
    ReportStartRequest,
    ReportTestResultRequest,
    ReportTestStartRequest,
)

logger = logging.getLogger(__name__)


def _get_session_or_404(db, run_id: str):
    session = db.session.find_unique(where={"id": run_id})
    if not session:
        return None, not_found("Validation run not found")
    return session, None


@require_auth
def report_start(run_id: str):
    """POST /v2/validation/runs/<id>/report/start — pytest session started."""
    data, error = ReportStartRequest.from_json(request.get_json())
    if error:
        return bad_request(error)

    db = get_db_client()
    session, err = _get_session_or_404(db, run_id)
    if err:
        return err

    if session.status not in ("ACTIVE",):
        return conflict(f"Cannot start a run with status {session.status}")

    db.session.update(
        where={"id": run_id},
        data={
            "status": "ACTIVE",
            "startedAt": datetime.now(timezone.utc),
        },
    )

    logger.info(f"Validation run {run_id} started by reporter")
    return jsonify(ApiResponse.ok({"runId": run_id, "status": "ACTIVE"}).to_dict()), 200


@require_auth
def report_test_start(run_id: str):
    """POST /v2/validation/runs/<id>/report/test-start — Individual test started."""
    data, error = ReportTestStartRequest.from_json(request.get_json())
    if error:
        return bad_request(error)

    db = get_db_client()
    session, err = _get_session_or_404(db, run_id)
    if err:
        return err

    # Find the test definition by name
    test = db.test.find_first(
        where={
            "name": data.test_name,
            "productId": session.productId,
        },
    )

    if not test:
        # Auto-create test definition if it doesn't exist (first run with new tests)
        test = db.test.create(
            data={
                "name": data.test_name,
                "productId": session.productId,
                "category": data.module,
                "enabled": True,
            },
        )

    # Find the device for this session
    device = db.device.find_first(where={"sessionId": run_id})
    if not device:
        return internal_error("No device found for this run")

    # Find existing execution or create one
    execution = db.testexecution.find_first(
        where={
            "testId": test.id,
            "deviceId": device.id,
        },
    )

    now = datetime.now(timezone.utc)

    if execution:
        db.testexecution.update(
            where={"id": execution.id},
            data={
                "status": "RUNNING",
                "startedAt": now,
            },
        )
    else:
        # Get the node from session config
        node_id = None
        if session.config and isinstance(session.config, dict):
            node_id = session.config.get("nodeId")

        if not node_id:
            # Fall back to first available node
            node = db.node.find_first()
            node_id = node.id if node else None

        if not node_id:
            return internal_error("No node configured for this run")

        execution = db.testexecution.create(
            data={
                "testId": test.id,
                "nodeId": node_id,
                "deviceId": device.id,
                "status": "RUNNING",
                "startedAt": now,
            },
        )

    # Update device status
    db.device.update(
        where={"id": device.id},
        data={"status": "IN_PROGRESS"},
    )

    logger.info(f"Test {data.test_name} started in run {run_id}")
    return jsonify(ApiResponse.ok({
        "executionId": execution.id,
        "testName": data.test_name,
        "status": "RUNNING",
    }).to_dict()), 200


@require_auth
def report_test_result(run_id: str):
    """POST /v2/validation/runs/<id>/report/test-result — Individual test finished."""
    data, error = ReportTestResultRequest.from_json(request.get_json())
    if error:
        return bad_request(error)

    db = get_db_client()
    session, err = _get_session_or_404(db, run_id)
    if err:
        return err

    # Find the test + execution
    test = db.test.find_first(
        where={
            "name": data.test_name,
            "productId": session.productId,
        },
    )

    if not test:
        return not_found(f"Test '{data.test_name}' not found")

    device = db.device.find_first(where={"sessionId": run_id})
    if not device:
        return internal_error("No device found for this run")

    execution = db.testexecution.find_first(
        where={
            "testId": test.id,
            "deviceId": device.id,
        },
    )

    if not execution:
        return not_found(f"No execution found for test '{data.test_name}'")

    now = datetime.now(timezone.utc)
    new_status = "PASSED" if data.passed else "FAILED"

    # Update execution status
    db.testexecution.update(
        where={"id": execution.id},
        data={
            "status": new_status,
            "finishedAt": now,
        },
    )

    # Build result JSON
    result_data = {}
    if data.measurements:
        result_data["measurements"] = data.measurements
    if data.error_message:
        result_data["errorMessage"] = data.error_message
    if data.duration_s is not None:
        result_data["durationS"] = data.duration_s

    # Count existing results to determine step index
    existing_count = db.testresult.count(where={"executionId": execution.id})

    # Create result
    result = db.testresult.create(
        data={
            "executionId": execution.id,
            "stepIndex": existing_count,
            "groupIndex": 0,
            "passed": data.passed,
            "result": Json(result_data),
        },
    )

    logger.info(f"Test {data.test_name} {'PASSED' if data.passed else 'FAILED'} in run {run_id}")
    return jsonify(ApiResponse.ok({
        "resultId": result.id,
        "executionId": execution.id,
        "testName": data.test_name,
        "passed": data.passed,
    }).to_dict()), 200


@require_auth
def report_finish(run_id: str):
    """POST /v2/validation/runs/<id>/report/finish — pytest session finished."""
    data, error = ReportFinishRequest.from_json(request.get_json())
    if error:
        return bad_request(error)

    db = get_db_client()
    session, err = _get_session_or_404(db, run_id)
    if err:
        return err

    now = datetime.now(timezone.utc)

    # Update session with final counts
    db.session.update(
        where={"id": run_id},
        data={
            "status": "COMPLETED",
            "completedCount": data.total,
            "passedCount": data.passed,
            "failedCount": data.failed + data.errors,
            "finishedAt": now,
        },
    )

    # Update device status based on results
    device = db.device.find_first(where={"sessionId": run_id})
    if device:
        device_status = "PASSED" if data.failed == 0 and data.errors == 0 else "FAILED"
        db.device.update(
            where={"id": device.id},
            data={"status": device_status},
        )

    logger.info(
        f"Validation run {run_id} finished: {data.passed}/{data.total} passed, "
        f"{data.failed} failed, {data.errors} errors"
    )

    return jsonify(ApiResponse.ok({
        "runId": run_id,
        "status": "COMPLETED",
        "total": data.total,
        "passed": data.passed,
        "failed": data.failed,
        "errors": data.errors,
    }).to_dict()), 200
