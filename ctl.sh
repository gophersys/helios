#!/bin/bash
# gophersys-standard control script: single entry point for humans and CI.
set -euo pipefail
cd "$(dirname "$0")"
cmd="${1:?usage: ctl.sh <test|vet|fmt|build>}"

# The three demo pages are build artifacts (gitignored), so every gate that
# MEASURES one has to build it first or it measures whatever the last run left
# on disk — and on a fresh checkout, nothing at all.
build_demos() {
  font="${UI_FONT:-}"
  if [ -z "$font" ]; then
    for c in "/Applications/Ableton Live 12 Suite.app/Contents/App-Resources/Fonts/AbletonSansSmall-Regular.ttf" \
             /usr/share/fonts/truetype/dejavu/DejaVuSans.ttf; do
      [ -f "$c" ] && font="$c" && break
    done
  fi
  [ -n "$font" ] || { echo "$cmd: no font found — set UI_FONT" >&2; exit 1; }
  if [[ "$font" == *AbletonSansSmall* ]]; then
    (cd demos/operator && python3 build/assemble.py)              # fidelity + drift guard
  else
    (cd demos/operator && python3 build/assemble.py --font "$font")
  fi
  # the blind demo: static render + battery at defaults
  (cd demos/telemetry && uv run --project ../../tools/ui python3 build/build.py)
  # the contract demo: drill session -> render tree state -> battery
  (cd demos/bench && uv run --project ../../tools/ui python3 build/build.py)
}

case "$cmd" in
  test)
    (cd tools/ui && uv run --extra dev pytest -q && uv run --extra dev ruff check .)
    for f in demos/operator/build/*.js; do node --check "$f"; done
    node demos/operator/build/params.js | grep -q "^PASS" || { echo "params self-test failed" >&2; exit 1; }
    ;;
  vet) (cd tools/ui && uv run --extra dev ruff check .) ;;
  fmt) (cd tools/ui && uv run --extra dev ruff format --check .) ;;
  build) (cd demos/operator && python3 build/assemble.py "${@:2}") ;;
  geometry)
    build_demos
    # the blind demo again at worst case: every value at its widest string
    (cd demos/telemetry && uv run --project ../../tools/ui python3 build/build.py --sweep)
    ;;
  score)
    # the craft scorecard: every registered predicate over the seeded corpus AND
    # the three demos. rc!=0 when a class misses its OWN seed (a check that
    # cannot fail is the defect) or a should-pass target carries a violation.
    build_demos >&2   # keeps this verb's stdout one parseable report, nothing hidden
    uv run --project tools/ui ui score --corpus corpus \
      demos/operator demos/telemetry demos/bench
    ;;
  test-review)
    # The review standard is org-central: cictl/review/review.sh reviews PRs on
    # the arc-review pool (wired in .github/workflows/on-pr.yml), and cictl
    # itself proves every guard via review_test.sh. Nothing to run per-repo.
    echo "test-review: consumed via on-pr.yml; guards proven in gophersys/cictl" ;;
  *) echo "ctl.sh: unknown target: $cmd" >&2; exit 2 ;;
esac
