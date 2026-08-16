#!/usr/bin/env bash
# Security scanning on Python backend projects.
# Gate: FAILS on high-severity + high-confidence findings (bandit).
# Use `# nosec BXXX` inline to suppress known false positives.
set -euo pipefail
source "$(dirname "$0")/../lib/log.sh"
source "$(dirname "$0")/../lib/context.sh"

log_stage "security — Python static security analysis (bandit)"

FAILED=false

# Scan each backend service for high-severity + high-confidence issues
for src_dir in \
  apps/backend/http-api/src \
  apps/backend/build-service/src \
  apps/backend/git-poller/src \
  libs/python/corekinect; do

  if [[ ! -d "$src_dir" ]]; then
    continue
  fi

  log_info "Scanning $src_dir..."

  # -lll = high severity only, -iii = high confidence only
  # nosec comments suppress known false positives inline
  if ! python3 -m bandit -r "$src_dir" -lll -iii -q \
      --exclude "$src_dir/tests,$src_dir/.venv" 2>&1; then
    log_error "High-severity findings in $src_dir"
    FAILED=true
  else
    log_ok "$src_dir — clean"
  fi
done

if $FAILED; then
  log_error "Security gate FAILED — fix findings or add # nosec BXXX with justification"
  exit 1
fi

log_stage_end
