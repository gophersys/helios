#!/usr/bin/env bash
# Coverage analysis on affected Python backend projects.
# Gate: fails if overall coverage < threshold.
set -euo pipefail
source "$(dirname "$0")/../lib/log.sh"
source "$(dirname "$0")/../lib/context.sh"

COVERAGE_THRESHOLD=${COVERAGE_THRESHOLD:-70}

log_stage "coverage — affected Python projects (threshold: ${COVERAGE_THRESHOLD}%)"

AFFECTED=$(npx nx show projects --affected --base="$NX_BASE" --with-target=coverage 2>/dev/null || true)

if [[ -z "$AFFECTED" ]]; then
  log_skip "no affected projects with coverage target"
  exit 0
fi

FAILED=false

for project in $AFFECTED; do
  log_info "Running coverage for $project..."
  if ! npx nx run "$project:coverage" 2>&1; then
    log_error "Coverage below ${COVERAGE_THRESHOLD}% for $project"
    FAILED=true
  fi
done

if $FAILED; then
  log_error "Coverage gate FAILED — one or more projects below ${COVERAGE_THRESHOLD}%"
  exit 1
fi

log_stage_end
