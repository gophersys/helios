---
paths:
  - "deploy/**/*"
  - "**/Dockerfile"
  - "**/project.json"
---

# Deployment Guide

## Architecture

```
deploy/ctl.sh <environment> <action>     # Single CLI for all environments
infrastructure/ctl.sh <cluster> <action> # Cluster provisioning (separate layer)

Environments:
  development   Docker Compose (local containers)
  staging       Kubernetes staging namespace
  production    Kubernetes production namespace
```

## Lifecycle Commands

```bash
# Development
nx start platform              # Full startup: protobuf → build → compose up → DB setup
nx update platform             # Fast: rebuild images → restart changed containers
nx stop platform               # Compose down

# Staging
nx start platform -c staging   # Preflight → infra bootstrap → secrets → build → deploy
nx update platform -c staging  # Secrets → rebuild → deploy (zero downtime)
nx stop platform -c staging    # Helm uninstall (keeps infrastructure)

# Status / Logs
nx run platform:status -c staging
./deploy/ctl.sh staging logs http-api
```

## How Deployment Works

1. `ctl.sh` builds **all** service images via `docker buildx build` (layer cached — unchanged services rebuild in <1s)
2. Default build targets: `api`, `frontend`, `git-poller`, `build-service`, `docs` (stock images like postgres, minio, pypi are not built)
3. Build metadata (version, environment, git commit, branch) is baked into every image via `--build-arg`
4. Images pushed to `containers.ad.corekinect.com` registry
5. Helm upgrade applies chart with environment-specific values
6. Init containers run in order: `wait-for-db` → `migrate-and-seed` (http-api)
7. Dependent services wait via init containers: build-service and git-poller wait for http-api
8. Rolling updates with `maxUnavailable: 0` ensure zero downtime

## Key Files

| File | Purpose |
|------|---------|
| `deploy/ctl.sh` | Platform CLI (all environments) |
| `deploy/project.json` | Nx project: start, update, stop, status |
| `deploy/production/helm/concord/` | Helm chart (templates, values) |
| `deploy/production/helm/values-staging.yaml` | Staging config |
| `deploy/production/helm/values-production.yaml` | Production config |
| `deploy/development/docker-compose.yaml` | Dev infrastructure |

## DB Migrations

Migrations + seeding auto-run on every deploy via init container (`migrate-and-seed`).
Prisma CLI and nodeenv are pre-warmed in the Docker image — zero runtime downloads.

```bash
# Create a new migration
cd prisma && npx prisma migrate dev --name <description>
```

## Rollback

```bash
helm rollback concord <revision> -n staging
helm history concord -n staging  # List revisions
```

## Troubleshooting

- **Pod CrashLoopBackOff**: Check init container logs: `kubectl logs <pod> -n staging -c migrate-and-seed`
- **Image not pulled**: Check `imagePullPolicy: Always` in values
- **Config mismatch**: `helm get values concord -n staging`
