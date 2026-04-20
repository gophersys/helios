# charts/cronjob

Runs on a schedule. Wraps Kubernetes `CronJob`.

## When to pick this

- Nightly aggregates, daily reports, weekly rollups.
- Periodic cleanup (log retention, tmp purge, expired-token sweep).
- Cache warmers, index rebuilders.
- Scheduled external syncs (pull from SaaS API, push to BI warehouse).

If it runs once and you trigger it manually, pick `job`. If it's
long-running and constantly consuming a queue, pick `worker`.

## What the chart emits

- `CronJob` — with the schedule, concurrency policy, and history limits.
- `ServiceAccount`, `ExternalSecret`, `NetworkPolicy`, `PrometheusRule` for
  run-success SLO (optional).
- No Service, no Ingress, no HPA, no PDB (jobs are transient).

## Schedule + concurrency

```yaml
schedule: "0 3 * * *"             # cron expression — UTC
timeZone: "UTC"                   # explicit to avoid DST surprises
concurrencyPolicy: Forbid         # Forbid | Allow | Replace (default: Forbid)
startingDeadlineSeconds: 600      # miss this window → don't run
successfulJobsHistoryLimit: 3
failedJobsHistoryLimit: 3
```

`Forbid` is the default because most scheduled work shouldn't run
concurrently. Explicitly opt into `Allow` only when overlapping runs
are safe and desired (e.g., fan-out that parallelizes naturally).

## Run semantics

Each invocation:

- Runs in a fresh pod — no shared state between runs, no persistence
  unless you mount a PVC (then you're not really a cronjob, you're a
  stateful process with a schedule; reconsider).
- Gets fresh ExternalSecrets each run — no stale-credential drift.
- Emits structured logs and metrics (via a sidecar or in-process push
  gateway if the process doesn't live long enough for scrape).

## Timeout + retry

```yaml
activeDeadlineSeconds: 3600       # kill if it runs longer than 1h
backoffLimit: 3                   # retry up to 3 times on failure
ttlSecondsAfterFinished: 86400    # cleanup completed pods after 24h
```

## Opinionated defaults

| Knob                               | Default      | Rationale                                      |
|------------------------------------|--------------|------------------------------------------------|
| `concurrencyPolicy`                | `Forbid`     | Most scheduled work is unsafe concurrent       |
| `timeZone`                         | `UTC`        | DST math is the devil                          |
| `activeDeadlineSeconds`            | `3600`       | Prevent runaway runs; override explicitly      |
| `backoffLimit`                     | `3`          | Transient failures recover; real failures page |
| `ttlSecondsAfterFinished`          | `86400`      | 24h log retention on the Job object            |
| `nodeRole`                         | `apps`       | Switch to `batch` when preemptible pool exists |

## Observability for cronjobs

- Run-count metric scraped via a push gateway sidecar (or emitted to
  NATS/stdout and reconciled by the log pipeline).
- `PrometheusRule` with:
  - `slo:cronjob:success_rate:<name>` — % of scheduled runs that
    completed successfully.
  - `cronjob:last_success_timestamp:<name>` — age of most recent
    successful run.
- Alertmanager: "cronjob hasn't succeeded in > 2× schedule interval"
  is the canonical stale-run alert.

## Example values

Install as release `codectl-nightly-rollup` in namespace `codectl-prod`:

```yaml
project: codectl                    # namespace: codectl-prod
env: prod
app:
  name: nightly-rollup              # full identifier: codectl-nightly-rollup

image:
  repository: ghcr.io/mateosegura/codectl
  tag: v1.42.0

schedule: "0 3 * * *"
timeZone: "UTC"
concurrencyPolicy: Forbid
activeDeadlineSeconds: 1800
backoffLimit: 2

jobSpec:
  command: ["/bin/codectl", "rollup", "--window=24h"]

resources:
  requests: { cpu: 200m, memory: 256Mi }
  limits:   { cpu: 1000m, memory: 256Mi }

secrets:
  - { key: DATABASE_URL, bwItem: codectl-db, bwProperty: uri, mode: env }

networkPolicy:
  allowEgressTo:
    - namespace: platform-databases
    - namespace: platform-secrets

observability:
  metrics:  { enabled: true, pushgateway: { enabled: true } }
  logs:     { format: json }

slo:
  tier: standard
  successRate: { target: 99.0, window: 30d }
  staleAfter:  "48h"                 # alert if last_success older
```

## Status

Skeleton. Templates are stubs.
