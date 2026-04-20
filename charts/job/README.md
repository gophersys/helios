# charts/job

One-shot `Job` — runs to completion, then disappears. Not scheduled, not
long-running.

## When to pick this

- Database migrations run during app deploy (as a Helm `post-install` or
  `post-upgrade` hook).
- One-off data backfills, schema rewrites, cache warmups.
- Bootstrap tasks during cluster or app initialization.
- Manually-triggered "run this thing once" operations.

If the workload is scheduled (periodic), pick `cronjob`. If it's
long-running, pick `worker`.

## What the chart emits

- `Job` — with optional Helm hook annotations (pre-install, post-install,
  pre-upgrade, post-upgrade, pre-delete).
- `ServiceAccount`, `ExternalSecret`, `NetworkPolicy`.
- No Service, no HPA, no PDB.

## Helm hook integration

Jobs that are part of another chart's lifecycle annotate themselves as
Helm hooks:

```yaml
job:
  helmHook:
    events: ["post-install", "post-upgrade"]
    weight: 10                    # earlier = lower weight
    deletePolicy: before-hook-creation,hook-succeeded
```

The chart emits:

```yaml
annotations:
  helm.sh/hook: post-install,post-upgrade
  helm.sh/hook-weight: "10"
  helm.sh/hook-delete-policy: before-hook-creation,hook-succeeded
```

Use this for DB migrations paired to a `stateless-app` release, etc.

## Idempotency expectation

Apps are expected to make job bodies idempotent whenever possible. The
chart's `backoffLimit` default is 2 — a failing job retries, so a
non-idempotent body causes duplicated effects on retry.

## Run semantics

```yaml
activeDeadlineSeconds: 3600
backoffLimit: 2
ttlSecondsAfterFinished: 3600
completions: 1                    # 1 for single-run; N for parallel
parallelism: 1                    # concurrent pods; for fan-out workloads
completionMode: NonIndexed        # NonIndexed | Indexed (for work-queue patterns)
```

For parallel fan-out jobs (e.g. "process these 100 work items across 10
pods"), use `Indexed` mode with `parallelism: 10, completions: 100`.

## Opinionated defaults

| Knob                               | Default      | Rationale                                      |
|------------------------------------|--------------|------------------------------------------------|
| `backoffLimit`                     | `2`          | Retry transient failures; 2 is conservative    |
| `activeDeadlineSeconds`            | `3600`       | Kill runaway; most bootstrap jobs < 10 min     |
| `ttlSecondsAfterFinished`          | `3600`       | Keep the Job object for 1h for log viewing     |
| `completions`                      | `1`          | Single run default                             |
| `parallelism`                      | `1`          | Single pod default                             |
| `completionMode`                   | `NonIndexed` | Indexed is opt-in                              |

## Example values

```yaml
app:
  name: codectl-db-migrate
  partOf: codectl
env: prod

image:
  repository: ghcr.io/mateosegura/codectl-migrator
  tag: v1.42.0

job:
  command: ["/bin/migrate", "up"]
  helmHook:
    events: ["post-install", "post-upgrade"]
    weight: 5
    deletePolicy: before-hook-creation,hook-succeeded

activeDeadlineSeconds: 600        # 10-min max

resources:
  requests: { cpu: 100m, memory: 128Mi }
  limits:   { cpu: 500m, memory: 128Mi }

secrets:
  - { key: DATABASE_URL, bwItem: app-codectl-db, bwProperty: uri, mode: env }

networkPolicy:
  allowEgressTo:
    - namespace: platform-databases
    - namespace: platform-secrets
```

## Fan-out example

```yaml
app:
  name: fintel-signal-reprocess
env: prod

job:
  command: ["/bin/fintel", "reprocess", "--index=$JOB_COMPLETION_INDEX"]

completions: 100
parallelism: 10
completionMode: Indexed

activeDeadlineSeconds: 21600       # 6-hour max
backoffLimit: 0                    # don't retry failed indices — investigate manually
```

## Status

Skeleton. Templates are stubs.
