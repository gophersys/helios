# The craft scorecard — coverage and failures, never a verdict

`./ctl.sh score` runs every registered defect-class predicate over a corpus of
seeded pages AND over the three demos, and prints one JSON report:

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

## Should-pass targets

```
densui score --corpus corpus demos/operator demos/telemetry demos/bench
```

Every positional argument is a directory that must come out CLEAN: its
`panel.toml` supplies the `[probe]` config (with `page` naming the rendered
file) and its `[rules]`, and any violation of any class fails the run, named
with the target. Half the point of the scorecard is there: a corpus proves the
predicates can fire, the demos prove they are not firing on the work we ship.

The demo pages are build artifacts, so `./ctl.sh score` builds all three before
scoring them — a target that cannot be probed exits non-zero and names itself.
It is never skipped, because a target silently dropped reads exactly like a
target that passed.

A corpus seed must ALSO run the configuration production runs. `corpus/breathing`
declares `text_kinds = ["value"]` like the demos do, because a defect visible
only to element-box probing certifies a code path no panel uses.

## Measured today

| Class | Predicate |
|---|---|
| `overlap` | `densui.audit.check_overlaps` |
| `crowding` | `densui.audit.check_crowding` |
| `gap-law` | `densui.audit.check_gap_law` |
| `containment` | `densui.audit.check_containment` |
| `breathing` | `densui.audit.check_breathing` |
| `alignment` | `densui.audit.check_level` |
| `size-ratio` | `densui.audit.check_ratios` |
| `axis-sprawl` | `densui.audit.check_axis_budget` |
| `hit-pitch` | `densui.audit.check_hit_pitch` |
| `fractional-edges` | `densui.audit.check_integer_edges` |
| `font-identity` | `densui.audit.check_font_identity` |

`size-ratio` and `font-identity` are the two classes a target must DECLARE to be
scored on: the rows live in each panel.toml's `[ratio]` table, the face in its
`[font]` table, and `corpus/size-ratio` and `corpus/font-identity` are what
prove the predicates fire. A panel that declares neither contributes no
violation — which is why the seed, not a demo, is the evidence.

`padding-rhythm`, `component-anatomy` and `colour` are UNMEASURED — named in the
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
