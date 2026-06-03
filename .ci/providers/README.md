# monorepo .ci/providers

Source of truth for every CI-system shim inherited by projects created
from this template.

## Shipped

| Provider | Subfolder | Native path |
|---|---|---|
| GitHub Actions | `github/` | `.github/workflows/` (symlinks) |

Every YAML is a thin shim: checkout with submodules, pull the
`ghcr.io/gophersys/base` image, run `bash .ci/ctl.sh <verb>`.

## Adding more providers

Follow the pattern documented in
`brain/.claude/rules/operations/ci-patterns.md`.
