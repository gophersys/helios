# golangci-parallel

phase:    submit
repo:     gophersys/libs
branch:   fix/golangci-parallel
worktree: ~/code/.worktrees/libs-golangci-parallel
pr:       6
attempt:  0/2

## Goal

`golangci-lint` refuses to run 2 instances at once. Eden's `nx.json` sets
`parallel: 10`, so the affected-gate starts many at the same time and they
collide. The gate then prints `golangci-lint found issues`, which is not what
happened, and the reader looks for lint findings that do not exist.

When this is done, a parallel gate run lints cleanly, and a failure says which
failure it was.

## Plan

APPROVED by Mateo on 2026-08-11, including the CI wiring in the same pull
request. Written by `dev-planner`, phase 1.

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

## Proven — phase 3, green

Re-verified by the orchestrator after the fixes, exit code read directly with no
pipe: `bash go/_ctl/lib_test.sh` -> rc 0. `shellcheck -S style` over all 4 shell
files -> rc 0. Tree clean, 11 commits on the branch.

`bash go/_ctl/lib_test.sh` -> rc 0, "5 test(s) hold; 4 of 5 proven able to fail;
1 stated no counter".

An earlier version of this line quoted "all 5 test(s) hold, and each is proven
able to fail". That sentence overstated the suite: `t_concurrent_lints_do_not_collide`
declares no counter-stimulus, so it is not proven able to fail. The suite now
COUNTS the proof instead of claiming it, and this line quotes what it really
prints. The exit-3 arm now prints
`golangci-lint failed to run (exit 3) — a run failure, not a lint finding`.

`shellcheck -S style ctl.sh go/_ctl/lib.sh templates/_ctl/template.sh` -> rc 0.
`cd go/errors && bash ./ctl.sh lint` -> `0 issues.` rc 0. A real library still
lints clean under the new config and the new handler.

`bash ./ctl.sh validate` in the container -> **rc 1, 4 pre-existing issues**. The
gate FAILED. Its parts are listed below because they are informative, but the
exit code is the result, and an earlier version of this section listed the parts
without it. The 4 issues pre-date this branch, proven by running the same
container against a pristine `origin/main`: the same 4, byte for byte.

`bash ./ctl.sh validate` CANNOT run on this host: /bin/bash is 3.2.57 and has no
mapfile, so the pre-existing script dies rc 127. The implementer built an
ubuntu 24.04 container with bash 5.2 and ran it there: 29 scripts shellchecked
including the 4 `_ctl/*.sh` that were never checked before, 25 project.json
parse, the new suite green.

## Proven — phase 2, red

`bash go/_ctl/lib_test.sh` -> EXIT 1, "4 failure(s) across both phases".

- `t_a_collision_is_not_reported_as_findings` RED. A stub exiting 3 with the real
  collision text produces `[error] golangci-lint found issues`. That is the
  defect, seen directly.
- `t_the_shared_config_is_schema_valid` RED. The key is absent from
  `.golangci.yml`. Its counter-arm proves the schema half works: the misspelling
  gives `additional properties 'allow-parallel-runner' not allowed`.
- `t_concurrent_lints_do_not_collide` RED. 3 of 8 real golangci-lint 2.12.2 runs
  exited 3. Red on 6 of 6 isolated runs. It is a lock race, so it is stable here
  and not guaranteed on a slower host.
- `t_real_findings_are_still_reported_as_findings` GREEN in phase 1, RED in phase
  2: the same test passes under exit 1 AND exit 3, because lib.sh prints 1
  message for both. The blindness, named.
- `t_a_clean_run_passes` GREEN, and correct to be green. A conservation guard
  against the fix over-correcting. Its counter-arm fails as it must.

The test author proved the GREEN direction out of tree, without touching the real
config: a temp copy with the key appended gave `config verify` exit 0 and 8 of 8
concurrent runs clean.

`shellcheck -S style go/_ctl/lib_test.sh` -> exit 0.

## Proven — phase 0

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

Nothing. The plan is approved and the CI wiring is in scope.

## The risk that matters most

`.ci/ctl.sh:96` explicitly skips `go/_ctl`, and line 98 skips the repository
root. libs' pull request CI runs only `ci-drift` and `affected-gate-fast`. So
`go/_ctl/lib.sh` — the file that holds EVERY gate verb — is gated by nothing
today, and root `validate` never runs in libs CI.

That is why this defect shipped. It also means a new test would be believed and
never executed unless it is wired in.

## What the implementer is bound to

The assertions bind to these. Breaking either turns a test red for the wrong
reason:
1. the failure message on exit 3 must NAME the code — it must match `exit[^0-9]*3`
2. the string `golangci-lint found issues` must be ABSENT on exit 3 and PRESENT
   on exit 1

## Phase 4 — refuted, then fixed

`dev-verifier` returned 8 findings. It broke the fix in 2 places and confirmed the
right tests went red: the config key set to false gave 5 of 5 runs red, and the
reverted `case` block gave 2 tests red including the counter-arm.

Fixed, each with the command that proves it:
1. HIGH. `project.json` inputs did NOT include `.golangci.yml` or the fixture, so
   Nx could serve a cached green after a change to the very file this work is
   about. The implementer's own claim to the contrary was false. Now covered, and
   proven by expanding the globs and checking every path the suite reads.
2. `ctl.sh validate` passed silently when it found 0 test suites. Now a failure:
   on a tree with no suite it reports 5 issues where it used to report 4.
3. A failed `cd` exited 1 and so read as "golangci-lint found issues" — the same
   lie, in the file that exists to delete it. It now names itself and exits 120,
   outside golangci-lint's 0-7 range and outside the shell's 126/127.
4. The suite's summary claimed "each is proven able to fail" when 1 test declares
   no counter. It now COUNTS: "4 of 5 proven able to fail; 1 stated no counter".
5. A provenance comment described a capture that no longer reproduces once the
   fix landed. Reworded, with a recipe that does.

ACCEPTED, not fixed: `templates/_ctl/template.sh` holds the same 8-line handler
as `go/_ctl/lib.sh`. The implementer measured before deferring: the 2 libraries
already share 22 function names and only 4 are byte-identical, so closing these 8
lines properly means creating the repository's first shared shell library and
moving all 22. That is a refactor of both gate libraries with its own proof
obligation. Moving 1 function to a third home while 21 stay duplicated would be
arbitrary. Recorded as debt.

## Decision, 2026-08-11

Mateo chose (b). This pull request lands the fix with the suite RUNNABLE but NOT
in the `pr` tier. The wiring follows in a separate pull request, after the 4
drift failures below are fixed. Recorded as task #32, because option (b) only
works if the follow-up actually happens — otherwise the suite gates nothing,
which is the failure this work exists to kill.

The implementer's change to `project.json` STAYS. The `validate` target is
cached, and its `inputs` did not list `_ctl/*.sh` or `*_test.sh`, so Nx would
have served a stale green after a change to the newly covered files. That is a
correct fix and it is in scope.

## The blocker that the decision defers

Wiring `validate` into the `pr` tier turns the lane red at once, for 4 drift
failures that pre-date this branch. The implementer proved they pre-date it by
running the same container against a pristine `origin/main`: the same 4, byte for
byte.

1. `.ci/project.json` has no `ci-drift` target, although `.ci/ctl.sh` implements
   the verb and the `pr` tier calls it. A genuine gap. Not the implementer's file.
2-4. 3 template `project.json` files report targets "missing from ctl.sh usage".
   FALSE POSITIVES. Those dispatchers hold no local `usage()`; they source
   `templates/_ctl/template.sh` and call `template_usage`, which does list every
   target. The drift parser only reads `^function usage() {` in the dispatcher
   itself, so it sees an empty usage block.

Also found: `cictl` is not on PATH on this host. It is buildable from
~/code/cictl, and the implementer proved that build faithful — run over the
UNCHANGED contract it regenerates every workflow byte for byte against what is
committed. So regeneration is safe the moment the contract change is approved.

## Phase 6 — both checks pass, and the pass is worthless

`pr tier` and `merge tier` both went green in 8 SECONDS on a pull request that
changes 6 files. Read the log rather than the badge:

```
affected-gate-fast: phase-gate implementation over affected projects (base=origin/main)
skipping .: not a library (libraries are go/<name> or typescript/<name>)
affected projects had no gateable ctl.sh — clean no-op
```

Every file this pull request touches is at the repository root, in `_ctl/`, or in
`templates/`. None is `go/<name>` or `typescript/<name>`, so the affected gate
classified all of them as "not a library" and ran NOTHING.

So the green means: no library changed. It does not mean the change is good. The
5 tests, the widened shellcheck set and the new `_ctl` coverage were all skipped.

This is the same defect class the pull request exists to fix, demonstrated live on
the pull request that fixes it. It is also the mechanical answer to the question
"why did this defect ship": nothing was ever going to catch it.

`libs` has NO `pr-review` workflow — only `nightly.yml`, `on-pr.yml` and
`on-push.yml`. So there is no review verdict for this pull request, and the skill
says to say so rather than leave the field blank.

## Next

STOP. Mateo decides whether to merge on a green that ran nothing, knowing the
evidence is the local and container runs recorded above.
