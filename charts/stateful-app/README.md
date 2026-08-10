# charts/stateful-app

For a service that needs a **stable network identity** and **persistent storage
for each replica**. A `StatefulSet` and a headless `Service` back it.

## When to pick this

- A self-hosted database or queue that has no dedicated platform service yet.
  For PostgreSQL, use `contracts/databases.md`, which goes through
  `platform/services/databases/postgresql/`. Do not deploy your own PostgreSQL.
- A single instance with a leader election, where pod-0 matters: a control-plane
  component or a metadata service.
- A service that is bound by storage and keeps a large working set on a local PV
  for low latency: an in-memory database persisted to local NVMe, a feature
  store, and similar services.

If the service does not need a stable identity, pick `stateless-app`. If storage
is the main concern and you want the platform to manage it, use one of the
implementations in `contracts/databases.md`.

## What the chart emits

- `StatefulSet` — `OrderedReady` pod management, `RollingUpdate` strategy
  with `partition: 0`.
- `Service` (headless) — `clusterIP: None` for stable per-pod DNS.
- `Service` (discovery) — optional ClusterIP for load-balanced reads.
- `PersistentVolumeClaim` template — per-replica, StorageClass from
  `values.storage.class`, retention-policy-bearing labels.
- `ServiceAccount`, `ServiceMonitor`, `PrometheusRule`, `ExternalSecret`,
  `NetworkPolicy`, `PodDisruptionBudget` — same as `stateless-app`.

## Volume protection

Every PVC rendered by this chart carries:

```yaml
metadata:
  labels:
    platform.gophersys/retain: "true"        # Kyverno blocks delete without override
    platform.gophersys/backup: "velero-daily"
  annotations:
    platform.gophersys/backup-schedule: "0 2 * * *"
```

`platform/core/policy/` refuses the deletion of a `PersistentVolumeClaim` when
`platform.gophersys/retain=true`, unless the PVC carries the annotation
`platform.gophersys/allow-delete: "<reason>"`.

`platform/services/backup/` (Velero) runs the declared schedule and copies the
snapshots to the object store that the cluster configured.

## Opinionated defaults

| Knob                              | Default                  | Rationale                                       |
|-----------------------------------|--------------------------|-------------------------------------------------|
| `replicas`                        | `1`                      | Stateful bring-up is expensive; start small     |
| `nodeRole`                        | `data`                   | RAM + storage locality                          |
| `podManagementPolicy`             | `OrderedReady`           | Predictable bring-up; switch to `Parallel` only for sharded systems |
| `updateStrategy`                  | `RollingUpdate` part=0   | Rolling with manual gate via partition          |
| `storage.class`                   | `standard`               | Cluster-default PV class                        |
| `storage.size`                    | `10Gi`                   | Start small; resize via PVC expansion           |
| `storage.accessMode`              | `ReadWriteOnce`          | Single-writer semantics                         |
| `pdb.minAvailable`                | `1`                      | Voluntary evictions blocked if would drop to 0  |
| `resources.requests.memory`       | `512Mi`                  | Data-plane baseline                             |
| `resources.limits.memory`         | `= requests`             | No memory overcommit                            |

## Scaling semantics

- `stateful-app` does NOT scale automatically by default. A change to the size of
  a StatefulSet moves data, and automation is seldom the correct choice.
- For a sharded system in the style of Cassandra, override
  `podManagementPolicy: Parallel`, and scale with explicit changes to the values
  that a reviewer approves in git.
- To upgrade with a rolling update: change `image.tag`. If you must validate each
  pod, set `updateStrategy.partition` to stage the rollout (N-1, N-2, and so on,
  down to 0).

## Example values

Install as release `intelligence-feature-store` in namespace
`intelligence-prod`:

```yaml
project: intelligence               # namespace: intelligence-prod
env: prod
app:
  name: feature-store               # full identifier: intelligence-feature-store
tenant: gophersys
nodeRole: data
dataClassification: internal

image:
  repository: ghcr.io/mateosegura/feature-store
  tag: v2.3.1

replicas: 3

storage:
  class: standard
  size: 100Gi
  accessMode: ReadWriteOnce

podManagementPolicy: OrderedReady

resources:
  requests: { cpu: 500m, memory: 2Gi }
  limits:   { cpu: 2000m, memory: 2Gi }

probes:
  startup:   { tcp: { port: grpc }, periodSeconds: 5, failureThreshold: 120 }
  readiness: { exec: { command: [/bin/feature-store, ready] }, periodSeconds: 10 }
  liveness:  { tcp: { port: grpc }, periodSeconds: 10 }

service:
  port: 9090
  targetPort: grpc

pdb:
  minAvailable: 2

slo:
  tier: critical
  availability: { target: 99.95, window: 30d }

backup:
  enabled: true
  schedule: "0 2 * * *"
  retention: 30d
```

## Status

Skeleton. Templates are stubs.
