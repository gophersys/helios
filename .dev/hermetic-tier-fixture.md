# hermetic-tier-fixture

phase:    plan
repo:     gophersys/libs
branch:   fix/hermetic-tier-fixture
worktree: ~/code/.worktrees/libs-hermetic-tier-fixture
pr:       -
attempt:  0/2

## Goal
libs `main` (da1f1ca) is RED on the on-push tier, and it is a FALSE-RED: the actual CI
gating works, but one test in `.ci/ctl_test.sh` — `t_a_fault_inside_the_producer_fails_the_tier`
— fails only on the ephemeral GitHub Actions runner. The test harness is not hermetic to the
outer job's git environment. When this lands, libs `main` goes green on the on-push tier for a
real reason, and the tier test suite passes regardless of the outer `NX_BASE` / checkout shape.

## Plan
(to be produced by dev-planner, then approved here)

## Proven
Established across three prior investigation firings (evidence in task #76):

- CONTROL: re-ran both commits' on-push in the current environment — e82815e (pre-#14) SUCCESS,
  da1f1ca (#14 merge) FAILURE x2. Deterministic by commit, not a flake. → caused by the #14 range.
- #14's diff is ONLY `.ci/ctl.sh` + `.ci/ctl_test.sh` (git diff --stat e82815e da1f1ca). The
  go/errors machinery, go_in_lib, the verb-conservation harness and baseline are byte-identical.
- The ONE genuine failure is `t_a_fault_inside_the_producer_fails_the_tier` in `.ci/ctl_test.sh`
  → "test suite failed: .ci/ctl_test.sh" → the `pr tier` job fails. The verb-conservation
  "verbs moved" and `missing required tool(s)` / `FAIL build` lines are phase-2 DISCRIMINATION
  scenarios (counter-stimuli meant to fail); nearly all show `ok`.
- The real `affected` command is NOT broken: installed `cictl@v0.1.0` (the runner's pinned
  version, .devcontainer/runner/Dockerfile:29) and ran `cictl affected -C <libs> --base
  origin/main~1` → rc=0, empty, no stderr. NOT a cictl bug, NOT version skew (v0.1.0 cmdAffected
  is byte-identical to HEAD).
- The failing run's OUT for that test = ONLY `[info] affected-gate-fast: … (base=origin/main~1)`,
  RC=128 — the stub's expected fault message `does not appear to be a git repository` never
  appeared.

## Leading hypothesis (for the planner to CONFIRM or REFUTE — I have been wrong 3x on this red)
The test harness does not control `NX_BASE`. `grep NX_BASE .ci/ctl_test.sh` shows it appears
ONLY in the two mutation awk programs — `run_verb` and `new_fixture` never set/unset it. So:
- On the CI PUSH tier, the job env sets `NX_BASE=origin/main~1`, which LEAKS into the fixture's
  producer (that is why OUT shows base=origin/main~1).
- In the devcontainer (local test run) `NX_BASE` is unset → the fixture's `.ci/ctl.sh` defaults
  it to `origin/main`.
- The fixture is a fresh `git init` with no commits and no `origin` remote; the fixture comment
  (ctl_test.sh ~L340) states the assumption "on main, with an origin it can fetch and whose main
  is HEAD." The ephemeral runner is a DETACHED HEAD with no fetchable origin/main, and the
  leaked `NX_BASE` differs, so a git command faults (rc=128) before the controlled stub-fault.

IMPORTANT tier asymmetry: the PR tier sets `NX_BASE=origin/${{ github.base_ref }}` = origin/main
(on-pr.yml), but the PUSH tier sets `NX_BASE=origin/main~1` (on-push). So this test likely
PASSES on the PR gate and fails ONLY on post-merge push. => THE PR GATE ALONE CANNOT PROVE THIS
FIX. The red must be reproduced locally with `NX_BASE=origin/main~1` (and, if needed, a detached
HEAD), proven red, then proven green after the harness is made hermetic.

## Fix direction (not yet the plan)
Make the tier-test fixture hermetic to the outer git environment, as the verb-conservation
harness already is (`env -i` in its capture). The harness must CONTROL `NX_BASE` for the fixture
(set it to a value the fixture's own git repo satisfies, or construct a self-contained origin the
fixture can fetch) so the test is deterministic regardless of the outer job's NX_BASE and checkout
shape. Do NOT weaken the assertion to "any non-zero rc" — the test's intent (a specific producer
fault reaches the log, and the tier does not declare green over an unseen failure) is correct.

## Blocked
Nothing. main is red but blocks no queued merge (only libs #15 targets main, held on Mateo/#37).

## Next
dev-planner: confirm/refute the NX_BASE-leak hypothesis by inspection, and produce the plan —
the exact fixture change, the local reproduction that proves red (NX_BASE=origin/main~1), and how
green is proven under BOTH NX_BASE values. Ownership: `.ci/ctl_test.sh` is a TEST file →
dev-test-author owns the change; no non-test production code is expected to change.
