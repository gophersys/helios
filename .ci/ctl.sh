#!/usr/bin/env bash
#
# .ci/ctl.sh — orchestration-layer CI for gophersys/infrastructure.
#
# Verb catalog:
#   validate             — aggregate (runs every validate-<layer> + top-level)
#   validate-machines    — machines/ only
#   validate-clusters    — clusters/ only
#   validate-providers   — providers/ only
#   validate-platform    — platform/{core,services}/ stub-README checks
#   validate-contracts   — contracts/ front-matter + required sections
#   validate-charts      — charts/ stubs
#   status               — repo status
#   release-check        — preflight for brain's release.sh
#   help
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

BG_PIDS=()

function on_exit() {
  local rc=$?
  if [[ ${#BG_PIDS[@]} -gt 0 ]]; then
    local pid
    for pid in "${BG_PIDS[@]}"; do
      kill "$pid" 2>/dev/null || true
    done
  fi
  return "$rc"
}
trap on_exit EXIT

# -------- per-layer validators --------

function cmd_validate_machines() {
  log_info "validate-machines"
  if [[ -x "$REPO_ROOT/machines/ctl.sh" ]]; then
    bash "$REPO_ROOT/machines/ctl.sh" validate
  else
    log_error "machines/ctl.sh missing"
    return 1
  fi
}

function cmd_validate_clusters() {
  log_info "validate-clusters"
  if [[ -x "$REPO_ROOT/clusters/ctl.sh" ]]; then
    bash "$REPO_ROOT/clusters/ctl.sh" validate
  else
    log_error "clusters/ctl.sh missing"
    return 1
  fi
}

function cmd_validate_providers() {
  log_info "validate-providers"
  local rc=0
  local d
  for d in "$REPO_ROOT"/providers/*/; do
    [[ -f "$d/README.md" ]] || { log_error "provider missing README: $(basename "$d")"; rc=1; }
  done
  [[ $rc -eq 0 ]] && log_success "validate-providers: OK"
  return "$rc"
}

function cmd_validate_platform() {
  log_info "validate-platform"
  local rc=0
  local d
  # Every leaf under platform/core and platform/services must have a README.
  while IFS= read -r -d '' d; do
    [[ -f "$d/README.md" ]] || { log_error "platform leaf missing README: ${d#"$REPO_ROOT"/}"; rc=1; }
  done < <(find "$REPO_ROOT/platform/core" "$REPO_ROOT/platform/services" -mindepth 1 -type d -print0 2>/dev/null)
  [[ $rc -eq 0 ]] && log_success "validate-platform: OK"
  return "$rc"
}

function cmd_validate_contracts() {
  log_info "validate-contracts"
  local rc=0
  local f
  for f in "$REPO_ROOT"/contracts/*.md; do
    [[ "$(basename "$f")" == "README.md" ]] && continue
    # Front-matter must start with ---
    if ! head -1 "$f" | grep -qx '^---$'; then
      log_error "contract missing front-matter: ${f#"$REPO_ROOT"/}"
      rc=1
      continue
    fi
    # Required sections
    local sec
    for sec in "## Abstract" "## Interface" "## Guarantees" "## Caveats" "## Example"; do
      if ! grep -qF "$sec" "$f"; then
        log_error "contract missing section '$sec': ${f#"$REPO_ROOT"/}"
        rc=1
      fi
    done
  done
  [[ $rc -eq 0 ]] && log_success "validate-contracts: OK"
  return "$rc"
}

function cmd_validate_charts() {
  log_info "validate-charts"
  local rc=0
  if [[ -d "$REPO_ROOT/charts" ]]; then
    local d
    for d in "$REPO_ROOT"/charts/*/; do
      [[ -f "$d/README.md" ]] || { log_error "chart leaf missing README: $(basename "$d")"; rc=1; }
    done
  fi
  [[ $rc -eq 0 ]] && log_success "validate-charts: OK"
  return "$rc"
}

# -------- aggregate --------

function cmd_validate() {
  local rc=0
  # Top-level validate (shellcheck, project.json parse) if present.
  if [[ -x "$REPO_ROOT/ctl.sh" ]]; then
    bash "$REPO_ROOT/ctl.sh" validate || rc=1
  fi
  cmd_validate_machines  || rc=1
  cmd_validate_clusters  || rc=1
  cmd_validate_providers || rc=1
  cmd_validate_platform  || rc=1
  cmd_validate_contracts || rc=1
  cmd_validate_charts    || rc=1
  echo
  if [[ $rc -eq 0 ]]; then
    log_success "all layers validated clean"
  else
    log_error "one or more layer validators failed — see above"
  fi
  return "$rc"
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
  cmd_validate || return 1
  log_success "release-check: ready (HEAD $head)"
}

function usage() {
  cat <<EOF
Usage: bash .ci/ctl.sh <command> [args]

Commands:
  validate              Aggregate: run every per-layer validator + top-level
  validate-machines     machines/ layer only
  validate-clusters     clusters/ layer only
  validate-providers    providers/ layer (README presence)
  validate-platform     platform/{core,services} README presence per leaf
  validate-contracts    contracts/ front-matter + required sections
  validate-charts       charts/ README presence
  status                Repo status (delegates when possible)
  release-check         Preflight for brain's release.sh (clean tree, on main,
                        in sync with origin, aggregate validate clean)
  help                  Show this message
EOF
}

function main() {
  local cmd="${1:-help}"
  shift || true
  case "$cmd" in
    validate)            cmd_validate            "$@" ;;
    validate-machines)   cmd_validate_machines   "$@" ;;
    validate-clusters)   cmd_validate_clusters   "$@" ;;
    validate-providers)  cmd_validate_providers  "$@" ;;
    validate-platform)   cmd_validate_platform   "$@" ;;
    validate-contracts)  cmd_validate_contracts  "$@" ;;
    validate-charts)     cmd_validate_charts     "$@" ;;
    status)              cmd_status              "$@" ;;
    release-check)       cmd_release_check       "$@" ;;
    help|"")             usage ;;
    *) log_error "unknown command: '$cmd'"; usage; exit 1 ;;
  esac
}

main "$@"
