#!/usr/bin/env bash
#
# rule-decision.sh — FSM transition `rule-decision`: decisions_open -> {decisions_ruled |
# decisions_open}. Settles ONE open fork. Guard: at least one open decision exists. It MOVES
# init/decisions/open/<id>.md to init/decisions/ruled/<id>.md (the git move that flips the
# unforgeable 'no open forks' guard), writes the ruling alongside, advances state to the
# git-derived destination, audits, prints the trailer. Does NOT commit.
#
# Usage: rule-decision.sh '<ruling-json>'
#
# shellcheck shell=bash
# shellcheck source=_supervisor.sh
# shellcheck disable=SC1091
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/_supervisor.sh"
sv_require_jq

PAYLOAD="${*:-}"
[[ -n "$PAYLOAD" ]] || sv_die "rule-decision requires a JSON ruling payload."

TRANSITION="rule-decision"

sv_assert_legal    "$TRANSITION"
sv_assert_guard    "$TRANSITION"
sv_validate_schema "ruling" "$PAYLOAD"

id="$(printf '%s' "$PAYLOAD" | jq -r '.id')"
root="$(sv_project_dir)"
open_rel="init/decisions/open/${id}.md"
open_abs="$root/$open_rel"
[[ -f "$open_abs" ]] || sv_die "no open decision '$id' at $open_rel — run /state-show and /open-decision first, or check the id."

# Cross-check the chosen option name against the open decision's declared options (read the
# fenced json front matter we wrote at open time).
chosen="$(printf '%s' "$PAYLOAD" | jq -r '.chosen')"
open_json="$(awk '/^```json$/{f=1;next} /^```$/{f=0} f' "$open_abs")"
if [[ -n "$open_json" ]]; then
  valid="$(printf '%s' "$open_json" | jq -r --arg c "$chosen" '([.options[].name] | index($c)) != null' 2>/dev/null || printf 'false')"
  [[ "$valid" == "true" ]] || sv_die "chosen option '$chosen' is not one of decision '$id' options ($(printf '%s' "$open_json" | jq -rc '[.options[].name]'))."
fi

ARTIFACT="init/decisions/ruled/${id}.md"

body="$(printf '%s' "$PAYLOAD" | jq -r '
  "# Ruling — \(.id)\n\n**Chosen:** \(.chosen)\n\n**Ruled by:** \(.ruled_by)\n\n## Rationale\n\n\(.rationale)\n"
')"
sv_write_markdown_artifact "$ARTIFACT" "$PAYLOAD" "$body"

# The git move that flips the guard: stage the new ruled file and remove the open one from the
# index AND the working tree. We use `git mv` semantics via add+rm so the open path is no longer
# tracked-or-staged (none-under becomes true once this is the last fork).
git -C "$root" add -- "$ARTIFACT" 2>/dev/null || true
if git -C "$root" ls-files --error-unmatch -- "$open_rel" >/dev/null 2>&1; then
  git -C "$root" rm -q -- "$open_rel" >/dev/null 2>&1 || { git -C "$root" rm -q --cached -- "$open_rel" >/dev/null 2>&1 || true; rm -f "$open_abs"; }
else
  # open file was staged-but-new (not yet in HEAD): unstage + delete from the tree.
  git -C "$root" reset -q -- "$open_rel" >/dev/null 2>&1 || true
  rm -f "$open_abs"
fi

printf 'ruled decision %s -> %s (chosen: %s); open fork cleared\n' "$id" "$ARTIFACT" "$chosen"
sv_finish_transition "$TRANSITION" "$ARTIFACT" "$(printf '%s' "$PAYLOAD" | jq -r '.ruled_by')" "chose:$chosen"
