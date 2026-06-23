---
description: Generate the product-scoping questionnaire (one question per file). FSM self-loop in init.
argument-hint: '{"questions":[{"id":"<slug>","prompt":"A focused product question?"}, ...]}'
allowed-tools: Bash(bash ./.claude/commands/propose-questionnaire.sh:*)
---

You are performing the `propose-questionnaire` FSM transition: turning the user's DESCRIBE brief into the product-scoping interview. The single argument is a JSON object with a `questions` array (matching the `questionnaire` schema); each entry is one focused question with a stable `id` slug and a `prompt`. The command writes each question to `init/product/questionnaire/<NN>-<id>.md` (the wizard renders the file body verbatim as the question), stages them, and prints the commit trailer. This runs ONCE to produce the whole questionnaire; the FSM stays in `init` so the human can answer each question (recorded via `/record-answer`) before you draft the charter.

!`bash ./.claude/commands/propose-questionnaire.sh $ARGUMENTS`
