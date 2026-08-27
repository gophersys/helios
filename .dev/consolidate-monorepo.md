# consolidate-monorepo

phase:    plan
repo:     gophersys/eden
branch:   chore/consolidate-monorepo
worktree: ~/code/.worktrees/eden-consolidate-monorepo
pr:       -
attempt:  1/2
plan:     SELF-APPROVED — preserve every source commit and dirty change before removing repository boundaries.

## Goal

Make Eden the single organization workspace: import the libraries, infrastructure,
development-container, CI-tooling, linter, and research source histories; expose one
root development container and one Nx/ctl command surface; remove superseded
submodules and development-container variants without losing work.

## Plan

1. Inventory every source repository, branch, worktree, open pull request, unpushed
   commit, and dirty file. Commit and push recoverable snapshots before migration.
2. Merge surviving feature progress into each source repository's `main`. Mateo
   explicitly waived CI and temporary build correctness on 2026-08-27: “fully skip
   ci for now”. Preserve conflict resolutions and source merge commits.
3. Import each source repository with history into its final Eden prefix. Replace
   the `.devcontainer`, `libs`, and `infrastructure` gitlinks with ordinary tracked
   directories.
4. Keep one root `.devcontainer/devcontainer.json`; retain image sources only for
   base, cloud, and buildkit. Remove superseded development-container variants.
5. Add one short root `ctl.sh` command surface and Nx ownership for the consolidated
   projects. Delete documentation and configuration made false by consolidation.
6. Prove history and file preservation with repository/object/path checks. Skip CI
   and builds under the explicit waiver, then merge the consolidation to `main`.
7. Only after Eden `main` contains the imported progress, remove redundant clean
   local clones and stale worktrees. Never discard an uncommitted or unpushed change.

## Proven

- `git fetch -q origin && git log -1 --oneline origin/main` — consolidation starts
  from Eden `15e973c`, the current remote main.
- `git submodule status` — the current checkout has three gitlinks:
  `.devcontainer`, `infrastructure`, and `libs`.
- `git status` across active worktrees — dirty feature work exists and must be
  snapshotted before cleanup.

## Blocked

None. The repository-deletion/architecture decision was approved by Mateo on
2026-08-27: “ok do it ... don't lose any progress”.

## Next

Create and push a machine-readable preservation inventory before merging source work.
