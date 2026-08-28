# root-workspace

phase:    verify
repo:     gophersys/eden
branch:   refactor/root-workspace
worktree: ~/code/.worktrees/eden-root-workspace
pr:       -
attempt:  1/2
plan:     SELF-APPROVED — establish a small active-workspace boundary without changing product code.

## Goal

Make the repository root tell one simple truth: Eden product projects participate
in Nx; imported research and proofs-of-concept remain available as source but do
not enter the active project graph. Keep one short root command surface and delete
configuration that describes the former submodule/workflow estate.

## Plan

1. Add a fast structural test that rejects active Nx projects under `research/`
   or `poc/` and rejects stale submodule/workflow language in root configuration.
2. Replace the legacy fixture-by-fixture `.nxignore` with explicit inactive-tree
   boundaries and remove dead workflow inputs from the scripts project.
3. Tighten `ctl.sh` safety and keep its public verbs small.
4. Run only shell/JSON/structural checks; no builds or CI.

## Proven

- `cat package.json nx.json .nxignore ctl.sh` — the root still described imported
  repositories as submodules and `.nxignore` did not exclude research or PoCs.
- `find . -name project.json` — research currently contributes 29 Nx projects.
- RED: `bash scripts/root-workspace_test.sh` exited 1 with four failures:
  missing `research/**`, missing `poc/**`, retired-estate prose, and inactive
  project definitions able to enter the graph.
- GREEN: `bash scripts/root-workspace_test.sh` prints
  `root-workspace contract: PASS` after the two explicit boundaries replaced
  85 lines of submodule-era exceptions.
- `bash scripts/ctl.sh lint` shellchecked 11 scripts and passed.
- `bash scripts/ctl.sh test` ran two suites successfully, then stopped because
  `assert-no-skipped-tests_test.sh` deliberately refuses BSD `mktemp` and names
  the devcontainer as required. No build or container start was authorized for
  this root-only slice.
- `.ci/` and seven tests whose sole subject was deleted workflows, duplicated
  provider files, or the 834-line `.ci/ctl.sh` were removed together.

## Blocked

The full scripts suite requires the Eden devcontainer. Targeted structural and
shell checks are green; no container was started under the no-build scope.

## Next

Commit the root slice, open its PR, and merge while GitHub Actions remain disabled.
