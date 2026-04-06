# Concord CI

Portable CI infrastructure. All logic lives in bash scripts that wrap Nx targets. Provider configs (Bitbucket, GitHub Actions, etc.) are thin shims that call `.ci/run`.

Run the same pipeline locally and in CI — identical behavior, zero vendor lock-in.

## Quick Start

```bash
# Show what's available
.ci/run list

# Preview what a pipeline will do (no execution)
.ci/run dry-run pr

# Run the PR pipeline locally
.ci/run pr

# Run a single stage
.ci/run stage lint
.ci/run stage typecheck
```

## Directory Layout

```
.ci/
├── run                  # Entry point — dispatches to pipelines and stages
├── README.md            # You're here
├── lib/
│   ├── log.sh           # Colored output, section headers, timing
│   └── context.sh       # CI vs local detection, git state, NX_BASE
├── stages/              # Leaf operations — each wraps one Nx target
│   ├── env-check.sh     # Validate .env.example registry (tools/env/setup.sh)
│   ├── lint.sh          # nx affected -t lint
│   ├── typecheck.sh     # nx affected -t typecheck
│   ├── test.sh          # nx affected -t test
│   ├── build.sh         # nx affected -t build (container images)
│   ├── push.sh          # nx affected -t push (CI-only, skips locally)
│   ├── deploy.sh        # helm upgrade via deploy/ctl.sh (CI-only)
│   └── smoke.sh         # health checks + smoke test suite
└── providers/           # CI provider shims (symlink to repo root to activate)
    ├── bitbucket-pipelines.yml
    └── github/workflows/ci.yml
```

## Pipelines

| Pipeline | Purpose | Stages |
|----------|---------|--------|
| `pr` | Every pull request. Must pass before merge. | env-check → lint → typecheck → test → build (dry) |
| `main` | After merge to main. Publishes artifacts. | pr → push → deploy staging → smoke staging |
| `release` | Promote staging to production. Manual trigger. | smoke staging → build prod → push → deploy prod → smoke prod → tag |
| `nightly` | Full sweep. Catches upstream drift and dep rot. | all projects (not affected-only) + npm audit + devcontainer rebuild |

**Stage ordering is intentional**: cheapest checks run first (env-check ~1s, lint ~5s) so failures surface fast. Expensive stages (build ~2min, deploy ~5min) run last.

## Stages

Each stage is a standalone script in `.ci/stages/`. Stages use `nx affected` by default — they only operate on projects changed since the base branch. The base branch is auto-detected from CI provider env vars (`BITBUCKET_PR_DESTINATION_BRANCH`, `GITHUB_BASE_REF`) or defaults to `origin/main`.

Run any stage individually:

```bash
.ci/run stage env-check
.ci/run stage lint
.ci/run stage typecheck
.ci/run stage test
.ci/run stage build staging      # pass config as arg
.ci/run stage push staging       # skips in local mode
.ci/run stage deploy staging     # skips in local mode
.ci/run stage smoke staging
```

### Adding a new stage

1. Create `.ci/stages/<name>.sh`
2. Follow this template:

```bash
#!/usr/bin/env bash
# One-line description of what this catches.
set -euo pipefail
source "$(dirname "$0")/../lib/log.sh"
source "$(dirname "$0")/../lib/context.sh"

log_stage "<name> — description"

# Your logic here (usually an nx affected command)
npx nx affected -t <target> --base="$NX_BASE"

log_stage_end
```

3. Add it to the relevant pipeline in `.ci/pipelines/`.
4. `chmod +x .ci/stages/<name>.sh`

## CI vs Local Mode

The scripts auto-detect the environment:

| Behavior | Local (`CI` unset) | CI (`CI=true`) |
|----------|-------------------|----------------|
| Push images | Skipped | Runs |
| Deploy | Skipped | Runs |
| Colors | Enabled (if terminal) | Disabled (unless `FORCE_COLOR=1`) |
| NX_BASE | `origin/main` | PR target branch |

Force CI mode locally: `CI=true .ci/run main`

## Activating a Provider

Provider configs live in `.ci/providers/`. To activate one, symlink or copy to where the provider expects it:

**Bitbucket Pipelines:**
```bash
ln -sf .ci/providers/bitbucket-pipelines.yml bitbucket-pipelines.yml
```

**GitHub Actions:**
```bash
ln -sf .ci/providers/github .github
```

To switch providers: remove the old symlink, create the new one. All pipeline logic stays in `.ci/`.

## Prerequisites

The CI runner needs:

- **Node.js** ≥ 22 with yarn 4 (`corepack enable`)
- **Docker** (for container builds)
- **Python 3** (for backend tests + Prisma)
- **kubectl + helm** (for deploy stages)

All of these are pre-installed in the `concord-devcontainer-base` image. Both provider shims use it as the CI runtime — same image devs work in.

## Environment Setup

The CI uses `tools/env/` to manage `.env` files:

```bash
# Populate all .env files from .env.example templates (dev mode)
npx nx setup env -c development

# Validate staging helm values exist
npx nx setup env -c staging
```

The `env-check` stage runs this at the start of every pipeline. If someone adds a new `.env.example` without registering it in `tools/env/known-env-files.txt`, the pipeline fails.

## Adding a New App/Service

When you add a new service to the monorepo:

1. Create its `.env.example` with all config vars
2. Register the path in `tools/env/known-env-files.txt`
3. Add Nx targets (`lint`, `typecheck`, `test`, `build`, `push`) in `project.json`
4. The CI will automatically pick it up via `nx affected`

No changes to `.ci/` needed — Nx handles project discovery.

## Troubleshooting

**"no affected projects"**: Your changes might not touch any project with that target. Run `npx nx show projects --affected --base=origin/main` to see what Nx considers affected.

**Tests fail locally but pass in CI**: Check if you need `nx start platform` running (DB, MinIO). Backend integration tests need infrastructure.

**Push/deploy skipped**: These only run when `CI=true`. Set it explicitly: `CI=true .ci/run stage push staging`
