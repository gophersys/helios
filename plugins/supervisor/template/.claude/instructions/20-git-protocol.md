# 20 — Git protocol: git is the only memory

The supervisor keeps **no hidden state**. Everything it knows is a tracked file under the canonical
paths. This is what makes a run resumable and auditable: a fresh session reconstructs the entire
project position by reading git.

## Canonical paths (the one home for each concept)

| Concept | Path | Written by |
|---|---|---|
| Charter | `init/charter/charter.md` | `/propose-charter` |
| Charter ratification marker | `init/charter/.ratified` | `/ratify-charter` |
| Work items (decomposed product) | `init/product/<id>.md` | `/propose-questionnaire` |
| Open work-package markers | `init/product/open/<package>` | `/plan` (seeded), `/advance` (removed) |
| Open decisions (unruled forks) | `init/decisions/open/<id>.md` | `/open-decision` |
| Ruled decisions | `init/decisions/ruled/<id>.md` | `/rule-decision` |
| Implementation plan | `init/plan/plan.md` | `/plan` |
| FSM state | `state/fsm.json` | every transition (advances `current_state`) |
| Audit trail | `audit/log.ndjson` | every transition (append-only) |

## The clean-tree rule

The working tree is **clean between transitions**. A transition is atomic from the FSM's view: the
command writes the artifact + advances state in the working tree, the orchestrator commits it, and
the tree returns to clean. The Stop hook BLOCKS you from ending a turn on a dirty tree — because a
dirty tree means the on-disk state and the committed state disagree, which breaks resume-by-checkout.

You do **not** commit. The orchestrator (the parent loop / the human) reviews the staged change and
commits it with the `fsm:` trailer the command printed. The `gate-commit` hook re-derives that
trailer from git and denies any commit whose trailer is not the legal transition — so even the
commit is verified, not trusted.

## Resume = checkout + re-read state

To resume an interrupted run: `git checkout` the branch, then re-read `state/fsm.json`'s
`current_state` (the SessionStart hook does this for you). The FSM tells you the one legal move; the
guards tell you (from git) what is already done. There is nothing to remember across sessions that is
not in git.

## The commit trailer grammar

Every transition commit carries exactly one line:

```
fsm: <from_state> -> <to_state> / <transition> / <artifact> / <guard_id>
```

Example: `fsm: decisions_open -> decisions_ruled / rule-decision / init/decisions/ruled/storage-engine.md / decision-open`

This is machine-parseable (the `gate-commit` hook parses it) and human-auditable (it reads like a
sentence). It is the join between the audit log, the FSM, and the git history.
