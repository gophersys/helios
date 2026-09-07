#!/usr/bin/env bash
set -Eeuo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
case "${1:-}" in
  check) exec node "$root/.ctl/check.mjs" ;;
  *) echo "Usage: ctl.sh check" >&2; exit 2 ;;
esac
