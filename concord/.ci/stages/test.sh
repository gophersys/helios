#!/usr/bin/env bash
# Run tests on affected projects.
# Catches: logic bugs, regressions, broken contracts.
set -euo pipefail
source "$(dirname "$0")/../lib/log.sh"
source "$(dirname "$0")/../lib/context.sh"

log_stage "test — affected projects"

AFFECTED=$(npx nx show projects --affected --base="$NX_BASE" --with-target=test 2>/dev/null || true)

if [[ -z "$AFFECTED" ]]; then
  log_skip "no affected projects with test target"
else
  npx nx affected -t test --base="$NX_BASE"
fi

log_stage_end
