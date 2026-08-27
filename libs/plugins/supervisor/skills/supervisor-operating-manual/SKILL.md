---
name: supervisor-operating-manual
description: The Eden supervisor's deterministic operating manual — how the LLM project-manager is made repeatable via a git-derived finite state machine, deny-by-default permissions, typed slash-commands per legal transition, and lifecycle gating hooks. Load when operating as the supervisor agent or wiring a supervisor AgentTemplate.
---

# Supervisor operating manual

The **supervisor** is an LLM project-manager made **deterministic**. Its determinism heart is four
mechanisms working together — none alone is enough:

1. **A finite state machine** (`state/fsm.json`). The project is always in one `current_state`; the
   FSM admits only a small fixed set of legal transitions from there. The lifecycle is:
   `init → charter_drafted → charter_ratified → product_decomposed → decisions_open →
   decisions_ruled → planned → building → done`.
2. **Hard interfaces** — the agent acts ONLY through one typed slash-command per transition
   (`state-show`, `propose-charter`, `ratify-charter`, `propose-questionnaire`, `open-decision`,
   `rule-decision`, `plan`, `advance`). Each validates its JSON payload against a schema, writes the
   artifact to its canonical git path, advances state, and prints a parseable `fsm:` commit trailer.
3. **Git as the only memory** — every fact is a tracked file; guards are **git predicates** (e.g.
   "no open forks" = `git ls-files init/decisions/open/` empty), so a prerequisite is true only when
   the artifact actually exists in git, unforgeable by prose. Resume = `git checkout` + re-read
   `state/fsm.json`.
4. **Gating hooks** — `settings.json` denies raw Write/Edit/Bash and allows only the command scripts
   + read-only git; four lifecycle hooks enforce it (SessionStart injects the live state; the two
   PreToolUse hooks deny out-of-interface tools and any commit whose `fsm:` trailer is not the legal
   transition; Stop blocks ending on a dirty tree or a dangling open fork).

## Where it lives

- The rendered operating manual: `template/.claude/` (settings.json, state/fsm.json,
  instructions/, commands/, hooks/, schemas/). An agent runs as the supervisor by being given this
  `.claude/` as its project configuration.
- The AgentTemplate that resolves to it: `AGENT-TEMPLATE.md` (Routing `Role:supervisor →
  {claude-code, opus-4.8}`, broad-but-clamped Grants, a long Budget, the SandboxSpec) — the data the
  orchestrator `TemplateStore` resolves to spawn a supervisor session.

## When you are the supervisor

Do exactly one thing per turn: read where you are (`/state-show`), run the one legal transition with
a schema-valid payload, hand the staged artifact + the printed `fsm:` trailer to the orchestrator to
commit, and leave a clean tree. Never free-form edit, never run ad-hoc shell, never skip the FSM.
The full prose is in `template/.claude/instructions/00..40`.
