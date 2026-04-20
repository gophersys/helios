# charts/worker

Long-running process that consumes a queue / stream / channel and produces
side effects. No inbound HTTP — no Service, no Ingress.

## When to pick this

- NATS JetStream consumers, Kafka consumers (future), Redis Streams
  consumers.
- Background job processors (email senders, async exporters).
- Event-driven side-effect workers (webhook fan-out, image resizers).
- Data pipeline stages (ingest, parse, grade, score) — as long as each
  stage is a long-running consumer, not a one-shot run.

If the workload runs to completion, pick `job`. If it's scheduled, pick
`cronjob`. If it serves HTTP, pick `stateless-app`.

## What the chart emits

- `Deployment` — no Service, no Ingress, no probes on HTTP (probes may
  still be TCP or exec).
- `ServiceAccount`, `ExternalSecret`, `NetworkPolicy`, `PodMonitor`,
  `PodDisruptionBudget`, `PrometheusRule`.
- `ScaledObject` (KEDA) — when `worker.autoscale.keda.enabled: true` and
  `platform/services/keda/` is installed.

## Autoscaling semantics

Workers often should scale to **zero** when the queue is empty, and scale
**up** with backlog depth. That's different from HPA (which only scales
on CPU/memory). The chart supports both:

- **Default**: HPA on CPU (60%), `min=1 max=10`. Works everywhere.
- **Preferred** (when KEDA is installed): `ScaledObject` with the queue
  depth trigger. Example for NATS JetStream:
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

Exactly one of HPA or KEDA is enabled at a time.

## Graceful shutdown

Workers receive SIGTERM when Kubernetes decides to evict the pod. The
chart renders:

- `terminationGracePeriodSeconds: 60` (overridable per workload).
- `preStop` hook running the worker's `drain` command (values-configurable),
  so in-flight messages are completed or re-queued before the process exits.

Apps are expected to:

1. Stop accepting new work on SIGTERM.
2. Finish current in-flight work within `gracePeriod - preStopTimeout`.
3. Exit cleanly.

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

Workers often process messages with side effects that can't be undone. The
chart's default rollout is conservative:

- `maxSurge: 1, maxUnavailable: 0` (always one more, never fewer).
- `minReadySeconds: 30` (longer burn-in than stateless-app).
- When Argo Rollouts lands: optional `strategy: canary` with metric-based
  analysis on consumer lag.

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
