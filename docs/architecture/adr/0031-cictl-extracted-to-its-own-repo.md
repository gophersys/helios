# ADR-0031 — cictl lives in its own public repository

- **Status:** accepted
- **Date:** 2026-08-10
- **Supersedes:** the placement of `tools/cictl` that ADR-0026 implied

## Context

`cictl` generates the CI workflows of a repository from `.ci/ci.contract.yaml`. It fails the
build when a person edits a generated file. It was at `eden/tools/cictl`.

Only `gophersys/libs` adopted it, and that repository failed **100 CI runs in sequence**. Every
run after the adoption on 2026-06-15 failed. There are 3 causes:

1. the renderer wrote `runs-on: ubuntu-latest` as a fixed value, so the jobs never reached the
   self-hosted pool;
2. it always emitted a `container:` block, and the block authenticates with `GITHUB_TOKEN`
   against a **private** package, which returns 403;
3. the generated workflows call the `cictl` binary, but no image installed that binary and no
   PATH held it. `libs` is also a separate repository, so `eden/tools/cictl` does not exist in
   its checkout.

Cause 3 is the placement problem. The CI of every repository needs this tool, so the tool cannot
live inside one of those repositories.

## Decision

**`cictl` is its own repository, `gophersys/cictl`, and it is public.**

The `+ runner` layer of the devcontainer images installs it, so every CI job has it on the PATH.

### Why not a submodule

A submodule puts a pointer in every repository that uses it. A correction to `cictl` would then
need 1 pull request in each of those repositories. A submodule also adds the authentication for a
private submodule to every Actions checkout.

### Why public

A public repository removes the distribution problem. `go install` then needs no credential in
any place: not in an image build, not on a developer machine, not in any repository, at any time.
A private repository would force `GOPRIVATE` and a build-time token into **every repository that
builds an image**. The Free plan has no organization secret for a private repository, so the
repositories cannot share one token.

`cictl` is a generator from YAML to YAML. It holds no secret and no proprietary logic. The
development images stay private. Only the generic code is public.

### Why the runner layer and not `base`

Install a tool only in the image that needs the tool. `cictl` is a CI function. `base` stays a
development environment. The runner layer also builds again in about 2 minutes, and `base` needs
about 1 hour. The short build time is important while the contract changes.

## Consequences

- This repository deletes `tools/cictl` and removes it from `go.work`.
- The contract gets a `runner` field. When `runner.container` is false, `cictl` emits no
  `container:` block. The runner image of a self-hosted pool already holds the toolchain.
  A `container:` image is also pulled *inside* the ephemeral pod, so it uses no cache and it
  costs more than 5 minutes for each job.
- The `image` field is necessary only in container mode, and the contract rejects it outside
  container mode. If a self-hosted pool also names an image, nothing uses that image, and a
  reader can believe that something does.
- A person writes the workflow of `cictl` by hand, and it runs on GitHub-hosted runners. The
  repository is public, and `arc-org` is in a runner group with
  `allows_public_repositories: false`, so its jobs would stay in the queue there and never run.
  That pool also runs a privileged dind sidecar, and a pull request from a fork must never reach
  that sidecar.
- `cictl` does not generate its own workflow. `cictl` gates the build. If it generated its own
  workflow, the build would produce the tool that gates that build. This is the only exception.

## Still open

Causes 1 and 2 are corrected, and this decision corrects cause 3. Nobody has generated the
workflows of `libs` again against the new contract, so the CI of `libs` still fails. Do not roll
`cictl` out to more repositories before the CI of `libs` passes.
