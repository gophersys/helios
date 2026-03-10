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

# SocketIO instance — set by register_v2_routes()
_socketio = None


def set_validation_socketio(sio):
    global _socketio
    _socketio = sio


def _emit_validation_event(event: str, data: dict, run_id: str | None = None):
    """Emit a validation event to subscribers.

    Events are emitted to:
    1. /kubernetes namespace (broadcast) - for backward compatibility
    2. /validation namespace (room-targeted) - for efficient room-based delivery

    Args:
        event: Event name (e.g., "validation_run_start")
        data: Event payload (must include "runId" for room targeting)
        run_id: Optional explicit run_id for room targeting (uses data["runId"] if not provided)
    """
    if not _socketio:
        return

    # Emit to /kubernetes namespace (broadcast for backward compatibility)
    _socketio.emit(event, data, namespace="/kubernetes")

    # Emit to /validation namespace with room targeting
    target_run_id = run_id or data.get("runId")
    if target_run_id:
        _socketio.emit(
            event,
            data,
            namespace="/validation",
            room=f"run:{target_run_id}"
        )


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

    _emit_validation_event("validation_run_start", {"runId": run_id, "status": "ACTIVE"})

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

    _emit_validation_event("validation_test_start", {
        "runId": run_id,
        "testName": data.test_name,
        "module": data.module,
        "executionId": execution.id,
    })

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
    if data.skipped:
        new_status = "SKIPPED"
    elif data.passed:
        new_status = "PASSED"
    else:
        new_status = "FAILED"

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
    if data.log_output:
        result_data["logOutput"] = data.log_output

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

    _emit_validation_event("validation_test_result", {
        "runId": run_id,
        "testName": data.test_name,
        "passed": data.passed,
        "skipped": data.skipped,
        "durationS": data.duration_s,
        "errorMessage": data.error_message,
        "measurements": data.measurements,
        "logOutput": data.log_output,
    })

    logger.info(f"Test {data.test_name} {'PASSED' if data.passed else 'FAILED'} in run {run_id}")
    return jsonify(ApiResponse.ok({
        "resultId": result.id,
        "executionId": execution.id,
        "testName": data.test_name,
        "passed": data.passed,
    }).to_dict()), 200


def _unlock_bench_if_locked(db, session) -> None:
    """Release the bench lock if this run had one.

    The bench ID is stored in session.config["benchId"] when trigger.py
    locks a bench for exclusive use during the run.
    """
    if not session.config or not isinstance(session.config, dict):
        return

    bench_id = session.config.get("benchId")
    if not bench_id:
        return

    try:
        bench = db.testbench.find_unique(where={"id": bench_id})
        if bench and bench.status == "LOCKED":
            db.testbench.update(
                where={"id": bench_id},
                data={
                    "status": "AVAILABLE",
                    "lockedBy": None,
                    "lockedAt": None,
                },
            )
            logger.info(f"Released bench lock: {bench.stationId} (was locked by run {session.id})")
    except Exception as e:
        # Don't fail the finish request if unlock fails — log and continue
        logger.warning(f"Failed to unlock bench {bench_id}: {e}")


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

    # Release bench lock before updating session status
    _unlock_bench_if_locked(db, session)

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

    # Mark any remaining QUEUED executions as SKIPPED (planned but never ran)
    device = db.device.find_first(where={"sessionId": run_id})
    if device:
        db.testexecution.update_many(
            where={
                "deviceId": device.id,
                "status": "QUEUED",
            },
            data={"status": "SKIPPED"},
        )

        device_status = "PASSED" if data.failed == 0 and data.errors == 0 else "FAILED"
        db.device.update(
            where={"id": device.id},
            data={"status": device_status},
        )

    _emit_validation_event("validation_run_finish", {
        "runId": run_id,
        "status": "COMPLETED",
        "total": data.total,
        "passed": data.passed,
        "failed": data.failed,
        "errors": data.errors,
        "durationS": data.duration_s,
    })

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
