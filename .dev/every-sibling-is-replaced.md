# every-sibling-is-replaced

phase:    fix — the verifier returned 6 findings
repo:     gophersys/libs
branch:   fix/every-sibling-is-replaced
worktree: ~/code/.worktrees/libs-replaces
pr:       -
attempt:  1/2

## Goal

2 libraries cannot build standalone, so they fail all 5 gate dimensions on `main`
and nothing reports it. Give them the `replace` directives they need, and add the
repository-wide check that stops the next library doing the same.

## The finding, from the 16-library sweep

`bash ./ctl.sh phase-gate implementation` over EVERY library at origin/main
e82815e found **4 of 16 RED**, each failing all 5 dimensions:

```
agentruntime     RED=5/5   missing go.sum entry      <- this feature
edenhttp         RED=5/5   missing go.sum entry      <- this feature
objectstorage    RED=5/5   missing go.sum entry (kr/pretty@v0.3.1)
orchestrator     RED=5/5   go: updates to go.mod needed
```

The last 2 are a DIFFERENT cause — manifest drift, each needing a judgement call.
They stay in task #37 and are deliberately not in this change.

## The cause for these 2 is structural, not drift

They require sibling libraries at `v0.0.0` with NO `replace` directive. `v0.0.0`
is unpublished, so the module cannot resolve at all — they build ONLY inside
eden's `go.work`. The gate builds standalone on purpose (`GOWORK=unset`), and that
is correct: a library that compiles only inside its parent workspace is a package
of the parent, not a library.

```
UNREPLACED agentruntime -> agentsession dependencies errors observability secrets testing
UNREPLACED edenhttp     -> agentruntime agentsession errors
```

## THE FIX IS PROVEN BEFORE IT IS WRITTEN

I added the 6 `replace` lines to `agentruntime` in a disposable tree and ran the
REAL gate:

```
before   5/5 RED
after    PASS go build ./...
         PASS golangci-lint full + hnslint + cohesion
         PASS apidiff: no break vs .apibaseline
         PASS go vet
         PASS unit + fake conformance GREEN (-race)      rc=0
```

No version moved, no `go mod tidy`, no manifest rewrite. Only the missing block.

## The check, and why the obvious formulation is wrong

I got this wrong TWICE before it was right, and the test must use the third form:

1. **count requires vs replaces** — flags 13 of 16. A `=> ../x` line also matches
   the requires pattern, so it double-counts.
2. **subtract the replaces** — still flags 5. `envelope`, `forge` and
   `objectstorage` legitimately carry MORE replaces than requires, because a
   replace may cover a requirement declared elsewhere.
3. **per-module: every REQUIRED sibling has a replace FOR THAT MODULE** — selects
   exactly the 2 the sweep found red.

A count-based test would be wrong in both directions: false alarms on 11
libraries, and it would still pass if a library replaced the WRONG module.

## Plan

APPROVED (self, under delegated authority).

- `go/_ctl/lib_test.sh` — a repository-wide assertion, form 3 above. RED today for
  2 libraries. It must name the library AND the unreplaced modules, because
  "somewhere a replace is missing" is not an actionable failure.
- `go/agentruntime/go.mod`, `go/edenhttp/go.mod` — add the `replace` blocks.
  NOTHING ELSE. No version bump, no tidy.

## Deliberately NOT in this change

- `objectstorage` and `orchestrator`. Different cause, each needs a decision.
- Task #49, the nightly that gates only affected projects and has therefore never
  checked any of this. That is the reason the 4 were invisible and it is the
  durable half — but it is a separate change with a capacity question in it.

## Proven

- The 16-library sweep, per-library logs in scratchpad/sweep-<lib>.log.
- The agentruntime fix, run through the real gate: 5/5 RED -> 5/5 PASS, rc=0.
- The check's 3 formulations, each run over all 16 go.mod files.

## Blocked

Nothing.

### Phase 2 — RED, reconstructed and confirmed by the verifier

The shipped test over main's go.mod set: rc=1, naming both offenders and every
module.

### Phase 3 — GREEN, and an AMENDMENT TO THE APPROVED PLAN (F5)

The plan said "add the `replace` blocks. NOTHING ELSE. No version bump, no tidy."
**That was wrong, and edenhttp proved it.** A `replace` in a DEPENDENCY's go.mod
is IGNORED by Go, so edenhttp must resolve agentruntime's siblings itself: the
closure is 8, not 3, and it also needs the `// indirect` require block that
`go mod tidy` produces.

Mateo authorised the wider patch with 2 guards, both proven:
- every added require line ends `// indirect` — 0 exceptions, no goleak, no rapid,
  no libs/go/testing. The objectstorage laundering did not happen.
- `go.sum` BYTE-IDENTICAL, and `GOWORK=off go mod tidy -diff` rc=0, so the
  hand-written block is a fixed point.

Recording the amendment here because the skill requires it and because the reason
previously lived only in a commit message, which a plan reader never sees.

Result: `go/agentruntime` and `go/edenhttp` both 5/5 PASS, suite 20 hold / 19 of
20 proven across 27 counter-stimuli, validate rc=0, conservation 17 unmoved.

## Phase 4 — 6 findings

**F3 (MEDIUM, and the real one).** agentruntime got a PARTIAL closure. Its 6
replaces cover its DIRECT siblings; `envelope` is still unreplaced in its module
graph, pulled in by `secrets`. The reasoning that drove the edenhttp fix was not
applied to agentruntime.

`go build` passes only because Go's pruned graph never loads envelope. Proven by a
one-line import, restored:

```
GOWORK=off go list -m all   -> rc=1  envelope@v0.0.0: invalid version
add   _ ".../secrets/platformconnectoradapter"   to advisor.go
GOWORK=off go build ./...   -> rc=1  missing go.sum entry for .../envelope
bash go/_ctl/lib_test.sh t_every_required_sibling_is_replaced -> rc=0  GREEN
```

**The exact error this change exists to eliminate, on a library it claims to have
fixed, with the new test green.** Merely sufficient, not complete.

**F1 (HIGH).** `assert_only_replace_directives_differ` has NEVER executed a
failing path — no counter-stimulus reaches it, another assertion fires first, and
the suite scores discrimination per TEST. On the shipped tree `repair_tree` is a
no-op, so it compares a file to a copy of itself. It guards this change's central
scope claim — "no require moved, no version moved" — and it is decorative.

**F2 (HIGH).** The words `transitive` and `closure` appear 0 times in the file, and
the failure message instructs the WRONG FIX: "Add the replace block; move no
version and run no go mod tidy." Following it verbatim is exactly what commit
5d78346 did, and it left the gate RED. A reader at 3am gets a green test over a
library that does not build.

**F4, F5 (mine).** This state file read `phase: plan` after phases 2 and 3 shipped,
and the plan amendment above was undeclared. Both fixed here.

**F6 (LOW).** `SIBLING_SCAN_AWK` declares `replace_once()` and never calls it.
shellcheck cannot see inside the quoted awk string.

## Note for anyone looking for the transitivity follow-up

The verifier searched `gh issue list` in gophersys/libs and gophersys/eden and
found nothing. It is filed in the session task ledger as **task #50**, not as a
GitHub issue. That is a real findability gap, not a missing filing.

## Next

Phase 7: implementer for F3, then test author for F1, F2 and F6.
