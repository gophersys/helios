---
description: Record the human's answer to one questionnaire question. FSM self-loop in init.
argument-hint: '{"question":"<NN-slug>","answer":"..."}'
allowed-tools: Bash(bash ./.claude/commands/record-answer.sh:*)
---

You are performing the `record-answer` FSM transition: recording the human's answer to ONE questionnaire question. The single argument is a JSON object matching the `answer` schema: `question` is the question's filename stem under `init/product/questionnaire/` (e.g. `01-audience`) and `answer` is the answer text. The command writes `init/product/answers/<question>.md`, stages it, and prints the commit trailer. Run it once per answer; the FSM stays in `init`. When every question is answered, draft the charter from the interview via `/propose-charter`.

!`bash ./.claude/commands/record-answer.sh $ARGUMENTS`
