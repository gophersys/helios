"""TestBench CRUD endpoints for validation infrastructure."""

import logging
import math
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from database import Json
from flask import jsonify, request

from src.lib.audit import log_audit
from src.lib.decorators import require_permissions
from src.lib.errors import bad_request, conflict, internal_error, not_found
from src.lib.permissions import Permissions
from src.lib.types import ApiResponse
from src.services.database.prisma import get_db_client

from .types import BenchCreateRequest, BenchLockRequest, BenchUpdateRequest

logger = logging.getLogger(__name__)


def _serialize_bench(bench) -> Dict[str, Any]:
    """Serialize a TestBench model to API response."""
    result = {
        "id": bench.id,
        "stationId": bench.stationId,
        "name": bench.name,
        "mtibAddress": bench.mtibAddress,
        "mtibRevision": bench.mtibRevision,
        "capabilities": bench.capabilities or [],
        "fixtureDesignId": bench.fixtureDesignId,
        "profileOverrides": bench.profileOverrides,
        "dutProduct": bench.dutProduct,
        "dutRevision": bench.dutRevision,
        "dutDeviceId": bench.dutDeviceId,
        "dutSnr": bench.dutSnr,
        "dutImei": bench.dutImei,
        "dutIccids": bench.dutIccids or [],
        "jlinkAppSerial": bench.jlinkAppSerial,
        "jlinkCommsSerial": bench.jlinkCommsSerial,
        "uartAppPath": bench.uartAppPath,
        "uartCommsPath": bench.uartCommsPath,
        "status": bench.status,
        "lockedBy": bench.lockedBy,
        "lockedAt": bench.lockedAt.isoformat() if bench.lockedAt else None,
        "lastHealthCheck": bench.lastHealthCheck.isoformat() if bench.lastHealthCheck else None,
        "metadata": bench.metadata,
        "createdAt": bench.createdAt.isoformat(),
        "updatedAt": bench.updatedAt.isoformat(),
        # Compute profile path from product/revision (used by validation K8s jobs)
        "profilePath": f"/app/fixtures/{bench.dutProduct}_{bench.dutRevision}.json",
    }

    # Include fixture design info if loaded
    if hasattr(bench, "fixtureDesign") and bench.fixtureDesign:
        result["fixtureDesign"] = {
            "id": bench.fixtureDesign.id,
            "name": bench.fixtureDesign.name,
            "product": bench.fixtureDesign.product,
            "revision": bench.fixtureDesign.revision,
            "capabilities": bench.fixtureDesign.capabilities or [],
        }

    return result


@require_permissions(Permissions.ADMIN_VALIDATION_VIEW)
def list_benches():
    """GET /v2/validation/benches - List all test benches."""
    db = get_db_client()

    page = max(1, request.args.get("page", 1, type=int))
    limit = min(max(1, request.args.get("limit", 50, type=int)), 100)
    skip = (page - 1) * limit

    # Filters
    where: Dict[str, Any] = {}

    product = request.args.get("product")
    if product:
        where["dutProduct"] = product.lower()

    status = request.args.get("status")
    if status:
        where["status"] = status.upper()

    capabilities = request.args.getlist("capability")
    if capabilities:
        where["capabilities"] = {"hasEvery": capabilities}

    try:
        total = db.testbench.count(where=where)
        benches = db.testbench.find_many(
            where=where,
            skip=skip,
            take=limit,
            order={"createdAt": "desc"},
            include={"fixtureDesign": True},
        )

        pages = math.ceil(total / limit) if limit > 0 else 0

        return jsonify(ApiResponse.paginated(
            data=[_serialize_bench(b) for b in benches],
            page=page,
            total_pages=pages,
            total_results=total,
            results_per_page=limit,
        ).to_dict()), 200

    except Exception as e:
        logger.error("Failed to list benches: %s", e)
        return internal_error("Failed to list benches")


@require_permissions(Permissions.ADMIN_VALIDATION_VIEW)
def get_bench(bench_id: str):
    """GET /v2/validation/benches/<id> - Get bench details."""
    db = get_db_client()

    try:
        bench = db.testbench.find_unique(
            where={"id": bench_id},
            include={"fixtureDesign": True},
        )
        if not bench:
            return not_found(f"Bench not found: {bench_id}")

        return jsonify(ApiResponse.ok(_serialize_bench(bench)).to_dict()), 200

    except Exception as e:
        logger.error("Failed to get bench %s: %s", bench_id, e)
        return internal_error("Failed to get bench")


@require_permissions(Permissions.ADMIN_VALIDATION_MANAGE)
def create_bench():
    """POST /v2/validation/benches - Create a new test bench."""
    data, error = BenchCreateRequest.from_json(request.get_json())
    if error:
        return bad_request(error)

    db = get_db_client()

    # Check for duplicate stationId
    existing = db.testbench.find_unique(where={"stationId": data.station_id})
    if existing:
        return conflict(f"Bench with stationId '{data.station_id}' already exists")

    # If fixture design specified, validate it exists and inherit capabilities
    if data.fixture_design_id:
        design = db.fixturedesign.find_unique(where={"id": data.fixture_design_id})
        if not design:
            return not_found(f"Fixture design not found: {data.fixture_design_id}")
        # Inherit capabilities from design if not explicitly provided
        if not data.capabilities:
            data.capabilities = design.capabilities or []

    try:
        create_data = {
            "stationId": data.station_id,
            "name": data.name,
            "mtibAddress": data.mtib_address,
            "capabilities": data.capabilities,
            "dutProduct": data.dut_product.lower(),
            "dutRevision": data.dut_revision.lower(),
            "status": "AVAILABLE",
        }
        # Optional fields
        if data.fixture_design_id:
            create_data["fixtureDesignId"] = data.fixture_design_id
        if data.profile_overrides:
            create_data["profileOverrides"] = Json(data.profile_overrides)
        if data.mtib_revision:
            create_data["mtibRevision"] = data.mtib_revision
        if data.dut_device_id:
            create_data["dutDeviceId"] = data.dut_device_id
        if data.dut_snr:
            create_data["dutSnr"] = data.dut_snr
        if data.dut_imei:
            create_data["dutImei"] = data.dut_imei
        if data.dut_iccids:
            create_data["dutIccids"] = data.dut_iccids
        if data.jlink_app_serial:
            create_data["jlinkAppSerial"] = data.jlink_app_serial
        if data.jlink_comms_serial:
            create_data["jlinkCommsSerial"] = data.jlink_comms_serial
        if data.uart_app_path:
            create_data["uartAppPath"] = data.uart_app_path
        if data.uart_comms_path:
            create_data["uartCommsPath"] = data.uart_comms_path
        if data.metadata:
            create_data["metadata"] = Json(data.metadata)

        bench = db.testbench.create(data=create_data)

        log_audit("validation.bench.create", "TestBench", bench.id, {
            "stationId": data.station_id,
            "dutProduct": data.dut_product,
        })

        return jsonify(ApiResponse.created(_serialize_bench(bench)).to_dict()), 201

    except Exception as e:
        logger.error("Failed to create bench: %s", e)
        return internal_error("Failed to create bench")


@require_permissions(Permissions.ADMIN_VALIDATION_MANAGE)
def update_bench(bench_id: str):
    """PATCH /v2/validation/benches/<id> - Update a test bench."""
    data, error = BenchUpdateRequest.from_json(request.get_json())
    if error:
        return bad_request(error)

    db = get_db_client()

    bench = db.testbench.find_unique(where={"id": bench_id})
    if not bench:
        return not_found(f"Bench not found: {bench_id}")

    update_data = data.to_update_data()
    if not update_data:
        return bad_request("No valid fields to update")

    # Handle metadata JSON wrapping
    if "metadata" in update_data:
        update_data["metadata"] = Json(update_data["metadata"]) if update_data["metadata"] else None

    try:
        updated = db.testbench.update(
            where={"id": bench_id},
            data=update_data,
        )

        log_audit("validation.bench.update", "TestBench", bench_id, update_data)

        return jsonify(ApiResponse.ok(_serialize_bench(updated)).to_dict()), 200

    except Exception as e:
        logger.error("Failed to update bench %s: %s", bench_id, e)
        return internal_error("Failed to update bench")


@require_permissions(Permissions.ADMIN_VALIDATION_MANAGE)
def delete_bench(bench_id: str):
    """DELETE /v2/validation/benches/<id> - Delete a test bench."""
    db = get_db_client()

    bench = db.testbench.find_unique(where={"id": bench_id})
    if not bench:
        return not_found(f"Bench not found: {bench_id}")

    if bench.status == "LOCKED":
        return bad_request("Cannot delete a locked bench")

    try:
        db.testbench.delete(where={"id": bench_id})

        log_audit("validation.bench.delete", "TestBench", bench_id, {
            "stationId": bench.stationId,
        })

        return jsonify(ApiResponse.deleted().to_dict()), 200

    except Exception as e:
        logger.error("Failed to delete bench %s: %s", bench_id, e)
        return internal_error("Failed to delete bench")


@require_permissions(Permissions.ADMIN_VALIDATION_MANAGE)
def lock_bench(bench_id: str):
    """POST /v2/validation/benches/<id>/lock - Lock a bench for exclusive use."""
    data, error = BenchLockRequest.from_json(request.get_json())
    if error:
        return bad_request(error)

    db = get_db_client()

    bench = db.testbench.find_unique(where={"id": bench_id})
    if not bench:
        return not_found(f"Bench not found: {bench_id}")

    if bench.status == "LOCKED":
        return conflict(f"Bench already locked by: {bench.lockedBy}")

    if bench.status in ("OFFLINE", "MAINTENANCE"):
        return bad_request(f"Bench not available: {bench.status}")

    try:
        updated = db.testbench.update(
            where={"id": bench_id},
            data={
                "status": "LOCKED",
                "lockedBy": data.locked_by,
                "lockedAt": datetime.now(timezone.utc),
            },
        )

        log_audit("validation.bench.lock", "TestBench", bench_id, {
            "lockedBy": data.locked_by,
        })

        return jsonify(ApiResponse.ok(_serialize_bench(updated)).to_dict()), 200

    except Exception as e:
        logger.error("Failed to lock bench %s: %s", bench_id, e)
        return internal_error("Failed to lock bench")


@require_permissions(Permissions.ADMIN_VALIDATION_MANAGE)
def unlock_bench(bench_id: str):
    """POST /v2/validation/benches/<id>/unlock - Release a bench lock."""
    db = get_db_client()

    bench = db.testbench.find_unique(where={"id": bench_id})
    if not bench:
        return not_found(f"Bench not found: {bench_id}")

    if bench.status != "LOCKED":
        return bad_request("Bench is not locked")

    try:
        updated = db.testbench.update(
            where={"id": bench_id},
            data={
                "status": "AVAILABLE",
                "lockedBy": None,
                "lockedAt": None,
            },
        )

        log_audit("validation.bench.unlock", "TestBench", bench_id, {
            "previousLockedBy": bench.lockedBy,
        })

        return jsonify(ApiResponse.ok(_serialize_bench(updated)).to_dict()), 200

    except Exception as e:
        logger.error("Failed to unlock bench %s: %s", bench_id, e)
        return internal_error("Failed to unlock bench")


def find_available_bench(
    product: str,
    revision: Optional[str] = None,
    capabilities: Optional[List[str]] = None,
) -> Optional[Dict[str, Any]]:
    """
    Find an available bench matching requirements.
    Used by CI pipeline scheduler.

    Args:
        product: Product name (e.g., "alpha", "Alpha B0")
        revision: Optional revision (e.g., "b0")
        capabilities: Required capabilities list

    Returns:
        Serialized bench dict if found, None otherwise
    """
    db = get_db_client()

    # Normalize product name: "Alpha B0" → "alpha", "alpha_fw" → "alpha"
    product_base = product.lower().replace(" ", "").replace("_fw", "").replace("_mfg", "")
    # Extract just the base name (alpha, sigma5, theta) without revision suffix
    for rev in ["b0", "b1", "a0", "a1", "3b4"]:
        product_base = product_base.replace(rev, "")
    product_base = product_base.strip()

    where: Dict[str, Any] = {
        "status": "AVAILABLE",
    }

    if capabilities:
        where["capabilities"] = {"hasEvery": capabilities}

    try:
        # Try exact match first
        bench = db.testbench.find_first(
            where={**where, "dutProduct": product_base}
        )

        # Try contains match if exact fails
        if not bench:
            bench = db.testbench.find_first(
                where={**where, "dutProduct": {"contains": product_base[:5]}}
            )

        # Filter by revision if specified and found
        if bench and revision:
            if bench.dutRevision.lower() != revision.lower():
                # Try to find a bench with matching revision
                bench_with_rev = db.testbench.find_first(
                    where={**where, "dutProduct": product_base, "dutRevision": revision.lower()}
                )
                if bench_with_rev:
                    bench = bench_with_rev

        return _serialize_bench(bench) if bench else None
    except Exception as e:
        logger.error("Failed to find available bench: %s", e)
        return None


@require_permissions(Permissions.ADMIN_VALIDATION_VIEW)
def discover_mtibs():
    """GET /v2/validation/benches/discover - Find unregistered MTIBs in K8s cluster.

    Returns K8s nodes that:
    - Have label 'node.corekinect.com/type=mtib'
    - Are not already registered as TestBench records

    This helps admins find newly added MTIBs that need registration.
    """
    db = get_db_client()

    try:
        # Try to load K8s client
        try:
            from kubernetes import client, config
            try:
                config.load_incluster_config()
            except config.ConfigException:
                config.load_kube_config()

            v1 = client.CoreV1Api()
            nodes = v1.list_node(label_selector="node.corekinect.com/type=mtib")
        except ImportError:
            logger.warning("kubernetes package not installed, returning mock data")
            # Return mock data for development
            nodes = type("MockNodeList", (), {"items": []})()
        except Exception as e:
            logger.warning("Failed to connect to K8s API: %s", e)
            nodes = type("MockNodeList", (), {"items": []})()

        # Get all registered bench MTIB addresses
        registered_addresses = set()
        benches = db.testbench.find_many(select={"mtibAddress": True})
        for b in benches:
            # Extract IP from "10.4.45.33:50053"
            addr = b.mtibAddress.split(":")[0] if b.mtibAddress else ""
            registered_addresses.add(addr)

        # Find unregistered nodes
        unregistered = []
        for node in nodes.items:
            # Get internal IP
            ip = None
            for addr in node.status.addresses or []:
                if addr.type == "InternalIP":
                    ip = addr.address
                    break

            if ip and ip not in registered_addresses:
                unregistered.append({
                    "hostname": node.metadata.name,
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
                })

        return jsonify(ApiResponse.ok(unregistered).to_dict()), 200

    except Exception as e:
        logger.error("Failed to discover MTIBs: %s", e)
        return internal_error("Failed to discover MTIBs")


@require_permissions(Permissions.ADMIN_VALIDATION_VIEW)
def get_bench_profile(bench_id: str):
    """GET /v2/validation/benches/<id>/profile - Get resolved fixture profile.

    Merges the fixture design's profileTemplate with the bench's profileOverrides,
    and injects DUT-specific info (device ID, SNR, etc.).

    This is the profile that gets passed to validation test runs.
    """
    db = get_db_client()

    try:
        bench = db.testbench.find_unique(
            where={"id": bench_id},
            include={"fixtureDesign": True},
        )
        if not bench:
            return not_found(f"Bench not found: {bench_id}")

        # Start with design template or empty dict
        profile = {}
        if bench.fixtureDesign and bench.fixtureDesign.profileTemplate:
            profile = dict(bench.fixtureDesign.profileTemplate)

        # Apply bench-specific overrides
        if bench.profileOverrides:
            _deep_merge(profile, bench.profileOverrides)

        # Inject DUT info
        profile["station_id"] = bench.stationId
        if bench.dutDeviceId:
            if "dut" not in profile:
                profile["dut"] = {}
            profile["dut"]["device_id"] = bench.dutDeviceId
        if bench.dutSnr:
            if "dut" not in profile:
                profile["dut"] = {}
            profile["dut"]["snr"] = bench.dutSnr
        if bench.dutImei:
            if "dut" not in profile:
                profile["dut"] = {}
            profile["dut"]["imei"] = bench.dutImei
        if bench.dutIccids:
            if "dut" not in profile:
                profile["dut"] = {}
            profile["dut"]["iccids"] = bench.dutIccids

        # Inject hardware paths
        if bench.uartAppPath:
            profile["uart_app_path"] = bench.uartAppPath
        if bench.uartCommsPath:
            profile["uart_comms_path"] = bench.uartCommsPath
        if bench.jlinkAppSerial:
            profile["jlink_app_serial"] = bench.jlinkAppSerial
        if bench.jlinkCommsSerial:
            profile["jlink_comms_serial"] = bench.jlinkCommsSerial

        # Set capabilities from bench (may override design)
        if bench.capabilities:
            profile["capabilities"] = bench.capabilities

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
