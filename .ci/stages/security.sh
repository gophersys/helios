#!/usr/bin/env bash
# Security scanning on affected Python backend projects.
# Gate: fails on high-severity findings (bandit).
set -euo pipefail
source "$(dirname "$0")/../lib/log.sh"
source "$(dirname "$0")/../lib/context.sh"

log_stage "security — affected Python projects (bandit)"

AFFECTED=$(npx nx show projects --affected --base="$NX_BASE" --with-target=security 2>/dev/null || true)

if [[ -z "$AFFECTED" ]]; then
  log_skip "no affected projects with security target"
  exit 0
fi

FAILED=false

for project in $AFFECTED; do
  log_info "Scanning $project..."
  if ! npx nx run "$project:security" 2>&1; then
    FAILED=true
  fi
done

if $FAILED; then
  log_error "Security gate FAILED — high-severity findings detected"
  exit 1
fi

log_stage_end
