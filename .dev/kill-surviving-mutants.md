# kill-surviving-mutants

phase:    red
repo:     gophersys/libs
branch:   test/kill-surviving-mutants
worktree: ~/code/.worktrees/libs-kill-mutants
pr:       -
attempt:  1/2

## Goal
Kill every surviving StrykerJS mutant in libs/typescript (primitives, scale,
theme, visualization) by writing the missing tests, so eden's substrate
mutate gate passes and the eden submodule bumps (#38/#86, eden #10) unblock.
Mateo decided 2026-08-18: fix the mutants, do not lower the floor.

## Plan
1. RED: run `bash ctl.sh mutate` in each of the 4 projects at origin/main —
   record every surviving mutant (file, line, mutator). This is the failure
   proof; mutation work inverts the red convention: red = survivors > floor.
2. GREEN: dev-test-author agents, one per project (disjoint dirs), write tests
   that kill the survivors. Tests only — no source edits; an equivalent mutant
   is ESCALATED, never silenced by a source change in this branch.
3. Gates: per-project `bash ctl.sh mutate` (floor holds), then the full
   per-project verbs the repo requires, then libs root validate.
4. Coordination: agents session works libs in parallel (their harness program).
   Ownership contract: scratchpad/agents-program/libs-ownership.md — this
   branch claims libs/typescript/** only; rebase on them, never the reverse.

## Proven
- (pending) mutate baseline logs: scratchpad/mutate-baseline-{project}.log

## Blocked
- Nothing. Baseline running in background (task bpanaeprt).

## Next
Read the 4 baseline logs; extract the survivor table; fan out test authors.
