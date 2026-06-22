---
description: Raise an unruled fork (an open decision) the human must settle. FSM transition into decisions_open.
argument-hint: '{"id":"<slug>","question":"...","context":"...","options":[{"name":"A","tradeoffs":"..."},{"name":"B","tradeoffs":"..."}],"affects":["<work-item-id>"]}'
allowed-tools: Bash(bash ./.claude/commands/open-decision.sh:*)
---

You are performing the `open-decision` FSM transition: recording one unruled fork. Eden's rule is one concept, one home — unruled forks go to `init/decisions/open/`, never into prose. The single argument is a JSON object matching the `decision` schema (a decidable question and at least two options with tradeoffs). The command writes `init/decisions/open/<id>.md`, advances the state to `decisions_open`, and prints the commit trailer. An open decision BLOCKS planning until every fork is ruled (the unforgeable `git ls-files init/decisions/open/` guard).

!`bash ./.claude/commands/open-decision.sh $ARGUMENTS`
