#!/usr/bin/env bash
set -Eeuo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

case "${1:-help}" in
  check|test)
    exec bash "$root/.ctl/test.sh"
    ;;
  configure|status)
    exec node "$root/.ctl/secrets.mjs" "$1"
    ;;
  *)
    echo "Usage: ctl.sh <check|configure|status|test>" >&2
    exit 2
    ;;
esac
