# charts/stateless-app

The **reference archetype**. It is a 12-factor HTTP or HTTPS service with no
persistent local state. The replicas are interchangeable, and you can roll each
replica on its own.

## When to pick this

- Web APIs, REST/GraphQL/gRPC backends, webhook receivers.
- Frontends that ship their own server (Next.js, Remix, Nuxt, Svelte Kit
  with SSR).
- Any HTTP service whose state lives in an external database (through
  `contracts/databases.md`), queue (through `contracts/messaging.md`), or
  object store.

If the service needs a persistent volume per replica, or an ordered start and an
ordered stop, pick `stateful-app` instead. If there is no inbound HTTP at all,
pick `worker`.

## What the chart emits

With a minimal valid `values.yaml`, the chart renders:

- `Deployment` — RollingUpdate strategy (`maxSurge: 1, maxUnavailable: 0`),
  `minReadySeconds: 10`.
- `Service` — ClusterIP by default; optional headless mode for gRPC.
- `ServiceAccount` — dedicated per release (ambient SA banned by policy).
- `HorizontalPodAutoscaler` — when `autoscale.enabled: true` (default);
  CPU + memory targets, `min=1 max=10` unless overridden.
- `PodDisruptionBudget` — always emitted; `maxUnavailable: 25%` for 2+
  replicas, `minAvailable: 1` for single replica.
- `ServiceMonitor` — when `observability.metrics.enabled: true`
  (default); scraped by `platform/services/observability/`.
- `PrometheusRule` — SLO recording rules from `values.slo`.
- `ExternalSecret` — one per entry in `values.secrets[]`.
- `NetworkPolicy` — baseline (deny-all + DNS + same-ns + metrics scrape)
  plus the app's declared `allowIngressFrom` / `allowEgressTo`.
- `Ingress` — only when `values.ingress.enabled: true`. Prefer the
  `ingress-app` archetype when the ingress is the main purpose of the service.

## Opinionated defaults

| Knob                            | Default                          | Override when                           |
|---------------------------------|----------------------------------|-----------------------------------------|
| `replicas`                      | `2`                              | single-replica preview envs; big fleets |
| `nodeRole`                      | `apps`                           | observability-stack-adjacent → `devops` |
| `resources.requests.cpu`        | `100m`                           | hot paths                               |
| `resources.requests.memory`     | `128Mi`                          | memory-heavy workloads                  |
| `resources.limits.cpu`          | `500m`                           | bursty compute                          |
| `resources.limits.memory`       | `128Mi`                          | **MUST equal requests** (no burstable mem) |
| `rollout.strategy`              | `RollingUpdate`                  | `canary` when progressive-delivery lands |
| `probes.startup`                | HTTP `/healthz`, 60s budget      | slower cold starts                      |
| `probes.readiness`              | HTTP `/readyz`, every 5s         | deeper readiness (DB check, etc.)       |
| `probes.liveness`               | HTTP `/healthz`, every 10s       | avoid DB calls in liveness              |
| `autoscale.cpuTarget`           | `60%`                            | latency-sensitive → lower, batch-y → higher |
| `autoscale.memTarget`           | `70%`                            | mem-bound                               |
| `pdb.maxUnavailable`            | `25%`                            | stricter availability tiers             |
| `slo.tier`                      | `standard`                       | customer-facing APIs → `high`/`critical` |
| `observability.metrics.port`    | `9090`                           | framework default differs               |

## Example values

Install as release `codectl-api` in namespace `codectl-prod`:

```yaml
project: codectl                    # determines namespace prefix: codectl-prod
env: prod                           # determines namespace suffix: codectl-prod
app:
  name: api                         # full identifier: codectl-api
tenant: gophersys
nodeRole: apps
dataClassification: internal

image:
  repository: ghcr.io/mateosegura/codectl-api
  tag: v1.42.0
  pullPolicy: IfNotPresent

replicas: 2

resources:
  requests: { cpu: 200m, memory: 256Mi }
  limits:   { cpu: 1000m, memory: 256Mi }

probes:
  startup:   { http: { path: /healthz, port: http }, initialDelaySeconds: 0, periodSeconds: 2, failureThreshold: 30 }
  readiness: { http: { path: /readyz,  port: http }, periodSeconds: 5 }
  liveness:  { http: { path: /healthz, port: http }, periodSeconds: 10 }

service:
  port: 8080
  targetPort: http

observability:
  metrics: { enabled: true, port: 9090, path: /metrics }
  logs:    { format: json, level: info }
  traces:  { enabled: true, samplingRatio: 0.1 }

secrets:
  - { key: DATABASE_URL,   bwItem: codectl-db,        bwProperty: uri,    mode: env }
  - { key: OPENAI_API_KEY, bwItem: codectl-openai,    bwProperty: apikey, mode: env }

networkPolicy:
  allowIngressFrom:
    - namespace: platform-ingress         # public traffic in
      pods: { app.kubernetes.io/name: traefik }
  allowEgressTo:
    - namespace: platform-secrets         # ESO
    - dns: { hosts: ["api.openai.com"] }  # egress to OpenAI

autoscale:
  enabled: true
  minReplicas: 2
  maxReplicas: 20
  cpuTarget: 60
  memTarget: 70

pdb:
  maxUnavailable: 25%

slo:
  tier: high
  availability: { target: 99.9, window: 30d }
  latency:      { target_ms: 300, window: 7d }

rollout:
  strategy: RollingUpdate
  maxSurge: 1
  maxUnavailable: 0
```

## Migration paths

- To `ingress-app`: set `values.ingress.enabled: true` and fill in the ingress
  block. stateless-app already emits the ingress itself.
- To `worker`: remove the `service` and `probes.http` blocks, and add
  `worker.queueSignal` for KEDA. `worker` is a separate archetype, because the
  autoscale semantics are different.
- To `stateful-app`: a declarative migration is not possible, because a
  StatefulSet and a Deployment are not interchangeable. Plan a cutover with both
  running side by side.

## Status

Skeleton. `Chart.yaml`, `values.yaml`, `values.schema.json` and `README.md` are
committed. The template files under `templates/` are stubs with inline comments
that describe what each one emits. The real templates land when the first app
adopts the archetype. That app is probably `codectl-api` or
`fintel-api-gateway`.
