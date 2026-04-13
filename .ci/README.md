# Concord CI

Portable CI infrastructure with AI-powered code review. All pipeline logic lives in bash scripts that wrap Nx targets. Provider configs (Bitbucket, GitHub Actions) are thin shims that call `.ci/run`.

Run the same pipeline locally and in CI — identical behavior, zero vendor lock-in.

## Quick Start

```bash
.ci/run list              # Show all pipelines and stages
.ci/run dry-run pr        # Preview what a pipeline will do
.ci/run pr                # Run the PR pipeline locally
.ci/run stage lint        # Run a single stage
```

## Architecture

```
.ci/
├── run                        Entry point — dispatches to pipelines and stages
├── lib/
│   ├── log.sh                 Colored output, section headers, timing
│   ├── context.sh             CI vs local detection, git state, NX_BASE
│   ├── ai-review.sh           AI review helpers (Claude, parsing, gating)
│   └── bitbucket.sh           Bitbucket REST API (PR comments)
├── stages/                    33 stage scripts (one per check)
│   ├── ai-review-*.sh         AI-powered reviews (Claude Code)
│   ├── ai-fix.sh              Auto-fix findings via Claude write mode
│   ├── proto-sync.sh          Protobuf stub generation check
│   ├── serializer-check.sh    Serializer vs OpenAPI schema coverage
│   ├── types-sync.sh          OpenAPI → TypeScript type generation
│   ├── trend-report.sh        Historical trend tracking
│   ├── lint.sh, test.sh ...   Standard quality gates (Nx targets)
│   └── ...
├── tools/                     Python analysis tools
│   ├── check-serializers.py   AST-based serializer field comparison
│   ├── generate-types.py      OpenAPI → TypeScript interface generator
│   └── trend-report.py        Trend computation and MinIO upload
├── pipelines/                 Pipeline orchestrators
│   ├── pr.sh                  Pull request (parallel gates + AI review)
│   ├── main.sh                Post-merge (PR + push + deploy staging)
│   ├── release.sh             Promote staging → production
│   ├── nightly.sh             Full sweep + E2E tests
│   └── weekly.sh              Deep AI analysis + architecture review
├── k8s/
│   └── entrypoint.sh          Nightly CronJob entrypoint (devcontainer + E2E)
└── providers/                 CI provider shims
    ├── bitbucket-pipelines.yml
    └── github/workflows/ci.yml

deploy/ci/                     Standalone CI platform (Helm chart)
├── helm/concord-ci/           Helm chart managing MinIO, CronJobs, dashboard
├── ctl.sh                     Lifecycle CLI (start, stop, update, status)
└── project.json               Nx project: deploy-ci

apps/ci/admin/                 CI dashboard (SvelteKit + adapter-node)
├── src/routes/                Overview, runs, trends, hotspots pages
├── src/lib/server/db.ts       SQLite database (run history, findings)
└── deploy/Dockerfile          Node.js runtime container
```

## Pipelines

| Pipeline | Schedule | Purpose | Key Stages |
|----------|----------|---------|------------|
| `pr` | Every PR | Must pass before merge | 19 parallel gates + AI review + auto-fix |
| `main` | Post-merge | Publish + deploy staging | PR gates + push + deploy + smoke |
| `release` | Manual | Promote staging → production | Smoke staging + build + deploy prod |
| `nightly` | Daily 2 AM | Full E2E sweep | All projects + integration tests + devcontainer rebuild |
| `weekly` | Saturday 3 AM | Deep AI analysis | AI review + architecture + serializer check + trends |

## AI-Powered Stages

| Stage | What it does | Gate |
|-------|-------------|------|
| `ai-review-completeness` | Schema/type propagation chain check | Blocks on critical |
| `ai-review-security` | OWASP vulnerability scan | Blocks on critical |
| `ai-review-blast-radius` | Cross-project impact analysis | Informational |
| `ai-review-docs` | Documentation staleness detection | Informational (blocks on weekly) |
| `ai-review-architecture` | Circular deps, god objects, coupling | Informational |
| `ai-fix` | Auto-fix: Claude commits fixes to the branch | Runs after AI failures |

AI stages use Claude Code in non-interactive mode (`claude -p`). Auth via `CLAUDE_CODE_OAUTH_TOKEN` env var or `~/.claude/.credentials.json` volume mount.

## Static Analysis Stages

| Stage | What it does | Gate |
|-------|-------------|------|
| `proto-sync` | Verifies protobuf stubs match .proto files | Blocks |
| `serializer-check` | Compares serializer keys vs OpenAPI schema | Advisory |
| `types-sync` | Generates TypeScript from OpenAPI, reports drift | Advisory |
| `trend-report` | Aggregates run metrics, uploads to MinIO | Always passes |

## Kubernetes Deployment

The CI platform runs in the `devops` namespace, fully independent from the main Concord platform.

**Managed by Helm chart** (`deploy/ci/helm/concord-ci/`):

| Resource | Purpose |
|----------|---------|
| `concord-ci-minio` | Artifact storage (5Gi PVC) |
| `concord-ci-admin` | Dashboard (SvelteKit + SQLite on 1Gi PVC) |
| `concord-ci-nightly` | Nightly CronJob (2 AM, DinD sidecar) |
| `concord-ci-weekly` | Weekly CronJob (Saturday 3 AM, no DinD) |
| `concord-ci-config` | ConfigMap (repo URL, branch, MinIO endpoint) |
| `concord-ci-entrypoint` | Entrypoint script for nightly job |
| `concord-ci-secrets` | MinIO credentials |

**Lifecycle:**

```bash
bash deploy/ci/ctl.sh start    # Install/upgrade Helm chart
bash deploy/ci/ctl.sh stop     # Uninstall (preserves PVCs)
bash deploy/ci/ctl.sh update   # Rebuild admin image + redeploy
bash deploy/ci/ctl.sh status   # Show all CI resources
bash deploy/ci/ctl.sh logs     # Tail admin dashboard logs
```

**External secrets** (must exist in devops namespace before deploying):
- `bitbucket-ssh-key` — Git clone auth
- `corekinect-ca-certs` — Internal TLS
- `claude-code-oauth` — AI review auth (OAuth token + credentials file)
- `dockerhub-credentials` — Docker Hub rate limit bypass

## CI Dashboard

**URL:** `admin.concord.local` (staging: `admin.staging.concord.local`, local: `localhost:4300`)

SvelteKit app with adapter-node, stores data in SQLite. Pages:
- **Overview** — Stats, sparklines, recent runs
- **Runs** — Filter by pipeline/verdict, click into run detail
- **Run Detail** — Collapsible stage cards (GitHub Actions style) with findings + terminal logs
- **Trends** — Issue/cost charts over 14 days, severity distribution
- **Hotspots** — Files flagged most frequently across reviews

After each CI run, the pipeline POSTs results to `/api/runs` with stage reports, findings, and captured logs.

## Adding a New Stage

1. Create `.ci/stages/<name>.sh` following the template:

```bash
#!/usr/bin/env bash
# One-line description.
set -euo pipefail
source "$(dirname "$0")/../lib/log.sh"
source "$(dirname "$0")/../lib/context.sh"

log_stage "<name> — description"
# Your logic here
log_stage_end
```

2. Add to the relevant pipeline in `.ci/pipelines/`.
3. `chmod +x .ci/stages/<name>.sh`
4. For AI stages, also source `.ci/lib/ai-review.sh` and use `ai_review_run`, `ai_review_parse`, etc.

## CI vs Local Mode

| Behavior | Local | CI (`CI=true`) |
|----------|-------|----------------|
| Push images | Skipped | Runs |
| Deploy | Skipped | Runs |
| AI review | Uses interactive OAuth | Uses `CLAUDE_CODE_OAUTH_TOKEN` |
| NX_BASE | `origin/main` | PR target branch |
| Colors | Enabled | Disabled |

## Report Format

Every AI review stage produces a standardized JSON report at `/tmp/ai-review/<stage>.json`:

```json
{
  "stage": "completeness",
  "timestamp": "2026-04-13T20:43:00Z",
  "branch": "feature/validation-demo",
  "commit": "add11e3",
  "verdict": "fail",
  "severity": "critical",
  "summary": "Schema changed but frontend types not updated",
  "findings": [{"file": "...", "severity": "critical", "message": "..."}],
  "issues": 4,
  "cost_usd": 0.34,
  "model": "claude-sonnet-4-6",
  "duration_seconds": 60,
  "logs": "── ai-review-completeness ──\ninfo  Running AI completeness review...\n..."
}
```
