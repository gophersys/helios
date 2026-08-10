# monorepo .ci/providers

This directory is the source of truth for every CI-system shim in this repository.

## The supplied providers

| Provider | Subfolder | Native path |
|---|---|---|
| GitHub Actions | `github/` | `.github/workflows/` |

Every YAML file is a thin shim. It checks out the repository with the submodules, it provides the
toolchain, and it runs `bash .ci/ctl.sh <verb>`. The logic is in `ctl.sh`. You can run `ctl.sh`
locally, check it with shellcheck and test it. You cannot do any of that with YAML.

## The 2 copies are NOT symlinks

An earlier version of this file said that `.github/workflows/` symlinks into `github/`. It also
said that "git tracks symlinks natively, so no generator is needed". **That statement is not
true, and it appears that it was never true.** Git records each of these files as a regular file,
with the mode `100644`. A symlink has the mode `120000`. Check the modes before you accept either
statement:

```sh
git ls-files -s .github/workflows/ | awk '{print $1, $4}'
```

Today there are 2 copies, and a person keeps them equal by hand. The same YAML is written 2 times.
This is a defect. It is not a design. The 2 copies became different one time. The `.devcontainer`
copy held an old version with 3 images. At the same time the document said that this copy was the
source of truth for the provider.

## The planned solution

`cictl` generates both copies from `.ci/ci.contract.yaml`. `cictl drift` fails the build if a
person edits a generated file. The result is 1 source, 2 outputs, and a gate that proves that the
2 outputs match.

`cictl` is not connected in this repository yet. This repository has no contract. Only `libs` has
one. Until this repository has a contract, a person maintains the 2 copies by hand. **Edit both
copies together.** Do not add a third copy.

## Adding a provider

A second provider needs a second renderer in `cictl`. Today the `providers` list in the contract
is an enum with 1 member. The abstraction is declared, but nobody has used it yet. Do not assume
that a second provider has no cost.
