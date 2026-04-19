#!/usr/bin/env bash
#
# ctl.sh — repo-wide control for gophersys/.devcontainer
#
# Builds, pushes, lists, and validates every base image under images/*.
# Delegates per-image work to images/<name>/ctl.sh.
#
# Usage: ./ctl.sh <command> [args...]
#
set -Eeuo pipefail
IFS=$'\n\t'

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC2034  # REPO_ROOT exposed for future cmd_* helpers
REPO_ROOT="$(git -C "$PROJECT_ROOT" rev-parse --show-toplevel)"

# Dependency order — parents first. Each entry is the image directory name
# under images/. The list is walked sequentially in build-all so that an
# image's base layer is available locally before the dependent builds.
BUILD_ORDER=(base node python go rust flutter zephyr)

# -------- logging --------
function log_info()  { printf '\033[0;36m[info]\033[0m  %s\n' "$*"; }
function log_warn()  { printf '\033[0;33m[warn]\033[0m  %s\n' "$*" >&2; }
function log_error() { printf '\033[0;31m[error]\033[0m %s\n' "$*" >&2; }

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

# -------- cleanup --------
BG_PIDS=()

function on_exit() {
  local rc=$?
  local pid
  for pid in "${BG_PIDS[@]}"; do
    kill "$pid" 2>/dev/null || true  # already exited — expected
  done
  return "$rc"
}
trap on_exit EXIT

# -------- helpers --------
function image_dir() {
  local name="$1"
  printf '%s/images/%s' "$PROJECT_ROOT" "$name"
}

function image_ctl() {
  local name="$1"
  shift
  local dir
  dir="$(image_dir "$name")"
  if [[ ! -x "$dir/ctl.sh" ]]; then
    log_error "missing or non-executable: $dir/ctl.sh"
    return 1
  fi
  (cd "$dir" && bash ./ctl.sh "$@")
}

# -------- commands --------
function cmd_build_all() {
  require_cmd docker
  local name
  for name in "${BUILD_ORDER[@]}"; do
    log_info "building image: $name"
    image_ctl "$name" build
  done
  log_info "build-all complete (${#BUILD_ORDER[@]} images)"
}

function cmd_push_all() {
  require_cmd docker
  local name
  for name in "${BUILD_ORDER[@]}"; do
    log_info "pushing image: $name"
    image_ctl "$name" push
  done
  log_info "push-all complete (${#BUILD_ORDER[@]} images)"
}

function cmd_list() {
  local name ref
  printf '%-10s  %s\n' "IMAGE" "REF"
  printf '%-10s  %s\n' "-----" "---"
  for name in "${BUILD_ORDER[@]}"; do
    ref="ghcr.io/gophersys/${name}:latest"
    printf '%-10s  %s\n' "$name" "$ref"
  done
}

function cmd_validate() {
  require_cmd shellcheck jq
  local rc=0
  local name dir

  log_info "shellcheck: ctl.sh"
  shellcheck "$PROJECT_ROOT/ctl.sh" || rc=1

  for name in "${BUILD_ORDER[@]}"; do
    dir="$(image_dir "$name")"
    log_info "shellcheck: images/${name}/ctl.sh"
    shellcheck "$dir/ctl.sh" || rc=1

    log_info "jq parse: images/${name}/project.json"
    jq empty "$dir/project.json" || rc=1

    if [[ ! -s "$dir/Dockerfile" ]]; then
      log_error "empty or missing Dockerfile: $dir/Dockerfile"
      rc=1
    elif ! grep -qE '^[[:space:]]*FROM[[:space:]]+' "$dir/Dockerfile"; then
      # BuildKit directives (`# syntax=...`) and comments are allowed
      # before the first FROM. We require at least one FROM to exist.
      log_error "Dockerfile has no FROM instruction: $dir/Dockerfile"
      rc=1
    fi
  done

  log_info "jq parse: project.json"
  jq empty "$PROJECT_ROOT/project.json" || rc=1

  if command -v hadolint >/dev/null 2>&1; then
    for name in "${BUILD_ORDER[@]}"; do
      dir="$(image_dir "$name")"
      log_info "hadolint: images/${name}/Dockerfile"
      hadolint "$dir/Dockerfile" || rc=1
    done
  else
    log_warn "hadolint not installed — skipping Dockerfile lint"
  fi

  if [[ $rc -eq 0 ]]; then
    log_info "validate: OK"
  else
    log_error "validate: FAILED"
  fi
  return "$rc"
}

function cmd_propagate() {
  local brain_root
  brain_root="$(git -C "$PROJECT_ROOT" rev-parse --show-superproject-working-tree 2>/dev/null || true)"
  if [[ -z "$brain_root" ]] || [[ ! -f "$brain_root/.claude/scripts/propagate.sh" ]]; then
    log_error "propagate must be run from within brain (brain/shared/.devcontainer/)"
    log_error "this script was invoked outside the brain orchestration context"
    exit 1
  fi
  bash "$brain_root/.claude/scripts/propagate.sh" ".devcontainer" "$@"
}

# -------- usage --------
function usage() {
  local order
  order="$(IFS=' '; printf '%s' "${BUILD_ORDER[*]}")"
  cat <<EOF
Usage: ./ctl.sh <command> [args...]

Commands:
  build-all    Build every image in dependency order (${order})
  push-all     Push every image to ghcr.io/gophersys/<name>
  list         List managed images and their canonical refs
  validate     shellcheck every ctl.sh + jq every project.json + hadolint Dockerfiles (if available)
  propagate    Fan out pointer bumps to every consuming project (defers to brain)
  help         Show this message

Per-image operations live under images/<name>/ctl.sh:
  build, push, pull, inspect, help
EOF
}

# -------- dispatcher --------
function main() {
  local cmd="${1:-help}"
  shift || true
  case "$cmd" in
    build-all)  cmd_build_all  "$@" ;;
    push-all)   cmd_push_all   "$@" ;;
    list)       cmd_list       "$@" ;;
    validate)   cmd_validate   "$@" ;;
    propagate)  cmd_propagate  "$@" ;;
    help|"")    usage ;;
    *)          log_error "unknown command: '$cmd'"; usage; exit 1 ;;
  esac
}

main "$@"
