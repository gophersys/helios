# golangci-parallel

phase:    intake
repo:     gophersys/libs
branch:   fix/golangci-parallel
worktree: ~/code/.worktrees/libs-golangci-parallel
pr:       -
attempt:  0/2

## Goal

`golangci-lint` refuses to run 2 instances at once. Eden's `nx.json` sets
`parallel: 10`, so the affected-gate starts many at the same time and they
collide. The gate then prints `golangci-lint found issues`, which is not what
happened, and the reader looks for lint findings that do not exist.

When this is done, a parallel gate run lints cleanly, and a failure says which
failure it was.

## Plan

Not yet written. Phase 1 delegates to `dev-planner`.

## Proven

- The defect is on 1 line, `libs/go/_ctl/lib.sh:158`:
  `( cd "$PROJECT_ROOT" && "$golangci_bin" run --timeout=180s ./... ) || { log_error "golangci-lint found issues"; exit 1; }`
  Read from the file. It carries 2 faults, not 1:
  1. no `--allow-parallel-runners`, so concurrent instances collide
  2. the handler asserts the cause. Any non-zero exit is reported as "found
     issues", including a collision, a timeout and a missing configuration file.
- `grep -rn 'allow-parallel-runners' libs/ nx.json` -> no match. The flag is set
  nowhere today.
- `grep -n 'parallel' nx.json` -> `"parallel": 10,` at line 4.

## Blocked

Nothing yet.

## Next

Run phase 1: delegate to `dev-planner`, write the plan here, and stop for Mateo.
