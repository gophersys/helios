# mktemp-gnu-template

phase:    intake
repo:     gophersys/eden
branch:   fix/mktemp-gnu-template
worktree: ~/code/.worktrees/eden-mktemp-gnu-template
pr:       -
attempt:  0/2

## Goal
`scripts/assert-no-skipped-tests.sh:22` calls `mktemp -t assert-no-skipped-tests` — BSD
syntax. GNU mktemp in the CI container rejects it ("too few X's in template"), so the
harness-conformance job has exited 1 before running a single Go test on every run since
2026-08-10 (proven from run 32007839673, line 382). When this is done, the gate runs
tests again on both its trigger paths (`harnesses/versions.env`, `libs/go/agentsession/**`),
and a regression test proves the failure mode cannot silently return.

## Plan
(pending phase 1)

## Proven
- `gh run view 32007839673 --log` line 382: `mktemp: too few X's in template
  'assert-no-skipped-tests'` then exit 1; harness install steps 1–7 succeeded first
  (discovery workflow wf_59ad5111, ledger agent + critic, 2026-08-18).

## Blocked
-

## Next
Phase 1: dev-planner.
