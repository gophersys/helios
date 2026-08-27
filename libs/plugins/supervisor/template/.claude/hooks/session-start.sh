#!/usr/bin/env bash
#
# session-start.sh — SessionStart hook (supervisor operating manual).
#
# Injects, into the agent's context at session start:
#   - its identity + the hard-interface rule (act ONLY through the typed slash-commands)
#   - the CURRENT FSM state and the ONE legal transition it may run next (read live from
#     state/fsm.json, so the agent is told exactly "you are here / do this one thing")
#   - the operating-manual instructions (instructions/*.md)
#
# Emits via hookSpecificOutput.additionalContext. Always exits 0 — a context injector must
# never block a session.
#
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_hooklib.sh
# shellcheck disable=SC1091
source "$SCRIPT_DIR/_hooklib.sh"

sv_read_input
PROJECT_DIR="$(sv_project_dir)"
FSM="$(sv_fsm)"

out=""
out+=$'# Supervisor — deterministic operating manual (you are the project-manager agent)\n\n'
out+=$'You are a DETERMINISTIC project manager. Your memory is git; your behavior is a finite '
out+=$'state machine. You do NOT free-form edit files or run arbitrary shell. You act ONLY by '
out+=$'running ONE typed slash-command per legal FSM transition. Every other tool is denied by '
out+=$'settings.json. The transition you run is decided by the current FSM state, not by your '
out+=$'judgement; guards are git predicates, so you cannot talk past a prerequisite — produce the '
out+=$'artifact and it becomes true, or it stays false.\n\n'

# --- the operating-manual instructions ---
INSTR_DIR="$PROJECT_DIR/.claude/instructions"
if [[ -d "$INSTR_DIR" ]]; then
  for f in "$INSTR_DIR"/*.md; do
    [[ -f "$f" ]] || continue
    out+="---"$'\n'
    out+="$(cat "$f")"
    out+=$'\n\n'
  done
fi

# --- the live FSM "you are here" ---
out+=$'---\n# You are here (live FSM state)\n\n'
if [[ -f "$FSM" ]] && command -v jq >/dev/null 2>&1; then
  cur="$(sv_current_state)"
  desc="$(jq -r --arg s "$cur" '(.states[] | select(.name==$s) | .description) // ""' "$FSM")"
  terminal="$(jq -r --arg s "$cur" '(.states[] | select(.name==$s) | .terminal) // false' "$FSM")"
  out+="current_state: **${cur}**"$'\n'
  [[ -n "$desc" ]] && out+="meaning: ${desc}"$'\n'
  out+=$'\n'
  if [[ "$terminal" == "true" ]]; then
    out+=$'This is a TERMINAL state — the lifecycle is finished. There is no transition to run.\n'
  else
    out+=$'The legal transition(s) from here (run the matching slash-command; the command validates '
    out+=$'the payload schema + the git guard, writes the canonical artifact, and advances state):\n\n'
    while IFS= read -r row; do
      [[ -n "$row" ]] || continue
      legal="$(printf '%s' "$row" | jq -r --arg s "$cur" '([.from[]] | index($s)) != null')"
      [[ "$legal" == "true" ]] || continue
      t="$(printf '%s' "$row" | jq -r '.transition')"
      cmd="$(printf '%s' "$row" | jq -r '.command')"
      art="$(printf '%s' "$row" | jq -r '.artifact')"
      gdesc="$(printf '%s' "$row" | jq -r '.guard.description')"
      out+="  - **${t}** → \`${cmd}\` (writes \`${art}\`; guard: ${gdesc})"$'\n'
    done < <(jq -c '.transitions[]' "$FSM")
    out+=$'\nIf unsure, run `/state-show` first — it prints exactly this, plus whether each guard is satisfied.\n'
  fi
else
  out+=$'(state/fsm.json not found or jq unavailable — run `/state-show` once the FSM is present.)\n'
fi

sv_emit_context "SessionStart" "$out"
exit 0
