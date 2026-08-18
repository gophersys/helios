#!/usr/bin/env bash
#
# scripts/ctl.sh — control script for the repository-level shell scripts in scripts/.
#
# scripts/ belonged to no Nx project, so `nx affected` mapped a change here to no target and the
# canonical gate ran nothing for it. That is how the BSD-only mktemp template in
# assert-no-skipped-tests.sh survived 8 days of green pull requests. These 2 verbs are the missing
# ownership: `lint` and `test` are the target names `.ci/ctl.sh affected-check` already asks for.
#
# Usage: ./ctl.sh <command> [args...]
#
# Verbs are uniform with the monorepo's nx:run-commands convention: project.json
# targets are thin wrappers that delegate here.
#
set -Eeuo pipefail
IFS=$'\n\t'

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# -------- logging --------
function log_info()    { printf '\033[0;36m[info]\033[0m  %s\n' "$*"; }
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

# collect_scripts <glob suffix> — echo each scripts/*<suffix> that exists, one per line. An
# unmatched glob stays literal under bash, so each candidate is tested before it is used.
function collect_scripts() {
  local suffix="$1" candidate
  for candidate in "$PROJECT_ROOT"/*"$suffix"; do
    [[ -f "$candidate" ]] || continue
    printf '%s\n' "$candidate"
  done
}

# -------- commands --------
function cmd_lint() {
  require_cmd shellcheck
  local -a scripts=()
  local script
  while IFS= read -r script; do
    scripts+=("$script")
  done < <(collect_scripts '.sh')
  # A lint that found nothing to lint and reported OK is the dead gate this project exists to
  # close, so an empty set fails instead.
  if [[ ${#scripts[@]} -eq 0 ]]; then
    log_error "lint: no *.sh found in $PROJECT_ROOT"
    exit 1
  fi
  log_info "lint: shellcheck ${#scripts[@]} script(s)"
  shellcheck "${scripts[@]}"
  log_success "lint: OK"
}

function cmd_test() {
  require_cmd bash
  local -a tests=()
  local test_script
  while IFS= read -r test_script; do
    tests+=("$test_script")
  done < <(collect_scripts '_test.sh')
  if [[ ${#tests[@]} -eq 0 ]]; then
    log_error "test: no *_test.sh found in $PROJECT_ROOT"
    exit 1
  fi
  # set -e stops at the first non-zero test script.
  for test_script in "${tests[@]}"; do
    log_info "test: ${test_script##*/}"
    bash "$test_script"
  done
  log_success "test: OK — ${#tests[@]} test script(s)"
}

# -------- usage --------
function usage() {
  cat <<EOF
Usage: ./ctl.sh <command> [args...]

Commands:
  lint         shellcheck every scripts/*.sh
  test         Run every scripts/*_test.sh, stopping at the first failure
  help         Show this message
EOF
}

# -------- dispatcher --------
function main() {
  local cmd="${1:-help}"
  shift || true
  case "$cmd" in
    lint)     cmd_lint "$@" ;;
    test)     cmd_test "$@" ;;
    help|"")  usage ;;
    *)        log_error "unknown command: '$cmd'"; usage; exit 1 ;;
  esac
}

main "$@"
