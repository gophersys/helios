# Deploy — `ctl.sh`

`deploy/ctl.sh` is the single bash entry point for every platform lifecycle operation across all three environments. Nx targets shell out to it; CI pipelines shell out to it; the `/concord-release` skill shells out to it. **No-one calls `helm`, `docker compose`, or `kubectl apply -f` directly.**

Refresh this file when: a subcommand is added, renamed, or removed; the preflight/verify/smoke chain changes shape; the dispatch table changes; or the env list changes.

## Location

```
deploy/
├── ctl.sh                      # this file — 1200 lines, pure bash
└── ci/ctl.sh                   # separate CLI for the concord-ci chart
```

## Invocation shape

```
./deploy/ctl.sh <environment> <action> [args...]
```

Two-axis dispatch. Environments: `development | staging | production | version`. Actions vary per environment (development has the compose-only lifecycle; staging/production share the K8s lifecycle).

The script auto-detects `cd "$REPO_ROOT"` from `BASH_SOURCE`, so it can be invoked from anywhere.

## Subcommand catalog

### Development (`./deploy/ctl.sh development …`)

| Action | What it does |
|---|---|
| `start` | Full 0→running. Generates protobuf via `libs/protocols/ctl.sh generate`, builds http-api+git-poller+build-service via Nx, starts compose infra (`db`, `minio`, `pypi`), waits for Postgres, runs `_db_setup` (prisma generate → push → seed), starts the rest of compose, waits for http-api healthcheck. Prints service URLs. |
| `update` | Rebuild images via `docker compose build --parallel`, recreate containers without rebuilding cache. Calls `_db_setup` only if `prisma/schema.prisma` hash changed since last update (`~/.nx/prisma-schema-hash-dev`). |
| `stop` | `docker compose down`. In CI, also `-v --remove-orphans` for a clean slate. |
| `status` | `docker compose ps`. |
| `logs [component]` | `docker compose logs -f --tail=50 [component]`. |
| `ready` | Re-migrate + re-seed the DB without bouncing containers. Useful after pulling a branch with schema changes. |

### Staging / Production (`./deploy/ctl.sh staging …` or `production …`)

| Action | What it does |
|---|---|
| `start` | Full chain: `_preflight` → `infrastructure/ctl.sh office bootstrap` (idempotent) → `infrastructure/clusters/office/secrets/create-all.sh <env>` → `cmd_deploy` (build+push+helm) → `_verify_rollout` → `_smoke_test`. Auto-rollback on either failure. |
| `update [--sync-secrets]` | Like `start`, but skips bootstrap and skips secrets sync if `concord-secrets` + `concord-infra-credentials` already exist (use `--sync-secrets` to force). |
| `stop [--confirm-delete]` | `helm uninstall concord -n <env> --wait`. Production refuses without `--confirm-delete`. PVCs survive (`helm.sh/resource-policy: keep`). |
| `deploy [targets…]` | Just build+push+helm — no preflight, no verify, no smoke. Used by `start`/`update` internally; the `.ci/stages/deploy.sh` script also calls this. |
| `quick [targets…]` | Build+push+restart only. Skips Helm entirely — fastest path when only the image needs to change. Default targets: `api frontend`. |
| `status` | `kubectl get pods` + `kubectl get svc` in the namespace. |
| `logs [component]` | `kubectl logs -n <env> -l app.kubernetes.io/name=concord-<component> -f --tail=100`. |
| `restart [targets…]` | `kubectl rollout restart deployment/concord-<target>` + wait. Default targets: `api frontend`. |
| `diff` | `helm diff upgrade concord deploy/production/helm/concord -n <env> -f values-<env>.yaml`. Requires the `helm-diff` plugin. |

### Other

| Action | What it does |
|---|---|
| `version` | Reads `/VERSION`, suffixes `-<sha>` if HEAD isn't an exact `v<version>` tag. |

## Internal helpers (no-direct-invocation)

| Helper | Purpose |
|---|---|
| `get_version` | `VERSION` file + `git describe`. Stamped into images as `APP_VERSION`. |
| `_git_commit`, `_git_branch`, `_git_dirty`, `_git_describe` | Git metadata; fall back to `.git-build-info` when run inside a devcontainer where `git` cannot resolve the repo (notably: when this repo is a submodule of an umbrella workspace and the parent `.git/modules` is not mounted). See "Submodule context" below. |
| `_corekinect_sha` | Deterministic SHA for `libs/python/corekinect/` at HEAD. Primary: `git log -1 --format=%H -- libs/python/corekinect/`. Fallbacks: `git ls-tree -d HEAD libs/python/corekinect`, then line 4 of `.git-build-info`. Baked into runner images as `COREKINECT_GIT_SHA`; read back by `_check_runner_corekinect_freshness`. See [`runner.md`](runner.md) Layer 2. |
| `_check_runner_corekinect_freshness <env>` | Phase D Layer 2 gate. Called by `cmd_update` before `cmd_deploy`. Compares the runner image's baked `COREKINECT_GIT_SHA` (via `docker image inspect`) against `_corekinect_sha`. Fails when they diverge unless `CONCORD_FORCE_STALE_RUNNER=1`. Warns + passes on legacy images (no baked var) and on locally-missing images. Full behavior matrix in [`runner.md`](runner.md). |
| `_preflight` | `kubectl cluster-info` + `command -v helm`. Aborts if either fails. |
| `_db_setup` | `cd prisma && yarn prisma generate && prisma db push && python3 -m seed.main`. Development only. |
| `cmd_build <env> [targets…]` | Parallel `docker buildx build --load` for each target. Sets `APP_VERSION`, `ENVIRONMENT`, `GIT_*`, `BUILD_TIME`, `BUILD_HOST` as build args. Default targets: `api frontend git-poller build-service runner docs`. |
| `_push_images <env> [targets…]` | If `k3s` binary is local: `docker save \| k3s ctr images import -` (faster path on the cluster nodes). Otherwise `docker push`. Always parallel. |
| `_cleanup_orphaned_pvcs <env>` | Deletes PVCs bound to non-existent PVs (otherwise pods hang `Pending` forever). Also clears PVs stuck `Terminating` with dead finalizers. Runs before every Helm install. |
| `_helm_deploy <env>` | Cleans orphaned PVCs; trims stale Helm release Secrets if >5 exist; runs `helm upgrade --install concord ... --timeout 600s` (no `--wait` — see below). |
| `_verify_rollout <env>` | Parallel `kubectl rollout status` on every Deployment matching `app.kubernetes.io/managed-by=Helm`. 180s timeout per deployment. **Skips MTIB Deployments** (managed-by `concord`, not `Helm`) — their readiness depends on physical hardware. |
| `_smoke_test <env>` | Exec into a running http-api pod, curl `http://concord-http-api:9001/v2/docs`. Retries 5× with 4s delay (handles iptables/DNS warmup). Plus a "build-service pod running" check. Frontend/docs are deliberately not smoked from http-api (NetworkPolicy egress blocks port 80). |
| `_rollback_on_failure <env>` | `helm rollback concord <prev_deployed_rev> -n <env> --wait`. Then re-runs `_verify_rollout` (best-effort). |
| `_restart_targets <env> [targets…]` | `kubectl rollout restart` + parallel `rollout status` wait. Backs `cmd_restart` and `cmd_quick`. |
| `_run_logged <filter> <label> <cmd…>` | Run a command capturing output to a temp file; on failure dump full output, on success grep `filter` for a summary line. Used by `_db_setup` to keep dev output tidy without swallowing errors. |

## Submodule context (when concord is a submodule)

When concord is checked out as a git submodule inside an umbrella workspace, the devcontainer mounts the workspace tree — but `.git/modules/concord/concord/` is typically not bind-mounted into the container, so `git` commands inside the container fail silently. `deploy/ctl.sh` falls back to `.git-build-info` (a 3-line plain-text file written by the host) in that case.

Refresh it on the host before any `nx update platform`:

```bash
{ git rev-parse --short HEAD; \
  git rev-parse --abbrev-ref HEAD; \
  [ -n "$(git status --porcelain 2>/dev/null)" ] && echo true || echo false; \
} > .git-build-info
```

The file contains three lines: short commit, branch, dirty flag. `ctl.sh` reads it inside the container.

When concord is cloned standalone (not as a submodule), `.git/` is a real directory and `git` works natively in the container — `.git-build-info` is unnecessary.
| `_prisma_schema_hash` | `sha256sum prisma/schema.prisma`. Used by `cmd_dev_update` to skip the seed when schema is unchanged. |

## Why no `helm upgrade --wait`

`_helm_deploy` deliberately omits `--wait`. The chart includes resources without a meaningful Ready condition — CronJobs, Ingress, PodDisruptionBudget — and `--wait` blocks on them indefinitely. The verification step is `_verify_rollout`, which is scoped to Deployments only.

## Why staging/production share the case statement

The dispatch is two-branch: `development|dev` and `staging|production`. The K8s subcommands are identical between staging and production — env name is just a parameter. The `production` env adds one guard (`--confirm-delete` on `stop`); everything else flows through the same `cmd_*` functions.

## Which Nx targets call which subcommand

See [`nx-targets.md`](nx-targets.md) for the full mapping. Quick reference:

| Nx target | `ctl.sh` action |
|---|---|
| `nx start platform` | `development start` |
| `nx update platform` | `development update` |
| `nx stop platform` | `development stop` |
| `nx ready platform` | `development ready` |
| `nx update platform -c staging` | `staging update` |
| `nx start platform -c staging` | `staging start` |
| `nx stop platform -c staging` | `staging stop` |
| `nx restart platform -c staging` | `staging restart` |
| `nx diff platform -c staging` | `staging diff` |
| `nx rollback platform -c staging` | (does **not** call ctl.sh — calls `helm rollback` directly from project.json) |

The `release` Nx target wraps `staging update`/`production update` in a check + smoke harness; `release.sh` in `.ci/pipelines/` is a parallel CI version.

## CI bypass behavior

`CI=true` changes two things:

- `cmd_build` streams docker build output to `/dev/stdout` instead of `/dev/null` (so the pipeline shows real-time progress).
- `cmd_dev_stop` adds `-v --remove-orphans` (clean slate between runs).
- `_db_setup` skips the `_run_logged` filtering and lets stdout stream directly.

## How to add a new subcommand

1. Add a `cmd_<name>()` function in the appropriate section.
2. Add a dispatch case to the `staging|production` or `development|dev` branch in the `case` at the bottom.
3. Update the `usage()` heredoc.
4. Add or modify the matching Nx target in `deploy/project.json` so consumers don't bypass Nx.
5. Update [`nx-targets.md`](nx-targets.md) and this file's catalog.

## Common failure modes

- **`kubectl cluster-info` fails** — `_preflight` aborts. Most often: VPN down, WSL routing broken, or `~/.kube/config` points at the wrong cluster. Run `kubectl cluster-info` standalone to see the real error.
- **`Cannot reach Kubernetes cluster` during dev** — wrong target. Dev commands don't use kubectl; if you see this on a dev start, you typed `staging start` by mistake.
- **`helm-diff plugin not installed`** — `cmd_diff` checks for it explicitly. Install: `helm plugin install https://github.com/databus23/helm-diff`.
- **`No previous revision to rollback to`** — `_rollback_on_failure` couldn't find a prior `deployed` revision. First-deploy failures land here. Look at `helm history concord -n <env>` and inspect the failed release manually.
- **Builds hang on docker buildx** — usually a buildx builder going stale. `docker buildx prune` and retry. Don't disable the parallel build (the timing matters for the release flow).
- **`git rev-parse` returns empty** — running inside the umbrella `work/` devcontainer where the parent `.git/modules` isn't mounted. Refresh `.git-build-info` on the host first: see the submodule rule in the workspace `work/.claude/rules/`.

## Library-mode sourcing (for tests)

The dispatcher at the bottom is guarded by:

```bash
if [[ "${BASH_SOURCE[0]}" != "${0}" ]] || [[ "${CONCORD_CTL_NO_DISPATCH:-0}" == "1" ]]; then
  return 0 2>/dev/null || exit 0
fi
```

This lets a test harness `source deploy/ctl.sh` to access the internal
functions without triggering the main dispatcher. Used by
[`deploy/runner/tests/test_ctl_runner_freshness_gate.py`](../../../../deploy/runner/tests/test_ctl_runner_freshness_gate.py)
to exercise `_check_runner_corekinect_freshness` with stubbed `docker`,
`git`, `kubectl`, `helm` binaries on PATH.

If you add a future test that wants to call a `cmd_*` or `_*` helper
directly, follow the same pattern: set `CONCORD_CTL_NO_DISPATCH=1`,
shove your stubs into a temp dir on PATH, then `source`.

## Related knowledge

- [`overview.md`](overview.md) — the env model + cluster topology that this CLI manages.
- [`helm.md`](helm.md) — the chart `_helm_deploy` installs.
- [`nx-targets.md`](nx-targets.md) — the Nx wrappers that call `ctl.sh`.
- [`secrets.md`](secrets.md) — `create-all.sh`, which `_secrets` step depends on.
- [`runner.md`](runner.md) — the test-runner image and its four-layer freshness enforcement (Layer 2 lives in this file).
