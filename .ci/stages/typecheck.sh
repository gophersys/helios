#!/usr/bin/env bash
# Type-check affected projects.
# Catches: type errors, missing imports, broken interfaces.
set -euo pipefail
source "$(dirname "$0")/../lib/log.sh"
source "$(dirname "$0")/../lib/context.sh"

log_stage "typecheck — affected projects"

AFFECTED=$(npx nx show projects --affected --base="$NX_BASE" --with-target=typecheck 2>/dev/null || true)

if [[ -z "$AFFECTED" ]]; then
  log_skip "no affected projects with typecheck target"
else
  npx nx affected -t typecheck --base="$NX_BASE"
fi

log_stage_end
