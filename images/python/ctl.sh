#!/usr/bin/env bash
#
# ctl.sh — control script for images-python
#
# Builds, pushes, pulls, and inspects the base image:
#   ghcr.io/gophersys/base
#
# Usage: ./ctl.sh <command> [args...]
#
set -Eeuo pipefail
IFS=$'\n\t'

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC2034  # REPO_ROOT exposed for future cmd_* helpers
REPO_ROOT="$(git -C "$PROJECT_ROOT" rev-parse --show-toplevel)"

IMAGE_NAME="python"
IMAGE_REF="ghcr.io/gophersys/${IMAGE_NAME}:latest"

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

# -------- commands --------
function cmd_build() {
  require_cmd docker
  log_info "building ${IMAGE_REF}"
  docker build -t "${IMAGE_REF}" "$PROJECT_ROOT"
}

function cmd_push() {
  require_cmd docker
  log_info "pushing ${IMAGE_REF}"
  docker push "${IMAGE_REF}"
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
  build     Build the image from ./Dockerfile
  push      Push the image to the registry
  pull      Pull the image from the registry
  inspect   Run docker image inspect on the local image
  help      Show this message
EOF
}

# -------- dispatcher --------
function main() {
  local cmd="${1:-help}"
  shift || true
  case "$cmd" in
    build)    cmd_build    "$@" ;;
    push)     cmd_push     "$@" ;;
    pull)     cmd_pull     "$@" ;;
    inspect)  cmd_inspect  "$@" ;;
    help|"")  usage ;;
    *)        log_error "unknown command: '$cmd'"; usage; exit 1 ;;
  esac
}

main "$@"
