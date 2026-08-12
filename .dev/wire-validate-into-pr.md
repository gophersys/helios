# wire-validate-into-pr

phase:    red
repo:     gophersys/libs
branch:   ci/wire-validate-into-pr
worktree: ~/code/.worktrees/libs-wire-validate
pr:       -
attempt:  0/2

## Goal

`go/_ctl/lib.sh` holds every gate verb in this repository, and nothing in CI runs
it. The pull request tier runs `ci-drift` and `affected-gate-fast`; the affected
gate skips `go/_ctl` outright, and no tier runs `validate` at all. The new shell
suite from libs#6 therefore runs only by hand.

That is the reason the golangci defect shipped, and the reason libs#6 went green
in 8 seconds while checking nothing.

When this is done, `validate` runs on every pull request, so the shell suite and
the `_ctl` shellcheck coverage gate real changes.

## Plan

APPROVED by Mateo, 2026-08-12, before going to sleep. He asked for the feature
to be finished and every repository cleaned up.

**The earlier reading was wrong, and I repeated it.** It said the 3 template
failures were false positives because those dispatchers have no local `usage()`
and delegate to a sourced one. The planner opened the files: `persistence/ctl.sh:43`
and `clients/go/ctl.sh:44` DO hold a local `usage()` listing exactly the right
verbs. The parser misses them for 2 different reasons — it matches only
`^function usage() {` and they use the POSIX `usage() {`, and it matches only
`cat <<EOF` and they use `cat <<'EOF'`. Only 1 of the 3 matches the sourced-usage
story.

**The parser is also blind to REAL drift.** With an empty usage list, its
usage-to-targets loop is vacuously green. So it never reported that
`templates/go/http-gateway/ctl.sh` documents AND dispatches `openapi`,
`verify-openapi` and `gen-client` with no matching `project.json` target. Fixing
the parser turns 17 false messages into 4 true ones.

The real count is 17 messages / 4 counted failures, not the 5 recorded at intake.

**The fix: ask the program, do not parse it.** Replace the source-text scraper in
`ctl.sh` with `bash <ctl> help`, and take the verbs from its output. A `help` that
exits non-zero, or yields no verbs, is its OWN counted failure naming the script —
never a silent empty list.

Prior art in this repository: `.ci/ctl.sh:200 cmd_list_verbs` (`__verbs`), which
`cictl` already runs rather than reading case arms. This adopts that rule. Three
regex patches would be the band-aid, and a 4th dispatcher shape would defeat them.

Files: `ctl.sh` (the parser, plus `require_cmd timeout`, plus shellcheck over
`*_test.sh`), `ctl_test.sh` (new, 6 tests), `.ci/project.json` (+ci-drift target),
`templates/go/http-gateway/project.json` (+3 real targets), `.ci/ci.contract.yaml`
(pr verbs become ci-drift, validate, affected-gate-fast), and the 2 REGENERATED
workflows.

## Cost, and the thing to expect

The pr tier is 8 seconds today. Measured locally: shellcheck 1.3s, jq+drift 0.6s.
The cost is `go/_ctl/lib_test.sh`, which runs 8 concurrent REAL golangci-lint
invocations. Estimated ~90 seconds total in CI, and the planner marked that
estimate UNVERIFIED — the first CI run settles it. Against a 15-minute timeout.

**Expect the lane to go red on the first run.** `lib_test.sh` has never executed
on an ARC runner. That is the intended outcome of this change, not a defect.

## Proven

- The 4 drift failures reproduce on this branch, in an ubuntu 24.04 container
  with bash 5.2, before any change:
  - `.ci/ctl.sh: usage entry 'ci-drift' missing from project.json targets`
  - `templates/go/http-gateway/clients/go/project.json: target 'generate' missing from ctl.sh usage`
  - `templates/go/http-gateway/persistence/project.json: target 'generate' missing from ctl.sh usage`
  - `templates/go/http-gateway/persistence/project.json: target 'verify' missing from ctl.sh usage`
  - `templates/go/http-gateway/project.json: target 'build' missing from ctl.sh usage`
- `bash ./ctl.sh validate` cannot run on this host: `/bin/bash` is 3.2.57 and has
  no `mapfile`. The container is the only way to run it here.

## Blocked

Nothing yet.

## Next

Phase 2: dev-test-author writes the 6 tests and proves each fails.
