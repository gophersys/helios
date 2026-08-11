#!/usr/bin/env bash
#
# ctl.sh — repo-wide control for gophersys/.devcontainer
#
# Builds, pushes, lists, and validates every image under the repo root.
# Delegates per-image work to <name>/ctl.sh.
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

# The logging, the tool gate and the multi-arch guard live in _ctl/lib.sh, 1
# time only. This script owns the repo-wide verbs, which act on the whole set.
#
# This script does NOT call require_buildx_and_multi_arch, and that is
# deliberate. The guard enforces the platform list of 1 image, and the list is
# not the same for every image: a runner image is amd64 only. `push` delegates
# to the per-image ctl.sh, which calls the guard with its own list.
# shellcheck source-path=SCRIPTDIR
# shellcheck source=_ctl/lib.sh
source "$PROJECT_ROOT/_ctl/lib.sh"

# Dependency order — parents first. `base` is the root of the dev-image
# family; `flutter` and `zephyr` both layer on top of `base`, and
# `zephyr-devbox` layers on top of `zephyr`.
#
# `base-runner` is the `+ runner` layer (directory `runner/`) applied to `base`.
# It is a CI image, not a devcontainer, so it has no devcontainer.json. One
# Dockerfile serves every parent — RUNNER_PARENT selects which — so adding
# `zephyr-runner` is a matrix entry, never a new directory.
BUILD_ORDER=(base base-runner flutter zephyr zephyr-devbox)

# -------- helpers --------
# Image name -> source directory. These are 1:1 except for the `+ runner`
# variants: one directory (`runner/`) builds `<parent>-runner` for every parent,
# so `base-runner` resolves to `runner`. Keeping one directory is the point —
# a second runner Dockerfile would drift from the first.
function image_dir() {
  local name="$1"
  case "$name" in
    *-runner) printf '%s/runner' "$PROJECT_ROOT" ;;
    *)        printf '%s/%s' "$PROJECT_ROOT" "$name" ;;
  esac
}

# Image name -> the RUNNER_PARENT its ctl.sh expects (runner variants only).
function runner_parent() {
  printf '%s' "${1%-runner}"
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
  # Runner variants share one directory, so the parent is passed in rather than
  # baked into the image's own ctl.sh.
  case "$name" in
    *-runner) (cd "$dir" && RUNNER_PARENT="$(runner_parent "$name")" bash ./ctl.sh "$@") ;;
    *)        (cd "$dir" && bash ./ctl.sh "$@") ;;
  esac
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
  printf '%-13s  %s\n' "IMAGE" "REF"
  printf '%-13s  %s\n' "-----" "---"
  for name in "${BUILD_ORDER[@]}"; do
    ref="ghcr.io/gophersys/${name}:latest"
    printf '%-13s  %s\n' "$name" "$ref"
  done
}

# Validate: shellcheck every ctl.sh, jq every project.json, hadolint every
# Dockerfile (warn if missing), and refuse Dockerfiles that hardcode a
# semver-shaped version inside a RUN line instead of threading an ARG.
function cmd_validate() {
  require_cmd shellcheck jq
  local rc=0
  local name dir script

  log_info "shellcheck: ctl.sh"
  shellcheck -x "$PROJECT_ROOT/ctl.sh" || rc=1

  # The shared library holds the body of every per-image verb, so it is the
  # most important script in the repository. shellcheck it explicitly. A
  # missing file makes shellcheck exit non-zero, which fails validate.
  log_info "shellcheck: _ctl/lib.sh"
  shellcheck -x "$PROJECT_ROOT/_ctl/lib.sh" || rc=1

  for name in "${BUILD_ORDER[@]}"; do
    dir="$(image_dir "$name")"
    # Every shell script an image dir ships (ctl.sh, entrypoints, ...).
    for script in "$dir"/*.sh; do
      log_info "shellcheck: ${name}/$(basename "$script")"
      shellcheck -x "$script" || rc=1
    done

    log_info "jq parse: ${name}/project.json"
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
      log_error "${name}/Dockerfile: hardcoded version(s) in RUN lines — use ARGs"
      printf '%s\n' "$bad" >&2
      rc=1
    fi
  done

  log_info "jq parse: project.json"
  jq empty "$PROJECT_ROOT/project.json" || rc=1

  if command -v hadolint >/dev/null 2>&1; then
    for name in "${BUILD_ORDER[@]}"; do
      dir="$(image_dir "$name")"
      log_info "hadolint: ${name}/Dockerfile"
      hadolint "$dir/Dockerfile" || rc=1
    done
  else
    # A missing tool is a FAILURE, never a skip. This printed a warning and
    # returned OK, so `validate` reported success while linting no Dockerfile at
    # all — on a host without hadolint it checked nothing and said it passed.
    log_error "hadolint is not installed, so no Dockerfile was linted. Install it (brew install hadolint) or run this inside the devcontainer, which has it."
    rc=1
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
