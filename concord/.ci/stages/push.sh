#!/usr/bin/env bash
# Push built images to the container registry.
# Only runs in CI on main/release branches.
set -euo pipefail
source "$(dirname "$0")/../lib/log.sh"
source "$(dirname "$0")/../lib/context.sh"

CONFIG="${1:-staging}"

log_stage "push — affected projects (config=$CONFIG)"

if [[ "$CI" != "true" ]]; then
  log_warn "Skipping push — not in CI. Run with CI=true to force."
  log_stage_end
  exit 0
fi

npx nx affected -t push --base="$NX_BASE" -c "$CONFIG"

log_stage_end
