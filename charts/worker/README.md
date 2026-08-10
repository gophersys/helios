# charts/worker

A long-running process that consumes a queue, a stream or a channel, and that
produces side effects. It takes no inbound HTTP, so it has no Service and no
Ingress.

## When to pick this

- NATS JetStream consumers, Kafka consumers (future), Redis Streams
  consumers.
- Background job processors (email senders, async exporters).
- Event-driven side-effect workers (webhook fan-out, image resizers).
- Stages of a data pipeline (ingest, parse, grade, score), while each stage is a
  long-running consumer and not a single run.

If the workload runs to completion, pick `job`. If it runs on a schedule, pick
`cronjob`. If it serves HTTP, pick `stateless-app`.

## What the chart emits

- `Deployment` — no Service, no Ingress, and no HTTP probe. A probe can still be
  TCP or exec.
- `ServiceAccount`, `ExternalSecret`, `NetworkPolicy`, `PodMonitor`,
  `PodDisruptionBudget`, `PrometheusRule`.
- `ScaledObject` (KEDA) — when `worker.autoscale.keda.enabled: true` and
  `platform/services/keda/` is installed.

## Autoscaling semantics

A worker often must scale to **zero** when the queue is empty, and scale **up**
with the depth of the backlog. An HPA cannot do that, because it scales on CPU
and memory only. The chart supports both methods:

- **Default**: an HPA on CPU (60%), `min=1 max=10`. It works on every cluster.
- **Preferred**, when KEDA is installed: a `ScaledObject` with a trigger on the
  queue depth. An example for NATS JetStream:
  ```yaml
  worker:
    autoscale:
      keda:
        enabled: true
        scaler: nats-jetstream
        stream: fintel.signals
        consumer: grader
        lagThreshold: 100
        minReplicas: 0
        maxReplicas: 20
        cooldownPeriod: 300s
  ```

Exactly 1 of the 2, the HPA or KEDA, is enabled at any time.

## Shutdown without loss

A worker receives SIGTERM when Kubernetes decides to evict the pod. The chart
renders:

- `terminationGracePeriodSeconds: 60`. You can override it per workload.
- a `preStop` hook that runs the `drain` command of the worker. You configure the
  command in the values. The worker then completes or re-queues the messages that
  are in progress, before the process exits.

An app must:

1. Stop the acceptance of new work when it receives SIGTERM.
2. Finish the work in progress within `gracePeriod - preStopTimeout`.
3. Exit with no error.

## Opinionated defaults

| Knob                              | Default              | Rationale                                       |
|-----------------------------------|----------------------|-------------------------------------------------|
| `replicas`                        | `1`                  | Start small; scale on backlog                   |
| `nodeRole`                        | `apps`               | `batch` when available for cost savings         |
| `terminationGracePeriodSeconds`   | `60`                 | Allow drain to finish                           |
| `autoscale.keda.minReplicas`      | `0`                  | Pay only for backlog                            |
| `autoscale.keda.cooldownPeriod`   | `300s`               | Avoid flappy scale-to-zero                      |
| `pdb.maxUnavailable`              | `50%`                | Workers tolerate more churn than web            |

## Progressive rollout

A worker often processes a message with a side effect that you cannot undo. The
default rollout of the chart is therefore careful:

- `maxSurge: 1, maxUnavailable: 0`, so there is always 1 more replica and never
  fewer.
- `minReadySeconds: 30`, which is a longer test period than stateless-app uses.
- When Argo Rollouts lands: an optional `strategy: canary`, with an analysis
  based on the metric for consumer lag.

## Example values

Install as release `fintel-signal-grader` in namespace `fintel-prod`:

```yaml
project: fintel                     # namespace: fintel-prod
env: prod
app:
  name: signal-grader               # full identifier: fintel-signal-grader
tenant: gophersys
nodeRole: apps
dataClassification: internal

image:
  repository: ghcr.io/mateosegura/fintel-grader
  tag: v3.1.0

replicas: 1

worker:
  command: ["/bin/grader", "run"]
  args: []
  preStop:
    command: ["/bin/grader", "drain", "--timeout=45s"]
  autoscale:
    keda:
      enabled: true
      scaler: nats-jetstream
      stream: fintel.signals
      consumer: grader
      lagThreshold: 50
      minReplicas: 0
      maxReplicas: 15
      cooldownPeriod: 300s

resources:
  requests: { cpu: 200m, memory: 256Mi }
  limits:   { cpu: 1000m, memory: 256Mi }

secrets:
  - { key: NATS_CREDS_FILE, bwItem: fintel-nats-grader-creds, mode: file }
  - { key: DATABASE_URL, bwItem: fintel-db, bwProperty: uri, mode: env }

networkPolicy:
  allowEgressTo:
    - namespace: platform-secrets
    - namespace: platform-messaging           # NATS
    - namespace: platform-databases            # Postgres
    - external: true                           # outbound to HTTP APIs

observability:
  metrics: { enabled: true, port: 9090, path: /metrics }
  logs:    { format: json }
  traces:  { enabled: true, samplingRatio: 1.0 }    # fuller traces on workers

slo:
  tier: high
  lag:
    target_seconds: 30            # p95 processing lag
    window: 7d
  successRate:
    target: 99.5                  # per-message success
    window: 30d
```

## Status

Skeleton. Templates are stubs.
