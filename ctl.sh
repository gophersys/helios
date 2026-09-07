#!/usr/bin/env bash
set -Eeuo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
case "${1:-}" in
  check) exec bash "$root/.ctl/check.sh" ;;
  setup) exec node "$root/.ctl/setup.mjs" ;;
  *) echo "Usage: ctl.sh <check|setup>" >&2; exit 2 ;;
esac
