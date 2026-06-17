#!/usr/bin/env bash
#
# clients/go/ctl.sh — the codegen sub-project for the http-gateway's typed Go test/integration
# client (ADR-0023, codegen axis #2: OpenAPI-first → emit the client). It runs oapi-codegen over
# ../../contract/openapi.yaml to emit a typed client into generated/, used by the integration lane
# to exercise the running handlers (the contract and the implementation are proven to AGREE).
#
# It is its OWN Go module (own go.mod) so the un-generated/regenerated client never breaks the
# gateway module's `go build ./...`, and `nx run http-gateway-template-client-go:generate`
# refreshes it independently. The parent template's `generate` verb delegates here.
#
set -Eeuo pipefail
IFS=$'\n\t'

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONTRACT="$PROJECT_ROOT/../../contract/openapi.yaml"
CONFIG="$PROJECT_ROOT/oapi-codegen.yaml"

log_info()    { printf '\033[0;36m[info]\033[0m  %s\n' "$*"; }
log_error()   { printf '\033[0;31m[error]\033[0m %s\n' "$*" >&2; }
log_success() { printf '\033[0;32m[ok]\033[0m    %s\n' "$*"; }

require_cmd() {
  local missing=() cmd
  for cmd in "$@"; do command -v "$cmd" >/dev/null 2>&1 || missing+=("$cmd"); done
  if [[ ${#missing[@]} -gt 0 ]]; then
    log_error "missing required tool(s): ${missing[*]} (FAIL-NOT-SKIP, ADR-0020)"
    exit 127
  fi
}

# generate — run oapi-codegen to emit the typed client from the OpenAPI contract.
cmd_generate() {
  require_cmd oapi-codegen
  if [[ ! -f "$CONTRACT" ]]; then
    log_error "generate: contract not found at $CONTRACT (OpenAPI-first — the contract is the source)"
    exit 1
  fi
  log_info "client-go: oapi-codegen ($CONTRACT → generated/)"
  ( cd "$PROJECT_ROOT" && oapi-codegen --config "$CONFIG" "$CONTRACT" )
  log_success "client-go: generate OK"
}

usage() {
  cat <<'EOF'
Usage: ./ctl.sh <command>

  generate   oapi-codegen — emit the typed Go test client from ../../contract/openapi.yaml
  help       Show this message
EOF
}

case "${1:-help}" in
  generate) cmd_generate ;;
  help|"")  usage ;;
  *)        log_error "unknown command: '$1'"; usage; exit 1 ;;
esac
