# mktemp-gnu-template

phase:    verify
repo:     gophersys/eden
branch:   fix/mktemp-gnu-template
worktree: ~/code/.worktrees/eden-mktemp-gnu-template
pr:       -
attempt:  0/2

## Goal
`scripts/assert-no-skipped-tests.sh:22` calls `mktemp -t assert-no-skipped-tests` — BSD
syntax. GNU mktemp in the CI container rejects it ("too few X's in template"), so the
harness-conformance job has exited 1 before running a single Go test on every run since
2026-08-10 (proven from run 32007839673, line 382). When this is done, the gate runs
tests again on both its trigger paths (`harnesses/versions.env`, `libs/go/agentsession/**`),
and a regression test proves the failure mode cannot silently return.

## Plan
plan: SELF-APPROVED (--auto). Risk weighed: Nx must map a scripts/-only change to the
new project or the lane runs nothing (same defect class again) — settled before PR with
`yarn nx show projects --affected --base=origin/main` in the container.

- Fix: scripts/assert-no-skipped-tests.sh:22 `mktemp -t assert-no-skipped-tests` →
  `mktemp -t assert-no-skipped-tests.XXXXXX` (eden's existing form, apps/agent-runtime
  ctl.sh:115,128, apps/agentgateway/ctl.sh:114).
- Tests (dev-test-author owns): scripts/assert-no-skipped-tests_test.sh — GNU-mktemp
  guard (exit 1 if not GNU, never skip); pass/skip/propagation/no-false-positive/usage
  cases against a stub `go`; scripts/mktemp-template_test.sh — repo-wide: every mktemp
  template carries ≥3 trailing X's (RED on today's tree).
- Wiring (dev-implementer owns): scripts/ctl.sh + scripts/project.json — `lint`
  (shellcheck) + `test` (run scripts/*_test.sh) as Nx targets; scripts/ is owned by no
  project today, which is why the dead gate survived 8 days.
- Sweep result (planner, reproduced in ghcr.io/gophersys/base): only 1 broken site;
  apps/agent-runtime, apps/agentgateway, apps/frontend forms are portable; .ci/ and
  .githooks/ contain no mktemp.
- Gates: shellcheck -S style; in-container scripts lint+test; yarn install +
  bash .ci/ctl.sh affected-check; CI fast lane runs the new project in the failing image.
- Out of scope: PR #4 rerun + omp drain verdict (S1); harness-conformance paths: change;
  unifying the 4 mktemp sites beyond the sweep rule.

## Proven
- `gh run view 32007839673 --log` line 382: `mktemp: too few X's in template
  'assert-no-skipped-tests'` then exit 1; harness install steps 1–7 succeeded first
  (discovery workflow wf_59ad5111, ledger agent + critic, 2026-08-18).
- RED (test author, commit 09467c5): `docker run --rm -v <worktree>:/w -w /w
  ghcr.io/gophersys/base:latest bash scripts/assert-no-skipped-tests_test.sh` → rc=1,
  4/5 cases FAIL, subject output IS the defect (`mktemp: too few X's in template
  'assert-no-skipped-tests'`); usage case green by design (arg check sits above line 22).
- RED: `... bash scripts/mktemp-template_test.sh` → rc=1, exactly 1 violation named:
  `scripts/assert-no-skipped-tests.sh:22`; 26 fixture rows + 4 portable sites, 0 false
  positives. Green proven against a patched throwaway tree (rc=0, 73 files / 7
  invocations / 0 violations).
- Mutant kills per assertion proven on copies (exit swap → propagation FAILs; SKIP grep
  deleted → skip FAILs; grep loosened → no-false-positive FAILs; usage exit 0 → usage
  FAILs; planted violation → scan names it).
- Fail-loud off-container: behaviour test exits 1 on macOS BSD mktemp naming the
  devcontainer, no skip. Static test runs identically on both (no guard, executes no mktemp).
- shellcheck -S style clean on both test files (host 0.11.0 rc=0, image 0.9.0 rc=0).
- PLAN CORRECTION (test author): the propagation case does NOT distinguish
  `${PIPESTATUS[0]}` from `$?` — equivalent mutant under the subject's pipefail. It
  proves only that go's exit code reaches the caller. Plan credit reduced accordingly.
- GREEN (implementer, commit c3b3436, 3 files +129/−1): in ghcr.io/gophersys/base —
  behaviour test rc=0 (5/5), sweep rc=0 (73 files, 7 invocations, 0 violations),
  `bash scripts/ctl.sh lint` rc=0 (6 scripts), `test` rc=0 (2 test scripts, stop-at-
  first-failure proven rc=3 in sandbox); shellcheck -S style rc=0 (0.11.0 host, 0.9.0 image).
- RISK SETTLED: `yarn nx show projects --affected --base=origin/main` → `repository-scripts`;
  `bash .ci/ctl.sh affected-check` rc=0 with "Successfully ran targets lint, test for
  project repository-scripts". Submodules initialized at pinned SHAs for yarn only;
  nothing staged; commit holds exactly 3 files.
- Static test in-container needs an identical-path mount (worktree .git is a pointer
  outside /w); behaviour test runs with the plain /w mount.

## Residue noted (out of scope here, carried to the board)
- .ci/ctl.sh has_nx fallbacks return 0 with a warning — green-that-checks-nothing class.
- .ci/ctl.sh:78 `validate` shellchecks only itself.
- tools/hnslint/ctl.sh:59 ends a lint pipeline with `|| true`.

## Blocked
-

## Next
Phase 1: dev-planner.
