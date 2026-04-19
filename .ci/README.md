# infrastructure .ci

Orchestration-layer CI for `gophersys/infrastructure`. Verbs invoked
locally inside a gophersys devcontainer, via Nx
(`nx run ci-infrastructure:<verb>`), or by any remote runner (see
`providers/`).

## Verbs

- `validate` — shellcheck + JSON validate; delegates to repo-level
  `ctl.sh validate` when present.
- `status` — inventory: machines, clusters, platform services.
- `release-check` — preflight for release.sh: clean working tree, on
  main, up to date with origin.
- `help`.

Follows the brain-wide CI convention documented in
`brain/.claude/rules/operations/ci-patterns.md`.

## Providers

`providers/` is the source of truth for every CI-system shim. Native
paths are symlinks into the matching subfolder. No providers wired yet.
