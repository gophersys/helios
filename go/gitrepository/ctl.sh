#!/usr/bin/env bash
#
# libs/go/gitrepository/ctl.sh — control script for the Eden gitrepository library
# (the S2 git-operations port: clone/fetch, worktree create/remove, status/diff,
# stage/commit with a per-actor Author identity, fast-forward-only push; the default
# Backend shells the system git binary; contract:
# docs/architecture/contracts/gitrepository.md).
#
# Usage: ./ctl.sh <command> [args...]
#
# Verbs are uniform with the monorepo's nx:run-commands convention: project.json
# targets are thin wrappers that delegate here, so a consumer can invoke
# `nx run gitrepository:test` without reading source.
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

function cmd_integration() {
  require_cmd go git
  log_info "integration: go test -tags integration ./... -race -count=1 (REAL system git + a local bare remote)"
  (cd "$PROJECT_ROOT" && go test -tags integration ./... -race -count=1)
  log_success "integration: OK"
}

function cmd_vet() {
  require_cmd go
  log_info "vet: go vet ./..."
  (cd "$PROJECT_ROOT" && go vet ./...)
  log_success "vet: OK"
}

function cmd_fmt() {
  require_cmd gofumpt
  log_info "fmt: gofumpt -w ."
  (cd "$PROJECT_ROOT" && gofumpt -w .)
  log_success "fmt: OK"
}

function cmd_lint() {
  require_cmd go gofumpt
  log_info "lint: gofumpt -l ."
  local unformatted
  unformatted="$(cd "$PROJECT_ROOT" && gofumpt -l .)"
  if [[ -n "$unformatted" ]]; then
    log_error "gofumpt found unformatted files:"
    printf '  %s\n' "$unformatted" >&2
    exit 1
  fi
  log_info "lint: go vet ./..."
  (cd "$PROJECT_ROOT" && go vet ./...)
  if command -v golangci-lint >/dev/null 2>&1; then
    log_info "lint: golangci-lint run ./..."
    (cd "$PROJECT_ROOT" && golangci-lint run ./...)
    log_info "lint: golangci-lint run --build-tags integration ./..."
    (cd "$PROJECT_ROOT" && golangci-lint run --build-tags integration ./...)
  else
    log_warn "lint: golangci-lint not installed — skipping (install per ADR-0018)"
  fi
  log_success "lint: OK"
}

function cmd_cover() {
  require_cmd go
  log_info "cover: go test ./... -coverprofile"
  local profile
  profile="$(mktemp -t gitrepository-cover.XXXXXX)"
  (cd "$PROJECT_ROOT" && go test ./... -covermode=atomic -coverprofile="$profile")
  (cd "$PROJECT_ROOT" && go tool cover -func="$profile" | tail -1)
  rm -f "$profile"
  log_success "cover: OK"
}

# -------- usage --------
function usage() {
  cat <<'EOF'
Usage: ./ctl.sh <command> [args...]

Commands:
  build        Compile the library (go build ./...)
  test         Run the unit + conformance suite with the race detector (go test ./... -race -count=1)
  integration  Run the REAL-substrate suite (go test -tags integration ./... -race -count=1; needs git)
  lint         Check formatting (gofumpt), run go vet, and golangci-lint (both tag sets) if installed
  vet          Run go vet ./...
  fmt          Format sources in place (gofumpt -w .)
  cover        Run tests with coverage and print the total
  help         Show this message
EOF
}

# -------- dispatcher --------
function main() {
  local cmd="${1:-help}"
  shift || true
  case "$cmd" in
    build)       cmd_build       "$@" ;;
    test)        cmd_test        "$@" ;;
    integration) cmd_integration "$@" ;;
    lint)        cmd_lint        "$@" ;;
    vet)         cmd_vet         "$@" ;;
    fmt)         cmd_fmt         "$@" ;;
    cover)       cmd_cover       "$@" ;;
    help|"")     usage ;;
    *)           log_error "unknown command: '$cmd'"; usage; exit 1 ;;
  esac
}

main "$@"
