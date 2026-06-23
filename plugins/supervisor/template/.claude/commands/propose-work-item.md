---
description: Decompose the ratified product into one work item. FSM transition into product_decomposed.
argument-hint: '{"id":"<slug>","title":"...","summary":"...","acceptance":["..."],"depends_on":["<slug>"]}'
allowed-tools: Bash(bash ./.claude/commands/propose-work-item.sh:*)
---

You are performing the `propose-work-item` FSM transition: decomposing the ratified charter into work items. Each invocation records ONE work item (run it once per unit). The single argument is a JSON object matching the `work-item` schema. The command writes `init/product/<id>.md`, advances the state, and prints the commit trailer. Repeat for each unit; the FSM stays in `product_decomposed` and lets you open decisions when the decomposition is complete.

!`bash ./.claude/commands/propose-work-item.sh '$ARGUMENTS'`
