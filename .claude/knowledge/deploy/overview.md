# Deploy — overview

The platform ships through three environments: `development` (Docker Compose on the developer's machine), `staging` (K8s namespace `staging`), and `production` (K8s namespace `production`). All three live in this repo. A single bash CLI (`deploy/ctl.sh`) and a single Helm chart (`deploy/production/helm/concord/`) drive every transition; Nx is the only sanctioned entry point.

Refresh this file when: an environment is added or removed, the cluster topology changes (new server/agent/edge node, new namespace), the image-tag strategy changes, or the staging → production promotion flow changes.

## The three environments

| Env | Runtime | Config source | Where state lives |
|---|---|---|---|
| `development` | Docker Compose | `deploy/development/docker-compose.yaml` + `deploy/development/.env` | Compose volumes on the dev host |
| `staging` | K3s namespace `staging` | `deploy/production/helm/concord/` + `values-staging.yaml` | PVCs in the office cluster |
| `production` | K3s namespace `production` | `deploy/production/helm/concord/` + `values-production.yaml` | PVCs in the office cluster |

`values-staging.yaml` and `values-production.yaml` sit next to each other; the chart they override is shared. Whatever changes in one **must** change in the other and in the compose file. See [`../../rules/all-three-envs.md`](../../rules/all-three-envs.md).

## Cluster topology — office K3s

Single K3s v1.33.x install. 3 control-plane + agents + edge nodes. Defined in `infrastructure/clusters/office/cluster.yaml`:

```
control-plane (etcd, masters)        agents (workers)
─────────────────────────────        ─────────────────────────────
concordserver01  10.4.45.11          concordagent01  10.4.45.21
concordserver02  10.4.45.12          concordagent02  10.4.45.22
concordserver03  10.4.45.13          concordagent03  10.4.45.23
                                     concordproxy    10.4.45.30
                                     wanda           10.4.45.32

edge (ARM64 Verdin iMX8MM, one per fixture)
────────────────────────────────────────────
verdin-imx8mm-15005696  10.4.45.33
verdin-imx8mm-15005670  10.4.45.34
verdin-imx8mm-15005721  10.4.45.36
verdin-imx8mm-15005714  10.4.45.37
verdin-imx8mm-15005668  10.4.45.39
```

API server: `https://10.4.45.10:6443` (HAProxy VIP fronting the three control-plane nodes).

## Workload types → node selector

Pods are scheduled by **workload type**, not by node name. `bootstrap.sh` labels each node with `concord.corekinect.com/workload-<type>=true` for every type it serves; pods set `nodeSelector: concord.corekinect.com/workload-<type>: "true"` via the `concord.workloadNodeSelector` helper.

| Workload | Runs | Hosts |
|---|---|---|
| `platform` | http-api, frontend, docs, git-poller, pypi | concordserver01-03, concordagent01-02 |
| `data` | postgres, minio | concordserver03, concordagent01, concordagent03 |
| `build` | build-service, dynamic builder containers | wanda |
| `devops` | concord-ci-* (separate Helm chart) | concordproxy, wanda |
| `worker` | validation/manufacturing K8s Jobs | concordagent01-03 |
| `edge` | per-fixture mtib-server deployments | verdin-imx8mm-* |

Full requirements in `infrastructure/clusters/office/cluster.yaml`. See [`verdin-edge.md`](verdin-edge.md) for how edge nodes onboard.

## Namespaces

| Namespace | Purpose | Helm release |
|---|---|---|
| `staging` | Pre-prod platform | `concord` (deploy/production/helm/concord) |
| `production` | Live platform | `concord` (same chart, different values) |
| `validation` | K8s Jobs spawned by http-api for validation/manufacturing runs | (no Helm — dynamic) |
| `devops` | CI platform | `concord-ci` (deploy/ci/helm/concord-ci) |
| `development` | Reserved for cluster-side dev experiments | (mostly unused; local dev is Compose) |

Manufacturing/validation **runner pods** land in the `validation` namespace regardless of the platform env — http-api sets that via `VALIDATION_NAMESPACE`. NetworkPolicy entries in `staging` and `production` explicitly allow inbound from `validation`.

## Image tag strategy

Images live at `containers.ad.corekinect.com/concord-*`:

- `concord-http-api`, `concord-frontend`, `concord-git-poller`, `concord-build-service`, `concord-docs`, `concord-test-runner`

Tags applied per build:

| Tag | When set | Read by |
|---|---|---|
| `:staging` | every main-branch deploy to staging | `values-staging.yaml` (`tag: staging`) |
| `:production` | every release-pipeline deploy to production | `values-production.yaml` (`tag: production`) |
| `:<env>-<sha>` | runner only, set by `ctl.sh` for traceability | manual debug |

The values files reference floating tags (`staging`, `production`) — the chart pins by environment, not by version. `helm upgrade` re-pulls because `global.imagePullPolicy: Always` and the deployment template stamps an annotation `rollme: <random>` to force a rolling restart. The canonical platform version is `/VERSION` and `ctl.sh::get_version` stamps it into images as the `APP_VERSION` build arg.

## Promotion flow

```
dev branch ──┐
             │ open PR
             ▼
        [.ci PR pipeline]   lint, typecheck, test, build, smoke
             │ merge to main
             ▼
        [.ci main pipeline] build :staging, push, helm upgrade staging,
             │              publish corectl wheel, smoke staging
             ▼
        staging                                 (verified)
             │ manual trigger (release pipeline) OR /concord-release skill
             ▼
        [.ci release pipeline] re-smoke staging,
             │                 build :production, push,
             │                 helm upgrade production,
             │                 publish corectl wheel,
             │                 smoke production, git tag
             ▼
        production
```

Staging deploy is automatic on every merge to `main`. Production deploy is **manual** — triggered from Bitbucket Pipelines or by running `/concord-release`. Both routes call the same `release.sh` pipeline. See [`../ci/pipelines.md`](../ci/pipelines.md).

The Nx wrapper:

| Step | Nx target |
|---|---|
| Deploy staging | `nx update platform -c staging` |
| Deploy production | `nx update platform -c production` |
| Preview diff first | `nx diff platform -c <env>` |
| Roll back | `nx rollback platform -c <env>` |

See [`nx-targets.md`](nx-targets.md) for the full catalog.

## What ships with each deploy

`ctl.sh <env> update` runs the chain:

1. **Preflight** — `kubectl cluster-info`, `helm` installed.
2. **Secrets** — `kubectl get secret concord-secrets` + `concord-infra-credentials`. If missing or `--sync-secrets`, runs `infrastructure/clusters/office/secrets/create-all.sh <env>`. See [`secrets.md`](secrets.md).
3. **Build** — `docker buildx build` for each image in parallel; tag `:<env>`.
4. **Push** — `docker push` (or `k3s ctr images import` if running on-cluster).
5. **Helm upgrade** — `helm upgrade --install concord deploy/production/helm/concord -n <env> -f values-<env>.yaml`, with `--timeout 600s` and no `--wait`.
6. **Rollout verify** — wait on every Helm-managed Deployment (excludes dynamic MTIB deployments — see [`helm.md`](helm.md) for why).
7. **Smoke test** — exec into a running http-api pod and curl `/v2/docs`. Plus a pod-running check for build-service.
8. **Rollback on failure** — if either verify or smoke fails, `helm rollback` to the last `deployed` revision.

## How to add a new environment

Rare. The shape of "another environment" is "another K8s namespace with its own values file":

1. Add the namespace to `infrastructure/clusters/office/cluster.yaml::namespaces`.
2. Create `deploy/production/helm/values-<env>.yaml` based on the closest existing one.
3. Add `<env>` configurations to every Nx target in `deploy/project.json` (start/update/stop/status/restart/sync-secrets/diff/rollback).
4. Add `<env>.env` to `infrastructure/clusters/office/secrets/` and update `.env.example`.
5. Update `ctl.sh` dispatch case if the env name doesn't fit `staging|production` (currently the case statement is hard-coded).
6. Refresh this file's table + the namespace table.

## Common failure modes

- **`Cannot reach Kubernetes cluster`** — `_preflight` failed. The dev's `kubeconfig` is wrong or VPN/WSL routing is down. Run `kubectl cluster-info` directly; the office cluster API is `10.4.45.10:6443`.
- **`No previous revision to rollback to`** — first deploy ever failed verification. Investigate the helm release directly (`helm history concord -n <env>`); the cleanup of stale Helm release secrets (>5) in `_helm_deploy` only triggers on subsequent deploys.
- **`one or more deployments failed to reach Ready state`** — image pull, init-container migration crash, or readiness probe still red. `kubectl logs -n <env> <pod> -c migrate-and-seed` is the first thing to check.
- **MTIB pods drag the verify step down** — they shouldn't; verification is scoped to `app.kubernetes.io/managed-by=Helm`. If MTIB pods are blocking rollouts, the chart's labelling regressed — fix the helper.
- **Stale `concord-tls` Secret** — production cert expired. cert-manager renews it; if it's stuck, inspect `Certificate/staging-concord-tls` in the namespace.

## Related knowledge

- [`helm.md`](helm.md) — chart layout, values-by-environment diff, template inventory.
- [`ctl-sh.md`](ctl-sh.md) — every subcommand the CLI exposes.
- [`nx-targets.md`](nx-targets.md) — the Nx entry points that wrap `ctl.sh`.
- [`secrets.md`](secrets.md) — secret inventory + rotation.
- [`network.md`](network.md) — ingress, TLS, internal DNS.
- [`verdin-edge.md`](verdin-edge.md) — edge node onboarding.
- [`../ci/pipelines.md`](../ci/pipelines.md) — what builds and pushes those `:staging` / `:production` tags.
- [`../ci/ci-platform.md`](../ci/ci-platform.md) — the separate CI Helm chart in `devops`.
