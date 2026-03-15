# Tier 2 — Resource Browser & Log Streaming

## Goal

Give admins a full resource browser for namespace-scoped workloads: pods, deployments, services, jobs, and config (ConfigMaps / Secrets). Super admins can perform mutating actions (scale, restart, delete). Real-time pod log streaming via SocketIO.

---

## Architecture

### Backend — New Files

```
src/services/kubernetes/
  serializers.py     MODIFY  — add pod, deployment, service, job, configmap, secret serializers
  pods.py            CREATE  — list, get, delete pod
  deployments.py     CREATE  — list, get, scale, restart deployment
  services_k8s.py    CREATE  — list, get service
  jobs.py            CREATE  — list, get, delete job
  configmaps.py      CREATE  — list, get configmap; list, get secret

src/api/v2/system/
  pods.py            CREATE  — REST endpoints for pods
  deployments.py     CREATE  — REST endpoints for deployments
  services_api.py    CREATE  — REST endpoints for services
  jobs.py            CREATE  — REST endpoints for jobs
  config.py          CREATE  — REST endpoints for configmaps + secrets
  logs.py            CREATE  — SocketIO handlers for pod log streaming

src/api/v2/router.py       MODIFY  — register new routes + SocketIO namespace
```

### Frontend — New Files

```
src/app/pages/system/
  system-page.tsx      MODIFY  — add Pods, Deployments, Services, Jobs, Config tabs
  pods-list.tsx        CREATE  — pod table with namespace filter
  pod-detail.tsx       CREATE  — pod detail with containers, events, log viewer
  deployments-list.tsx CREATE  — deployment table
  deployment-detail.tsx CREATE — deployment detail with scale/restart actions
  services-list.tsx    CREATE  — service table
  service-detail.tsx   CREATE  — service detail with endpoints/ports
  jobs-list.tsx        CREATE  — job table
  job-detail.tsx       CREATE  — job detail with pod list
  config-list.tsx      CREATE  — configmaps + secrets tabs

src/app/components/system/
  log-viewer.tsx       CREATE  — terminal-style log display with SocketIO
  action-button.tsx    CREATE  — button for mutating actions with confirmation
```

---

## Permissions

| Permission | Actions |
|---|---|
| `Concord.Admin.System.View` | List/get all resources, stream logs (read-only) |
| `Concord.Admin.System.Manage` | Scale deployments, restart deployments, delete pods, delete jobs |

---

## API Contracts

### Pods

**GET /v2/system/pods?namespace=\<ns\>**

```json
{
  "ok": true,
  "data": [
    {
      "name": "my-pod-abc123",
      "namespace": "default",
      "status": "Running",
      "ready": "1/1",
      "restarts": 0,
      "nodeName": "worker-1",
      "podIp": "10.244.0.5",
      "containers": [
        { "name": "main", "image": "nginx:1.25", "ready": true, "restartCount": 0, "state": "running" }
      ],
      "createdAt": "2024-01-15T10:00:00Z",
      "age": "3d 4h"
    }
  ]
}
```

**GET /v2/system/pods/\<namespace\>/\<name\>**

Same shape as list item plus:
- `conditions`: array of pod conditions
- `volumes`: array of volume names + types
- `events`: recent events for this pod
- `tolerations`: array of tolerations
- `serviceAccount`: string

**DELETE /v2/system/pods/\<namespace\>/\<name\>** — requires `System.Manage`

### Deployments

**GET /v2/system/deployments?namespace=\<ns\>**

```json
{
  "ok": true,
  "data": [
    {
      "name": "my-app",
      "namespace": "default",
      "replicas": { "desired": 3, "ready": 3, "available": 3, "updated": 3 },
      "strategy": "RollingUpdate",
      "containers": [
        { "name": "main", "image": "my-app:v2.1" }
      ],
      "conditions": [
        { "type": "Available", "status": "True", "reason": "MinimumReplicasAvailable" }
      ],
      "createdAt": "2024-01-10T08:00:00Z",
      "age": "8d 6h"
    }
  ]
}
```

**GET /v2/system/deployments/\<namespace\>/\<name\>** — same shape plus `selector`, `labels`, `annotations`

**POST /v2/system/deployments/\<namespace\>/\<name\>/scale** — requires `System.Manage`
```json
{ "replicas": 5 }
```

**POST /v2/system/deployments/\<namespace\>/\<name\>/restart** — requires `System.Manage`

### Services

**GET /v2/system/services?namespace=\<ns\>**

```json
{
  "ok": true,
  "data": [
    {
      "name": "my-svc",
      "namespace": "default",
      "type": "ClusterIP",
      "clusterIp": "10.96.0.10",
      "ports": [
        { "name": "http", "port": 80, "targetPort": "8080", "protocol": "TCP" }
      ],
      "selector": { "app": "my-app" },
      "createdAt": "2024-01-10T08:00:00Z",
      "age": "8d 6h"
    }
  ]
}
```

**GET /v2/system/services/\<namespace\>/\<name\>** — same shape plus `externalIps`, `loadBalancerIp`

### Jobs

**GET /v2/system/jobs?namespace=\<ns\>**

```json
{
  "ok": true,
  "data": [
    {
      "name": "migrate-db",
      "namespace": "default",
      "completions": "1/1",
      "parallelism": 1,
      "active": 0,
      "succeeded": 1,
      "failed": 0,
      "status": "Complete",
      "duration": "45s",
      "createdAt": "2024-01-15T10:00:00Z",
      "age": "3d 4h"
    }
  ]
}
```

**GET /v2/system/jobs/\<namespace\>/\<name\>** — same plus `pods` array, `conditions`, `backoffLimit`

**DELETE /v2/system/jobs/\<namespace\>/\<name\>** — requires `System.Manage`

### ConfigMaps & Secrets

**GET /v2/system/configmaps?namespace=\<ns\>**

```json
{
  "ok": true,
  "data": [
    {
      "name": "app-config",
      "namespace": "default",
      "dataKeys": ["DATABASE_URL", "LOG_LEVEL"],
      "dataCount": 2,
      "createdAt": "2024-01-10T08:00:00Z",
      "age": "8d 6h"
    }
  ]
}
```

**GET /v2/system/configmaps/\<namespace\>/\<name\>** — same plus `data` (full key-value map)

**GET /v2/system/secrets?namespace=\<ns\>** — same shape as configmaps but `type` field added, data keys only (no values for security)

**GET /v2/system/secrets/\<namespace\>/\<name\>** — includes `data` with values base64-decoded but masked (first 4 chars + `****`)

### Log Streaming (SocketIO)

**Namespace:** `/system`

**Events:**
- Client → `subscribe_logs` `{ namespace, pod, container, tailLines? }`
- Server → `log_line` `{ timestamp, line }`
- Server → `log_error` `{ message }`
- Client → `unsubscribe_logs`

---

## Frontend Component Tree

```
/system (SystemPage — MODIFIED)
  ├── Sub-navigation: [Overview, Nodes, Pods, Deployments, Services, Jobs, Config, Events]
  │
  ├── /system/pods → PodsList
  │     ├── NamespaceSelector
  │     └── ResourceTable (name, namespace, status, ready, restarts, node, age)
  │
  ├── /system/pods/:namespace/:name → PodDetail
  │     ├── Status header + containers table
  │     ├── Conditions table
  │     ├── LogViewer (SocketIO streaming)
  │     └── Delete button (System.Manage only)
  │
  ├── /system/deployments → DeploymentsList
  │     ├── NamespaceSelector
  │     └── ResourceTable (name, namespace, replicas, strategy, image, age)
  │
  ├── /system/deployments/:namespace/:name → DeploymentDetail
  │     ├── Replica status + strategy
  │     ├── Scale slider/input (System.Manage)
  │     ├── Restart button (System.Manage)
  │     └── Conditions table
  │
  ├── /system/services → ServicesList
  │     ├── NamespaceSelector
  │     └── ResourceTable (name, namespace, type, clusterIP, ports, age)
  │
  ├── /system/services/:namespace/:name → ServiceDetail
  │     ├── Ports table
  │     └── Selector labels
  │
  ├── /system/jobs → JobsList
  │     ├── NamespaceSelector
  │     └── ResourceTable (name, namespace, completions, status, duration, age)
  │
  ├── /system/jobs/:namespace/:name → JobDetail
  │     ├── Status + completions
  │     ├── Pods table
  │     └── Delete button (System.Manage)
  │
  └── /system/config → ConfigList
        ├── ConfigMaps/Secrets tab toggle
        ├── NamespaceSelector
        └── ResourceTable (name, namespace, keys, age)
```

---

## Phase Checklist

- [x] Phase 1 — Backend: serializers for pods, deployments, services, jobs, configmaps, secrets
- [x] Phase 2 — Backend: service modules for all resource types
- [x] Phase 3 — Backend: REST API routes + mutating actions
- [x] Phase 4 — Backend: pod log streaming via SocketIO
- [x] Phase 5 — Frontend: pod list/detail + log viewer + system page tab expansion
- [x] Phase 6 — Frontend: deployments, services, jobs, config pages
