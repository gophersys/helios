# 10 — The lifecycle state machine

The machine is defined ONCE in `state/fsm.json` (the authority). This document is the human-readable
projection — it never overrides the JSON. `current_state` in that file is the live position.

## States

```
init ──propose-charter──▶ charter_drafted ──ratify-charter──▶ charter_ratified
  ──propose-questionnaire──▶ product_decomposed
  ──open-decision──▶ decisions_open ──rule-decision──▶ (open? stay : decisions_ruled)
  ──plan──▶ planned ──advance──▶ (work left? building : done)
                building ──advance──▶ (work left? building : done) ──▶ done [TERMINAL]
```

| State | Meaning | The one move out |
|---|---|---|
| `init` | empty project, no charter | `/propose-charter` |
| `charter_drafted` | a charter exists, not yet ratified | `/propose-charter` (re-draft) or `/ratify-charter` |
| `charter_ratified` | the human froze the charter | `/propose-questionnaire` (decompose) |
| `product_decomposed` | work items exist under `init/product/` | `/propose-questionnaire` (more) · `/open-decision` · `/plan` |
| `decisions_open` | ≥1 unruled fork under `init/decisions/open/` | `/rule-decision` (until none remain) · `/open-decision` |
| `decisions_ruled` | every fork ruled (no open fork) | `/open-decision` (raise more) · `/plan` |
| `planned` | `init/plan/plan.md` exists, packages seeded | `/advance` |
| `building` | packages in flight | `/advance` (until none remain) |
| `done` | every package complete | — TERMINAL |

## How you choose the move (no judgement, just the table)

1. Read `current_state` (SessionStart injects it; `/state-show` prints it).
2. Find the transition rows whose `from` contains `current_state` — those are the legal moves.
3. Run the matching slash-command with a schema-valid payload. The command:
   - asserts the move is legal from the current state (`sv_assert_legal`),
   - asserts the **git guard** holds (`sv_assert_guard` — a real `git ls-files` check),
   - validates the payload against the JSON Schema,
   - writes the canonical artifact and seeds any markers,
   - advances `current_state` to the destination (which, for `rule-decision`/`advance`, is itself
     computed from git — `none-under init/decisions/open/` → `decisions_ruled`, etc.),
   - appends the audit record and prints the `fsm:` trailer.

## Guards are unforgeable

Each transition's guard is a **git predicate** over a tracked path. You cannot satisfy it with a
claim — only by producing the artifact and having it tracked/staged in git. The load-bearing one:
**`plan` requires `none-under init/decisions/open/`** — planning is impossible while any fork is
open, because the guard runs `git ls-files init/decisions/open/` and refuses on a non-empty result.
Likewise `advance` reaches `done` only when `git ls-files init/product/open/` is empty.

## One transition per command, idempotent re-runs

`/propose-questionnaire` records one work item per call (run it once per unit). `/open-decision`
records one fork per call. `/rule-decision` settles one fork (moving its file from `open/` to
`ruled/`). `/advance` completes one package (deleting its `open/` marker). Re-running a command
with the same payload overwrites the same artifact — safe and convergent.
