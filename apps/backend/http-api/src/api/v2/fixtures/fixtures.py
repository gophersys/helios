import logging
import math
import socket
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from flask import g, jsonify, request
from database import Json

from src.lib.audit import log_audit
from src.lib.decorators import require_auth, require_permissions, _get_permissions_for_set
from src.lib.errors import bad_request, conflict, not_found
from src.lib.permissions import Permissions
from src.lib.types import ApiResponse
from src.services.database.prisma import get_db_client
from src.services.kubernetes.mtib_deployments import (
    create_mtib_deployment,
    delete_mtib_deployment,
    get_mtib_deployment_status,
    get_mtib_pod_image_sha,
    list_mtib_deployments,
)

from .types import FixtureCreateRequest, FixtureUpdateRequest, SlotCreateRequest, SlotUpdateRequest, SlotAssignRequest

logger = logging.getLogger(__name__)


# ── Dashboard ─────────────────────────────────────────────────


@require_auth  # Intentionally open to all authenticated users — dashboard self-filters sections by the caller's permission set
def dashboard_overview():
    """Dashboard overview — stats and fixtures filtered by role and product access.

    Returns per-section counts (products, builds, validation, manufacturing,
    fixtures) plus the fixture health grid, scoped to the caller's permissions
    and product access.
    """
    db = get_db_client()
    user = g.current_user or {}
    user_id = user.get("sub")

    # Resolve permissions
    role = g.effective_role if hasattr(g, "effective_role") else user.get("role", "OPERATOR")
    is_admin = role in ("ADMIN", "MAINTAINER")

    perm_set_id = user.get("permissionSetId")
    perms = _get_permissions_for_set(perm_set_id) if perm_set_id else []
    perms = perms or []
    if is_admin:
        perms = ["products:view", "builds:view", "validation:view",
                 "manufacturing:view", "fixtures:view"]

    # Resolve product access
    product_where: dict = {}
    if not is_admin and user_id:
        access_rows = db.productaccess.find_many(where={"userId": user_id})
        product_ids = [row.productId for row in access_rows]
        product_where = {"id": {"in": product_ids}}

    # ── Build run stats (each section gated by permission) ──

    stats: dict = {}

    if "products:view" in perms:
        products = db.product.find_many(where=product_where)
        stats["products"] = {
            "total": len(products),
            "active": sum(1 for p in products if p.status == "ACTIVE"),
        }

    if "builds:view" in perms:
        build_where: dict = {}
        if product_where:
            build_where["productId"] = product_where.get("id", {})
        total_builds = db.buildrun.count(where=build_where)
        active_builds = db.buildrun.count(where={**build_where, "status": {"in": ["PENDING", "BUILDING", "VALIDATING"]}})
        failed_recent = db.buildrun.count(where={**build_where, "status": "FAILED"})
        stats["builds"] = {
            "total": total_builds,
            "active": active_builds,
            "failed": failed_recent,
        }

    if "validation:view" in perms:
        run_where: dict = {"type": "VALIDATION"}
        if product_where:
            run_where["productId"] = product_where.get("id", {})
        total_runs = db.testrun.count(where=run_where)
        active_runs = db.testrun.count(where={**run_where, "status": "ACTIVE"})
        passed_runs = db.testrun.count(where={**run_where, "status": "COMPLETED"})
        queue_depth = db.validationqueueentry.count(where={"status": {"in": ["QUEUED", "ASSIGNED"]}})
        stats["validation"] = {
            "total": total_runs,
            "active": active_runs,
            "passed": passed_runs,
            "passRate": round(passed_runs / total_runs * 100) if total_runs > 0 else None,
            "queueDepth": queue_depth,
        }

    if "manufacturing:view" in perms:
        mfg_where: dict = {}
        if product_where:
            mfg_where["productId"] = product_where.get("id", {})
        total_sessions = db.manufacturingsession.count(where=mfg_where)
        active_sessions = db.manufacturingsession.count(where={**mfg_where, "status": "ACTIVE"})
        stats["manufacturing"] = {
            "total": total_sessions,
            "active": active_sessions,
        }

    # ── Fixtures (same role + product filtering as before) ──

    fixture_results = []
    can_see_fixtures = "fixtures:view" in perms or "manufacturing:view" in perms or "validation:view" in perms

    if can_see_fixtures:
        fixture_where: dict = {}
        if not is_admin and "fixtures:view" not in perms:
            allowed_types = set()
            if "manufacturing:view" in perms:
                allowed_types.add("MANUFACTURING")
            if "validation:view" in perms:
                allowed_types.add("VALIDATION")
            if allowed_types:
                fixture_where["type"] = {"in": list(allowed_types)}

        if product_where:
            fixture_where["productId"] = product_where.get("id", {})

        fixtures = db.fixture.find_many(
            where=fixture_where,
            order={"name": "asc"},
            include={
                "product": True,
                "slots": {"include": {"node": True}},
            },
        )

        # Single batched K8s call shared across all fixtures in this response.
        dashboard_mtib_status = _get_mtib_status_map(None)

        for f in fixtures:
            slots = f.slots or []
            slot_count = len(slots)
            assigned_count = len([s for s in slots if s.nodeId is not None])

            # Single source of truth — derive everything from the live
            # health helper so list / detail / dashboard agree.
            if slot_count == 0:
                health = "EMPTY"
                nodes_ready = 0
                nodes_total = 0
            else:
                computed = _compute_fixture_health(f, dashboard_mtib_status)
                health = computed["health"]
                nodes_ready = computed["healthDetails"]["nodesReady"]
                nodes_total = computed["healthDetails"]["nodesTotal"]

            fixture_results.append({
                "id": f.id,
                "name": f.name,
                "type": f.type,
                "active": f.active,
                "productName": f.product.name if hasattr(f, "product") and f.product else None,
                "productId": f.productId,
                "slotCount": slot_count,
                "assignedCount": assigned_count,
                "nodesReady": nodes_ready,
                "nodesTotal": nodes_total,
                "health": health,
                "updatedAt": f.updatedAt.isoformat(),
            })

    if "fixtures:view" in perms or is_admin:
        stats["fixtures"] = {
            "total": len(fixture_results),
            "online": sum(1 for f in fixture_results if f["health"] == "ONLINE"),
            "degraded": sum(1 for f in fixture_results if f["health"] in ("OFFLINE", "ERROR")),
        }

    return jsonify(ApiResponse.ok({
        "stats": stats,
        "fixtures": fixture_results,
    }).to_dict()), 200


# ── Fixture Health Computation ────────────────────────────────


def _grpc_probe(host: str, port: int = 50053, timeout_s: float = 0.5) -> bool:
    """Single-shot TCP probe used as a lightweight gRPC reachability check.

    Returns True if the port accepts a connection within the timeout.
    Suitable for per-request health checks where the polling variant
    in services.kubernetes.mtib_deployments.wait_for_mtibs_healthy is
    too slow.
    """
    if not host:
        return False
    try:
        sock = socket.create_connection((host, port), timeout=timeout_s)
        sock.close()
        return True
    except (OSError, socket.timeout):
        return False


def _probe_slots_concurrent(
    probe_targets: list[dict],
    port: int = 50053,
    timeout_s: float = 0.5,
) -> dict[str, bool]:
    """Run gRPC probes against multiple slot node IPs concurrently.

    Each entry in probe_targets must have 'slot_id' and 'host' keys.
    Returns a map of slot_id -> reachable bool.
    """
    if not probe_targets:
        return {}

    def _probe_one(target: dict) -> tuple[str, bool]:
        return target["slot_id"], _grpc_probe(target.get("host", ""), port=port, timeout_s=timeout_s)

    results: dict[str, bool] = {}
    workers = min(len(probe_targets), 8)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for slot_id, ok in pool.map(_probe_one, probe_targets):
            results[slot_id] = ok
    return results


def _get_mtib_status_map(fixture: Any) -> dict[str, dict]:
    """Build a map of MTIB deployment_name -> status using a single batched K8s call.

    Used to avoid N×M K8s reads when computing health across many fixtures.
    Returns an empty dict if K8s is unreachable.
    """
    try:
        deployments = list_mtib_deployments() or []
    except Exception as e:
        logger.warning("Failed to list MTIB deployments: %s", e)
        return {}

    by_name: dict[str, dict] = {}
    for dep in deployments:
        name = dep.get("name") if isinstance(dep, dict) else None
        if name:
            by_name[name] = dep
    return by_name


def _compute_node_status(
    node: Any,
    mtib_state: str | None,
) -> str:
    """Live node status — never persisted.

    Three values:
      * ``MAINTENANCE`` — admin took the node out of rotation
        (``Node.disabled == True``); always wins regardless of live state.
      * ``ONLINE`` — MTIB deployment is up and the gRPC probe answered.
      * ``OFFLINE`` — anything else (no deployment, deployment not ready,
        probe failed).

    The fine-grained ``state`` per slot (NOT_DEPLOYED, DEPLOYING,
    PROBE_FAILED, etc) lives on ``slot.mtibStatus`` for callers that
    need the precise reason.
    """
    if getattr(node, "disabled", False):
        return "MAINTENANCE"
    if mtib_state == "READY":
        return "ONLINE"
    return "OFFLINE"


def _compute_lock_state(
    fixture: Any,
    active_sessions_by_fixture: dict[str, Any] | None = None,
    active_runs_by_fixture: dict[str, Any] | None = None,
) -> tuple[str, str | None, str | None]:
    """Derive the API ``lockState`` (FREE/IN_USE/MAINTENANCE) for a fixture
    from live session/run state. Never persisted on the row.

    Order of precedence:
      1. ``fixture.disabled == True``                                  → MAINTENANCE
      2. an active ManufacturingSession on this fixture                → IN_USE
      3. an active TestRun on this fixture                             → IN_USE
      4. otherwise                                                     → FREE

    Returns ``(lockState, lockedBy, lockedAt)``. ``lockedBy`` is the session
    or run id when IN_USE; ``lockedAt`` is its ``startedAt`` (falling back
    to ``createdAt``).

    Both lookup maps are optional. When omitted, the corresponding source
    is treated as "no active rows" — callers that serve a list endpoint
    must batch-load these once and pass them in to avoid N+1 queries.
    """
    if getattr(fixture, "disabled", False):
        return "MAINTENANCE", None, None

    sess_map = active_sessions_by_fixture or {}
    run_map = active_runs_by_fixture or {}

    holder = sess_map.get(fixture.id) or run_map.get(fixture.id)
    if holder is None:
        return "FREE", None, None

    started = getattr(holder, "startedAt", None) or getattr(holder, "createdAt", None)
    locked_at = started.isoformat() if started else None
    return "IN_USE", getattr(holder, "id", None), locked_at


def _load_active_holders(db, fixture_ids: list[str] | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
    """Fetch active sessions + active runs by fixtureId for one batched
    serialize pass. Each map is ``{fixtureId: row}`` keyed by the fixture
    that's currently locked. Pass ``fixture_ids`` to scope the query;
    omit to fetch globally (used by single-fixture endpoints)."""
    where_sess: dict = {"status": "ACTIVE"}
    where_run: dict = {"status": "ACTIVE"}
    if fixture_ids is not None:
        if not fixture_ids:
            return {}, {}
        where_sess["fixtureId"] = {"in": fixture_ids}
        where_run["fixtureId"] = {"in": fixture_ids}

    sessions = db.manufacturingsession.find_many(where=where_sess)
    runs = db.testrun.find_many(where=where_run)

    sess_by = {s.fixtureId: s for s in sessions if getattr(s, "fixtureId", None)}
    run_by = {r.fixtureId: r for r in runs if getattr(r, "fixtureId", None)}
    return sess_by, run_by


def _compute_assignable(
    lock_state: str,
    health: str,
) -> tuple[bool, str | None]:
    """Single-question predicate: can a session start on this fixture right now?

    Returns ``(assignable, reason)``. ``reason`` is None when assignable; a
    short human-readable string explaining the block otherwise. The session
    create endpoint surfaces ``reason`` verbatim in 409 responses.
    """
    if lock_state == "MAINTENANCE":
        return False, "Fixture is in maintenance mode"
    if lock_state == "IN_USE":
        return False, "Fixture is locked by an active session"
    if health != "ONLINE":
        return False, f"Hardware not ready (health={health})"
    return True, None


def _compute_fixture_health(
    fixture: Any,
    mtib_status_by_deploy_name: dict[str, dict] | None = None,
) -> dict:
    """Live health for a fixture — derived only from K8s pod readiness +
    gRPC probe. Never reads any persisted reachability column.

    Returns:
        ``health``: ONLINE | OFFLINE | ERROR | UNASSIGNED
        ``healthDetails``: {nodesReady, nodesTotal, mtibsReady, mtibsTotal}
        ``slotStates``: per-slot {state, label, reason, deployName,
                                  replicasOk, podsOk, probeOk}

    Per-slot ``state`` vocabulary — single source of truth for both the
    panel tile and the slot detail modal:

      * ``READY``         — deployment ready AND probe answered
      * ``DEPLOYING``     — deployment exists but pods not ready
      * ``PROBE_FAILED``  — pods ready but gRPC probe didn't respond
      * ``NOT_DEPLOYED``  — node has no MTIB deployment
      * ``DISABLED``      — node has ``disabled = true`` (admin override)

    Aggregate health rules:
      * ``UNASSIGNED`` — no assigned slots
      * ``ONLINE``     — every assigned slot is READY
      * ``OFFLINE``    — every assigned slot is NOT_DEPLOYED or DISABLED
      * ``ERROR``      — any partial / mixed state
    """
    slots = getattr(fixture, "slots", None) or []
    assigned = [
        s for s in slots
        if getattr(s, "nodeId", None) and getattr(s, "node", None)
    ]
    nodes_total = len(assigned)

    if nodes_total == 0:
        return {
            "health": "UNASSIGNED",
            "healthDetails": {
                "nodesReady": 0,
                "nodesTotal": 0,
                "mtibsReady": 0,
                "mtibsTotal": 0,
            },
            "slotStates": {},
        }

    status_map = mtib_status_by_deploy_name or {}

    # Phase 1 — read K8s deployment state per assigned slot.
    slot_mtib_state: dict[str, dict] = {}
    probe_targets: list[dict] = []
    mtibs_total = 0
    mtibs_ready = 0

    for slot in assigned:
        node = slot.node
        meta = node.metadata if isinstance(getattr(node, "metadata", None), dict) else {}
        deploy_name = meta.get("deployment_name") if isinstance(meta, dict) else None

        deploy = status_map.get(deploy_name) if deploy_name else None
        replicas_ok = pods_ok = False
        if deploy:
            mtibs_total += 1
            replicas = deploy.get("replicas") or 0
            ready_replicas = deploy.get("readyReplicas") or 0
            replicas_ok = replicas > 0 and ready_replicas == replicas
            # ``list_mtib_deployments`` is a bulk call (one K8s list per
            # fixture-status request) and intentionally does NOT fan out
            # per-deployment pod queries — that's the N+1 we're avoiding.
            # When the pod list is absent, trust the deployment-level
            # readiness gate above. Per-pod detail is still surfaced by
            # the per-deployment status endpoint for drill-in views.
            pods = deploy.get("pods") or []
            pods_ok = all(p.get("ready") for p in pods) if pods else True
            if replicas_ok and pods_ok:
                mtibs_ready += 1

        slot_mtib_state[slot.id] = {
            "deploy_name": deploy_name,
            "replicas_ok": replicas_ok,
            "pods_ok": pods_ok,
            "disabled": bool(getattr(node, "disabled", False)),
        }

        # Probe only when the deployment looks ready and the node isn't
        # admin-disabled — anything else can't possibly be READY.
        if replicas_ok and pods_ok and not slot_mtib_state[slot.id]["disabled"]:
            host = getattr(node, "ipAddress", None) or getattr(node, "hostname", None)
            if host:
                probe_targets.append({"slot_id": slot.id, "host": host})

    # Phase 2 — concurrent gRPC probes.
    probe_results = _probe_slots_concurrent(probe_targets)

    # Phase 3 — derive per-slot state + aggregate counters.
    slot_states: dict[str, dict] = {}
    nodes_ready = 0
    nodes_disabled = nodes_not_deployed = 0
    for slot in assigned:
        s = slot_mtib_state[slot.id]
        deploy_name = s["deploy_name"]
        replicas_ok = s["replicas_ok"]
        pods_ok = s["pods_ok"]
        probe_ok = bool(probe_results.get(slot.id, False))

        if s["disabled"]:
            short, label, reason = "DISABLED", "Node disabled", "node has disabled=true"
            nodes_disabled += 1
        elif not deploy_name:
            short, label, reason = "NOT_DEPLOYED", "MTIB not deployed", "node has no MTIB deployment"
            nodes_not_deployed += 1
        elif not (replicas_ok and pods_ok):
            short, label, reason = "DEPLOYING", "MTIB deploying", "deployment replicas/pods not ready yet"
        elif not probe_ok:
            short, label, reason = "PROBE_FAILED", "MTIB probe failed", "deployment ready but gRPC probe didn't respond"
        else:
            short, label, reason = "READY", "MTIB ready", ""
            nodes_ready += 1

        slot_states[slot.id] = {
            "state": short,
            "label": label,
            "reason": reason,
            "deployName": deploy_name,
            "replicasOk": replicas_ok,
            "podsOk": pods_ok,
            "probeOk": probe_ok,
        }

    details = {
        "nodesReady": nodes_ready,
        "nodesTotal": nodes_total,
        "mtibsReady": mtibs_ready,
        "mtibsTotal": mtibs_total,
    }

    if nodes_ready == nodes_total:
        health = "ONLINE"
    elif (nodes_disabled + nodes_not_deployed) == nodes_total:
        # Every slot is either admin-disabled or has no deployment yet —
        # nothing's broken, the fixture is just powered down / unconfigured.
        health = "OFFLINE"
    else:
        health = "ERROR"

    return {"health": health, "healthDetails": details, "slotStates": slot_states}


# ── Serializers ────────────────────────────────────────────────


def _serialize_fixture(
    f: Any,
    include_slots: bool = False,
    mtib_status_by_deploy_name: dict[str, dict] | None = None,
    active_sessions_by_fixture: dict[str, Any] | None = None,
    active_runs_by_fixture: dict[str, Any] | None = None,
) -> dict:
    """Serialize a Fixture DB record to an API response dict.

    Adds four computed fields the UI uses as the canonical readiness
    signals:

      * ``health``        — live aggregate of K8s + gRPC probe state
      * ``lockState``     — derived live (FREE/IN_USE/MAINTENANCE), see
                            :func:`_compute_lock_state`. Never read from DB.
      * ``assignable``    — single boolean ``health == ONLINE && lockState == FREE``
      * ``assignableReason`` — short string explaining a False, else null

    Anything reading the fixture should consult ``assignable`` for "can
    I run a session?" and surface ``assignableReason`` verbatim. Direct
    reads of ``lockState`` or ``health`` are reserved for UI display.

    ``active_sessions_by_fixture`` / ``active_runs_by_fixture`` should be
    pre-batched by the caller for list endpoints; single-record callers
    can omit them and let this function do its own lookup.
    """
    if active_sessions_by_fixture is None and active_runs_by_fixture is None:
        # Single-record path — batch on demand for just this fixture.
        active_sessions_by_fixture, active_runs_by_fixture = _load_active_holders(
            get_db_client(), [f.id]
        )

    lock_state, locked_by, locked_at = _compute_lock_state(
        f, active_sessions_by_fixture, active_runs_by_fixture
    )

    data = {
        "id": f.id,
        "name": f.name,
        "stationId": f.stationId if hasattr(f, "stationId") else None,
        "productId": f.productId,
        "type": f.type,
        "designId": f.designId if hasattr(f, "designId") else None,
        "boardRevisionId": f.boardRevisionId if hasattr(f, "boardRevisionId") else None,
        "purpose": getattr(f, "purpose", "RELEASE"),
        "disabled": bool(getattr(f, "disabled", False)),
        "lockState": lock_state,
        "lockedBy": locked_by,
        "lockedAt": locked_at,
        "profileOverrides": f.profileOverrides if hasattr(f, "profileOverrides") else None,
        "description": f.description,
        "panelRows": f.panelRows if hasattr(f, "panelRows") else 1,
        "panelCols": f.panelCols if hasattr(f, "panelCols") else 1,
        "active": f.active,
        "metadata": f.metadata,
        "lastHealthCheck": f.lastHealthCheck.isoformat() if hasattr(f, "lastHealthCheck") and f.lastHealthCheck else None,
        "createdById": getattr(f, "createdById", None),
        "createdAt": f.createdAt.isoformat(),
        "updatedAt": f.updatedAt.isoformat(),
    }
    if hasattr(f, "product") and f.product:
        data["productName"] = f.product.name
    if hasattr(f, "boardRevision") and f.boardRevision:
        rev = f.boardRevision
        data["boardRevision"] = {
            "id": rev.id,
            "version": rev.version,
            "ckBoardsName": getattr(rev, "ckBoardsName", None),
            "socs": getattr(rev, "socs", []) or [],
        }
    if hasattr(f, "design") and f.design:
        data["design"] = {
            "id": f.design.id,
            "name": f.design.name,
            "boardRevisionId": f.design.boardRevisionId,
            "revision": f.design.revision,
        }
    if hasattr(f, "slots") and f.slots is not None:
        data["slotCount"] = len(f.slots)
        data["assignedCount"] = len([s for s in f.slots if s.nodeId is not None])
        health = _compute_fixture_health(f, mtib_status_by_deploy_name)
        data["health"] = health["health"]
        data["healthDetails"] = health["healthDetails"]
        slot_states = health.get("slotStates") or {}
        if include_slots:
            data["slots"] = [
                _serialize_slot(s, mtib_state=slot_states.get(s.id))
                for s in f.slots
            ]
    else:
        data["health"] = "UNASSIGNED"
        data["healthDetails"] = {
            "nodesReady": 0,
            "nodesTotal": 0,
            "mtibsReady": 0,
            "mtibsTotal": 0,
        }

    assignable, reason = _compute_assignable(lock_state, data["health"])
    data["assignable"] = assignable
    data["assignableReason"] = reason
    return data


def _serialize_slot(s: Any, mtib_state: dict | None = None) -> dict:
    """Serialize a FixtureSlot DB record to an API response dict.

    ``mtib_state`` is optional per-slot MTIB state from
    :func:`_compute_fixture_health`. When present, the slot tile in the
    UI renders its own MTIB-status chip so operators don't have to
    cross-reference the fixture-wide ERROR badge against individual
    nodes to find the broken one.
    """
    data = {
        "id": s.id,
        "fixtureId": s.fixtureId,
        "slotIndex": s.slotIndex,
        "label": s.label,
        "nodeId": s.nodeId,
        "active": s.active,
        # Hardware paths
        "jlinkAppSerial": s.jlinkAppSerial if hasattr(s, "jlinkAppSerial") else None,
        "jlinkCommsSerial": s.jlinkCommsSerial if hasattr(s, "jlinkCommsSerial") else None,
        "uartAppPath": s.uartAppPath if hasattr(s, "uartAppPath") else None,
        "uartCommsPath": s.uartCommsPath if hasattr(s, "uartCommsPath") else None,
        # DUT identity
        "dutDeviceId": s.dutDeviceId if hasattr(s, "dutDeviceId") else None,
        "dutSnr": s.dutSnr if hasattr(s, "dutSnr") else None,
        "dutImei": s.dutImei if hasattr(s, "dutImei") else None,
        "dutIccids": s.dutIccids if hasattr(s, "dutIccids") else [],
        "createdAt": s.createdAt.isoformat(),
        "updatedAt": s.updatedAt.isoformat(),
    }
    if hasattr(s, "node") and s.node:
        # Live-derive ``node.status`` from the slot's mtib state (and the
        # admin disabled flag) — never read from the DB. The fine-grained
        # state (NOT_DEPLOYED, DEPLOYING, PROBE_FAILED, …) is in
        # ``mtibStatus.state``; this field is the 3-value summary.
        mtib_short = mtib_state.get("state") if mtib_state else None
        data["node"] = {
            "id": s.node.id,
            "name": s.node.name,
            "hostname": s.node.hostname,
            "type": s.node.type,
            "disabled": bool(getattr(s.node, "disabled", False)),
            "status": _compute_node_status(s.node, mtib_short),
        }
    if mtib_state is not None:
        data["mtibStatus"] = mtib_state
    return data


# ── Fixtures CRUD ──────────────────────────────────────────────


@require_permissions(Permissions.FIXTURES_VIEW)
def list_fixtures():
    """List fixtures with pagination and optional type/product filtering."""
    db = get_db_client()

    page = max(1, request.args.get("page", 1, type=int))
    limit = min(max(1, request.args.get("limit", 50, type=int)), 100)
    skip = (page - 1) * limit

    where: dict = {}
    fixture_type = request.args.get("type", type=str)
    if fixture_type:
        fixture_type = fixture_type.strip().upper()
        if fixture_type in ("MANUFACTURING", "VALIDATION"):
            where["type"] = fixture_type
    product_id = request.args.get("productId", type=str)
    if product_id:
        where["productId"] = product_id.strip()

    search = request.args.get("search", type=str)
    if search:
        where["name"] = {"contains": search.strip(), "mode": "insensitive"}

    total = db.fixture.count(where=where)
    fixtures = db.fixture.find_many(
        where=where,
        skip=skip,
        take=limit,
        order={"name": "asc"},
        include={
            "product": True,
            "design": True,
            "slots": {
                "include": {"node": True},
                "order_by": {"slotIndex": "asc"},
            },
        },
    )
    # Single batched K8s call shared across all fixtures in this response.
    mtib_status = _get_mtib_status_map(None)
    # Single batched lookup of active sessions/runs — derives lockState live.
    sess_by, run_by = _load_active_holders(db, [f.id for f in fixtures])
    return jsonify(ApiResponse.ok({
        "data": [
            _serialize_fixture(
                f,
                mtib_status_by_deploy_name=mtib_status,
                active_sessions_by_fixture=sess_by,
                active_runs_by_fixture=run_by,
            )
            for f in fixtures
        ],
        "pagination": {
            "page": page,
            "limit": limit,
            "total": total,
            "pages": math.ceil(total / limit) if limit > 0 else 0,
        },
    }).to_dict()), 200


@require_permissions(Permissions.FIXTURES_MANAGE)
def create_fixture():
    """Create a fixture with auto-generated slots."""
    data, error = FixtureCreateRequest.from_json(request.get_json())
    if error:
        return bad_request(error)

    db = get_db_client()

    # Verify product exists
    product = db.product.find_unique(where={"id": data.productId})
    if not product:
        return not_found("Product not found")

    # Check name uniqueness
    existing = db.fixture.find_first(where={"name": data.name})
    if existing:
        return conflict("Fixture with this name already exists")

    # Check stationId uniqueness if provided
    station_id = getattr(data, "stationId", None)
    if station_id:
        if db.fixture.find_first(where={"stationId": station_id}):
            return conflict(f"Fixture with stationId '{station_id}' already exists")

    # Build create payload
    create_data: dict = {
        "name": data.name,
        "productId": data.productId,
        "type": data.type,
        "description": data.description,
    }
    if station_id:
        create_data["stationId"] = station_id
    design_id = getattr(data, "designId", None)
    design = None
    if design_id:
        design = db.fixturedesign.find_unique(where={"id": design_id})
        if not design:
            return not_found("Fixture design not found")
        create_data["designId"] = design_id
        # Derive type and boardRevisionId from design if not explicitly set
        if not create_data.get("boardRevisionId") and design.boardRevisionId:
            create_data["boardRevisionId"] = design.boardRevisionId
        if hasattr(design, "type") and design.type:
            create_data["type"] = design.type

    # Panel layout
    panel_rows = getattr(data, "panelRows", None)
    panel_cols = getattr(data, "panelCols", None)
    if panel_rows is not None:
        create_data["panelRows"] = max(1, min(10, int(panel_rows)))
    if panel_cols is not None:
        create_data["panelCols"] = max(1, min(10, int(panel_cols)))

    if data.metadata is not None:
        create_data["metadata"] = Json(data.metadata)

    user = getattr(g, "current_user", None)
    if user and isinstance(user, dict):
        create_data["createdById"] = user.get("sub")

    # Auto-create slots from design's slotDefinitions, or from manual slots
    slot_defs = None
    if design and hasattr(design, "slotDefinitions") and design.slotDefinitions:
        slot_defs = design.slotDefinitions if isinstance(design.slotDefinitions, list) else []
    if slot_defs:
        create_data["slots"] = {
            "create": [
                {
                    "slotIndex": s.get("index", i),
                    "label": s.get("label"),
                    "jlinkAppSerial": s.get("jlink_app_serial"),
                    "jlinkCommsSerial": s.get("jlink_comms_serial"),
                    "uartAppPath": s.get("uart_app_path"),
                    "uartCommsPath": s.get("uart_comms_path"),
                }
                for i, s in enumerate(slot_defs)
            ]
        }
    elif data.slots:
        create_data["slots"] = {
            "create": [
                {
                    "slotIndex": s["slotIndex"],
                    "label": s.get("label"),
                }
                for s in data.slots
            ]
        }

    fixture = db.fixture.create(
        data=create_data,
        include={"product": True, "slots": True},
    )
    log_audit("fixture.create", "Fixture", fixture.id, {"name": data.name, "type": data.type, "productId": data.productId})
    return jsonify(ApiResponse.ok(_serialize_fixture(fixture, include_slots=True)).to_dict()), 201


@require_permissions(Permissions.FIXTURES_VIEW)
def get_fixture(fixture_id: str):
    """Get a fixture with its slots and node details."""
    db = get_db_client()
    fixture = db.fixture.find_unique(
        where={"id": fixture_id},
        include={
            "product": True,
            "design": True,
            "slots": {
                "order_by": {"slotIndex": "asc"},
                "include": {"node": True},
            },
        },
    )
    if not fixture:
        return not_found("Fixture not found")
    mtib_status = _get_mtib_status_map(fixture)
    return jsonify(
        ApiResponse.ok(
            _serialize_fixture(
                fixture,
                include_slots=True,
                mtib_status_by_deploy_name=mtib_status,
            )
        ).to_dict()
    ), 200


@require_permissions(Permissions.FIXTURES_MANAGE)
def update_fixture(fixture_id: str):
    """Update a fixture's properties."""
    data, error = FixtureUpdateRequest.from_json(request.get_json())
    if error or data is None:
        return bad_request(error)

    db = get_db_client()
    existing = db.fixture.find_unique(where={"id": fixture_id})
    if not existing:
        return not_found("Fixture not found")

    # Check name uniqueness if changing
    if data.name and data.name != existing.name:
        dup = db.fixture.find_first(where={"name": data.name})
        if dup:
            return conflict("Fixture with this name already exists")

    # purpose flips have to wait for an idle fixture — switching DEV ↔
    # RELEASE while a session is mid-run would orphan the run from the
    # gate that admitted it (e.g. dev session → flip to RELEASE → next
    # panel scan rejects mid-shift). Refuse upfront.
    if data.purpose is not None and data.purpose != existing.purpose:
        sess_by, run_by = _load_active_holders(db, [fixture_id])
        if fixture_id in sess_by or fixture_id in run_by:
            return conflict(
                "Cannot change fixture purpose while a session or run is "
                "active on it. End it first."
            )

    update_data = data.to_update_data()
    if "metadata" in update_data and update_data["metadata"] is not None:
        update_data["metadata"] = Json(update_data["metadata"])

    fixture = db.fixture.update(
        where={"id": fixture_id},
        data=update_data,
        include={"product": True, "slots": True},
    )
    log_audit("fixture.update", "Fixture", fixture_id, {"name": existing.name, "changes": data.to_update_data()})
    return jsonify(ApiResponse.ok(_serialize_fixture(fixture)).to_dict()), 200


@require_permissions(Permissions.FIXTURES_MANAGE)
def delete_fixture(fixture_id: str):
    """Delete a fixture — undeploys MTIB servers and frees all assigned nodes."""
    db = get_db_client()
    existing = db.fixture.find_unique(
        where={"id": fixture_id},
        include={"slots": True},
    )
    if not existing:
        return not_found("Fixture not found")

    # Check for active manufacturing sessions (archived/completed don't block)
    active_sessions = db.manufacturingsession.count(
        where={"fixtureId": fixture_id, "status": "ACTIVE"}
    )
    if active_sessions > 0:
        return conflict(f"Cannot delete fixture: {active_sessions} active manufacturing session(s)")

    # Check for truly active test runs — orphaned PENDING runs from dead sessions don't block
    active_runs = db.testrun.count(
        where={
            "fixtureId": fixture_id,
            "status": {"in": ["ACTIVE"]},
        }
    )
    if active_runs > 0:
        return conflict(f"Cannot delete — {active_runs} active test run(s) on this fixture")

    # Undeploy MTIB servers and free assigned nodes before deleting
    freed_nodes = []
    for slot in (getattr(existing, "slots", None) or []):
        if slot.nodeId:
            _undeploy_mtib_for_slot(db, slot.nodeId)
            freed_nodes.append(slot.nodeId)

    # Check for any remaining sessions (must be archived+deleted first)
    remaining_sessions = db.manufacturingsession.count(where={"fixtureId": fixture_id})
    if remaining_sessions > 0:
        return conflict(
            f"Cannot delete fixture: {remaining_sessions} manufacturing session(s) still reference it. "
            "Archive and delete all sessions for this fixture first."
        )

    # Check for any remaining test runs
    remaining_runs = db.testrun.count(where={"fixtureId": fixture_id})
    if remaining_runs > 0:
        return conflict(
            f"Cannot delete fixture: {remaining_runs} test run(s) still reference it. "
            "Delete all associated sessions first."
        )

    # Disconnect queue entries (nullable FK)
    db.validationqueueentry.update_many(
        where={"fixtureId": fixture_id},
        data={"fixtureId": None},
    )

    db.fixture.delete(where={"id": fixture_id})
    log_audit("fixture.delete", "Fixture", fixture_id, {
        "name": existing.name, "type": existing.type, "freedNodes": freed_nodes,
    })
    return jsonify(ApiResponse.ok({"deleted": True}).to_dict()), 200


# ── Slots ──────────────────────────────────────────────────────


@require_permissions(Permissions.FIXTURES_MANAGE)
def create_slot(fixture_id: str):
    """Add a new slot to a fixture."""
    db = get_db_client()
    fixture = db.fixture.find_unique(where={"id": fixture_id})
    if not fixture:
        return not_found("Fixture not found")

    data, error = SlotCreateRequest.from_json(request.get_json())
    if error or data is None:
        return bad_request(error)

    # Check slotIndex uniqueness within fixture
    existing_slot = db.fixtureslot.find_first(
        where={"fixtureId": fixture_id, "slotIndex": data.slotIndex}
    )
    if existing_slot:
        return conflict(f"Slot with index {data.slotIndex} already exists in this fixture")

    slot_data = {
        "fixtureId": fixture_id,
        "slotIndex": data.slotIndex,
        "label": data.label,
    }
    # Copy optional fields that are set
    _optional_fields = (
        "jlinkAppSerial", "jlinkCommsSerial", "uartAppPath", "uartCommsPath",
        "dutDeviceId", "dutSnr", "dutImei", "dutIccids",
    )
    for field in _optional_fields:
        value = getattr(data, field, None)
        if value:
            slot_data[field] = value

    slot = db.fixtureslot.create(
        data=slot_data,
        include={"node": True},
    )
    log_audit("fixture.slot.create", "FixtureSlot", slot.id, {"fixtureId": fixture_id, "slotIndex": data.slotIndex})
    return jsonify(ApiResponse.ok(_serialize_slot(slot)).to_dict()), 201


@require_permissions(Permissions.FIXTURES_MANAGE)
def update_slot(fixture_id: str, slot_id: str):
    """Update a fixture slot's properties."""
    db = get_db_client()
    slot = db.fixtureslot.find_first(
        where={"id": slot_id, "fixtureId": fixture_id}
    )
    if not slot:
        return not_found("Slot not found")

    data, error = SlotUpdateRequest.from_json(request.get_json())
    if error or data is None:
        return bad_request(error)

    update_data = data.to_update_data()
    updated = db.fixtureslot.update(
        where={"id": slot_id},
        data=update_data,
        include={"node": True},
    )
    log_audit("fixture.slot.update", "FixtureSlot", slot_id, {"fixtureId": fixture_id, "changes": update_data})
    return jsonify(ApiResponse.ok(_serialize_slot(updated)).to_dict()), 200


@require_permissions(Permissions.FIXTURES_MANAGE)
def delete_slot(fixture_id: str, slot_id: str):
    """Delete a fixture slot if it has no assigned node."""
    db = get_db_client()
    slot = db.fixtureslot.find_first(
        where={"id": slot_id, "fixtureId": fixture_id},
        include={"testExecutions": True},
    )
    if not slot:
        return not_found("Slot not found")

    # Check if any test executions reference this slot
    if hasattr(slot, "testExecutions") and slot.testExecutions:
        return conflict("Cannot delete slot: it has associated test executions")

    db.fixtureslot.delete(where={"id": slot_id})
    log_audit("fixture.slot.delete", "FixtureSlot", slot_id, {"fixtureId": fixture_id, "slotIndex": slot.slotIndex})
    return jsonify(ApiResponse.ok({"deleted": True}).to_dict()), 200


@require_permissions(Permissions.FIXTURES_MANAGE)
def assign_slot_node(fixture_id: str, slot_id: str):
    """PUT /v2/fixtures/<id>/slots/<sid>/assign — assign or unassign a node.

    When a node is assigned, the MTIB server K8s Deployment is auto-created.
    When a node is unassigned, the deployment is auto-deleted.
    """
    db = get_db_client()

    fixture = db.fixture.find_unique(where={"id": fixture_id})
    if not fixture:
        return not_found("Fixture not found")

    slot = db.fixtureslot.find_first(
        where={"id": slot_id, "fixtureId": fixture_id}
    )
    if not slot:
        return not_found("Slot not found")

    data, error = SlotAssignRequest.from_json(request.get_json())
    if error or data is None:
        return bad_request(error)

    if data.nodeId is None:
        return _unassign_slot_node(db, fixture_id, slot_id, slot)

    return _assign_slot_node_to(db, fixture_id, slot_id, slot, fixture, data.nodeId)


def _unassign_slot_node(db, fixture_id: str, slot_id: str, slot):
    """Unassign a node from a slot — undeploy MTIB server and clear the link."""
    if slot.nodeId:
        _undeploy_mtib_for_slot(db, slot.nodeId)
    updated = db.fixtureslot.update(
        where={"id": slot_id},
        data={"nodeId": None},
        include={"node": True},
    )
    log_audit("fixture.slot.unassign", "FixtureSlot", slot_id, {
        "fixtureId": fixture_id, "previousNodeId": slot.nodeId,
    })
    return jsonify(ApiResponse.ok(_serialize_slot(updated)).to_dict()), 200


def _assign_slot_node_to(db, fixture_id: str, slot_id: str, slot, fixture, node_id: str):
    """Assign a node to a slot — validate, deploy MTIB, link the node."""
    node = db.node.find_unique(where={"id": node_id})
    if not node:
        return not_found("Node not found")

    if node.type != fixture.type:
        return bad_request(f"Node type '{node.type}' does not match fixture type '{fixture.type}'")

    existing_assignment = db.fixtureslot.find_first(where={"nodeId": node_id})
    if existing_assignment and existing_assignment.id != slot_id:
        return conflict(f"Node is already assigned to another slot (fixture slot {existing_assignment.id})")

    # If replacing a different node, undeploy the old one
    if slot.nodeId and slot.nodeId != node_id:
        _undeploy_mtib_for_slot(db, slot.nodeId)

    updated = db.fixtureslot.update(
        where={"id": slot_id},
        data={"nodeId": node_id},
        include={"node": True},
    )

    deploy_name = _deploy_mtib_for_slot(node, fixture, slot.slotIndex)
    if deploy_name:
        logger.info("Auto-deployed MTIB server %s for slot %d on %s", deploy_name, slot.slotIndex, node.hostname)

    log_audit("fixture.slot.assign", "FixtureSlot", slot_id, {
        "fixtureId": fixture_id, "nodeId": node_id,
        "previousNodeId": slot.nodeId, "deploymentName": deploy_name,
    })
    return jsonify(ApiResponse.ok(_serialize_slot(updated)).to_dict()), 200


# ── MTIB Deployment Helpers ──────────────────────────────────


def _mtib_env_for_fixture(fixture) -> dict[str, str]:
    """Build the env-var dict the MTIB server pod needs for this fixture.

    The fixture type is the single source of truth. Validation fixtures have
    a FluidNC linear rail wired up for motion-driven tests (vibration, IMU
    sweep, etc.) — the mtib-server's MotionStart RPC is gated behind
    MOTION_ENABLED=true. Manufacturing fixtures never have motion hardware,
    so the same flag stays false.

    If a future fixture needs a per-instance override (e.g. a validation
    bench without a rail), add it via Fixture.profileOverrides and read it
    here — but the default must match the type contract.
    """
    motion_enabled = "true" if fixture.type == "VALIDATION" else "false"
    return {"MOTION_ENABLED": motion_enabled}


def _deploy_mtib_for_slot(node, fixture, slot_index: int) -> str | None:
    """Deploy an MTIB server K8s Deployment for a node in a fixture slot.
    Stores the deployment name in Node.metadata["deployment_name"].
    After deployment, polls gRPC port 50053 on the node IP for up to 60s.
    """
    config: dict = {"env": _mtib_env_for_fixture(fixture)}
    deploy_name = create_mtib_deployment(
        node_hostname=node.hostname,
        fixture_id=fixture.id,
        deployment_id=f"fixture-{fixture.id[:8]}",
        slot_index=slot_index,
        config=config,
    )
    if deploy_name:
        db = get_db_client()
        meta = node.metadata if isinstance(node.metadata, dict) else {}
        meta["deployment_name"] = deploy_name
        # Stamp the deployment_name so subsequent serializations can map
        # the node back to its K8s deployment for live status. Reachability
        # is computed live — do not persist it.
        db.node.update(where={"id": node.id}, data={"metadata": Json(meta)})

        # gRPC health check — poll TCP 50053 on the node IP
        if node.ipAddress:
            healthy = _poll_grpc_health(node.ipAddress, 50053, timeout_s=60)
            if healthy:
                # Record the running image SHA for traceability
                try:
                    image_sha = get_mtib_pod_image_sha(deploy_name)
                    if image_sha:
                        meta["mtibImageSha"] = image_sha
                        db.node.update(where={"id": node.id}, data={"metadata": Json(meta)})
                except Exception as e:
                    logger.warning("Failed to get MTIB image SHA for %s: %s", deploy_name, e)

    return deploy_name


def _poll_grpc_health(host: str, port: int, timeout_s: int = 60) -> bool:
    """Poll a TCP port until it accepts connections or timeout is reached.

    This is a best-effort health check — failure is logged but does not
    block the deployment from being recorded.
    """
    deadline = time.monotonic() + timeout_s
    interval = 2.0
    while time.monotonic() < deadline:
        try:
            sock = socket.create_connection((host, port), timeout=3)
            sock.close()
            logger.info("gRPC health check passed: %s:%d", host, port)
            return True
        except (OSError, socket.timeout):
            time.sleep(interval)
    logger.warning("gRPC health check timed out after %ds: %s:%d", timeout_s, host, port)
    return False


def _undeploy_mtib_for_slot(db, node_id: str) -> bool:
    """Undeploy the MTIB server for a node. Clears Node.metadata["deployment_name"]."""
    node = db.node.find_unique(where={"id": node_id})
    if not node:
        return False

    meta = node.metadata if isinstance(node.metadata, dict) else {}
    deploy_name = meta.get("deployment_name")
    if not deploy_name:
        return True  # Nothing to undeploy

    delete_mtib_deployment(deploy_name)

    meta.pop("deployment_name", None)
    db.node.update(where={"id": node_id}, data={"metadata": Json(meta)})
    return True


# ── Fixture-Level Deploy/Undeploy/Status ─────────────────────


@require_permissions(Permissions.FIXTURES_MANAGE)
def deploy_fixture(fixture_id: str):
    """POST /v2/fixtures/<id>/deploy — deploy MTIB servers on all assigned slots."""
    db = get_db_client()
    fixture = db.fixture.find_unique(
        where={"id": fixture_id},
        include={"slots": {"include": {"node": True}}},
    )
    if not fixture:
        return not_found("Fixture not found")

    slots = fixture.slots or []
    assigned = [s for s in slots if s.nodeId and s.node]
    if not assigned:
        return bad_request("No nodes assigned to any slot")

    deployed = []
    failed = []
    for slot in assigned:
        name = _deploy_mtib_for_slot(slot.node, fixture, slot.slotIndex)
        if name:
            deployed.append({"slotIndex": slot.slotIndex, "hostname": slot.node.hostname, "deploymentName": name})
        else:
            failed.append({"slotIndex": slot.slotIndex, "hostname": slot.node.hostname, "error": "Deploy failed"})

    log_audit("fixture.deploy", "Fixture", fixture_id, {
        "deployed": len(deployed), "failed": len(failed),
    })
    return jsonify(ApiResponse.ok({
        "deployed": deployed, "failed": failed,
    }).to_dict()), 200


@require_permissions(Permissions.FIXTURES_MANAGE)
def undeploy_fixture(fixture_id: str):
    """POST /v2/fixtures/<id>/undeploy — undeploy all MTIB servers."""
    db = get_db_client()
    fixture = db.fixture.find_unique(
        where={"id": fixture_id},
        include={"slots": {"include": {"node": True}}},
    )
    if not fixture:
        return not_found("Fixture not found")

    sess_by, run_by = _load_active_holders(db, [fixture_id])
    if fixture_id in sess_by or fixture_id in run_by:
        return conflict("Cannot undeploy a locked fixture — a session is running")

    undeployed = []
    for slot in (fixture.slots or []):
        if slot.nodeId:
            success = _undeploy_mtib_for_slot(db, slot.nodeId)
            undeployed.append({"slotIndex": slot.slotIndex, "success": success})

    log_audit("fixture.undeploy", "Fixture", fixture_id, {"count": len(undeployed)})
    return jsonify(ApiResponse.ok({"undeployed": undeployed}).to_dict()), 200


@require_permissions(Permissions.FIXTURES_VIEW)
def get_fixture_deploy_status(fixture_id: str):
    """GET /v2/fixtures/<id>/deploy-status — per-slot MTIB deployment status."""
    db = get_db_client()
    fixture = db.fixture.find_unique(
        where={"id": fixture_id},
        include={"slots": {"include": {"node": True}}},
    )
    if not fixture:
        return not_found("Fixture not found")

    slot_statuses = []
    for slot in (fixture.slots or []):
        entry = {
            "slotIndex": slot.slotIndex,
            "label": slot.label,
            "nodeId": slot.nodeId,
            "hostname": slot.node.hostname if slot.node else None,
            "deployment": None,
        }
        if slot.node:
            meta = slot.node.metadata if isinstance(slot.node.metadata, dict) else {}
            deploy_name = meta.get("deployment_name")
            if deploy_name:
                try:
                    entry["deployment"] = get_mtib_deployment_status(deploy_name)
                except Exception:
                    entry["deployment"] = {"name": deploy_name, "status": "unknown"}
        slot_statuses.append(entry)

    return jsonify(ApiResponse.ok({"slots": slot_statuses}).to_dict()), 200


# ---------------------------------------------------------------------------
#  POST /v2/fixtures/batch — batch action on multiple fixtures
# ---------------------------------------------------------------------------


@require_permissions(Permissions.FIXTURES_MANAGE)
def batch_fixtures_action():
    """Apply an action to multiple fixtures at once."""
    db = get_db_client()
    body = request.get_json()
    if not body:
        return bad_request("Request body required")

    action = (body.get("action") or "").strip().lower()
    ids = body.get("ids", [])

    if action not in ("delete",):
        return bad_request("action must be 'delete'")
    if not isinstance(ids, list) or not ids:
        return bad_request("ids must be a non-empty array")

    succeeded = []
    failed = []

    for fid in ids:
        fixture = db.fixture.find_unique(
            where={"id": fid},
            include={"slots": True},
        )
        if not fixture:
            failed.append({"id": fid, "reason": "Not found"})
            continue

        # Check for active manufacturing sessions
        active_sessions = db.manufacturingsession.count(
            where={"fixtureId": fid, "status": "ACTIVE"}
        )
        if active_sessions > 0:
            failed.append({"id": fid, "reason": f"{active_sessions} active manufacturing session(s)"})
            continue

        # Check for active test runs
        active_runs = db.testrun.count(
            where={"fixtureId": fid, "status": {"in": ["ACTIVE"]}}
        )
        if active_runs > 0:
            failed.append({"id": fid, "reason": f"{active_runs} active test run(s)"})
            continue

        # Undeploy MTIB servers for each assigned slot before deleting
        for slot in (getattr(fixture, "slots", None) or []):
            if slot.nodeId:
                _undeploy_mtib_for_slot(db, slot.nodeId)

        db.fixture.delete(where={"id": fid})
        log_audit("fixture.delete", "Fixture", fid, {"batch": True})
        succeeded.append(fid)

    return jsonify(ApiResponse.ok({
        "action": action,
        "succeeded": succeeded,
        "failed": failed,
    }).to_dict()), 200
