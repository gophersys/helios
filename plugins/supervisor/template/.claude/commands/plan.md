---
description: Bind work items to ordered work packages. FSM transition into planned (requires NO open forks).
argument-hint: '{"packages":[{"id":"<slug>","work_items":["<item-id>"],"order":0,"budget":{"max_cost_micros":0,"max_turns":0}}]}'
allowed-tools: Bash(bash ./.claude/commands/plan.sh:*)
---

You are performing the `plan` FSM transition: producing the implementation plan. This transition's guard is the unforgeable `no open forks` predicate — it reads `git ls-files init/decisions/open/` and refuses to plan while any fork is open. The single argument is a JSON object matching the `plan` schema (ordered packages, each binding one or more work-item ids). The command writes `init/plan/plan.md`, seeds one `init/product/open/<package>` marker per package (these are the `advance` transition's work-remaining tokens), advances the state to `planned`, and prints the commit trailer.

!`bash ./.claude/commands/plan.sh '$ARGUMENTS'`
