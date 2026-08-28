---
description: Record the human's ratification of the drafted charter. FSM transition into charter_ratified.
argument-hint: '{"ratified_by":"<name>","ratified_at":"<rfc3339>"}'
allowed-tools: Bash(bash ./.claude/commands/ratify-charter.sh:*)
---

You are performing the `ratify-charter` FSM transition. Ratification is the HUMAN's act — only run this when the human has explicitly approved the charter; do not self-ratify on the human's behalf. The single argument is a JSON object matching the `ratification` schema (who ratified, when). The command writes the `init/charter/.ratified` marker (whose git presence is the downstream guard), advances the state, and prints the commit trailer.

!`bash ./.claude/commands/ratify-charter.sh '$ARGUMENTS'`
