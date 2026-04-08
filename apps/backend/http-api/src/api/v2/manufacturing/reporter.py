"""Manufacturing reporter callbacks — /v2/manufacturing/sessions/<id>/report/."""

import logging
from datetime import datetime, timezone

from database import Json
from flask import jsonify, request

from src.lib.decorators import require_auth
from src.lib.errors import bad_request, not_found
from src.lib.types import ApiResponse
from src.services.database.prisma import get_db_client

from .types import (
    ReportPanelCompleteRequest,
    ReportPanelStartRequest,
    ReportStageResultRequest,
    ReportUnitResultRequest,
    ReportUnitStartRequest,
)

logger = logging.getLogger(__name__)

# SocketIO instance — set by register_v2_routes()
_socketio = None


def set_manufacturing_reporter_socketio(sio):
    global _socketio
    _socketio = sio


def _emit(event: str, data: dict, session_id: str | None = None):
    if not _socketio:
        return
    _socketio.emit(event, data, namespace="/manufacturing")


def _get_session_or_404(db, session_id: str):
    session = db.manufacturingsession.find_unique(where={"id": session_id})
    if not session:
        return None, not_found("Manufacturing session not found")
    return session, None


# ---------------------------------------------------------------------------
# POST /report/panel-start
# ---------------------------------------------------------------------------

@require_auth
def report_panel_start(session_id: str):
    db = get_db_client()
    session, err = _get_session_or_404(db, session_id)
    if err:
        return err

    data, error = ReportPanelStartRequest.from_json(request.get_json())
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
    )

    db.manufacturingsession.update(
        where={"id": session_id},
        data={"panelCount": {"increment": 1}},
    )

    result = {
        "id": panel.id,
        "sessionId": session_id,
        "panelIndex": panel.panelIndex,
        "qrCode": panel.qrCode,
        "unitCount": panel.unitCount,
        "status": panel.status,
    }

    _emit("manufacturing_panel_start", {**result, "sessionId": session_id}, session_id)
    return jsonify(ApiResponse.ok(result).to_dict()), 201


# ---------------------------------------------------------------------------
# POST /report/unit-start
# ---------------------------------------------------------------------------

@require_auth
def report_unit_start(session_id: str):
    db = get_db_client()
    session, err = _get_session_or_404(db, session_id)
    if err:
        return err

    data, error = ReportUnitStartRequest.from_json(request.get_json())
    if error:
        return bad_request(error)

    panel = db.manufacturingpanel.find_unique(where={"id": data.panelId})
    if not panel:
        return not_found("Panel not found")

    unit = db.manufacturingunit.create(
        data={
            "panelId": data.panelId,
            "slotIndex": data.slotIndex,
            "slotId": data.slotId,
            "serialNumber": data.serialNumber,
            "stages": Json([]),
        },
    )

    result = {
        "id": unit.id,
        "panelId": unit.panelId,
        "slotIndex": unit.slotIndex,
        "slotId": unit.slotId,
        "status": unit.status,
    }

    _emit("manufacturing_unit_start", {**result, "sessionId": session_id}, session_id)
    return jsonify(ApiResponse.ok(result).to_dict()), 201


# ---------------------------------------------------------------------------
# POST /report/stage-result
# ---------------------------------------------------------------------------

@require_auth
def report_stage_result(session_id: str):
    db = get_db_client()
    session, err = _get_session_or_404(db, session_id)
    if err:
        return err

    data, error = ReportStageResultRequest.from_json(request.get_json())
    if error:
        return bad_request(error)

    unit = db.manufacturingunit.find_unique(where={"id": data.unitId})
    if not unit:
        return not_found("Unit not found")

    # Append stage result to the stages JSON array
    stages = list(unit.stages) if unit.stages else []
    stage_entry = {
        "name": data.stageName,
        "status": data.status,
    }
    if data.durationMs is not None:
        stage_entry["durationMs"] = data.durationMs
    if data.measurements is not None:
        stage_entry["measurements"] = data.measurements
    if data.errorMessage is not None:
        stage_entry["errorMessage"] = data.errorMessage
    stages.append(stage_entry)

    updated = db.manufacturingunit.update(
        where={"id": data.unitId},
        data={"stages": Json(stages)},
    )

    result = {
        "unitId": data.unitId,
        "stageName": data.stageName,
        "status": data.status,
        "stages": updated.stages,
    }

    _emit("manufacturing_stage_result", {**result, "sessionId": session_id}, session_id)
    return jsonify(ApiResponse.ok(result).to_dict()), 200


# ---------------------------------------------------------------------------
# POST /report/unit-result
# ---------------------------------------------------------------------------

@require_auth
def report_unit_result(session_id: str):
    db = get_db_client()
    session, err = _get_session_or_404(db, session_id)
    if err:
        return err

    data, error = ReportUnitResultRequest.from_json(request.get_json())
    if error:
        return bad_request(error)

    unit = db.manufacturingunit.find_unique(where={"id": data.unitId})
    if not unit:
        return not_found("Unit not found")

    now = datetime.now(timezone.utc)
    update_data = {
        "status": data.status,
        "completedAt": now,
    }
    if data.serialNumber:
        update_data["serialNumber"] = data.serialNumber
    if data.durationMs is not None:
        update_data["durationMs"] = data.durationMs
    if data.errorMessage:
        update_data["errorMessage"] = data.errorMessage

    updated = db.manufacturingunit.update(
        where={"id": data.unitId},
        data=update_data,
    )

    result = {
        "unitId": data.unitId,
        "status": updated.status,
        "serialNumber": updated.serialNumber,
        "durationMs": updated.durationMs,
    }

    _emit("manufacturing_unit_result", {**result, "sessionId": session_id}, session_id)
    return jsonify(ApiResponse.ok(result).to_dict()), 200


# ---------------------------------------------------------------------------
# POST /report/panel-complete
# ---------------------------------------------------------------------------

@require_auth
def report_panel_complete(session_id: str):
    db = get_db_client()
    session, err = _get_session_or_404(db, session_id)
    if err:
        return err

    data, error = ReportPanelCompleteRequest.from_json(request.get_json())
    if error:
        return bad_request(error)

    panel = db.manufacturingpanel.find_unique(where={"id": data.panelId})
    if not panel:
        return not_found("Panel not found")

    now = datetime.now(timezone.utc)
    updated_panel = db.manufacturingpanel.update(
        where={"id": data.panelId},
        data={
            "status": data.status,
            "passedUnits": data.passedUnits,
            "failedUnits": data.failedUnits,
            "completedAt": now,
            "durationMs": data.durationMs,
        },
    )

    # Update session aggregate counts
    count_field = "passedCount" if data.status == "PASSED" else "failedCount"
    db.manufacturingsession.update(
        where={"id": session_id},
        data={count_field: {"increment": 1}},
    )

    result = {
        "panelId": data.panelId,
        "status": updated_panel.status,
        "passedUnits": data.passedUnits,
        "failedUnits": data.failedUnits,
        "durationMs": data.durationMs,
    }

    _emit("manufacturing_panel_complete", {**result, "sessionId": session_id}, session_id)
    return jsonify(ApiResponse.ok(result).to_dict()), 200
