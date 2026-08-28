#!/usr/bin/env bash
set -Eeuo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
images=(base cloud)

usage() {
  echo "Usage: .devcontainer/ctl.sh <list|build|push|pull|inspect|verify-published|mirror-buildkit> [image] [arguments]"
}

image_command() {
  local verb="$1" image="${2:-}"
  shift 2 || true
  case "$image" in
    base|cloud) exec bash "$root/$image/ctl.sh" "$verb" "$@" ;;
    *) echo "image must be base or cloud" >&2; exit 2 ;;
  esac
}

case "${1:-help}" in
  list)
    printf '%s\n' "${images[@]}" buildkit
    ;;
  build|push|pull|inspect|verify-published)
    verb="$1"
    shift
    image_command "$verb" "$@"
    ;;
  mirror-buildkit)
    shift
    exec bash "$root/.ci/mirror-buildkit.sh" "$@"
    ;;
  help|-h|--help)
    usage
    ;;
  *)
    usage >&2
    exit 2
    ;;
esac
