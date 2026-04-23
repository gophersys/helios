"""Fixture-backed bench endpoints for validation infrastructure.

Legacy bench CRUD — now delegates to the unified Fixture model.
"""

import logging
import math
from datetime import datetime, timezone
from typing import Any, Dict

from database import Json
from flask import jsonify, request

from src.lib.audit import log_audit
from src.lib.decorators import require_permissions
from src.lib.errors import bad_request, conflict, internal_error, not_found
from src.lib.permissions import Permissions
from src.lib.types import ApiResponse
from src.services.database.prisma import get_db_client

from .types import BenchCreateRequest, BenchLockRequest, BenchUpdateRequest

try:
    from kubernetes import client as k8s_client, config as k8s_config
    _HAS_KUBERNETES = True
except ImportError:
    _HAS_KUBERNETES = False

logger = logging.getLogger(__name__)


def _serialize_bench(fixture, slot=None) -> Dict[str, Any]:
    """Serialize a Fixture + first FixtureSlot to the legacy bench API shape.

    Maintains backward compatibility for consumers expecting the old TestBench fields.
    """
    # Get first slot for DUT/hardware info
    if slot is None:
        slots = fixture.slots if hasattr(fixture, "slots") and fixture.slots else []
        slot = slots[0] if slots else None

    result = {
        "id": fixture.id,
        "stationId": fixture.stationId,
        "name": fixture.name,
        "status": fixture.status,
        "lockedBy": fixture.lockedBy,
        "lockedAt": fixture.lockedAt.isoformat() if fixture.lockedAt else None,
        "profileOverrides": fixture.profileOverrides if hasattr(fixture, "profileOverrides") else None,
        "lastHealthCheck": fixture.lastHealthCheck.isoformat() if hasattr(fixture, "lastHealthCheck") and fixture.lastHealthCheck else None,
        "metadata": fixture.metadata,
        "createdAt": fixture.createdAt.isoformat(),
        "updatedAt": fixture.updatedAt.isoformat(),
    }

    # Product info
    if hasattr(fixture, "product") and fixture.product:
        result["dutProduct"] = fixture.product.slug or fixture.product.name.lower()
    else:
        result["dutProduct"] = None
    result["productId"] = fixture.productId

    # Design info
    if hasattr(fixture, "design") and fixture.design:
        result["fixtureDesign"] = {
            "id": fixture.design.id,
            "name": fixture.design.name,
            "boardRevisionId": fixture.design.boardRevisionId,
            "revision": fixture.design.revision,
            "capabilities": fixture.design.capabilities or [],
        }
        result["dutRevision"] = fixture.design.revision
        result["capabilities"] = fixture.design.capabilities or []
        result["mtibRevision"] = fixture.design.revision
    else:
        result["fixtureDesign"] = None
        result["dutRevision"] = None
        result["capabilities"] = []
        result["mtibRevision"] = None

    # Slot-derived fields (hardware paths + DUT identity)
    if slot:
        result["dutDeviceId"] = slot.dutDeviceId
        result["dutSnr"] = slot.dutSnr
        result["dutImei"] = slot.dutImei
        result["dutIccids"] = slot.dutIccids or []
        result["jlinkAppSerial"] = slot.jlinkAppSerial
        result["jlinkCommsSerial"] = slot.jlinkCommsSerial
        result["uartAppPath"] = slot.uartAppPath
        result["uartCommsPath"] = slot.uartCommsPath
        # Derive MTIB address from slot's node
        if hasattr(slot, "node") and slot.node and slot.node.ipAddress:
            result["mtibAddress"] = f"{slot.node.ipAddress}:50053"
        else:
            result["mtibAddress"] = None
    else:
        result["dutDeviceId"] = None
        result["dutSnr"] = None
        result["dutImei"] = None
        result["dutIccids"] = []
        result["jlinkAppSerial"] = None
        result["jlinkCommsSerial"] = None
        result["uartAppPath"] = None
        result["uartCommsPath"] = None
        result["mtibAddress"] = None

    # Compute profile path
    dut_product = result.get("dutProduct") or "unknown"
    dut_revision = result.get("dutRevision") or "unknown"
    result["profilePath"] = f"/app/fixtures/{dut_product}_{dut_revision}.json"

    return result


@require_permissions(Permissions.FIXTURES_VIEW)
def list_benches():
    """GET /v2/fixtures/benches - List all fixtures as benches."""
    db = get_db_client()

    page = max(1, request.args.get("page", 1, type=int))
    limit = min(max(1, request.args.get("limit", 50, type=int)), 100)
    skip = (page - 1) * limit

    # Filters
    where: Dict[str, Any] = {}

    station_id = request.args.get("station_id")
    if station_id:
        where["stationId"] = station_id

    product = request.args.get("product")
    if product:
        where["product"] = {"slug": {"contains": product.lower()}}

    status = request.args.get("status")
    if status:
        where["status"] = status.upper()

    try:
        total = db.fixture.count(where=where)
        fixtures = db.fixture.find_many(
            where=where,
            skip=skip,
            take=limit,
            order={"createdAt": "desc"},
            include={
                "product": True,
                "design": True,
                "slots": {
                    "where": {"active": True},
                    "order_by": {"slotIndex": "asc"},
                    "include": {"node": True},
                },
            },
        )

        pages = math.ceil(total / limit) if limit > 0 else 0

        return jsonify(ApiResponse.ok({
            "data": [_serialize_bench(f) for f in fixtures],
            "pagination": {
                "page": page,
                "limit": limit,
                "total": total,
                "pages": pages,
            },
        }).to_dict()), 200

    except Exception as e:
        logger.error("Failed to list benches: %s", e)
        return internal_error("Failed to list benches")


@require_permissions(Permissions.FIXTURES_VIEW)
def get_bench(bench_id: str):
    """GET /v2/fixtures/benches/<id> - Get fixture as bench details."""
    db = get_db_client()

    try:
        fixture = db.fixture.find_unique(
            where={"id": bench_id},
            include={
                "product": True,
                "design": True,
                "slots": {
                    "where": {"active": True},
                    "order_by": {"slotIndex": "asc"},
                    "include": {"node": True},
                },
            },
        )
        if not fixture:
            return not_found(f"Bench not found: {bench_id}")

        return jsonify(ApiResponse.ok(_serialize_bench(fixture)).to_dict()), 200

    except Exception as e:
        logger.error("Failed to get bench %s: %s", bench_id, e)
        return internal_error("Failed to get bench")


@require_permissions(Permissions.FIXTURES_MANAGE)
def create_bench():
    """POST /v2/fixtures/benches - Create a new fixture (bench compat)."""
    data, error = BenchCreateRequest.from_json(request.get_json())
    if error or data is None:
        return bad_request(error)

    db = get_db_client()

    # Check for duplicate stationId
    if data.station_id:
        existing = db.fixture.find_first(where={"stationId": data.station_id})
        if existing:
            return conflict(f"Bench with stationId '{data.station_id}' already exists")

    # Look up product by slug match
    product_base = data.dut_product.lower().replace(" ", "").replace("_fw", "").replace("_mfg", "")
    product = db.product.find_first(where={"slug": {"contains": product_base[:5]}})
    if not product:
        return bad_request(f"No product found matching '{data.dut_product}'")

    try:
        # Create Fixture
        create_data = {
            "name": data.name,
            "stationId": data.station_id,
            "productId": product.id,
            "type": "VALIDATION",
            "status": "AVAILABLE",
        }
        if data.fixture_design_id:
            create_data["designId"] = data.fixture_design_id
        if data.profile_overrides:
            create_data["profileOverrides"] = Json(data.profile_overrides)
        if data.metadata:
            create_data["metadata"] = Json(data.metadata)

        fixture = db.fixture.create(
            data=create_data,
            include={"product": True, "design": True},
        )

        # Create first slot with hardware paths and DUT info
        slot_data = {
            "fixtureId": fixture.id,
            "slotIndex": 0,
            "label": "Primary",
        }
        if data.dut_device_id:
            slot_data["dutDeviceId"] = data.dut_device_id
        if data.dut_snr:
            slot_data["dutSnr"] = data.dut_snr
        if data.dut_imei:
            slot_data["dutImei"] = data.dut_imei
        if data.dut_iccids:
            slot_data["dutIccids"] = data.dut_iccids
        if data.jlink_app_serial:
            slot_data["jlinkAppSerial"] = data.jlink_app_serial
        if data.jlink_comms_serial:
            slot_data["jlinkCommsSerial"] = data.jlink_comms_serial
        if data.uart_app_path:
            slot_data["uartAppPath"] = data.uart_app_path
        if data.uart_comms_path:
            slot_data["uartCommsPath"] = data.uart_comms_path

        slot = db.fixtureslot.create(data=slot_data)

        log_audit("validation.bench.create", "Fixture", fixture.id, {
            "stationId": data.station_id,
            "dutProduct": data.dut_product,
        })

        return jsonify(ApiResponse.created(_serialize_bench(fixture, slot=slot)).to_dict()), 201

    except Exception as e:
        logger.error("Failed to create bench: %s", e)
        return internal_error("Failed to create bench")


@require_permissions(Permissions.FIXTURES_MANAGE)
def update_bench(bench_id: str):
    """PATCH /v2/fixtures/benches/<id> - Update a fixture (bench compat)."""
    data, error = BenchUpdateRequest.from_json(request.get_json())
    if error or data is None:
        return bad_request(error)

    db = get_db_client()

    fixture = db.fixture.find_unique(
        where={"id": bench_id},
        include={
            "slots": {
                "where": {"active": True},
                "order_by": {"slotIndex": "asc"},
            },
        },
    )
    if not fixture:
        return not_found(f"Bench not found: {bench_id}")

    update_data = data.to_update_data()
    if not update_data:
        return bad_request("No valid fields to update")

    # Separate fixture fields from slot fields
    slot_fields = {}
    fixture_fields = {}
    slot_keys = {
        "dutDeviceId", "dutSnr", "dutImei", "dutIccids",
        "jlinkAppSerial", "jlinkCommsSerial", "uartAppPath", "uartCommsPath",
    }
    fixture_key_map = {
        "name": "name",
        "mtibRevision": None,  # Stored in design now
        "capabilities": None,  # Stored in design now
        "fixtureDesignId": "designId",
        "profileOverrides": "profileOverrides",
        "status": "status",
        "metadata": "metadata",
    }

    for key, val in update_data.items():
        if key in slot_keys:
            slot_fields[key] = val
        elif key in fixture_key_map:
            mapped = fixture_key_map[key]
            if mapped:
                fixture_fields[mapped] = val

    # Handle metadata JSON wrapping
    if "metadata" in fixture_fields and fixture_fields["metadata"] is not None:
        fixture_fields["metadata"] = Json(fixture_fields["metadata"])
    if "profileOverrides" in fixture_fields and fixture_fields["profileOverrides"] is not None:
        fixture_fields["profileOverrides"] = Json(fixture_fields["profileOverrides"])

    try:
        if fixture_fields:
            db.fixture.update(where={"id": bench_id}, data=fixture_fields)

        # Update first slot if slot fields provided
        if slot_fields and fixture.slots:
            first_slot = fixture.slots[0]
            db.fixtureslot.update(where={"id": first_slot.id}, data=slot_fields)

        # Re-fetch with includes
        updated = db.fixture.find_unique(
            where={"id": bench_id},
            include={
                "product": True,
                "design": True,
                "slots": {
                    "where": {"active": True},
                    "order_by": {"slotIndex": "asc"},
                    "include": {"node": True},
                },
            },
        )

        log_audit("validation.bench.update", "Fixture", bench_id, update_data)

        return jsonify(ApiResponse.ok(_serialize_bench(updated)).to_dict()), 200

    except Exception as e:
        logger.error("Failed to update bench %s: %s", bench_id, e)
        return internal_error("Failed to update bench")


@require_permissions(Permissions.FIXTURES_MANAGE)
def delete_bench(bench_id: str):
    """DELETE /v2/fixtures/benches/<id> - Delete a fixture (bench compat)."""
    db = get_db_client()

    fixture = db.fixture.find_unique(where={"id": bench_id})
    if not fixture:
        return not_found(f"Bench not found: {bench_id}")

    if fixture.status == "LOCKED":
        return bad_request("Cannot delete a locked bench")

    try:
        db.fixture.delete(where={"id": bench_id})

        log_audit("validation.bench.delete", "Fixture", bench_id, {
            "stationId": fixture.stationId,
        })

        return jsonify(ApiResponse.deleted().to_dict()), 200

    except Exception as e:
        logger.error("Failed to delete bench %s: %s", bench_id, e)
        return internal_error("Failed to delete bench")


@require_permissions(Permissions.FIXTURES_MANAGE)
def lock_bench(bench_id: str):
    """POST /v2/fixtures/benches/<id>/lock - Lock a fixture for exclusive use."""
    data, error = BenchLockRequest.from_json(request.get_json())
    if error or data is None:
        return bad_request(error)

    db = get_db_client()

    fixture = db.fixture.find_unique(where={"id": bench_id})
    if not fixture:
        return not_found(f"Bench not found: {bench_id}")

    if fixture.status == "LOCKED":
        return conflict(f"Bench already locked by: {fixture.lockedBy}")

    if fixture.status in ("OFFLINE", "MAINTENANCE"):
        return bad_request(f"Bench not available: {fixture.status}")

    try:
        db.fixture.update(
            where={"id": bench_id},
            data={
                "status": "LOCKED",
                "lockedBy": data.locked_by,
                "lockedAt": datetime.now(timezone.utc),
            },
        )

        updated = db.fixture.find_unique(
            where={"id": bench_id},
            include={
                "product": True,
                "design": True,
                "slots": {
                    "where": {"active": True},
                    "order_by": {"slotIndex": "asc"},
                    "include": {"node": True},
                },
            },
        )

        log_audit("validation.bench.lock", "Fixture", bench_id, {
            "lockedBy": data.locked_by,
        })

        return jsonify(ApiResponse.ok(_serialize_bench(updated)).to_dict()), 200

    except Exception as e:
        logger.error("Failed to lock bench %s: %s", bench_id, e)
        return internal_error("Failed to lock bench")


@require_permissions(Permissions.FIXTURES_MANAGE)
def unlock_bench(bench_id: str):
    """POST /v2/fixtures/benches/<id>/unlock - Release a fixture lock."""
    db = get_db_client()

    fixture = db.fixture.find_unique(where={"id": bench_id})
    if not fixture:
        return not_found(f"Bench not found: {bench_id}")

    if fixture.status != "LOCKED":
        return bad_request("Bench is not locked")

    try:
        db.fixture.update(
            where={"id": bench_id},
            data={
                "status": "AVAILABLE",
                "lockedBy": None,
                "lockedAt": None,
            },
        )

        updated = db.fixture.find_unique(
            where={"id": bench_id},
            include={
                "product": True,
                "design": True,
                "slots": {
                    "where": {"active": True},
                    "order_by": {"slotIndex": "asc"},
                    "include": {"node": True},
                },
            },
        )

        log_audit("validation.bench.unlock", "Fixture", bench_id, {
            "previousLockedBy": fixture.lockedBy,
        })

        return jsonify(ApiResponse.ok(_serialize_bench(updated)).to_dict()), 200

    except Exception as e:
        logger.error("Failed to unlock bench %s: %s", bench_id, e)
        return internal_error("Failed to unlock bench")


@require_permissions(Permissions.FIXTURES_VIEW)
def discover_mtibs():
    """GET /v2/fixtures/benches/discover - Find unregistered MTIBs in K8s cluster."""
    db = get_db_client()

    try:
        if not _HAS_KUBERNETES:
            logger.warning("kubernetes package not installed, returning mock data")
            nodes = type("MockNodeList", (), {"items": []})()
        else:
            try:
                try:
                    k8s_config.load_incluster_config()
                except k8s_config.ConfigException:
                    k8s_config.load_kube_config()

                v1 = k8s_client.CoreV1Api()
                nodes = v1.list_node(label_selector="node.corekinect.com/type=mtib")
            except Exception as e:
                logger.warning("Failed to connect to K8s API: %s", e)
                nodes = type("MockNodeList", (), {"items": []})()

        # Get all registered fixture slot node IPs (via slot -> node)
        registered_addresses = set()
        all_slots = db.fixtureslot.find_many(
            where={"nodeId": {"not": None}},
            include={"node": True},
        )
        for slot in all_slots:
            if hasattr(slot, "node") and slot.node and slot.node.ipAddress:
                registered_addresses.add(slot.node.ipAddress)

        # Get all registered Node hostnames and IPs
        registered_nodes = db.node.find_many()
        registered_node_hostnames = {n.hostname for n in registered_nodes}
        registered_node_ips = {n.ipAddress for n in registered_nodes if n.ipAddress}

        # Find unregistered nodes
        unregistered = []
        for node in nodes.items:
            ip = None
            for addr in node.status.addresses or []:
                if addr.type == "InternalIP":
                    ip = addr.address
                    break

            hostname = node.metadata.name
            has_fixture = ip in registered_addresses if ip else False
            has_node = hostname in registered_node_hostnames or (ip in registered_node_ips if ip else False)

            if ip and not has_fixture:
                unregistered.append({
                    "hostname": hostname,
                    "ip": ip,
                    "mtibAddress": f"{ip}:50053",
                    "labels": dict(node.metadata.labels or {}),
                    "hardwareRevision": (node.metadata.labels or {}).get(
                        "node.corekinect.com/mtib-revision"
                    ),
                    "ready": any(
                        c.type == "Ready" and c.status == "True"
                        for c in (node.status.conditions or [])
                    ),
                    "hasNodeRecord": has_node,
                })

        return jsonify(ApiResponse.ok(unregistered).to_dict()), 200

    except Exception as e:
        logger.error("Failed to discover MTIBs: %s", e)
        return internal_error("Failed to discover MTIBs")


@require_permissions(Permissions.FIXTURES_VIEW)
def get_bench_profile(bench_id: str):
    """GET /v2/fixtures/benches/<id>/profile - Get resolved fixture profile."""
    db = get_db_client()

    try:
        fixture = db.fixture.find_unique(
            where={"id": bench_id},
            include={
                "product": True,
                "design": True,
                "slots": {
                    "where": {"active": True},
                    "order_by": {"slotIndex": "asc"},
                },
            },
        )
        if not fixture:
            return not_found(f"Bench not found: {bench_id}")

        # Start with design template or empty dict
        profile = {}
        if hasattr(fixture, "design") and fixture.design and fixture.design.profileTemplate:
            profile = dict(fixture.design.profileTemplate)

        # Apply fixture-specific overrides
        if fixture.profileOverrides:
            _deep_merge(profile, fixture.profileOverrides)

        # Inject station info
        profile["station_id"] = fixture.stationId

        # Inject DUT info from first slot
        slots = fixture.slots or []
        if slots:
            slot = slots[0]
            if slot.dutDeviceId:
                if "dut" not in profile:
                    profile["dut"] = {}
                profile["dut"]["device_id"] = slot.dutDeviceId
            if slot.dutSnr:
                if "dut" not in profile:
                    profile["dut"] = {}
                profile["dut"]["snr"] = slot.dutSnr
            if slot.dutImei:
                if "dut" not in profile:
                    profile["dut"] = {}
                profile["dut"]["imei"] = slot.dutImei
            if slot.dutIccids:
                if "dut" not in profile:
                    profile["dut"] = {}
                profile["dut"]["iccids"] = slot.dutIccids

            # Inject hardware paths
            if slot.uartAppPath:
                profile["uart_app_path"] = slot.uartAppPath
            if slot.uartCommsPath:
                profile["uart_comms_path"] = slot.uartCommsPath
            if slot.jlinkAppSerial:
                profile["jlink_app_serial"] = slot.jlinkAppSerial
            if slot.jlinkCommsSerial:
                profile["jlink_comms_serial"] = slot.jlinkCommsSerial

        # Set capabilities from design
        if hasattr(fixture, "design") and fixture.design and fixture.design.capabilities:
            profile["capabilities"] = fixture.design.capabilities

        # Inject Product metadata
        if hasattr(fixture, "product") and fixture.product:
            product = fixture.product
            profile["product"] = {
                "id": product.id,
                "name": product.name,
                "slug": product.slug,
            }
            if product.metadata and isinstance(product.metadata, dict):
                profile["product"].update(product.metadata)

        return jsonify(ApiResponse.ok(profile).to_dict()), 200

    except Exception as e:
        logger.error("Failed to get bench profile %s: %s", bench_id, e)
        return internal_error("Failed to get bench profile")


def _deep_merge(base: dict, overrides: dict) -> None:
    """Deep merge overrides into base dict (mutates base)."""
    for key, value in overrides.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value
