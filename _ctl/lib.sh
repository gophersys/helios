#!/usr/bin/env bash
#
# _ctl/lib.sh — the shared ctl library for gophersys/.devcontainer.
#
# The body of every per-image verb lives here, 1 time only. Each per-image
# ctl.sh sets its metadata, sources this file, and dispatches into it. Before
# this file existed, the 5 per-image scripts each carried the same 140 lines,
# and 6 scripts each carried a copy of the multi-arch push guard.
#
# The repo-root ctl.sh and .ci/ctl.sh source this file for the logging, the
# tool gate and the guard. Their own verbs act on the whole set of images, so
# they keep those verbs themselves.
#
# The pattern is the same one that gophersys/libs uses in go/_ctl/lib.sh. The
# directory name starts with an underscore, so Nx and Go ignore it. It is not
# an image directory.
#
# A sourcing script sets this metadata BEFORE the source line, because this
# file reads it while it loads:
#   PROJECT_ROOT           Required. The directory that holds the script.
#   IMAGE_NAME             Required for the image verbs. Example: flutter.
#   MULTI_ARCH_PLATFORMS   Optional. The default is the 2 platforms that the
#                          policy demands. Set it only to declare a measured
#                          narrower target, and give the measurement.
#   IMAGE_BUILD_ARGS       Optional array. Extra arguments for docker build.
#
# This metadata is read at call time, so a script can set it after the source
# line, for example to use a value that this file computes:
#   IMAGE_USAGE_HEADER     Optional text. Extra lines below the Image: header.
#   IMAGE_USAGE_COMMANDS   Optional text. Extra lines below the command list.
#
# shellcheck shell=bash

set -Eeuo pipefail
IFS=$'\n\t'

: "${PROJECT_ROOT:?_ctl/lib.sh: the sourcing ctl.sh must set PROJECT_ROOT}"

# REPO_ROOT is advisory. A script that runs inside the container reads a
# bind-mounted repository, where a different uid trips the dubious-ownership
# guard of git. Fall back to PROJECT_ROOT, so no script stops at startup.
if [[ -z "${REPO_ROOT:-}" ]]; then
  REPO_ROOT="$(git -C "$PROJECT_ROOT" rev-parse --show-toplevel 2>/dev/null || printf '%s' "$PROJECT_ROOT")"
fi
export REPO_ROOT

# Every image of this repository is published under 1 registry namespace.
IMAGE_REGISTRY_NAMESPACE="ghcr.io/gophersys"

# Both architectures have real users: an arm64 Mac and an amd64 Linux host.
# This is the policy default. There is no flag that makes `push` narrower.
: "${MULTI_ARCH_PLATFORMS:=linux/amd64,linux/arm64}"

if [[ -n "${IMAGE_NAME:-}" ]]; then
  IMAGE_REF="${IMAGE_REGISTRY_NAMESPACE}/${IMAGE_NAME}:latest"
fi

# Extra arguments for docker build. The runner layer threads its parent through
# BASE_IMAGE here. Declare the array only if the sourcing script did not.
if ! declare -p IMAGE_BUILD_ARGS >/dev/null 2>&1; then
  IMAGE_BUILD_ARGS=()
fi

# -------- logging --------
function log_info()  { printf '\033[0;36m[info]\033[0m  %s\n' "$*"; }
function log_warn()  { printf '\033[0;33m[warn]\033[0m  %s\n' "$*" >&2; }
function log_error() { printf '\033[0;31m[error]\033[0m %s\n' "$*" >&2; }

# -------- tool gate --------
# A missing tool is a failure, never a skip.
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

# Guard: docker and docker buildx must be present. A verb that acts on the
# whole set of images calls this alone, because the platform list is not the
# same for every image.
function require_buildx() {
  require_cmd docker
  if ! docker buildx version >/dev/null 2>&1; then
    log_error "docker buildx is not installed — multi-arch push is mandatory"
    exit 127
  fi
}

# Guard: buildx must also be able to build every platform that this image
# requires. A verb that pushes MUST call this first. There is no flag that
# makes the push single-arch. Multi-arch on push is policy, not preference.
#
# The guard fails closed in 4 conditions: the platform list is empty, buildx is
# absent, no builder is active, or the active builder cannot emulate 1 of the
# required platforms.
function require_buildx_and_multi_arch() {
  if [[ -z "${MULTI_ARCH_PLATFORMS:-}" ]]; then
    log_error "MULTI_ARCH_PLATFORMS is empty — the guard cannot enforce a platform"
    exit 1
  fi
  require_buildx
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

# -------- no EXIT trap, and that is deliberate --------
# The 8 scripts of this repository each carried the same cleanup block: a
# BG_PIDS array, an on_exit function that killed the pids, and `trap on_exit
# EXIT`. Nothing ever added a pid to BG_PIDS, and no script starts a background
# job. The block killed nothing.
#
# It was not free. On bash 3.2, which is the bash of macOS and the bash that
# runs these scripts on a developer host, `$?` is 0 when the EXIT trap starts
# after the shell aborts on an unbound variable. Measured on this repository:
# with the trap, a script that aborts on an unbound variable exits 0. Without
# the trap, it exits 1. The block turned a fatal abort into a reported success.
#
# A script that starts a background job must clean up its own job, and it must
# not add an EXIT trap that returns a status.

# -------- image verbs --------
function image_build() {
  require_cmd docker
  log_info "building ${IMAGE_REF} (native single-arch)"
  docker build "${IMAGE_BUILD_ARGS[@]+"${IMAGE_BUILD_ARGS[@]}"}" -t "${IMAGE_REF}" "$PROJECT_ROOT"
}

function image_build_multi_arch() {
  require_buildx_and_multi_arch
  log_info "buildx multi-arch (${MULTI_ARCH_PLATFORMS}) — no push"
  docker buildx build \
    --platform "${MULTI_ARCH_PLATFORMS}" \
    "${IMAGE_BUILD_ARGS[@]+"${IMAGE_BUILD_ARGS[@]}"}" \
    --tag "${IMAGE_REF}" \
    --load=false \
    "$PROJECT_ROOT"
}

function image_push() {
  require_buildx_and_multi_arch
  require_cmd git
  local short_sha image_ref_sha
  short_sha="$(git -C "$PROJECT_ROOT" rev-parse --short=7 HEAD 2>/dev/null || true)"
  if [[ -z "$short_sha" ]]; then
    log_error "cannot determine short SHA for tag; is $PROJECT_ROOT a git repo?"
    exit 1
  fi
  image_ref_sha="${IMAGE_REGISTRY_NAMESPACE}/${IMAGE_NAME}:${short_sha}"
  log_info "buildx multi-arch (${MULTI_ARCH_PLATFORMS}) + push to ${IMAGE_REF} and ${image_ref_sha}"
  docker buildx build \
    --platform "${MULTI_ARCH_PLATFORMS}" \
    "${IMAGE_BUILD_ARGS[@]+"${IMAGE_BUILD_ARGS[@]}"}" \
    --tag "${IMAGE_REF}" \
    --tag "${image_ref_sha}" \
    --push \
    "$PROJECT_ROOT"
}

function image_pull() {
  require_cmd docker
  log_info "pulling ${IMAGE_REF}"
  docker pull "${IMAGE_REF}"
}

function image_inspect() {
  require_cmd docker
  docker image inspect "${IMAGE_REF}"
}

# -------- usage --------
# This block is the specification of the per-image interface. An image that adds
# a verb adds its line through IMAGE_USAGE_COMMANDS.
function image_usage() {
  cat <<EOF
Usage: ./ctl.sh <command> [args...]

Image: ${IMAGE_REF}${IMAGE_USAGE_HEADER:-}

Commands:
  build              Build the image natively (single-arch, fast)
  build-multi-arch   buildx --platform ${MULTI_ARCH_PLATFORMS}, no push
  push               ENFORCED multi-arch buildx build + push
  pull               docker pull ${IMAGE_REF}
  inspect            docker image inspect ${IMAGE_REF}${IMAGE_USAGE_COMMANDS:-}
  help               Show this message
EOF
}

# -------- dispatcher --------
# A per-image ctl.sh that adds a verb handles that verb itself, then sends every
# other verb here.
function image_main() {
  : "${IMAGE_NAME:?_ctl/lib.sh: the sourcing ctl.sh must set IMAGE_NAME}"
  local cmd="${1:-help}"
  shift || true
  case "$cmd" in
    build)             image_build             "$@" ;;
    build-multi-arch)  image_build_multi_arch  "$@" ;;
    push)              image_push              "$@" ;;
    pull)              image_pull              "$@" ;;
    inspect)           image_inspect           "$@" ;;
    help|"")           image_usage ;;
    *)                 log_error "unknown command: '$cmd'"; image_usage; exit 1 ;;
  esac
}
