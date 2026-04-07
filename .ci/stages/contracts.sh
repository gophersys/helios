#!/usr/bin/env bash
# Contract tests — API response shape validation.
# Catches serializer regressions before they reach clients.
set -euo pipefail
source "$(dirname "$0")/../lib/log.sh"
source "$(dirname "$0")/../lib/context.sh"

log_stage "contracts — API response shape validation"

AFFECTED=$(npx nx show projects --affected --base="$NX_BASE" --with-target=contracts 2>/dev/null || true)

if [[ -z "$AFFECTED" ]]; then
  log_skip "no affected projects with contracts target"
  log_stage_end
  exit 0
fi

FAILED=false

for project in $AFFECTED; do
  log_info "Running contract tests for $project..."
  if ! npx nx run "$project:contracts" 2>&1; then
    FAILED=true
  fi
done

if $FAILED; then
  log_err "Contract gate FAILED — API response shapes have changed"
  exit 1
fi

log_stage_end
