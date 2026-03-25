import logging

from flask import jsonify

from src.lib.decorators import require_permissions
from src.lib.errors import not_found, internal_error
from src.lib.permissions import Permissions
from src.lib.types import ApiResponse
from src.services.database.prisma import get_db_client
from src.services.mtib_observability import get_observability_service

logger = logging.getLogger(__name__)


@require_permissions(Permissions.DEVICES_VIEW)
def get_fleet_observability():
    """Get observability overview for all MTIBs."""
    svc = get_observability_service()
    if not svc:
        return internal_error("Observability service not available")

    snapshots = svc.get_all_snapshots()
    overview = svc.get_fleet_overview()

    # Also fetch node records for full metadata
    db = get_db_client()
    db_nodes = {n.id: n for n in db.node.find_many()}

    nodes = []
    for node_id, entry in snapshots.items():
        db_node = db_nodes.get(node_id)
        has_error = bool(entry.get("error"))
        nodes.append({
            "id": node_id,
            "name": entry.get("nodeName", ""),
            "hostname": entry.get("hostname", ""),
            "type": db_node.type if db_node else "",
            "status": db_node.status if db_node else "OFFLINE",
            "ip_address": entry.get("ipAddress"),
            "hardware_revision": db_node.hardwareRevision if db_node else None,
            "deployment_status": _get_deployment_status(db_node) if db_node else None,
            "snapshot": _normalize_snapshot(entry.get("snapshot")) if not has_error else None,
            "last_seen": entry.get("lastUpdated"),
            "online": not has_error and entry.get("snapshot") is not None,
            "error": entry.get("error"),
        })

    return jsonify(ApiResponse.ok({
        "nodes": nodes,
        "summary": {
            "total": overview["totalNodes"],
            "online": overview["onlineNodes"],
            "offline": overview["errorNodes"],
            "total_power_mw": overview["totalPowerMw"],
        },
    }).to_dict()), 200


def _get_deployment_status(db_node) -> dict | None:
    """Get K8s deployment status for a node, if available."""
    if not db_node.metadata or not isinstance(db_node.metadata, dict):
        return None
    deploy_name = db_node.metadata.get("deployment_name")
    if not deploy_name:
        return None
    try:
        from src.services.kubernetes.mtib_deployments import get_mtib_deployment_status
        status = get_mtib_deployment_status(deploy_name)
        if not status:
            return {"status": "not_deployed", "replicas": 0, "ready": 0, "pod_name": "", "restart_count": 0}
        pods = status.get("pods", [])
        pod = pods[0] if pods else {}
        ready_count = status.get("readyReplicas", 0) or 0
        return {
            "status": "running" if ready_count > 0 else "pending",
            "replicas": status.get("replicas", 0) or 0,
            "ready": ready_count,
            "pod_name": pod.get("name", ""),
            "restart_count": pod.get("restarts", 0),
        }
    except Exception:
        return None


def _normalize_snapshot(snapshot: dict | None) -> dict | None:
    """Normalize a gRPC snapshot dict to match frontend ObservabilitySnapshot interface."""
    if not snapshot:
        return None
    return {
        "timestamp": snapshot.get("timestamp", ""),
        "power_readings": [
            {
                "channel": pr.get("channel", 0),
                "enabled": pr.get("enabled", False),
                "voltage_v": pr.get("voltage_v", 0.0),
                "current_ma": pr.get("current_ma", 0.0),
                "power_mw": pr.get("power_mw", 0.0),
            }
            for pr in snapshot.get("powerReadings", [])
        ],
        "gpio_states": [
            {
                "pin": gs.get("pin", 0),
                "direction": gs.get("direction", 0),
                "value": gs.get("value", False),
                "configured": gs.get("configured", False),
            }
            for gs in snapshot.get("gpioStates", [])
        ],
        "uart_ports": [
            {
                "port_name": up.get("portName", ""),
                "is_open": up.get("isOpen", False),
                "baud_rate": up.get("baudRate", 0),
                "client_count": up.get("clientCount", 0),
                "bytes_received": up.get("bytesReceived", 0),
                "bytes_sent": up.get("bytesSent", 0),
                "recent_lines": up.get("recentLines", []),
            }
            for up in snapshot.get("uartPorts", [])
        ],
        "system_metrics": _normalize_system_metrics(snapshot.get("systemMetrics")),
        "connected_clients": [
            {
                "client_id": cc.get("clientId", ""),
                "remote_addr": cc.get("remoteAddr", ""),
                "connected_since": cc.get("connectedSince", ""),
                "active_rpcs": cc.get("activeRpcs", []),
            }
            for cc in snapshot.get("connectedClients", [])
        ],
        "adc_readings": [
            {
                "channel": ar.get("channel", 0),
                "voltage_v": ar.get("voltage_v", 0.0) if isinstance(ar.get("voltage_v"), (int, float)) else ar.get("voltageV", 0.0),
                "raw_value": ar.get("raw_value", 0) if isinstance(ar.get("raw_value"), (int, float)) else ar.get("rawValue", 0),
            }
            for ar in snapshot.get("adcReadings", [])
        ],
    }


def _normalize_system_metrics(sm: dict | None) -> dict:
    """Normalize system metrics to match frontend SystemMetrics interface."""
    if not sm:
        return {
            "cpu_percent": 0.0, "memory_percent": 0.0, "disk_percent": 0.0,
            "uptime_seconds": 0, "hostname": "", "os_info": "",
            "hardware_revision": "", "server_version": "",
            "grpc_active_connections": 0, "grpc_total_requests": 0,
        }
    return {
        "cpu_percent": sm.get("cpuPercent", 0.0),
        "memory_percent": sm.get("memoryPercent", 0.0),
        "disk_percent": sm.get("diskPercent", 0.0),
        "uptime_seconds": sm.get("uptimeSeconds", 0),
        "hostname": sm.get("hostname", ""),
        "os_info": sm.get("osInfo", ""),
        "hardware_revision": sm.get("hardwareRevision", ""),
        "server_version": sm.get("serverVersion", ""),
        "grpc_active_connections": sm.get("grpcActiveConnections", 0),
        "grpc_total_requests": sm.get("grpcTotalRequests", 0),
    }


@require_permissions(Permissions.DEVICES_VIEW)
def get_node_observability(node_id: str):
    """Get full observability snapshot for a single MTIB."""
    db = get_db_client()
    node = db.node.find_unique(where={"id": node_id})
    if not node:
        return not_found("Node not found")

    svc = get_observability_service()
    if not svc:
        return internal_error("Observability service not available")

    entry = svc.get_snapshot(node_id)
    raw_snapshot = entry.get("snapshot") if entry else None
    return jsonify(ApiResponse.ok({
        "node": {
            "id": node.id,
            "name": node.name,
            "hostname": node.hostname,
            "ipAddress": node.ipAddress,
        },
        "snapshot": _normalize_snapshot(raw_snapshot) if raw_snapshot else None,
        "lastUpdated": entry.get("lastUpdated") if entry else None,
        "error": entry.get("error") if entry else "No data collected yet",
    }).to_dict()), 200


@require_permissions(Permissions.DEVICES_VIEW)
def get_node_power(node_id: str):
    """Get power readings for a single MTIB."""
    db = get_db_client()
    node = db.node.find_unique(where={"id": node_id})
    if not node:
        return not_found("Node not found")

    svc = get_observability_service()
    if not svc:
        return internal_error("Observability service not available")

    entry = svc.get_snapshot(node_id)
    snapshot = entry.get("snapshot") if entry else None

    normalized = _normalize_snapshot(snapshot) if snapshot else None
    return jsonify(ApiResponse.ok({
        "nodeId": node_id,
        "powerReadings": normalized["power_readings"] if normalized else [],
        "error": entry.get("error") if entry else "No data collected yet",
    }).to_dict()), 200


@require_permissions(Permissions.DEVICES_VIEW)
def get_node_gpio(node_id: str):
    """Get GPIO states for a single MTIB."""
    db = get_db_client()
    node = db.node.find_unique(where={"id": node_id})
    if not node:
        return not_found("Node not found")

    svc = get_observability_service()
    if not svc:
        return internal_error("Observability service not available")

    entry = svc.get_snapshot(node_id)
    snapshot = entry.get("snapshot") if entry else None

    normalized = _normalize_snapshot(snapshot) if snapshot else None
    return jsonify(ApiResponse.ok({
        "nodeId": node_id,
        "gpioStates": normalized["gpio_states"] if normalized else [],
        "error": entry.get("error") if entry else "No data collected yet",
    }).to_dict()), 200


@require_permissions(Permissions.DEVICES_VIEW)
def get_node_uart(node_id: str):
    """Get UART status and recent output for a single MTIB."""
    db = get_db_client()
    node = db.node.find_unique(where={"id": node_id})
    if not node:
        return not_found("Node not found")

    svc = get_observability_service()
    if not svc:
        return internal_error("Observability service not available")

    entry = svc.get_snapshot(node_id)
    snapshot = entry.get("snapshot") if entry else None

    normalized = _normalize_snapshot(snapshot) if snapshot else None
    return jsonify(ApiResponse.ok({
        "nodeId": node_id,
        "uartPorts": normalized["uart_ports"] if normalized else [],
        "error": entry.get("error") if entry else "No data collected yet",
    }).to_dict()), 200


@require_permissions(Permissions.DEVICES_VIEW)
def get_node_system(node_id: str):
    """Get system metrics for a single MTIB."""
    db = get_db_client()
    node = db.node.find_unique(where={"id": node_id})
    if not node:
        return not_found("Node not found")

    svc = get_observability_service()
    if not svc:
        return internal_error("Observability service not available")

    entry = svc.get_snapshot(node_id)
    snapshot = entry.get("snapshot") if entry else None

    normalized = _normalize_snapshot(snapshot) if snapshot else None
    return jsonify(ApiResponse.ok({
        "nodeId": node_id,
        "systemMetrics": normalized["system_metrics"] if normalized else None,
        "error": entry.get("error") if entry else "No data collected yet",
    }).to_dict()), 200
