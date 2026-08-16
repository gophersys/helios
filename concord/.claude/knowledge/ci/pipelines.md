# CI — pipelines

The `.ci/` directory is portable CI infrastructure: every check runs locally and in CI from the same bash scripts. Provider configs (`.ci/providers/bitbucket-pipelines.yml`, `.ci/providers/github/workflows/ci.yml`) are thin shims that call `./.ci/run <pipeline>`. The Bitbucket shim is the active one; activate by symlinking it to repo root as `bitbucket-pipelines.yml`.

Refresh this file when: a pipeline (`pr`, `main`, `release`, `nightly`, `weekly`) is added, removed, or reorganized; a stage is added to or removed from a pipeline; the gating behavior of a pipeline changes; the provider shim changes.

## Location

```
.ci/
├── run                         # entry point — dispatches to pipelines/stages
├── lib/
│   ├── log.sh                  # log_stage, log_ok, log_warn, log_err, log_skip
│   ├── context.sh              # CI vs local, ci_summary, NX_BASE resolution
│   ├── ai-review.sh            # AI review helpers (Claude wrappers)
│   └── bitbucket.sh            # Bitbucket REST API (PR comments)
├── pipelines/
│   ├── pr.sh                   # PR pipeline
│   ├── main.sh                 # main-branch pipeline
│   ├── release.sh              # production release pipeline
│   ├── nightly.sh              # nightly sweep
│   └── weekly.sh               # weekly AI-deep review
├── stages/                     # 33+ stage scripts, one per check
├── tools/                      # Python analysis tools (serializer-check, types-gen, trend-report)
├── k8s/entrypoint.sh           # entry script for the concord-ci-nightly CronJob
├── providers/
│   ├── bitbucket-pipelines.yml # Bitbucket Pipelines shim (active)
│   └── github/workflows/ci.yml # GitHub Actions shim (parallel implementation)
├── project.json                # `ci` Nx project (validate/status/logs)
├── README.md                   # human-readable architecture overview
└── run                         # entry point (same as above, symlinked)
```

The `concord-ci` Helm chart that hosts the scheduled jobs lives at `deploy/ci/helm/concord-ci/`; see [`ci-platform.md`](ci-platform.md).

## Entry point — `.ci/run`

```
./.ci/run <pipeline>            # run a full pipeline
./.ci/run stage <stage> [args]  # run a single stage
./.ci/run list                  # show pipelines + stages
./.ci/run dry-run <pipeline>    # show what would run
```

Pipelines: `pr`, `main`, `release`, `nightly`, `weekly`. The script `cd`s to repo root and sources `lib/log.sh` + `lib/context.sh`. Same code path locally and in CI; CI behavior is gated by `[[ "$CI" == "true" ]]` checks inside individual stages.

Nx wrapper: `nx run ci:validate` runs the PR pipeline locally.

## The five pipelines

### `pr` — pull request

Runs on every PR. Must pass before merge.

```
Stage 1: env-check + secret-scan                       (sequential safety gates)
Stage 2: 19 quality gates in parallel:
  lint, typecheck, typecheck-python, test, coverage,
  complexity, security, dep-audit, contracts,
  schema-check, docstrings, docs-build, dep-pin,
  api-compat, migration-safety, proto-sync,
  ai-review-completeness, ai-review-security,
  ai-review-blast-radius, ai-review-docs
Stage 3: test-integration                              (real DB, compose stack)
Stage 4: build staging                                 (only if everything passed)
Stage 5: image-scan                                    (post-build)
```

On failure: if any `ai-review-*.json` reports exist, runs `ai-fix.sh` once (Claude auto-fixes findings) before exiting.

### `main` — post-merge to main

```
1. Run the PR pipeline in full
2. push staging       — npx nx affected -t push --base=<base> -c staging
3. deploy staging     — ./deploy/ctl.sh staging deploy
4. publish-corectl staging  — push the corectl wheel to staging's internal PyPI
5. smoke staging      — curl /v2/docs + pytest tests/smoke/
```

Triggered automatically by Bitbucket Pipelines on every push to `main`. End state: staging has the latest `:staging` image tag for every changed service, and the deploy was smoke-tested.

### `release` — production deploy (manual)

Triggered manually from Bitbucket Pipelines (`custom: release`) or by the `/concord-release` skill.

```
1. pre-flight: smoke staging   — fail fast if staging is broken
2. build production
3. push production             — pushes :production image tags
4. deploy production           — ./deploy/ctl.sh production deploy
5. publish-corectl production  — push corectl wheel to production PyPI
6. smoke production            — must pass before tag
7. git tag v<YYYY.MM.DD>-<sha> — only in CI; pushed to origin
```

The `/concord-release` skill is the developer-side equivalent — it bumps `VERSION`, writes a CHANGELOG entry, opens a release PR, and on merge triggers this pipeline.

### `nightly` — full sweep

Runs daily at 02:00 America/Chicago via the `concord-ci-nightly` CronJob in the `devops` namespace. Forces `NX_BASE=HEAD~100` so `nx affected` means "everything."

Sequence (all `|| true` — failures don't abort the run):

```
env-check
nightly — full lint        nx run-many -t lint --all
nightly — full typecheck   nx run-many -t typecheck --all
nightly — full test        nx run-many -t test --all
nightly — full build       nx run-many -t build --all -c staging
nightly — npm audit        cd apps/frontend/app && npm audit --omit=dev
nightly — Python dep audit
nightly — secret scan
nightly — container image scan
nightly — Python type check
nightly — dependency pinning check
nightly — integration tests
nightly — mutation testing
nightly — devcontainer rebuild   nx run devcontainer:build-all
nightly — AI completeness review
nightly — AI security review
nightly — AI blast radius review
nightly — AI docs review
nightly — proto sync check
nightly — serializer completeness
nightly — type generation check
nightly — trend report
```

The CronJob runs with a DinD sidecar so it can rebuild devcontainer images.

### `weekly` — deep AI review

Runs Saturday at 03:00 America/Chicago via the `concord-ci-weekly` CronJob. `NX_BASE=HEAD~200`. No DinD — just AI + static analysis.

```
ai-review-completeness
ai-review-security
ai-review-blast-radius
ai-review-docs --threshold=critical
ai-review-architecture
serializer-check
proto-sync
types-sync
trend-report
```

Each stage's stdout/stderr is teed to `/tmp/ai-review/<name>.log` and merged into the matching `/tmp/ai-review/<name>.json` report. Results are POSTed to the CI dashboard (`${CI_DASHBOARD_URL}/api/runs`) and uploaded to MinIO at `cluster/<bucket>/weekly/<date>-<sha>/`.

## Stage inventory (~33 scripts)

Grouped by intent. Every stage prints `── <name> ──` at start and `── done ──` at end via `log_stage`/`log_stage_end`.

| Group | Stages |
|---|---|
| Safety gates | `env-check`, `secret-scan` |
| Lint / type | `lint`, `typecheck`, `typecheck-python`, `docstrings` |
| Test | `test`, `test-integration`, `coverage`, `mutation` |
| Build / push / deploy | `build`, `push`, `deploy`, `smoke`, `publish-corectl` |
| Static analysis | `complexity`, `security`, `dep-audit`, `dep-pin`, `image-scan`, `contracts`, `schema-check`, `migration-safety`, `api-compat`, `proto-sync`, `serializer-check`, `types-sync` |
| Docs | `docs-build` |
| AI review | `ai-review-completeness`, `ai-review-security`, `ai-review-blast-radius`, `ai-review-docs`, `ai-review-architecture`, `ai-fix` |
| Reporting | `trend-report` |

Stage shape — every script:

```bash
#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/../lib/log.sh"
source "$(dirname "$0")/../lib/context.sh"

CONFIG="${1:-staging}"
log_stage "<name> — <description> (config=$CONFIG)"
# logic — typically `npx nx affected -t <target> ...`
log_stage_end
```

## CI vs local

Set by `lib/context.sh`. Most stages behave identically; a few gate on `[[ "$CI" == "true" ]]`:

| Stage | Local | CI |
|---|---|---|
| `push` | Skipped (warning) | `nx affected -t push` |
| `deploy` | Skipped (warning) | `./deploy/ctl.sh <env> deploy` |
| `ai-review-*` | Uses interactive Claude OAuth (`~/.claude/.credentials.json`) | Uses `CLAUDE_CODE_OAUTH_TOKEN` env var |
| `release.sh: git tag` | Skipped | Tags + `git push origin v<ver>` |
| `NX_BASE` | `origin/main` | PR target branch (Bitbucket: `BITBUCKET_PR_DESTINATION_BRANCH`) |

## Bitbucket Pipelines shim

`.ci/providers/bitbucket-pipelines.yml`:

```yaml
image: containers.ad.corekinect.com/concord-devcontainer-base:latest
pipelines:
  pull-requests:
    '**':
      - step:
          name: PR checks
          caches: [node, docker]
          script: [./.ci/run pr]
  branches:
    main:
      - step:
          name: Build + Deploy staging
          caches: [node, docker]
          services: [docker]
          script: [./.ci/run main]
  custom:
    release:
      - step:
          name: Release to production
          trigger: manual
          services: [docker]
          script: [./.ci/run release]
definitions:
  services:
    docker:
      memory: 4096
```

Activation: `ln -sf .ci/providers/bitbucket-pipelines.yml bitbucket-pipelines.yml` at repo root.

The `nightly` and `weekly` pipelines are **not** triggered by Bitbucket — they run from the `concord-ci-*` CronJobs in `devops`. See [`ci-platform.md`](ci-platform.md).

## How a CI run reaches the dashboard

```
.ci/run weekly
  └─ runs each stage, writes /tmp/ai-review/<stage>.{log,json}
      └─ POST to $CI_DASHBOARD_URL/api/runs (concord-ci-admin)
          └─ admin writes to SQLite, surfaces in /runs/<id>
              └─ mc cp /tmp/ai-review/* to ci-minio for archival
```

`CI_DASHBOARD_URL` is set on the CronJob from `concord-ci-config` ConfigMap.

## How to add a stage

1. Create `.ci/stages/<name>.sh` using the shape above. `chmod +x` it.
2. Add a `run_stage` (or `bash "$DIR/stages/<name>.sh"`) line to the pipeline that should include it.
3. If AI-based, source `lib/ai-review.sh` and use `ai_review_run`, `ai_review_parse`, `ai_review_gate`.
4. Update the stage inventory in this file.
5. If it needs to run on schedule, also add it to `nightly.sh` and/or `weekly.sh`.

## How to add a pipeline

1. Create `.ci/pipelines/<name>.sh`.
2. Add `<name>` to the case statement in `.ci/run` (pipelines case branch).
3. If it needs a CI trigger, add a section to `.ci/providers/bitbucket-pipelines.yml`.
4. If it runs on schedule, add a CronJob template in `deploy/ci/helm/concord-ci/templates/` and a values block in `values.yaml`.
5. Update this file.

## Common failure modes

- **`./.ci/run main` fails on `push staging`** — only runs in CI. Set `CI=true` locally to force, or run individual stages: `./.ci/run stage build staging` then a manual `docker push`.
- **`ai-review-*` returns immediately with `verdict: skipped`** — Claude credentials missing. In CI: `CLAUDE_CODE_OAUTH_TOKEN` not set in Bitbucket Pipelines variables. Locally: `~/.claude/.credentials.json` doesn't exist or is expired.
- **`nx affected` returns "no projects"** — `NX_BASE` is wrong. Locally, `context.sh` sets it to `origin/main`; in CI to the PR base. If the base ref isn't fetched, fall back to `HEAD~1`.
- **Pre-flight smoke fails in `release.sh`** — staging is broken. Don't promote. Investigate and re-deploy staging via `nx update platform -c staging` first.
- **`bitbucket-pipelines.yml` not detected by Bitbucket** — the symlink at repo root is missing or pointing at a non-existent file. Recreate: `ln -sf .ci/providers/bitbucket-pipelines.yml bitbucket-pipelines.yml`.
- **`integration` stage cannot reach Postgres** — the dev compose stack isn't up. `nx start platform` first; then re-run. CI containers start their own compose stack via `nx run platform:start` inside the test job.

## Related knowledge

- [`ci-platform.md`](ci-platform.md) — the Helm chart that runs nightly/weekly + hosts the dashboard.
- [`../deploy/ctl-sh.md`](../deploy/ctl-sh.md) — the deploy/push commands the pipelines wrap.
- [`../deploy/nx-targets.md`](../deploy/nx-targets.md) — `ci:validate` and the per-app `build`/`push` targets.
- [`../deploy/secrets.md`](../deploy/secrets.md) — `bitbucket-ssh-key`, `claude-code-oauth`, `ci-minio-upload`, `corekinect-ca-certs`.
- [`../../rules/nx-only.md`](../../rules/nx-only.md) — stages must go through Nx, not bypass it.
