#!/usr/bin/env bash
#
# libs/go/configuration/ctl.sh — control script for the Eden configuration
# pattern library (the universal input-IR machinery, 10 §4).
#
# Usage: ./ctl.sh <command> [args...]
#
# Verbs are uniform with the monorepo's nx:run-commands convention: project.json
# targets are thin wrappers that delegate here, so a consumer can invoke
# `nx run configuration:test` without reading source.
#
set -Eeuo pipefail
IFS=$'\n\t'

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

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
  log_info "test: go test ./... -race -count=1"
  (cd "$PROJECT_ROOT" && go test ./... -race -count=1)
  log_success "test: OK"
}

function cmd_fmt() {
  require_cmd go gofmt
  log_info "fmt: gofmt -w ."
  (cd "$PROJECT_ROOT" && gofmt -w .)
  log_success "fmt: OK"
}

function cmd_vet() {
  require_cmd go
  log_info "vet: go vet ./..."
  (cd "$PROJECT_ROOT" && go vet ./...)
  log_success "vet: OK"
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
  if command -v staticcheck >/dev/null 2>&1; then
    log_info "lint: staticcheck ./..."
    (cd "$PROJECT_ROOT" && staticcheck ./...)
  else
    log_warn "lint: staticcheck not installed; skipping (install: go install honnef.co/go/tools/cmd/staticcheck@latest)"
  fi
  log_success "lint: OK"
}

function cmd_cover() {
  require_cmd go
  log_info "cover: go test ./... -coverprofile"
  (cd "$PROJECT_ROOT" && go test ./... -coverprofile=coverage.out -covermode=atomic && go tool cover -func=coverage.out | tail -1)
  log_success "cover: OK"
}

# -------- usage --------
function usage() {
  cat <<EOF
Usage: ./ctl.sh <command> [args...]

Commands:
  build        Compile the library (go build ./...)
  test         Run the test suite with the race detector (go test ./... -race -count=1)
  lint         Check formatting (gofmt), run go vet, and staticcheck if available
  vet          Run go vet ./...
  fmt          Format sources in place (gofmt -w .)
  cover        Run tests with a coverage profile and print the total
  help         Show this message
EOF
}

# -------- dispatcher --------
function main() {
  local cmd="${1:-help}"
  shift || true
  case "$cmd" in
    build)    cmd_build "$@" ;;
    test)     cmd_test  "$@" ;;
    lint)     cmd_lint  "$@" ;;
    vet)      cmd_vet   "$@" ;;
    fmt)      cmd_fmt   "$@" ;;
    cover)    cmd_cover "$@" ;;
    help|"")  usage ;;
    *)        log_error "unknown command: '$cmd'"; usage; exit 1 ;;
  esac
}

main "$@"
