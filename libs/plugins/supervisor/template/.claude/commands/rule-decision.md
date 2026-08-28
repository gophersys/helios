---
description: Settle one open fork — choose an option and record the rationale. FSM transition that clears the fork.
argument-hint: '{"id":"<open-decision-slug>","chosen":"<option-name>","rationale":"...","ruled_by":"<name>"}'
allowed-tools: Bash(bash ./.claude/commands/rule-decision.sh:*)
---

You are performing the `rule-decision` FSM transition: settling one open decision. Ruling a fork is a HUMAN's call — record the human's chosen option and rationale, do not invent the verdict. The single argument is a JSON object matching the `ruling` schema. The command MOVES `init/decisions/open/<id>.md` to `init/decisions/ruled/<id>.md` (the git move that flips the `no open forks` guard), advances the state, and prints the commit trailer. When this was the last open fork, the FSM moves to `decisions_ruled` and planning is unlocked; otherwise it stays in `decisions_open` — the destination is computed from git, not asserted.

!`bash ./.claude/commands/rule-decision.sh '$ARGUMENTS'`
