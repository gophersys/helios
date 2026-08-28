# root-workspace

phase:    plan
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

## Blocked

None.

## Next

Write and run the failing root-workspace contract test.
