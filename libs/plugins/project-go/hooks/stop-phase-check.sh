#!/usr/bin/env bash
#
# stop-phase-check.sh — Stop hook (ADR-0020 AI instrumentation).
#
# When the agent tries to END its turn on a library it has been editing, run a FAST `phase-gate
# qa` subset for the touched lib(s); if it is not green, return a Stop-blocking decision so the
# agent cannot conclude "done" while a phase gate is red. This is the mechanical guarantee that
# the agent always carries a library to completion correctly — it cannot stop before qa is green.
#
# Bounded by a touched-lib guard (no touched lib → allow stop immediately) and by running only
# the cheap, deterministic qa dimensions (maintainability + no-shortcuts + cover-floor + vuln),
# NOT the host-bound integration/load/mutation lanes — those belong to the explicit phase-gate
# verb and CI, so the Stop hook never fires spuriously or hangs.
#
# Stop decision channel: {"decision":"block","reason": <failing dimensions>} blocks turn-end;
# absent/exit 0 allows it. Honors the stop_hook_active guard so a blocked-then-retried stop does
# not loop forever.
#
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_lib.sh
# shellcheck disable=SC1091
source "$SCRIPT_DIR/_lib.sh"

pg_read_input

# Avoid an infinite stop→block→stop loop: if we already blocked once this turn, allow the stop.
STOP_ACTIVE="$(pg_json '.stop_hook_active' 'false')"
[[ "$STOP_ACTIVE" == "true" ]] && exit 0

TOUCHED="$(pg_touched_libs 2>/dev/null || true)"
[[ -z "$TOUCHED" ]] && exit 0   # no library was being edited — nothing to gate; allow stop

command -v go >/dev/null 2>&1 || exit 0   # cannot gate without go — degrade open (CI is authoritative)

failing=""
while IFS= read -r lib; do
  [[ -n "$lib" ]] || continue
  root="$(pg_repo_root)"; lib_dir="$root/libs/go/$lib"
  [[ -f "$lib_dir/ctl.sh" ]] || continue

  libfail=""
  # The cheap, deterministic qa subset (no integration/load/mutation — those are CI + the verb).
  # maintainability: strict lint + hnslint + doc + cohesion.
  out="$( ( cd "$lib_dir" && bash ./ctl.sh maintainability ) 2>&1 || true )"
  printf '%s' "$out" | grep -qiE 'maintainability: OK' || libfail+="  - maintainability (lint/hnslint/cohesion) is RED"$'\n'
  # cover-floor: per-package floor.
  out="$( ( cd "$lib_dir" && bash ./ctl.sh cover-floor ) 2>&1 || true )"
  printf '%s' "$out" | grep -qiE 'cover-floor: (every production package|.* >= )' || libfail+="  - cover-floor: a production package is below the floor"$'\n'
  # no-shortcuts grep (ADR-0017): scan non-test bodies for stub/swallow/TODO tells.
  if grep -rnE 'panic\("(unimplemented|not implemented|TODO)|^\s*return nil, nil\s*$|//\s*(TODO|FIXME)\b' \
        "$lib_dir" --include='*.go' --exclude='*_test.go' >/dev/null 2>&1; then
    libfail+="  - no-shortcuts (ADR-0017): a stub/swallow/TODO remains in a non-test body"$'\n'
  fi
  # vuln (fast): govulncheck if present.
  if pg_have govulncheck >/dev/null; then
    out="$( ( cd "$lib_dir" && bash ./ctl.sh vuln ) 2>&1 || true )"
    printf '%s' "$out" | grep -qiE 'No vulnerabilities found|vuln: OK' || libfail+="  - vuln: a vulnerable dependency was found"$'\n'
  fi

  if [[ -n "$libfail" ]]; then
    failing+="libs/go/${lib}:"$'\n'"$libfail"
  fi
done <<< "$TOUCHED"

if [[ -z "$failing" ]]; then
  exit 0   # qa subset green for every touched lib — allow the stop
fi

reason="ADR-0020: you cannot end your turn — a library you edited is not past phase-gate qa. Fix the failing dimensions below, re-run \`bash ./ctl.sh phase-gate qa\` until green, then stop:"$'\n\n'"$failing"$'\n'"(This is the qa subset; the full gate also runs integration/load/mutate — run \`ctl.sh phase-gate all\`.)"

if command -v jq >/dev/null 2>&1; then
  jq -n --arg r "$reason" '{decision: "block", reason: $r}'
else
  esc="$(printf '%s' "$reason" | sed 's/\\/\\\\/g; s/"/\\"/g' | awk '{printf "%s\\n", $0}')"
  printf '{"decision":"block","reason":"%s"}' "$esc"
fi
exit 0
