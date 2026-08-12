# one-gate-library

phase:    plan
repo:     gophersys/libs
branch:   refactor/one-gate-library
worktree: ~/code/.worktrees/libs-one-gate
pr:       -
attempt:  0/2

## Goal

go/_ctl/lib.sh and templates/_ctl/template.sh are 2 parallel shell gate
libraries, and templates does not source go/_ctl. They share 22 function names
and only 4 are byte-identical. The repository's own rule 10-interface-design.md
says one concept, one home.

It has already bitten: the golangci exit-code handler had to be fixed in both
files, with a test on only one of them.

Also in scope, same file: `templates/_ctl/template.sh` calls `hnslint ./...`, a Go
package pattern where hnslint wants directories. That line had never executed
because hnslint was never on PATH in CI.

## Plan

Phase 1 running. The planner was told NOT to unify on principle: if the 18
differences are meaningful, it must say so and propose the smaller correct change
instead.

## Proven

- Measured by the implementer during the golangci work: 22 shared function names,
  4 byte-identical (_eden_monorepo_root, cmd_fmt, have_cmd, require_cmd).
- The hnslint failure is real, not a wrong argument: running the pinned v0.1.0
  with the correct argument still fails, because hnslint encodes the
  libs/go/<slug> layout and a template is not that.

## Blocked

Nothing.

## Next

Phase 2 once the plan lands.
