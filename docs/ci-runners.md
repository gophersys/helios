# CI runners

Self-hosted GitHub Actions capacity for the `gophersys` org, and what a repo has to
do to use it.

## What exists

One org-wide [actions-runner-controller][arc] scale set:

| | |
|---|---|
| Scale set name / `runs-on:` label | **`arc-org`** |
| Registered against | `https://github.com/gophersys` (org level, not per-repo) |
| Cluster | homelab k3s, namespace `arc-runners` (controller in `arc-systems`) |
| Managed by | ArgoCD — `platform/services/gitops/registry/app-arc-runners-org.yaml` |
| Chart | `gha-runner-scale-set` 0.14.2 |
| Capacity | `minRunners: 0`, `maxRunners: 4` |
| Runner image | stock `ghcr.io/actions/actions-runner:latest` |
| Container mode | `dind` — privileged Docker-in-Docker sidecar |
| Auth | GitHub App, secret `arc-github-app` (Bitwarden: `shared/github/arc-app`) |

Scale-to-zero means a cold job waits ~30–60s for a pod. Capacity is shared across
**every** repo in the org, so a workflow with many parallel jobs starves everyone else.

## What a runner does and does not give you

- **No sudo.** The runner image is stock and jobs run unprivileged inside it. A job
  cannot `apt-get install` its toolchain.
- **Docker works.** The dind sidecar is privileged, so jobs can `docker build`,
  `docker run`, and run k3d/kind. This is how repos get tooling the base image lacks:
  put it in a container image and run the job's real work inside it.
- **Ephemeral.** Each job gets a fresh pod; nothing persists between runs except what
  you push to a registry or an `actions/cache` entry.

## Onboarding a repo

For a **private** repo, nothing: the Default runner group is `visibility: all`, so any
private repo in the org can use `runs-on: arc-org` immediately.

```yaml
jobs:
  build:
    runs-on: arc-org      # self-hosted (ARC)
```

### Public repos are blocked by default

The Default runner group has **`allows_public_repositories: false`**. A public repo's
jobs will queue **forever** with no error — the ARC listener simply reports
`"assigned job"=0` and never scales up, and the job shows `runner_group_name: ""`.
There is no message in the GitHub UI explaining why.

Diagnose with:

```bash
# needs admin:org (Bitwarden: shared/github/pat-godmode)
gh api orgs/gophersys/actions/runner-groups/1 --jq '{allows_public_repositories}'
gh api repos/gophersys/<repo>/actions/runs/<id>/jobs --jq '.jobs[] | {labels,runner_group_name}'
```

This default is deliberate and **should not be flipped casually**. Self-hosted runners
on a public repo let a fork PR execute arbitrary code on our hardware, and because this
scale set runs a *privileged* dind sidecar, that code can reach the node — which means
the cluster. The standard mitigations before enabling it are:

1. Require approval for **all** outside-collaborator workflow runs, not just
   first-time contributors.
2. Prefer a **separate** runner group and scale set for public repos, without dind, and
   with the toolchain baked into a custom runner image instead. A non-privileged runner
   turns node compromise back into job compromise.
3. Keep `maxRunners` low on that group so an abusive PR cannot exhaust org capacity.

When `hardware` needed these runners it was public and hit exactly this. Rather than
weaken the policy for one repo, the repo was made **private** — the cheapest correct
fix, and reversible. If it ever needs to be public again, do option 2 first; do not
simply flip the flag.

As of writing the org has one public repo, `esp32-starter`, which does not use CI, and
the policy remains disabled.

## Consumers

| Repo | Uses | Notes |
|---|---|---|
| `infrastructure` | `arc-org` | `validate.yml` — kubeconform + kustomize; installs tools to `$HOME/bin` because there is no sudo |
| `eden` | `arc-org` | needs dind for k3d-based gates |
| `workspaces` | `arc-org` | |
| `hardware` | `arc-org` | Needs KiCad 10, supplied by `ghcr.io/gophersys/hardware-ci` (built from `ci/Dockerfile` in that repo) rather than a custom runner image. Made private specifically to use these runners — see the public-repo section |

### KiCad / EDA workloads

`hardware` runs `kicad-cli` for ERC, DRC, netlist export and Gerber generation. KiCad is
not on the runner image and cannot be apt-installed without sudo, so that repo builds
`ghcr.io/gophersys/hardware-ci` (Ubuntu 24.04 + the `ppa:kicad/kicad-10.0-releases` PPA)
and runs its test suite inside it via `docker run`. Any future EDA repo should reuse
that image rather than rebuild the KiCad install.

If public-repo access is ever granted via a separate non-dind group (option 2 above),
that image becomes the **runner** image and the `docker run` indirection disappears.

## Changing the scale set

Edit `platform/services/gitops/registry/app-arc-runners-org.yaml` and let ArgoCD sync
(`selfHeal: true`, `prune: true`). Do not `kubectl edit` the `AutoscalingRunnerSet` —
Argo will revert it.

`.github/workflows/validate.yml` kubeconform-validates that file on every PR.

[arc]: https://github.com/actions/actions-runner-controller
