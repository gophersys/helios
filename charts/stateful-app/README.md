# charts/stateful-app

Services that need **stable network identity** and **per-replica
persistent storage**. Backed by `StatefulSet` and headless `Service`.

## When to pick this

- Self-hosted databases or queues that **don't** yet have a dedicated
  platform service (if it's PostgreSQL, use `contracts/databases.md`
  which goes through `platform/services/databases/postgresql/`; don't
  deploy your own).
- Leader-elected singletons where pod-0 matters (control plane components,
  metadata services).
- Storage-bound services with large working sets kept on local PV for
  latency (in-memory DB persisted to local NVMe, feature stores, etc.).

If the service doesn't need stable identity, pick `stateless-app`. If
storage is the primary concern and you want the platform to manage it,
use one of the `contracts/databases.md` implementations.

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

`platform/core/policy/` denies `PersistentVolumeClaim` deletion when
`platform.gophersys/retain=true` unless the request carries
`platform.gophersys/allow-delete: "<reason>"` annotation on the PVC.

`platform/services/backup/` (Velero) runs the declared schedule and
replicates snapshots to the cluster's configured object store.

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

- `stateful-app` does NOT auto-scale by default. Scaling a StatefulSet
  involves data movement; automation is rarely the right call.
- For sharded systems (Cassandra-style), override `podManagementPolicy:
  Parallel` and scale via explicit values bumps reviewed in git.
- Rolling upgrade: bump `image.tag`, set `updateStrategy.partition` to
  stage the rollout (N-1, N-2, ..., 0) if validation-per-pod is needed.

## Example values

```yaml
app:
  name: my-feature-store
env: prod
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
