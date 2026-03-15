# Phase 1 — Backend: Serializers for Tier 2 Resources

## Objective

Extend `serializers.py` with mapper functions for pods, deployments, services, jobs, configmaps, and secrets. These convert raw kubernetes-client Python objects into clean dicts — same pattern as Tier 1.

---

## 1. Modify `src/services/kubernetes/serializers.py`

Add the following functions after the existing `serialize_event()` function.

### `serialize_pod(pod)` — for list views

```python
def serialize_pod(pod) -> dict:
    metadata = pod.metadata
    spec = pod.spec
    status = pod.status

    # Container summary
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

    # If no container_statuses yet, use spec containers
    if not containers and spec and spec.containers:
        containers = [
            {"name": c.name, "image": c.image, "ready": False, "restartCount": 0, "state": "waiting"}
            for c in spec.containers
        ]

    # Ready string: "2/3"
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
```

### `serialize_pod_detail(pod)` — for detail view

```python
def serialize_pod_detail(pod) -> dict:
    base = serialize_pod(pod)
    metadata = pod.metadata
    spec = pod.spec
    status = pod.status

    # Conditions
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

    # Volumes
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

    # Tolerations
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
```

### `serialize_deployment(deployment)` — for list views

```python
def serialize_deployment(deployment) -> dict:
    metadata = deployment.metadata
    spec = deployment.spec
    status = deployment.status

    # Replica counts
    desired = spec.replicas if spec else 0
    ready = status.ready_replicas or 0 if status else 0
    available = status.available_replicas or 0 if status else 0
    updated = status.updated_replicas or 0 if status else 0

    # Strategy
    strategy = "RollingUpdate"
    if spec and spec.strategy and spec.strategy.type:
        strategy = spec.strategy.type

    # Container images from template
    containers = []
    if spec and spec.template and spec.template.spec:
        containers = [
            {"name": c.name, "image": c.image}
            for c in spec.template.spec.containers
        ]

    # Conditions
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
```

### `serialize_service(service)` — for list views

```python
def serialize_service(service) -> dict:
    metadata = service.metadata
    spec = service.spec

    ports = []
    if spec and spec.ports:
        for p in spec.ports:
            ports.append({
                "name": p.name or "",
                "port": p.port,
                "targetPort": str(p.target_port) if p.target_port else "",
                "protocol": p.protocol or "TCP",
                "nodePort": p.node_port,
            })

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
```

### `serialize_job(job)` — for list views

```python
def serialize_job(job) -> dict:
    metadata = job.metadata
    spec = job.spec
    status = job.status

    active = status.active or 0 if status else 0
    succeeded = status.succeeded or 0 if status else 0
    failed = status.failed or 0 if status else 0
    completions = spec.completions or 1 if spec else 1
    parallelism = spec.parallelism or 1 if spec else 1

    # Status string
    job_status = "Running"
    if status:
        if status.completion_time:
            job_status = "Complete"
        elif failed > 0 and active == 0:
            job_status = "Failed"

    # Duration
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

    # Conditions
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
```

### `serialize_configmap(cm)` — for list and detail views

```python
def serialize_configmap(cm, include_data: bool = False) -> dict:
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
```

### `serialize_secret(secret, include_data: bool = False)` — for list and detail views

```python
def serialize_secret(secret, include_data: bool = False) -> dict:
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
            except Exception:
                masked[key] = "****"
        result["data"] = masked

    return result
```

---

## Verification

1. `python3 -m py_compile src/services/kubernetes/serializers.py` — passes
2. No new imports needed except `base64` (stdlib) in `serialize_secret`
3. All serializers handle None gracefully for status/spec/metadata fields

---

## Overview Update

```
- [x] Phase 1 — Backend: serializers for pods, deployments, services, jobs, configmaps, secrets
```
