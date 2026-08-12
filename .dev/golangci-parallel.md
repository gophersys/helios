# golangci-parallel

phase:    plan
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

AWAITING MATEO'S APPROVAL. Written by `dev-planner`, phase 1.

**The fix is a config key, not a CLI flag.** `run.allow-parallel-runners: true`
in `.golangci.yml` is discovered by all 4 call sites at once, so the collision
closes in 1 line at 1 home. A CLI flag would have to be repeated at each site.

Files:
1. `.golangci.yml` — add `allow-parallel-runners: true` under `run:`. This alone
   fixes the collision everywhere.
2. `go/_ctl/lib.sh:158` — branch on the exit code instead of asserting a cause:
   0 pass, 1 "found issues", anything else "failed to run (exit N) — not a lint
   finding".
3. `templates/_ctl/template.sh:150-151` — the identical wrong handler, a second
   home. Aligned, or the template ships a message known to be false.
4. `go/_ctl/lib_test.sh` — new. The repository's first shell test.
5. `ctl.sh` — widen `find_all_ctl_scripts` so `_ctl/*.sh` and `*_test.sh` are
   covered.

**nx.json is the wrong place.** `parallel: 10` governs every task in every
language. Serialising all of them to work around 1 tool's file lock pays a
monorepo-wide cost, and it is the wrong repository: a standalone libs clone and 2
hand-run `ctl.sh` still collide.

**Fault 2 is in scope, same pull request.** Exit 3 also means bad config, a panic
or an OOM kill. Fixing only the collision leaves the lie in place for the next
cause. It is also the only half that is deterministically testable.

5 tests, each with the mutation that makes it fail:
  1. a collision (stub exits 3) is NOT reported as findings
  2. real findings (stub exits 1) ARE still reported as findings
  3. a clean run (stub exits 0) passes
  4. 8 concurrent REAL golangci-lint runs produce no collision
  5. `golangci-lint config verify` accepts the shared config

## Verified by the planner, by running it

- golangci-lint 2.12.2 exit codes: 0 clean, 1 issues found, 3 run failure.
- Without the key: 3 of 8 concurrent runs collided. With it: 8 of 8 clean.
- Typo check: `allow-parallel-runner` (singular) exits 3; the correct spelling
  exits 0. YAML accepts the typo silently, so test 5 is what catches it.
- No shell test harness exists anywhere in libs: 0 `*_test.sh`, 0 `.bats`.

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

Waiting for Mateo to approve the plan, and to answer 1 open question: whether to
wire the new test into CI in this same pull request.

## The risk that matters most

`.ci/ctl.sh:96` explicitly skips `go/_ctl`, and line 98 skips the repository
root. libs' pull request CI runs only `ci-drift` and `affected-gate-fast`. So
`go/_ctl/lib.sh` — the file that holds EVERY gate verb — is gated by nothing
today, and root `validate` never runs in libs CI.

That is why this defect shipped. It also means a new test would be believed and
never executed unless it is wired in.

## Next

STOP. Mateo approves or rejects the plan.
