#!/usr/bin/env bash
#
# libs/go/testing/ctl.sh — control script for the Eden `testing` library: the
# meta-pattern. It vends the canonical FAKES of the two universal deterministic
# ports (FakeClock, FakeRandomSource — the dependencies.Clock / RandomSource
# interfaces are owned by the `dependencies` pattern) and owns the conformance-
# suite construct that proves adapter ≡ fake substitutability (08 §2). The core
# `package testing` imports neither stdlib "testing" nor any assertion library;
# the *testing.T adapters live in `testingtest` (10 §6.1, contract
# docs/architecture/contracts/testing.md, frozen per ADR-0016).
#
# Usage: ./ctl.sh <command> [args...]
#
# Verbs are uniform with the monorepo's nx:run-commands convention: project.json
# targets are thin wrappers that delegate here, so a consumer can invoke
# `nx run testing:test` without reading source.
#
set -Eeuo pipefail
IFS=$'\n\t'

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# find_go_work walks up from PROJECT_ROOT to locate the monorepo's dev go.work.
# NOTE: `libs/` is a git SUBMODULE, so `git rev-parse --show-toplevel` stops at the
# submodule root (…/libs) — but the workspace lives at the MONOREPO root (one level
# above libs). We therefore walk the directory tree by hand rather than ask git.
function find_go_work() {
  local dir="$PROJECT_ROOT"
  while [[ "$dir" != "/" ]]; do
    if [[ -f "$dir/go.work" ]]; then
      printf '%s\n' "$dir/go.work"
      return 0
    fi
    dir="$(dirname "$dir")"
  done
  return 1
}

# GOWORK policy. Unlike the stdlib-only leaf libraries (errors, dependencies,
# configuration), `testing` imports an in-repo module (dependencies) that has no
# PUBLISHED version yet — so a hard GOWORK=off cannot resolve it pre-publish.
# Default policy:
#   - if the caller set GOWORK, honor it (CI/release sets GOWORK=off explicitly);
#   - else if the dev workspace exists, use it (cross-module dev resolution);
#   - else fall back to off (the 10 §6.1 release discipline).
# This keeps the release invariant (a stray workspace never masks a missing
# published version — CI passes GOWORK=off) while letting local dev gates run.
if [[ -z "${GOWORK:-}" ]]; then
  if go_work_path="$(find_go_work)"; then
    export GOWORK="$go_work_path"
  else
    export GOWORK="off"
  fi
fi

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
