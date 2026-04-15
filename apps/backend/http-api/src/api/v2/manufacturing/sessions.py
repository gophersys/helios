"""Manufacturing sessions v2 — /v2/manufacturing/sessions (TestRun-based).

Replaces the old panel/unit model with the shared TestRun hierarchy:
ManufacturingSession -> TestRun -> RunTarget -> TestExecution -> TestStep.

Each panel scan creates a TestRun within the session. Each run has RunTarget
records (one per fixture slot) and each target has TestExecution records
(manufacturing steps).
"""

import logging
import math
import re
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

# CoreOps client — lazy-initialized singleton
_coreops_client = None
_coreops_init_attempted = False


def _get_coreops_client():
    """Get or initialize the CoreOps client. Returns None if credentials not configured."""
    global _coreops_client, _coreops_init_attempted
    if _coreops_init_attempted:
        return _coreops_client
    _coreops_init_attempted = True
    try:
        from corekinect.core_ops.client import CoreOpsClient
        _coreops_client = CoreOpsClient()
        logger.info("CoreOps client initialized: %s", _coreops_client._config.server_url)
    except Exception as e:
        logger.warning("CoreOps client not available: %s", e)
        _coreops_client = None
    return _coreops_client


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
        "assetSetId": s.assetSetId if hasattr(s, "assetSetId") else None,
        "assetSet": (
            {
                "id": s.assetSet.id,
                "version": s.assetSet.version,
                "variant": s.assetSet.variant,
                "status": s.assetSet.status,
            }
            if hasattr(s, "assetSet") and s.assetSet
            else None
        ),
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
            {
                "id": s.fixture.id,
                "name": s.fixture.name,
                "panelRows": s.fixture.panelRows,
                "panelCols": s.fixture.panelCols,
                "metadata": s.fixture.metadata,
            }
            if hasattr(s, "fixture") and s.fixture
            else None
        ),
        "operator": (
            {"id": s.operator.id, "name": s.operator.name, "email": s.operator.email}
            if hasattr(s, "operator") and s.operator
            else None
        ),
        "runCount": len(s.runs) if hasattr(s, "runs") and s.runs else 0,
        "totalUnits": sum(r.targetCount or 0 for r in s.runs) if hasattr(s, "runs") and s.runs else 0,
        "passedUnits": sum(r.passedCount or 0 for r in s.runs) if hasattr(s, "runs") and s.runs else 0,
        "failedUnits": sum(r.failedCount or 0 for r in s.runs) if hasattr(s, "runs") and s.runs else 0,
        "runnerStatus": getattr(s, "runnerStatus", None),
        "runnerDeploymentName": getattr(s, "runnerDeploymentName", None),
        "runnerLastHeartbeat": (
            s.runnerLastHeartbeat.isoformat()
            if getattr(s, "runnerLastHeartbeat", None)
            else None
        ),
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

    # Concurrency gate — prevent all fixtures from being consumed by manufacturing
    from config.env import env_config
    max_sessions = getattr(env_config, "MAX_CONCURRENT_MANUFACTURING_SESSIONS", 4)
    active_sessions = db.manufacturingsession.count(where={"status": "ACTIVE"})
    if active_sessions >= max_sessions:
        return conflict(
            f"Maximum concurrent manufacturing sessions ({max_sessions}) reached. "
            f"End an active session before starting a new one."
        )

    # Validate fixture (include boardRevision for config resolution)
    fixture = db.fixture.find_unique(
        where={"id": fixture_id},
        include={"boardRevision": True},
    )
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

    # ── Resolve firmware AssetSet ──
    asset_set_id = (body.get("assetSetId") or "").strip() or None
    if asset_set_id:
        # Explicit selection — validate it
        asset_set = db.assetset.find_unique(where={"id": asset_set_id})
        if not asset_set:
            return not_found("AssetSet not found")
        if asset_set.productId != product_id:
            return bad_request("AssetSet does not belong to this product")
        if asset_set.status == "PENDING":
            return bad_request(
                f"AssetSet is not ready (current status: {asset_set.status})"
            )
    else:
        # Auto-resolve from ManufacturingConfig (match fixture's board revision)
        config_where: dict = {"productId": product_id}
        if fixture.boardRevisionId:
            config_where["boardRevisionId"] = fixture.boardRevisionId
        mfg_config = db.manufacturingconfig.find_first(
            where=config_where
        )
        if mfg_config:
            if mfg_config.firmwareSetId:
                asset_set_id = mfg_config.firmwareSetId
            elif mfg_config.firmwareSource == "latest_build":
                latest = db.assetset.find_first(
                    where={"productId": product_id, "status": "COMPLETE"},
                    order={"createdAt": "desc"},
                )
                if latest:
                    asset_set_id = latest.id

    create_data: dict = {
        "productId": product_id,
        "fixtureId": fixture_id,
        "operatorId": operator_id,
    }
    if asset_set_id:
        create_data["assetSetId"] = asset_set_id
    if body.get("config") is not None:
        create_data["config"] = Json(body["config"])
    if body.get("notes"):
        create_data["notes"] = body["notes"]

    session = db.manufacturingsession.create(
        data=create_data,
        include={
            "product": True,
            "fixture": True,
            "operator": True,
            "assetSet": True,
            "runs": True,
        },
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

    # Deploy persistent manufacturing runner
    # Re-fetch fixture with slot→node relations for MTIB address resolution
    fixture_with_slots = db.fixture.find_unique(
        where={"id": fixture_id},
        include={
            "slots": {
                "where": {"active": True},
                "order_by": {"slotIndex": "asc"},
                "include": {"node": True},
            },
        },
    )
    if fixture_with_slots:
        # Snapshot the fixture configuration at session start for traceability.
        # This preserves the exact slot→node mapping even if nodes are reassigned later.
        snapshot_slots = []
        for s in (fixture_with_slots.slots or []):
            node = s.node if hasattr(s, "node") and s.node else None
            node_meta = node.metadata if node and isinstance(node.metadata, dict) else {}
            snapshot_slots.append({
                "slotIndex": s.slotIndex,
                "slotId": s.id,
                "label": s.label,
                "nodeId": s.nodeId,
                "nodeName": node.name if node else None,
                "nodeHostname": node.hostname if node else None,
                "nodeIp": node.ipAddress if node else None,
                "dutSnr": s.dutSnr if hasattr(s, "dutSnr") else None,
                "dutDeviceId": s.dutDeviceId if hasattr(s, "dutDeviceId") else None,
                # MTIB traceability — record exact deployment + image at session start
                "mtibDeploymentName": node_meta.get("deployment_name"),
                "mtibImageSha": node_meta.get("mtibImageSha"),
            })

        snapshot = {
            "fixtureId": fixture_with_slots.id,
            "fixtureName": fixture_with_slots.name,
            "fixtureType": fixture_with_slots.type,
            "panelRows": fixture_with_slots.panelRows,
            "panelCols": fixture_with_slots.panelCols,
            "slots": snapshot_slots,
            "capturedAt": datetime.now(timezone.utc).isoformat(),
        }
        existing_config = session.config if isinstance(session.config, dict) else {}
        existing_config["fixtureSnapshot"] = snapshot

        # ── MTIB health check — verify all nodes are reachable before deploying runner ──
        db.manufacturingsession.update(
            where={"id": session.id},
            data={"runnerStatus": "CHECKING_MTIBS", "config": Json(existing_config)},
        )

        from src.services.kubernetes.mtib_deployments import wait_for_mtibs_healthy
        mtib_check = wait_for_mtibs_healthy(snapshot_slots, timeout_s=30)
        if mtib_check["unhealthy"]:
            unhealthy_names = [
                s.get("nodeHostname") or f"slot-{s['slotIndex']}"
                for s in mtib_check["unhealthy"]
            ]
            logger.warning(
                "MTIB health check failed for session %s: %s",
                session.id, unhealthy_names,
            )
            # Don't block — set warning in config but continue with runner deploy
            existing_config["mtibHealthWarning"] = {
                "unhealthyNodes": unhealthy_names,
                "checkedAt": datetime.now(timezone.utc).isoformat(),
            }
            db.manufacturingsession.update(
                where={"id": session.id},
                data={"config": Json(existing_config)},
            )

        # ── Deploy persistent manufacturing runner ──
        from src.api.v2.manufacturing.runner import deploy_manufacturing_runner
        runner_name = deploy_manufacturing_runner(db, session, fixture_with_slots, product)
        if not runner_name:
            logger.warning("Failed to deploy runner for session %s", session.id)
        # Re-fetch session to include updated runner fields
        refreshed = db.manufacturingsession.find_unique(
            where={"id": session.id},
            include={
                "product": True,
                "fixture": True,
                "operator": True,
                "assetSet": True,
                "runs": True,
            },
        )
        if refreshed:
            session = refreshed

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
    fixture_id = request.args.get("fixtureId")
    if fixture_id:
        where["fixtureId"] = fixture_id
    status = request.args.get("status")
    if status:
        where["status"] = status

    sessions = db.manufacturingsession.find_many(
        where=where,
        include={
            "product": True,
            "fixture": True,
            "operator": True,
            "assetSet": True,
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
            "fixture": {"include": {"boardRevision": True}},
            "operator": True,
            "assetSet": True,
            "runs": {
                "include": {
                    "testPackage": True,
                    "boardRevision": True,
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
# Panel SNR resolution helpers
# ---------------------------------------------------------------------------

def _parse_position_map(raw) -> dict[int, int] | None:
    """Parse a panelPositionMap from fixture metadata.

    Accepts either a dict of string keys {"0": 1, "1": 0, ...}
    or a list [1, 0, 3, 2] (index = CoreOps position, value = fixture slot).
    Returns {coreops_position: fixture_slot_index} or None if not configured.
    """
    if not raw:
        return None
    if isinstance(raw, list):
        return {i: int(v) for i, v in enumerate(raw)}
    if isinstance(raw, dict):
        return {int(k): int(v) for k, v in raw.items()}
    return None


def _resolve_panel_snrs(
    primary_snr: str,
    slot_count: int,
    position_map: dict | None = None,
) -> list[dict]:
    """Resolve per-slot SNRs for a panel from a scanned barcode.

    Calls CoreOps boards/assemblies/search to look up the panel assembly.
    CoreOps returns each board's serial number and its panel position.

    For singletons (slot_count=1), the scanned SNR is the DUT's SNR.
    For panels, CoreOps returns all board SNRs at their positions.

    Args:
        primary_snr: Scanned barcode (one board's SNR from the panel).
        slot_count: Number of panel slots on the fixture.
        position_map: Optional mapping from CoreOps panelPosition (int) to
            fixture slotIndex (int). Needed when the physical panel layout
            doesn't match CoreOps's position numbering.
            Example: {0: 1, 1: 0, 2: 3, 3: 2} swaps positions 0↔1 and 2↔3.

    Returns a list of dicts: [{"slotIndex": 0, "snr": "0A2J", "deviceId": None}, ...].
    """
    result = [{"slotIndex": i, "snr": None, "deviceId": None} for i in range(slot_count)]

    # Singleton: scanned SNR is the DUT
    if slot_count == 1:
        result[0]["snr"] = primary_snr
        return result

    # Panel: look up assembly in CoreOps
    coreops = _get_coreops_client()
    if not coreops:
        logger.warning("CoreOps not available — using scanned SNR on slot-0 only")
        result[0]["snr"] = primary_snr
        return result

    try:
        assembly = coreops.search_board_assembly(primary_snr)
        boards = assembly.get("boards", [])

        if not boards:
            logger.warning("No boards found in CoreOps for SNR %s", primary_snr)
            result[0]["snr"] = primary_snr
            return result

        # Map each board to its fixture slot.
        # CoreOps returns panelPosition (assembly order).
        # position_map translates CoreOps position → fixture slotIndex.
        for board in boards:
            coreops_position = board.get("panelPosition")
            board_snr = board.get("boardSerialNumber")
            if coreops_position is None or not board_snr:
                continue

            # Apply position remap if configured
            slot_idx = position_map.get(coreops_position, coreops_position) if position_map else coreops_position

            if 0 <= slot_idx < slot_count:
                result[slot_idx]["snr"] = board_snr

        logger.info(
            "Resolved panel %s → %s%s",
            primary_snr,
            ", ".join(f"slot-{r['slotIndex']}={r['snr']}" for r in result if r["snr"]),
            f" (position_map={position_map})" if position_map else "",
        )

    except Exception as e:
        logger.warning("CoreOps assembly search failed for %s: %s", primary_snr, e)
        result[0]["snr"] = primary_snr

    return result


# ---------------------------------------------------------------------------
# POST /v2/manufacturing/sessions/<id>/resolve-panel
# ---------------------------------------------------------------------------


@require_permissions(Permissions.MANUFACTURING_RUN)
def resolve_panel(session_id: str):
    """Resolve panel SNRs from a primary SNR based on fixture slot layout."""
    db = get_db_client()

    session = db.manufacturingsession.find_unique(
        where={"id": session_id},
        include={
            "fixture": {
                "include": {
                    "slots": {"order_by": {"slotIndex": "asc"}},
                },
            },
        },
    )
    if not session:
        return not_found("Manufacturing session not found")
    if session.status != "ACTIVE":
        return bad_request("Session is not active")

    body = request.get_json()
    if not body:
        return bad_request("Request body must contain JSON data")

    snr = (body.get("snr") or "").strip()
    if not snr:
        return bad_request("snr is required")

    run_type = (body.get("runType") or "panel").strip().lower()

    fixture = session.fixture
    all_slots = [
        s for s in (fixture.slots if hasattr(fixture, "slots") and fixture.slots else [])
        if s.active
    ]

    if not all_slots:
        return bad_request("Fixture has no active slots")

    # Split panel vs standalone slots
    panel_slots = [s for s in all_slots if not (s.label or "").lower().startswith("standalone")]
    standalone_slots = [s for s in all_slots if (s.label or "").lower().startswith("standalone")]

    coreops_client = _get_coreops_client()
    result_slots = []

    if run_type == "standalone":
        # Standalone: scanned SNR is the DUT directly
        slots = standalone_slots if standalone_slots else all_slots[-1:]
        for slot in slots:
            device_id = None
            coreops_error = None
            if coreops_client:
                try:
                    device_id = coreops_client.assign_device_id(snr)
                except Exception as e:
                    coreops_error = str(e)
                    logger.warning("CoreOps assign_device_id failed for SNR %s: %s", snr, e)
            result_slots.append({
                "slotIndex": slot.slotIndex,
                "snr": snr,
                "deviceId": device_id,
                "label": slot.label if hasattr(slot, "label") and slot.label else f"Slot {slot.slotIndex + 1}",
                "coreopsError": coreops_error,
            })
    else:
        # Panel: resolve via CoreOps assembly lookup
        slots = panel_slots if panel_slots else all_slots
        fixture_meta = fixture.metadata if hasattr(fixture, "metadata") and isinstance(fixture.metadata, dict) else {}
        position_map = _parse_position_map(fixture_meta.get("panelPositionMap"))
        resolved = _resolve_panel_snrs(snr, len(slots), position_map=position_map)

        for slot, r in zip(slots, resolved):
            slot_snr = r.get("snr")
            device_id = None
            coreops_error = None

            if slot_snr and coreops_client:
                try:
                    device_id = coreops_client.assign_device_id(slot_snr)
                except Exception as e:
                    coreops_error = str(e)
                    logger.warning("CoreOps assign_device_id failed for SNR %s: %s", slot_snr, e)

            result_slots.append({
                "slotIndex": slot.slotIndex,
                "snr": slot_snr,
                "deviceId": device_id,
                "label": slot.label if hasattr(slot, "label") and slot.label else f"Slot {slot.slotIndex + 1}",
                "coreopsError": coreops_error,
            })

    return jsonify(ApiResponse.ok({
        "primarySnr": snr,
        "coreopsAvailable": coreops_client is not None,
        "slots": result_slots,
    }).to_dict()), 200


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

    run_type = (body.get("runType") or "panel").strip().lower()
    if run_type not in ("panel", "standalone"):
        return bad_request("runType must be 'panel' or 'standalone'")

    slot_snrs = body.get("slotSnrs")  # optional pre-resolved SNRs
    if slot_snrs is not None:
        if not isinstance(slot_snrs, list):
            return bad_request("slotSnrs must be an array")
        for entry in slot_snrs:
            if not isinstance(entry, dict) or "slotIndex" not in entry or "snr" not in entry:
                return bad_request("Each slotSnrs entry must have 'slotIndex' and 'snr'")

    # Resolve test package
    explicit_version = body.get("testPackageVersion")
    tp, tp_error = _resolve_test_package(
        db, session.productId, explicit_version
    )
    if tp_error:
        return tp_error

    operator_id = g.current_user["sub"]

    # Determine active slots from the fixture, split by panel vs standalone
    fixture = session.fixture
    all_slots = [s for s in (fixture.slots if hasattr(fixture, "slots") and fixture.slots else []) if s.active]

    # Standalone slot is identified by label (set by the fixture wizard)
    panel_slots = [s for s in all_slots if not (s.label or "").lower().startswith("standalone")]
    standalone_slots = [s for s in all_slots if (s.label or "").lower().startswith("standalone")]

    if run_type == "standalone":
        slots = standalone_slots if standalone_slots else all_slots[-1:]
    else:
        slots = panel_slots if panel_slots else all_slots

    target_count = len(slots)

    # Build a lookup for pre-resolved SNRs by slotIndex
    snr_lookup: dict[int, str] = {}
    if slot_snrs:
        for entry in slot_snrs:
            snr_lookup[entry["slotIndex"]] = entry["snr"]

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
    # Populate board revision from the fixture
    if hasattr(fixture, "boardRevisionId") and fixture.boardRevisionId:
        run_data["boardRevisionId"] = fixture.boardRevisionId
    if session.assetSetId:
        run_data["assetSetId"] = session.assetSetId
    if tp:
        run_data["testPackageId"] = tp.id
        logger.info("Manufacturing run using test package %s (v%s)", tp.id, tp.version)

    run = db.testrun.create(data=run_data)

    # Auto-create RunTarget records (one per active fixture slot).
    # For standalone runs, the qrCode IS the DUT serial number.
    # For panel runs, resolve per-slot SNRs via CoreOps assembly lookup.
    if run_type == "panel" and not slot_snrs:
        # Look up panel assembly in CoreOps to get each board's unique SNR.
        # position_map remaps CoreOps panelPosition → fixture slotIndex.
        fixture_meta = fixture.metadata if hasattr(fixture, "metadata") and isinstance(fixture.metadata, dict) else {}
        position_map = _parse_position_map(fixture_meta.get("panelPositionMap"))
        resolved = _resolve_panel_snrs(qr_code, len(slots), position_map=position_map)
        resolved_lookup = {r["slotIndex"]: r for r in resolved}

        # Also resolve device IDs for each board
        coreops_client = _get_coreops_client()
        for slot in slots:
            r = resolved_lookup.get(slot.slotIndex, {})
            slot_snr = snr_lookup.get(slot.slotIndex, r.get("snr"))
            device_id = None

            if slot_snr and coreops_client:
                try:
                    device_id = coreops_client.assign_device_id(slot_snr)
                except Exception as e:
                    logger.warning("CoreOps assign_device_id failed for SNR %s: %s", slot_snr, e)

            db.runtarget.create(
                data={
                    "runId": run.id,
                    "slotIndex": slot.slotIndex,
                    "slotId": slot.id,
                    "serialNumber": slot_snr,
                    "deviceId": device_id or (slot.dutDeviceId if hasattr(slot, "dutDeviceId") else None),
                },
            )
    else:
        # Standalone or explicit slotSnrs
        for slot in slots:
            if run_type == "standalone":
                serial_number = snr_lookup.get(slot.slotIndex, qr_code)
            else:
                serial_number = snr_lookup.get(
                    slot.slotIndex,
                    slot.dutSnr if hasattr(slot, "dutSnr") else None,
                )
            db.runtarget.create(
                data={
                    "runId": run.id,
                    "slotIndex": slot.slotIndex,
                    "slotId": slot.id,
                    "serialNumber": serial_number,
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
# POST /v2/manufacturing/sessions/<id>/redeploy-runner — retry runner deploy
# ---------------------------------------------------------------------------


@require_permissions(Permissions.MANUFACTURING_RUN)
def redeploy_manufacturing_runner(session_id: str):
    """Tear down the current runner (if any) and redeploy for an active session."""
    db = get_db_client()
    session = db.manufacturingsession.find_unique(
        where={"id": session_id},
        include={
            "product": True,
            "fixture": {
                "include": {
                    "slots": {
                        "where": {"active": True},
                        "order_by": {"slotIndex": "asc"},
                        "include": {"node": True},
                    },
                },
            },
        },
    )
    if not session:
        return not_found("Manufacturing session not found")
    if session.status != "ACTIVE":
        return bad_request("Session is not active")

    # Tear down existing runner if any
    from src.api.v2.manufacturing.runner import (
        teardown_manufacturing_runner,
        deploy_manufacturing_runner,
    )
    teardown_manufacturing_runner(db, session)

    # Redeploy
    runner_name = deploy_manufacturing_runner(db, session, session.fixture, session.product)
    if not runner_name:
        return internal_error("Runner deployment failed — check Docker/K8s availability")

    # Re-fetch with updated runner fields
    refreshed = db.manufacturingsession.find_unique(
        where={"id": session_id},
        include={
            "product": True,
            "fixture": True,
            "operator": True,
            "assetSet": True,
            "runs": True,
        },
    )
    payload = _serialize_session(refreshed or session, include_runs=True)
    return jsonify(ApiResponse.ok(payload).to_dict()), 200


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

    # Teardown the persistent manufacturing runner
    from src.api.v2.manufacturing.runner import teardown_manufacturing_runner
    teardown_manufacturing_runner(db, session)

    now = datetime.now(timezone.utc)
    updated = db.manufacturingsession.update(
        where={"id": session_id},
        data={"status": "COMPLETED", "endedAt": now},
        include={
            "product": True,
            "fixture": True,
            "operator": True,
            "assetSet": True,
            "runs": True,
        },
    )

    # Clean up orphaned PENDING runs — they'll never execute now
    db.testrun.update_many(
        where={"manufacturingSessionId": session_id, "status": "PENDING"},
        data={"status": "FAILED", "errorMessage": "Session ended before run started"},
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
# POST /v2/manufacturing/sessions/<id>/archive — archive session
# ---------------------------------------------------------------------------


@require_permissions(Permissions.MANUFACTURING_MANAGE)
def archive_session(session_id: str):
    """Archive a completed manufacturing session."""
    db = get_db_client()
    session = db.manufacturingsession.find_unique(where={"id": session_id})
    if not session:
        return not_found("Session not found")
    if session.status == "ARCHIVED":
        return bad_request("Session is already archived")
    if session.status == "ACTIVE":
        return bad_request("Cannot archive an active session. End it first.")

    updated = db.manufacturingsession.update(
        where={"id": session_id},
        data={"status": "ARCHIVED"},
        include={"product": True, "fixture": True, "operator": True},
    )
    log_audit("manufacturing.session.archive", "ManufacturingSession", session_id, {})
    return jsonify(ApiResponse.ok(_serialize_session(updated)).to_dict()), 200


# ---------------------------------------------------------------------------
# DELETE /v2/manufacturing/sessions/<id> — delete session
# ---------------------------------------------------------------------------


@require_permissions(Permissions.MANUFACTURING_MANAGE)
def delete_session(session_id: str):
    """Delete an archived manufacturing session and its cascaded test runs."""
    db = get_db_client()
    session = db.manufacturingsession.find_unique(where={"id": session_id})
    if not session:
        return not_found("Session not found")
    if session.status != "ARCHIVED":
        return bad_request("Session must be archived before it can be deleted")

    # Check no active runs
    active_runs = db.testrun.count(
        where={"manufacturingSessionId": session_id, "status": {"in": ["PENDING", "ACTIVE"]}}
    )
    if active_runs > 0:
        return conflict(f"Cannot delete — {active_runs} test run(s) still active")

    # Delete session (TestRuns cascade via schema onDelete)
    db.manufacturingsession.delete(where={"id": session_id})
    log_audit("manufacturing.session.delete", "ManufacturingSession", session_id, {})
    return jsonify(ApiResponse.ok({"deleted": True}).to_dict()), 200


# ---------------------------------------------------------------------------
# POST /v2/manufacturing/sessions/batch — batch archive or delete
# ---------------------------------------------------------------------------


@require_permissions(Permissions.MANUFACTURING_MANAGE)
def batch_sessions_action():
    """Apply an action to multiple manufacturing sessions at once."""
    db = get_db_client()
    body = request.get_json()
    if not body:
        return bad_request("Request body required")

    action = (body.get("action") or "").strip().lower()
    session_ids = body.get("sessionIds", [])

    if action not in ("archive", "delete"):
        return bad_request("action must be 'archive' or 'delete'")
    if not isinstance(session_ids, list) or not session_ids:
        return bad_request("sessionIds must be a non-empty array")

    succeeded = []
    failed = []

    for sid in session_ids:
        session = db.manufacturingsession.find_unique(where={"id": sid})
        if not session:
            failed.append({"id": sid, "reason": "Not found"})
            continue

        if action == "archive":
            if session.status == "ACTIVE":
                failed.append({"id": sid, "reason": "Cannot archive active session"})
                continue
            if session.status == "ARCHIVED":
                succeeded.append(sid)
                continue
            db.manufacturingsession.update(
                where={"id": sid}, data={"status": "ARCHIVED"},
            )
            log_audit("manufacturing.session.archive", "ManufacturingSession", sid, {"batch": True})
            succeeded.append(sid)

        elif action == "delete":
            if session.status not in ("ARCHIVED", "COMPLETED", "CANCELLED"):
                failed.append({"id": sid, "reason": f"Cannot delete {session.status} session"})
                continue
            active_runs = db.testrun.count(
                where={"manufacturingSessionId": sid, "status": {"in": ["ACTIVE", "PENDING"]}}
            )
            if active_runs > 0:
                failed.append({"id": sid, "reason": f"{active_runs} active run(s)"})
                continue
            db.manufacturingsession.delete(where={"id": sid})
            log_audit("manufacturing.session.delete", "ManufacturingSession", sid, {"batch": True})
            succeeded.append(sid)

    return jsonify(ApiResponse.ok({
        "action": action,
        "succeeded": succeeded,
        "failed": failed,
    }).to_dict()), 200


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
            "assetSet": True,
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


# ---------------------------------------------------------------------------
# CoreOps proxy — used by manufacturing test runners
# ---------------------------------------------------------------------------


@require_permissions(Permissions.MANUFACTURING_RUN)
def coreops_assign_device_id():
    """POST /v2/manufacturing/coreops/devices/assign

    Proxy to CoreOps: assign a device ID from a board serial number.
    """
    body = request.get_json()
    if not body:
        return bad_request("Request body required")

    snr = (body.get("snr") or "").strip()
    if not snr:
        return bad_request("snr is required")

    client = _get_coreops_client()
    if not client:
        return jsonify(ApiResponse.ok({
            "error": "CoreOps not configured",
            "snr": snr,
        }).to_dict()), 503

    try:
        device_id = client.assign_device_id(snr)
        return jsonify(ApiResponse.ok({
            "deviceId": device_id,
            "snr": snr,
        }).to_dict()), 200
    except Exception as e:
        logger.error("CoreOps assign_device_id failed for SNR %s: %s", snr, e)
        return jsonify(ApiResponse.ok({
            "error": str(e),
            "snr": snr,
        }).to_dict()), 502


@require_permissions(Permissions.MANUFACTURING_RUN)
def coreops_upload_key():
    """POST /v2/manufacturing/coreops/devices/keys

    Proxy to CoreOps: upload a public key for a device.
    """
    body = request.get_json()
    if not body:
        return bad_request("Request body required")

    device_id = (body.get("deviceId") or "").strip()
    pub_key = (body.get("pubKey") or "").strip()
    if not device_id or not pub_key:
        return bad_request("deviceId and pubKey are required")

    client = _get_coreops_client()
    if not client:
        return jsonify(ApiResponse.ok({"error": "CoreOps not configured"}).to_dict()), 503

    try:
        client.upload_public_key(device_id, pub_key)
        return jsonify(ApiResponse.ok({"success": True}).to_dict()), 200
    except Exception as e:
        logger.error("CoreOps upload_public_key failed: %s", e)
        return jsonify(ApiResponse.ok({"error": str(e)}).to_dict()), 502


@require_permissions(Permissions.MANUFACTURING_RUN)
def coreops_save_iccid():
    """POST /v2/manufacturing/coreops/devices/iccids

    Proxy to CoreOps: register an ICCID/SIM.
    """
    body = request.get_json()
    if not body:
        return bad_request("Request body required")

    iccid = (body.get("iccid") or "").strip()
    carrier = (body.get("carrier") or "").strip()
    snr = (body.get("snr") or "").strip()
    imei = (body.get("imei") or "").strip()
    if not iccid or not snr:
        return bad_request("iccid and snr are required")

    client = _get_coreops_client()
    if not client:
        return jsonify(ApiResponse.ok({"error": "CoreOps not configured"}).to_dict()), 503

    try:
        client.save_iccid(iccid, carrier, snr, imei)
        return jsonify(ApiResponse.ok({"success": True}).to_dict()), 200
    except Exception as e:
        logger.error("CoreOps save_iccid failed: %s", e)
        return jsonify(ApiResponse.ok({"error": str(e)}).to_dict()), 502
