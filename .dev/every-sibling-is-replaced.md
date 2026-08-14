# every-sibling-is-replaced

phase:    verify
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

## Plan — SUPERSEDED, see phases 7 and 9

The plan below is the ORIGINAL scope and it is no longer true. It said 2
libraries and "NOTHING ELSE"; the change is 8 `go.mod` files, and both
`objectstorage` and `orchestrator` — listed here as deliberately excluded — were
changed in `6738f52`. Kept verbatim rather than edited, because the amendments and
their reasons are the record. A reader who stops here gets the wrong scope; the
phases below are authoritative.

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


## Phase 9 — the 3 lines landed, and MY PREDICTION WAS WRONG in an instructive way

`6738f52`. 2 files, 3 insertions. Both errors changed exactly as measured:

```
BEFORE  objectstorage  envelope@v0.0.0: invalid version  +  kr/pretty missing go.sum entry
        orchestrator   envelope + observability invalid  +  updates to go.mod needed
AFTER   objectstorage  kr/pretty@v0.3.1: missing go.sum entry for go.mod file
        orchestrator   updates to go.mod needed; to update it: go mod tidy
```

All 3 lines proven LOAD-BEARING — dropped one at a time with `go mod edit
-dropreplace`, each restores an `invalid version` naming exactly that module.
Guards held: 0 added `require` lines; `go.sum` sha256 IDENTICAL before and after
for both libraries; `go mod edit -fmt` diff rc=0, so no block was reformatted.

Suite rc=0 (67s), `ctl.sh validate` rc=0 in the container. `phase-gate
implementation` still 5/5 FAIL for both, unchanged from the sweep, as intended.

### THE FINDING — I predicted a table failure. There was none, and that is the defect.

I told the implementer to expect the suite to go red and quote the table failure.
**No such failure exists.** `t_every_library_resolves_its_full_module_graph`
(`go/_ctl/lib_test.sh:1441`) has exactly two arms:

```
unexpected   red  AND NOT on the table
stale        rc==0 AND on the table
```

**It never compares the recorded REASON to the observed error.** Both libraries
stayed rc=1, so both remain legitimately exempt and neither arm fires. The census
line is identical either side of the change: `16 librar(y|ies) read, 4 red, 4 on
the exemption table`. Only `replaces=` moved.

So **the exemption reasons are unpoliced prose.** The table policed itself in
`b3be25e` only because those four libraries went fully GREEN. A same-class defect
wearing a different-class label is invisible to every check in this repository —
which is precisely how these two survived, and why MEASUREMENT caught them rather
than the suite.

That is the deepest instance tonight of the estate's dominant defect family: a
control that is green because it cannot see. Here the control cannot see the one
field a human wrote by hand.

### The wording is now wrong in one direction only

`go/_ctl/lib_test.sh:715` still says orchestrator "needs a second replace plus
pgx/v5 5.7.6 -> 5.10.0". The second replace is now IN, so the true residual is the
bump alone. The prose block at 700-712 repeats it at line 704. Line 714's
objectstorage reason is now exactly correct — `kr/pretty` is its sole remaining
error.

## Could not verify

**eden's workspace build.** `~/code/eden/go.work` carries its own top-level
`replace` for all 20 modules including `envelope` and `observability`, and
go.work replaces take precedence, so these lines are INERT in workspace mode —
the same as the six identical replaces already on this branch. Reasoned from the
file, not built, because eden's submodule pointer sits at a different commit.

## Next

Test author, in priority order:
1. **Police the reason text.** An exemption entry should carry a machine-checkable
   expectation — the error substring the library must actually produce — so a
   wrong or stale reason FAILS instead of reading as documentation.
2. F3 — the network discriminator: a transport error must not be reported as a
   missing replace with a fix instruction that is wrong.
3. F4 — a counter-stimulus for the `scanned -gt 0` vacuity floor.
4. F5 — a phantom exemption entry naming a library that does not exist must fail.
5. Correct the orchestrator reason wording at :704 and :715.


## Phase 10 — the exemption reasons are ASSERTIONS now (`b8a8cac`)

Format is `<library> | <anchor> | <reason>`. Three arms police it, and **two read
the OBSERVATION, not the prose**:

```
reason       the observed error does not contain the anchor
same-class   the observed error names a SIBLING at v0.0.0 — not exemptible, whatever the anchor says
phantom      the entry names a library the scan never walked
```

**The `same-class` arm is the one that closes the hole I opened.** It matches
`github\.com/gophersys/libs/go/[a-z]+@v0\.0\.0` in the observed error and refuses
any exemption over it — with ZERO reliance on the prose being honest. It would
have caught `objectstorage` and `orchestrator` the day their reasons were written.

**On anchoring, answered rather than guessed.** Anchor on the MODULE PATH where
the error names one: Go rewords prose between releases (`missing go.sum entry`
gained `for go.mod file`), but a module path inside an error is DATA — the
identity of the thing that failed, and the exact discriminator between `envelope`
and `kr/pretty`. Where no module is named (`orchestrator` prints only `updates to
go.mod needed`) the anchor is Go's own error string. All four measured from a real
run.

**Does it move the prose problem? "Partly, and I will not pretend otherwise."**
The anchor is still typed by a human; what changed is that it is mechanically
refuted every run, and the same-class arm needs no hand-written input at all. The
degenerate case — an anchor so generic it matches anything, since `grep -F ""`
matches every error Go prints — is closed by an 8-character floor with its own
counter-stimulus. An anchor that is wrong but plausible remains possible, and
fails the moment the error it claims does not appear.

### F3 — a network outage is no longer a code finding

```
--network none, GOPROXY=off
[test] HARNESS FAILURE, not a finding: the module proxy is unreachable, so this run
       measured the network rather than agentruntime's manifest. ... CHANGE NO go.mod.
```

The discriminator is sharp and worth keeping: manifest markers are tested FIRST,
because an unreplaced private sibling fails THROUGH the network and carries
transport text too — but it also carries `invalid version`, which no reachability
failure ever produces. And the `unexpected` arm now prescribes no fix unless the
module named is a sibling: *"no fix is prescribed here: the module named is not a
sibling, so a replace is NOT the answer."* That kills the case where an outage
told 12 libraries to add a replace for a third-party module.

### It corrected my mapping

I said `tree:transitive-replace-dropped` should fire `unexpected`. It fires
`same-class` — the more specific arm claims it and gives the right fix. That left
`unexpected` with no counter, so `exempt:none` was added. **Eight counters, eight
arms, each verified to fire its own**, including both directions on the reason
arm: a wrong recorded reason fails, and phase-1 green is all four anchors matching
their observed errors.

```
bash go/_ctl/lib_test.sh   rc=0  126s  21 test(s) hold; 20 of 21 proven able to fail
                                        across 37 counter-stimuli; 1 stated no counter
bash ./ctl.sh validate     rc=0  validate: all checks passed
shellcheck                 rc=0
```

### A red it refused to report away, and a retraction

`validate` failed the FIRST time, rc=1, inside `verb_conservation_test.sh` with a
false *"the verbs moved"* diff. Root cause found rather than rerun-until-green:

```
mktemp: failed to create directory ... No space left on device
```

The Docker VM was at 90%. `mktemp` returned empty, the suite built its sandbox at
`/bin` and `/tree`, and recorded a **disk artifact as a contract change naming an
innocent library**. Filed as task #69 — it is not this branch's file to fix.

It also retracted its own intermediate claim: it had attributed 12G of growth to
`verb_conservation_test.sh`, which was wrong, because `df /` inside a container
reports the whole shared VM filesystem and the delta included other agents' runs.

## Next

Verification, then the pull request.


## Phase 11 — final verification: the central claim SURVIVES, two latent gaps remain

The verifier executed every attack and could not refute the branch.

```
ctl.sh validate            rc=0   913 lines, all checks passed
go/_ctl/lib_test.sh        rc=0   115s   21 hold; 20 of 21 proven able to fail
                                          across 37 counter-stimuli
shellcheck (3 files)       rc=0
```

**All 22 added replace lines are load-bearing** — each dropped individually with
`go mod edit -dropreplace`, 22 of 22 gave rc=1 naming that exact module at
`@v0.0.0`. Zero inert lines. **`go.sum` sha256 IDENTICAL to origin/main for all 8
touched libraries**, and every added `require` in edenhttp ends `// indirect`.

**The exemption table holds NO same-class defect today.** All 16 libraries run:
12 rc=0, 4 rc=1 — exactly the table. Every recorded anchor is present in its own
library's observed error, and no `…/go/*@v0.0.0` appears in any of the four.

**The network discriminator survives both outage shapes**, including the partial
one I had not asked for: with `github.com` blackholed but the proxy reachable, a
healthy library still returns rc=0 (no false red), while an unreplaced sibling
produces `invalid version: git ls-remote … Failed to connect`, which carries the
manifest marker AND matches the sibling regex. Manifest-first ordering classifies
it as code, correctly.

**The break-test names the right fix**, and test 18 stays GREEN over it — `forge`
does not require `envelope` directly, so test 21 is genuinely carrying the weight.

### Two LATENT gaps — not live defects, but the guard is for the NEXT library

**F1 (MEDIUM). The same-class regex contradicts this repository's own naming rule.**

```
SIBLING_FAILURE_PATTERN="github\.com/gophersys/libs/go/[a-z]+@v0\.0\.0"
```

`.claude/rules/11-naming.md` defines the slug as `word ("-" word)*` with
`word := [a-z][a-z0-9]*` — **digits and hyphens are legal**. A future `go/oauth2`
or `go/agent-session` at `v0.0.0` is not matched. Two wrong results follow: on the
table, the arm stays silent and the prose decides again — the exact state
objectstorage and orchestrator were in; off the table, the `unexpected` arm prints
*"a replace is NOT the answer"* when a replace is precisely the answer.

The direct scan does not compensate: its awk is name-agnostic but reads DIRECT
requirements only, and this class is transitive.

**F2 (MEDIUM). The 8-character floor does not close the class it is documented to
close.** `github.com` is 10 characters and appears in 3 of the 4 exempt libraries'
real errors. Proven by break-test — anchor set to `github.com`, suite **stays
green**. My sentence claiming the floor "closes the degenerate case" overstates;
the code comment ("closes the degenerate cases") is the honest one.

**Bounded, and this matters:** the same-class arm reads the OBSERVATION, so a
generic anchor can hide only a drifted DIFFERENT-class reason — never a sibling
defect. That is the difference between a weakened guard and a broken one.

### Documentation findings, corrected above

The plan section is now marked superseded (8 go.mod files, not 2). My claim that
`1 stated no counter` is "honest" was wrong — the counter is UNWIRED, not
probabilistic. Two `## Proven` lines remain unreproducible: one cites a scratchpad
log from a previous session that no longer exists, the other names no command.

## Next

One more phase-2 pass for F1 and F2, so the guard holds for the next library
rather than only for this tree. Then the pull request.


## Phase 12 — both latent gaps closed (`d031cdd`), and a real defect found in the harness

**F1 — the pattern now follows the grammar, and is policed in BOTH directions.**
Transcribed from `11-naming.md`, reusing `SIBLING_PREFIX` with its dots escaped —
an unescaped `.` would have let `githubXcom/...` satisfy the arm:

```
SIBLING_SLUG_PATTERN='[a-z][a-z0-9]*(-[a-z][a-z0-9]*)*'
```

Two LOAD-TIME assertions fail if the transcription and the rule ever disagree
either way: it must ACCEPT a slug the rule permits and REJECT one it forbids.
Proven against the old pattern:

```
[test] the sibling-failure pattern rejects a slug 11-naming.md permits
       ('agent-session2'); it has drifted from the grammar it is transcribed from
```

**F2 — judged, not implemented blindly, and the judgement is the good part.** Plain
cross-library uniqueness would fire on this tree, because `dependencies` and
`errors` both legitimately fail on `testify`. The rule shipped instead:

> an anchor may match another red library's error ONLY IF that library records the
> SAME anchor.

Sharing a defect is not the fault; **recording a different defect from the one you
match** is. `testify` on both -> identical -> legal. `github.com` on
`objectstorage`, matching `dependencies`' error whose anchor is
`github.com/stretchr/testify` -> refused.

The length floor stays for the empty case only, redocumented as the loose proxy it
is. Stated bound, in the code: with exactly ONE red library the corpus is empty and
a generic anchor is unpoliced — and the same-class arm still holds there, so the
worst case remains a drifted different-class reason, never a hidden sibling defect.

**It caught itself reintroducing the class.** Adding the specificity arm broke
`exempt:wrong-reason`: swapping `errors`' anchor made `dependencies`' anchor
non-specific, specificity is checked first, so it claimed the failure — and **the
reason arm would have gone uncovered again, silently, while still scoring
"proven"**. Re-aimed at `orchestrator`, which shares its defect with nobody, and
all ten stimuli verified to fire ten distinct arms.

### A REAL DEFECT IN THE HARNESS — filed as task #71

The first full run came back rc=1. It checked the disk before believing the red —
`No space left on device` — and then found something worse in the log:

```
mkdir: cannot create directory '.../tree.caUzdC/objectstorage': No space left on device
```

for FOUR libraries, **while `copy_module_tree` reported SUCCESS**. It is reached
through `MODULE_TREE="$(mutant_tree ...)" || return 2`, and a `||`-left position
suppresses errexit all the way down — the same suppression this file already
documents at lib.sh's phase-gate call site, and the same one `.ci/ctl.sh:74` had.

So the loop counted ITERATIONS rather than successful copies, cleared its `-gt 0`
floor, and returned a **silently truncated tree**. A scan over three libraries
believing it read sixteen, reporting a pass.

Fixed: every command carries its own `|| die`, and **the floor is COMPLETENESS,
not "more than none"**. Proven with a 200k tmpfs `/tmp`:

```
rc=1  [test] could not copy agentsession/go.sum into /tmp/.../tree.1oIprj (check free space)
```

The phase-8 hardening also earned its keep during that run: five unbuildable
stimuli were named individually and the summary still printed.

```
bash go/_ctl/lib_test.sh   rc=0   188s   21 hold; 20 of 21 proven able to fail
                                          across 39 counter-stimuli
bash ./ctl.sh validate     rc=0   17 project records hold; 3 mutants caught
shellcheck                 rc=0
```

188s against the ~115s I quoted: the VM is shared and under emulation. An honest
measurement, not a fast green.

## Next

Focused verification of the two new arms — this branch already passed a full
adversarial pass on correctness, and these changes close the two gaps that pass
named. Then the pull request.
