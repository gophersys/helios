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

The `fail` profile is the half that matters most here. Read
`templates/go/http-gateway.txt` under `profile=fail`: `phase-gate architecture` and
`phase-gate testing` both exit **0** while every tool they ran exited 1. Read
`go/errors.txt` under the same profile: all four phases exit 1. That difference is
the defect `go/_ctl/lib.sh` already fixed and `templates/_ctl/template.sh` never
received.

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
