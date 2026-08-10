# charts/job

A single-run `Job`. It runs to completion, then it is removed. It is not
scheduled, and it does not run for a long time.

## When to pick this

- A database migration that runs during an app deploy, as a Helm `post-install`
  or `post-upgrade` hook.
- A single data backfill, a schema rewrite, or a cache warmup.
- A bootstrap task during the initialization of a cluster or an app.
- An operation that a person starts by hand, one time.

If the workload runs on a schedule, pick `cronjob`. If it runs for a long time,
pick `worker`.

## What the chart emits

- `Job` — with optional Helm hook annotations (pre-install, post-install,
  pre-upgrade, post-upgrade, pre-delete).
- `ServiceAccount`, `ExternalSecret`, `NetworkPolicy`.
- No Service, no HPA, no PDB.

## Helm hook integration

A job that is part of the lifecycle of another chart annotates itself as a Helm
hook:

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

Use this pattern for a database migration paired with a `stateless-app` release,
and for similar cases.

## The requirement for idempotency

An app must make the body of a job idempotent whenever that is possible. The
default `backoffLimit` of the chart is 2, so a job that fails runs again. A body
that is not idempotent therefore causes duplicate effects when it runs again.

## Run semantics

```yaml
activeDeadlineSeconds: 3600
backoffLimit: 2
ttlSecondsAfterFinished: 3600
completions: 1                    # 1 for single-run; N for parallel
parallelism: 1                    # concurrent pods; for fan-out workloads
completionMode: NonIndexed        # NonIndexed | Indexed (for work-queue patterns)
```

For a parallel fan-out job, for example the processing of 100 work items across
10 pods, use the `Indexed` mode with `parallelism: 10, completions: 100`.

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

Install as release `codectl-db-migrate` in namespace `codectl-prod`:

```yaml
project: codectl                    # namespace: codectl-prod
env: prod
app:
  name: db-migrate                  # full identifier: codectl-db-migrate

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
  - { key: DATABASE_URL, bwItem: codectl-db, bwProperty: uri, mode: env }

networkPolicy:
  allowEgressTo:
    - namespace: platform-databases
    - namespace: platform-secrets
```

## Fan-out example

```yaml
project: fintel                     # namespace: fintel-prod
env: prod
app:
  name: signal-reprocess            # full identifier: fintel-signal-reprocess

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
