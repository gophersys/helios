# wire-validate-into-pr

phase:    intake
repo:     gophersys/libs
branch:   ci/wire-validate-into-pr
worktree: ~/code/.worktrees/libs-wire-validate
pr:       -
attempt:  0/2

## Goal

`go/_ctl/lib.sh` holds every gate verb in this repository, and nothing in CI runs
it. The pull request tier runs `ci-drift` and `affected-gate-fast`; the affected
gate skips `go/_ctl` outright, and no tier runs `validate` at all. The new shell
suite from libs#6 therefore runs only by hand.

That is the reason the golangci defect shipped, and the reason libs#6 went green
in 8 seconds while checking nothing.

When this is done, `validate` runs on every pull request, so the shell suite and
the `_ctl` shellcheck coverage gate real changes.

## Plan

Not yet written. Phase 1 delegates to `dev-planner`.

## Proven

- The 4 drift failures reproduce on this branch, in an ubuntu 24.04 container
  with bash 5.2, before any change:
  - `.ci/ctl.sh: usage entry 'ci-drift' missing from project.json targets`
  - `templates/go/http-gateway/clients/go/project.json: target 'generate' missing from ctl.sh usage`
  - `templates/go/http-gateway/persistence/project.json: target 'generate' missing from ctl.sh usage`
  - `templates/go/http-gateway/persistence/project.json: target 'verify' missing from ctl.sh usage`
  - `templates/go/http-gateway/project.json: target 'build' missing from ctl.sh usage`
- `bash ./ctl.sh validate` cannot run on this host: `/bin/bash` is 3.2.57 and has
  no `mapfile`. The container is the only way to run it here.

## Blocked

Nothing yet.

## Next

Phase 1: `dev-planner` decides which of the 4 are real, and how to wire `validate`
into the `pr` tier without turning the lane red on someone else's debt.
