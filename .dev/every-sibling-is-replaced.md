# every-sibling-is-replaced

phase:    fix — verifier round 2 returned 5 findings
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

## Phase 7 — the scope widened, then measurement narrowed it back

**The decision, mine, under delegated plan authority.** The new full-graph test
found 7 red libraries, not 2, and the test author tabled all 7 in
`MODULE_GRAPH_EXEMPT` rather than widen the fix on its own authority. That was the
right escalation. I widened it, on this principle:

> An exemption table may hold only defects of a DIFFERENT class. A same-class
> defect gets fixed, never tabled.

Six known one-line violations sitting in a table would have made this feature's
own central claim — every sibling is replaced — false at the moment it merged.

**Then the implementer refuted half my premise, and it was right.** I told it "all
7 have green `go build`, `go vet` and `go test` standalone". Measured at HEAD in
disposable copies, before any edit:

```
objectstorage  GOWORK=off go build ./...  rc=1  missing go.sum entry for kr/pretty@v0.3.1
orchestrator   GOWORK=off go build ./...  rc=1  go: updates to go.mod needed
               GOWORK=off go vet ./...    rc=1  (same)
```

That contradicted my brief and AGREED with the 16-library sweep already recorded
at the top of this file, which listed both as RED=5/5. I carried a claim forward
from a later report instead of checking it against the sweep in this document.
**The state file was right and I was wrong** — which is the whole reason it exists.

- `objectstorage` — go.sum line 17 carries the `h1:` hash for `kr/pretty v0.3.1`
  with no `/go.mod` hash. No replace can fix it, and the fix writes go.sum, which
  guard 2 forbids. Line reverted.
- `orchestrator` — needs a SECOND replace (`observability`, reached via
  agentruntime), and even then resolves only by bumping a DIRECT dependency
  (`pgx/v5 5.7.6 -> 5.10.0`, plus x/text and x/tools). Beyond replace +
  `// indirect`, and a judgement call. Both lines reverted.

Both stay on the table, and the table's own wording already partitioned the set
correctly: those two read "deferred to task #37" while the four fixed read "not in
this change's scope".

**Fixed: 4, one line each, closure = 1 for all four.**
`agentsession`, `forge`, `gitrepository`, `workspaceprovider`.

```
GOWORK=off go list -m all       rc=0 for all four
phase-gate implementation       rc=0  PASS=5 FAIL=0  for all four
go.sum                          byte-identical, sha256 unchanged for all four
```

## Now RED, on purpose, and it needs the test author

`bash ./ctl.sh validate` -> rc=1, `test suite failed: go/_ctl/lib_test.sh`. Two
causes, both consequences of the fix working:

1. Four `MODULE_GRAPH_EXEMPT` entries are now stale. The table is enforced in both
   directions, so a library that starts resolving FAILS. That is the table
   policing itself.
2. The `exempt-library-repaired` counter-stimulus can no longer be BUILT: it
   repairs `agentsession`, which is now already repaired, so the mutant changes
   nothing and the suite aborts before its summary. It must point at a library
   still genuinely on the table.

## Next

Test author: delete the 4 stale entries, and re-point the
`exempt-library-repaired` mutant at a library that is still exempt.


## Phase 8 — the gates, run for real by the verifier (155s and 983s, not fast greens)

```
bash go/_ctl/lib_test.sh    rc=0   155s
   21 test(s) hold; 20 of 21 proven able to fail across 31 counter-stimuli; 1 stated no counter
bash ./ctl.sh validate      rc=0   983s   validate: all checks passed
   incl. verb_conservation_test.sh: 17 project record(s) hold; 3 mutant(s) caught
shellcheck -S style go/_ctl/lib_test.sh     rc=0
phase-gate implementation   rc=0  PASS=5 FAIL=0  for forge, agentsession,
                                  gitrepository, workspaceprovider, agentruntime
```

Survived refutation, each attacked deliberately: all six `envelope` replace lines
are LOAD-BEARING (removing any one gives rc=1); `go.sum` is byte-identical
(sha256 equal to origin/main for all six); every added require ends `// indirect`
(count of exceptions: 0); `exempt:stale` discriminates on a LIVE green case, not
an empty one; the `die`-aborts-the-suite defect is genuinely closed (a stimulus
that cannot be built is now a named failing assertion and the suite continues);
`1 stated no counter` is honest — it is `t_concurrent_lints_do_not_collide`,
unchanged from main, whose stated reason is a property of the check.

## Phase 8 findings — MY WIDENING DECISION WAS HALF WRONG

**F1 (HIGH). The table holds two SAME-CLASS defects, which is exactly what my own
principle forbids.** I widened the scope on the rule that an exemption table may
hold only a DIFFERENT-class defect. `objectstorage` and `orchestrator` are still
missing the one-line `envelope` replace that the other four received. Measured:

```
objectstorage as-is                      -> envelope@v0.0.0: invalid version
objectstorage + envelope replace         -> kr/pretty: missing go.sum entry   <- the TABLED reason
orchestrator + observability only        -> envelope@v0.0.0: invalid version
orchestrator + envelope only             -> observability@v0.0.0: invalid version
orchestrator + envelope + observability  -> updates to go.mod needed          <- the TABLED reason
```

**The reasons written in the table are the errors that appear AFTER the fix, not
the errors the tool reports today.** And `orchestrator` needs TWO replaces —
`observability` as well as `envelope` — which is named nowhere: not in the table,
not in this file, not in a commit message.

Both added lines leave `go.sum` byte-identical, so guard 2 does not forbid them.
I accepted "unfixable within the guards" from a report without measuring it.

**F3 (MEDIUM, and the one that would bite a stranger).** Test 21 cannot tell "a
sibling is unreplaced" from "the proxy is unreachable" — both are rc!=0 from
`go list -m all`. With no network all 16 libraries go red, 12 are not on the
table, and the failure tells the reader to add a replace for
`github.com/antithesishq/antithesis-sdk-go@v0.7.0-default-no-op`, a third-party
module for which no replace is correct. **This check now runs on every PR and
push.** The discriminator exists: a transport error is not a
`v0.0.0: invalid version`, and it should abort as a harness failure the way
`assert_gate_harness_intact` already does.

**F4 (LOW).** Test 21's `scanned -gt 0` vacuity floor has no counter-stimulus,
while the comment above it claims "ONE COUNTER PER ARM". Tests 18 and 19 both
carry `tree:empty` for exactly this. If the `MODULE_TREE` glob ever stops
matching, test 21 passes having loaded zero graphs and is still scored proven.

**F5 (LOW).** An exemption entry naming a library that does not exist is never
policed — the stale arm only fires for a library the scan actually walked. Proven
by adding `phantomlib` to the table: rc=0, green, no complaint.

**F2 (MEDIUM, mine).** This file was stale: it still said the branch was RED and
ordered work already finished, and `## Proven` stopped at phase 1 with no record
of the phase-8 gates. Fixed by this entry. Note the phase-1 sweep logs it cites
live in a scratchpad from a previous session and no longer exist, so that one
proof is no longer re-readable by anyone.

## Next

Implementer: 3 replace lines — `envelope` for objectstorage, `envelope` +
`observability` for orchestrator. Then test author: shrink the table to the true
residual reasons, add the network discriminator (F3), the vacuity counter (F4)
and the phantom-entry guard (F5).
