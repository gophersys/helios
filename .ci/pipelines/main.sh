#!/usr/bin/env bash
# Pipeline: Main Branch
# Runs after merge to main. Builds, pushes, deploys to staging.
set -euo pipefail

DIR="$(cd "$(dirname "$0")/.." && pwd)"

# All PR checks (env, lint, typecheck, test, build)
bash "$DIR/pipelines/pr.sh"

# Push images to registry
bash "$DIR/stages/push.sh" staging

# Deploy to staging
bash "$DIR/stages/deploy.sh" staging

# Verify staging is alive
bash "$DIR/stages/smoke.sh" staging
