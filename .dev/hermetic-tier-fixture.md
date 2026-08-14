# hermetic-tier-fixture

phase:    wait
repo:     gophersys/libs
branch:   fix/hermetic-tier-fixture
worktree: ~/code/.worktrees/libs-hermetic-tier-fixture
pr:       16
attempt:  0/2

## Goal
libs `main` (da1f1ca) is a FALSE-RED on the on-push tier: the real CI gating works, but one test
in `.ci/ctl_test.sh` — `t_a_fault_inside_the_producer_fails_the_tier` — fails only on the
ephemeral runner because the tier-test fixture is not hermetic to the outer job's `NX_BASE`. When
this lands, libs `main` goes green on the on-push tier for a real reason, and the tier-test suite
passes regardless of the outer `NX_BASE`.

## Plan — APPROVED, and CONFIRMED by measurement
The planted-fault line (ctl_test.sh:185) `git fetch --quiet origin "$NX_BASE"` emits different
bytes per value: `origin/main` → `does not appear to be a git repository` (missing remote);
`origin/main~1` → `invalid refspec 'origin/main~1'` (`~1` rejected first). The test guards on the
first string. `run_verb` set only PATH/EDEN_TEST_GATED_LOG/BASH_ENV, so the push tier's
`NX_BASE=origin/main~1` leaked in and the guard failed (rc=128). The PR tier uses `origin/main`,
so the PR gate passes either way — the fix must be proven locally under `origin/main~1`.

FIX (one token, in the TEST file): add `NX_BASE=origin/main` to `run_verb`'s env prefix. Assertions
untouched; `.ci/ctl.sh` and the workflow NX_BASE values untouched.

## Proven
- ROOT CAUSE controlled: re-ran both commits' on-push — e82815e (pre-#14) SUCCESS, da1f1ca (#14)
  FAILURE x2 → caused by #14's range; `.ci/ctl_test.sh` is the SOLE `test suite failed` entry on
  da1f1ca (rest are phase-2 discrimination counter-stimuli).
- Real gate is NOT broken: `cictl@v0.1.0` (runner's pinned version) `affected --base origin/main~1`
  → rc=0. Test-harness hermeticity bug only.
- RED reproduced (orchestrator, base-runner, unfixed): `NX_BASE=origin/main~1 bash .ci/ctl_test.sh
  t_a_fault_inside_the_producer_fails_the_tier` → `invalid refspec 'origin/main~1'`, rc=128,
  SUITE_RC=1 — byte-for-byte the runner.
- GREEN (dev-test-author + dev-verifier both reproduced, base-runner): the one-token fix (commit
  1bb9a94, only .ci/ctl_test.sh, +2/-1) → full suite under `origin/main~1` SUITE_RC=0 (15/15 hold,
  15/15 proven-able-to-fail); single test under `origin/main` = 0; under UNSET = 0; shellcheck clean.
- LOAD-BEARING (dev-verifier break-test): revert the token on an in-container copy → the exact
  original false-red returns (`invalid refspec`, rc=128, FAIL). Guards byte-identical to da1f1ca.
- dev-verifier VERDICT: PASS — survives refutation; no weakened assertion, no masked failure, no
  scope creep, state file honest.
- Partial `bash .ci/ctl.sh validate` (base-runner, stopped as redundant) was green in progress:
  template_test.sh ok, ctl_test.sh passed, verb-conservation phase 1 passing project-by-project.

## Blocked
Nothing. Blocks no queued merge (only libs #15 targets main, held on Mateo/#37).

## Next
Push, open PR. Note in the PR body: the PR gate runs `NX_BASE=origin/main` and so CANNOT reproduce
this fix; the `origin/main~1` proof is the local base-runner run above. Then phase 6 (wait) → phase
8 (merge, on Mateo's authority — 4 conditions).
