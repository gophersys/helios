#!/usr/bin/env bash
#
# ctl.sh — control script for images-orchestrator
#
# Builds, pushes, pulls, and inspects the orchestrator image:
#   ghcr.io/gophersys/orchestrator
#
# Multi-arch policy:
#   - build             native single-arch (fast dev loop)
#   - build-multi-arch  explicit buildx multi-arch build, --load=false (no push)
#   - push              ENFORCED multi-arch via buildx --push
#
# Usage: ./ctl.sh <command> [args...]
#
set -Eeuo pipefail
IFS=$'\n\t'

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(git -C "$PROJECT_ROOT" rev-parse --show-toplevel)"
export REPO_ROOT

IMAGE_NAME="orchestrator"
IMAGE_REF="ghcr.io/gophersys/${IMAGE_NAME}:latest"
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

# -------- commands --------
function cmd_build() {
  require_cmd docker
  log_info "building ${IMAGE_REF} (native single-arch)"
  docker build -t "${IMAGE_REF}" "$PROJECT_ROOT"
}

function cmd_build_multi_arch() {
  require_buildx_and_multi_arch
  log_info "buildx multi-arch (${MULTI_ARCH_PLATFORMS}) — no push"
  docker buildx build \
    --platform "${MULTI_ARCH_PLATFORMS}" \
    --tag "${IMAGE_REF}" \
    --load=false \
    "$PROJECT_ROOT"
}

function cmd_push() {
  require_buildx_and_multi_arch
  require_cmd git
  local short_sha image_ref_sha
  short_sha="$(git -C "$PROJECT_ROOT" rev-parse --short=7 HEAD 2>/dev/null || true)"
  if [[ -z "$short_sha" ]]; then
    log_error "cannot determine short SHA for tag; is $PROJECT_ROOT a git repo?"
    exit 1
  fi
  image_ref_sha="ghcr.io/gophersys/${IMAGE_NAME}:${short_sha}"
  log_info "buildx multi-arch (${MULTI_ARCH_PLATFORMS}) + push to ${IMAGE_REF} and ${image_ref_sha}"
  docker buildx build \
    --platform "${MULTI_ARCH_PLATFORMS}" \
    --tag "${IMAGE_REF}" \
    --tag "${image_ref_sha}" \
    --push \
    "$PROJECT_ROOT"
}

function cmd_pull() {
  require_cmd docker
  log_info "pulling ${IMAGE_REF}"
  docker pull "${IMAGE_REF}"
}

function cmd_inspect() {
  require_cmd docker
  docker image inspect "${IMAGE_REF}"
}

# -------- usage --------
function usage() {
  cat <<EOF
Usage: ./ctl.sh <command> [args...]

Image: ${IMAGE_REF}

Commands:
  build              Build the image natively (single-arch, fast)
  build-multi-arch   buildx --platform ${MULTI_ARCH_PLATFORMS}, no push
  push               ENFORCED multi-arch buildx build + push
  pull               docker pull ${IMAGE_REF}
  inspect            docker image inspect ${IMAGE_REF}
  help               Show this message
EOF
}

# -------- dispatcher --------
function main() {
  local cmd="${1:-help}"
  shift || true
  case "$cmd" in
    build)             cmd_build             "$@" ;;
    build-multi-arch)  cmd_build_multi_arch  "$@" ;;
    push)              cmd_push              "$@" ;;
    pull)              cmd_pull              "$@" ;;
    inspect)           cmd_inspect           "$@" ;;
    help|"")           usage ;;
    *)                 log_error "unknown command: '$cmd'"; usage; exit 1 ;;
  esac
}

main "$@"
