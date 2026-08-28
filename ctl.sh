#!/usr/bin/env bash
set -Eeuo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

usage() {
  cat <<'USAGE'
Usage: ./ctl.sh <verb> [arguments]

  up                 Start the Eden devcontainer
  shell              Open a shell in the Eden devcontainer
  exec -- <command>  Run a command in the Eden devcontainer
  down               Remove the Eden devcontainer
  run <project> <target> [-- ...]
                     Run one Nx target in the devcontainer
  image <verb> ...   Manage base/cloud images
  status             Show the consolidated repository state
USAGE
}

require_devcontainer() {
  command -v devcontainer >/dev/null 2>&1 || {
    echo "missing devcontainer CLI" >&2
    exit 127
  }
}

case "${1:-help}" in
  up)
    require_devcontainer
    exec devcontainer up --workspace-folder "$root"
    ;;
  shell)
    require_devcontainer
    exec devcontainer exec --workspace-folder "$root" zsh
    ;;
  exec)
    require_devcontainer
    shift
    [[ "${1:-}" == "--" ]] && shift
    [[ $# -gt 0 ]] || { usage >&2; exit 2; }
    exec devcontainer exec --workspace-folder "$root" "$@"
    ;;
  down)
    require_devcontainer
    command -v docker >/dev/null 2>&1 || {
      echo "missing docker CLI" >&2
      exit 127
    }
    docker ps --all --quiet --filter "label=devcontainer.local_folder=$root" |
      while IFS= read -r container_id; do
        [[ -n "$container_id" ]] && docker rm --force "$container_id" >/dev/null
      done
    ;;
  run)
    shift
    [[ $# -ge 2 ]] || { usage >&2; exit 2; }
    exec "$root/ctl.sh" exec -- yarn nx run "$1:$2" "${@:3}"
    ;;
  image)
    shift
    exec bash "$root/.devcontainer/ctl.sh" "$@"
    ;;
  status)
    git -C "$root" status --short --branch
    ;;
  help|-h|--help)
    usage
    ;;
  *)
    usage >&2
    exit 2
    ;;
esac
