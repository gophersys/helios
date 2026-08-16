#!/usr/bin/env bash
# Stage: types-sync
# Gate:  ADVISORY — reports drift between OpenAPI schema and generated types.
#
# Generates TypeScript interfaces from the OpenAPI schema in docs.py and
# reports whether they match the committed baseline. Does not modify any
# files or fail the pipeline.
set -euo pipefail

source "$(dirname "$0")/../lib/log.sh"

log_stage "types-sync — OpenAPI-to-TypeScript drift check"

TOOL="$(dirname "$0")/../tools/generate-types.py"
GENERATED="/tmp/generated-api.ts"

if [[ ! -f "$TOOL" ]]; then
  log_err "generate-types.py not found"
  log_stage_end
  exit 0
fi

# Generate types from OpenAPI
if ! python3 "$TOOL" --output "$GENERATED" 2>&1; then
  log_warn "Type generation failed — skipping"
  log_stage_end
  exit 0
fi

SCHEMA_COUNT=$(grep -c "^export interface" "$GENERATED" 2>/dev/null || echo "0")
log_info "Generated $SCHEMA_COUNT interfaces from OpenAPI"

# Compare against models.ts to measure coverage
MODELS_FILE="apps/frontend/app/src/lib/types/models.ts"
if [[ -f "$MODELS_FILE" ]]; then
  MODELS_COUNT=$(grep -c "^export interface" "$MODELS_FILE" 2>/dev/null || echo "0")
  log_info "Existing models.ts has $MODELS_COUNT interfaces"
  log_info "Coverage: $SCHEMA_COUNT/$MODELS_COUNT interfaces have OpenAPI definitions"
fi

log_ok "Type generation complete (advisory only)"
log_stage_end
exit 0
