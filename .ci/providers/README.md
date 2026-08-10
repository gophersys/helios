# monorepo .ci/providers

Source of truth for every CI-system shim in this repo.

## Shipped

| Provider | Subfolder | Native path |
|---|---|---|
| GitHub Actions | `github/` | `.github/workflows/` |

Every YAML is a thin shim: checkout with submodules, provide the toolchain, run
`bash .ci/ctl.sh <verb>`. The logic lives in `ctl.sh`, where it can be run
locally, shellchecked and tested — not in YAML, where none of that is possible.

## The two copies are NOT symlinks

This file previously said `.github/workflows/` symlinks into `github/`, and that
"git tracks symlinks natively, so no generator is needed". **It is not true and
appears never to have been.** Git records every one of these as a regular file
(mode `100644`); a symlink would be `120000`. Verify before believing either
claim:

```sh
git ls-files -s .github/workflows/ | awk '{print $1, $4}'
```

What actually exists today is a **hand-maintained twin**: the same YAML written
out twice and kept in step by hand. That is a defect, not a design. It has
already drifted once — the `.devcontainer` copy sat on a stale three-image
version while claiming to be the provider source of truth.

## Where this is going

`cictl` generates both copies from `.ci/ci.contract.yaml` and `cictl drift`
fails the build on any hand-edit. That closes the gap properly: one source, two
outputs, a gate that proves they match.

It is not wired here yet. This repo has no contract — only `libs` does. Until it
does, treat the twins as hand-maintained and **edit both together**, and do not
add a third copy.

## Adding a provider

A second provider means a second renderer in `cictl`. The `providers` list in the
contract is an enum with one member today; the abstraction is declared but not
yet exercised, so do not assume it is free.
