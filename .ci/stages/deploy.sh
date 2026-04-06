#!/usr/bin/env bash
# Deploy to a target environment via Helm.
# Only runs in CI (or with CI=true forced).
set -euo pipefail
source "$(dirname "$0")/../lib/log.sh"
source "$(dirname "$0")/../lib/context.sh"

ENV="${1:-staging}"

log_stage "deploy — $ENV"

if [[ "$CI" != "true" ]]; then
  log_warn "Skipping deploy — not in CI. Run with CI=true to force."
  log_stage_end
  exit 0
fi

./deploy/production/ctl.sh "$ENV" deploy

log_stage_end
