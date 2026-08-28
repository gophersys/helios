#!/usr/bin/env bash
#
# state-show.sh — read-only FSM inspector. Prints the current state and the ONE legal
# transition the agent may run next (the transition whose `from` contains current_state and
# whose guard is satisfied). It mutates nothing. This is the agent's "you are here".
#
# shellcheck shell=bash
# shellcheck source=_supervisor.sh
# shellcheck disable=SC1091
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/_supervisor.sh"

sv_require_jq

cur="$(sv_current_state)"
terminal="$(sv_state_terminal "$cur")"

printf '═══ supervisor FSM ═══\n'
printf 'current_state: %s\n' "$cur"
desc="$(jq -r --arg s "$cur" '(.states[] | select(.name==$s) | .description) // ""' "$(sv_fsm_path)")"
[[ -n "$desc" ]] && printf 'meaning: %s\n' "$desc"

if [[ "$terminal" == "true" ]]; then
  printf '\nThis is a TERMINAL state. The lifecycle is finished; there is no further transition.\n'
  exit 0
fi

printf '\nlegal transition(s) from here (each runs its own typed slash-command):\n'
# A transition is legal-from-here when current_state is in its `from`. We additionally report
# whether its git guard is currently SATISFIED, so the agent sees what it must produce first.
printf '%s' "$(jq -c '.transitions[]' "$(sv_fsm_path)")" | jq -c '.' "$(sv_fsm_path)" >/dev/null 2>&1 || true

found=0
while IFS= read -r row; do
  [[ -n "$row" ]] || continue
  legal="$(printf '%s' "$row" | jq -r --arg s "$cur" '([.from[]] | index($s)) != null')"
  [[ "$legal" == "true" ]] || continue
  found=1
  t="$(printf '%s' "$row" | jq -r '.transition')"
  cmd="$(printf '%s' "$row" | jq -r '.command')"
  artifact="$(printf '%s' "$row" | jq -r '.artifact')"
  schema="$(printf '%s' "$row" | jq -r '.schema')"
  gpred="$(printf '%s' "$row" | jq -r '.guard.git_predicate')"
  gpath="$(printf '%s' "$row" | jq -r '.guard.path')"
  gdesc="$(printf '%s' "$row" | jq -r '.guard.description')"
  if sv_eval_predicate "$gpred" "$gpath" 2>/dev/null; then gstate='SATISFIED'; else gstate='NOT YET — produce/stage the prerequisite first'; fi
  printf '  • %s   (command: %s)\n' "$t" "$cmd"
  printf '      writes artifact: %s   (schema: %s)\n' "$artifact" "$schema"
  printf '      guard: %s [%s %s] -> %s\n' "$gdesc" "$gpred" "$gpath" "$gstate"
done < <(jq -c '.transitions[]' "$(sv_fsm_path)")

[[ "$found" -eq 1 ]] || printf '  (none — fsm.json declares no transition from %s; this is a misconfiguration)\n' "$cur"
