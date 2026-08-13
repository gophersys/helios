#!/bin/bash
# gophersys-standard control script: single entry point for humans and CI.
set -euo pipefail
cd "$(dirname "$0")"
cmd="${1:?usage: ctl.sh <test|vet|fmt|build>}"
case "$cmd" in
  test)
    (cd tools/densui && uv run --extra dev pytest -q && uv run --extra dev ruff check .)
    for f in demos/operator/build/*.js; do node --check "$f"; done
    node demos/operator/build/params.js | grep -q "^PASS" || { echo "params self-test failed" >&2; exit 1; }
    ;;
  vet) (cd tools/densui && uv run --extra dev ruff check .) ;;
  fmt) (cd tools/densui && uv run --extra dev ruff format --check .) ;;
  build) (cd demos/operator && python3 build/assemble.py "${@:2}") ;;
  *) echo "ctl.sh: unknown target: $cmd" >&2; exit 2 ;;
esac
