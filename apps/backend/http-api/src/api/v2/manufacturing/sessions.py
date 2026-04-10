"""Manufacturing sessions — /v2/manufacturing/sessions."""

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

from .types import PanelCreateRequest, SessionCreateRequest

logger = logging.getLogger(__name__)

# SocketIO instance — set by register_v2_routes()
_socketio = None


def set_manufacturing_socketio(sio):
    global _socketio
    _socketio = sio


def _emit(event: str, data: dict, session_id: str | None = None):
    if not _socketio:
        return
    _socketio.emit(event, data, namespace="/manufacturing")


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


def _serialize_panel(p) -> dict:
    d = {
        "id": p.id,
        "sessionId": p.sessionId,
        "panelIndex": p.panelIndex,
        "qrCode": p.qrCode,
        "status": p.status,
        "unitCount": p.unitCount,
        "passedUnits": p.passedUnits,
        "failedUnits": p.failedUnits,
        "startedAt": p.startedAt.isoformat() if p.startedAt else None,
        "completedAt": p.completedAt.isoformat() if hasattr(p, "completedAt") and p.completedAt else None,
        "durationMs": p.durationMs if hasattr(p, "durationMs") else None,
    }
    if hasattr(p, "units") and p.units:
        d["units"] = [_serialize_unit(u) for u in p.units]
    else:
        d["units"] = []
    return d


def _serialize_unit(u) -> dict:
    return {
        "id": u.id,
        "panelId": u.panelId,
        "slotIndex": u.slotIndex,
        "slotId": u.slotId,
        "serialNumber": u.serialNumber,
        "status": u.status,
        "stages": u.stages,
        "errorMessage": u.errorMessage,
        "startedAt": u.startedAt.isoformat() if u.startedAt else None,
        "completedAt": u.completedAt.isoformat() if hasattr(u, "completedAt") and u.completedAt else None,
        "durationMs": u.durationMs if hasattr(u, "durationMs") else None,
    }


def _serialize_session(s, include_panels=False) -> dict:
    d = {
        "id": s.id,
        "productId": s.productId,
        "fixtureId": s.fixtureId,
        "status": s.status,
        "operatorId": s.operatorId,
        "panelCount": s.panelCount,
        "passedCount": s.passedCount,
        "failedCount": s.failedCount,
        "config": s.config,
        "testPackageId": getattr(s, "testPackageId", None),
        "testPackageVersion": getattr(s.testPackage, "version", None) if hasattr(s, "testPackage") and s.testPackage else None,
        "startedAt": s.startedAt.isoformat() if s.startedAt else None,
        "endedAt": s.endedAt.isoformat() if hasattr(s, "endedAt") and s.endedAt else None,
        "createdAt": s.createdAt.isoformat() if s.createdAt else None,
        "product": {"id": s.product.id, "name": s.product.name} if hasattr(s, "product") and s.product else None,
        "fixture": {"id": s.fixture.id, "name": s.fixture.name} if hasattr(s, "fixture") and s.fixture else None,
        "operator": {"id": s.operator.id, "name": s.operator.name, "email": s.operator.email} if hasattr(s, "operator") and s.operator else None,
    }
    if include_panels and hasattr(s, "panels") and s.panels:
        d["panels"] = [_serialize_panel(p) for p in s.panels]
    elif include_panels:
        d["panels"] = []
    return d


# ---------------------------------------------------------------------------
# GET /v2/manufacturing/fixtures
# ---------------------------------------------------------------------------

@require_permissions(Permissions.MANUFACTURING_VIEW)
def list_manufacturing_fixtures():
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
# POST /v2/manufacturing/sessions
# ---------------------------------------------------------------------------

@require_permissions(Permissions.MANUFACTURING_RUN)
def create_manufacturing_session():
    db = get_db_client()
    data, error = SessionCreateRequest.from_json(request.get_json())
    if error:
        return bad_request(error)

    fixture = db.fixture.find_unique(where={"id": data.fixtureId})
    if not fixture:
        return not_found("Fixture not found")

    if fixture.status != "AVAILABLE":
        return conflict("Fixture is not available (current status: {})".format(fixture.status))

    operator_id = g.current_user["sub"]

    create_data: dict = {
        "productId": data.productId,
        "fixtureId": data.fixtureId,
        "operatorId": operator_id,
    }
    if data.config is not None:
        create_data["config"] = Json(data.config)

    # Resolve manufacturing test package (explicit version or latest)
    tp = None
    try:
        if data.testPackageVersion:
            tp = db.testpackage.find_first(
                where={
                    "productId": data.productId,
                    "type": "MANUFACTURING",
                    "version": data.testPackageVersion,
                },
            )
            if not tp:
                return not_found(f"Manufacturing test package version '{data.testPackageVersion}' not found")
        else:
            tp = db.testpackage.find_first(
                where={"productId": data.productId, "type": "MANUFACTURING", "status": "RELEASED"},
                order={"createdAt": "desc"},
            )
            if not tp:
                tp = db.testpackage.find_first(
                    where={"productId": data.productId, "type": "MANUFACTURING"},
                    order={"createdAt": "desc"},
                )
        if tp:
            create_data["testPackageId"] = tp.id
            logger.info("Manufacturing session using test package %s", tp.version)
    except Exception as e:
        logger.warning("Failed to resolve manufacturing test package: %s", e)

    session = db.manufacturingsession.create(
        data=create_data,
        include={"product": True, "fixture": True, "operator": True, "panels": True, "testPackage": True},
    )

    # Lock the fixture
    db.fixture.update(
        where={"id": data.fixtureId},
        data={"status": "LOCKED", "lockedBy": session.id, "lockedAt": datetime.now(timezone.utc)},
    )

    log_audit("create", "manufacturing_session", session.id, {
        "productId": data.productId,
        "fixtureId": data.fixtureId,
    })

    _emit("manufacturing_session_start", _serialize_session(session), session.id)
    return jsonify(ApiResponse.ok(_serialize_session(session, include_panels=True)).to_dict()), 201


# ---------------------------------------------------------------------------
# GET /v2/manufacturing/sessions (paginated)
# ---------------------------------------------------------------------------

@require_permissions(Permissions.MANUFACTURING_VIEW)
def list_manufacturing_sessions():
    db = get_db_client()
    page = max(1, request.args.get("page", 1, type=int))
    limit = min(max(1, request.args.get("limit", 50, type=int)), 100)
    skip = (page - 1) * limit

    where = {}
    product_id = request.args.get("productId")
    if product_id:
        where["productId"] = product_id
    status = request.args.get("status")
    if status:
        where["status"] = status

    sessions = db.manufacturingsession.find_many(
        where=where,
        include={"product": True, "fixture": True, "operator": True},
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
# GET /v2/manufacturing/sessions/<id>
# ---------------------------------------------------------------------------

@require_permissions(Permissions.MANUFACTURING_VIEW)
def get_manufacturing_session(session_id: str):
    db = get_db_client()
    session = db.manufacturingsession.find_unique(
        where={"id": session_id},
        include={
            "product": True,
            "fixture": True,
            "operator": True,
            "panels": {"include": {"units": True}},
        },
    )
    if not session:
        return not_found("Manufacturing session not found")

    return jsonify(ApiResponse.ok(_serialize_session(session, include_panels=True)).to_dict()), 200


# ---------------------------------------------------------------------------
# POST /v2/manufacturing/sessions/<id>/panels
# ---------------------------------------------------------------------------

@require_permissions(Permissions.MANUFACTURING_RUN)
def add_manufacturing_panel(session_id: str):
    db = get_db_client()
    session = db.manufacturingsession.find_unique(where={"id": session_id})
    if not session:
        return not_found("Manufacturing session not found")

    if session.status != "ACTIVE":
        return bad_request("Session is not active")

    data, error = PanelCreateRequest.from_json(request.get_json())
    if error:
        return bad_request(error)

    panel_index = db.manufacturingpanel.count(where={"sessionId": session_id})

    panel = db.manufacturingpanel.create(
        data={
            "sessionId": session_id,
            "panelIndex": panel_index,
            "qrCode": data.qrCode,
            "unitCount": data.unitCount,
        },
        include={"units": True},
    )

    # Auto-create units for each fixture slot (up to unitCount)
    fixture = db.fixture.find_unique(
        where={"id": session.fixtureId},
        include={"slots": True},
    )
    slots = fixture.slots if fixture and hasattr(fixture, "slots") else []
    for i in range(data.unitCount):
        slot = slots[i] if i < len(slots) else None
        db.manufacturingunit.create(
            data={
                "panelId": panel.id,
                "slotIndex": i,
                "slotId": slot.id if slot else f"slot-{i}",
                "stages": Json([]),
            },
        )

    # Re-fetch panel with units
    panel = db.manufacturingpanel.find_unique(
        where={"id": panel.id},
        include={"units": True},
    )

    db.manufacturingsession.update(
        where={"id": session_id},
        data={"panelCount": {"increment": 1}},
    )

    _emit("manufacturing_panel_start", _serialize_panel(panel), session_id)
    return jsonify(ApiResponse.ok(_serialize_panel(panel)).to_dict()), 201


# ---------------------------------------------------------------------------
# POST /v2/manufacturing/sessions/<id>/end
# ---------------------------------------------------------------------------

@require_permissions(Permissions.MANUFACTURING_RUN)
def end_manufacturing_session(session_id: str):
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
        include={"product": True, "fixture": True, "operator": True},
    )

    # Release the fixture
    db.fixture.update(
        where={"id": session.fixtureId},
        data={"status": "AVAILABLE", "lockedBy": None, "lockedAt": None},
    )

    log_audit("end", "manufacturing_session", session_id, {"status": "COMPLETED"})
    _emit("manufacturing_session_end", _serialize_session(updated), session_id)
    return jsonify(ApiResponse.ok(_serialize_session(updated)).to_dict()), 200


# ---------------------------------------------------------------------------
# GET /v2/manufacturing/sessions/<id>/results
# ---------------------------------------------------------------------------

@require_permissions(Permissions.MANUFACTURING_VIEW)
def get_manufacturing_results(session_id: str):
    db = get_db_client()
    session = db.manufacturingsession.find_unique(
        where={"id": session_id},
        include={
            "product": True,
            "fixture": True,
            "operator": True,
            "panels": {"include": {"units": True}},
        },
    )
    if not session:
        return not_found("Manufacturing session not found")

    return jsonify(ApiResponse.ok(_serialize_session(session, include_panels=True)).to_dict()), 200
