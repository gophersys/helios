#!/usr/bin/env bash
#
# .ci/ctl.sh — CI orchestration layer for gophersys/.devcontainer
#
# Sits one level above the repo-level ctl.sh and the per-image ctl.sh scripts.
# Every verb here acts on the WHOLE set of managed images (base + flutter +
# zephyr + zephyr-devbox) in dependency order, and delegates per-image work
# to the repo-level ctl.sh.
#
# Verbs:
#   validate              shellcheck + hadolint + jq across the repo
#   build-all             native single-arch build of every image, parent first
#   build-all-multi-arch  explicit buildx multi-arch build of every image, no push
#   push-all              ENFORCED multi-arch buildx --push of every image
#   smoke-test-all        run .ci/smoke.sh against each image (native-arch only)
#   help
#
# Usage: bash .ci/ctl.sh <verb> [args...]
#
set -Eeuo pipefail
IFS=$'\n\t'

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$PROJECT_ROOT/.." && pwd)"

# The logging and the tool gate live in _ctl/lib.sh, 1 time only. This script
# owns the verbs that act on the whole set of images.
# shellcheck source-path=SCRIPTDIR
# shellcheck source=../_ctl/lib.sh
source "$REPO_ROOT/_ctl/lib.sh"

# Dependency order — parents first.
BUILD_ORDER=(base base-runner flutter zephyr zephyr-devbox)

# Image name -> source directory. 1:1 except the `+ runner` variants: one
# directory (`runner/`) builds `<parent>-runner` for every parent. Mirrors the
# resolver in the repo-level ctl.sh; both must agree.
function image_dir() {
  local name="$1"
  case "$name" in
    *-runner) printf '%s/runner' "$REPO_ROOT" ;;
    *)        printf '%s/%s' "$REPO_ROOT" "$name" ;;
  esac
}

# -------- helpers --------
function repo_ctl() {
  (cd "$REPO_ROOT" && bash ./ctl.sh "$@")
}

# -------- verbs --------

# validate — shellcheck + hadolint + jq, recursive over the managed tree.
function cmd_validate() {
  require_cmd shellcheck jq
  local rc=0
  local name dir script

  log_info "shellcheck: .ci/ctl.sh"
  shellcheck -x "$PROJECT_ROOT/ctl.sh" || rc=1

  if [[ -f "$PROJECT_ROOT/smoke.sh" ]]; then
    log_info "shellcheck: .ci/smoke.sh"
    shellcheck -x "$PROJECT_ROOT/smoke.sh" || rc=1
  fi

  log_info "shellcheck: ctl.sh"
  shellcheck -x "$REPO_ROOT/ctl.sh" || rc=1

  # The shared library holds the body of every per-image verb. A missing file
  # makes shellcheck exit non-zero, which fails validate.
  log_info "shellcheck: _ctl/lib.sh"
  shellcheck -x "$REPO_ROOT/_ctl/lib.sh" || rc=1

  for name in "${BUILD_ORDER[@]}"; do
    dir="$(image_dir "$name")"
    # Every shell script an image dir ships (ctl.sh, entrypoints, ...).
    for script in "$dir"/*.sh; do
      log_info "shellcheck: ${name}/$(basename "$script")"
      shellcheck -x "$script" || rc=1
    done

    log_info "jq parse: ${name}/project.json"
    jq empty "$dir/project.json" || rc=1
  done

  log_info "jq parse: project.json"
  jq empty "$REPO_ROOT/project.json" || rc=1

  log_info "jq parse: .ci/project.json"
  jq empty "$PROJECT_ROOT/project.json" || rc=1

  if command -v hadolint >/dev/null 2>&1; then
    for name in "${BUILD_ORDER[@]}"; do
      dir="$(image_dir "$name")"
      log_info "hadolint: ${name}/Dockerfile"
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

# build-all — native single-arch build of every image, in dependency order.
function cmd_build_all() {
  require_cmd docker
  local name
  for name in "${BUILD_ORDER[@]}"; do
    log_info "=== building ${name} (native single-arch) ==="
    repo_ctl build "$name"
  done
  log_info "build-all: OK"
}

# build-all-multi-arch — explicit multi-arch build of every image, no push.
function cmd_build_all_multi_arch() {
  require_cmd docker
  local name
  for name in "${BUILD_ORDER[@]}"; do
    log_info "=== building ${name} (multi-arch, no push) ==="
    repo_ctl build-multi-arch "$name"
  done
  log_info "build-all-multi-arch: OK"
}

# push-all — ENFORCED multi-arch push of every image to ghcr.
# This verb checks only that buildx exists, because the required platform list
# is not the same for every image. The per-image ctl.sh calls the full guard
# require_buildx_and_multi_arch with its own list.
function cmd_push_all() {
  require_buildx
  local name
  for name in "${BUILD_ORDER[@]}"; do
    log_info "=== pushing ${name} (multi-arch) ==="
    repo_ctl push "$name"
  done
  log_info "push-all: OK"
}

# smoke-test-all — run .ci/smoke.sh against each image. Native arch only;
# QEMU is not involved because we run the image for our own arch.
function cmd_smoke_test_all() {
  require_cmd docker
  if [[ ! -x "$PROJECT_ROOT/smoke.sh" ]]; then
    log_error "missing or non-executable: .ci/smoke.sh"
    return 1
  fi
  local name rc=0
  for name in "${BUILD_ORDER[@]}"; do
    log_info "=== smoke-testing ${name} ==="
    if ! bash "$PROJECT_ROOT/smoke.sh" "$name"; then
      log_error "smoke-test failed for ${name}"
      rc=1
    fi
  done
  if [[ $rc -eq 0 ]]; then
    log_info "smoke-test-all: OK"
  else
    log_error "smoke-test-all: FAILED"
  fi
  return "$rc"
}

# -------- usage --------
function usage() {
  local order
  order="$(IFS=' '; printf '%s' "${BUILD_ORDER[*]}")"
  cat <<EOF
Usage: bash .ci/ctl.sh <verb> [args...]

Managed images (build order): ${order}

Verbs:
  validate              shellcheck + hadolint + jq across the repo
  build-all             Native single-arch build of every image
  build-all-multi-arch  Explicit multi-arch build of every image (no push)
  push-all              ENFORCED multi-arch push of every image to ghcr.io
  smoke-test-all        Run .ci/smoke.sh against each freshly-built image
  help                  Show this message
EOF
}

# -------- dispatcher --------
function main() {
  local cmd="${1:-help}"
  shift || true
  case "$cmd" in
    validate)             cmd_validate             "$@" ;;
    build-all)            cmd_build_all            "$@" ;;
    build-all-multi-arch) cmd_build_all_multi_arch "$@" ;;
    push-all)             cmd_push_all             "$@" ;;
    smoke-test-all)       cmd_smoke_test_all       "$@" ;;
    help|"")              usage ;;
    *)                    log_error "unknown verb: '$cmd'"; usage; exit 1 ;;
  esac
}

main "$@"
