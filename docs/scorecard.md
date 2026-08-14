# The craft scorecard — coverage and failures, never a verdict

`./ctl.sh score` runs every registered defect-class predicate over a corpus of
seeded pages and prints one JSON report:

```
{"classes": {"<class>": {"measured": bool, "violations": [...], "seed_caught": bool|null}},
 "failures": [...]}
```

Those two top-level keys are the whole vocabulary. There is no field for
"looks human", "reads as generated", or "passes" — `docs/eyes.md` governs, and
no predicate in this repository can support such a claim. The scorecard reports
what is MEASURED, what VIOLATED, and nothing else.

## The three properties it exists to hold

1. **A class with no predicate reports UNMEASURED**, a sentinel object rather
   than a string, and is never readable as clean. Zero violations from a check
   that never ran is the exact lie this repository has already shipped once:
   `demos/telemetry/panel.toml` declared `[ratio]` rows that nothing executed.
2. **A registry row naming a symbol that does not exist is a failure.**
   `densui.score.REGISTRY` holds dotted symbol names, and a test resolves every
   one of them — a believed check that runs nothing cannot survive the suite.
3. **A predicate that misses its own seeded defect fails the run.** Each
   measured class owns `corpus/<class>/` — `page.html` with exactly ONE
   deliberate defect of that class, `panel.toml` with the `[probe]` selectors,
   and `TELL.md` naming the defect. If the predicate stays silent on its own
   seed, `densui score` exits non-zero: a check that cannot fail is the defect.

## Measured today

| Class | Predicate |
|---|---|
| `overlap` | `densui.audit.check_overlaps` |
| `crowding` | `densui.audit.check_crowding` |
| `gap-law` | `densui.audit.check_gap_law` |
| `containment` | `densui.audit.check_containment` |
| `breathing` | `densui.audit.check_breathing` |
| `alignment` | `densui.audit.check_level` |

`size-ratio`, `padding-rhythm`, `axis-sprawl`, `hit-pitch`, `fractional-edges`,
`font-identity`, `component-anatomy` and `colour` are UNMEASURED — named in the
registry so the gap is visible, with no predicate claimed. `REGISTRY` is the
source of truth; when a class flips to measured, its predicate, its corpus seed
and this table move in the same commit.

## Adding a class

Add the row to `REGISTRY` with its dotted predicate symbol and the adapter that
feeds it probe output, then add `corpus/<class>/` seeded with one defect of that
class and run `./ctl.sh score`. A seed whose class stays silent is a bug in the
page or in the predicate — never in the tolerance. Seeds carry no `[rules]`
override for the same reason: a defect that only trips a loosened rule proves
nothing about the check that ships.
