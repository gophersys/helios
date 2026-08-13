# every-sibling-is-replaced

phase:    plan
repo:     gophersys/libs
branch:   fix/every-sibling-is-replaced
worktree: ~/code/.worktrees/libs-replaces
pr:       -
attempt:  0/2

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

## Next

Phase 2 — the red test, proven to fail for the right reason and to name both
offenders and their unreplaced modules.
