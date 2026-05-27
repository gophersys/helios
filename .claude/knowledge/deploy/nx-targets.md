# Deploy — Nx targets

Nx is the only sanctioned entry point for build/test/deploy/run operations in this repo. Per [`../../rules/nx-only.md`](../../rules/nx-only.md), never invoke `docker`, `helm`, `kubectl apply`, `pnpm run <script>`, or `bash deploy/ctl.sh …` directly — go through Nx so caching, dependency graph, and preflight checks aren't bypassed.

This file catalogs the Nx targets that exist in `deploy/project.json` (project `platform`) and `deploy/ci/project.json` (project `deploy-ci`), with the underlying `ctl.sh` subcommand each one shells into.

Refresh this file when: an Nx target is added, renamed, or removed in any deploy-related `project.json`; a target's underlying command changes; a new configuration is added (e.g., a new environment).

## Project map

| Project | `project.json` | Domain |
|---|---|---|
| `platform` | `deploy/project.json` | Main concord platform — http-api, frontend, build-service, git-poller, docs, infrastructure. |
| `deploy-ci` | `deploy/ci/project.json` | The standalone CI Helm chart in `devops`. |
| `test-runner` | `deploy/runner/project.json` | The Python runner image baked once and reused by validation/manufacturing Jobs. |
| `ci` | `.ci/project.json` | Thin wrapper for the `.ci/` pipeline scripts. |
| `infrastructure` | `infrastructure/project.json` | Cluster bootstrap, secrets sync, RBAC. |
| `env` | `tools/env/project.json` | Provides the `env:preflight` dep that almost every deploy target runs first. |

Each backend app (`http-api`, `git-poller`, `build-service`) and the frontends have their own `build` / `push` targets — those build the images that `platform:update` then helm-deploys.

## `platform` target catalog

| Target | Configurations | Underlying command | Notes |
|---|---|---|---|
| `start` | `development` (default), `staging`, `production` | `bash deploy/ctl.sh <env> start` | Full 0→running. `dependsOn: env:preflight`. |
| `update` | `development` (default), `staging`, `production` | `bash deploy/ctl.sh <env> update` (staging + production also chain `bash scripts/record-release.sh <env>`) | Fast rebuild + redeploy. `forwardAllArgs: true` so `--sync-secrets` reaches `ctl.sh`. `dependsOn: env:preflight`. Since v0.12.13 the staging + production configurations also run `scripts/record-release.sh` after `ctl.sh update` returns so the env's `releases` table reflects every deploy — closes the 2026-05-27 gap where 0.12.6 through 0.12.12 deploys never showed up in the UI's /releases page. |
| `record-release` | `staging`, `production` | `bash scripts/record-release.sh <env>` | Standalone re-run of the release-record POST for the current `VERSION`. Use when a deploy was made out-of-band (e.g., direct `ctl.sh` invocation) and the record never landed. Idempotent — POSTs, falls back to PATCH on 409. |
| `stop` | `development` (default), `staging`, `production` | `bash deploy/ctl.sh <env> stop` | Production refuses without `--confirm-delete`. |
| `ready` | (no configs) | `bash deploy/ctl.sh development ready` | Re-migrate + re-seed dev DB without bouncing containers. |
| `status` | `development` (default), `staging`, `production` | `bash deploy/ctl.sh <env> status` | Compose `ps` for dev; `kubectl get pods,svc` for K8s. |
| `restart` | `staging`, `production` | `bash deploy/ctl.sh <env> restart` | Rolling restart of one or more deployments. `forwardAllArgs: true`. `dependsOn: env:preflight`. |
| `diff` | `staging`, `production` | `bash deploy/ctl.sh <env> diff` | `helm diff upgrade` against current cluster state. `dependsOn: env:preflight`. |
| `rollback` | `staging`, `production` | `helm history concord -n <env> --max 5` then `helm rollback concord -n <env>` | **Bypasses ctl.sh** — calls helm directly. Rolls back one revision. `dependsOn: env:preflight`. |
| `sync-secrets` | `staging`, `production`, `devops` | `bash infrastructure/clusters/office/secrets/create-all.sh <env>` | `dependsOn: env:preflight`. Forces a Secret re-sync from local `.env` files. |
| `check` | `development`, `staging` | `nx run-many -t test -p http-api corekinect && nx typecheck http-api && nx typecheck app` | Fast pre-deploy guardrail. Used by `release`. |
| `test` | (no configs) | `nx run-many -t test -p http-api corekinect app` | Aggregator of per-app `test` targets. |
| `test:integration` | (no configs) | `pytest tests/development/integration/ -v --timeout=60` | Requires the dev compose stack. |
| `test:e2e` | (no configs) | `pytest tests/development/e2e/ -v --timeout=300 -x` | E2E against the full dev stack. |
| `test:smoke` | `staging` (default), `production` | `pytest tests/smoke/ -v --timeout=30 --target-url=<env URL> --api-key=<CI admin key>` | Hits the deployed env's HTTPS endpoint. |
| `release` | `staging`, `production` | `platform:check` → `bash deploy/ctl.sh <env> update` → `platform:status` → `platform:test:smoke` | Multi-step deploy with pre/post checks. `dependsOn: env:preflight`. |

### Common invocations

```bash
# Dev
nx start platform                            # full local startup
nx update platform                           # fast rebuild + restart
nx ready platform                            # just re-seed DB

# Staging
nx update platform -c staging                # the bread-and-butter deploy
nx diff platform -c staging                  # preview before deploying
nx run platform:sync-secrets -c staging      # force secret resync
nx run platform:test:smoke -c staging        # remote smoke test only

# Production
nx update platform -c production             # via /concord-release skill in practice
nx rollback platform -c production           # undo last revision
nx stop platform -c production -- --confirm-delete

# Operations
nx run platform:status -c staging            # pods + services
nx logs platform -c staging                  # not a target — use `kubectl logs` or run ctl.sh directly

# Release record (auto-fires after nx update; this is the manual re-run)
nx run platform:record-release -c production
```

### `record-release` — auto-paired with every deploy

`scripts/record-release.sh <env>` runs automatically after every
`nx update platform -c {staging,production}` because the `update`
target's configuration chains them sequentially:

```json
"staging": {
  "commands": [
    "bash deploy/ctl.sh staging update",
    "bash scripts/record-release.sh staging"
  ],
  "parallel": false
}
```

What it does:

1. Reads `VERSION`, `git rev-parse HEAD`, `git rev-parse --abbrev-ref HEAD`. Falls back to `.git-build-info` if `git` is unavailable inside the devcontainer (submodule layout).
2. Looks up the previous version from `releases.createdAt DESC` and builds a changelog from `git log <prev>..HEAD`.
3. Picks the http-api pod, mints a JWT inside it using `JWT_SECRET_KEY` with `role: "ADMIN"` for the release-recorder user (`RELEASE_RECORDER_USER_ID` env var on the http-api Deployment; falls back to `mateo@corekinect.com`).
4. POSTs `/v2/releases`. On 409 (version already exists) PATCHes the existing row so re-runs are idempotent.
5. Verifies the top of the `releases` table matches `<VERSION>|RELEASED`.

Escape hatch: `CONCORD_SKIP_RELEASE_RECORD=1` skips the script (use only when you're intentionally deploying without recording — e.g., the deploy itself is being tested).

This contract closes the 2026-05-27 incident where `0.12.6` through `0.12.12` deploys all landed in production without ever creating a release record, because operators ran `nx update platform -c production` directly instead of going through `/concord-release` Phase 11.

## `deploy-ci` target catalog

| Target | Underlying command | Notes |
|---|---|---|
| `start` | `bash deploy/ci/ctl.sh start` | `helm upgrade --install concord-ci` in `devops` namespace. |
| `stop` | `bash deploy/ci/ctl.sh stop` | `helm uninstall concord-ci`; PVCs survive. |
| `update` | `bash deploy/ci/ctl.sh update` | Rebuilds the ci-admin image, then helm upgrade. |
| `status` | `bash deploy/ci/ctl.sh status` | Resources in the `devops` namespace tagged `app.kubernetes.io/part-of=concord-ci`. |
| `diff` | `bash deploy/ci/ctl.sh diff` | helm-diff preview. |
| `logs` | `bash deploy/ci/ctl.sh logs` | Tail `concord-ci-admin` logs (override component as an arg). |
| `trigger-nightly` | `kubectl create job -n devops --from=cronjob/concord-ci-nightly ci-manual-nightly-<ts>` | Run the nightly CI pipeline on demand. |
| `trigger-weekly` | `kubectl create job -n devops --from=cronjob/concord-ci-weekly ci-manual-weekly-<ts>` | Run the weekly AI-review pipeline on demand. |

See [`../ci/ci-platform.md`](../ci/ci-platform.md).

## `test-runner` target catalog

| Target | Configurations | Underlying command |
|---|---|---|
| `build` | `development` (default), `staging`, `production` | `nx run test-runner:containerize -c <env>` |
| `containerize` | same | `@nx-tools/nx-container:build` — buildx, file `deploy/runner/Dockerfile`, tags `concord/test-runner:<env>` and `containers.ad.corekinect.com/concord-test-runner:<env>` |
| `push` | same | `docker push containers.ad.corekinect.com/concord-test-runner:<env>` (no-op for `development`) |

The runner image is the base layer for K8s Jobs spawned by http-api during validation/manufacturing sessions. Build it once per release; runner Jobs reference the `:staging` or `:production` tag depending on which platform created them.

The image's `ENTRYPOINT` (`/app/entrypoint.sh`) branches on the `TEST_FRAMEWORK` env var injected by the backend:

- `PYTEST` (default; legacy) — downloads the test package, installs deps, runs `python3 /app/run.py --stage <stage>` or the direct `pytest tests/<stage>/` fallback.
- `ZTEST` — `exec python3 -m corekinect.test.ztest_runner --run-id ... --target-id ... --asset-set /app/assets --mtib-host ... --labels ...`. For the ZTEST path the backend ALSO overrides container `command` to `["python3", "-m", "corekinect.test.ztest_runner", ...]` so the entrypoint script is bypassed entirely — the entrypoint branch is the in-script safety net for callers that don't override command.

Dispatch lives in `apps/backend/http-api/src/services/kubernetes/runner_dispatch.py` and is wired from `manual.py` (staging/prod) and `scheduler.py` (Docker dev fallback). See `apps/backend/http-api.md` for the full flow.

## `ci` target catalog

| Target | Underlying command | Notes |
|---|---|---|
| `validate` | `bash .ci/run pr` | Run the full PR pipeline locally. |
| `status` | `bash deploy/ci/ctl.sh status` | Alias of `deploy-ci:status`. |
| `logs` | `bash deploy/ci/ctl.sh logs` | Alias of `deploy-ci:logs`. |

The actual pipeline scripts live in `.ci/pipelines/*.sh` — see [`../ci/pipelines.md`](../ci/pipelines.md).

## Per-app build/push targets

Every backend service and frontend has the same shape:

| Project | `build` (containerize) | `push` |
|---|---|---|
| `http-api` | `apps/backend/http-api/deploy/Dockerfile` → `concord-http-api:<env>` | `docker push` to `containers.ad.corekinect.com` |
| `git-poller` | `apps/backend/git-poller/deploy/Dockerfile` → `concord-git-poller:<env>` | same |
| `build-service` | `apps/backend/build-service/deploy/Dockerfile` → `concord-build-service:<env>` | same |
| `app` (frontend) | `apps/frontend/app/deploy/Dockerfile` → `concord-frontend:<env>` | same |
| `docs` | `apps/frontend/docs/deploy/Dockerfile` → `concord-docs:<env>` | same |
| `ci-admin` | `apps/frontend/ci-admin/deploy/Dockerfile` → `concord-ci-admin:latest` | (only deployed to `devops`, not staged) |
| `test-runner` | `deploy/runner/Dockerfile` → `concord-test-runner:<env>` | same |

These are normally invoked by `ctl.sh::cmd_build` (which runs `docker buildx` directly for parallelism), not by `nx affected -t build`. The `.ci/stages/build.sh` and `.ci/stages/push.sh` scripts use `nx affected` to build only changed projects.

## The `env:preflight` dependency

Almost every deploy target depends on `env:preflight`. That project (`tools/env/`) validates the local `.env` files, the kubeconfig context, and (for K8s envs) the `concord-tls` Secret. A failed preflight aborts the target before any state-changing work runs.

## Pitfalls

- **Don't `nx affected -t build` for a deploy** — the deploy chain in `ctl.sh::cmd_deploy` already builds in parallel via `docker buildx`. The `nx affected` path is for CI's "build only changed" optimization; running it from a developer machine duplicates work.
- **`nx run platform:rollback`** skips `ctl.sh` and calls `helm rollback` directly. If the rollback chain ever needs preflight (e.g., to refresh `.git-build-info` in the umbrella workspace), move that logic into the project.json `commands`, not into `ctl.sh`.
- **`forwardAllArgs: true`** is on `update` and `restart`. That's how `--sync-secrets` and target lists (`api frontend`) reach `ctl.sh`. Don't strip it.
- **`platform:test:smoke` hardcodes the API key** — `ck_ci_admin_x8K2mP9vL4nQ7wR1tY6uI3oA5sD0fG`. This is the seeded CI admin key, identical across environments. The smoke tests use it because they have to be invokable from CI without per-env secrets.

## How to add a new target

1. Decide which `project.json` owns it. Cross-cutting deploys go in `deploy/project.json`; per-app actions go in the app's `project.json`.
2. If it shells into `ctl.sh`, add the subcommand to `ctl.sh` first (see [`ctl-sh.md`](ctl-sh.md)).
3. Add the target with `defaultConfiguration` + per-env `configurations` if it differs per env.
4. Add `"dependsOn": [{ "projects": ["env"], "target": "preflight", "params": "forward" }]` if it touches the cluster.
5. Update this file's table.
6. Run `nx graph` to verify nothing else broke.

## Common failure modes

- **`Cannot find configuration "production" for target "update"`** — the configuration isn't defined under `targets.update.configurations`. Add it.
- **Stale Nx cache after `ctl.sh` outputs change** — `ctl.sh` doesn't write `dist/` so Nx never invalidates. If a target's behavior changed but Nx replays cached output, run `nx reset` or `nx run platform:update --skip-nx-cache`.
- **Wrong working directory** — every target sets `cwd: "{workspaceRoot}"`. If you add one without that, paths in `ctl.sh` (which `cd`s to repo root itself) still work, but Nx may resolve relative paths wrong.
- **`env:preflight` blocks unexpectedly** — preflight checks the local kubeconfig and `.env` completeness. Failing in CI usually means a Bitbucket Pipelines variable wasn't injected.

## Related knowledge

- [`ctl-sh.md`](ctl-sh.md) — the bash CLI these targets wrap.
- [`overview.md`](overview.md) — the env model.
- [`secrets.md`](secrets.md) — what `sync-secrets` actually pushes.
- [`../ci/pipelines.md`](../ci/pipelines.md) — how CI invokes these.
- [`../../rules/nx-only.md`](../../rules/nx-only.md) — the rule that says go through Nx.
