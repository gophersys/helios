# one-gate-library

phase:    red
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

APPROVED.

**The finding that matters most, and it is worse than the duplication.** The
template's `phase-gate` has reported PASS on FAILING `go build`, `go test`,
`govulncheck`, `gosec`, `gitleaks` and `hnslint` for its whole life. The false
green is not a risk of this change; it is already realised.

**So fixing the runner will turn the template RED for the first time.** That is
not a regression this feature causes. It is the first honest reading, and the
pull request must say so plainly, or a reviewer applies the caused-versus-
surfaced rule backwards.

**The hnslint step cannot be made both meaningful and green here, and that is an
escalation rather than a decision.** hnslint carries 2 kinds of check and
conflates them:
- LAYOUT — module path `libs/go/<slug>`, 1 go.mod per directory, primary package
  equals the slug. **No conformant application can ever satisfy these.** A
  template's `cmd/gateway` must be `package main`. These findings are not defects.
- NAMING — the `Store` / `Configuration` / `Dependencies` findings. HNS-1 rule 11,
  and universal. These ARE real defects in the template, and a template its own
  naming linter rejects will generate applications that violate HNS-1.

All 3 options in my brief fail as stated. Conforming the template is impossible;
dropping the step loses the real half; teaching hnslint the layout is right in
substance but the general rule is that **hnslint should separate its layout checks
from its naming checks and let the caller select** — another repository, a
release, and a pin bump under rule 22.

Accepted approach: fix the shared body so the check CAN fail, invoke hnslint with
a directory, and distinguish an argument error from a finding — the same
principle as the golangci exit-code handler, applied once instead of twice. Land
the template's step as a DECLARED skip carrying its reason, so the gate prints it
on every run. Declared, counted, visible — the same idiom as the suite's `none:`
counter.

**A correction to something I said.** My claim that installing hnslint "made a
dead check reachable" is half true. It made the check RUN; it still cannot fail.
Proven: `./...: not a directory` followed by `[ok] maintainability: OK`. So
fixing `./...` alone changes nothing observable, and the runner unification is
the prerequisite for the hnslint decision to matter at all. That sets the order.

**Load-bearing caveat for phase 2.** The `hnslint` on this Mac's GOPATH/bin is
`github.com/gophersys/eden/tools/hnslint (devel)` — the OLD eden binary, not the
public `gophersys/hnslint` that rule 11 names and CI pins. That is exactly the
shadowing rule 11 warns about. The naming findings were INFERRED from
`.golangci.yml`'s description, not observed. Phase 2 must re-run the PINNED
binary in the devcontainer and record its real output. If the pinned binary emits
no naming findings, dropping the step becomes defensible and the recommendation
changes.

## Proven

- Measured by the implementer during the golangci work: 22 shared function names,
  4 byte-identical (_eden_monorepo_root, cmd_fmt, have_cmd, require_cmd).
- The hnslint failure is real, not a wrong argument: running the pinned v0.1.0
  with the correct argument still fails, because hnslint encodes the
  libs/go/<slug> layout and a template is not that.

## Blocked

Nothing.

## Next

Phase 2, in this order, because the order is load-bearing: re-run the PINNED
hnslint and record what it really says, then prove the template's gate reports
PASS over a failing verb.
