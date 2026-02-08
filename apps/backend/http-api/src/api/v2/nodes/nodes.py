import math
from typing import Any

from flask import jsonify, request

from src.lib.audit import log_audit
from src.lib.decorators import require_permissions
from src.lib.errors import bad_request, conflict, internal_error, not_found
from src.lib.permissions import Permissions
from src.lib.types import ApiResponse
from src.services.database.prisma import get_db_client

from .types import NodeCreateRequest, NodeUpdateRequest

try:
    from src.services.kubernetes.client import get_core_v1_api
    from kubernetes.client.exceptions import ApiException
    K8S_AVAILABLE = True
except ImportError:
    K8S_AVAILABLE = False


def _serialize_node(n: Any, include_slot: bool = False) -> dict:
    data = {
        "id": n.id,
        "name": n.name,
        "hostname": n.hostname,
        "type": n.type,
        "status": n.status,
        "ipAddress": n.ipAddress,
        "hardwareRevision": n.hardwareRevision,
        "metadata": n.metadata,
        "createdAt": n.createdAt.isoformat(),
        "updatedAt": n.updatedAt.isoformat(),
    }
    if include_slot and hasattr(n, "fixtureSlot") and n.fixtureSlot:
        slot = n.fixtureSlot
        data["fixtureSlot"] = {
            "id": slot.id,
            "fixtureId": slot.fixtureId,
            "slotIndex": slot.slotIndex,
            "label": slot.label,
        }
        if hasattr(slot, "fixture") and slot.fixture:
            data["fixtureSlot"]["fixtureName"] = slot.fixture.name
    return data


# -- Nodes CRUD ---------------------------------------------------------------


@require_permissions(Permissions.ADMIN_NODES_VIEW)
def list_nodes():
    db = get_db_client()

    page = max(1, request.args.get("page", 1, type=int))
    limit = min(max(1, request.args.get("limit", 50, type=int)), 100)
    skip = (page - 1) * limit

    where: dict = {}
    node_type = request.args.get("type", "").strip().upper()
    if node_type in ("MANUFACTURING", "VALIDATION"):
        where["type"] = node_type

    total = db.node.count(where=where)
    nodes = db.node.find_many(
        where=where,
        skip=skip,
        take=limit,
        order={"name": "asc"},
        include={"fixtureSlot": True},
    )
    return jsonify(ApiResponse.ok({
        "data": [_serialize_node(n, include_slot=True) for n in nodes],
        "pagination": {
            "page": page,
            "limit": limit,
            "total": total,
            "pages": math.ceil(total / limit) if limit > 0 else 0,
        },
    }).to_dict()), 200


@require_permissions(Permissions.ADMIN_NODES_MANAGE)
def create_node():
    data, error = NodeCreateRequest.from_json(request.get_json())
    if error:
        return bad_request(error)

    db = get_db_client()

    existing = db.node.find_first(where={"hostname": data.hostname})
    if existing:
        return conflict("Node with this hostname already exists")

    node = db.node.create(
        data={
            "name": data.name,
            "hostname": data.hostname,
            "type": data.type,
            "ipAddress": data.ipAddress,
            "hardwareRevision": data.hardwareRevision,
            "metadata": data.metadata,
        },
        include={"fixtureSlot": True},
    )
    log_audit("node.create", "Node", node.id, {"name": data.name, "hostname": data.hostname, "type": data.type})
    return jsonify(ApiResponse.ok(_serialize_node(node, include_slot=True)).to_dict()), 201


@require_permissions(Permissions.ADMIN_NODES_MANAGE)
def sync_nodes_from_k8s():
    if not K8S_AVAILABLE:
        return internal_error("Kubernetes client not available")

    try:
        core_v1 = get_core_v1_api()
        k8s_nodes = core_v1.list_node()
    except ApiException:
        return internal_error("Failed to connect to Kubernetes API")
    except Exception:
        return internal_error("Kubernetes API unavailable")

    db = get_db_client()

    # Get all existing nodes from DB keyed by hostname
    db_nodes = db.node.find_many()
    db_hostname_map = {n.hostname: n for n in db_nodes}

    discovered = []
    registered = []
    seen_hostnames = set()

    for k8s_node in k8s_nodes.items:
        labels = k8s_node.metadata.labels or {}
        arch = labels.get("kubernetes.io/arch", "")
        if arch != "arm64":
            continue

        # Only include Ready nodes
        is_ready = False
        for condition in (k8s_node.status.conditions or []):
            if condition.type == "Ready" and condition.status == "True":
                is_ready = True
                break
        if not is_ready:
            continue

        hostname = k8s_node.metadata.name
        seen_hostnames.add(hostname)

        ip = ""
        for addr in (k8s_node.status.addresses or []):
            if addr.type == "InternalIP":
                ip = addr.address
                break

        os_image = k8s_node.status.node_info.os_image if k8s_node.status.node_info else ""
        kubelet_version = k8s_node.status.node_info.kubelet_version if k8s_node.status.node_info else ""

        if hostname in db_hostname_map:
            db_node = db_hostname_map[hostname]
            registered.append({
                "id": db_node.id,
                "name": db_node.name,
                "hostname": hostname,
                "type": db_node.type,
                "status": db_node.status,
                "ipAddress": ip or db_node.ipAddress,
            })
        else:
            discovered.append({
                "hostname": hostname,
                "ip": ip,
                "arch": arch,
                "osImage": os_image,
                "kubeletVersion": kubelet_version,
                "labels": labels,
            })

    # Nodes in DB but not found in K8s arm64 list
    offline = []
    for db_node in db_nodes:
        if db_node.hostname not in seen_hostnames:
            offline.append({
                "id": db_node.id,
                "name": db_node.name,
                "hostname": db_node.hostname,
                "type": db_node.type,
                "status": db_node.status,
            })

    return jsonify(ApiResponse.ok({
        "registered": registered,
        "discovered": discovered,
        "offline": offline,
    }).to_dict()), 200


@require_permissions(Permissions.ADMIN_NODES_VIEW)
def get_node(node_id: str):
    db = get_db_client()
    node = db.node.find_unique(
        where={"id": node_id},
        include={"fixtureSlot": {"include": {"fixture": True}}},
    )
    if not node:
        return not_found("Node not found")
    return jsonify(ApiResponse.ok(_serialize_node(node, include_slot=True)).to_dict()), 200


@require_permissions(Permissions.ADMIN_NODES_MANAGE)
def update_node(node_id: str):
    data, error = NodeUpdateRequest.from_json(request.get_json())
    if error:
        return bad_request(error)

    db = get_db_client()
    existing = db.node.find_unique(where={"id": node_id})
    if not existing:
        return not_found("Node not found")

    node = db.node.update(
        where={"id": node_id},
        data=data.to_update_data(),
        include={"fixtureSlot": True},
    )
    log_audit("node.update", "Node", node_id, {"name": existing.name, "changes": data.to_update_data()})
    return jsonify(ApiResponse.ok(_serialize_node(node, include_slot=True)).to_dict()), 200


@require_permissions(Permissions.ADMIN_NODES_MANAGE)
def delete_node(node_id: str):
    db = get_db_client()
    existing = db.node.find_unique(
        where={"id": node_id},
        include={"testExecutions": True},
    )
    if not existing:
        return not_found("Node not found")

    if hasattr(existing, "testExecutions") and existing.testExecutions:
        return conflict("Cannot delete node: it has associated test executions")

    db.node.delete(where={"id": node_id})
    log_audit("node.delete", "Node", node_id, {"name": existing.name, "hostname": existing.hostname})
    return jsonify(ApiResponse.ok({"deleted": True}).to_dict()), 200


@require_permissions(Permissions.ADMIN_NODES_MANAGE)
def check_node_health(node_id: str):
    db = get_db_client()
    node = db.node.find_unique(where={"id": node_id})
    if not node:
        return not_found("Node not found")

    healthy = False
    status = "OFFLINE"
    details = {}

    if node.ipAddress:
        try:
            import grpc
            channel = grpc.insecure_channel(f"{node.ipAddress}:50051")
            try:
                grpc.channel_ready_future(channel).result(timeout=5)
                healthy = True
                status = "ONLINE"
                details["grpc"] = "connected"
            except grpc.FutureTimeoutError:
                details["grpc"] = "timeout"
            finally:
                channel.close()
        except Exception as e:
            details["grpc"] = str(e)
    else:
        details["grpc"] = "no IP address configured"

    db.node.update(
        where={"id": node_id},
        data={"status": status},
    )

    return jsonify(ApiResponse.ok({
        "nodeId": node_id,
        "healthy": healthy,
        "status": status,
        "details": details,
    }).to_dict()), 200


@require_permissions(Permissions.ADMIN_NODES_MANAGE)
def register_node(node_id: str):
    if not K8S_AVAILABLE:
        return internal_error("Kubernetes client not available")

    req_data = request.get_json() or {}
    hostname = (req_data.get("hostname") or "").strip()
    node_type = (req_data.get("type") or "").strip().upper()
    name = (req_data.get("name") or hostname).strip()

    if not hostname:
        return bad_request("Hostname is required")
    if node_type not in ("MANUFACTURING", "VALIDATION"):
        return bad_request("Type must be MANUFACTURING or VALIDATION")

    db = get_db_client()

    # Check if node with this hostname already exists
    existing = db.node.find_first(where={"hostname": hostname})
    if existing:
        return conflict("Node with this hostname already exists")

    # Apply K8s labels and taints
    purpose = "manufacturing" if node_type == "MANUFACTURING" else "validation"
    try:
        core_v1 = get_core_v1_api()
        body = {
            "metadata": {
                "labels": {
                    "corekinect.com/role": "edge",
                    "corekinect.com/purpose": purpose,
                }
            },
            "spec": {
                "taints": [
                    {"key": "corekinect.com/role", "value": "edge", "effect": "NoSchedule"}
                ]
            }
        }
        core_v1.patch_node(hostname, body)
    except ApiException:
        return internal_error("Failed to apply K8s labels")
    except Exception:
        return internal_error("Kubernetes API unavailable")

    # Get IP from K8s node
    ip_address = req_data.get("ip", "")

    node = db.node.create(
        data={
            "name": name,
            "hostname": hostname,
            "type": node_type,
            "status": "ONLINE",
            "ipAddress": ip_address if ip_address else None,
        },
        include={"fixtureSlot": True},
    )
    log_audit("node.register", "Node", node.id, {"name": name, "hostname": hostname, "type": node_type})
    return jsonify(ApiResponse.ok(_serialize_node(node, include_slot=True)).to_dict()), 201
