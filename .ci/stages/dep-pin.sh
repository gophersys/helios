#!/usr/bin/env bash
# Dependency pinning enforcement.
# Gate: warns if requirements.txt uses unpinned ranges (>=, ~=, no version).
# Enterprise builds must be reproducible — loose pins cause "works on my machine".
set -euo pipefail
source "$(dirname "$0")/../lib/log.sh"

log_stage "dep-pin — dependency pinning check"

WARNED=false

check_requirements() {
  local req_file="$1"
  local issues=0

  if [[ ! -f "$req_file" ]]; then
    return
  fi

  while IFS= read -r line; do
    # Skip empty lines, comments, flags
    [[ -z "$line" || "$line" =~ ^# || "$line" =~ ^- ]] && continue

    # Check for unpinned deps (no == anywhere in the line)
    if [[ ! "$line" =~ == ]]; then
      # Allow git+https:// and file:// references
      if [[ "$line" =~ ^(git\+|file:|http) ]]; then
        continue
      fi
      echo "    UNPINNED: $line"
      ((issues++)) || true
    fi
  done < "$req_file"

  if [[ "$issues" -gt 0 ]]; then
    log_warn "$req_file has $issues unpinned dependencies"
    WARNED=true
  else
    log_ok "$req_file — all pinned"
  fi
}

for req in \
  apps/backend/build-service/requirements.txt \
  apps/backend/git-poller/requirements.txt \
  apps/frontend/docs/requirements.txt; do
  check_requirements "$req"
done

if $WARNED; then
  log_warn "Some dependencies use loose version ranges"
  log_info "Run: pip freeze > requirements.txt (in each service's venv) to pin exact versions"
  log_info "This is advisory for now — will become a hard gate in the future"
fi

log_stage_end
# Advisory only — don't fail the pipeline yet
# TODO: promote to hard gate after pinning all deps
exit 0
