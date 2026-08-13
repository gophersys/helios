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
