# one-gate-library

phase:    green — the hnslint escalation is DECIDED (2026-08-13)
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

### Phase 2 — the false green is REPRODUCED, not inferred

The pinned binary was confirmed first: `hnslint` in `ghcr.io/gophersys/base:latest`
reports `mod github.com/gophersys/hnslint v0.1.0`, so this is the public tool and
not the shadowing eden build.

A fixture holding 1 Go file that does not compile, driven through the real entry
point, exits **0**:

```
── phase-gate step: test
FAIL  example.com/brokentemplate [build failed]
[ok]  test: OK
PASS  test
[ok]  phase-gate testing: GREEN
PHASE-GATE-TESTING-EXIT=0
```

The same verb ALONE exits 1. All 6 named verbs confirmed, including the case this
file already quoted: `./...: not a directory` → `[ok] maintainability: OK` →
`PASS maintainability`.

**Root cause isolated.** Bash's errexit-ignore context for an `if` condition
propagates into the subshell DESPITE the re-armed `set -Eeuo pipefail`.
`go/_ctl/lib.sh:1009-1020` already documents and fixes this exact trap. So the
false green is CAUSED BY THE DUPLICATION this feature exists to remove, which is
the strongest possible argument for it. Today only lint, `require_cmd` and
`_assert_*` — the paths with an explicit `exit` — can fail at all.

3 red tests, each observed failing for the right reason, plus 2 conservation
guards each observed failing under its own counter-stimulus, plus a 17-project
verb-conservation record whose 3 planted mutants were all caught.

## The decision — MATEO, 2026-08-13: the rule follows the practice

**The evidence that settled it.** Across the 17 libraries:

```
26 type Config struct       in 14 libs
22 type Deps   struct       in the same 14 libs
 0 type Configuration struct
 0 type Dependencies  struct
```

So hnslint is not inventing a ruling. It is codifying what every library already
does, and `templates/go/http-gateway` is the ONLY outlier in the repository. The
apparent contradiction was rule 11 being vague where the code is unanimous.

**What changes:**
1. `.claude/rules/11-naming.md` — the narrow exemption stops saying `Config`/`Deps`
   are "fine" and says they are REQUIRED for the constructor-spine types. The slug
   ban is untouched: a package or directory named `config`/`deps` is still
   forbidden. Only the 2 spine TYPE names are pinned.
2. `templates/go/http-gateway/persistence/persistence.go` — `Configuration` ->
   `Config`, `Dependencies` -> `Deps`, so the template stops generating
   applications that fail their own linter.
3. `Store` -> a meaningful compound. It was a defect under the ORIGINAL reading
   too, and it is the one finding both readings agreed on.

**No hnslint release is needed**, which is why this option was cheapest. Option B
would have cost a v0.1.1 plus a pin bump and left the spine spelled 2 ways.

### This resolves the NAMING half only. The template still cannot go green.

hnslint's LAYOUT findings survive the rename and always will:

```
no primary package found in the library root; expected package "http-gateway"
module path is ".../libs/templates/go/http-gateway", want ".../libs/go/http-gateway"
```

A template is not a library at `go/<slug>`, and its `cmd/gateway` must be
`package main`. **No conformant application can ever satisfy those**, so they are
not defects to fix — they are the wrong check pointed at the wrong thing. That is
task #34, and it needs a real hnslint release because v0.1.0 has NO FLAGS at all.

Do not paper over it with a skip in the meantime. Report the layout findings
honestly and let the gate be red for a stated reason.

## Blocked

The plan assumed `Configuration` and `Dependencies` were defects to be spelled
out. The pinned hnslint says the OPPOSITE:

```
persistence/persistence.go: exported type "Configuration" is a full-spelled spine outlier;
  use Config as the type name (10 §5 founder ruling)
persistence/persistence.go: exported type "Dependencies" is a full-spelled spine outlier;
  use Deps as the type name (10 §5 founder ruling)
internal/api/v1/resource/resource.go: exported type "Store" is a bare banned HNS-1 token
```

Only `Store` is a defect in the direction the plan assumed. So "the template
violates HNS-1 naming" is true, but 2 of the 3 findings demand the SHORT form,
while `rule 11`'s table bans `config`/`deps` and its narrow exemption merely
PERMITS `Config`/`Deps` as type names. The tool REQUIRES what the rule permits.
That gap is a decision, not a defect to code around, and it is task #34's
territory.

**Two further facts that kill the plan's accepted approach as written:**
- hnslint v0.1.0 has NO FLAGS. `hnslint <dir> [dir...]` only; `-naming`, `-layout`
  and `-h` are all read as directory arguments. "Let the caller select" needs a
  real release of gophersys/hnslint, not a call-site change.
- An argument error and a finding are BOTH exit 1. Only "no arguments" is
  distinct, at exit 2. So "distinguish an argument error from a finding" cannot be
  done by exit code alone at this version.

**The shadowing warning was right, and it mattered.** This Mac's
`/Users/mateo/go/bin/hnslint` is `github.com/gophersys/eden/tools/hnslint (devel)`.
Against the same directory it prints only the 2 layout findings and ZERO naming
findings — it cannot see the half the decision turns on. Anyone who had run this
locally would have concluded the naming half did not exist.

## Next

STOP for Mateo on the hnslint question. The runner unification is unblocked and
independent: phase 3 may fix the shared body so the gate can fail, which is the
prerequisite for the hnslint step to matter at all. Do not land a declared skip
for hnslint until the question above is answered — and if a skip does land, the
argv floor test must be rewritten in the same change, visibly.
