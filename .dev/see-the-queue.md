# see-the-queue

phase:    fix — audit returned 8 findings
repo:     gophersys/infrastructure
branch:   ci/see-the-queue
worktree: ~/code/.worktrees/infra-queue
pr:       172
attempt:  1/2

## Goal

`timeout-minutes` counts execution only, never queue, so a job that waits an hour
for a runner and then runs 30 seconds looks healthy. Add a verb that can see the
wait, and gate on it.

## THIS FILE WAS MISSING

A 10-agent audit found no `.dev/*.md` for this feature at all, so the artefact the
process names as the source of truth did not exist and every claim lived in commit
bodies and one PR comment. Written now, from the audit's measurements.

## What is proven, and it reproduced under audit

```
9 fixture cases            rc=0
ctl.sh validate            rc=0
live gophersys/infrastructure   rc=1, names the 1114 s job as contention=1105s
same 90-job arc-org window: OLD rule fires on 61, NEW on 3 (927 s, 65 s, 53 s)
the CI step demonstrably ran on the real runner
```

Both run-level anchoring refutations reproduce to the second: `run.created_at` is
stale after a re-run (4353 s of phantom queue against a job that waited 6 s), and
`run.run_started_at` counts a dependency's run time. `job.created_at` is correct.

The `[20, 28]` percentile band is exact, and its two boundaries fail for genuinely
DIFFERENT reasons — below it the warm-start cluster leaks into the floor, above it
the floor climbs into the contended cluster. Neither discriminator is redundant.

## Audit findings — 8

**F1 (HIGH). The headline change is unguarded.** The repo-wide dispatch floor is
the whole point of `79d7fe3`. Reverting line 254 to a per-workflow floor
(`JOBS_SAMPLE` -> `JOBS_WINDOW`) keeps **all 9 cases green and CI green**, while
measurably changing the live answer (floor 9s -> 7s on a sample of 18 instead of
107). Same class as everything else found tonight: the deliverable ships with
nothing asserting it.

**F2 (HIGH). A "known limitation" test is actively blocking an improvement.**
`known_limitation_quartile_rises_when_most_jobs_wait` is the SOLE assertion that
forbids `ALARM_FACTOR=2` — and K=2 makes the verb correctly alarm on the very
window that case calls a limitation. Measured sweep:

```
K=1  rc=1 (5 failures)     K=3  rc=0  <- shipped
K=2  rc=1 (1 failure — the known_limitation case)
K=20 rc=0                  K=21 rc=1 (estimator_is_a_floor_not_a_median)
```

A case that documents a weakness must not be the thing that PREVENTS its fix.

**F3 (MEDIUM). The corridor is documented twice, the two disagree, and both are
false.** The test file says K from 1.4 to 20.8; commit `f579be5` says 1.4 to 27.
Measured by sweeping only `ALARM_FACTOR` in the shipped script: the admissible
band is **[3, 20]**. K=1.4 is red and K=27 is red. So the factor is pinned at
exactly its shipped value from below — it is not "free inside a corridor".

**F4 (MEDIUM). A commit claims fixtures it never committed.** `02274f3` says "Two
fixtures cover the boundary, a zero-second execution, a skipped job and a job
still in flight." `git show --name-status` shows it added `ctl.sh` and
`verify-runner-queue.sh` and **no fixture**. Across all 9 fixtures on the branch
tip: `skipped=0`, `null-ts=0`. Both branches of the verdict loop have zero
automated coverage.

**F5 (MEDIUM). The help text describes the rule that was deleted.** `ctl.sh:201`
still says "Assert no job waited for a runner longer than it ran" — the rule
`79d7fe3` removed for firing falsely on 17 of 36 jobs. The shipped rule is
`queue > floor * 3`, and `long-queue-long-execution.json` exists precisely to
prove the old wording wrong.

**F6 (MEDIUM). No state file.** Fixed by this file.

**F7 (LOW). The floor rank is not the "nearest rank" its comment claims.**
`rank = n*p/100 + 1` biases the floor UP by one order statistic, which makes the
alarm less sensitive. On `mostly-contended.json`: shipped rank 6 -> floor 410s;
nearest rank 5 -> floor 400s.

**F8 (LOW).** On the fixture path the no-verdict message names the default LIVE
workflow and advises "widen the window with the third argument" — both meaningless
when reading a fixture.

## Blocked

PR #172 is HELD, and not on these findings: the `pr-review` agent hit its 2-round
limit and reported **pass without reviewing**, while both existing approvals
predate the entire floor rule. See task #60.

## Deliberately NOT in this change

- Per-runner-label floors (arc-org 9s vs arc-review 7s). Needs a decision.
- The org-wide floor. GitHub exposes no org-level runs or jobs endpoint.

## Next

Test author: F1 (guard the repo-wide floor), F2 (make the limitation case stop
forbidding its own fix), F4 (the two missing fixture shapes).
Then implementer: F3, F5, F7, F8.


## Phase 2 round 2 — F2 and F3 closed, F1 proven UNCLOSABLE at the fixture layer

```
cases=11 assertion-failures=0   rc=0
ctl.sh validate                 rc=0
```

### F1 — NOT a missing fixture. A SEAM property, and it was proven, not asserted.

The test author reproduced my mutation, then instrumented a copy with `cmp` at the
fixture branch and ran every fixture through it:

```
dispatch-only         PROBE identical rows=36
floor-not-median      PROBE identical rows=21
warm-and-cold-starts  PROBE identical rows=25
uniform-saturation    PROBE identical rows=34
mostly-contended      PROBE identical rows=20
```

`cp "$JOBS_SAMPLE" "$JOBS_WINDOW"` is **unconditional**, so the mutation swaps two
BYTE-IDENTICAL files. **No fixture content can distinguish them — this is closed
under all possible fixtures, not merely the ones written.** The live split is on
`run.path` from the RUNS endpoint, and a jobs-API response carries no run path, so
a fixture cannot express "these jobs belong to another workflow" at all.

It declined to write a case that can never pass, and declined to add a dead
fixture. That is the correct outcome and a better one than a green test.

**SEAM NEEDED — implementer's change:**

```
preferred  the fixture carries the runs index beside the jobs:
             {"runs":[{"id":..,"path":".github/workflows/validate.yml"}], "jobs":[..]}
           and the fixture path splits on run_id -> path. Mirrors live exactly and
           keeps run.path as the single split key, preserving the one-extractor rule.
cheaper    read `.workflow_name` per job and match the workflow argument on the
           fixture path. Works, but fixture and live would then split on DIFFERENT
           fields — the exact divergence the one-extractor rule exists to stop.
```

### F2 — CLOSED, and the fix generalises

The case now asserts the MECHANISM and never the sensitivity:

```
asserted      the floor is dragged into the contended cluster (computed BEFORE the
              factor, so true for every K)
asserted      the SMALLEST wait escapes — at a 410s floor the alarm is >= 410s for
              any K >= 1, so a 400s wait is invisible whatever K is
NOT asserted  how many of the other 15 are caught. That is K's business.
```

Band moved **[3,20] -> [2,20]**, and the lower bound is now held by false-fire
evidence instead of by a limitation note. It also checked the same trap on the
OTHER axis: at p=0/10/19 the limitation case fails, but the warm-start case fails
at all of those too, so it is never a sole veto there either.

### F3 — CLOSED, proven by mutation rather than by arrival

Both fixtures were green on arrival (the behaviour existed, it was untested), so
each was proven by breaking the code:

```
M1 skipped into the floor sample   -> floor 0s, 16 false fires, rc=1
M2 skipped given a verdict         -> skipped=8 / checked=16 absent
M3 in-flight out of the sample     -> floor 470s, exit 0 on a saturated window
M4 in-flight given a verdict       -> pending=12 / checked=8 absent
```

Four mutants, four different assertions killing them.

### The corridor is corrected

Both old figures were arithmetic on one fixture rather than a sweep. The header now
records the measured bands — `FLOOR_PERCENTILE [20,28]`, `ALARM_FACTOR [2,20]` —
says "sweep, do not derive", and notes that the `f579be5` commit body stands wrong
in the log and cannot be corrected.

## DECIDED — K=2 must be excluded on dispatch-budget grounds

The test author raised this and asked rather than assuming. **Add the 16s cold
start.**

The measured worst no-contention queue on this pool is **16s**. The warm-and-cold
fixture tops out at 12s, so nothing currently rejects K=2 on budget grounds — and
K=2 gives an 18s alarm, **2 seconds of margin** over the worst real dispatch. That
is not a margin; one slightly slower cold start false-fires, which is the original
defect returning by a different route.

K=3 gives 27s against a 16s worst dispatch — 11s of headroom. The fixture should
express the pool as measured, not as convenient, and the band should be constrained
by the dispatch budget rather than by which fixtures happen to exist.

## Next

Implementer FIRST (the seam is a source change): the runs-index seam for F1, plus
F5 (help text still describes the deleted rule), F7 (the rank is not "nearest
rank"), F8 (the fixture-path message names the live workflow).
Then test author: the F1 case once the seam exists, and the 16s cold start.


## Phase 3 — the seam is built and the mutant is KILLABLE (`ebed9f4`, `1dee494`)

The red was the surviving mutant itself: the implementer reproduced
`JOBS_SAMPLE -> JOBS_WINDOW` independently and got `cases=11
assertion-failures=0`. Items 2-4 had no test at all; their red was the measured
falsehood.

### The seam, and it preserves the one-extractor rule

A fixture may now carry `{"runs":[{"id":..,"path":..}], "jobs":[..]}`. The fixture
path selects jobs by `run_id` through **the literally identical `case` pattern the
live path uses**, and the field list is SHARED — `RUN_FIELDS='[ .id, .path ] |
@tsv'` feeds both `.workflow_runs[]` (live) and `(.runs // [])[]` (fixture). Only
the envelope key differs, which the two APIs force. `run.path` stays the single
split key.

**Backward compatibility:** `(.runs // [])` yields an empty index for a bare
jobs-API response, which takes the old `cp` branch. All 11 existing fixtures work
unmodified — and the header now records what a bare fixture CAN prove (floor
arithmetic, the rule, the verdict loop, skipped/pending) and what it CANNOT (which
jobs feed which sample).

**The demonstration — the one-word revert is now killable:**

```
scratch fixture: 8 pr-review jobs waiting 30-37s + 20 validate jobs served in 3s
SHIPPED   floor  3s — sample of 28   alarm  9s   rc=1, 8 flagged
MUTANT    floor 31s — sample of  8   alarm 93s   rc=0, 0 flagged
```

Same fixture with `validate.yml` as the second argument: same repo-wide floor over
28 jobs, window of 20, rc=0 — **the split moves the window without moving the
floor**, which is the property the whole design rests on. Scratch fixture deleted.

### The rank formula changed, and THE BAND MOVED — swept, not assumed

`ceil(n*p/100)`, clamped to >= 1. The old `n*p/100 + 1` sits one order statistic
higher **only when `n*p/100` is a whole number**, and it biases the floor UP, which
makes a saturation detector less sensitive. The reasoning recorded in the file is
the part worth keeping: the false-fire margin is `ALARM_FACTOR`'s job and the
header prices it explicitly (16s worst dispatch vs a 27s alarm). **A second margin
hidden inside the estimator is a constant nobody can read, and it scales with n.**

```
FLOOR_PERCENTILE band:  [20, 28]  ->  [21, 28]
NEW   p=20 rc=1 (3 failures)   p=21..28 rc=0   p=29 rc=1
OLD   p=19 rc=1 (3 failures)   p=20..28 rc=0   p=29 rc=1
```

Only the lower bound moved, by one, and the cause is exact: at p=20 on the 25-job
warm-and-cold fixture, `25*20/100 = 5` precisely, so the new rank 5 lands on the
LAST warm start (7s) and `estimator_clears_the_warm_start_cluster` correctly
rejects it. Shipped 25 keeps 4 below and 3 above. The "never a sole veto" property
survives — at p=20 the warm-start case fails alongside `known_limitation`.

`mostly-contended` floor 410s -> **400s**, exactly the figure the audit computed
for a true nearest rank.

### The live answer did not move, and it said WHY

```
bash scripts/verify-runner-queue.sh gophersys/infrastructure   rc=1
  dispatch floor 7s — the lower quartile of a sample of 103 job(s), every workflow
  worst: 31531318733 review queue=1114s contention=1107s exec=151s
```

Byte-identical to the pre-change baseline it captured first, because
`103*25/100 = 25.75` is not a whole number so both formulas agree at rank 26.
Confirmed independently against the cached sample.

### The help text names no constant, deliberately

`ctl.sh:201` now reads "Assert no job waited far past the measured dispatch
floor". It names **no number**: `ALARM_FACTOR` may move inside its band, and a `3`
copied into `ctl.sh` would go stale exactly the way the deleted sentence did.

## Two things for the test author

**The header's band is now off by one.** `test-verify-runner-queue.sh:69-72`
records `[20, 28]` and "19 and below"; it must be `[21, 28]` and "20 and below".
Nothing is red today because the suite is green at the shipped 25 — the number is
simply false now, which is the exact defect class this branch exists to close.

**A malformed-fixture hole, flagged before it bites:** a `run_id` in a fixture's
jobs that the runs index does NOT carry is silently dropped from the window while
staying in the sample. No committed fixture exercises it. Worth knowing while
writing the F1 case.

## Next

Test author: the F1 case (the seam now exists), the `[21, 28]` header correction,
the 16s cold start I decided, and a judgement on the malformed-fixture hole.
