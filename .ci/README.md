# infrastructure .ci

The CI orchestration layer for `gophersys/infrastructure`. You call a verb
locally inside a gophersys devcontainer, through Nx
(`nx run ci-infrastructure:<verb>`), or from any remote runner. See
`providers/`.

## Verbs

- `validate` — runs shellcheck and validates the JSON. It delegates to the
  repo-level `ctl.sh validate` when that file exists.
- `status` — prints the inventory: the machines, the clusters and the platform
  services.
- `release-check` — the checks before release.sh runs: the working tree is clean,
  the branch is main, and the branch is up to date with origin.
- `help`.

This follows the CI convention for the whole brain ecosystem, documented in
`brain/.claude/rules/operations/ci-patterns.md`.

## Providers

`providers/` is the source of truth for the adapter of each CI system. The native
paths are symlinks into the matching subfolder. No provider is wired yet.
