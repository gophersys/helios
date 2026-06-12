#!/usr/bin/env bash
#
# tools/documentvalidator/ctl.sh — control script for the Eden document
# validator (shape + traceability enforcement, doc 11 §8).
#
# Usage: ./ctl.sh <command> [args...]
#
# Verbs are uniform with the monorepo's nx:run-commands convention: project.json
# targets are thin wrappers that delegate here, so a consumer can invoke
# `nx run documentvalidator:test` without reading source.
#
set -Eeuo pipefail
IFS=$'\n\t'

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(git -C "$PROJECT_ROOT" rev-parse --show-toplevel 2>/dev/null || echo "$PROJECT_ROOT")"
SCHEMA_DIR="$REPO_ROOT/schemas/document/v1"
EXAMPLE_DIR="$SCHEMA_DIR/examples/linkbox"

# -------- logging --------
function log_info()    { printf '\033[0;36m[info]\033[0m  %s\n' "$*"; }
function log_warn()    { printf '\033[0;33m[warn]\033[0m  %s\n' "$*" >&2; }
function log_error()   { printf '\033[0;31m[error]\033[0m %s\n' "$*" >&2; }
function log_success() { printf '\033[0;32m[ok]\033[0m    %s\n' "$*"; }

# -------- tool gate --------
function require_cmd() {
  local missing=()
  local cmd
  for cmd in "$@"; do
    command -v "$cmd" >/dev/null 2>&1 || missing+=("$cmd")
  done
  if [[ ${#missing[@]} -gt 0 ]]; then
    log_error "missing required tool(s): ${missing[*]}"
    exit 127
  fi
}

# -------- commands --------
function cmd_build() {
  require_cmd go
  log_info "build: go build ./..."
  (cd "$PROJECT_ROOT" && go build ./...)
  log_success "build: OK"
}

function cmd_test() {
  require_cmd go
  log_info "test: go test ./..."
  (cd "$PROJECT_ROOT" && go test ./...)
  log_success "test: OK"
}

function cmd_lint() {
  require_cmd go gofmt
  log_info "lint: gofmt -l ."
  local unformatted
  unformatted="$(cd "$PROJECT_ROOT" && gofmt -l .)"
  if [[ -n "$unformatted" ]]; then
    log_error "gofmt found unformatted files:"
    printf '  %s\n' "$unformatted" >&2
    exit 1
  fi
  log_info "lint: go vet ./..."
  (cd "$PROJECT_ROOT" && go vet ./...)
  log_success "lint: OK"
}

function cmd_validate() {
  require_cmd go
  if [[ ! -d "$EXAMPLE_DIR" ]]; then
    log_error "example project not found at $EXAMPLE_DIR"
    exit 1
  fi
  log_info "validate: running the validator against the linkbox example"
  (cd "$PROJECT_ROOT" && go run ./cmd/documentvalidator validate "$EXAMPLE_DIR" --schemas "$SCHEMA_DIR")
  log_success "validate: example is clean"
}

function cmd_project() {
  require_cmd go
  if [[ ! -d "$EXAMPLE_DIR" ]]; then
    log_error "example project not found at $EXAMPLE_DIR"
    exit 1
  fi
  log_info "project: emitting the linkbox example projections (NDJSON to stdout)"
  (cd "$PROJECT_ROOT" && go run ./cmd/documentvalidator project "$EXAMPLE_DIR" --schemas "$SCHEMA_DIR")
  log_success "project: OK"
}

# -------- usage --------
function usage() {
  cat <<EOF
Usage: ./ctl.sh <command> [args...]

Commands:
  build        Compile the validator (go build ./...)
  test         Run the Go test suite (go test ./...)
  lint         Check formatting (gofmt) and run go vet
  validate     Run the validator against the worked linkbox example project
  project      Emit the linkbox example's JSON projections (the UI contract)
  help         Show this message
EOF
}

# -------- dispatcher --------
function main() {
  local cmd="${1:-help}"
  shift || true
  case "$cmd" in
    build)    cmd_build    "$@" ;;
    test)     cmd_test     "$@" ;;
    lint)     cmd_lint     "$@" ;;
    validate) cmd_validate "$@" ;;
    project)  cmd_project  "$@" ;;
    help|"")  usage ;;
    *)        log_error "unknown command: '$cmd'"; usage; exit 1 ;;
  esac
}

main "$@"
