#!/usr/bin/env bash
set -Eeuo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
case "${1:-}" in
  check|review|status|sync) exec node "$root/.ctl/main.mjs" "$1" ;;
  *) echo "Usage: ctl.sh <check|review|status|sync>" >&2; exit 2 ;;
esac
