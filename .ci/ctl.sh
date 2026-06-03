#!/usr/bin/env bash
#
# monorepo/.ci/ctl.sh — baseline CI for every project created from the
# gophersys/template monorepo scaffold.
#
# Verbs run `nx run-many` or `nx affected` over the whole monorepo. When
# nx isn't yet installed (fresh scaffold), the verbs fall through to a
# no-op with an informational message so the workflow doesn't explode on
# day one.
#
set -Eeuo pipefail
IFS=$'\n\t'

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(git -C "$PROJECT_ROOT" rev-parse --show-toplevel)"

function log_info()    { printf '\033[0;36m[info]\033[0m  %s\n' "$*"; }
function log_warn()    { printf '\033[0;33m[warn]\033[0m  %s\n' "$*" >&2; }
function log_error()   { printf '\033[0;31m[error]\033[0m %s\n' "$*" >&2; }
function log_success() { printf '\033[0;32m[ok]\033[0m    %s\n' "$*"; }

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

function on_exit() {
  local rc=$?
  return "$rc"
}
trap on_exit EXIT

# Base commit for `nx affected`. Defaults to origin/main.
NX_BASE="${NX_BASE:-origin/main}"

function has_nx() {
  # Check, in order: global nx, node_modules/.bin (npm/yarn classic), Yarn
  # 4 PnP (needs `yarn nx` to resolve via .pnp.cjs).
  if command -v nx >/dev/null 2>&1; then return 0; fi
  if [[ -x "$REPO_ROOT/node_modules/.bin/nx" ]]; then return 0; fi
  if [[ -f "$REPO_ROOT/.pnp.cjs" ]] && command -v yarn >/dev/null 2>&1; then
    return 0
  fi
  return 1
}

function nx_cmd() {
  if command -v nx >/dev/null 2>&1; then
    nx "$@"
  elif [[ -x "$REPO_ROOT/node_modules/.bin/nx" ]]; then
    "$REPO_ROOT/node_modules/.bin/nx" "$@"
  else
    # Yarn 4 PnP: `yarn nx` resolves via .pnp.cjs. --silent suppresses
    # yarn's own banner lines so nx output stays clean.
    (cd "$REPO_ROOT" && yarn nx "$@")
  fi
}

function cmd_validate() {
  log_info "validate: shellcheck .ci/ctl.sh"
  require_cmd shellcheck jq
  shellcheck "$PROJECT_ROOT/ctl.sh"

  if has_nx; then
    log_info "validate: nx run-many -t validate"
    (cd "$REPO_ROOT" && nx_cmd run-many -t validate --output-style=stream) || return 1
  else
    log_warn "nx not available; project-level validate skipped"
  fi
  log_success "validate: OK"
}

function cmd_build_all() {
  if ! has_nx; then
    log_warn "nx not available; build-all is a no-op"
    return 0
  fi
  (cd "$REPO_ROOT" && nx_cmd run-many -t build --output-style=stream)
}

function cmd_test_all() {
  if ! has_nx; then
    log_warn "nx not available; test-all is a no-op"
    return 0
  fi
  (cd "$REPO_ROOT" && nx_cmd run-many -t test --output-style=stream)
}

function cmd_lint_all() {
  if ! has_nx; then
    log_warn "nx not available; lint-all is a no-op"
    return 0
  fi
  (cd "$REPO_ROOT" && nx_cmd run-many -t lint --output-style=stream)
}

function cmd_typecheck_all() {
  if ! has_nx; then
    log_warn "nx not available; typecheck-all is a no-op"
    return 0
  fi
  (cd "$REPO_ROOT" && nx_cmd run-many -t typecheck --output-style=stream)
}

function cmd_affected_build() {
  if ! has_nx; then log_warn "nx not available; affected-build is a no-op"; return 0; fi
  (cd "$REPO_ROOT" && nx_cmd affected -t build --base="$NX_BASE" --output-style=stream)
}

function cmd_affected_test() {
  if ! has_nx; then log_warn "nx not available; affected-test is a no-op"; return 0; fi
  (cd "$REPO_ROOT" && nx_cmd affected -t test --base="$NX_BASE" --output-style=stream)
}

function cmd_affected_check() {
  if ! has_nx; then log_warn "nx not available; affected-check is a no-op"; return 0; fi
  (cd "$REPO_ROOT" && nx_cmd affected -t lint,typecheck,test --base="$NX_BASE" --output-style=stream)
}

function cmd_release_check() {
  require_cmd git
  if [[ -n "$(git -C "$REPO_ROOT" status --porcelain)" ]]; then
    log_error "working tree dirty"
    git -C "$REPO_ROOT" status --short >&2
    return 1
  fi
  local branch
  branch="$(git -C "$REPO_ROOT" rev-parse --abbrev-ref HEAD)"
  if [[ "$branch" != "main" ]]; then
    log_error "not on main (on '$branch')"
    return 1
  fi
  git -C "$REPO_ROOT" fetch --quiet origin
  local head remote
  head="$(git -C "$REPO_ROOT" rev-parse HEAD)"
  remote="$(git -C "$REPO_ROOT" rev-parse origin/main)"
  if [[ "$head" != "$remote" ]]; then
    log_error "main ($head) != origin/main ($remote)"
    return 1
  fi
  log_success "release-check: ready"
}

function usage() {
  cat <<EOF
Usage: bash .ci/ctl.sh <command> [args]

Commands:
  validate        shellcheck + nx run-many -t validate
  build-all       nx run-many -t build
  test-all        nx run-many -t test
  lint-all        nx run-many -t lint
  typecheck-all   nx run-many -t typecheck
  affected-build  nx affected -t build (base=\${NX_BASE:-origin/main})
  affected-test   nx affected -t test
  affected-check  nx affected -t lint,typecheck,test (canonical PR gate)
  release-check   preflight: clean, on main, up to date with origin
  help            Show this message
EOF
}

function main() {
  local cmd="${1:-help}"
  shift || true
  case "$cmd" in
    validate)        cmd_validate        "$@" ;;
    build-all)       cmd_build_all       "$@" ;;
    test-all)        cmd_test_all        "$@" ;;
    lint-all)        cmd_lint_all        "$@" ;;
    typecheck-all)   cmd_typecheck_all   "$@" ;;
    affected-build)  cmd_affected_build  "$@" ;;
    affected-test)   cmd_affected_test   "$@" ;;
    affected-check)  cmd_affected_check  "$@" ;;
    release-check)   cmd_release_check   "$@" ;;
    help|"")         usage ;;
    *) log_error "unknown command: '$cmd'"; usage; exit 1 ;;
  esac
}

main "$@"
