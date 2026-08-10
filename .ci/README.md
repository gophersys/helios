# monorepo .ci

Every project created from this template inherits this baseline CI layer. Every verb operates on
the whole monorepo. A verb uses `nx run-many` or `nx affected`.

## Verbs

- `validate` — runs shellcheck on every ctl.sh, then runs `nx run-many -t validate`.
- `build-all` — runs `nx run-many -t build`.
- `test-all` — runs `nx run-many -t test`.
- `lint-all` — runs `nx run-many -t lint`.
- `typecheck-all` — runs `nx run-many -t typecheck`.
- `affected-build` — runs `nx affected -t build` against `main`.
- `affected-test` — runs `nx affected -t test`.
- `affected-check` — runs `nx affected -t lint,typecheck,test`. This is the canonical
  pull-request gate verb.
- `release-check` — the preflight for a release. It checks that the working tree is clean, that
  you are on main, and that the branch is up to date with origin.
- `help`.

## Invocation

These 3 commands do the same thing in every environment:

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

`providers/` is the source of truth for every CI-system shim. The native paths
(`.github/workflows/`) hold a copy of the matching subfolder. They are regular files, not symlinks: git records them with the mode `100644`. See
`brain/.claude/rules/operations/ci-patterns.md`.

Every new project gets these providers by default:

- `github/on-push.yml` — runs `affected-check` on every push.
- `github/on-pr.yml` — runs `affected-check` on every pull request.

A project extends these files. A project does not replace them.
