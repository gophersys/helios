#!/usr/bin/env bash
#
# .ci/ctl.sh — orchestration-layer CI for gophersys/infrastructure.
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

function cmd_validate() {
  if [[ -x "$REPO_ROOT/ctl.sh" ]]; then
    bash "$REPO_ROOT/ctl.sh" validate "$@"
  else
    log_warn "no repo-level ctl.sh; running minimal validation"
    require_cmd shellcheck
    local files
    mapfile -t files < <(find "$PROJECT_ROOT" -name '*.sh' -not -path '*/.git/*')
    [[ ${#files[@]} -gt 0 ]] && shellcheck "${files[@]}"
    log_success "validate: OK"
  fi
}

function cmd_status() {
  if [[ -x "$REPO_ROOT/ctl.sh" ]]; then
    bash "$REPO_ROOT/ctl.sh" status "$@"
  else
    log_warn "no repo-level ctl.sh; printing minimal status"
    git -C "$REPO_ROOT" status --short | head -20
  fi
}

function cmd_release_check() {
  require_cmd git
  if [[ -n "$(git -C "$REPO_ROOT" status --porcelain)" ]]; then
    log_error "working tree dirty; commit or stash before release"
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
    log_error "main ($head) != origin/main ($remote); pull/push before release"
    return 1
  fi
  log_success "release-check: ready (HEAD $head)"
}

function usage() {
  cat <<EOF
Usage: bash .ci/ctl.sh <command> [args]

Commands:
  validate       shellcheck + JSON validate (delegates when possible)
  status         repo status (delegates when possible)
  release-check  preflight for brain's release.sh
  help           Show this message
EOF
}

function main() {
  local cmd="${1:-help}"
  shift || true
  case "$cmd" in
    validate)       cmd_validate       "$@" ;;
    status)         cmd_status         "$@" ;;
    release-check)  cmd_release_check  "$@" ;;
    help|"")        usage ;;
    *) log_error "unknown command: '$cmd'"; usage; exit 1 ;;
  esac
}

main "$@"
