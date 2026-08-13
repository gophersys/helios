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
  geometry)
    font="${DENSUI_FONT:-}"
    if [ -z "$font" ]; then
      for c in "/Applications/Ableton Live 12 Suite.app/Contents/App-Resources/Fonts/AbletonSansSmall-Regular.ttf" \
               /usr/share/fonts/truetype/dejavu/DejaVuSans.ttf; do
        [ -f "$c" ] && font="$c" && break
      done
    fi
    [ -n "$font" ] || { echo "geometry: no font found — set DENSUI_FONT" >&2; exit 1; }
    if [[ "$font" == *AbletonSansSmall* ]]; then
      (cd demos/operator && python3 build/assemble.py)              # fidelity + drift guard
    else
      (cd demos/operator && python3 build/assemble.py --font "$font")
    fi
    ;;
  *) echo "ctl.sh: unknown target: $cmd" >&2; exit 2 ;;
esac
