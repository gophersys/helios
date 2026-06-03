# monorepo .ci

Baseline CI layer inherited by every project created from this template.
Every verb operates across the whole monorepo via `nx run-many` or
`nx affected`.

## Verbs

- `validate` — shellcheck every ctl.sh + `nx run-many -t validate`.
- `build-all` — `nx run-many -t build`.
- `test-all` — `nx run-many -t test`.
- `lint-all` — `nx run-many -t lint`.
- `typecheck-all` — `nx run-many -t typecheck`.
- `affected-build` — `nx affected -t build` (against `main`).
- `affected-test` — `nx affected -t test`.
- `affected-check` — `nx affected -t lint,typecheck,test`. The canonical
  PR-gate verb.
- `release-check` — preflight for release: clean working tree, on main,
  up to date with origin.
- `help`.

## Invocation

Identical three ways, everywhere:

```
# Local, inside a gophersys devcontainer
bash .ci/ctl.sh <verb>

# Via Nx (from project root)
nx run ci-<project>:<verb>

# In any CI runner
docker run --rm -v "$PWD:/workspace" \
  ghcr.io/gophersys/base:latest \
  bash -c "cd /workspace && bash .ci/ctl.sh <verb>"
```

## Providers

`providers/` is the source of truth for every CI-system shim. Native
paths (`.github/workflows/`) are symlinks into the matching subfolder.
See `brain/.claude/rules/operations/ci-patterns.md`.

Shipped providers (default for every new project):

- `github/on-push.yml` — runs `affected-check` on every push.
- `github/on-pr.yml` — runs `affected-check` on every PR.

Projects extend these; they don't replace them.
