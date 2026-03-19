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
    StepStartRequest,
    StepResultRequest,
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

    if session.status not in ("ACTIVE", "PENDING"):
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
def report_test_list(run_id: str):
    """POST /v2/sessions/<id>/report/test-list — Full test list after collection.

    Sent by the reporter after pytest collection finishes, before any tests run.
    Broadcast via WebSocket AND persist in session config so the frontend can
    pre-populate test steps on both live subscription and page reload.
    """
    data = request.get_json()
    if not data:
        return bad_request("Request body required")

    tests = data.get("tests", [])

    # Persist test list in session config for page-reload hydration
    db = get_db_client()
    try:
        session = db.session.find_unique(where={"id": run_id})
        if session:
            existing_config = session.config if isinstance(session.config, dict) else {}
            existing_config["testList"] = tests
            db.session.update(
                where={"id": run_id},
                data={"config": Json(existing_config)},
            )
    except Exception as e:
        logger.warning("Failed to persist test list for run %s: %s", run_id, e)

    # Broadcast via WebSocket for live subscribers
    _emit_validation_event("validation_test_list", {
        "runId": run_id,
        "tests": tests,
    })

    return jsonify(ApiResponse.ok({"count": len(tests)}).to_dict()), 200


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

    # Find or create the test definition.
    # Unique constraint: (productId, name, category). Tests with the same name
    # in different modules are DISTINCT records — no collision.
    test = db.test.find_first(
        where={
            "name": data.test_name,
            "productId": session.productId,
            "category": data.module or "uncategorized",
        },
    )

    if not test:
        test = db.test.create(
            data={
                "name": data.test_name,
                "productId": session.productId,
                "category": data.module or "uncategorized",
                "enabled": True,
            },
        )

    # Find the device for this session
    device = db.device.find_first(where={"sessionId": run_id})
    if not device:
        return internal_error("No device found for this run")

    # Find existing execution or create one (simple lookup — test ID is unique per module)
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
            data={"status": "RUNNING", "startedAt": now},
        )
    else:
        node_id = None
        if session.config and isinstance(session.config, dict):
            node_id = session.config.get("nodeId")
        if not node_id:
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

    # Find the test + execution (unique by productId + name + category)
    test = db.test.find_first(
        where={
            "name": data.test_name,
            "productId": session.productId,
            "category": data.module or "uncategorized",
        },
    )
    if not test:
        # Fallback: name-only (backward compat with old test records)
        test = db.test.find_first(
            where={"name": data.test_name, "productId": session.productId},
        )
    if not test:
        return not_found(f"Test '{data.test_name}' not found")

    device = db.device.find_first(where={"sessionId": run_id})
    if not device:
        return internal_error("No device found for this run")

    execution = db.testexecution.find_first(
        where={"testId": test.id, "deviceId": device.id},
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

    # Count existing steps to determine step index
    existing_count = db.teststep.count(where={"executionId": execution.id})

    # Build step data
    step_data = {
        "executionId": execution.id,
        "stepIndex": existing_count,
        "name": data.test_name,
        "status": new_status,
        "passed": data.passed,
        "startedAt": execution.startedAt,
        "finishedAt": now,
    }
    if data.error_message:
        step_data["errorMessage"] = data.error_message
    if data.measurements:
        step_data["measurements"] = Json(data.measurements)
    if data.duration_s is not None:
        step_data["durationMs"] = int(data.duration_s * 1000)
    if data.log_output:
        step_data["logOutput"] = data.log_output

    # Create step
    result = db.teststep.create(data=step_data)

    _emit_validation_event("validation_test_result", {
        "runId": run_id,
        "testName": data.test_name,
        "module": data.module,
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


def _unlock_fixture_if_locked(db, session) -> None:
    """Release the fixture lock if this run had one.

    The fixture ID is stored in session.config["fixtureId"] (or legacy
    "benchId") when trigger.py locks a fixture for exclusive use during the run.
    Also checks session.fixtureId FK.
    """
    if not session.config or not isinstance(session.config, dict):
        fixture_id = getattr(session, "fixtureId", None)
    else:
        fixture_id = session.config.get("fixtureId") or session.config.get("benchId")
        if not fixture_id:
            fixture_id = getattr(session, "fixtureId", None)

    if not fixture_id:
        return

    try:
        fixture = db.fixture.find_unique(where={"id": fixture_id})
        if fixture and fixture.status == "LOCKED":
            db.fixture.update(
                where={"id": fixture_id},
                data={
                    "status": "AVAILABLE",
                    "lockedBy": None,
                    "lockedAt": None,
                },
            )
            station = fixture.stationId or fixture.id
            logger.info(f"Released fixture lock: {station} (was locked by run {session.id})")
    except Exception as e:
        # Don't fail the finish request if unlock fails — log and continue
        logger.warning(f"Failed to unlock fixture {fixture_id}: {e}")


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

    # Release fixture lock before updating session status
    _unlock_fixture_if_locked(db, session)

    # Determine final status using new SessionStatus enum (PASSED/FAILED)
    if data.failed == 0 and data.errors == 0:
        final_status = "PASSED"
    else:
        final_status = "FAILED"

    # Calculate duration if session has startedAt
    duration_ms = None
    if session.startedAt:
        duration_ms = int((now - session.startedAt).total_seconds() * 1000)

    # Update session with final counts
    db.session.update(
        where={"id": run_id},
        data={
            "status": final_status,
            "completedCount": data.total,
            "passedCount": data.passed,
            "failedCount": data.failed + data.errors,
            "durationMs": duration_ms,
            "finishedAt": now,
        },
    )

    # Mark any remaining QUEUED or RUNNING executions as SKIPPED.
    # RUNNING executions happen when test-start fired but the test was then
    # skipped by class-level fail-fast before test-result could update them.
    device = db.device.find_first(where={"sessionId": run_id})
    if device:
        db.testexecution.update_many(
            where={
                "deviceId": device.id,
                "status": {"in": ["QUEUED", "RUNNING"]},
            },
            data={"status": "SKIPPED"},
        )

        device_status = "PASSED" if data.failed == 0 and data.errors == 0 else "FAILED"
        db.device.update(
            where={"id": device.id},
            data={"status": device_status},
        )

    # Flush any buffered log data to MinIO before announcing finish
    from .logs import flush_log_buffers_for_run
    flush_log_buffers_for_run(run_id)

    _emit_validation_event("validation_run_finish", {
        "runId": run_id,
        "status": final_status,
        "total": data.total,
        "passed": data.passed,
        "failed": data.failed,
        "errors": data.errors,
        "durationS": data.duration_s,
        "durationMs": duration_ms,
    })

    # Propagate result back to parent pipeline if this run was triggered by one
    pipeline_id = getattr(session, "pipelineRunId", None)
    if pipeline_id:
        try:
            pipeline_status = "SUCCESS" if (data.failed == 0 and data.errors == 0) else "FAILED"
            db.pipelinerun.update(
                where={"id": pipeline_id},
                data={
                    "status": pipeline_status,
                    "finishedAt": now,
                },
            )
            _emit_validation_event("ci_pipeline_complete", {
                "pipelineId": pipeline_id,
                "status": pipeline_status,
                "validationRunId": run_id,
            })
            logger.info(f"Pipeline {pipeline_id} finished with status {pipeline_status}")
        except Exception as e:
            logger.warning(f"Failed to update parent pipeline {pipeline_id}: {e}")

    logger.info(
        f"Validation run {run_id} finished: {data.passed}/{data.total} passed, "
        f"{data.failed} failed, {data.errors} errors"
    )

    return jsonify(ApiResponse.ok({
        "runId": run_id,
        "status": final_status,
        "total": data.total,
        "passed": data.passed,
        "failed": data.failed,
        "errors": data.errors,
    }).to_dict()), 200


# -------------------------------------------------
#           Sub-Step Reporter Endpoints
# -------------------------------------------------


def _find_execution_for_test(db, session, test_name: str, device_serial: str = None):
    """Find the TestExecution for a given test name and optional device serial.

    Returns (execution, error_response) tuple.
    """
    test = db.test.find_first(
        where={
            "name": test_name,
            "productId": session.productId,
        },
    )
    if not test:
        return None, not_found(f"Test '{test_name}' not found")

    # Find device — by serial if provided, else first device in session
    if device_serial:
        device = db.device.find_first(
            where={"sessionId": session.id, "serialNumber": device_serial},
        )
    else:
        device = db.device.find_first(where={"sessionId": session.id})

    if not device:
        return None, not_found("No device found for this session")

    execution = db.testexecution.find_first(
        where={
            "testId": test.id,
            "deviceId": device.id,
        },
    )
    if not execution:
        return None, not_found(f"No execution found for test '{test_name}'")

    return execution, None


@require_auth
def report_step_start(run_id: str):
    """POST /v2/validation/runs/<id>/report/step-start — Sub-step started."""
    data, error = StepStartRequest.from_json(request.get_json())
    if error:
        return bad_request(error)

    db = get_db_client()
    session, err = _get_session_or_404(db, run_id)
    if err:
        return err

    execution, err = _find_execution_for_test(
        db, session, data.test_name, data.device_serial,
    )
    if err:
        return err

    now = datetime.now(timezone.utc)

    # Create TestStep record with status=RUNNING
    step = db.teststep.create(
        data={
            "executionId": execution.id,
            "stepIndex": data.step_index,
            "name": data.step_name,
            "status": "RUNNING",
            "startedAt": now,
        },
    )

    _emit_validation_event("test_step_start", {
        "runId": run_id,
        "testName": data.test_name,
        "deviceSerial": data.device_serial,
        "stepName": data.step_name,
        "stepIndex": data.step_index,
        "stepId": step.id,
        "executionId": execution.id,
    })

    logger.info(f"Step '{data.step_name}' (index={data.step_index}) started in test {data.test_name}, run {run_id}")
    return jsonify(ApiResponse.ok({
        "stepId": step.id,
        "executionId": execution.id,
        "stepName": data.step_name,
        "stepIndex": data.step_index,
        "status": "RUNNING",
    }).to_dict()), 200


@require_auth
def report_step_result(run_id: str):
    """POST /v2/validation/runs/<id>/report/step-result — Sub-step finished."""
    data, error = StepResultRequest.from_json(request.get_json())
    if error:
        return bad_request(error)

    db = get_db_client()
    session, err = _get_session_or_404(db, run_id)
    if err:
        return err

    execution, err = _find_execution_for_test(
        db, session, data.test_name, data.device_serial,
    )
    if err:
        return err

    # Find the TestStep by execution + stepIndex
    step = db.teststep.find_first(
        where={
            "executionId": execution.id,
            "stepIndex": data.step_index,
        },
    )

    now = datetime.now(timezone.utc)
    new_status = "PASSED" if data.passed else "FAILED"

    if step:
        # Update existing step
        update_data = {
            "status": new_status,
            "passed": data.passed,
            "finishedAt": now,
        }
        if data.error_message:
            update_data["errorMessage"] = data.error_message
        if data.measurements:
            update_data["measurements"] = Json(data.measurements)
        if data.duration_ms is not None:
            update_data["durationMs"] = data.duration_ms
        elif step.startedAt:
            update_data["durationMs"] = int((now - step.startedAt).total_seconds() * 1000)

        step = db.teststep.update(
            where={"id": step.id},
            data=update_data,
        )
    else:
        # Step wasn't pre-created via step-start — create it now with result
        step_data = {
            "executionId": execution.id,
            "stepIndex": data.step_index,
            "name": f"step-{data.step_index}",
            "status": new_status,
            "passed": data.passed,
            "finishedAt": now,
        }
        if data.error_message:
            step_data["errorMessage"] = data.error_message
        if data.measurements:
            step_data["measurements"] = Json(data.measurements)
        if data.duration_ms is not None:
            step_data["durationMs"] = data.duration_ms

        step = db.teststep.create(data=step_data)

    _emit_validation_event("test_step_result", {
        "runId": run_id,
        "testName": data.test_name,
        "deviceSerial": data.device_serial,
        "stepIndex": data.step_index,
        "passed": data.passed,
        "errorMessage": data.error_message,
        "measurements": data.measurements,
        "stepId": step.id,
        "executionId": execution.id,
    })

    logger.info(
        f"Step index={data.step_index} {'PASSED' if data.passed else 'FAILED'} "
        f"in test {data.test_name}, run {run_id}"
    )
    return jsonify(ApiResponse.ok({
        "stepId": step.id,
        "executionId": execution.id,
        "stepIndex": data.step_index,
        "passed": data.passed,
    }).to_dict()), 200


# -------------------------------------------------
#           Telemetry Streaming Endpoint
# -------------------------------------------------


@require_auth
def report_telemetry(run_id: str):
    """POST /v2/sessions/<id>/report/telemetry — Receive telemetry batch.

    Receives batched telemetry samples (UART lines, power measurements,
    sensor data) and broadcasts immediately via WebSocket for live rendering.

    No database storage — telemetry is ephemeral for live viewing.
    Persistent storage is handled by the test runner writing JSONL files
    to MinIO directly.

    Payload:
        {"samples": [
            {"t": 1710000.123, "type": "uart", "target": "app", "test": "test_02", "line": "MCUboot starting"},
            {"t": 1710000.456, "type": "power", "test": "test_03", "mA": 25.4, "mV": 4520},
        ]}
    """
    data = request.get_json()
    if not data:
        return bad_request("Request body required")

    samples = data.get("samples", [])
    if not samples:
        return jsonify(ApiResponse.ok({"count": 0}).to_dict()), 200

    # Broadcast to WebSocket subscribers immediately (low latency path)
    _emit_validation_event("telemetry", {
        "runId": run_id,
        "samples": samples,
    })

    return jsonify(ApiResponse.ok({"count": len(samples)}).to_dict()), 200
