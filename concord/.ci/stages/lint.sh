#!/usr/bin/env bash
# Run linters on affected projects.
# Catches: style violations, dead imports, unsafe patterns.
set -euo pipefail
source "$(dirname "$0")/../lib/log.sh"
source "$(dirname "$0")/../lib/context.sh"

log_stage "lint — affected projects"

AFFECTED=$(npx nx show projects --affected --base="$NX_BASE" --with-target=lint 2>/dev/null || true)

if [[ -z "$AFFECTED" ]]; then
  log_skip "no affected projects with lint target"
else
  npx nx affected -t lint --base="$NX_BASE"
fi

log_stage_end
