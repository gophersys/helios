#!/usr/bin/env bash
# Stage: proto-sync
# Gate:  BLOCKING — fails if generated protobuf stubs are stale.
#
# Checks whether .proto files were modified in this changeset. If so,
# re-runs code generation and verifies the committed stubs match.
# Catches: developers who edit .proto without running `ctl.sh generate`.
set -euo pipefail

source "$(dirname "$0")/../lib/log.sh"
source "$(dirname "$0")/../lib/context.sh"

log_stage "proto-sync — generated stubs verification"

# Only run if proto files changed
PROTO_CHANGED=$(git diff --name-only "${NX_BASE}"...HEAD -- 'libs/protocols/**/*.proto' 2>/dev/null || true)

if [[ -z "$PROTO_CHANGED" ]]; then
  log_skip "no .proto files changed"
  log_stage_end
  exit 0
fi

log_info "Proto files changed:"
echo "$PROTO_CHANGED" | sed 's/^/  /'

# Regenerate stubs
log_info "Regenerating protobuf stubs..."
if ! bash libs/protocols/ctl.sh generate 2>&1; then
  log_err "Proto generation failed"
  log_stage_end
  exit 1
fi

# Check for drift
if ! git diff --exit-code --stat libs/protocols/ >/dev/null 2>&1; then
  log_err "Generated protobuf stubs are STALE"
  log_err "Run 'bash libs/protocols/ctl.sh generate' and commit the results:"
  git diff --stat libs/protocols/ | sed 's/^/  /'
  log_stage_end
  exit 1
fi

log_ok "Protobuf stubs are in sync"
log_stage_end
