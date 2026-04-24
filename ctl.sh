#!/usr/bin/env bash
#
# ctl.sh — repo-wide control for gophersys/.devcontainer
#
# Builds, pushes, lists, and validates every base image under images/*.
# Delegates per-image work to images/<name>/ctl.sh.
#
# Multi-arch policy:
#   - `build`               native single-arch (fast dev loop)
#   - `build-multi-arch`    explicit buildx multi-arch build (no push)
#   - `push`                ENFORCED multi-arch via buildx (guarded)
#
# Usage: ./ctl.sh <command> [args...]
#
set -Eeuo pipefail
IFS=$'\n\t'

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(git -C "$PROJECT_ROOT" rev-parse --show-toplevel)"
export REPO_ROOT

# Dependency order — parents first. `base` is the root of the dev-image
# family; `flutter` and `zephyr` both layer on top of `base`. `orchestrator`
# is a peer of `base` (not a derivative) — different role, different size.
BUILD_ORDER=(base flutter zephyr orchestrator)

# Multi-arch platforms enforced on push.
MULTI_ARCH_PLATFORMS="linux/amd64,linux/arm64"

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

# Guard: require docker buildx available and capable of multi-arch builds.
# Callers that push MUST invoke this first — there is no flag to downgrade
# to single-arch push. Multi-arch on push is policy, not preference.
function require_buildx_and_multi_arch() {
  require_cmd docker
  if ! docker buildx version >/dev/null 2>&1; then
    log_error "docker buildx is not installed — multi-arch push is mandatory"
    exit 127
  fi
  if ! docker buildx inspect >/dev/null 2>&1; then
    log_error "no active buildx builder — run: docker buildx create --use --name gophersys"
    exit 1
  fi
  local platforms
  platforms="$(docker buildx inspect --bootstrap 2>/dev/null | awk -F': ' '/^Platforms/ {print $2}' | head -1)"
  if [[ -z "$platforms" ]]; then
    log_error "buildx builder reports no platforms; cannot enforce multi-arch"
    exit 1
  fi
  local p
  local -a _platforms
  IFS=',' read -r -a _platforms <<< "$MULTI_ARCH_PLATFORMS"
  for p in "${_platforms[@]}"; do
    if ! printf '%s' "$platforms" | grep -q -- "$p"; then
      log_error "buildx builder missing required platform: $p"
      log_error "current builder platforms: $platforms"
      log_error "enable via QEMU: docker run --privileged --rm tonistiigi/binfmt --install all"
      exit 1
    fi
  done
}

# -------- cleanup --------
BG_PIDS=()

function on_exit() {
  local rc=$?
  local pid
  if [[ ${#BG_PIDS[@]} -gt 0 ]]; then
    for pid in "${BG_PIDS[@]}"; do
      kill "$pid" 2>/dev/null || true  # already exited — expected
    done
  fi
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
function cmd_build() {
  local name="${1:-}"
  if [[ -z "$name" ]]; then
    log_error "usage: ./ctl.sh build <image>"
    exit 2
  fi
  shift
  image_ctl "$name" build "$@"
}

function cmd_build_multi_arch() {
  local name="${1:-}"
  if [[ -z "$name" ]]; then
    log_error "usage: ./ctl.sh build-multi-arch <image>"
    exit 2
  fi
  shift
  image_ctl "$name" build-multi-arch "$@"
}

function cmd_push() {
  local name="${1:-}"
  if [[ -z "$name" ]]; then
    log_error "usage: ./ctl.sh push <image>"
    exit 2
  fi
  shift
  image_ctl "$name" push "$@"
}

function cmd_pull() {
  local name="${1:-}"
  if [[ -z "$name" ]]; then
    log_error "usage: ./ctl.sh pull <image>"
    exit 2
  fi
  shift
  image_ctl "$name" pull "$@"
}

function cmd_inspect() {
  local name="${1:-}"
  if [[ -z "$name" ]]; then
    log_error "usage: ./ctl.sh inspect <image>"
    exit 2
  fi
  shift
  image_ctl "$name" inspect "$@"
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

# Validate: shellcheck every ctl.sh, jq every project.json, hadolint every
# Dockerfile (warn if missing), and refuse Dockerfiles that hardcode a
# semver-shaped version inside a RUN line instead of threading an ARG.
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
      continue
    fi
    if ! grep -qE '^[[:space:]]*FROM[[:space:]]+' "$dir/Dockerfile"; then
      log_error "Dockerfile has no FROM instruction: $dir/Dockerfile"
      rc=1
    fi

    # Reject semver literals inside RUN lines — every version MUST come
    # from an ARG at the top of the Dockerfile.
    local bad
    bad="$(grep -nE '^[[:space:]]*RUN[[:space:]].*=[0-9]+\.[0-9]+\.[0-9]+' "$dir/Dockerfile" || true)"
    if [[ -n "$bad" ]]; then
      log_error "images/${name}/Dockerfile: hardcoded version(s) in RUN lines — use ARGs"
      printf '%s\n' "$bad" >&2
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

# Propagate: delegate submodule pointer bumps to brain's propagate script.
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

# Release: delegate to brain's release.sh. Same parent-context requirement.
function cmd_release() {
  local brain_root
  brain_root="$(git -C "$PROJECT_ROOT" rev-parse --show-superproject-working-tree 2>/dev/null || true)"
  if [[ -z "$brain_root" ]] || [[ ! -f "$brain_root/.claude/scripts/release.sh" ]]; then
    log_error "release must be run from within brain (brain/shared/.devcontainer/)"
    log_error "this script was invoked outside the brain orchestration context"
    exit 1
  fi
  bash "$brain_root/.claude/scripts/release.sh" ".devcontainer" "$@"
}

# -------- usage --------
function usage() {
  local order
  order="$(IFS=' '; printf '%s' "${BUILD_ORDER[*]}")"
  cat <<EOF
Usage: ./ctl.sh <command> [args...]

Images (build order): ${order}

Per-image commands (take <image> as first arg):
  build <image>              Native single-arch build (fast dev loop)
  build-multi-arch <image>   Explicit buildx multi-arch build (no push)
  push <image>               ENFORCED multi-arch buildx build + push
  pull <image>               docker pull ghcr.io/gophersys/<image>:latest
  inspect <image>            docker image inspect ghcr.io/gophersys/<image>:latest

Repo-wide commands:
  list                       Print managed image refs
  validate                   shellcheck, jq, hadolint, ARG-discipline checks
  propagate                  Fan out submodule bumps (delegates to brain)
  release                    Cut a release (delegates to brain)
  help                       Show this message
EOF
}

# -------- dispatcher --------
function main() {
  local cmd="${1:-help}"
  shift || true
  case "$cmd" in
    build)              cmd_build             "$@" ;;
    build-multi-arch)   cmd_build_multi_arch  "$@" ;;
    push)               cmd_push              "$@" ;;
    pull)               cmd_pull              "$@" ;;
    inspect)            cmd_inspect           "$@" ;;
    list)               cmd_list              "$@" ;;
    validate)           cmd_validate          "$@" ;;
    propagate)          cmd_propagate         "$@" ;;
    release)            cmd_release           "$@" ;;
    help|"")            usage ;;
    *)                  log_error "unknown command: '$cmd'"; usage; exit 1 ;;
  esac
}

main "$@"
