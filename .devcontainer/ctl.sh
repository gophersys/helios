#!/usr/bin/env bash
set -Eeuo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

case "${1:-help}" in
  test)
    exec bash "$root/test-entrypoint.sh"
    ;;
  *)
    echo "Usage: ctl.sh test" >&2
    exit 2
    ;;
esac
