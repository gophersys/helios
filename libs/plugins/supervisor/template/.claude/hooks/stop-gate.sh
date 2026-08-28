#!/usr/bin/env bash
#
# stop-gate.sh — Stop hook (the clean-tree / no-dangling-transition wall).
#
# The supervisor's memory IS git, and the contract is: the working tree is CLEAN between
# transitions (a transition either completes and is committed, or it is not started). This hook
# blocks the agent from ending its turn while:
#   (a) the working tree is dirty — an artifact was written by a command but not yet committed by
#       the orchestrator, OR an out-of-band edit leaked in; either way the recorded git state and
#       the on-disk state disagree, which breaks resume-by-checkout. Stop is blocked until the
#       tree is clean (the orchestrator commits the pending transition, or the change is reverted).
#   (b) the FSM is mid-flow in a state that demands a decision be ruled before progress
#       (`decisions_open`) — a turn should not end leaving a fork dangling silently; the agent is
#       reminded to rule it (or that the human must).
#
# Honors stop_hook_active to avoid an infinite block→stop loop. Block channel:
# {"decision":"block","reason":...}; allow: exit 0.
#
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_hooklib.sh
# shellcheck disable=SC1091
source "$SCRIPT_DIR/_hooklib.sh"

sv_read_input

STOP_ACTIVE="$(sv_json '.stop_hook_active' 'false')"
[[ "$STOP_ACTIVE" == "true" ]] && exit 0

# (a) dirty tree → block.
if sv_tree_dirty; then
  root="$(sv_project_dir)"
  dirty="$(git -C "$root" status --porcelain 2>/dev/null | head -20)"
  sv_block_stop "Supervisor cannot end the turn: the working tree is DIRTY. Git is the supervisor's only memory, and a transition must leave a CLEAN tree (it either completes and is committed, or it is not started). Resolve the pending change before stopping:
${dirty}

If you just ran a transition command, the artifact is staged/written and awaiting the orchestrator's review+commit — that is expected; hand off and let the commit land (the gate-commit hook will verify its fsm: trailer). If the change is stray, revert it. Do not end mid-transition."
fi

# (b) dangling open fork in decisions_open → remind (block once).
cur="$(sv_current_state)"
if [[ "$cur" == "decisions_open" ]]; then
  forks="$(sv_open_forks)"
  if [[ "${forks:-0}" -gt 0 ]]; then
    sv_block_stop "Supervisor cannot end the turn cleanly: the FSM is in 'decisions_open' with ${forks} unruled fork(s) under init/decisions/open/. A fork left open BLOCKS planning (the unforgeable no-open-forks guard). Rule each via /rule-decision (the human's chosen option + rationale), or explicitly confirm with the human that the fork stays open pending their input — then the next turn resumes from git. Run /state-show to list them."
  fi
fi

exit 0
