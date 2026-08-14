# shellcheck-floor

phase:    verify
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

## Plan — APPROVED (dev-planner + orchestrator, 2026-08-14)
ONE HOME: NEW `scripts/lint-shell.sh` (dev-implementer) — matches infra's verify-*.sh pattern (rule
40; verify-structure/verify-registry-paths/verify-exposure are each one script called by BOTH ctl.sh
+ validate.yml). It: discovers `.sh` once (bash 3.2-safe `while read -r -d ''`, NO mapfile), FLOOR
(0 files → exit 1 naming it), `bash -n` each, then `shellcheck "${files[@]}"` with findings VISIBLE
(the old ctl.sh hid them via >/dev/null). NO `xargs -0 -r` (the -r is the swallow). Missing shellcheck
→ exit 127 (FAIL-NOT-SKIP). Prints `lint-shell: linted N shell script(s)`.
- ctl.sh (dev-implementer): line 122 `require_cmd jq shellcheck`→`require_cmd jq`; replace the shell
  block (137-168) with `bash "$PROJECT_ROOT/scripts/lint-shell.sh" "$PROJECT_ROOT" || rc=1`.
- .github/workflows/validate.yml (dev-implementer): replace the shellcheck job body (92-99) with
  `run: bash scripts/lint-shell.sh` + a step `run: bash scripts/test-lint-shell.sh`. Confined to the
  shellcheck job (83-99).
- scripts/test-lint-shell.sh (NEW, dev-test-author): case suite mirroring test-verify-runner-queue.sh.

TESTS (dev-test-author, scripts/test-lint-shell.sh):
1. floor_fires_on_empty_tree — `lint-shell.sh "$(mktemp -d)"` exits ≠0 + "no shell scripts found".
2. a_violating_script_fails — mktemp dir w/ one SC2086-violating .sh → exits ≠0 AND the finding is in output.
3. lints_the_real_tree — `lint-shell.sh "$REPO_ROOT"` exits 0, count ≥1.
4. ctl_validate_uses_the_shared_linter — `bash ctl.sh validate` exits 0 + output has `lint-shell: linted`.
BAD FIXTURES under mktemp ONLY (never in the repo tree — the real gate would lint them red). Both new
.sh must be shellcheck-clean (the gate lints them).

RED framing: the NEW script/floor does not exist yet, so its tests fail (script absent / floor not
enforced); PLUS the current-bug reproduction stands: `printf '' | xargs -0 -r shellcheck; echo $?` → 0.
GREEN: implementer creates lint-shell.sh + wiring → all 4 cases pass; `ctl.sh validate` green; real
tree lints 21→23 files.

CONFLICT: DISJOINT vs #175 — #175 hits validate.yml @65 (manifests) + ctl.sh @196/256/273; this hits
validate.yml @83-99 (shellcheck job) + cmd_validate @117-176, and MOST logic moves to 2 NEW files.
Git auto-merges; second-to-land takes a clean update.

FOLLOW-UP (not this PR): the SAME `xargs -0 -r kubeconform` swallow at validate.yml:49 — same class,
different job/tool. Filed separately to keep this PR focused.

## Next
dev-test-author: write scripts/test-lint-shell.sh (4 cases above), prove RED (the floor script/behaviour
is absent; + reproduce the current xargs -r zero-file green). Ownership: test-lint-shell.sh →
dev-test-author; lint-shell.sh + ctl.sh + validate.yml → dev-implementer.
