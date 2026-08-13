# cictl-swallow

phase:    verify
repo:     gophersys/libs
branch:   fix/cictl-swallow
worktree: ~/code/.worktrees/libs-cictl-swallow
pr:       -
attempt:  1/2

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

Nothing blocking. One neighbour UNVERIFIED, reported rather than hidden:

`go/_ctl/lib_test.sh` could not run here. It is FAIL-NOT-SKIP and named its
blocker each time: no go, then no golangci-lint, and finally the real substrate
`ghcr.io/gophersys/base:latest` returns **no matching manifest for
linux/arm64/v8**. The image has no arm64 build, so it cannot run on this Apple
Silicon host at all.

That is a direct, measured cost of D42 (arm64 dropped from the images): a
developer on Apple Silicon cannot run this repository's own gate locally. Worth
carrying into the arm64 decision, since the mini now builds arm64 natively.

The suite covers `go/_ctl/lib.sh`, which this change does not touch, so the risk
is low — but it is UNVERIFIED, not green.

## Next

Verifier: try to refute that this is done.
