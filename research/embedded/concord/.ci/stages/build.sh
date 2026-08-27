#!/usr/bin/env bash
# Build container images for affected projects.
# Catches: Dockerfile errors, missing deps, broken builds.
set -euo pipefail
source "$(dirname "$0")/../lib/log.sh"
source "$(dirname "$0")/../lib/context.sh"

CONFIG="${1:-staging}"

log_stage "build — affected projects (config=$CONFIG)"

AFFECTED=$(npx nx show projects --affected --base="$NX_BASE" --with-target=build 2>/dev/null || true)

if [[ -z "$AFFECTED" ]]; then
  log_skip "no affected projects with build target"
else
  npx nx affected -t build --base="$NX_BASE" -c "$CONFIG"
fi

log_stage_end
