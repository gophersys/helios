# CI Platform Deployment

Standalone CI platform for Concord, deployed as a Helm chart in the `devops` namespace. Fully independent from the main application platform.

## Components

| Resource | Image | Purpose |
|---|---|---|
| `concord-ci-minio` | `minio/minio` | Artifact storage (5Gi PVC) |
| `concord-ci-admin` | `concord-ci-admin` | Dashboard (SvelteKit + SQLite) |
| `concord-ci-nightly` | `concord-devcontainer-base` | Nightly E2E CronJob (DinD) |
| `concord-ci-weekly` | `concord-devcontainer-base` | Weekly AI analysis CronJob |

## Commands

```bash
bash deploy/ci/ctl.sh start    # Install/upgrade Helm chart
bash deploy/ci/ctl.sh stop     # Uninstall (PVCs preserved)
bash deploy/ci/ctl.sh update   # Rebuild dashboard + redeploy
bash deploy/ci/ctl.sh status   # Show resources
bash deploy/ci/ctl.sh logs     # Tail dashboard logs
bash deploy/ci/ctl.sh diff     # Preview Helm changes
```

## Prerequisites

External secrets must exist in the `devops` namespace:

```bash
kubectl get secret -n devops bitbucket-ssh-key       # Git clone
kubectl get secret -n devops corekinect-ca-certs     # Internal TLS
kubectl get secret -n devops claude-code-oauth       # AI review auth
kubectl get secret -n devops dockerhub-credentials   # Docker Hub
```

Create them via: `bash infrastructure/clusters/office/secrets/create-all.sh devops`

## Dashboard

- **Production:** `admin.concord.local`
- **Staging:** `admin.staging.concord.local`
- **Local dev:** `cd apps/ci/admin && npm run dev` (port 4300)

## Overriding Values

```bash
# Test against a feature branch
helm upgrade concord-ci deploy/ci/helm/concord-ci -n devops \
  --set config.branch=feature/my-branch \
  --set admin.enabled=true

# Disable nightly runs
helm upgrade concord-ci deploy/ci/helm/concord-ci -n devops \
  --set nightly.enabled=false
```
