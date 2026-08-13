# cictl-swallow

phase:    plan
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

Nothing yet. Phase 2 owes a RED test.

## Blocked

Nothing.

## Next

Test author: reproduce the swallow as a failing test.
