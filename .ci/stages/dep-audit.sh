#!/usr/bin/env bash
# Dependency vulnerability scanning via pip-audit.
# Gate: fails if any known CVE is found in installed packages.
set -euo pipefail
source "$(dirname "$0")/../lib/log.sh"

log_stage "dep-audit — Python dependency vulnerability scan"

FAILED=false

# Scan each service's requirements
for req in \
  apps/backend/build-service/requirements.txt \
  apps/backend/git-poller/requirements.txt \
  apps/frontend/docs/requirements.txt; do

  if [[ ! -f "$req" ]]; then
    continue
  fi

  log_info "Auditing $req..."
  if ! python3 -m pip_audit -r "$req" --desc --progress-spinner=off 2>&1; then
    log_error "Vulnerabilities found in $req"
    FAILED=true
  else
    log_ok "$req — no known vulnerabilities"
  fi
done

# Scan http-api installed packages (no requirements.txt, uses pyproject.toml)
log_info "Auditing installed http-api packages..."
if ! python3 -m pip_audit --desc --progress-spinner=off 2>&1; then
  log_error "Vulnerabilities found in installed packages"
  FAILED=true
else
  log_ok "Installed packages — no known vulnerabilities"
fi

if $FAILED; then
  log_error "Dependency audit FAILED — fix or suppress known CVEs"
  exit 1
fi

log_stage_end
