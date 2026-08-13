# cictl-swallow

phase:    fix
repo:     gophersys/libs
branch:   fix/cictl-swallow
worktree: ~/code/.worktrees/libs-cictl-swallow
pr:       -
attempt:  2/2

## Goal

`.ci/ctl.sh` reports a clean pass when `cictl` is absent, over libraries it never
looked at. Make the gate fail loudly instead, so a missing tool can never again be
reported as "no affected projects".

## The defect, PROVEN 2026-08-12 — do not re-derive

`.ci/ctl.sh:74`:

```sh
mapfile -t projects < <(affected_projects)
```

`affected_projects` opens with `require_cmd cictl`, whose failure path is
`exit 127`. **Process substitution is a SUBSHELL**, so that exit kills only the
subshell. `mapfile` reads an empty stream, and the caller logs
"no affected projects — clean no-op" and returns 0.

Measured on the same worktree, same base:

```
without cictl:  [error] missing required tool(s): cictl
                no affected projects for base 'origin/main' — clean no-op   rc=0
with cictl:     affected = go/objectstorage, go/secrets, go/workspaceprovider
                                                                            rc=1
```

The PR gate reported PASS over 3 real libraries, one of them RED.

## Why this is bigger than a missing binary

The same swallow hits ANY failure of `cictl affected`, not only an absent tool:
a bad base ref, a shallow clone, a git error. Today CI survives only because the
runner image happens to carry `cictl`. Nothing asserts that.

## Plan

APPROVED (self, under delegated authority, 2026-08-13).

The fix must go where it cannot be repeated. Two candidate shapes:

1. Run the tool check in the CALLER's own shell, before the substitution.
2. Do not read `affected_projects` through a process substitution at all —
   capture to a variable, check the status, then split.

Prefer whichever makes the swallow structurally impossible rather than merely
absent at this one call site. If other process substitutions in this file have
the same shape, they are in scope: the class is the deliverable, not the line.

## Deliberately NOT in this change

- Task #16, rolling `.ci` into the other repos. This must land FIRST, or the
  defect ships to every one of them.
- The runner image's `cictl` presence. That it happens to be there is luck, not a
  guarantee, but asserting it is a different change.

## Proven

Phase 2 — RED. `bash .ci/ctl_test.sh` -> rc=1, `5 failure(s) across both phases`.
The suite has two phases: phase 1 asserts behaviour, phase 2 asserts each test can
FAIL under a counter-stimulus. 4 red in phase 1; test 3 red in phase 2.

Its discrimination was proven from BOTH sides, in throwaway copies:
- correct oracle (capture, check status, split) -> rc=0, 5 of 5 proven able to fail
- LAZY oracle ("an empty listing is a failure") -> rc=1, tests 3 and 4 FAIL

That second one is what makes this suite good. It refuses the over-fix as firmly
as the under-fix, so the change cannot become "always fail".

Phase 3 — GREEN. `run_phase_gate_over_affected` now captures the listing, reads
the status, then splits:

```sh
listing="$(affected_projects)" || status=$?
if [[ "$status" -ne 0 ]]; then
  log_error "cictl affected failed (exit $status) for base '${NX_BASE}'; the affected set is unknown, so nothing was gated"
  return "$status"
fi
[[ -z "$listing" ]] || mapfile -t projects <<<"$listing"
```

The `[[ -z "$listing" ]] ||` guard is LOAD-BEARING: `<<<""` yields one empty
element, which would take a genuinely empty affected set out of the
"no affected projects" arm and break test 3.

`.ci/ctl.sh` now holds ZERO process substitutions.

All 5 tests green in both phases. `shellcheck -S style .ci/ctl.sh` rc=0.
Root `ctl_test.sh` rc=0 (10 hold, 10 of 10 proven able to fail).
`verb_conservation_test.sh` rc=0 (17 records, 3 mutants caught).

The class fix demonstrated on all 3 tier verbs, cictl genuinely absent:

```
affected-gate-fast       rc=127   cictl affected failed (exit 127) ... nothing was gated
affected-gate-substrate  rc=127   identical
gate-all                 rc=127   identical
```

All three fail, all three NAME the tool, none makes an empty-set claim.

## Blocked

Nothing blocking.

### CORRECTION — an arm64 claim I wrote here was FALSE

This section previously said `ghcr.io/gophersys/base:latest` "has no arm64 build,
so it cannot run on this Apple Silicon host at all", and concluded that "a
developer on Apple Silicon cannot run this repository's own gate locally... worth
carrying into the arm64 decision."

**The conclusion is false and I aimed it at a real architecture decision.** The
image is amd64, is already local, and runs here under emulation. Measured by the
verifier:

```
docker image inspect ghcr.io/gophersys/base:latest --format '{{.Architecture}}/{{.Os}}'
  -> amd64/linux
bash ./ctl.sh validate  in that image   -> rc=0, all 6 shell suites green
bash go/_ctl/lib_test.sh                -> rc=0, 17 test(s) hold
```

The premise ("no arm64 manifest") is probably true. The conclusion drawn from it
was not, and it is exactly the kind of plausible-sounding claim that gets carried
into a decision unchecked. I took it from an agent report without running it.

Also corrected: the earlier text said "One neighbour UNVERIFIED". In the ad-hoc
ubuntu image TWO suites failed — `lib_test.sh` and `vulnerability_test.sh`, both
for a missing tool. Both are GREEN in the real base image.

### CORRECTION — the defect narrative overstated the exposure

This file said "Today CI survives only because the runner image happens to carry
`cictl`. Nothing asserts that." **Not true for 2 of the 4 tiers.** In `on-pr.yml`
and `on-push.yml`, `ci-drift` runs FIRST, and `cmd_ci_drift` calls
`require_cmd cictl` in the CALLER's own shell and exits 127. An absent cictl
therefore cannot reach `affected-gate-fast` in those tiers.

The claim holds only for the merge tier (`affected-gate-substrate` runs alone)
and nightly (`gate-all` first). The fix is still needed — the NON-127 stimuli (a
bad base ref, a shallow clone, a git fault) hit every tier — but the stated
reason was wrong.

## Phase 4 — REFUTED. The swallow moved; it did not die.

The verifier broke the central claim, by execution:

**`listing="$(affected_projects)" || status=$?` puts `affected_projects` on the
LEFT of `||`, which disables `set -e` for its whole body.** Only the LAST
command's status becomes the function's status; every earlier command's is
discarded. That is the exact defect this change exists to kill, relocated one
function inward.

`affected_projects` is safe today ONLY BY ACCIDENT: it holds 2 commands and the
first (`require_cmd`) `exit`s rather than returns. Adding one ordinary line
restores the false green. The verifier added a plausible one:

```sh
function affected_projects() {
  require_cmd cictl
  git -C "$REPO_ROOT" fetch --quiet origin "$NX_BASE"   # <- one ordinary line
  cictl affected -C "$REPO_ROOT" --base "$NX_BASE"
}
```

With the fetch failing and cictl succeeding, `affected-gate-fast` printed git's
own `fatal: 'origin' does not appear to be a git repository` and still exited
**rc=0** with `all 1 affected project(s) green`.

`shellcheck` sees it (SC2310 at `.ci/ctl.sh:84:14`) but ONLY under `-o all`, and
`cmd_validate` runs bare `shellcheck`, so CI is blind to it.

The plan asked for a fix that "makes the swallow structurally impossible rather
than merely absent at this one call site". By that standard the deliverable is
NOT met.

**Second finding: the suite proves "non-zero", never 127.** Every status
assertion is `[[ "$RC" -ne 0 ]]`. Changing `return "$status"` to `return 1` keeps
the suite fully green. But rule 20 states the contract — "an absent tool is a
gate failure (exit 127), not a skip" — and this file's own Proven section treats
rc=127 as a property of the deliverable. It is unguarded.

**Out of scope, recorded so it is not lost:** the same class survives at
`ctl.sh:79`, `mapfile -t dirs < <(find ... -printf ...)`. `-printf` is GNU-only,
so on a BSD find the producer fails in the subshell and `./ctl.sh status` reports
0 libraries with rc=0. The three sibling calls at 153-155 have a `_floor_of_one`;
this one does not.

## What the verifier attacked and could NOT break

Recorded because a survived refutation is worth more than a claim: `status` is
truly local (4 calls in one process gave 127, 0, 4, 0); the real status
propagates (cictl exit 3 -> rc=3, SIGKILL -> rc=137, absent -> rc=127 on all 3
tier verbs); the `[[ -z "$listing" ]] ||` guard is load-bearing (removing it
reddens test 3) and no whitespace listing produces a phantom project; all 3 tier
verbs propagate the exact code with no wrapper or pipeline; the test split is
real, not a dodge; and the repository's own `ctl.sh validate` is rc=0 in the real
base image with `ok: .ci/ctl_test.sh` in the log, so the new suite is genuinely
wired into the pr tier.

## Next

Test author: a stimulus where `affected_projects` has a FAILING first command and
a SUCCEEDING last one, plus a test pinning rc=127 rather than merely non-zero.
Then the implementer for the structure.
