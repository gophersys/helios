---
description: Draft (or re-draft) the product charter from a JSON payload. FSM transition into charter_drafted.
argument-hint: '{"title":"...","problem":"...","outcomes":["..."],"non_goals":["..."],"constraints":["..."],"stakeholders":["..."]}'
allowed-tools: Bash(bash ./.claude/commands/propose-charter.sh:*)
---

You are performing the `propose-charter` FSM transition. The single argument is a JSON object matching the `charter` schema. Pass it verbatim to the script. Do not write the charter file yourself — the command writes it to its canonical git path, validates the schema and the FSM guard, advances the state, and prints the commit trailer. If the script rejects the payload, fix the payload and re-run; never bypass it.

!`bash ./.claude/commands/propose-charter.sh '$ARGUMENTS'`
