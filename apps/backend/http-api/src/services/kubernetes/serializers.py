from datetime import datetime, timezone
from typing import Optional


def _isoformat(dt: Optional[datetime]) -> Optional[str]:
    """Convert a datetime to ISO 8601 string, adding UTC timezone if naive.

    Args:
        dt: Datetime to format, or None.

    Returns:
        ISO 8601 string, or None if dt is None.
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def _age(dt: Optional[datetime]) -> str:
    """Format a datetime as a human-readable age string relative to now.

    Args:
        dt: Creation or start datetime, or None.

    Returns:
        Age string like "3d 2h", "1h 30m", "45m", or "Unknown" if dt is None.
    """
    if dt is None:
        return "Unknown"
    now = datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    delta = now - dt
    days = delta.days
    hours = delta.seconds // 3600
    minutes = (delta.seconds % 3600) // 60
    if days > 0:
        return f"{days}d {hours}h"
    if hours > 0:
        return f"{hours}h {minutes}m"
    return f"{minutes}m"


def serialize_namespace(ns) -> dict:
    """Serialize a Kubernetes Namespace object to an API dict.

    Args:
        ns: kubernetes.client.V1Namespace instance.

    Returns:
        Dict with name, status, createdAt, and age fields.
    """
    return {
        "name": ns.metadata.name,
        "status": ns.status.phase if ns.status else "Unknown",
        "createdAt": _isoformat(ns.metadata.creation_timestamp),
        "age": _age(ns.metadata.creation_timestamp),
    }


def serialize_node(node) -> dict:
    """Serialize a Kubernetes Node object to an API dict.

    Args:
        node: kubernetes.client.V1Node instance.

    Returns:
        Dict with name, status, roles, capacity, conditions, and other node metadata.
    """
    status = node.status
    spec = node.spec
    metadata = node.metadata

    # Determine Ready status
    conditions = []
    ready_status = "Unknown"
    if status and status.conditions:
        for c in status.conditions:
            conditions.append({
                "type": c.type,
                "status": c.status,
                "reason": c.reason or "",
                "message": c.message or "",
                "lastTransition": _isoformat(c.last_transition_time),
            })
            if c.type == "Ready":
                ready_status = "Ready" if c.status == "True" else "NotReady"

    # Roles from labels
    roles = []
    labels = metadata.labels or {}
    for key in labels:
        if key.startswith("node-role.kubernetes.io/"):
            roles.append(key.split("/")[1])
    if not roles:
        roles = ["worker"]

    # Node info
    node_info = status.node_info if status else None

    # Capacity and allocatable
    capacity = {}
    allocatable = {}
    if status:
        if status.capacity:
            capacity = {k: str(v) for k, v in status.capacity.items() if k in ("cpu", "memory", "pods", "ephemeral-storage")}
        if status.allocatable:
            allocatable = {k: str(v) for k, v in status.allocatable.items() if k in ("cpu", "memory", "pods", "ephemeral-storage")}

    # Internal IP
    internal_ip = ""
    if status and status.addresses:
        for addr in status.addresses:
            if addr.type == "InternalIP":
                internal_ip = addr.address
                break

    return {
        "name": metadata.name,
        "status": ready_status,
        "roles": roles,
        "internalIp": internal_ip,
        "osImage": node_info.os_image if node_info else "",
        "kubeletVersion": node_info.kubelet_version if node_info else "",
        "containerRuntime": node_info.container_runtime_version if node_info else "",
        "architecture": node_info.architecture if node_info else "",
        "capacity": capacity,
        "allocatable": allocatable,
        "conditions": conditions,
        "labels": dict(labels),
        "annotations": dict(metadata.annotations or {}),
        "taints": [
            {"key": t.key, "value": t.value or "", "effect": t.effect}
            for t in (spec.taints or [])
        ],
        "unschedulable": bool(spec.unschedulable),
        "createdAt": _isoformat(metadata.creation_timestamp),
        "age": _age(metadata.creation_timestamp),
    }


def serialize_event(event) -> dict:
    """Serialize a Kubernetes Event object to an API dict.

    Args:
        event: kubernetes.client.CoreV1Event instance.

    Returns:
        Dict with type, reason, message, object, count, firstSeen, lastSeen, and source.
    """
    obj = event.involved_object
    return {
        "type": event.type or "Normal",
        "reason": event.reason or "",
        "message": event.message or "",
        "object": f"{obj.kind.lower()}/{obj.name}" if obj else "",
        "namespace": obj.namespace or "" if obj else "",
        "count": event.count or 1,
        "firstSeen": _isoformat(event.first_timestamp),
        "lastSeen": _isoformat(event.last_timestamp or event.metadata.creation_timestamp),
        "source": event.source.component if event.source else "",
    }


def serialize_pod(pod) -> dict:
    """Serialize a Kubernetes Pod object to a summary API dict.

    Args:
        pod: kubernetes.client.V1Pod instance.

    Returns:
        Dict with name, namespace, status, ready count, restarts, nodeName, and containers.
    """
    metadata = pod.metadata
    spec = pod.spec
    status = pod.status

    containers = []
    container_statuses = status.container_statuses or [] if status else []
    for cs in container_statuses:
        state = "waiting"
        if cs.state:
            if cs.state.running:
                state = "running"
            elif cs.state.terminated:
                state = "terminated"
        containers.append({
            "name": cs.name,
            "image": cs.image,
            "ready": cs.ready or False,
            "restartCount": cs.restart_count or 0,
            "state": state,
        })

    if not containers and spec and spec.containers:
        containers = [
            {"name": c.name, "image": c.image, "ready": False, "restartCount": 0, "state": "waiting"}
            for c in spec.containers
        ]

    total = len(containers)
    ready_count = sum(1 for c in containers if c["ready"])
    total_restarts = sum(c["restartCount"] for c in containers)

    return {
        "name": metadata.name,
        "namespace": metadata.namespace,
        "status": status.phase if status else "Unknown",
        "ready": f"{ready_count}/{total}",
        "restarts": total_restarts,
        "nodeName": spec.node_name if spec else "",
        "podIp": status.pod_ip if status else "",
        "containers": containers,
        "createdAt": _isoformat(metadata.creation_timestamp),
        "age": _age(metadata.creation_timestamp),
    }


def serialize_pod_detail(pod) -> dict:
    """Serialize a Kubernetes Pod to a detailed API dict including conditions, volumes, and tolerations.

    Args:
        pod: kubernetes.client.V1Pod instance.

    Returns:
        Extended pod dict (superset of serialize_pod) with conditions, volumes, tolerations,
        serviceAccount, labels, annotations, and qosClass.
    """
    base = serialize_pod(pod)
    metadata = pod.metadata
    spec = pod.spec
    status = pod.status

    conditions = []
    if status and status.conditions:
        for c in status.conditions:
            conditions.append({
                "type": c.type,
                "status": c.status,
                "reason": c.reason or "",
                "message": c.message or "",
                "lastTransition": _isoformat(c.last_transition_time),
            })

    volumes = []
    if spec and spec.volumes:
        for v in spec.volumes:
            vol_type = "unknown"
            if v.config_map:
                vol_type = "configMap"
            elif v.secret:
                vol_type = "secret"
            elif v.persistent_volume_claim:
                vol_type = "pvc"
            elif v.empty_dir is not None:
                vol_type = "emptyDir"
            elif v.host_path:
                vol_type = "hostPath"
            elif v.projected:
                vol_type = "projected"
            elif v.downward_api:
                vol_type = "downwardAPI"
            volumes.append({"name": v.name, "type": vol_type})

    tolerations = []
    if spec and spec.tolerations:
        for t in spec.tolerations:
            tolerations.append({
                "key": t.key or "",
                "operator": t.operator or "Equal",
                "value": t.value or "",
                "effect": t.effect or "",
            })

    base.update({
        "conditions": conditions,
        "volumes": volumes,
        "tolerations": tolerations,
        "serviceAccount": spec.service_account_name if spec else "",
        "labels": dict(metadata.labels or {}),
        "annotations": dict(metadata.annotations or {}),
        "qosClass": status.qos_class if status else "",
    })
    return base


def serialize_deployment(deployment) -> dict:
    """Serialize a Kubernetes Deployment object to an API dict.

    Args:
        deployment: kubernetes.client.V1Deployment instance.

    Returns:
        Dict with name, namespace, replica counts, strategy, containers, and conditions.
    """
    metadata = deployment.metadata
    spec = deployment.spec
    status = deployment.status

    desired = spec.replicas if spec else 0
    ready = status.ready_replicas or 0 if status else 0
    available = status.available_replicas or 0 if status else 0
    updated = status.updated_replicas or 0 if status else 0

    strategy = "RollingUpdate"
    if spec and spec.strategy and spec.strategy.type:
        strategy = spec.strategy.type

    containers = []
    if spec and spec.template and spec.template.spec:
        containers = [
            {"name": c.name, "image": c.image}
            for c in spec.template.spec.containers
        ]

    conditions = []
    if status and status.conditions:
        for c in status.conditions:
            conditions.append({
                "type": c.type,
                "status": c.status,
                "reason": c.reason or "",
                "message": c.message or "",
                "lastTransition": _isoformat(c.last_transition_time),
            })

    return {
        "name": metadata.name,
        "namespace": metadata.namespace,
        "replicas": {
            "desired": desired,
            "ready": ready,
            "available": available,
            "updated": updated,
        },
        "strategy": strategy,
        "containers": containers,
        "conditions": conditions,
        "labels": dict(metadata.labels or {}),
        "annotations": dict(metadata.annotations or {}),
        "selector": dict((spec.selector.match_labels or {}) if spec and spec.selector else {}),
        "createdAt": _isoformat(metadata.creation_timestamp),
        "age": _age(metadata.creation_timestamp),
    }


def _serialize_service_port(p) -> dict:
    """Serialize a single Kubernetes service port."""
    return {
        "name": p.name or "",
        "port": p.port,
        "targetPort": str(p.target_port) if p.target_port else "",
        "protocol": p.protocol or "TCP",
        "nodePort": p.node_port,
    }


def serialize_service(service) -> dict:
    """Serialize a Kubernetes Service object to an API dict.

    Args:
        service: kubernetes.client.V1Service instance.

    Returns:
        Dict with name, namespace, type, clusterIp, ports, and selector.
    """
    metadata = service.metadata
    spec = service.spec

    ports = [_serialize_service_port(p) for p in spec.ports] if spec and spec.ports else []

    return {
        "name": metadata.name,
        "namespace": metadata.namespace,
        "type": spec.type if spec else "ClusterIP",
        "clusterIp": spec.cluster_ip if spec else "",
        "externalIps": list(spec.external_i_ps or []) if spec else [],
        "loadBalancerIp": spec.load_balancer_ip if spec else None,
        "ports": ports,
        "selector": dict(spec.selector or {}) if spec else {},
        "createdAt": _isoformat(metadata.creation_timestamp),
        "age": _age(metadata.creation_timestamp),
    }


def serialize_job(job) -> dict:
    """Serialize a Kubernetes Job object to an API dict.

    Args:
        job: kubernetes.client.V1Job instance.

    Returns:
        Dict with name, namespace, status, completions, duration, and conditions.
    """
    metadata = job.metadata
    spec = job.spec
    status = job.status

    active = status.active or 0 if status else 0
    succeeded = status.succeeded or 0 if status else 0
    failed = status.failed or 0 if status else 0
    completions = spec.completions or 1 if spec else 1
    parallelism = spec.parallelism or 1 if spec else 1

    job_status = "Running"
    if status:
        if status.completion_time:
            job_status = "Complete"
        elif failed > 0 and active == 0:
            job_status = "Failed"

    duration = ""
    if status and status.start_time:
        end = status.completion_time or datetime.now(timezone.utc)
        if status.start_time.tzinfo is None:
            start = status.start_time.replace(tzinfo=timezone.utc)
        else:
            start = status.start_time
        if isinstance(end, datetime) and end.tzinfo is None:
            end = end.replace(tzinfo=timezone.utc)
        delta = end - start
        total_secs = int(delta.total_seconds())
        if total_secs >= 3600:
            duration = f"{total_secs // 3600}h {(total_secs % 3600) // 60}m"
        elif total_secs >= 60:
            duration = f"{total_secs // 60}m {total_secs % 60}s"
        else:
            duration = f"{total_secs}s"

    conditions = []
    if status and status.conditions:
        for c in status.conditions:
            conditions.append({
                "type": c.type,
                "status": c.status,
                "reason": c.reason or "",
                "message": c.message or "",
                "lastTransition": _isoformat(c.last_transition_time),
            })

    return {
        "name": metadata.name,
        "namespace": metadata.namespace,
        "completions": f"{succeeded}/{completions}",
        "parallelism": parallelism,
        "active": active,
        "succeeded": succeeded,
        "failed": failed,
        "status": job_status,
        "duration": duration,
        "backoffLimit": spec.backoff_limit if spec else 6,
        "conditions": conditions,
        "labels": dict(metadata.labels or {}),
        "createdAt": _isoformat(metadata.creation_timestamp),
        "age": _age(metadata.creation_timestamp),
    }


def serialize_configmap(cm, include_data: bool = False) -> dict:
    """Serialize a Kubernetes ConfigMap to an API dict.

    Args:
        cm: kubernetes.client.V1ConfigMap instance.
        include_data: When True, include the full data key-value pairs in the response.

    Returns:
        Dict with name, namespace, dataKeys, dataCount, createdAt, age,
        and optionally data when include_data is True.
    """
    metadata = cm.metadata
    data = cm.data or {}

    result = {
        "name": metadata.name,
        "namespace": metadata.namespace,
        "dataKeys": list(data.keys()),
        "dataCount": len(data),
        "createdAt": _isoformat(metadata.creation_timestamp),
        "age": _age(metadata.creation_timestamp),
    }

    if include_data:
        result["data"] = dict(data)

    return result


def serialize_secret(secret, include_data: bool = False) -> dict:
    """Serialize a Kubernetes Secret to an API dict with masked values.

    Args:
        secret: kubernetes.client.V1Secret instance.
        include_data: When True, include masked (first 4 chars + ****) decoded values.

    Returns:
        Dict with name, namespace, type, dataKeys, dataCount, createdAt, age,
        and optionally masked data when include_data is True.
    """
    metadata = secret.metadata
    data = secret.data or {}

    result = {
        "name": metadata.name,
        "namespace": metadata.namespace,
        "type": secret.type or "Opaque",
        "dataKeys": list(data.keys()),
        "dataCount": len(data),
        "createdAt": _isoformat(metadata.creation_timestamp),
        "age": _age(metadata.creation_timestamp),
    }

    if include_data:
        import base64
        masked = {}
        for key, val in data.items():
            try:
                decoded = base64.b64decode(val).decode("utf-8", errors="replace")
                masked[key] = decoded[:4] + "****" if len(decoded) > 4 else "****"
            except (ValueError, UnicodeDecodeError):
                masked[key] = "****"
        result["data"] = masked

    return result


def serialize_role(role) -> dict:
    """Serialize a Kubernetes Role or ClusterRole to an API dict.

    Args:
        role: kubernetes.client.V1Role or V1ClusterRole instance.

    Returns:
        Dict with name, namespace, rules, labels, createdAt, and age.
    """
    metadata = role.metadata
    rules = []
    for r in (role.rules or []):
        rules.append({
            "apiGroups": list(r.api_groups or [""]),
            "resources": list(r.resources or []),
            "verbs": list(r.verbs or []),
            "resourceNames": list(r.resource_names or []),
        })

    return {
        "name": metadata.name,
        "namespace": getattr(metadata, "namespace", None) or "",
        "rules": rules,
        "labels": dict(metadata.labels or {}),
        "createdAt": _isoformat(metadata.creation_timestamp),
        "age": _age(metadata.creation_timestamp),
    }


def serialize_role_binding(binding) -> dict:
    """Serialize a Kubernetes RoleBinding or ClusterRoleBinding to an API dict.

    Args:
        binding: kubernetes.client.V1RoleBinding or V1ClusterRoleBinding instance.

    Returns:
        Dict with name, namespace, roleRef, subjects, createdAt, and age.
    """
    metadata = binding.metadata
    role_ref = binding.role_ref

    subjects = []
    for s in (binding.subjects or []):
        subjects.append({
            "kind": s.kind,
            "name": s.name,
            "namespace": getattr(s, "namespace", None) or "",
        })

    return {
        "name": metadata.name,
        "namespace": getattr(metadata, "namespace", None) or "",
        "roleRef": {
            "kind": role_ref.kind if role_ref else "",
            "name": role_ref.name if role_ref else "",
        },
        "subjects": subjects,
        "createdAt": _isoformat(metadata.creation_timestamp),
        "age": _age(metadata.creation_timestamp),
    }


def serialize_service_account(sa) -> dict:
    """Serialize a Kubernetes ServiceAccount to an API dict.

    Args:
        sa: kubernetes.client.V1ServiceAccount instance.

    Returns:
        Dict with name, namespace, secrets, labels, createdAt, and age.
    """
    metadata = sa.metadata
    secrets = [s.name for s in (sa.secrets or [])] if sa.secrets else []

    return {
        "name": metadata.name,
        "namespace": metadata.namespace,
        "secrets": secrets,
        "labels": dict(metadata.labels or {}),
        "createdAt": _isoformat(metadata.creation_timestamp),
        "age": _age(metadata.creation_timestamp),
    }
