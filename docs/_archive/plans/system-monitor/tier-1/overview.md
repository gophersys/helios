# Tier 1 — Cluster Overview & Node Management

## Goal

Give super admins a live operational dashboard: cluster health, node status/capacity, namespace listing, resource counts, and a scrollable events feed. Normal admins get the same view, read-only.

---

## Architecture

### Backend

```
src/services/kubernetes/
  client.py          MODIFY  — add get_client() accessor
  cache.py           CREATE  — TTL in-memory cache for K8s API responses
  serializers.py     CREATE  — K8s object -> dict mappers
  cluster.py         CREATE  — cluster info, namespace list, resource summary
  nodes.py           CREATE  — node list, node detail
  events.py          CREATE  — event list with filtering

src/api/v2/system/
  __init__.py        CREATE
  cluster.py         CREATE  — GET /v2/system/cluster, GET /v2/system/namespaces
  nodes.py           CREATE  — GET /v2/system/nodes, GET /v2/system/nodes/<name>
  events.py          CREATE  — GET /v2/system/events

src/api/v2/router.py       MODIFY  — register system routes
src/lib/permissions.py      MODIFY  — add System.View, System.Manage
```

### Frontend

```
src/app/pages/system/
  system-page.tsx          CREATE  — layout with sub-navigation
  overview.tsx             CREATE  — cluster dashboard
  nodes-list.tsx           CREATE  — node table
  node-detail.tsx          CREATE  — single node detail view
  events-list.tsx          CREATE  — filterable events feed

src/app/components/system/
  metric-card.tsx          CREATE  — stat card (number + label + icon)
  resource-table.tsx       CREATE  — reusable sortable table
  namespace-selector.tsx   CREATE  — dropdown namespace picker
  status-indicator.tsx     CREATE  — dot + label status component
  resource-age.tsx         CREATE  — "3d 12h" age display

src/app/app.tsx            MODIFY  — add /system/* routes
src/app/components/sidebar.tsx  MODIFY  — add System nav item under Admin
```

---

## Permissions

| Permission | Who | Allows |
|---|---|---|
| `Concord.Admin.System.View` | Normal admin | Read-only cluster, nodes, events |
| `Concord.Admin.System.Manage` | Super admin | All Tier 2/3 actions (scale, restart, exec) |

Tier 1 only uses `System.View` — no mutating actions yet.

---

## API Contracts

### GET /v2/system/cluster

```json
{
  "ok": true,
  "data": {
    "kubernetesVersion": "v1.28.4",
    "platform": "linux/amd64",
    "nodeCount": 5,
    "namespaceCount": 4,
    "resources": {
      "pods": { "running": 24, "pending": 1, "failed": 0, "total": 25 },
      "deployments": { "available": 8, "progressing": 0, "total": 8 },
      "services": { "total": 12 },
      "jobs": { "active": 2, "succeeded": 14, "failed": 1, "total": 17 }
    }
  }
}
```

### GET /v2/system/namespaces

```json
{
  "ok": true,
  "data": [
    { "name": "default", "status": "Active", "createdAt": "2024-01-01T00:00:00Z" },
    { "name": "kube-system", "status": "Active", "createdAt": "2024-01-01T00:00:00Z" }
  ]
}
```

### GET /v2/system/nodes

```json
{
  "ok": true,
  "data": [
    {
      "name": "worker-1",
      "status": "Ready",
      "roles": ["worker"],
      "internalIp": "10.0.0.5",
      "osImage": "Ubuntu 22.04",
      "kubeletVersion": "v1.28.4",
      "containerRuntime": "containerd://1.7.2",
      "capacity": { "cpu": "4", "memory": "8Gi", "pods": "110" },
      "allocatable": { "cpu": "3800m", "memory": "7Gi", "pods": "110" },
      "allocated": { "cpuRequests": "1200m", "memoryRequests": "2Gi", "podCount": 12 },
      "conditions": [
        { "type": "Ready", "status": "True", "reason": "KubeletReady", "message": "kubelet is posting ready status", "lastTransition": "2024-01-15T10:00:00Z" }
      ],
      "labels": { "kubernetes.io/hostname": "worker-1" },
      "createdAt": "2024-01-01T00:00:00Z",
      "age": "45d"
    }
  ]
}
```

### GET /v2/system/nodes/\<name\>

Same shape as a single item from the list above but with full conditions and labels.

### GET /v2/system/events?namespace=\<ns\>&limit=\<n\>

```json
{
  "ok": true,
  "data": [
    {
      "type": "Warning",
      "reason": "BackOff",
      "message": "Back-off restarting failed container",
      "object": "pod/my-pod",
      "namespace": "default",
      "count": 5,
      "firstSeen": "2024-01-15T10:00:00Z",
      "lastSeen": "2024-01-15T10:05:00Z",
      "source": "kubelet"
    }
  ]
}
```

---

## Frontend Component Tree

```
/system (SystemPage)
  ├── Sub-navigation: [Overview, Nodes, Events]
  │
  ├── /system (default) → Overview
  │     ├── MetricCard × 4 (nodes, pods, deployments, jobs)
  │     ├── NamespaceSelector (stored in URL query or state)
  │     ├── ResourceTable (top pods by restart count)
  │     └── Events feed (last 20 events)
  │
  ├── /system/nodes → NodesList
  │     └── ResourceTable (all nodes with status, IP, version, capacity)
  │
  ├── /system/nodes/:name → NodeDetail
  │     ├── MetricCard × 3 (CPU, memory, pods)
  │     ├── Conditions table
  │     └── Labels/annotations display
  │
  └── /system/events → EventsList
        ├── NamespaceSelector
        └── ResourceTable (events with type, reason, object, message, age)
```

---

## Phase Checklist

- [x] Phase 1 — Backend: permissions, cache, serializers
- [x] Phase 2 — Backend: cluster, node, event services
- [x] Phase 3 — Backend: API routes + router registration
- [x] Phase 4 — Frontend: system page layout, shared components, routing, nav
- [x] Phase 5 — Frontend: cluster overview dashboard
- [x] Phase 6 — Frontend: nodes list/detail + events feed

---

## Completion Notes

- All phases implemented and working
- Polling interval set to 1s for real-time updates
- Tag filtering added using `corekinect.com/role` and `corekinect.com/purpose` labels
- Progress rings show percentages, usage bars show actual values
- Node detail has clean 3x2 info grid layout
