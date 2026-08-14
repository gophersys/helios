# hermetic-tier-fixture

phase:    red
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

## Plan — APPROVED (dev-planner CONFIRMED the hypothesis by direct measurement; orchestrator approved 2026-08-14)
Root cause CONFIRMED. The planted-fault line (ctl_test.sh:185) `git fetch --quiet origin "$NX_BASE"`
emits DIFFERENT bytes per NX_BASE value:
- `origin/main`    → `fatal: 'origin' does not appear to be a git repository`  (missing remote)
- `origin/main~1`  → `fatal: invalid refspec 'origin/main~1'`                   (`~1` rejected FIRST)
The test guards on `does not appear to be a git repository` (ctl_test.sh:633). `run_verb`
(ctl_test.sh:497) sets only PATH/EDEN_TEST_GATED_LOG/BASH_ENV, so the outer job's NX_BASE leaks in
(fixture `ctl.sh:44` keeps `${NX_BASE:-origin/main}`). On-push sets origin/main~1 → guard fails at
rc=128 (today's red). On-pr/devcontainer use origin/main/unset → pass. Sole variable = the leaked
NX_BASE. NOT detached-HEAD, NOT absent-origin.

THE FIX (one token, in the TEST file `.ci/ctl_test.sh`): add `NX_BASE=origin/main` to `run_verb`'s
env prefix (line 497), beside PATH/EDEN_TEST_GATED_LOG/BASH_ENV, with a one-line comment (the
fixture is hermetic to the outer NX_BASE as it already is to PATH; origin/main is a valid refspec
so the planted fetch fails at the missing remote — the intended fault — under any outer value).
Do NOT weaken the assertion. Do NOT touch .ci/ctl.sh, the mutation programs, or the workflow
NX_BASE values. dev-test-author owns this; NO dev-implementer (no source file to change).

## Proven
(added to the prior evidence)
- RED REPRODUCED by the orchestrator in `ghcr.io/gophersys/base-runner:e0c6bc5` (bash 5.2, cictl
  present) against the CURRENT unfixed worktree:
  `docker run --rm --platform linux/amd64 -v <wt>:/w -w /w base-runner bash -c 'git config --global
  --add safe.directory "*"; NX_BASE=origin/main~1 bash .ci/ctl_test.sh
  t_a_fault_inside_the_producer_fails_the_tier'`
  → OUTPUT: `fatal: invalid refspec 'origin/main~1'`, `no failing command ran inside the producer …
  (rc=128)`, `FAIL t_a_fault_inside_the_producer_fails_the_tier`, SUITE_RC=1. Byte-for-byte the
  runner's failure. THE RED IS PROVEN, for the right reason.
- Proof env verified: base:latest lacks cictl (runner-layer only, #20) → MUST use base-runner.

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
