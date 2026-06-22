# 30 — Hard interfaces: act only through the typed commands

The supervisor's determinism depends on it having a **small, fixed set of legal actions**. You act
ONLY through the typed slash-commands. Everything else is denied by `settings.json` and re-denied
with an explanation by the `gate-tool` hook.

## The complete action surface

| Command | Transition | Payload schema | What it does |
|---|---|---|---|
| `/state-show` | (read-only) | — | prints `current_state` + the one legal transition + each guard's status |
| `/propose-charter` | `propose-charter` | `charter` | drafts/redrafts `init/charter/charter.md` |
| `/ratify-charter` | `ratify-charter` | `ratification` | writes `init/charter/.ratified` (the human's freeze) |
| `/propose-questionnaire` | `propose-questionnaire` | `work-item` | records one work item under `init/product/` |
| `/open-decision` | `open-decision` | `decision` | raises one unruled fork under `init/decisions/open/` |
| `/rule-decision` | `rule-decision` | `ruling` | moves a fork `open/` → `ruled/` (settles it) |
| `/plan` | `plan` | `plan` | writes `init/plan/plan.md`, seeds work-package markers |
| `/advance` | `advance` | `advance` | completes one package; FSM recomputes `building`/`done` |

## What you may NOT do

- **No `Write` / `Edit` / `MultiEdit`.** You never author or modify a file directly. The command
  is the only writer of a canonical artifact, so the schema and the path are always enforced.
- **No ad-hoc `Bash`.** The only shell you may run is a command script (above) or a read-only git
  verb (`git status` / `ls-files` / `log` / `diff` / `show`) to inspect state. No `git add`,
  `commit`, `push`, `rm`, `reset`, `mv` by hand — the commands stage what they must; the
  orchestrator commits.
- **No skipping the FSM.** You may not run a command for a transition that is illegal from the
  current state (the command refuses), nor fabricate a guard's prerequisite (the guard reads git).
- **No self-ratifying / self-ruling on the human's behalf.** `/ratify-charter` and `/rule-decision`
  record a HUMAN's decision. Only run them once the human has chosen; carry their verdict and
  rationale verbatim.

## Why this shape

An LLM is a powerful but non-deterministic engine. Bolting it to a fixed action set + a git-derived
FSM + schema-validated payloads converts it into a repeatable process: the same git state always
admits the same legal moves, the same payload always writes the same artifact, and every move is
audited and gate-verified. The hard interface is the cage that makes the project manager
trustworthy.
