# CI — platform (the `concord-ci` Helm chart)

The CI platform is a **separate** Helm release in the `devops` namespace, fully independent from the main `concord` chart. It hosts the scheduled CronJobs (nightly + weekly), its own MinIO for artifact storage, and a SvelteKit dashboard (ci-admin). When the main platform crashes, the CI platform survives — and vice versa.

Refresh this file when: a CronJob is added, removed, or its schedule changes; the chart's templates change shape; the CI dashboard image or routing changes; an external secret it depends on changes; the workload-type for `devops` nodes changes.

## Location

```
deploy/ci/
├── ctl.sh                        # lifecycle CLI (start/stop/update/status/logs/diff)
├── project.json                  # `deploy-ci` Nx project
├── README.md
└── helm/concord-ci/
    ├── Chart.yaml                # name: concord-ci, version: 0.1.0
    ├── values.yaml               # all defaults inline (no per-env overrides)
    ├── files/entrypoint.sh       # nightly CronJob entrypoint (copied into ConfigMap)
    └── templates/
        ├── _helpers.tpl
        ├── admin-deployment.yaml      # ci-admin Deployment + Service
        ├── configmap.yaml             # concord-ci-config (env vars)
        ├── data-pvc.yaml              # 1Gi PVC for SQLite + reports
        ├── entrypoint-configmap.yaml  # concord-ci-entrypoint (boots ci-runner)
        ├── ingress.yaml               # Traefik ingress for admin.<host>
        ├── minio.yaml                 # ci-minio Deployment + PVC + Service
        ├── nightly-cronjob.yaml       # concord-ci-nightly
        ├── secrets.yaml               # concord-ci-secrets (MinIO creds)
        └── weekly-cronjob.yaml        # concord-ci-weekly
```

## Release identity

- Helm release name: `concord-ci`
- Namespace: `devops`
- Chart version: `0.1.0` (independent from the main platform chart's `0.2.0`)
- Workload label: pods land on nodes with `concord.corekinect.com/workload-devops=true` (currently `concordproxy` + `wanda`)
- Identifying label: every resource has `app.kubernetes.io/part-of=concord-ci`

## What it deploys

| Template | Resource | Purpose | Gate |
|---|---|---|---|
| `minio.yaml` | `Deployment/concord-ci-minio` + `PVC/concord-ci-minio` (5Gi) + `Service` | Artifact + report storage for CI runs. Separate from the platform's MinIO. | `minio.enabled` |
| `admin-deployment.yaml` | `Deployment/concord-ci-admin` + `Service` (port 3000) | SvelteKit + adapter-node dashboard. Reads SQLite at `/data/concord-ci.db`. | `admin.enabled` |
| `data-pvc.yaml` | `PVC/concord-ci-data` (1Gi) | SQLite database + run report archive for the dashboard. | always |
| `nightly-cronjob.yaml` | `CronJob/concord-ci-nightly` | Daily 02:00 America/Chicago. ci-runner + DinD sidecar. | `nightly.enabled` |
| `weekly-cronjob.yaml` | `CronJob/concord-ci-weekly` | Saturday 03:00 America/Chicago. ci-runner only (no DinD). | `weekly.enabled` |
| `ingress.yaml` | `Ingress/concord-ci-ingress` | `admin.<host>` → ci-admin. Traefik. | `ingress.enabled && admin.enabled` |
| `configmap.yaml` | `ConfigMap/concord-ci-config` | Env vars: repo URL, branch, MinIO endpoint, dashboard URL. | always |
| `entrypoint-configmap.yaml` | `ConfigMap/concord-ci-entrypoint` | The bash entrypoint script run by the nightly CronJob's `ci-runner` container. | always |
| `secrets.yaml` | `Secret/concord-ci-secrets` | MinIO root credentials, derived from `values.yaml.minio.rootPassword`. | always |

## Values overview (defaults from `values.yaml`)

| Key | Default | What |
|---|---|---|
| `global.namespace` | `devops` | Target namespace |
| `global.imagePullPolicy` | `Always` | |
| `global.nodeSelector` | `concord.corekinect.com/workload: devops` | Where everything runs |
| `minio.enabled` | `true` | |
| `minio.image` | `minio/minio:RELEASE.2024-11-07T00-52-20Z` | |
| `minio.storage` | `5Gi` | |
| `minio.rootUser` / `rootPassword` | `ci-minio` / `ci-minio-changeme` | Override before deploying to a shared cluster |
| `admin.enabled` | `false` (by default; set true to expose dashboard) | |
| `admin.image.repository` | `containers.ad.corekinect.com/concord-ci-admin` | |
| `admin.image.tag` | `latest` | |
| `admin.port` | `3000` | |
| `data.storage` | `1Gi` | SQLite DB volume |
| `nightly.enabled` | `true` | |
| `nightly.schedule` | `"0 2 * * *"` | Daily 02:00 |
| `nightly.timeZone` | `"America/Chicago"` | |
| `nightly.activeDeadlineSeconds` | `7200` | 2-hour cap |
| `nightly.image` | `containers.ad.corekinect.com/concord-devcontainer-base:latest` | |
| `nightly.resources.runner` | requests 4 CPU / 8Gi, limits 6 / 12 | |
| `nightly.resources.dind` | requests 2 / 4Gi, limits 4 / 8 | |
| `weekly.enabled` | `true` | |
| `weekly.schedule` | `"0 3 * * 6"` | Saturday 03:00 |
| `weekly.timeZone` | `"America/Chicago"` | |
| `weekly.resources` | requests 2 / 4Gi, limits 4 / 8 | |
| `ingress.host` | `concord.local` | Dashboard at `admin.<host>` |
| `ingress.tls.secretName` | `concord-ci-tls` | Separate from the platform's `concord-tls` |
| `config.repoUrl` | `git@bitbucket.org:corekinect/concord.git` | What the runners clone |
| `config.branch` | `main` | Which branch to clone |
| `config.minioBucket` | `ci` | Bucket name for artifact storage |

## The two CronJobs

### `concord-ci-nightly`

Runs daily at 02:00 (Chicago). Two containers per Job:

- **`ci-runner`** — devcontainer-base image. Mounts: `bitbucket-ssh-key` (optional), `ca-certs` (optional), `claude-code-oauth` (optional), entrypoint ConfigMap. Workflow:
  1. Install CA certs.
  2. Wait for the DinD sidecar's socket.
  3. Clone the repo via SSH.
  4. Run `./.ci/run nightly` (see [`pipelines.md`](pipelines.md)).
  5. Upload `/tmp/ai-review/*` to ci-minio via `mc`.
- **`dind` (sidecar)** — Docker-in-Docker. Used to rebuild devcontainer images during the nightly sweep. Host-path-mounted at `/var/lib/concord/ci/docker` so layers survive between runs.

The Job pod has `concurrencyPolicy: Forbid` and `backoffLimit: 0` — no retries, no concurrent runs.

### `concord-ci-weekly`

Runs Saturday at 03:00 (Chicago). Single container (`ci-runner`); no DinD. Runs `./.ci/run weekly` — purely AI + static analysis. Result reports POST to the ci-admin dashboard.

## External secrets (consumed but not managed)

The chart references these Secrets in CronJob mounts with `optional: true`. They must already exist in `devops`, created by `infrastructure/clusters/office/secrets/create-all.sh devops`:

| Secret | Purpose |
|---|---|
| `bitbucket-ssh-key` | Git clone of the repo |
| `corekinect-ca-certs` | Internal CA trust for `pip install`, `git clone` against internal hosts |
| `claude-code-oauth` | AI review auth (`credentials.json`) |
| `dockerhub-credentials` | Docker Hub rate-limit bypass (referenced via `imagePullSecrets` on the Job pods — only if configured) |

See [`../deploy/secrets.md`](../deploy/secrets.md) for the full secret inventory.

## Internal secrets (managed by this chart)

`templates/secrets.yaml` renders `Secret/concord-ci-secrets` with:

```yaml
stringData:
  MINIO_ROOT_PASSWORD: {{ .Values.minio.rootPassword | quote }}
  MINIO_ACCESS_KEY:    {{ .Values.minio.rootUser    | quote }}
  MINIO_SECRET_KEY:    {{ .Values.minio.rootPassword | quote }}
```

Rotating these means editing `values.yaml` and `helm upgrade`-ing — the MinIO Deployment picks up the new password on next pod restart, after which any existing client connections fail until re-authed.

## Dashboard (ci-admin)

SvelteKit + `adapter-node`. Pages:

- **Overview** — sparklines, recent runs.
- **Runs** — filter by pipeline + verdict; click into a run.
- **Run Detail** — collapsible stage cards (GitHub Actions style) with findings + captured logs.
- **Trends** — issue/cost charts over 14 days.
- **Hotspots** — files most-flagged across reviews.

Persists in SQLite on the 1Gi `concord-ci-data` PVC. Receives runs via `POST /api/runs` from the weekly pipeline.

URLs:

- Production: `admin.concord.local` (or `admin.<ingress.host>`).
- Staging: `admin.staging.concord.local` (separate `concord-ci` release in another devops namespace, when present).
- Local dev: `cd apps/ci/admin && npm run dev` → `http://localhost:4300`.

The dashboard image is built **on-demand** by `deploy/ci/ctl.sh update`:

```bash
docker buildx build \
  --file apps/frontend/ci-admin/deploy/Dockerfile \
  --tag containers.ad.corekinect.com/concord-ci-admin:latest \
  --load .
```

It's tagged `:latest` (not pinned to env) because there's only one CI dashboard cluster-wide.

## Lifecycle

```
nx run deploy-ci:start       # helm upgrade --install concord-ci
nx run deploy-ci:stop        # helm uninstall (PVCs survive)
nx run deploy-ci:update      # rebuild dashboard image + helm upgrade
nx run deploy-ci:status      # kubectl get all -n devops -l app.kubernetes.io/part-of=concord-ci
nx run deploy-ci:diff        # helm diff
nx run deploy-ci:logs        # tail concord-ci-admin
nx run deploy-ci:trigger-nightly  # kubectl create job --from=cronjob/concord-ci-nightly
nx run deploy-ci:trigger-weekly   # kubectl create job --from=cronjob/concord-ci-weekly
```

Underlying script: `bash deploy/ci/ctl.sh <action>`. Direct invocation is allowed for the CI chart (it's outside the main platform's nx-only discipline) but `nx run deploy-ci:*` is preferred.

## Independent failure domain

The CI platform is deliberately decoupled from the main concord platform:

- Different namespace (`devops` vs `staging`/`production`).
- Different MinIO (`concord-ci-minio` vs `concord-minio`).
- Different DB (SQLite in admin vs Postgres in concord).
- Different node pool (`workload-devops` vs `workload-platform`).
- Different Helm release, chart, values.

Consequence: a broken platform deploy does not stop the nightly CI run, and vice versa. The CI dashboard can also serve as a post-mortem viewer when the platform is down (it's read-only against its SQLite).

## How to add a new CronJob

1. Drop `templates/<name>-cronjob.yaml` modeled on `weekly-cronjob.yaml`.
2. Add a `<name>:` block to `values.yaml` (`enabled`, `schedule`, `timeZone`, `image`, `resources`).
3. Add the matching pipeline script in `.ci/pipelines/<name>.sh` (the CronJob's `args` should call `./.ci/run <name>`).
4. Add a `trigger-<name>` target to `deploy/ci/project.json` so operators can run it on demand.
5. Update this file's CronJob list and [`pipelines.md`](pipelines.md).

## How to change the schedule

1. Edit `values.yaml` (`nightly.schedule` or `weekly.schedule`). Use cron syntax in the `timeZone` specified (`timeZone: America/Chicago`).
2. `nx run deploy-ci:update`.
3. Verify: `kubectl get cronjob -n devops -l app.kubernetes.io/part-of=concord-ci`.

## Common failure modes

- **Nightly CronJob's Job pod stays `Pending`** — no `workload-devops` node has capacity (the runner container requests 4 CPU + 8Gi). Either scale up `wanda`/`concordproxy` or temporarily reduce `nightly.resources.runner.requests`.
- **`error: failed to pull image "containers.ad.corekinect.com/concord-devcontainer-base:latest"`** — internal registry unreachable from the `devops` namespace. Check NetworkPolicy and that `corekinect-ca-certs` is mounted (the image hostname is internal-only).
- **DinD socket never appears** — `/var/lib/concord/ci/docker` host path is wrong or unwritable. Check the host node's filesystem; the DinD sidecar logs are the diagnostic.
- **`POST /api/runs` 502s from the runner** — `concord-ci-admin` is `CrashLoopBackOff` (often a SQLite migration). Check `kubectl logs deployment/concord-ci-admin -n devops`.
- **`mc cp` fails to ci-minio** — `MINIO_ACCESS_KEY`/`SECRET_KEY` mismatch between `concord-ci-secrets` and the runner's env. The `ci-minio-upload` Secret (from `create-all.sh`) is a separate path used by the *weekly* pipeline; the *nightly* one uses `concord-ci-secrets` directly. Don't conflate them.
- **`admin.concord.local` 404** — `admin.enabled: false` in values. Default is off; set `--set admin.enabled=true` or edit values and `nx run deploy-ci:update`.
- **Manual trigger fails with `cronjobs.batch "concord-ci-nightly" not found`** — the chart isn't installed in `devops`. Run `nx run deploy-ci:start`.

## Related knowledge

- [`pipelines.md`](pipelines.md) — the `.ci/run nightly` / `weekly` scripts these CronJobs invoke.
- [`../deploy/overview.md`](../deploy/overview.md) — the `devops` namespace in the cluster topology.
- [`../deploy/secrets.md`](../deploy/secrets.md) — the external secrets the CronJobs mount.
- [`../deploy/nx-targets.md`](../deploy/nx-targets.md) — the `deploy-ci` Nx target catalog.
- [`../deploy/network.md`](../deploy/network.md) — the `admin.<host>` ingress + TLS Secret.
