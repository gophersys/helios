# Deploy — Helm chart

One Helm chart drives both staging and production. The chart lives at `deploy/production/helm/concord/`; per-environment values files sit one level up at `deploy/production/helm/values-staging.yaml` and `values-production.yaml`. The `production/` path is historical — both environments use this chart.

Refresh this file when: a new template is added or removed from `templates/`, a values key is renamed or its semantic changes, the staging/production diff changes meaningfully (replicas, resource limits, retention windows, scheduler concurrency), or the chart version bumps.

## Location

```
deploy/production/helm/
├── values-staging.yaml      # staging overrides
├── values-production.yaml   # production overrides
└── concord/
    ├── Chart.yaml           # name: concord, version: 0.2.0, appVersion: 0.2.0
    ├── values.yaml          # defaults (almost everything off by default)
    └── templates/
        ├── _helpers.tpl
        ├── configmap.yaml
        ├── http-api-deployment.yaml
        ├── http-api-service.yaml
        ├── http-api-serviceaccount.yaml
        ├── frontend-deployment.yaml
        ├── frontend-service.yaml
        ├── docs-deployment.yaml
        ├── build-service-deployment.yaml
        ├── git-poller-deployment.yaml
        ├── infra-postgres.yaml
        ├── infra-minio.yaml
        ├── infra-pypi.yaml
        ├── ingress.yaml
        ├── network-policies.yaml
        ├── pdb.yaml
        ├── resource-quotas.yaml
        ├── backup-cronjob.yaml
        └── retention-cronjob.yaml
```

The chart name in K8s is `concord` (the Helm release name set by `ctl.sh`).

## Templates — what each one renders

| File | Renders | Gate |
|---|---|---|
| `configmap.yaml` | `ConfigMap/concord-config` — every key from `.Values.config` plus `ENVIRONMENT`. | always |
| `http-api-deployment.yaml` | `Deployment/concord-http-api` with two init containers (`wait-for-db`, `migrate-and-seed`), the http-api container, and the `bitbucket-ssh-key` volume. | `httpApi.enabled` |
| `http-api-service.yaml` | `Service/concord-http-api` (ClusterIP, port 9001). | `httpApi.enabled` |
| `http-api-serviceaccount.yaml` | `ServiceAccount/concord-api` — used so the pod can call the K8s API to create runner Jobs and MTIB Deployments. | `httpApi.serviceAccount.create` |
| `frontend-deployment.yaml` | `Deployment/concord-frontend` (nginx serving the SvelteKit build). | `frontend.enabled` |
| `frontend-service.yaml` | `Service/concord-frontend` (port 80). | `frontend.enabled` |
| `docs-deployment.yaml` | `Deployment/concord-docs` (nginx serving the MkDocs static site). | `docs.enabled` |
| `build-service-deployment.yaml` | `Deployment/concord-build-service` — privileged (Docker socket mount), pinned to `workload-build` nodes, 40-min termination grace for in-flight builds. | `buildService.enabled` |
| `git-poller-deployment.yaml` | `Deployment/concord-git-poller` — `bitbucket-ssh-key` mount, polls Bitbucket on `gitPoller.pollInterval`. | `gitPoller.enabled` |
| `infra-postgres.yaml` | `StatefulSet/concord-postgres` + PVC + Service. PVC has `helm.sh/resource-policy: keep`. | `infrastructure.postgres.enabled` |
| `infra-minio.yaml` | `Deployment/concord-minio` + PVC + Service. PVC kept on uninstall. | `infrastructure.minio.enabled` |
| `infra-pypi.yaml` | `Deployment/concord-pypi` (htpasswd init container if auth enabled) + PVC + Service. | `infrastructure.pypi.enabled` |
| `ingress.yaml` | `Ingress/concord-ingress` — Traefik. Hosts: `{host}` (UI+API), `docs.{host}`, `pypi.{host}`. Routes `/v2`, `/auth`, `/socket.io` to http-api; everything else to frontend. | `ingress.enabled` |
| `network-policies.yaml` | Three `NetworkPolicy` resources: `concord-postgres-restrict`, `concord-minio-restrict`, `concord-http-api-restrict`. See [`network.md`](network.md). | `networkPolicies.enabled` |
| `pdb.yaml` | `PodDisruptionBudget` for http-api, build-service, frontend, git-poller. Single-replica services use `minAvailable: 0` to allow drain when not Ready. | per service `.enabled` |
| `resource-quotas.yaml` | `ResourceQuota/concord-resource-quota` — caps namespace CPU/memory. | `resourceQuotas.enabled` |
| `backup-cronjob.yaml` | `CronJob/concord-backup-postgres` (`pg_dump → gzip → MinIO`), `CronJob/concord-backup-minio` (weekly mirror), pre-upgrade backup hook, weekly verify job. | `backups.postgres.enabled` / `backups.minio.enabled` |
| `retention-cronjob.yaml` | `CronJob/concord-retention-test-packages` (daily prune), `CronJob/concord-retention-mfg-session-reaper` (every 15 min). | `retention.testPackages.enabled` / `retention.mfgSessionReaper.enabled` |

## `_helpers.tpl`

| Template | Output |
|---|---|
| `concord.labels` | `app.kubernetes.io/part-of: concord`, `managed-by: {{ .Release.Service }}`, `helm.sh/chart`. Applied to everything Helm renders — used by `ctl.sh`'s rollout verifier to scope the wait. |
| `concord.httpApi.selectorLabels` | `app.kubernetes.io/name: concord-http-api`, `component: backend`. |
| `concord.frontend.selectorLabels`, `concord.buildService.selectorLabels`, `concord.gitPoller.selectorLabels`, `concord.docs.selectorLabels` | Same pattern per service. |
| `concord.workloadNodeSelector` | Renders `nodeSelector: concord.corekinect.com/workload-<type>: "true"` plus any per-service `extra` overrides. Every workload pod uses this. |

## Staging vs production — key differences

These are the keys that actually differ between `values-staging.yaml` and `values-production.yaml`. Everything else is identical (same image names, same template gates, same internal config).

| Key | staging | production |
|---|---|---|
| `global.environment` | `staging` | `production` |
| `ingress.host` | `staging.concord.ad.corekinect.com` | `concord.ad.corekinect.com` |
| `infrastructure.postgres.storage` | `10Gi` | `20Gi` |
| `infrastructure.minio.storage` | `15Gi` | `25Gi` |
| `infrastructure.pypi.storage` | `3Gi` | `5Gi` |
| `httpApi.resources.requests.cpu` | `100m` | `250m` |
| `httpApi.image.tag` | `staging` | `production` |
| `frontend.image.tag` | `staging` | `production` |
| `buildService.image.tag` | `staging` | `production` |
| `gitPoller.image.tag` | `staging` | `production` |
| `docs.image.tag` | `staging` | `production` |
| `config.LOG_LEVEL` | `4` (debug) | `2` (info) |
| `config.BITBUCKET_POLLER_INTERVAL_S` | `15` | `300` |
| `config.MAX_CONCURRENT_BUILDS` | `4` | `8` |
| `config.MAX_CONCURRENT_VALIDATION_RUNS` | `8` | `16` |
| `config.MAX_CONCURRENT_MANUFACTURING_SESSIONS` | `4` | `8` |
| `config.MANUFACTURING_TIMEOUT_MINUTES` | `120` | `180` |
| `config.CORS_ORIGINS` | includes `http://localhost:4200` | locked to the production hostname |
| `config.CONCORD_API_HOST` | `staging.concord.ad.corekinect.com` | `concord.ad.corekinect.com` |
| `config.CONCORD_API_URL` (internal) | `http://concord-http-api.staging.svc.cluster.local:9001` | `http://concord-http-api.production.svc.cluster.local:9001` |
| `resourceQuotas.cpu` / `.memory` | `12` / `16Gi` | `32` / `40Gi` |
| `backups.postgres.retain` | `7` | `30` |

Identical between the two: `AUTH_ENABLED=true`, `MTIB_PORT=50053`, `BITBUCKET_WORKSPACE=corekinect`, `STORAGE_URL=http://concord-minio:9000`, `AUTH_SERVER_URL=https://auth.office.corekinect.cloud:2013`, `COREOPS_*`, `networkPolicies.enabled=true`, `infrastructure.{postgres,minio,pypi}.enabled=true`.

## Config that flows in via the chart vs in via Secrets

`ConfigMap/concord-config` is generated from `.Values.config` (the keys in the table above). It's mounted via `envFrom` on http-api, build-service, git-poller. **All non-secret config goes here.**

Secrets (`concord-secrets`, `concord-infra-credentials`, `concord-build-service-secrets`, `bitbucket-ssh-key`, `concord-pypi-htpasswd`, `coreops-credentials`, `theta-mcuboot-keys`, `corecloud-validation`) are **not** managed by Helm. They're created by `infrastructure/clusters/office/secrets/create-all.sh` from local `.env` files. Pods reference them by `valueFrom.secretKeyRef`. See [`secrets.md`](secrets.md).

## Forced rolling restart on upgrade

Each Deployment template carries two pod annotations:

```yaml
checksum/config: {{ include (print $.Template.BasePath "/configmap.yaml") . | sha256sum }}
rollme: {{ randAlphaNum 10 | quote }}
```

`checksum/config` triggers a restart whenever `concord-config` changes. `rollme` randomizes every `helm upgrade`, so a re-deploy with no value changes still rolls pods — required because images use floating `:staging` / `:production` tags and the actual image digest only changes after a `docker push`. Combined with `imagePullPolicy: Always`, pods always come up on the latest pushed image.

## Why rollout verification scopes to Helm-managed only

`_verify_rollout` in `ctl.sh` filters by `app.kubernetes.io/managed-by=Helm`. The same namespace also hosts dynamic MTIB deployments (`mtib-<verdin-host>-s<slot>`) created at runtime by http-api when fixtures come online. Those deployments carry `corekinect.com/managed-by=concord` (not `Helm`) and their readiness depends on the physical Verdin node being powered up — not on whether the platform deploy succeeded. Including them used to trigger spurious rollbacks every time a fixture was powered off.

## Recent history worth knowing

- **`BITBUCKET_WORKSPACE`** — caused the v0.9.18 incident. The var was referenced in code but absent from values files; staging had it via env injection, production didn't. Fixed by adding to both values files and adding a CI guard. The CI helm-values-completeness check now flags any required key missing from either file.
- **`MOTION_ENABLED`** — *not* in the Helm chart at all. It's derived per-fixture at MTIB deploy time by http-api's `_mtib_env_for_fixture(fixture)`. Validation fixtures get `MOTION_ENABLED=true`; manufacturing fixtures get `false`. Don't add it to the values files — it doesn't belong there.
- **httpApi memory bump** — staging requests `1Gi`, production same; limits are `2Gi`. Earlier (Q4 2025) the limit was `512Mi` and the pod OOM'd under build webhook bursts. Bumped after the incident.

## How to add a new template

1. Drop a new YAML in `deploy/production/helm/concord/templates/`. Gate it on a values key (`{{- if .Values.myThing.enabled }}`).
2. Add the labels via `{{ include "concord.labels" . | nindent 4 }}` and the appropriate selector helper.
3. Use `{{- include "concord.workloadNodeSelector" (dict "workload" "<type>" "extra" .Values.myThing.nodeSelector) | nindent 6 }}` for scheduling.
4. Add the values key to `concord/values.yaml` with sensible defaults.
5. Add overrides to `values-staging.yaml` and `values-production.yaml` — both, always (see [`../../rules/all-three-envs.md`](../../rules/all-three-envs.md)).
6. If the new resource is a Deployment that should be tracked by rollout verification, make sure it inherits `app.kubernetes.io/managed-by: Helm` (it does automatically via `concord.labels`).
7. Update this file's template table.

## How to add a new config key

1. Add it to `.Values.config` in `values-staging.yaml` AND `values-production.yaml`. The configmap template loops over the map, so no template change is needed.
2. Mirror it in `deploy/development/docker-compose.yaml` under the consuming service's `environment:` block.
3. If it's a secret, see [`secrets.md`](secrets.md) instead — never put credentials in `values.yaml`.
4. Read it in the service's Python code with a sensible default or explicit fail-fast.
5. Update this file's "Staging vs production" diff table if the value differs between envs.

## Common failure modes

- **Helm install fails with `release "concord" not found` on rollback** — too many stale release Secrets in the namespace. `_helm_deploy` cleans these (keeps last 5) on the next upgrade, but a fresh namespace plus a failed first install leaves no history. Solution: `helm uninstall concord -n <env> --keep-history=false` then retry.
- **`PVC pending forever`** — a PVC bound to a PV that no longer exists. `_cleanup_orphaned_pvcs` deletes these before each Helm install. If it still happens, the `local-path` provisioner is choking on the agent node.
- **Init container `migrate-and-seed` crashloops with `P3009`** — a previous migration failed to apply cleanly. The init container auto-resolves once (rolls back the failed migration and retries). If it loops twice, the migration is genuinely broken; fix it in `prisma/migrations/` and redeploy.
- **`Secret concord-config-… not found`** when chart references a renamed configmap — chart-rendered names follow `concord-config` (no per-release suffix). If you renamed it, all `envFrom.configMapRef` references must update too.
- **PypiServer fails with `htpasswd` missing** — `concord-pypi-htpasswd` Secret not synced. Run `nx run platform:sync-secrets -c <env>` after putting `PYPI_HTPASSWD` in `shared.env`.

## Related knowledge

- [`overview.md`](overview.md) — environments, topology, promotion flow.
- [`ctl-sh.md`](ctl-sh.md) — the CLI that runs `helm upgrade`.
- [`secrets.md`](secrets.md) — what *isn't* in the chart.
- [`network.md`](network.md) — ingress, TLS, NetworkPolicy.
- [`../prisma/migrations.md`](../prisma/migrations.md) — the init container that runs them.
