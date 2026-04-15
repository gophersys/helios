"""Unified reporter callbacks for test runs.

POST /v2/runs/<run_id>/report/<event>

Called by the ConcordReporter running inside K8s Jobs for both validation
and manufacturing test runs.  Auth is via API key injected into the job
environment (CONCORD_API_KEY).

Data model: TestRun -> RunTarget -> TestExecution -> TestStep
"""

import io
import logging
from datetime import datetime, timezone
from typing import Optional

from database import Json
from flask import jsonify, request
from flask_socketio import SocketIO

from src.lib.decorators import require_auth
from src.lib.errors import bad_request, internal_error, not_found
from src.lib.types import ApiResponse
from src.services.database.prisma import get_db_client
from src.services.storage.client import (
    StoragePrefixes,
    get_bucket_name,
    get_storage_client,
    storage_key,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Status transition validation
# ---------------------------------------------------------------------------

_VALID_RUN_TRANSITIONS = {
    "PENDING": {"ACTIVE", "CANCELLED"},
    "ACTIVE": {"ACTIVE", "COMPLETED", "FAILED", "CANCELLED"},  # ACTIVE→ACTIVE is idempotent
    "COMPLETED": set(),
    "FAILED": set(),
    "CANCELLED": set(),
}


def _validate_run_transition(current: str, target: str) -> Optional[str]:
    """Return error message if transition is invalid, None if OK."""
    allowed = _VALID_RUN_TRANSITIONS.get(current, set())
    if target not in allowed:
        return f"Cannot transition run from '{current}' to '{target}'"
    return None

# ---------------------------------------------------------------------------
# SocketIO plumbing
# ---------------------------------------------------------------------------

_socketio: SocketIO | None = None

LOG_OVERFLOW_BYTES = 10 * 1024  # 10 KB inline limit


def init_socketio(sio: SocketIO):
    """Store the SocketIO instance for emitting run events."""
    global _socketio
    _socketio = sio


def _emit(event: str, data: dict, run_id: str):
    """Emit an event to the /runs namespace, room run:<run_id>."""
    if _socketio:
        _socketio.emit(event, data, namespace="/runs", to=f"run:{run_id}")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_run_or_404(run_id: str):
    """Look up a TestRun, returning (run, None) or (None, error_response)."""
    db = get_db_client()
    run = db.testrun.find_unique(where={"id": run_id})
    if not run:
        return None, not_found(f"Run {run_id} not found")
    return run, None


def _resolve_target(db, run_id: str, body: dict):
    """Find a RunTarget by explicit targetId, slotIndex, deviceSerial, or default.

    Resolution priority:
      1. targetId — direct ID lookup
      2. slotIndex — (runId, slotIndex) compound key
      3. deviceSerial — match RunTarget.serialNumber (multi-slot manufacturing)
      4. Default to first target (single-slot validation)

    Returns (target, None) or (None, error_response).
    """
    target_id = body.get("targetId")
    if target_id:
        target = db.runtarget.find_unique(where={"id": target_id})
        if not target:
            return None, not_found(f"Target {target_id} not found")
        return target, None

    slot_index = body.get("targetSlotIndex")
    if slot_index is None:
        slot_index = body.get("slotIndex")

    if slot_index is not None:
        target = db.runtarget.find_unique(
            where={"runId_slotIndex": {"runId": run_id, "slotIndex": slot_index}},
        )
        if not target:
            return None, not_found(f"No target at slot {slot_index} in run {run_id}")
        return target, None

    # Priority 3: deviceSerial → RunTarget.serialNumber (multi-slot)
    device_serial = body.get("deviceSerial")
    if device_serial:
        target = db.runtarget.find_first(
            where={"runId": run_id, "serialNumber": device_serial},
        )
        if target:
            return target, None

    # Default: first target (single-slot validation runs)
    target = db.runtarget.find_first(
        where={"runId": run_id},
        order={"slotIndex": "asc"},
    )
    if not target:
        return None, not_found(f"No targets found for run {run_id}")
    return target, None


def _find_execution_by_name(db, target_id: str, name: str):
    """Find a TestExecution by target + name.

    Returns (execution, None) or (None, error_response).
    """
    execution = db.testexecution.find_first(
        where={"targetId": target_id, "name": name},
    )
    if not execution:
        return None, not_found(f"Execution '{name}' not found for target {target_id}")
    return execution, None


def _store_log_overflow(log_output: str, run_id: str, entity_key: str) -> tuple[str, str | None]:
    """Truncate log output and store overflow in MinIO.

    Returns (truncated_output, storage_key_or_none).
    """
    if not log_output or len(log_output.encode("utf-8")) <= LOG_OVERFLOW_BYTES:
        return log_output or "", None

    truncated = log_output[:LOG_OVERFLOW_BYTES]
    object_name = storage_key(StoragePrefixes.SESSIONS, f"{run_id}/logs/{entity_key}.log")

    try:
        storage = get_storage_client()
        bucket = get_bucket_name()
        data = log_output.encode("utf-8")
        storage.put_object(
            bucket,
            object_name,
            io.BytesIO(data),
            length=len(data),
            content_type="text/plain",
        )
    except Exception as e:
        logger.warning("Failed to store log overflow for %s: %s", entity_key, e)
        return truncated, None

    return truncated, object_name


def _unlock_fixture(db, run) -> None:
    """Release the fixture lock if the run holds one."""
    fixture_id = getattr(run, "fixtureId", None)
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
            logger.info("Released fixture lock %s (run %s)", fixture_id, run.id)
    except Exception as e:
        logger.warning("Failed to unlock fixture %s: %s", fixture_id, e)


def _propagate_to_build_run(db, run, now: datetime) -> None:
    """Update parent build run and emit CI build run event if applicable."""
    build_run_id = getattr(run, "buildRunId", None)
    if not build_run_id:
        return

    try:
        build_run_status = "SUCCESS" if (run.failedCount or 0) == 0 else "FAILED"
        db.buildrun.update(
            where={"id": build_run_id},
            data={"status": build_run_status, "finishedAt": now},
        )
        _emit("ci_build_run_complete", {
            "buildRunId": build_run_id,
            "status": build_run_status,
            "runId": run.id,
        }, run.id)
        logger.info("Build run %s finished with status %s", build_run_id, build_run_status)
    except Exception as e:
        logger.warning("Failed to update build run %s: %s", build_run_id, e)


def _complete_queue_entry(db, run_id: str, now: datetime) -> None:
    """Mark the validation queue entry as completed if one exists."""
    try:
        entry = db.validationqueueentry.find_first(where={"testRunId": run_id})
        if not entry:
            # Legacy: queue entries may reference via sessionId instead
            entry = db.validationqueueentry.find_first(where={"sessionId": run_id})
        if entry and entry.status == "RUNNING":
            db.validationqueueentry.update(
                where={"id": entry.id},
                data={"status": "COMPLETED", "completedAt": now},
            )
    except Exception as e:
        logger.warning("Failed to update queue entry for run %s: %s", run_id, e)


def _process_queue() -> None:
    """Attempt to start the next queued validation run."""
    try:
        from src.api.v2.runs.queue import process_queue
        process_queue()
    except Exception as e:
        logger.warning("Queue processing after run finish failed: %s", e)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@require_auth
def report_preflight(run_id: str):
    """POST /v2/runs/<run_id>/report/preflight -- Preflight check results."""
    run, err = _get_run_or_404(run_id)
    if err:
        return err

    body = request.get_json() or {}
    status = body.get("status", "UNKNOWN")
    checks = body.get("checks", [])

    _emit("run_preflight", {
        "runId": run_id,
        "status": status,
        "checks": checks,
    }, run_id)

    logger.info("Run %s preflight: %s (%d checks)", run_id, status, len(checks))
    return jsonify(ApiResponse.ok({"runId": run_id, "preflight": status}).to_dict()), 200


@require_auth
def report_start(run_id: str):
    """POST /v2/runs/<run_id>/report/start -- Run started."""
    run, err = _get_run_or_404(run_id)
    if err:
        return err

    err = _validate_run_transition(run.status, "ACTIVE")
    if err:
        return bad_request(err)

    db = get_db_client()
    now = datetime.now(timezone.utc)
    db.testrun.update(
        where={"id": run_id},
        data={"status": "ACTIVE", "startedAt": now},
    )

    _emit("run_start", {"runId": run_id, "status": "ACTIVE"}, run_id)
    logger.info("Run %s started", run_id)
    return jsonify(ApiResponse.ok({"runId": run_id, "status": "ACTIVE"}).to_dict()), 200


@require_auth
def report_test_list(run_id: str):
    """POST /v2/runs/<run_id>/report/test-list -- Full test list after collection.

    For multi-slot runs, parses [slot-N] from test names and emits
    per-target events so the frontend can populate each slot's skeleton.
    """
    body = request.get_json()
    if not body:
        return bad_request("Request body required")

    tests = body.get("tests", [])

    db = get_db_client()

    # Persist full test list in run config (for page reload hydration)
    try:
        run = db.testrun.find_unique(where={"id": run_id})
        if run:
            existing_config = run.config if isinstance(run.config, dict) else {}
            existing_config["testList"] = tests
            db.testrun.update(
                where={"id": run_id},
                data={"config": Json(existing_config)},
            )
    except Exception as e:
        logger.warning("Failed to persist test list for run %s: %s", run_id, e)

    # Group tests by slot index for multi-slot routing
    targets = db.runtarget.find_many(
        where={"runId": run_id}, order={"slotIndex": "asc"},
    )

    if len(targets) > 1:
        # Multi-slot: parse [slot-N] from test names and emit per-target
        import re as _re
        tests_by_slot: dict = {}
        for test in tests:
            m = _re.search(r"\[slot-(\d+)\]", test.get("name", ""))
            slot_idx = int(m.group(1)) if m else 0
            tests_by_slot.setdefault(slot_idx, []).append(test)

        for target in targets:
            slot_tests = tests_by_slot.get(target.slotIndex, [])
            if slot_tests:
                _emit("run_test_list", {
                    "runId": run_id,
                    "targetId": target.id,
                    "tests": slot_tests,
                }, run_id)

        logger.info(
            "Test list for run %s: %d tests across %d slots",
            run_id, len(tests), len(targets),
        )
    else:
        # Single-slot: emit all tests to the run room
        _emit("run_test_list", {
            "runId": run_id,
            "targetId": targets[0].id if targets else None,
            "tests": tests,
        }, run_id)

    return jsonify(ApiResponse.ok({"count": len(tests)}).to_dict()), 200


@require_auth
def report_target_start(run_id: str):
    """POST /v2/runs/<run_id>/report/target-start -- Target DUT started."""
    body = request.get_json()
    if not body:
        return bad_request("Request body required")

    slot_index = body.get("slotIndex")
    if slot_index is None:
        return bad_request("slotIndex is required")

    db = get_db_client()
    target = db.runtarget.find_unique(
        where={"runId_slotIndex": {"runId": run_id, "slotIndex": slot_index}},
    )
    if not target:
        return not_found(f"No target at slot {slot_index} in run {run_id}")

    now = datetime.now(timezone.utc)
    update_data: dict = {"status": "RUNNING", "startedAt": now}
    if body.get("serialNumber"):
        update_data["serialNumber"] = body["serialNumber"]
    if body.get("deviceId"):
        update_data["deviceId"] = body["deviceId"]

    db.runtarget.update(where={"id": target.id}, data=update_data)

    _emit("run_target_start", {
        "runId": run_id,
        "targetId": target.id,
        "slotIndex": slot_index,
        "serialNumber": body.get("serialNumber"),
        "deviceId": body.get("deviceId"),
    }, run_id)

    logger.info("Target slot %d started in run %s", slot_index, run_id)
    return jsonify(ApiResponse.ok({
        "targetId": target.id,
        "slotIndex": slot_index,
        "status": "RUNNING",
    }).to_dict()), 200


@require_auth
def report_execution_start(run_id: str):
    """POST /v2/runs/<run_id>/report/execution-start -- Test execution started."""
    body = request.get_json()
    if not body:
        return bad_request("Request body required")

    # Accept both "name" and "testName" (corekinect reporter sends "testName")
    name = (body.get("name") or body.get("testName") or "").strip()
    if not name:
        return bad_request("name or testName is required")

    db = get_db_client()
    target, err = _resolve_target(db, run_id, body)
    if err:
        return err

    now = datetime.now(timezone.utc)
    module = body.get("module")

    # Find existing execution or create one
    execution = db.testexecution.find_first(
        where={"targetId": target.id, "name": name},
    )

    if execution:
        db.testexecution.update(
            where={"id": execution.id},
            data={"status": "RUNNING", "startedAt": now},
        )
    else:
        exec_index = db.testexecution.count(where={"targetId": target.id})
        execution = db.testexecution.create(
            data={
                "targetId": target.id,
                "executionIndex": exec_index,
                "name": name,
                "module": module,
                "status": "RUNNING",
                "startedAt": now,
            },
        )

    _emit("run_execution_start", {
        "runId": run_id,
        "targetId": target.id,
        "executionId": execution.id,
        "name": name,
        "module": module,
    }, run_id)

    logger.info("Execution '%s' started for target %s in run %s", name, target.id, run_id)
    return jsonify(ApiResponse.ok({
        "executionId": execution.id,
        "targetId": target.id,
        "name": name,
        "status": "RUNNING",
    }).to_dict()), 200


@require_auth
def report_execution_result(run_id: str):
    """POST /v2/runs/<run_id>/report/execution-result -- Test execution finished."""
    body = request.get_json()
    if not body:
        return bad_request("Request body required")

    # Accept both "name" and "testName" (corekinect reporter sends "testName")
    name = (body.get("name") or body.get("testName") or "").strip()
    if not name:
        return bad_request("name or testName is required")

    db = get_db_client()
    target, err = _resolve_target(db, run_id, body)
    if err:
        return err

    # Find existing execution or auto-create (handles setup-phase skips
    # where execution-start never fired)
    execution = db.testexecution.find_first(
        where={"targetId": target.id, "name": name},
    )
    if not execution:
        exec_index = db.testexecution.count(where={"targetId": target.id})
        execution = db.testexecution.create(
            data={
                "targetId": target.id,
                "executionIndex": exec_index,
                "name": name,
                "module": body.get("module"),
                "status": "RUNNING",
                "startedAt": datetime.now(timezone.utc),
            },
        )

    now = datetime.now(timezone.utc)
    skipped = body.get("skipped", False)
    passed = body.get("passed", False)
    if skipped:
        new_status = "SKIPPED"
    elif passed:
        new_status = "PASSED"
    else:
        new_status = "FAILED"

    # Accept both "durationMs" and "durationS" (corekinect sends seconds)
    duration_ms = body.get("durationMs")
    if duration_ms is None and body.get("durationS") is not None:
        duration_ms = int(body["durationS"] * 1000)

    update_data: dict = {
        "status": new_status,
        "completedAt": now,
    }
    if duration_ms is not None:
        update_data["durationMs"] = duration_ms
    if body.get("errorMessage"):
        update_data["errorMessage"] = body["errorMessage"]
    if body.get("measurements"):
        update_data["measurements"] = Json(body["measurements"])

    # Handle log output with overflow
    log_output = body.get("logOutput")
    if log_output:
        entity_key = f"executions/{execution.id}"
        truncated, overflow_key = _store_log_overflow(log_output, run_id, entity_key)
        update_data["logOutput"] = truncated
        if overflow_key:
            update_data["logStorageKey"] = overflow_key

    db.testexecution.update(where={"id": execution.id}, data=update_data)

    _emit("run_execution_result", {
        "runId": run_id,
        "targetId": target.id,
        "executionId": execution.id,
        "name": name,
        "module": body.get("module"),
        "passed": passed,
        "skipped": skipped,
        "durationMs": body.get("durationMs"),
        "errorMessage": body.get("errorMessage"),
        "measurements": body.get("measurements"),
    }, run_id)

    logger.info(
        "Execution '%s' %s in run %s",
        name, new_status, run_id,
    )
    return jsonify(ApiResponse.ok({
        "executionId": execution.id,
        "name": name,
        "passed": passed,
        "status": new_status,
    }).to_dict()), 200


@require_auth
def report_step_start(run_id: str):
    """POST /v2/runs/<run_id>/report/step-start -- Sub-step started."""
    body = request.get_json()
    if not body:
        return bad_request("Request body required")

    test_name = (body.get("testName") or "").strip()
    step_name = (body.get("stepName") or "").strip()
    step_index = body.get("stepIndex")
    if not test_name:
        return bad_request("testName is required")
    if step_index is None:
        return bad_request("stepIndex is required")

    db = get_db_client()
    target, err = _resolve_target(db, run_id, body)
    if err:
        return err

    execution, err = _find_execution_by_name(db, target.id, test_name)
    if err:
        return err

    now = datetime.now(timezone.utc)
    step = db.teststep.create(
        data={
            "executionId": execution.id,
            "stepIndex": step_index,
            "name": step_name or f"step-{step_index}",
            "status": "RUNNING",
            "startedAt": now,
        },
    )

    _emit("run_step_start", {
        "runId": run_id,
        "targetId": target.id,
        "executionId": execution.id,
        "stepId": step.id,
        "testName": test_name,
        "stepName": step_name,
        "stepIndex": step_index,
    }, run_id)

    logger.info(
        "Step '%s' (index=%d) started in execution '%s', run %s",
        step_name, step_index, test_name, run_id,
    )
    return jsonify(ApiResponse.ok({
        "stepId": step.id,
        "executionId": execution.id,
        "stepIndex": step_index,
        "status": "RUNNING",
    }).to_dict()), 200


@require_auth
def report_step_result(run_id: str):
    """POST /v2/runs/<run_id>/report/step-result -- Sub-step finished."""
    body = request.get_json()
    if not body:
        return bad_request("Request body required")

    test_name = (body.get("testName") or "").strip()
    step_index = body.get("stepIndex")
    if not test_name:
        return bad_request("testName is required")
    if step_index is None:
        return bad_request("stepIndex is required")

    db = get_db_client()
    target, err = _resolve_target(db, run_id, body)
    if err:
        return err

    execution, err = _find_execution_by_name(db, target.id, test_name)
    if err:
        return err

    passed = body.get("passed", False)
    now = datetime.now(timezone.utc)
    new_status = "PASSED" if passed else "FAILED"

    # Find existing step or create one
    step = db.teststep.find_first(
        where={"executionId": execution.id, "stepIndex": step_index},
    )

    if step:
        update_data: dict = {
            "status": new_status,
            "passed": passed,
            "completedAt": now,
        }
        if body.get("errorMessage"):
            update_data["errorMessage"] = body["errorMessage"]
        if body.get("measurements"):
            update_data["measurements"] = Json(body["measurements"])
        if body.get("durationMs") is not None:
            update_data["durationMs"] = body["durationMs"]
        elif step.startedAt:
            update_data["durationMs"] = int((now - step.startedAt).total_seconds() * 1000)

        step = db.teststep.update(where={"id": step.id}, data=update_data)
    else:
        # No prior step_start -- create with result directly
        step_data: dict = {
            "executionId": execution.id,
            "stepIndex": step_index,
            "name": f"step-{step_index}",
            "status": new_status,
            "passed": passed,
            "completedAt": now,
        }
        if body.get("errorMessage"):
            step_data["errorMessage"] = body["errorMessage"]
        if body.get("measurements"):
            step_data["measurements"] = Json(body["measurements"])
        if body.get("durationMs") is not None:
            step_data["durationMs"] = body["durationMs"]

        step = db.teststep.create(data=step_data)

    _emit("run_step_result", {
        "runId": run_id,
        "targetId": target.id,
        "executionId": execution.id,
        "stepId": step.id,
        "testName": test_name,
        "stepIndex": step_index,
        "passed": passed,
        "errorMessage": body.get("errorMessage"),
        "measurements": body.get("measurements"),
    }, run_id)

    logger.info(
        "Step index=%d %s in execution '%s', run %s",
        step_index, "PASSED" if passed else "FAILED", test_name, run_id,
    )
    return jsonify(ApiResponse.ok({
        "stepId": step.id,
        "executionId": execution.id,
        "stepIndex": step_index,
        "passed": passed,
    }).to_dict()), 200


@require_auth
def report_target_result(run_id: str):
    """POST /v2/runs/<run_id>/report/target-result -- Target DUT finished."""
    body = request.get_json()
    if not body:
        return bad_request("Request body required")

    slot_index = body.get("slotIndex")
    if slot_index is None:
        return bad_request("slotIndex is required")

    status = body.get("status")
    if not status:
        return bad_request("status is required")

    VALID_TARGET_STATUSES = {"PENDING", "RUNNING", "PASSED", "FAILED", "ERROR", "SKIPPED"}
    if status not in VALID_TARGET_STATUSES:
        return bad_request(f"Invalid target status. Must be one of: {', '.join(sorted(VALID_TARGET_STATUSES))}")

    db = get_db_client()
    target = db.runtarget.find_unique(
        where={"runId_slotIndex": {"runId": run_id, "slotIndex": slot_index}},
    )
    if not target:
        return not_found(f"No target at slot {slot_index} in run {run_id}")

    now = datetime.now(timezone.utc)
    update_data: dict = {
        "status": status,
        "completedAt": now,
    }
    if body.get("serialNumber"):
        update_data["serialNumber"] = body["serialNumber"]
    if body.get("errorMessage"):
        update_data["errorMessage"] = body["errorMessage"]
    if body.get("durationMs") is not None:
        update_data["durationMs"] = body["durationMs"]

    db.runtarget.update(where={"id": target.id}, data=update_data)

    _emit("run_target_result", {
        "runId": run_id,
        "targetId": target.id,
        "slotIndex": slot_index,
        "status": status,
        "serialNumber": body.get("serialNumber"),
        "errorMessage": body.get("errorMessage"),
        "durationMs": body.get("durationMs"),
    }, run_id)

    logger.info("Target slot %d finished with status %s in run %s", slot_index, status, run_id)
    return jsonify(ApiResponse.ok({
        "targetId": target.id,
        "slotIndex": slot_index,
        "status": status,
    }).to_dict()), 200


@require_auth
def report_finish(run_id: str):
    """POST /v2/runs/<run_id>/report/finish -- Entire run finished."""
    body = request.get_json()
    if not body:
        return bad_request("Request body required")

    db = get_db_client()
    run, err = _get_run_or_404(run_id)
    if err:
        return err

    now = datetime.now(timezone.utc)
    total = body.get("total", 0)
    passed = body.get("passed", 0)
    failed = body.get("failed", 0)
    errors = body.get("errors", 0)

    # Determine final status and validate the transition
    has_system_errors = errors > 0
    final_status = "FAILED" if has_system_errors or failed > 0 else "COMPLETED"
    err = _validate_run_transition(run.status, final_status)
    if err:
        return bad_request(err)
    # Accept both durationMs and durationS (corekinect sends seconds)
    duration_ms = body.get("durationMs")
    if duration_ms is None and body.get("durationS") is not None:
        duration_ms = int(body["durationS"] * 1000)

    # Mark remaining PENDING/RUNNING executions as SKIPPED (not FAILED —
    # these are tests that never ran, not tests that failed)
    targets = db.runtarget.find_many(where={"runId": run_id}, include={"executions": True})
    target_ids = [t.id for t in targets]
    if target_ids:
        db.testexecution.update_many(
            where={
                "targetId": {"in": target_ids},
                "status": {"in": ["PENDING", "RUNNING"]},
            },
            data={"status": "SKIPPED", "completedAt": now},
        )

    # Compute per-target final status from their executions.
    # A target PASSED if it has at least one execution and zero failures.
    # A target with any FAILED execution is FAILED. Otherwise ERROR.
    for target in targets:
        if target.status not in ("PENDING", "RUNNING"):
            continue  # already finalized (e.g., by report_target_result)
        execs = target.executions or []
        has_failed = any(e.status in ("FAILED", "ERROR") for e in execs)
        has_passed = any(e.status == "PASSED" for e in execs)
        if has_failed:
            target_status = "FAILED"
        elif has_passed:
            target_status = "PASSED"
        else:
            target_status = "ERROR"
        db.runtarget.update(
            where={"id": target.id},
            data={"status": target_status, "completedAt": now},
        )

    run_update: dict = {
        "completedCount": total,
        "passedCount": passed,
        "failedCount": failed + errors,
        "status": final_status,
        "completedAt": now,
    }
    if duration_ms is not None:
        run_update["durationMs"] = duration_ms
    elif run.startedAt:
        run_update["durationMs"] = int((now - run.startedAt).total_seconds() * 1000)
    if body.get("errorMessage"):
        run_update["errorMessage"] = body["errorMessage"]

    db.testrun.update(where={"id": run_id}, data=run_update)

    # Refresh run after update for downstream helpers
    run = db.testrun.find_unique(where={"id": run_id})

    # Post-finish housekeeping
    _unlock_fixture(db, run)
    _complete_queue_entry(db, run_id, now)
    _process_queue()

    _emit("run_finish", {
        "runId": run_id,
        "status": final_status,
        "total": total,
        "passed": passed,
        "failed": failed,
        "errors": errors,
        "durationMs": run_update.get("durationMs"),
    }, run_id)

    # Build run propagation
    _propagate_to_build_run(db, run, now)

    logger.info(
        "Run %s finished: %s (%d passed, %d failed, %d errors)",
        run_id, final_status, passed, failed, errors,
    )
    return jsonify(ApiResponse.ok({
        "runId": run_id,
        "status": final_status,
        "total": total,
        "passed": passed,
        "failed": failed,
    }).to_dict()), 200


# ---------------------------------------------------------------------------
# Streaming / ephemeral endpoints
# ---------------------------------------------------------------------------


@require_auth
def report_log_chunk(run_id: str):
    """POST /v2/runs/<run_id>/report/log-chunk -- Receive log chunk from runner."""
    body = request.get_json()
    if not body:
        return bad_request("Request body required")

    file_name = body.get("file")
    if not file_name:
        return bad_request("file is required")

    _emit("run_log_chunk", {
        "runId": run_id,
        "file": file_name,
        "offset": body.get("offset", 0),
        "data": body.get("data"),
        "testName": body.get("testName"),
        "timestamp": body.get("timestamp"),
        "deviceSerial": body.get("deviceSerial"),
    }, run_id)

    return jsonify(ApiResponse.ok({"received": True}).to_dict()), 200


@require_auth
def report_telemetry(run_id: str):
    """POST /v2/runs/<run_id>/report/telemetry -- Receive telemetry batch.

    Ephemeral: broadcast via WebSocket for live viewing, no DB storage.
    """
    body = request.get_json()
    if not body:
        return bad_request("Request body required")

    samples = body.get("samples", [])
    if not samples:
        return jsonify(ApiResponse.ok({"count": 0}).to_dict()), 200

    _emit("run_telemetry", {"runId": run_id, "samples": samples}, run_id)
    return jsonify(ApiResponse.ok({"count": len(samples)}).to_dict()), 200
