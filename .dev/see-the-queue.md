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
