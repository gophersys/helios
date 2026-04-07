#!/usr/bin/env bash
# Docstring coverage enforcement.
# Gate: fails if docstring coverage drops below thresholds.
set -euo pipefail
source "$(dirname "$0")/../lib/log.sh"
source "$(dirname "$0")/../lib/context.sh"

log_stage "docstrings — docstring coverage enforcement"

FAILED=false

# Shared libraries — 55% threshold (current: 56%, raise as coverage improves)
log_info "Checking libs/python/corekinect/ (threshold: 55%)"
if ! python3 -m interrogate libs/python/corekinect/ \
    --fail-under=90 \
    --ignore-init-method --ignore-magic --ignore-private --ignore-module \
    --quiet 2>&1; then
  log_error "Library docstring coverage below 55%"
  FAILED=true
fi

# http-api — 55% threshold (current: 58%, raise as coverage improves)
log_info "Checking apps/backend/http-api/src/ (threshold: 55%)"
if ! python3 -m interrogate apps/backend/http-api/src/ \
    --fail-under=90 \
    --ignore-init-method --ignore-magic --ignore-private --ignore-module \
    --quiet 2>&1; then
  log_error "http-api docstring coverage below 55%"
  FAILED=true
fi

if $FAILED; then
  log_error "Docstring gate FAILED"
  exit 1
fi

log_stage_end
