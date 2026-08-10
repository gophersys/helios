# ADR-0031 — cictl lives in its own public repository

- **Status:** accepted
- **Date:** 2026-08-10
- **Supersedes:** the `tools/cictl` placement implied by ADR-0026

## Context

`cictl` generates each repo's CI workflows from `.ci/ci.contract.yaml` and fails
the build when a generated file is hand-edited. It lived at `eden/tools/cictl`.

Its only adopter, `gophersys/libs`, had failed **100 consecutive CI runs** —
every run since adoption on 2026-06-15. Three causes:

1. the renderer hardcoded `runs-on: ubuntu-latest`, so jobs never reached the
   self-hosted fleet;
2. it always emitted a `container:` block authenticated with `GITHUB_TOKEN`
   against a **private** package, which returns 403;
3. the `cictl` binary the generated workflows invoke was installed in no image
   and on no PATH — and `libs` is a standalone repo, so `eden/tools/cictl` does
   not exist in its checkout.

Cause 3 is the placement problem. A tool that every repo's CI depends on cannot
live inside one of those repos.

## Decision

**`cictl` is its own repository, `gophersys/cictl`, and it is public.**

It is installed into the `+ runner` layer of the devcontainer images, so every CI
job has it on PATH.

### Why not a submodule

A submodule puts a pointer in every consuming repo. One `cictl` fix would become
one pull request per repo — a fix that must be repeated. It also drags private
submodule authentication into every Actions checkout.

### Why public

The distribution problem disappears. `go install` then needs no credential
anywhere: image builds, developer machines, any repo, permanently. Private would
have forced `GOPRIVATE` plus a build-time token into **every repo that builds an
image**, and the Free plan has no organization secrets for private repos to share
one.

`cictl` is a YAML-to-YAML generator holding no secrets and no proprietary logic.
The dev images stay private; only the generic plumbing is visible.

### Why the runner layer and not `base`

The image that needs a tool is the image that gets it. `cictl` is a CI concern;
`base` stays a development environment. The runner layer also rebuilds in about
two minutes against `base`'s hour, which matters while the contract is moving.

## Consequences

- `tools/cictl` is deleted from this repo and dropped from `go.work`.
- The contract gains a `runner` field. When `runner.container` is false no
  `container:` block is emitted, because a self-hosted pool's runner image
  already carries the toolchain — and a `container:` image is pulled *inside*
  the ephemeral pod, so it caches nothing and re-pays over five minutes per job.
- `image` is required only in container mode and rejected outside it: a
  self-hosted pool that also names an image is dead configuration reading as
  intent.
- `cictl`'s own workflow is hand-written and runs on GitHub-hosted runners. It is
  public, and `arc-org` sits in a runner group with
  `allows_public_repositories: false`, so its jobs would queue forever there —
  and that pool runs a privileged dind sidecar a fork PR must never reach.
- `cictl` does not generate its own workflow. That would make the tool gating the
  build a product of the build it gates. It is the only such exception.

## Still open

Causes 1 and 2 are fixed and cause 3 is addressed by this decision, but `libs`
has not yet been regenerated against the new contract, so it remains red. Nothing
should be rolled out to further repos until it is green.
