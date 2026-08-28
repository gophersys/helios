---
name: plan-feature
description: Decompose a feature request into an ordered, file-level work plan with specialist agent handoffs. The entry point for "I want to add X".
argument-hint: "<feature description>"
---

# /plan-feature

Spawn the `planner` agent (`.claude/agents/planner.md`) to produce a structured plan for the feature.

## How to invoke

Pass the user's request verbatim. Don't paraphrase — the planner needs the original wording to ask the right clarifying questions.

If the request is one sentence, ask the user for:
- The motivation (why now?)
- Any constraints (existing data, deadline, integration with X?)

If it's a paragraph, hand it straight to the planner.

## What you get back

A structured plan with:
- Summary
- Scope (apps, knowledge files, rules in play)
- Open questions
- Ordered steps with owning agent + file paths
- Cross-cutting touchpoints (auth, audit, three envs, Prisma flow, knowledge updates)
- Acceptance criteria

## Then what

For each step in the plan, spawn the named specialist agent with that step's scope. Run steps in the order the plan specifies; parallel steps go in one batch.

After all steps land, run the plan's acceptance commands and report.

## Don't

- Don't start writing code before the plan is approved by the user.
- Don't let the planner skip the cross-cutting checklist. Auth, audit, three envs, Prisma flow, and knowledge updates are non-negotiable.
- Don't merge steps to "save time" — the planner's ordering exists for a reason.
