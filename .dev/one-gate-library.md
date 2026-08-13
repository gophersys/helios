# one-gate-library

phase:    pr
repo:     gophersys/libs
branch:   refactor/one-gate-library
worktree: ~/code/.worktrees/libs-one-gate
pr:       -
attempt:  1/2

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

### Phase 3 — GREEN, every line run

- `bash templates/_ctl/template_test.sh` -> rc=0,
  `5 test(s) hold; 5 of 5 proven able to fail; 0 stated no counter`.
- `bash verb_conservation_test.sh` -> rc=0,
  `17 project record(s) hold; 3 mutant(s) caught`. The rename did NOT move the
  golden, so nothing had to be re-recorded for it.
- `bash ./ctl.sh validate` -> rc=0.
- hnslint contrast, the deliverable: naming findings 3 -> 0, layout findings 2 ->
  2, `HNSLINT_RC=1`. Still red, correctly, with no skip and no silencing.
- The template still builds: `go build`, `go vet`, `go test` all rc=0,
  `gofumpt -l` clean.

Commits `1bb027c..58bfb97`: e400c8b (the runner can now fail), 921a6ae (rule 11
pins the spine names), 58bfb97 (the template uses them).

### The evidence was re-counted, not repeated

The implementer verified my numbers itself rather than trusting the brief:
`type Config struct` 26 in 14 libs, `type Deps struct` 22 in 14 libs, and a diff
proves the 2 library sets are IDENTICAL. Zero long-form declarations under `go/`.

**And it found something better.** The outlier was inside the TEMPLATE, not only
against the libraries: `internal/server/server.go`, `internal/api/v1/mount.go`
and `internal/api/v1/ping/route.go` already used `Config`/`Deps`. Only
`persistence` disagreed. So this was a self-consistency fix as much as a rule
change.

`Store` -> `Persistence`, and not a free choice: rule 11 maps `db`/`repo`/`store`
-> `persistence`, so that IS the required form. `ResourceStore` and
`ResourcePersistence` both stutter as `resource.X`, which revive's exported rule
flags in the strict set. `Repository` would relabel a banned token, not fix it.

### Ownership, flagged rather than hidden

The rename touched 2 `_test.go` files inside the template
(`resource_integration_test.go`, `resource_route_test.go`). Those are shipped
template SOURCE, not the phase-2 suites. The implementer flagged it for checking
rather than assuming, and I checked the diff: 2 type references and 1 comment.
No assertion, tolerance, case or skip changed.

## Next

Phase 4 — the adversarial refutation, then the pull request. The hnslint LAYOUT
half stays red on purpose (task #34); it needs an hnslint release because v0.1.0
has no flags.

STOP for Mateo was on the hnslint question. The runner unification is unblocked and
independent: phase 3 may fix the shared body so the gate can fail, which is the
prerequisite for the hnslint step to matter at all. Do not land a declared skip
for hnslint until the question above is answered — and if a skip does land, the
argv floor test must be rewritten in the same change, visibly.


## Phase 4 — the adversarial pass found the defect this feature is named for

F1 (HIGH). `go/_ctl/lib.sh:1187-1190` ran the 4 phases in the `||`-LEFT position,
which suppresses errexit and propagates the suppression into `_gate_run`'s
subshell. **The same defect the template fixed on this branch, still live in the
file this feature calls the one home.** Commit `e400c8b` even states the rule in
its own message and applies it only to the template.

Severity: `phase-gate all` is a wired Nx target in all 16 `go/*/project.json` and
is the nightly CI verb `gate-all`.

Proven on a fixture with a REAL Go toolchain and REAL git, both revisions:

```
PRE-FIX  (e00b47f)   [ok] build: OK      PASS  skeleton compiles (go build)   rc=1
POST-FIX (21ddf6e)   (no build: OK)      FAIL  skeleton compiles (go build)   rc=1
```

The pre-fix run printed `[ok] build: OK` directly under the compiler's
`cannot use "this does not compile" ... as int value`, and reached rc=1 only BY
ACCIDENT, through `go vet`'s explicit exit. A clean fixture still reaches
`[ok] phase-gate all: GREEN`, rc=0, so the gate is not stuck red.

F2 (LOW). Rule 11 said 17 libraries; there are 16 — `go/_ctl` is the shared gate
library, not a library under gate. That number was mine. 17 is the
verb-conservation PROJECT count leaking into a LIBRARY count, and the distinction
is load-bearing: adding `templates/go/http-gateway` would have made the 2 zero
rows into ones.

F3 (LOW). `testdata/verb-conservation/README.md:70` said 7 tool lines; the table
beneath enumerated 8. Verified from the re-record diff itself. Now 8, and the
entry carries the count check so the next reader can redo it.

### The goldens moved, and it is the gate becoming honest

16 records, 1 line each, always the same, only in `profile=fail` under the bare
`### verb phase-gate` block:

```
 gofumpt -l .
-go      vet ./...
```

That `go vet` only ever ran BECAUSE errexit was suppressed. CAUSATION PROVEN, not
assumed: the implementer stashed `lib.sh` and re-ran to get the clean baseline
`17 project record(s) hold`, rc=0.

**THE SAFETY PROPERTY, checked before re-recording.** Both revisions split at
`profile=fail` and the `pass` halves diffed alone: BYTE-IDENTICAL in all 17
records, 1239 -> 1239 gate-tool lines. Nothing disappears when everything passes.
A short-circuit on a failing tool is honesty; a check vanishing on a pass would be
a regression wearing honesty's clothes.

4 fail-profile properties confirmed independently: 16 records touched and only
those; 1 line removed each; nothing added; no exit code moved.

Corroboration that needs no argument: `templates/go/http-gateway` — which has had
this fix since `e400c8b` — DID NOT MOVE.

### Green

- `bash go/_ctl/lib_test.sh` rc=0, `7 test(s) hold; 6 of 7 proven able to fail`
- `bash templates/_ctl/template_test.sh` rc=0, `5 of 5 proven able to fail`
- `bash verb_conservation_test.sh` rc=0, `17 records hold; 3 mutants caught`
- `bash ./ctl.sh validate` rc=0, `all checks passed`, zero `[error]` lines

### Found and filed, not fixed here

`_cohesion_scan` leads a command substitution with a `grep` that exits 1 when a
library declares no exported type. Errexit used to swallow it; now it kills
`cmd_maintainability`. No library reaches it today (the lowest is `errors` at 1),
but `phase-gate architecture` runs on a SKELETON, which is exactly that shape.
Task #47, with the warning not to re-suppress errexit: every previously swallowed
non-zero in that file is now load-bearing.

## Next

Phase 5 — the pull request.
