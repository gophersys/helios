#!/usr/bin/env bash
#
# advance.sh — FSM transition `advance`: {planned|building} -> {building|done}. Marks ONE work
# package complete. Guard: a plan exists (init/plan/plan.md). Removes the package's
# init/product/open/<package> marker (the git delete that decrements work-remaining); the FSM
# destination is computed from whether any marker remains (none -> done, any -> building).
# Records the completion in the audit log, advances state, prints the trailer. Does NOT commit.
#
# Usage: advance.sh '<advance-json>'
#
# shellcheck shell=bash
# shellcheck source=_supervisor.sh
# shellcheck disable=SC1091
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/_supervisor.sh"
sv_require_jq

PAYLOAD="${*:-}"
[[ -n "$PAYLOAD" ]] || sv_die "advance requires a JSON advance payload (which package completed)."

TRANSITION="advance"

sv_assert_legal    "$TRANSITION"
sv_assert_guard    "$TRANSITION"
sv_validate_schema "advance" "$PAYLOAD"

pkg="$(printf '%s' "$PAYLOAD" | jq -r '.package')"
root="$(sv_project_dir)"
marker_rel="init/product/open/${pkg}"
marker_abs="$root/$marker_rel"

# The package must currently be open (tracked or staged), else this is a no-op error.
if ! sv_git_tracked "$marker_rel"; then
  sv_die "package '$pkg' is not an open work package (no tracked $marker_rel). Run /state-show to see remaining packages."
fi

# The git delete that decrements work-remaining.
if git -C "$root" ls-files --error-unmatch -- "$marker_rel" >/dev/null 2>&1; then
  git -C "$root" rm -q -- "$marker_rel" >/dev/null 2>&1 || { git -C "$root" rm -q --cached -- "$marker_rel" >/dev/null 2>&1 || true; rm -f "$marker_abs"; }
else
  git -C "$root" reset -q -- "$marker_rel" >/dev/null 2>&1 || true
  rm -f "$marker_abs"
fi

# The artifact this transition records is the FSM file itself (the completion is state movement
# plus the audit record; no new document is authored).
ARTIFACT="state/fsm.json"
printf 'package %s marked complete; %s removed\n' "$pkg" "$marker_rel"
sv_finish_transition "$TRANSITION" "$ARTIFACT" "$(printf '%s' "$PAYLOAD" | jq -r '.completed_by')" "package:$pkg"
