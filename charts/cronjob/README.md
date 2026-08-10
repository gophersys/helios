# charts/cronjob

A workload that runs on a schedule. It wraps the Kubernetes `CronJob`.

## When to pick this

- A nightly aggregate, a daily report, or a weekly rollup.
- A periodic cleanup: log retention, a purge of tmp, or a sweep of expired
  tokens.
- A cache warmer or an index rebuilder.
- A scheduled sync with an external system: a pull from a SaaS API, or a push to
  a BI warehouse.

If it runs once and you start it by hand, pick `job`. If it runs for a long time
and consumes a queue continuously, pick `worker`.

## What the chart emits

- `CronJob` — with the schedule, the concurrency policy and the history limits.
- `ServiceAccount`, `ExternalSecret`, `NetworkPolicy`, and an optional
  `PrometheusRule` for the SLO on run success.
- No Service, no Ingress, no HPA and no PDB, because a job is temporary.

## Schedule + concurrency

```yaml
schedule: "0 3 * * *"             # cron expression — UTC
timeZone: "UTC"                   # explicit to avoid DST surprises
concurrencyPolicy: Forbid         # Forbid | Allow | Replace (default: Forbid)
startingDeadlineSeconds: 600      # miss this window → don't run
successfulJobsHistoryLimit: 3
failedJobsHistoryLimit: 3
```

`Forbid` is the default, because most scheduled work should not run 2 times at
once. Choose `Allow` explicitly only when 2 overlapping runs are safe and wanted,
for example a fan-out that divides its work naturally.

## Run semantics

Each run:

- runs in a new pod. There is no shared state between runs, and there is no
  persistence unless you mount a PVC. If you mount a PVC, the workload is not a
  cronjob. It is a stateful process with a schedule, and you must reconsider the
  archetype.
- gets new ExternalSecrets, so a credential never becomes stale.
- emits structured logs and metrics. Use a sidecar, or an in-process push
  gateway if the process does not run long enough for a scrape.

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
| `timeZone`                         | `UTC`        | Daylight-saving arithmetic causes errors       |
| `activeDeadlineSeconds`            | `3600`       | Prevent runaway runs; override explicitly      |
| `backoffLimit`                     | `3`          | Transient failures recover; real failures page |
| `ttlSecondsAfterFinished`          | `86400`      | 24h log retention on the Job object            |
| `nodeRole`                         | `apps`       | Switch to `batch` when preemptible pool exists |

## Observability for a cronjob

- A push gateway sidecar exposes the run-count metric for the scrape. As an
  alternative, the job emits the metric to NATS or stdout, and the log pipeline
  reconciles it.
- A `PrometheusRule` with:
  - `slo:cronjob:success_rate:<name>` — the percentage of scheduled runs that
    completed successfully.
  - `cronjob:last_success_timestamp:<name>` — the age of the most recent
    successful run.
- The canonical alert in Alertmanager is: the cronjob has not succeeded for more
  than 2 times its schedule interval.

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
