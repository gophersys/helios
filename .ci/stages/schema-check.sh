#!/usr/bin/env bash
# Schema check — Prisma field validation (advisory).
# Detects unknown field names in db.<model>.create() call sites.
set -euo pipefail
source "$(dirname "$0")/../lib/log.sh"
source "$(dirname "$0")/../lib/context.sh"

log_stage "schema-check — Prisma field validation"

AFFECTED=$(npx nx show projects --affected --base="$NX_BASE" --with-target=schema-check 2>/dev/null || true)

if [[ -z "$AFFECTED" ]]; then
  log_skip "no affected projects with schema-check target"
  log_stage_end
  exit 0
fi

FAILED=false

for project in $AFFECTED; do
  log_info "Running schema-check for $project..."
  if ! npx nx run "$project:schema-check" 2>&1; then
    FAILED=true
  fi
done

if $FAILED; then
  log_err "Schema-check gate FAILED"
  exit 1
fi

log_stage_end
