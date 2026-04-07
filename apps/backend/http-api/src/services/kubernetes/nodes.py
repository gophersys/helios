import logging

from kubernetes.client.exceptions import ApiException

from .client import get_core_v1_api
from .serializers import serialize_node

logger = logging.getLogger(__name__)


def list_nodes() -> list[dict]:
    """List all Kubernetes nodes with allocated resource summaries.

    Returns:
        List of serialized Node dicts, each with an 'allocated' field showing
        current CPU requests, memory requests, and pod count.
    """
    core = get_core_v1_api()
    node_list = core.list_node()

    nodes = []
    for node in node_list.items:
        serialized = serialize_node(node)

        # Count pods allocated to this node
        pods = core.list_pod_for_all_namespaces(
            field_selector=f"spec.nodeName={node.metadata.name},status.phase!=Succeeded,status.phase!=Failed"
        )

        # Sum resource requests
        cpu_requests_m = 0
        memory_requests_bytes = 0
        for pod in pods.items:
            for container in pod.spec.containers:
                if container.resources and container.resources.requests:
                    cpu_req = container.resources.requests.get("cpu", "0")
                    mem_req = container.resources.requests.get("memory", "0")
                    cpu_requests_m += _parse_cpu(cpu_req)
                    memory_requests_bytes += _parse_memory(mem_req)

        serialized["allocated"] = {
            "cpuRequests": f"{cpu_requests_m}m",
            "memoryRequests": _format_memory(memory_requests_bytes),
            "podCount": len(pods.items),
        }
        nodes.append(serialized)

    return nodes


def get_node(name: str) -> dict | None:
    """Fetch a single Kubernetes node by name with pods and resource allocation.

    Args:
        name: Hostname of the Kubernetes node.

    Returns:
        Serialized Node dict with 'allocated' and 'pods' fields, or None if not found.
    """
    core = get_core_v1_api()
    try:
        node = core.read_node(name)
    except ApiException as e:
        logger.warning("Failed to read node %s: %s", name, e.reason)
        return None

    serialized = serialize_node(node)

    pods = core.list_pod_for_all_namespaces(
        field_selector=f"spec.nodeName={name},status.phase!=Succeeded,status.phase!=Failed"
    )

    cpu_requests_m = 0
    memory_requests_bytes = 0
    for pod in pods.items:
        for container in pod.spec.containers:
            if container.resources and container.resources.requests:
                cpu_req = container.resources.requests.get("cpu", "0")
                mem_req = container.resources.requests.get("memory", "0")
                cpu_requests_m += _parse_cpu(cpu_req)
                memory_requests_bytes += _parse_memory(mem_req)

    serialized["allocated"] = {
        "cpuRequests": f"{cpu_requests_m}m",
        "memoryRequests": _format_memory(memory_requests_bytes),
        "podCount": len(pods.items),
    }

    # Include pods running on this node
    serialized["pods"] = [
        {
            "name": p.metadata.name,
            "namespace": p.metadata.namespace,
            "status": p.status.phase or "Unknown",
            "restarts": sum(
                (cs.restart_count or 0)
                for cs in (p.status.container_statuses or [])
            ),
        }
        for p in pods.items
    ]

    return serialized


def _parse_cpu(value: str) -> int:
    """Parse CPU value to millicores."""
    if value.endswith("m"):
        return int(value[:-1])
    try:
        return int(float(value) * 1000)
    except (ValueError, TypeError):
        return 0


def _parse_memory(value: str) -> int:
    """Parse memory value to bytes."""
    suffixes = {"Ki": 1024, "Mi": 1024**2, "Gi": 1024**3, "Ti": 1024**4}
    for suffix, multiplier in suffixes.items():
        if value.endswith(suffix):
            try:
                return int(float(value[:-len(suffix)]) * multiplier)
            except (ValueError, TypeError):
                return 0
    try:
        return int(value)
    except (ValueError, TypeError):
        return 0


def _format_memory(bytes_val: int) -> str:
    """Format bytes to human-readable."""
    if bytes_val >= 1024**3:
        return f"{bytes_val / 1024**3:.1f}Gi"
    if bytes_val >= 1024**2:
        return f"{bytes_val / 1024**2:.0f}Mi"
    if bytes_val >= 1024:
        return f"{bytes_val / 1024:.0f}Ki"
    return f"{bytes_val}"
