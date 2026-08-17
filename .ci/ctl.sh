#!/usr/bin/env bash
#
# .ci/ctl.sh — CI orchestration layer for gophersys/.devcontainer
#
# Sits one level above the repo-level ctl.sh and the per-image ctl.sh scripts.
#
# Verbs:
#   validate              shellcheck + hadolint + jq across the repo
#   help
#
# `build-all`, `push-all` and `smoke-test-all` stood here and are DELETED. Each
# one looped BUILD_ORDER unconditionally, which is the opposite of the
# affected-only rule every publishing job obeys: a job gates its build, its smoke
# and its push on `.ci/affected.sh <image>`, so the unit of a CI run is 1 image
# and not the set. No workflow and no script called any of the 3. A verb nothing
# invokes is a capability the usage block advertises and nobody maintains, and
# `push-all` advertised a way to publish all 5 images past that gate.
#
# Usage: bash .ci/ctl.sh <verb> [args...]
#
set -Eeuo pipefail
IFS=$'\n\t'

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$PROJECT_ROOT/.." && pwd)"

# The logging and the tool gate live in _ctl/lib.sh, 1 time only.
# shellcheck source-path=SCRIPTDIR
# shellcheck source=../_ctl/lib.sh
source "$REPO_ROOT/_ctl/lib.sh"

# Dependency order — parents first. `cloud` stands alone (FROM ubuntu): the
# successor image of the consolidation program (ledger #94), and what all 3 ARC
# pools run. `base-runner` was here and is RETIRED — see the note beside the
# other BUILD_ORDER, in the repository-root ctl.sh. The 2 must agree, and
# validate.yml asserts that they do.
BUILD_ORDER=(base flutter zephyr zephyr-devbox cloud)

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

# -------- usage --------
function usage() {
  local order
  order="$(IFS=' '; printf '%s' "${BUILD_ORDER[*]}")"
  cat <<EOF
Usage: bash .ci/ctl.sh <verb> [args...]

Managed images (build order): ${order}

Verbs:
  validate              shellcheck + hadolint + jq across the repo
  help                  Show this message
EOF
}

# -------- dispatcher --------
function main() {
  local cmd="${1:-help}"
  shift || true
  case "$cmd" in
    validate)             cmd_validate             "$@" ;;
    help|"")              usage ;;
    *)                    log_error "unknown verb: '$cmd'"; usage; exit 1 ;;
  esac
}

main "$@"
