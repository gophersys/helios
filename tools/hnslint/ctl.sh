#!/usr/bin/env bash
#
# tools/hnslint/ctl.sh — control script for hnslint, the structural HNS-1 naming
# checker (ADR-0018 Layer 1; 10 §5). hnslint enforces the rules forbidigo
# cannot: module path, primary/fakes package names, and banned directory/package
# tokens for a libs/go/<slug> module.
#
# Usage: ./ctl.sh <command> [args...]
#
# Verbs are uniform with the monorepo's nx:run-commands convention: project.json
# targets are thin wrappers that delegate here.
#
set -Eeuo pipefail
IFS=$'\n\t'

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(git -C "$PROJECT_ROOT" rev-parse --show-toplevel 2>/dev/null || echo "$PROJECT_ROOT")"
LIBS_GO_DIR="$REPO_ROOT/libs/go"

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
  # GOWORK=off isolates the tool from the dev workspace (10 §6.1, ADR-0018).
  (cd "$PROJECT_ROOT" && GOWORK=off go build ./...)
  log_success "build: OK"
}

function cmd_test() {
  require_cmd go
  log_info "test: go test -race ./..."
  (cd "$PROJECT_ROOT" && GOWORK=off go test -race ./...)
  log_success "test: OK"
}

function cmd_lint() {
  require_cmd go gofumpt
  log_info "lint: gofumpt -l ."
  local unformatted
  unformatted="$(cd "$PROJECT_ROOT" && gofumpt -l . | grep -v '/testdata/' || true)"
  if [[ -n "$unformatted" ]]; then
    log_error "gofumpt found unformatted files:"
    printf '  %s\n' "$unformatted" >&2
    exit 1
  fi
  log_info "lint: go vet ./..."
  (cd "$PROJECT_ROOT" && GOWORK=off go vet ./...)
  log_success "lint: OK"
}

# cmd_run executes hnslint against the directories given as arguments, or
# against all six libs/go/* libraries when none are supplied.
function cmd_run() {
  require_cmd go
  local -a targets=("$@")
  if [[ ${#targets[@]} -eq 0 ]]; then
    if [[ ! -d "$LIBS_GO_DIR" ]]; then
      log_error "libs/go not found at $LIBS_GO_DIR; pass directories explicitly"
      exit 1
    fi
    local d
    for d in "$LIBS_GO_DIR"/*/; do
      [[ -d "$d" ]] && targets+=("${d%/}")
    done
    log_info "run: linting all libs/go/* libraries"
  fi
  (cd "$PROJECT_ROOT" && GOWORK=off go run ./cmd/hnslint "${targets[@]}")
  log_success "run: all targets conform"
}

# -------- usage --------
function usage() {
  cat <<EOF
Usage: ./ctl.sh <command> [args...]

Commands:
  build        Compile hnslint (go build ./...)
  test         Run the test suite with the race detector (go test -race ./...)
  lint         Check formatting (gofumpt) and run go vet
  run [dir...] Run hnslint against the given dirs, or all libs/go/* when omitted
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
    run)      cmd_run   "$@" ;;
    help|"")  usage ;;
    *)        log_error "unknown command: '$cmd'"; usage; exit 1 ;;
  esac
}

main "$@"
