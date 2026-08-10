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
| Runner image | `ghcr.io/gophersys/base-runner` — the `base` **dev** image plus the runner binary. See [`ci-substrate.md`](ci-substrate.md). |
| Container mode | `dind` — privileged Docker-in-Docker sidecar, pod spec written out (see below) |
| Auth | GitHub App, secret `arc-github-app` (Bitwarden: `shared/github/arc-app`) |

Scale-to-zero means a cold job waits ~30–60s for a pod. Capacity is shared across
**every** repo in the org, so a workflow with many parallel jobs starves everyone else.

## What a runner does and does not give you

- **Sudo, and the full dev toolchain.** The runner image is the `base` dev image,
  so a job gets Go, Node, Python, Rust, kubectl, helm, terraform, k3d, kind,
  kubeconform, shellcheck, gitleaks and the ADR-0020 gate tools at the same
  versions an interactive session gets, and `dev` has passwordless sudo.
  Jobs no longer download their tooling into `$HOME/bin`.
- **Docker works.** The dind sidecar is privileged, so jobs can `docker build`,
  `docker run`, and run k3d/kind. This is how repos get tooling the base image lacks:
  put it in a container image and run the job's real work inside it.
- **Ephemeral.** Each job gets a fresh pod; nothing persists between runs except what
  you push to a registry or an `actions/cache` entry.

## Sizing and placement

Until 2026-08-10 the pod declared **no requests and no limits at all**. Every runner
was best-effort: the scheduler treated four concurrent builds as free, and a runaway
`docker build` could take a node's memory or fill its disk.

Per runner pod, across both containers:

| | `runner` | `dind` | pod total |
|---|---|---|---|
| CPU request | 500m | 500m | **1 core** |
| CPU limit | none | none | **none** |
| Memory request | 1Gi | 1Gi | **2Gi** |
| Memory limit | 6Gi | 6Gi | 12Gi |
| Ephemeral request | 2Gi | 8Gi | **10Gi** |
| Ephemeral limit | 10Gi | 30Gi | 40Gi |

At `maxRunners: 4` the fleet reserves **4 cores, 8Gi RAM and 40Gi disk** — comfortable
against four workers of 4 cores / 14Gi.

Three decisions are worth keeping:

- **Size `dind`, not just `runner`.** `dind` is a native sidecar (`restartPolicy:
  Always`), and it is where image builds actually spend CPU, memory and disk. Its
  requests count toward the pod, so leaving it unset made the pod look free.
- **No CPU limit, on purpose.** CFS throttling makes builds slow and intermittently
  flaky. The request already guarantees the share; a limit only adds stalls.
- **Ephemeral-storage requests do the real placement work.** Image layers live in the
  `dind` container's writable layer. Declaring 10Gi per pod stops the scheduler from
  stacking builds onto a node that has no disk left — the failure mode the memory
  numbers would never have caught.

Placement is declared, not labelled: a `nodeAffinity` `NotIn [k3s-w-4]` keeps builds
off the USB-passthrough embedded node, and a preferred `podAntiAffinity` spreads
concurrent runners across workers. Hostnames are used directly so nothing depends on
a label applied by hand outside git.

### Why the pod spec is written out instead of `containerMode: dind`

`containerMode: dind` **generates** the pod spec and **appends** anything you add
rather than merging it. Supplying a container named `dind` under that mode renders a
second container with the same name, which the API server rejects. The chart's own
values file says it plainly: *"If any customization is required for dind, containerMode
should remain empty, and configuration should be applied to the template."*

So `containerMode` is gone and `template.spec` carries the chart's documented dind spec
verbatim plus resources, affinity and volume size limits. Verify a change before merging:

```bash
yq -r '.spec.source.helm.values' \
  platform/services/gitops/registry/app-arc-runners-org.yaml > /tmp/v.yaml
helm template arc-org \
  oci://ghcr.io/actions/actions-runner-controller-charts/gha-runner-scale-set \
  --version 0.14.2 -n arc-runners -f /tmp/v.yaml > /tmp/r.yaml
yq 'select(.kind=="AutoscalingRunnerSet")' /tmp/r.yaml \
  | kubectl apply --server-side --dry-run=server -f -
```

Check the rendered `initContainers` / `containers` names are unique. A duplicate name
is the specific way this chart fails, and Argo will report it only after it syncs.

## Roadmap

The interface these steps build toward — pools for physical capability, images
for software capability — is specified in [`ci-substrate.md`](ci-substrate.md).

| Next | What it adds | Blocked on |
|---|---|---|
| Per-domain pools (`arc-zephyr`, `arc-kicad`, `arc-flutter`, `arc-usb`) | firmware, hardware, mobile | nothing — the recipe is in `ci-substrate.md` |
| **Mac mini runner** | macOS builds, **iOS and Android** via two phones on USB with full device control | phones not connected yet (2026-08-10) — the machine is `macbook-mini` in `contracts/access.yaml` |
| Windows VM runner on `pve-03` | Windows builds | licence choice |
| Argo on the cloud cluster | closes debt D18 | nothing |

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

As of 2026-08-09 the org has **no public repos** (`esp32-starter` was deleted; a bundle is in `~/code/.archive/`), and
the policy remains disabled.

## Consumers

| Repo | Uses | Notes |
|---|---|---|
| `infrastructure` | `arc-org` | `validate.yml` — kubeconform + `kubectl kustomize`, both from the runner image |
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
