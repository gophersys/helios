import logging
import math
from typing import Any

from flask import g, jsonify, request
from database import Json

from src.lib.audit import log_audit
from src.lib.decorators import require_auth, require_permissions
from src.lib.errors import bad_request, conflict, not_found
from src.lib.permissions import Permissions
from src.lib.types import ApiResponse
from src.services.database.prisma import get_db_client

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
    from src.lib.decorators import _get_permissions_for_set

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

        for f in fixtures:
            slots = f.slots or []
            slot_count = len(slots)
            assigned_slots = [s for s in slots if s.nodeId is not None]
            assigned_count = len(assigned_slots)

            nodes_online = nodes_offline = nodes_error = 0
            for s in assigned_slots:
                if hasattr(s, "node") and s.node:
                    status = s.node.status
                    if status == "ONLINE":
                        nodes_online += 1
                    elif status == "ERROR":
                        nodes_error += 1
                    else:
                        nodes_offline += 1

            if slot_count == 0:
                health = "EMPTY"
            elif assigned_count == 0:
                health = "UNASSIGNED"
            elif nodes_error > 0:
                health = "ERROR"
            elif nodes_offline > 0:
                health = "DEGRADED"
            elif nodes_online == assigned_count:
                health = "HEALTHY"
            else:
                health = "UNKNOWN"

            fixture_results.append({
                "id": f.id,
                "name": f.name,
                "type": f.type,
                "active": f.active,
                "productName": f.product.name if hasattr(f, "product") and f.product else None,
                "productId": f.productId,
                "slotCount": slot_count,
                "assignedCount": assigned_count,
                "nodesOnline": nodes_online,
                "nodesOffline": nodes_offline,
                "nodesError": nodes_error,
                "health": health,
                "updatedAt": f.updatedAt.isoformat(),
            })

    if "fixtures:view" in perms or is_admin:
        stats["fixtures"] = {
            "total": len(fixture_results),
            "online": sum(1 for f in fixture_results if f["health"] == "HEALTHY"),
            "degraded": sum(1 for f in fixture_results if f["health"] in ("DEGRADED", "ERROR")),
        }

    return jsonify(ApiResponse.ok({
        "stats": stats,
        "fixtures": fixture_results,
    }).to_dict()), 200


# ── Serializers ────────────────────────────────────────────────


def _serialize_fixture(f: Any, include_slots: bool = False) -> dict:
    """Serialize a Fixture DB record to an API response dict."""
    data = {
        "id": f.id,
        "name": f.name,
        "stationId": f.stationId if hasattr(f, "stationId") else None,
        "productId": f.productId,
        "type": f.type,
        "designId": f.designId if hasattr(f, "designId") else None,
        "boardRevisionId": f.boardRevisionId if hasattr(f, "boardRevisionId") else None,
        "status": f.status if hasattr(f, "status") else "AVAILABLE",
        "lockedBy": f.lockedBy if hasattr(f, "lockedBy") else None,
        "lockedAt": f.lockedAt.isoformat() if hasattr(f, "lockedAt") and f.lockedAt else None,
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
            "capabilities": f.design.capabilities or [],
        }
    if hasattr(f, "slots") and f.slots is not None:
        data["slotCount"] = len(f.slots)
        data["assignedCount"] = len([s for s in f.slots if s.nodeId is not None])
        if include_slots:
            data["slots"] = [_serialize_slot(s) for s in f.slots]
    return data


def _serialize_slot(s: Any) -> dict:
    """Serialize a FixtureSlot DB record to an API response dict."""
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
        data["node"] = {
            "id": s.node.id,
            "name": s.node.name,
            "hostname": s.node.hostname,
            "type": s.node.type,
            "status": s.node.status,
        }
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

    total = db.fixture.count(where=where)
    fixtures = db.fixture.find_many(
        where=where,
        skip=skip,
        take=limit,
        order={"name": "asc"},
        include={"product": True, "slots": True},
    )
    return jsonify(ApiResponse.ok({
        "data": [_serialize_fixture(f) for f in fixtures],
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
    return jsonify(ApiResponse.ok(_serialize_fixture(fixture, include_slots=True)).to_dict()), 200


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
    from src.lib.errors import bad_request, conflict, not_found

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


def _deploy_mtib_for_slot(node, fixture, slot_index: int) -> str | None:
    """Deploy an MTIB server K8s Deployment for a node in a fixture slot.
    Stores the deployment name in Node.metadata["deployment_name"].
    After deployment, polls gRPC port 50053 on the node IP for up to 60s.
    """
    try:
        from src.services.kubernetes.mtib_deployments import create_mtib_deployment
    except ImportError:
        logger.warning("K8s client not available — skipping MTIB deploy for %s", node.hostname)
        return None

    config: dict = {"env": {}}
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
        db.node.update(where={"id": node.id}, data={"metadata": Json(meta), "status": "ONLINE"})

        # gRPC health check — poll TCP 50053 on the node IP
        if node.ipAddress:
            _poll_grpc_health(node.ipAddress, 50053, timeout_s=60)

    return deploy_name


def _poll_grpc_health(host: str, port: int, timeout_s: int = 60) -> bool:
    """Poll a TCP port until it accepts connections or timeout is reached.

    This is a best-effort health check — failure is logged but does not
    block the deployment from being recorded.
    """
    import socket
    import time

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

    try:
        from src.services.kubernetes.mtib_deployments import delete_mtib_deployment
        delete_mtib_deployment(deploy_name)
    except ImportError:
        logger.warning("K8s client not available — skipping MTIB undeploy for %s", node.hostname)

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

    if fixture.status == "LOCKED":
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

    from src.services.kubernetes.mtib_deployments import get_mtib_deployment_status

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
