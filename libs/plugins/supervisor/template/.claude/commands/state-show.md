---
description: Show the current FSM state and the ONE legal transition (read-only).
argument-hint: ""
allowed-tools: Bash(bash ./.claude/commands/state-show.sh:*)
---

Run the supervisor state inspector and report exactly what it prints — the current state and the single legal next transition. Do not infer or invent transitions; only what the FSM emits is real.

!`bash ./.claude/commands/state-show.sh`
