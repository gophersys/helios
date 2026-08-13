# verb-conservation records

One file per project that sources a shared gate library. Each file is the recorded
**observable behaviour of every verb** that project's `ctl.sh` dispatches:

- the verb's **exit code**, and
- the **argv of every external gate tool** it invoked, in order, with the named
  environment (`RAPID_CHECKS`, `EDEN_LOAD_N`, `GOWORK`, `GOFLAGS`, `CGO_ENABLED`)
  that came with it.

Two profiles are recorded per project:

| profile | every gate tool exits | what it pins |
|---|---|---|
| `pass` | 0 | the happy-path tool sequence — flags, tags, order |
| `fail` | 1 | **failure propagation** — which verbs and which phases still report success |

The `fail` profile is the half that matters most here: it is where a gate that reports
success over a red verb becomes visible. Read `templates/go/http-gateway.txt` and
`go/errors.txt` under `profile=fail` — all four phases of both now exit 1.

That agreement is new. It is recorded below, because a golden that changes without a
stated reason is indistinguishable from one bent to make a test pass.

## Re-record log

A golden moves only in a commit that says why. One entry per re-record.

### 2026-08-12 — `go/workspaceprovider.txt`, a mount-path artifact removed

Not a verb change. This record had been captured with the worktree mounted at `/w`,
and the normalizer's repository rule was unanchored, so the 2 characters `/w`
matched **inside** `<sandbox>/workspaceprovider-cover.AbC123` and the record froze
`<sandbox><repository>orkspaceprovider-cover.<tmp>`. `go/workspaceprovider` is the
only project whose name begins with `w`, so exactly 1 of 17 records was affected and
the other 16 hid it.

The record therefore **passed at `/w` and failed at the real worktree path** — the
one thing `normalize` exists to prevent. The rule is now anchored to a path boundary
(`verb_conservation_test.sh`, `normalize`), the record was re-captured, and 16 lines
changed, every one of them a `<repository>` artifact being repaired. The check
skeleton — verb headers, exit codes, and the tool name of every invocation, in order
— is byte-identical across the change in **both** profiles, so no verb moved. The
record now holds identically with the tree mounted at `/w` and at its real path: 17
records, 3 mutants caught, from both.

### 2026-08-12 — `templates/go/http-gateway.txt`, the one-gate-library feature

`templates/_ctl/template.sh` reported PASS over failing verbs for its whole life, and
the previous revision of this record froze that as fact. The gate was fixed, so the
record moved. **Every difference is the gate becoming honest; none is a check being
dropped.**

`profile=pass` — 3 lines changed, and **no check was lost**:

```
-hnslint  ./...
+hnslint  <sandbox>/tree/templates/go/http-gateway
```

`./...` is a Go package pattern and hnslint takes directories, so it answered
`./...: not a directory` and exit 1 without inspecting a file. That is the same
argument `go/_ctl/lib.sh` already passed. The safety property was verified
mechanically before re-recording, not by eye: the pass profile's **check skeleton**
— every verb header, every exit code, and the tool name of every invocation, in
order — is byte-identical across the change, and the per-tool invocation counts are
unchanged (`hnslint` 3 before, 3 after). The 3 lines above are the only differences
in the whole pass half.

`profile=fail` — 2 exit codes moved and 8 tool lines went away. Every one is a
consequence of a red verb finally being propagated:

| what moved | why |
|---|---|
| `phase-gate architecture` exit 0 → 1 | the phase built its verdict with `rows+=("$?") \|\| rc=1`; an append always succeeds, so `rc` was never set and the phase was GREEN whatever its dimensions did |
| `phase-gate testing` exit 0 → 1 | same class: `_gate_run` ran each verb as an `if` condition, where bash suppresses errexit into the subshell, so a failing verb returned 0 |
| bare `phase-gate` drops 5 tool lines | `all` short-circuits on the first red phase, and architecture is now red, so the downstream phases are never reached |
| `lint` inside a gate drops 1 `go vet ./...` in implementation and 1 in qa | `lint` now stops at the failing `gofumpt -l .` instead of continuing |
| `cover` drops `go tool cover` | `cover` now stops at the failing `go test -coverprofile` |

Nothing here changes what the gate runs when the tools are green; it changes only
what it does when they are not. The other 16 project records held byte for byte
across the same change, and all 3 planted mutants were still caught.

Count check, because this file exists to make a re-record auditable: the table has
5 rows and the middle one covers 2 lines, so it enumerates **8**, and the diff
agrees — `git show dda26cf -- templates/go/http-gateway.txt | grep -E '^[-+][^-+]'`
is 13 removals, of which 3 are the `hnslint` lines in the pass half and 2 are
`exit 0`, leaving 8 tool lines.

### 2026-08-13 — the 16 `go/*.txt` records, `phase-gate all` becoming honest

`go/_ctl/lib.sh` ran the four phases as `phase_architecture || { … }` — the
`||`-LEFT position, where bash suppresses errexit and carries the suppression down
through the phase function into `_gate_run`'s `( set -e; "$@" )` subshell. That is
byte-for-byte the defect the entry above fixed in `templates/_ctl/template.sh`, at
the one call site that fix did not reach. It is fixed; the records moved.

**The move is 1 line per record, the same line in all 16, and only there:**

```
 ### verb phase-gate            (profile=fail, no argument, so `all`)
 exit 1
 go	build ./...
 gofumpt	-l .
-go	vet ./...
```

That `go vet ./...` only ever ran BECAUSE errexit was suppressed. `cmd_lint` reads
`unformatted="$( … gofumpt -l . )"` first; with errexit live the verb stops there
and never reaches vet. The same record already says so twice — its own
`### verb lint` and `### verb maintainability` blocks in `profile=fail` are

```
### verb lint            ### verb maintainability
exit 1                   exit 1
gofumpt	-l .             gofumpt	-l .
```

— both stop at `gofumpt`. Only the `phase-gate` block ran on, because only it had
the suppression. The 16 records now agree with themselves.

**`templates/go/http-gateway.txt` did not move at all.** It has had this fix since
`e400c8b`, so there was no suppression left in it to remove. A record that stays
byte-identical while its 16 siblings each drop the same line is the strongest
evidence available that the cause is the fix and not the harness — and the
implementer measured the other direction too: with `go/_ctl/lib.sh` stashed, the
suite returns to `17 project record(s) hold; 3 mutant(s) caught`.

**No check disappeared from the `pass` profile**, and that was verified before
re-recording rather than assumed. Both revisions were split at `profile=fail` and
the `pass` halves diffed alone: **byte-identical in all 17 records**, gate-tool
line counts unchanged in every one (61 → 61 for the template, 1239 → 1239 summed
across the 17). A short-circuit on a FAILING tool is honesty; a check vanishing
when everything passes would be a regression wearing honesty's clothes, and it is
the pass half that would show it.

Four properties of the `fail` half, each confirmed on its own: 16 records touched,
exactly 1 line removed from each (`git diff --numstat` reads `0 1` for all 16),
**nothing added anywhere** (0 `+` lines in the whole diff), and **no exit code
changed** (0 `exit ` lines touched). The verbs still fail; one of them just stopped
running a tool it could only ever reach through a suppressed error.

### 2026-08-13 — the 16 `go/*.txt` records, the substrate lanes gaining a stated budget

`go/_ctl/lib.sh` ran `integration`, `lifecycle`, `load` and `_cover_profile` with no
`-timeout`, so **Go's own 10 minutes per package was the budget nobody chose**. The
planner measured `workspaceprovider/kubernetesadapter` at 601.3s isolated / 544.1s
in-lane against that 600.0s wall — a coin flip at 91-100% of it, which is why it read
as flake rather than as a limit. `EDEN_SUBSTRATE_TIMEOUT` gives the lanes a number they
state out loud, and the records moved.

**Every changed line is an argv GAINING a flag. Nothing was removed, and no exit code
moved.** 320 removals and 320 additions, and each removal is byte-identical to an
addition once the new flags are stripped from it — `0` removed lines are left over.
All 640 changed lines begin `go<TAB>test`; `0` are an `exit ` line, a `### verb`
header, or another tool.

**4 argv shapes, and no fifth.** Reduced over the per-lib coverprofile name, the
`EDEN_LOAD_N` scale and the budget itself, the added lines collapse to exactly:

```
go	test -tags integration ./... -count=1 -timeout=<T> -v
go	test -tags lifecycle ./... -race -count=1 -timeout=<T>
go	test -tags load ./... -race -count=1 -timeout=<T> EDEN_LOAD_N=<N>
go	test -tags <COVERTAGS> -coverpkg=./... ./... -covermode=atomic -coverprofile=<P> -count=1 -timeout=<T> EDEN_LOAD_N=<N>
```

(One line each, tab-separated after `go`, exactly as the record spells them.)

| shape | why it moved |
|---|---|
| `integration` | the lane the measurement implicates; it also gains `-v`, and only it |
| `lifecycle`, `load` | the other two lanes that stand up real substrate — the same class, so the same budget |
| the coverage run | `_cover_profile` had the identical omission, and `cover-floor` is a dimension of **both** `phase-gate testing` and `phase-gate qa`; a cluster lib puts `integration` in `EDEN_COVER_TAGS`, so this run stands up the same clusters |

`<COVERTAGS>` is `lifecycle load` or `lifecycle load integration` per the lib's own
`EDEN_COVER_TAGS`. That split is **pre-existing** and appears unchanged on both sides
of the diff.

**20 lines per record, 10 in each profile, and the same 7 verbs every time** — the
5 lanes on their own, plus the 4 the `testing` phase re-runs and the 1 the `qa` phase
does:

```
cover 1   cover-floor 1   integration 1   lifecycle 1   load 1
phase-gate testing 4      phase-gate qa 1              = 10 per profile
```

Identical in `pass` and `fail`: `160` changed lines in each half, `16` records × `20`.
The `fail` half moving in lockstep with `pass` is the tell that this is a flag being
added to a command, not a verb changing what it does when a tool goes red.

**`-timeout=25m` appears in exactly 2 records** — `go/orchestrator.txt` and
`go/workspaceprovider.txt`, the 2 libs that stand up clusters and set the override in
their own `ctl.sh`. The other **14** carry `-timeout=10m`, which is Go's own default,
so those libraries change behaviour not at all — only the number stops being implied.
No record carries both, and there is no third value. (`--timeout=180s` also appears in
these files: it is golangci-lint's own long-standing flag, on `0` `go test` lines, and
it is on neither side of this diff.)

> **Superseded the same day, in part.** The orchestrator override was dropped hours
> later and that record is back at `10m` — see the last entry in this log for why. `25m`
> now appears in **1** record, `go/workspaceprovider.txt`, and 15 carry `10m`. The
> paragraph above is left as it was written: it records what was true at that
> re-record, which is what this log is for.

**`-v` appears on the `integration` shape and nowhere else** — 64 lines, all
`-tags integration`, `0` on lifecycle, load or the coverage run. It is deliberate and
narrow: `go test -v` prints each test's own elapsed time, which is the per-test cost
baseline the lane has never had, and which the deferred real fix (wiring the shared
cluster the harness already advertises through the dead `harnessConfig.perTest`) will
need in CI to prove it worked.

**`templates/go/http-gateway.txt` did not move.** It sources
`templates/_ctl/template.sh`, a different gate library that this change does not
touch. Its `integration` verb records `go	test -tags integration ./... -race
-count=1` — a *different* argv from the one the 16 go libraries share, which is the
point: the template lane was never running the command that was fixed, and it carries
no `go test -timeout` at all (its only `--timeout=180s` is golangci-lint's). A record
that stays byte-identical while its 16 siblings each gain the same 4 shapes bounds the
blast radius to the library that was edited.

### 2026-08-13 — `go/orchestrator.txt` back to `10m`, because its own gate is red on main

**This is not an oversight, and a reader finding orchestrator at the default should not
read it as one.** The `25m` override was dropped from `go/orchestrator/ctl.sh`, so the
library takes the shared default again and its record follows.

CI ran the pr tier and `affected-gate-fast` went RED on `go/orchestrator` — 5 of 5
dimensions, `go build ./...` among them, with `go: updates to go.mod needed; to update
it: go mod tidy`. **The control was run before anything was changed**: a detached
worktree at `origin/main`, same command, same container, produced the identical summary
and the identical message. **Surfaced, not caused.**

The cause is pre-existing manifest drift, and it is visible in the two files without
running anything:

```
go/orchestrator/go.mod:13   github.com/jackc/pgx/v5 v5.7.6
go/orchestrator/go.mod:107  github.com/gophersys/libs/go/secrets v0.0.0 => ../secrets
go/secrets/go.mod:10        github.com/jackc/pgx/v5 v5.10.0
```

The graph already demands a raise the manifest has never taken. Fixing it means shipping
a production Postgres-driver upgrade, which has no business riding inside a timeout
change — so orchestrator's `25m` returns with the drift fix, where the pgx raise gets
reviewed as the production change it is.

What made this visible at all is the override itself: setting `EDEN_SUBSTRATE_TIMEOUT`
in `go/orchestrator/ctl.sh` is what made the library *affected* for the first time. That
is the plan's own stated risk — a change to `go/_ctl/lib.sh` alone gates zero libraries —
working exactly as written. It just found a defect underneath.

**The move is 20 lines in 1 record, and every one is the same line with a different
number.** `git diff --numstat` reads `20 20`; every removed line is byte-identical to an
added line once `25m`/`10m` is masked; `0` removed lines are not a `25m` line, `0` added
lines are not a `10m` line; `0` `exit` lines and `0` `### verb` headers moved; all 40
changed lines are `go<TAB>test`. No argv gained or lost a flag — only the budget's value
changed.

**`go/workspaceprovider.txt` still says `25m`, on all 20 of its lines, and did not appear
in the diff.** That matters more than the orchestrator move: if both records fell to
`10m` the knob would be doing nothing, and the override mechanism would be untested by
anything. `go/workspaceprovider` passes 5 of 5 on this branch, so the substrate tier
still exercises this change through a library that actually runs it.

Counted over the whole of `testdata/`, `-timeout=25m` is on **20 record lines, all of
them in `go/workspaceprovider.txt`** — 1 library, as intended. (A `grep -rc` over
`testdata/` returns 21: the 21st is prose in this file, not a record.)

## These are not edited by hand

`verb_conservation_test.sh` (repository root) diffs a live capture against them on
every run, and re-records them only when asked:

```sh
bash verb_conservation_test.sh                    # verify all projects, then the mutants
bash verb_conservation_test.sh go/errors          # verify one project
EDEN_CONSERVATION_RECORD=1 bash verb_conservation_test.sh   # RE-RECORD, then review the diff
```

Re-recording is the same discipline as `ctl.sh bench-record` and
`ctl.sh apidiff-record`: a deliberate, reviewed commit. A diff you did not intend is
a verb whose behaviour moved.

The capture runs against a copy of the project under `mktemp -d`, with every gate tool
replaced by a recording stub, so it touches no real tool, writes nothing into this
tree, and depends on nothing the host has installed. Run it inside
`ghcr.io/gophersys/base` — a host bash older than 4 is rejected rather than worked
around.
