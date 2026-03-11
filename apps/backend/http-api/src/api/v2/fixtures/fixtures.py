import logging
import math
from typing import Any

from flask import jsonify, request
from database import Json

from src.lib.audit import log_audit
from src.lib.decorators import require_permissions
from src.lib.errors import bad_request, conflict, not_found
from src.lib.permissions import Permissions
from src.lib.types import ApiResponse
from src.services.database.prisma import get_db_client

from .types import FixtureCreateRequest, FixtureUpdateRequest, SlotCreateRequest, SlotUpdateRequest, SlotAssignRequest

logger = logging.getLogger(__name__)


# ── Dashboard ─────────────────────────────────────────────────


@require_permissions(Permissions.FIXTURES_VIEW)
def dashboard_overview():
    db = get_db_client()

    fixtures = db.fixture.find_many(
        order={"name": "asc"},
        include={
            "product": True,
            "slots": {"include": {"node": True}},
        },
    )

    results = []
    for f in fixtures:
        slots = f.slots or []
        slot_count = len(slots)
        assigned_slots = [s for s in slots if s.nodeId is not None]
        assigned_count = len(assigned_slots)

        nodes_online = 0
        nodes_offline = 0
        nodes_error = 0
        for s in assigned_slots:
            if hasattr(s, "node") and s.node:
                status = s.node.status
                if status == "ONLINE":
                    nodes_online += 1
                elif status == "ERROR":
                    nodes_error += 1
                else:
                    nodes_offline += 1

        # Derive health
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

        # Deployment info
        deployments = f.deployments if hasattr(f, "deployments") and f.deployments else []
        has_active = False
        active_status = None
        if deployments:
            latest = deployments[0]
            if latest.status in ("RUNNING", "PENDING"):
                has_active = True
                active_status = latest.status

        results.append({
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
            "hasActiveDeployment": has_active,
            "activeDeploymentStatus": active_status,
            "updatedAt": f.updatedAt.isoformat(),
        })

    return jsonify(ApiResponse.ok(results).to_dict()), 200


# ── Serializers ────────────────────────────────────────────────


def _serialize_fixture(f: Any, include_slots: bool = False) -> dict:
    data = {
        "id": f.id,
        "name": f.name,
        "productId": f.productId,
        "type": f.type,
        "description": f.description,
        "active": f.active,
        "metadata": f.metadata,
        "createdAt": f.createdAt.isoformat(),
        "updatedAt": f.updatedAt.isoformat(),
    }
    if hasattr(f, "product") and f.product:
        data["productName"] = f.product.name
    if hasattr(f, "slots") and f.slots is not None:
        data["slotCount"] = len(f.slots)
        if include_slots:
            data["slots"] = [_serialize_slot(s) for s in f.slots]
    return data


def _serialize_slot(s: Any) -> dict:
    data = {
        "id": s.id,
        "fixtureId": s.fixtureId,
        "slotIndex": s.slotIndex,
        "label": s.label,
        "nodeId": s.nodeId,
        "active": s.active,
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

    # Build create payload
    create_data: dict = {
        "name": data.name,
        "productId": data.productId,
        "type": data.type,
        "description": data.description,
    }
    if data.metadata is not None:
        create_data["metadata"] = Json(data.metadata)

    # Create initial slots if provided
    if data.slots:
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
    db = get_db_client()
    fixture = db.fixture.find_unique(
        where={"id": fixture_id},
        include={
            "product": True,
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
    data, error = FixtureUpdateRequest.from_json(request.get_json())
    if error:
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
    db = get_db_client()
    existing = db.fixture.find_unique(
        where={"id": fixture_id},
        include={"sessions": True, "deployments": True},
    )
    if not existing:
        return not_found("Fixture not found")

    # Check for active sessions
    if hasattr(existing, "sessions") and existing.sessions:
        return conflict("Cannot delete fixture: it has associated sessions")

    # Check for active deployments
    if hasattr(existing, "deployments") and existing.deployments:
        return conflict("Cannot delete fixture: it has associated deployments")

    db.fixture.delete(where={"id": fixture_id})
    log_audit("fixture.delete", "Fixture", fixture_id, {"name": existing.name, "type": existing.type})
    return jsonify(ApiResponse.ok({"deleted": True}).to_dict()), 200


# ── Slots ──────────────────────────────────────────────────────


@require_permissions(Permissions.FIXTURES_MANAGE)
def create_slot(fixture_id: str):
    db = get_db_client()
    fixture = db.fixture.find_unique(where={"id": fixture_id})
    if not fixture:
        return not_found("Fixture not found")

    data, error = SlotCreateRequest.from_json(request.get_json())
    if error:
        return bad_request(error)

    # Check slotIndex uniqueness within fixture
    existing_slot = db.fixtureslot.find_first(
        where={"fixtureId": fixture_id, "slotIndex": data.slotIndex}
    )
    if existing_slot:
        return conflict(f"Slot with index {data.slotIndex} already exists in this fixture")

    slot = db.fixtureslot.create(
        data={
            "fixtureId": fixture_id,
            "slotIndex": data.slotIndex,
            "label": data.label,
        },
        include={"node": True},
    )
    log_audit("fixture.slot.create", "FixtureSlot", slot.id, {"fixtureId": fixture_id, "slotIndex": data.slotIndex})
    return jsonify(ApiResponse.ok(_serialize_slot(slot)).to_dict()), 201


@require_permissions(Permissions.FIXTURES_MANAGE)
def update_slot(fixture_id: str, slot_id: str):
    db = get_db_client()
    slot = db.fixtureslot.find_first(
        where={"id": slot_id, "fixtureId": fixture_id}
    )
    if not slot:
        return not_found("Slot not found")

    data, error = SlotUpdateRequest.from_json(request.get_json())
    if error:
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
    db = get_db_client()

    # Verify fixture exists
    fixture = db.fixture.find_unique(where={"id": fixture_id})
    if not fixture:
        return not_found("Fixture not found")

    # Verify slot exists and belongs to fixture
    slot = db.fixtureslot.find_first(
        where={"id": slot_id, "fixtureId": fixture_id}
    )
    if not slot:
        return not_found("Slot not found")

    data, error = SlotAssignRequest.from_json(request.get_json())
    if error:
        return bad_request(error)

    if data.nodeId is None:
        # Unassign node
        updated = db.fixtureslot.update(
            where={"id": slot_id},
            data={"nodeId": None},
            include={"node": True},
        )
        log_audit("fixture.slot.unassign", "FixtureSlot", slot_id, {"fixtureId": fixture_id, "previousNodeId": slot.nodeId})
        return jsonify(ApiResponse.ok(_serialize_slot(updated)).to_dict()), 200

    # Verify node exists
    node = db.node.find_unique(where={"id": data.nodeId})
    if not node:
        return not_found("Node not found")

    # Verify node type matches fixture type
    if node.type != fixture.type:
        return bad_request(f"Node type '{node.type}' does not match fixture type '{fixture.type}'")

    # Check if node is already assigned to a different slot
    existing_assignment = db.fixtureslot.find_first(
        where={"nodeId": data.nodeId}
    )
    if existing_assignment and existing_assignment.id != slot_id:
        return conflict(f"Node is already assigned to another slot (fixture slot {existing_assignment.id})")

    updated = db.fixtureslot.update(
        where={"id": slot_id},
        data={"nodeId": data.nodeId},
        include={"node": True},
    )
    log_audit("fixture.slot.assign", "FixtureSlot", slot_id, {"fixtureId": fixture_id, "nodeId": data.nodeId, "previousNodeId": slot.nodeId})
    return jsonify(ApiResponse.ok(_serialize_slot(updated)).to_dict()), 200
