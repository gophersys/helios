# shellcheck-floor

phase:    plan
repo:     gophersys/infrastructure
branch:   ci/shellcheck-floor
worktree: ~/code/.worktrees/infra-shellcheck-floor
pr:       -
attempt:  0/2

## REMINDER: delete this .dev file in the FINAL commit before merge; prove gone with git cat-file -e.

## Goal
The infra shellcheck gate proves no coverage: it goes green over ZERO files. When fixed, both the
CI shellcheck job and `ctl.sh validate` FAIL loudly if they find no scripts to lint (a floor),
instead of logging "shellcheck clean" over nothing — so a future path narrowing (renamed dir, wrong
path) that silently lints fewer/zero scripts turns the gate red instead of a false green.

## Proven (verification sweep, 2026-08-14)
- `.github/workflows/validate.yml:99` shellcheck job: `find . -name '*.sh' … -print0 | xargs -0 -r
  shellcheck`. `-r` (--no-run-if-empty) → empty list runs shellcheck 0 times, exits 0. Reproduced:
  `printf '' | xargs -0 -r shellcheck; echo $?` → 0 (shellcheck did NOT run). No floor/count step.
- `ctl.sh:157-168` cmd_validate: `for sh in "${sh_files[@]}"` loop; empty array → 0 iterations,
  `sc_fail` stays 0 → logs "shellcheck clean (strict mode)" (line 165) — a pass over nothing. Line
  150 counts (`checked N bash script(s)`) but never fails on 0.
- Today `find` matches 19 files, so LATENT — but nothing catches a future narrowing to zero.

## Fix direction (planner to make concrete)
Add a FLOOR to BOTH spots: count the .sh files found; if zero, FAIL naming it ("the shellcheck job
found no scripts, so it linted nothing"). ctl.sh cmd_validate: assert `${#sh_files[@]} -gt 0` before
the loop (or fail if 0 after). Workflow job: capture the file list, assert non-empty, then lint —
e.g. `mapfile -d '' files < <(find … -print0); [ ${#files[@]} -gt 0 ] || { echo "no scripts"; exit 1; }
shellcheck "${files[@]}"`. Do NOT keep `xargs -r` (it is the swallow). Keep full strictness.

## Testability (planner MUST resolve)
- ctl.sh floor IS testable: run `ctl.sh validate` against a tree with NO .sh files → must exit non-zero
  with the floor message. Does infra have a ctl_test.sh / validate self-test to hook into, or is a new
  test fixture needed? The planner names the mechanism.
- The workflow YAML floor is harder (no live runner). Options: (a) extract the shellcheck-floor logic
  into a small script `scripts/lint-shell.sh` that BOTH the workflow AND ctl.sh call (one home,
  testable), or (b) prove the workflow step's floor by running its exact `run:` block locally against
  an empty dir. Planner recommends the house way (infra .claude/rules/*, verify-structure conventions).

## Conflict (revised hold)
Shares validate.yml + ctl.sh with open PR #175 (feat/mini-buildx), but DISJOINT regions (#175:
validate.yml ~65-80 verify-buildx step + ctl.sh ~196-320 verify_* funcs; #57: validate.yml ~76-99
shellcheck job + ctl.sh ~150-168 cmd_validate). Different hunks → git auto-merges. #175 is
Mateo-blocked, so #57 proceeds independently; whichever merges second gets a clean update-from-main.

## Blocked
Nothing. Non-Mateo (CI hardening, not a contract/chart change).

## Next
dev-planner: read infra .claude/rules/* + verify-structure conventions; decide the one-home approach
(a shared `scripts/lint-shell.sh` vs inline floors in both), name the test mechanism for the ctl.sh
floor, and give the red/green recipe. Then approve.
