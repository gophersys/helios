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
#   build-all             build every image, parent first
#   push-all              GUARDED buildx --push of every image
#   smoke-test-all        run .ci/smoke.sh against each image
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

# Dependency order — parents first. `cloud` stands alone (FROM ubuntu): the
# additive successor image of the consolidation program (ledger #94).
BUILD_ORDER=(base base-runner flutter zephyr zephyr-devbox cloud)

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
  # ONE body, in the repository-root ctl.sh. This used to be a second copy, and
  # the 2 diverged: this one never carried the ARG-discipline check, so
  # `.ci/ctl.sh validate` reported OK on a Dockerfile with a hardcoded version in
  # a RUN line that `./ctl.sh validate` rejected. A weaker twin of a gate is worse
  # than no twin, because whoever runs it believes they ran the gate.
  bash "$REPO_ROOT/ctl.sh" validate "$@"
}

# build-all — build every image, in dependency order.
function cmd_build_all() {
  require_cmd docker
  local name
  for name in "${BUILD_ORDER[@]}"; do
    log_info "=== building ${name} ==="
    repo_ctl build "$name"
  done
  log_info "build-all: OK"
}

# push-all — GUARDED push of every image to ghcr.
# This verb checks only that buildx exists, because the required platform list
# is not the same for every image. The per-image ctl.sh calls the full guard
# require_buildx_and_platforms with its own list.
function cmd_push_all() {
  require_buildx
  local name
  for name in "${BUILD_ORDER[@]}"; do
    log_info "=== pushing ${name} ==="
    repo_ctl push "$name"
  done
  log_info "push-all: OK"
}

# smoke-test-all — run .ci/smoke.sh against each image. The image runs on the
# host architecture, which is the architecture it was built for.
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
  build-all             Build every image, parent first
  push-all              GUARDED push of every image to ghcr.io
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
    push-all)             cmd_push_all             "$@" ;;
    smoke-test-all)       cmd_smoke_test_all       "$@" ;;
    help|"")              usage ;;
    *)                    log_error "unknown verb: '$cmd'"; usage; exit 1 ;;
  esac
}

main "$@"
