"""Manufacturing sessions v2 — /v2/manufacturing/sessions (TestRun-based).

Replaces the old panel/unit model with the shared TestRun hierarchy:
ManufacturingSession -> TestRun -> RunTarget -> TestExecution -> TestStep.

Each panel scan creates a TestRun within the session. Each run has RunTarget
records (one per fixture slot) and each target has TestExecution records
(manufacturing steps).
"""

import logging
import math
from datetime import datetime, timezone

from flask import g, jsonify, request

from database import Json
from src.lib.audit import log_audit
from src.lib.decorators import require_permissions
from src.lib.errors import bad_request, conflict, not_found
from src.lib.permissions import Permissions
from src.lib.types import ApiResponse
from src.services.database.prisma import get_db_client

logger = logging.getLogger(__name__)

# SocketIO instance — set by register_v2_routes()
_socketio = None


def set_manufacturing_socketio(sio):
    """Assign the SocketIO instance used for real-time events."""
    global _socketio
    _socketio = sio


def _emit(event: str, data: dict, room: str | None = None):
    """Emit an event on the /runs namespace."""
    if not _socketio:
        return
    kwargs = {"namespace": "/runs"}
    if room:
        kwargs["room"] = room
    _socketio.emit(event, data, **kwargs)


# ---------------------------------------------------------------------------
# Serializers
# ---------------------------------------------------------------------------


def _serialize_step(step) -> dict:
    return {
        "id": step.id,
        "executionId": step.executionId,
        "stepIndex": step.stepIndex,
        "name": step.name,
        "status": step.status,
        "passed": step.passed,
        "durationMs": step.durationMs,
        "errorMessage": step.errorMessage,
        "measurements": step.measurements,
        "startedAt": step.startedAt.isoformat() if step.startedAt else None,
        "completedAt": step.completedAt.isoformat() if step.completedAt else None,
    }


def _serialize_execution(ex) -> dict:
    d = {
        "id": ex.id,
        "targetId": ex.targetId,
        "executionIndex": ex.executionIndex,
        "name": ex.name,
        "module": ex.module,
        "status": ex.status,
        "durationMs": ex.durationMs,
        "errorMessage": ex.errorMessage,
        "measurements": ex.measurements,
        "startedAt": ex.startedAt.isoformat() if ex.startedAt else None,
        "completedAt": ex.completedAt.isoformat() if ex.completedAt else None,
    }
    if hasattr(ex, "steps") and ex.steps:
        d["steps"] = [_serialize_step(s) for s in ex.steps]
    else:
        d["steps"] = []
    return d


def _serialize_target(t) -> dict:
    d = {
        "id": t.id,
        "runId": t.runId,
        "slotIndex": t.slotIndex,
        "slotId": t.slotId,
        "serialNumber": t.serialNumber,
        "deviceId": t.deviceId,
        "status": t.status,
        "metadata": t.metadata,
        "errorMessage": t.errorMessage,
        "startedAt": t.startedAt.isoformat() if t.startedAt else None,
        "completedAt": t.completedAt.isoformat() if t.completedAt else None,
        "durationMs": t.durationMs,
    }
    if hasattr(t, "executions") and t.executions:
        d["executions"] = [_serialize_execution(e) for e in t.executions]
    else:
        d["executions"] = []
    return d


def _serialize_run(run, include_targets=False) -> dict:
    d = {
        "id": run.id,
        "type": run.type,
        "name": run.name,
        "productId": run.productId,
        "fixtureId": run.fixtureId,
        "testPackageId": run.testPackageId,
        "manufacturingSessionId": run.manufacturingSessionId,
        "panelIdentifier": run.panelIdentifier,
        "status": run.status,
        "operatorId": run.operatorId,
        "targetCount": run.targetCount,
        "completedCount": getattr(run, "completedCount", 0),
        "passedCount": run.passedCount,
        "failedCount": run.failedCount,
        "config": run.config,
        "notes": run.notes,
        "errorMessage": run.errorMessage,
        "startedAt": run.startedAt.isoformat() if run.startedAt else None,
        "completedAt": run.completedAt.isoformat() if run.completedAt else None,
        "durationMs": run.durationMs,
        "createdAt": run.createdAt.isoformat() if run.createdAt else None,
    }
    if hasattr(run, "testPackage") and run.testPackage:
        d["testPackageVersion"] = run.testPackage.version
    if include_targets and hasattr(run, "targets") and run.targets:
        d["targets"] = [_serialize_target(t) for t in run.targets]
    elif include_targets:
        d["targets"] = []
    return d


def _serialize_session(s, include_runs=False) -> dict:
    d = {
        "id": s.id,
        "productId": s.productId,
        "fixtureId": s.fixtureId,
        "status": s.status,
        "operatorId": s.operatorId,
        "config": s.config,
        "notes": s.notes,
        "startedAt": s.startedAt.isoformat() if s.startedAt else None,
        "endedAt": s.endedAt.isoformat() if hasattr(s, "endedAt") and s.endedAt else None,
        "createdAt": s.createdAt.isoformat() if s.createdAt else None,
        "product": (
            {"id": s.product.id, "name": s.product.name}
            if hasattr(s, "product") and s.product
            else None
        ),
        "fixture": (
            {"id": s.fixture.id, "name": s.fixture.name}
            if hasattr(s, "fixture") and s.fixture
            else None
        ),
        "operator": (
            {"id": s.operator.id, "name": s.operator.name, "email": s.operator.email}
            if hasattr(s, "operator") and s.operator
            else None
        ),
        "runCount": len(s.runs) if hasattr(s, "runs") and s.runs else 0,
    }
    if include_runs and hasattr(s, "runs") and s.runs:
        d["runs"] = [_serialize_run(r) for r in s.runs]
    elif include_runs:
        d["runs"] = []
    return d


# ---------------------------------------------------------------------------
# Test package resolution
# ---------------------------------------------------------------------------


def _resolve_test_package(db, product_id: str, explicit_version: str | None = None):
    """Resolve the manufacturing test package.

    Priority:
    1. Explicit version (if provided)
    2. Latest RELEASED MANUFACTURING package
    3. Latest MANUFACTURING package (dev fallback)

    Returns (test_package, error_response) — error_response is a Flask tuple
    when the explicit version is not found.
    """
    if explicit_version:
        tp = db.testpackage.find_first(
            where={
                "productId": product_id,
                "type": "MANUFACTURING",
                "version": explicit_version,
            },
        )
        if not tp:
            return None, not_found(
                f"Manufacturing test package version '{explicit_version}' not found"
            )
        return tp, None

    # Latest released
    tp = db.testpackage.find_first(
        where={"productId": product_id, "type": "MANUFACTURING", "status": "RELEASED"},
        order={"createdAt": "desc"},
    )
    if tp:
        return tp, None

    # Fallback to latest dev
    tp = db.testpackage.find_first(
        where={"productId": product_id, "type": "MANUFACTURING"},
        order={"createdAt": "desc"},
    )
    return tp, None


# ---------------------------------------------------------------------------
# GET /v2/manufacturing/fixtures — list manufacturing fixtures
# ---------------------------------------------------------------------------


@require_permissions(Permissions.MANUFACTURING_VIEW)
def list_manufacturing_fixtures():
    """List active MANUFACTURING-type fixtures with pagination."""
    db = get_db_client()
    page = max(1, request.args.get("page", 1, type=int))
    limit = min(max(1, request.args.get("limit", 50, type=int)), 100)
    skip = (page - 1) * limit

    where = {"type": "MANUFACTURING", "active": True}

    fixtures = db.fixture.find_many(
        where=where,
        include={"product": True},
        skip=skip,
        take=limit,
        order={"name": "asc"},
    )
    total = db.fixture.count(where=where)

    def _serialize_fixture(f) -> dict:
        return {
            "id": f.id,
            "name": f.name,
            "productId": f.productId,
            "type": f.type,
            "status": f.status,
            "lockedBy": f.lockedBy,
            "active": f.active,
            "product": {"id": f.product.id, "name": f.product.name} if hasattr(f, "product") and f.product else None,
        }

    return jsonify({
        "data": [_serialize_fixture(f) for f in fixtures],
        "pagination": {
            "page": page,
            "limit": limit,
            "total": total,
            "pages": math.ceil(total / limit) if total > 0 else 0,
        },
    }), 200


# ---------------------------------------------------------------------------
# POST /v2/manufacturing/sessions -- create session
# ---------------------------------------------------------------------------


@require_permissions(Permissions.MANUFACTURING_RUN)
def create_manufacturing_session():
    """Create a manufacturing session, locking the fixture."""
    db = get_db_client()
    body = request.get_json()
    if not body:
        return bad_request("Request body must contain JSON data")

    product_id = (body.get("productId") or "").strip()
    if not product_id:
        return bad_request("productId is required")
    fixture_id = (body.get("fixtureId") or "").strip()
    if not fixture_id:
        return bad_request("fixtureId is required")

    # Validate fixture
    fixture = db.fixture.find_unique(where={"id": fixture_id})
    if not fixture:
        return not_found("Fixture not found")
    if fixture.status != "AVAILABLE":
        return conflict(
            "Fixture is not available (current status: {})".format(fixture.status)
        )

    # Validate product
    product = db.product.find_unique(where={"id": product_id})
    if not product:
        return not_found("Product not found")

    operator_id = g.current_user["sub"]

    create_data: dict = {
        "productId": product_id,
        "fixtureId": fixture_id,
        "operatorId": operator_id,
    }
    if body.get("config") is not None:
        create_data["config"] = Json(body["config"])
    if body.get("notes"):
        create_data["notes"] = body["notes"]

    session = db.manufacturingsession.create(
        data=create_data,
        include={"product": True, "fixture": True, "operator": True, "runs": True},
    )

    # Lock the fixture
    db.fixture.update(
        where={"id": fixture_id},
        data={
            "status": "LOCKED",
            "lockedBy": session.id,
            "lockedAt": datetime.now(timezone.utc),
        },
    )

    log_audit("manufacturing_session.create", "ManufacturingSession", session.id, {
        "productId": product_id,
        "fixtureId": fixture_id,
    })

    payload = _serialize_session(session, include_runs=True)
    _emit("manufacturing_session_start", payload, f"mfg-session:{session.id}")
    return jsonify(ApiResponse.ok(payload).to_dict()), 201


# ---------------------------------------------------------------------------
# GET /v2/manufacturing/sessions — list sessions
# ---------------------------------------------------------------------------


@require_permissions(Permissions.MANUFACTURING_VIEW)
def list_manufacturing_sessions():
    """List manufacturing sessions with pagination and optional filters."""
    db = get_db_client()
    page = max(1, request.args.get("page", 1, type=int))
    limit = min(max(1, request.args.get("limit", 20, type=int)), 100)
    skip = (page - 1) * limit

    where: dict = {}
    product_id = request.args.get("productId")
    if product_id:
        where["productId"] = product_id
    status = request.args.get("status")
    if status:
        where["status"] = status

    sessions = db.manufacturingsession.find_many(
        where=where,
        include={
            "product": True,
            "fixture": True,
            "operator": True,
            "runs": True,
        },
        skip=skip,
        take=limit,
        order={"startedAt": "desc"},
    )
    total = db.manufacturingsession.count(where=where)

    return jsonify({
        "data": [_serialize_session(s) for s in sessions],
        "pagination": {
            "page": page,
            "limit": limit,
            "total": total,
            "pages": math.ceil(total / limit) if total > 0 else 0,
        },
    }), 200


# ---------------------------------------------------------------------------
# GET /v2/manufacturing/sessions/<id> — get session detail
# ---------------------------------------------------------------------------


@require_permissions(Permissions.MANUFACTURING_VIEW)
def get_manufacturing_session(session_id: str):
    """Return a session with nested runs, targets, executions, and steps."""
    db = get_db_client()
    session = db.manufacturingsession.find_unique(
        where={"id": session_id},
        include={
            "product": True,
            "fixture": True,
            "operator": True,
            "runs": {
                "include": {
                    "testPackage": True,
                    "targets": {
                        "include": {
                            "executions": {
                                "include": {"steps": True},
                            },
                        },
                    },
                },
                "order_by": {"createdAt": "asc"},
            },
        },
    )
    if not session:
        return not_found("Manufacturing session not found")

    payload = _serialize_session(session, include_runs=True)
    # Enrich runs with full target tree
    if hasattr(session, "runs") and session.runs:
        payload["runs"] = [
            _serialize_run(r, include_targets=True) for r in session.runs
        ]

    return jsonify(ApiResponse.ok(payload).to_dict()), 200


# ---------------------------------------------------------------------------
# POST /v2/manufacturing/sessions/<id>/runs — add a run (panel scan)
# ---------------------------------------------------------------------------


@require_permissions(Permissions.MANUFACTURING_RUN)
def add_manufacturing_run(session_id: str):
    """Scan a panel QR code to create a TestRun within the session."""
    db = get_db_client()

    session = db.manufacturingsession.find_unique(
        where={"id": session_id},
        include={"fixture": {"include": {"slots": {"order_by": {"slotIndex": "asc"}}}}},
    )
    if not session:
        return not_found("Manufacturing session not found")
    if session.status != "ACTIVE":
        return bad_request("Session is not active")

    body = request.get_json()
    if not body:
        return bad_request("Request body must contain JSON data")

    qr_code = (body.get("qrCode") or "").strip()
    if not qr_code:
        return bad_request("qrCode is required")

    # Resolve test package
    explicit_version = body.get("testPackageVersion")
    tp, tp_error = _resolve_test_package(
        db, session.productId, explicit_version
    )
    if tp_error:
        return tp_error

    operator_id = g.current_user["sub"]

    # Determine active slots from the fixture
    fixture = session.fixture
    slots = [s for s in (fixture.slots if hasattr(fixture, "slots") and fixture.slots else []) if s.active]
    target_count = len(slots)

    # Create the TestRun
    run_data: dict = {
        "type": "MANUFACTURING",
        "productId": session.productId,
        "fixtureId": session.fixtureId,
        "manufacturingSessionId": session_id,
        "panelIdentifier": qr_code,
        "operatorId": operator_id,
        "status": "PENDING",
        "targetCount": target_count,
    }
    if tp:
        run_data["testPackageId"] = tp.id
        logger.info("Manufacturing run using test package %s (v%s)", tp.id, tp.version)

    run = db.testrun.create(data=run_data)

    # Auto-create RunTarget records (one per active fixture slot)
    for slot in slots:
        db.runtarget.create(
            data={
                "runId": run.id,
                "slotIndex": slot.slotIndex,
                "slotId": slot.id,
                "serialNumber": slot.dutSnr if hasattr(slot, "dutSnr") else None,
                "deviceId": slot.dutDeviceId if hasattr(slot, "dutDeviceId") else None,
            },
        )

    # Re-fetch run with targets and test package for the response
    run = db.testrun.find_unique(
        where={"id": run.id},
        include={
            "testPackage": True,
            "targets": {"order_by": {"slotIndex": "asc"}},
        },
    )

    log_audit("manufacturing_run.create", "TestRun", run.id, {
        "sessionId": session_id,
        "panelIdentifier": qr_code,
        "testPackageId": tp.id if tp else None,
        "targetCount": target_count,
    })

    payload = _serialize_run(run, include_targets=True)
    _emit("manufacturing_run_start", payload, f"mfg-session:{session_id}")
    return jsonify(ApiResponse.ok(payload).to_dict()), 201


# ---------------------------------------------------------------------------
# POST /v2/manufacturing/sessions/<id>/end — end session
# ---------------------------------------------------------------------------


@require_permissions(Permissions.MANUFACTURING_RUN)
def end_manufacturing_session(session_id: str):
    """End an active manufacturing session and unlock the fixture."""
    db = get_db_client()
    session = db.manufacturingsession.find_unique(where={"id": session_id})
    if not session:
        return not_found("Manufacturing session not found")
    if session.status != "ACTIVE":
        return bad_request("Session is not active")

    now = datetime.now(timezone.utc)
    updated = db.manufacturingsession.update(
        where={"id": session_id},
        data={"status": "COMPLETED", "endedAt": now},
        include={"product": True, "fixture": True, "operator": True, "runs": True},
    )

    # Unlock the fixture
    db.fixture.update(
        where={"id": session.fixtureId},
        data={"status": "AVAILABLE", "lockedBy": None, "lockedAt": None},
    )

    log_audit("manufacturing_session.end", "ManufacturingSession", session_id, {
        "status": "COMPLETED",
    })

    payload = _serialize_session(updated)
    _emit("manufacturing_session_end", payload, f"mfg-session:{session_id}")
    return jsonify(ApiResponse.ok(payload).to_dict()), 200


# ---------------------------------------------------------------------------
# GET /v2/manufacturing/sessions/<id>/results — aggregate results
# ---------------------------------------------------------------------------


@require_permissions(Permissions.MANUFACTURING_VIEW)
def get_manufacturing_results(session_id: str):
    """Return session results with all runs, targets, and executions."""
    db = get_db_client()
    session = db.manufacturingsession.find_unique(
        where={"id": session_id},
        include={
            "product": True,
            "fixture": True,
            "operator": True,
            "runs": {
                "include": {
                    "testPackage": True,
                    "targets": {
                        "include": {
                            "executions": {
                                "include": {"steps": True},
                            },
                        },
                    },
                },
                "order_by": {"createdAt": "asc"},
            },
        },
    )
    if not session:
        return not_found("Manufacturing session not found")

    payload = _serialize_session(session, include_runs=True)
    # Enrich runs with full target tree
    if hasattr(session, "runs") and session.runs:
        payload["runs"] = [
            _serialize_run(r, include_targets=True) for r in session.runs
        ]

    # Aggregate counts across all runs
    total_targets = 0
    total_passed = 0
    total_failed = 0
    for run in (session.runs or []):
        total_targets += run.targetCount
        total_passed += run.passedCount
        total_failed += run.failedCount

    payload["aggregates"] = {
        "runCount": len(session.runs) if session.runs else 0,
        "totalTargets": total_targets,
        "totalPassed": total_passed,
        "totalFailed": total_failed,
        "passRate": (
            round(total_passed / total_targets * 100, 1)
            if total_targets > 0
            else None
        ),
    }

    return jsonify(ApiResponse.ok(payload).to_dict()), 200
