# libs .ci

Orchestration-layer CI for `gophersys/libs`. Verbs are invoked locally
inside a gophersys devcontainer, via Nx (`nx run ci-libs:<verb>`), or by
a remote CI runner (see `.ci/providers/`).

## Verbs

- `validate` — shellcheck + JSON validate; delegates to repo-level
  `ctl.sh validate`.
- `status` — inventory: total libs per language subtree.
- `release-check` — preflight for release.sh: clean working tree, on
  main, up to date with origin.
- `help`.

Follows the brain-wide CI convention documented in
`brain/.claude/rules/operations/ci-patterns.md`.

## Providers

`providers/` is the source of truth for every CI-system shim. Native
paths (`.github/workflows/`) are symlinks into `providers/github/`.

Currently no providers wired — libs rarely needs its own CI beyond
ecosystem-level checks run from brain.
