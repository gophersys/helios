---
paths:
  - "deploy/**/*"
  - "**/Dockerfile"
  - "**/project.json"
---

# Deployment Guide

## Architecture

```
Dev Machine (devcontainer)
  | build (Nx containerize)
  | import (docker save | k3s ctr images import)
K3s Cluster (10.4.45.10:6443)
  +-- staging namespace    (staging.concord.local)
  +-- production namespace (concord.local)
```

## Deploy Commands

```bash
./deploy/ctl.sh staging deploy      # Build + import + Helm upgrade (staging)
./deploy/ctl.sh production deploy   # Build + import + Helm upgrade (production)
./deploy/ctl.sh staging status      # Check pods/svc/ingress
./deploy/ctl.sh staging logs http-api  # Tail API logs
./deploy/ctl.sh diff staging        # Preview changes (needs helm-diff)
./deploy/ctl.sh status staging      # Shortcut for staging status
```

## How Deployment Works

1. `ctl.sh` calls `npx nx run <project>:containerize -c <env>` (defined in project.json)
2. Nx uses `@nx-tools/nx-container:build` which runs `docker build` with the service's Dockerfile
3. Images are tagged as `concord/<service>:<env>` + registry tag
4. Images imported into K3s via `docker save | sudo k3s ctr images import -`
5. Helm upgrade applies the chart with environment-specific values
6. Init container runs `prisma migrate deploy` before the API starts

## Key Files

| File | Purpose |
|------|---------|
| `deploy/ctl.sh` | Main deployment CLI |
| `deploy/helm/concord/` | Helm chart (templates, values) |
| `deploy/helm/values-staging.yaml` | Staging config overrides |
| `deploy/helm/values-production.yaml` | Production config overrides |
| `apps/backend/http-api/deploy/Dockerfile` | API container image |
| `apps/frontend/app/deploy/Dockerfile` | Frontend container image |
| `apps/backend/http-api/project.json` | Nx targets: containerize, push, deploy |
| `apps/frontend/app/project.json` | Nx targets: containerize, push, deploy |

## Adding a New Service

1. Create `apps/<layer>/<service>/deploy/Dockerfile`
2. Create `apps/<layer>/<service>/project.json` with targets: `containerize`, `push`, `deploy`, `test`, `typecheck`, `serve`
3. Add Helm template at `deploy/helm/concord/templates/<service>-deployment.yaml`
4. Add config/secret entries to `values.yaml`, `values-staging.yaml`, `values-production.yaml`
5. Add image vars + build/import/push logic to `ctl.sh`

## DB Migrations

Migrations auto-run on every deploy via init container. To add a new migration:
```bash
cd prisma && npx prisma migrate dev --name <description>
```
Then deploy — the init container picks it up automatically.

## Rollback

```bash
helm rollback concord <revision> -n staging
helm rollback concord <revision> -n production
helm history concord -n staging  # List revisions
```

## Troubleshooting

- **Pod CrashLoopBackOff**: Check init container logs first: `kubectl logs <pod> -n staging -c migrate`
- **Image not found**: Verify import: `sudo k3s crictl images | grep concord`
- **Config mismatch**: Compare values: `helm get values concord -n staging`
