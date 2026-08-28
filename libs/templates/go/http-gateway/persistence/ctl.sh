#!/usr/bin/env bash
#
# persistence/ctl.sh — the codegen sub-project for the http-gateway's sqlc/pgx data layer
# (ADR-0023, codegen axis #1). It owns ONE verb that matters — `generate` — which runs sqlc over
# schema/ + the *.sql queries to emit the typed Querier into generated/. It is its own Nx
# sub-project so `nx run http-gateway-template-persistence:generate` refreshes the data layer
# independently, and the parent template's `generate` delegates here.
#
set -Eeuo pipefail
IFS=$'\n\t'

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

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

# generate — run sqlc to emit the typed pgx Querier from schema/ + the query *.sql files.
cmd_generate() {
  require_cmd sqlc
  log_info "persistence: sqlc generate (schema/ + queries → generated/)"
  ( cd "$PROJECT_ROOT" && sqlc generate )
  log_success "persistence: generate OK"
}

# verify — sqlc vet/diff so CI fails if generated/ is stale vs schema + queries.
cmd_verify() {
  require_cmd sqlc
  log_info "persistence: sqlc vet (generated/ is up to date)"
  ( cd "$PROJECT_ROOT" && sqlc vet )
  log_success "persistence: verify OK"
}

usage() {
  cat <<'EOF'
Usage: ./ctl.sh <command>

  generate   sqlc generate — emit the typed pgx Querier from schema/ + queries into generated/
  verify     sqlc vet — fail if generated/ is stale vs schema/queries
  help       Show this message
EOF
}

case "${1:-help}" in
  generate) cmd_generate ;;
  verify)   cmd_verify ;;
  help|"")  usage ;;
  *)        log_error "unknown command: '$1'"; usage; exit 1 ;;
esac
