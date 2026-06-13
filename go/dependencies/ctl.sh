#!/usr/bin/env bash
#
# libs/go/dependencies/ctl.sh — control script for the Eden `dependencies`
# library: the universal port set (Clock, RandomSource, Sink) + wiring
# discipline (Resolve/Validate). Leaf library, stdlib only (10 §4, contract
# docs/architecture/contracts/dependencies.md, frozen per ADR-0016).
#
# Usage: ./ctl.sh <command> [args...]
#
# Verbs are uniform with the monorepo's nx:run-commands convention: project.json
# targets are thin wrappers that delegate here, so a consumer can invoke
# `nx run dependencies:test` without reading source.
#
set -Eeuo pipefail
IFS=$'\n\t'

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Release builds and gate runs use GOWORK=off so a stray dev workspace can never
# mask a missing published version (10 §6.1).
export GOWORK="${GOWORK:-off}"

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
  require_cmd gofmt
  log_info "fmt: gofmt -l ."
  local unformatted
  unformatted="$(cd "$PROJECT_ROOT" && gofmt -l .)"
  if [[ -n "$unformatted" ]]; then
    log_error "gofmt found unformatted files:"
    printf '  %s\n' "$unformatted" >&2
    exit 1
  fi
  log_success "fmt: OK"
}

function cmd_vet() {
  require_cmd go
  log_info "vet: go vet ./..."
  (cd "$PROJECT_ROOT" && go vet ./...)
  log_success "vet: OK"
}

function cmd_lint() {
  # lint = formatting + vet + staticcheck (if available).
  cmd_fmt
  cmd_vet
  if command -v staticcheck >/dev/null 2>&1; then
    log_info "lint: staticcheck ./..."
    (cd "$PROJECT_ROOT" && staticcheck ./...)
    log_success "lint: staticcheck OK"
  else
    log_warn "lint: staticcheck not installed; skipping (fmt + vet enforced)"
  fi
}

function cmd_cover() {
  require_cmd go
  log_info "cover: go test ./... -covermode=atomic -coverprofile=coverage.out"
  (cd "$PROJECT_ROOT" && go test ./... -covermode=atomic -coverprofile=coverage.out)
  (cd "$PROJECT_ROOT" && go tool cover -func=coverage.out | tail -1)
  log_success "cover: OK (profile at coverage.out)"
}

# -------- usage --------
function usage() {
  cat <<EOF
Usage: ./ctl.sh <command> [args...]

Commands:
  build        Compile the library (go build ./...)
  test         Run the test suite with the race detector (go test ./... -race)
  lint         Check formatting (gofmt) + go vet + staticcheck (if installed)
  vet          Run go vet ./...
  fmt          Check formatting with gofmt -l
  cover        Run tests with a coverage profile (coverage.out)
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
