#!/usr/bin/env bash
# Cyclomatic complexity analysis on affected Python backend projects.
# Gate: fails if any new function exceeds CC threshold (allowlisted functions exempt).
set -euo pipefail
source "$(dirname "$0")/../lib/log.sh"
source "$(dirname "$0")/../lib/context.sh"

CC_THRESHOLD=${CC_THRESHOLD:-15}
AVG_THRESHOLD=${AVG_CC_THRESHOLD:-6}
ALLOWLIST="$(dirname "$0")/../complexity-allowlist.json"

log_stage "complexity — affected Python projects (max CC=${CC_THRESHOLD}, avg≤${AVG_THRESHOLD})"

AFFECTED=$(npx nx show projects --affected --base="$NX_BASE" --with-target=complexity 2>/dev/null || true)

if [[ -z "$AFFECTED" ]]; then
  log_skip "no affected projects with complexity target"
  exit 0
fi

FAILED=false

for project in $AFFECTED; do
  log_info "Analyzing complexity for $project..."
  if ! npx nx run "$project:complexity" 2>&1; then
    FAILED=true
  fi
done

if $FAILED; then
  log_error "Complexity gate FAILED"
  exit 1
fi

log_stage_end
