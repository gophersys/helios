# Phase 2 — Backend: Cluster, Node, and Event Services

## Objective

Create the three service modules that query the Kubernetes API and return serialized dicts. These are the business logic layer — the API routes (Phase 3) are thin wrappers around these.

---

## 1. Create `src/services/kubernetes/cluster.py`

```python
from typing import Any

from .cache import cached
from .client import get_core_v1_api, get_apps_v1_api, get_batch_v1_api
from .serializers import serialize_namespace


def get_cluster_info() -> dict:
    """Get cluster version and high-level resource summary."""
    core = get_core_v1_api()

    # Version info from one of the nodes
    nodes = core.list_node()
    version_info = {}
    if nodes.items:
        ni = nodes.items[0].status.node_info
        version_info = {
            "kubernetesVersion": ni.kubelet_version if ni else "Unknown",
            "platform": f"{ni.operating_system}/{ni.architecture}" if ni else "Unknown",
        }

    # Resource counts
    all_pods = core.list_pod_for_all_namespaces()
    pod_phases = {"Running": 0, "Pending": 0, "Failed": 0, "Succeeded": 0, "Unknown": 0}
    for pod in all_pods.items:
        phase = pod.status.phase or "Unknown"
        pod_phases[phase] = pod_phases.get(phase, 0) + 1

    apps = get_apps_v1_api()
    all_deployments = apps.list_deployment_for_all_namespaces()
    dep_available = sum(1 for d in all_deployments.items if d.status.available_replicas and d.status.available_replicas > 0)

    all_services = core.list_service_for_all_namespaces()

    batch = get_batch_v1_api()
    all_jobs = batch.list_job_for_all_namespaces()
    job_active = sum(1 for j in all_jobs.items if j.status.active and j.status.active > 0)
    job_succeeded = sum(1 for j in all_jobs.items if j.status.succeeded and j.status.succeeded > 0)
    job_failed = sum(1 for j in all_jobs.items if j.status.failed and j.status.failed > 0)

    namespaces = core.list_namespace()

    return {
        **version_info,
        "nodeCount": len(nodes.items),
        "namespaceCount": len(namespaces.items),
        "resources": {
            "pods": {
                "running": pod_phases.get("Running", 0),
                "pending": pod_phases.get("Pending", 0),
                "failed": pod_phases.get("Failed", 0),
                "succeeded": pod_phases.get("Succeeded", 0),
                "total": len(all_pods.items),
            },
            "deployments": {
                "available": dep_available,
                "progressing": len(all_deployments.items) - dep_available,
                "total": len(all_deployments.items),
            },
            "services": {
                "total": len(all_services.items),
            },
            "jobs": {
                "active": job_active,
                "succeeded": job_succeeded,
                "failed": job_failed,
                "total": len(all_jobs.items),
            },
        },
    }


def list_namespaces() -> list[dict]:
    core = get_core_v1_api()
    ns_list = core.list_namespace()
    return [serialize_namespace(ns) for ns in ns_list.items]
```

---

## 2. Create `src/services/kubernetes/nodes.py`

```python
from .client import get_core_v1_api
from .serializers import serialize_node


def list_nodes() -> list[dict]:
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
    core = get_core_v1_api()
    try:
        node = core.read_node(name)
    except Exception:
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
```

---

## 3. Create `src/services/kubernetes/events.py`

```python
from .client import get_core_v1_api
from .serializers import serialize_event


def list_events(namespace: str | None = None, limit: int = 100) -> list[dict]:
    core = get_core_v1_api()

    if namespace:
        event_list = core.list_namespaced_event(namespace, limit=limit)
    else:
        event_list = core.list_event_for_all_namespaces(limit=limit)

    events = [serialize_event(e) for e in event_list.items]

    # Sort by lastSeen descending (most recent first)
    events.sort(key=lambda e: e.get("lastSeen") or "", reverse=True)

    return events[:limit]
```

---

## Verification

1. `python3 -m py_compile src/services/kubernetes/cluster.py`
2. `python3 -m py_compile src/services/kubernetes/nodes.py`
3. `python3 -m py_compile src/services/kubernetes/events.py`
4. All three import without error when the K8s client is initialized.

---

## Overview Update

```
- [x] Phase 2 — Backend: cluster, node, event services
```
