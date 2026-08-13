# CI runners

Self-hosted GitHub Actions capacity for the `gophersys` org, and what a repo must
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

The pool scales to zero, so a cold job waits 30 to 60 seconds for a pod.
**Every** repo in the org shares the same capacity. A workflow with many parallel
jobs therefore leaves no capacity for the other repos.

## What a runner does and does not give you

- **Sudo, and the full dev toolchain.** The runner image is the `base` dev image.
  A job gets Go, Node, Python, Rust, kubectl, helm, terraform, k3d, kind,
  kubeconform, shellcheck, gitleaks and the ADR-0020 gate tools at the same
  versions an interactive session gets. The `dev` user has passwordless sudo.
  Jobs no longer download their tooling into `$HOME/bin`.
- **Docker works.** The dind sidecar is privileged, so a job can run
  `docker build`, `docker run`, k3d and kind. This is how a repo gets tooling
  that the base image lacks: put the tooling in a container image and run the
  job's real work inside that image.
- **Temporary.** Each job gets a new pod. Nothing persists between runs, except
  what you push to a registry or to an `actions/cache` entry.

## Sizing and placement

Until 2026-08-10 the pod declared **no requests and no limits at all**. Every
runner was best-effort. The scheduler treated 4 concurrent builds as free, and a
`docker build` without control could take a node's memory or fill its disk.

Per runner pod, across both containers:

| | `runner` | `dind` | pod total |
|---|---|---|---|
| CPU request | 500m | 500m | **1 core** |
| CPU limit | none | none | **none** |
| Memory request | 1Gi | 1Gi | **2Gi** |
| Memory limit | 6Gi | 6Gi | 12Gi |
| Ephemeral request | 2Gi | 8Gi | **10Gi** |
| Ephemeral limit | 10Gi | 30Gi | 40Gi |

At `maxRunners: 4` the pool reserves **4 cores, 8Gi RAM and 40Gi disk**. That is
comfortable against 4 workers of 4 cores and 14Gi each.

Keep these 3 decisions:

- **Size `dind`, not only `runner`.** `dind` is a native sidecar
  (`restartPolicy: Always`), and it is where an image build spends CPU, memory
  and disk. Its requests count toward the pod, so an unset value made the pod
  look free.
- **No CPU limit, on purpose.** CFS throttling makes builds slow and
  intermittently unreliable. The request already guarantees the share. A limit
  only adds stalls.
- **The ephemeral-storage requests do the placement work.** Image layers live in
  the writable layer of the `dind` container. A declaration of 10Gi per pod stops
  the scheduler from putting more builds onto a node that has no disk left. The
  memory numbers would never have caught that failure.

Declare the placement; do not use a hand-applied label. A `nodeAffinity`
`NotIn [k3s-w-4]` keeps builds off the USB-passthrough embedded node, and a
preferred `podAntiAffinity` spreads concurrent runners across the workers. The
manifest uses the hostnames directly, so nothing depends on a label applied by
hand outside git.

### Why the pod spec is written out instead of `containerMode: dind`

`containerMode: dind` **generates** the pod spec and **appends** anything you add
instead of a merge. A container named `dind` supplied under that mode renders a
second container with the same name, and the API server rejects that. The chart's
own values file states it: *"If any customization is required for dind,
containerMode should remain empty, and configuration should be applied to the
template."*

`containerMode` is therefore removed, and `template.spec` carries the chart's
documented dind spec without change, plus the resources, the affinity and the
volume size limits. Verify a change before you merge it:

```bash
yq -r '.spec.source.helm.values' \
  platform/services/gitops/registry/app-arc-runners-org.yaml > /tmp/v.yaml
helm template arc-org \
  oci://ghcr.io/actions/actions-runner-controller-charts/gha-runner-scale-set \
  --version 0.14.2 -n arc-runners -f /tmp/v.yaml > /tmp/r.yaml
yq 'select(.kind=="AutoscalingRunnerSet")' /tmp/r.yaml \
  | kubectl apply --server-side --dry-run=server -f -
```

Check that the names in the rendered `initContainers` and `containers` are
unique. A duplicate name is the specific way this chart fails, and Argo reports
it only after it syncs.

## Roadmap

`ci-substrate.md` specifies the interface that these steps build toward: pools
for physical capability, images for software capability. See
[`ci-substrate.md`](ci-substrate.md).

| Next | What it adds | Blocked on |
|---|---|---|
| Per-domain pools (`arc-zephyr`, `arc-kicad`, `arc-flutter`, `arc-usb`) | firmware, hardware, mobile | nothing — the procedure is in `ci-substrate.md` |
| **Mac mini runner** | macOS builds, **iOS and Android** through 2 phones on USB with full device control | the machine is `macos-ci-runner` in `contracts/access.yaml`. It was enrolled on 2026-08-13 and it is reachable by key on the LAN. It is not on the tailnet, it has no container runtime, and the runner is not registered. The phones are not connected. |
| Windows VM runner on `pve-03` | Windows builds | the licence choice |
| Argo on the cloud cluster | closes debt D18 | nothing |

## Onboarding a repo

A **private** repo needs no action. The Default runner group is
`visibility: all`, so any private repo in the org can use `runs-on: arc-org`
immediately.

```yaml
jobs:
  build:
    runs-on: arc-org      # self-hosted (ARC)
```

### Public repos are blocked by default

The Default runner group has **`allows_public_repositories: false`**. The jobs of
a public repo queue **forever** with no error. The ARC listener reports
`"assigned job"=0` and never scales up, and the job shows
`runner_group_name: ""`. The GitHub UI gives no message that explains the cause.

Diagnose with:

```bash
# needs admin:org (Bitwarden: shared/github/pat-godmode)
gh api orgs/gophersys/actions/runner-groups/1 --jq '{allows_public_repositories}'
gh api repos/gophersys/<repo>/actions/runs/<id>/jobs --jq '.jobs[] | {labels,runner_group_name}'
```

This default is deliberate, and **you should not change it casually**. A
self-hosted runner on a public repo lets a pull request from a fork run arbitrary
code on our hardware. This scale set runs a *privileged* dind sidecar, so that
code can reach the node, and therefore the cluster. Apply these standard controls
before you enable it:

1. Require approval for **all** workflow runs from outside collaborators, not
   only for first-time contributors.
2. Prefer a **separate** runner group and scale set for public repos, without
   dind, and with the toolchain built into a custom runner image instead. A
   runner without privilege turns a node compromise back into a job compromise.
3. Keep `maxRunners` low on that group, so an abusive pull request cannot use all
   the org capacity.

The `hardware` repo was public when it needed these runners, and its jobs queued
for this reason. The repo was made **private** instead of a change to the policy.
That was the least expensive correct fix, and you can reverse it. If the repo
must be public again, do option 2 first. Do not simply change the flag.

As of 2026-08-09 the org has **no public repos** (`esp32-starter` was deleted; a
bundle is in `~/code/.archive/`), and the policy stays disabled.

## Consumers

| Repo | Uses | Notes |
|---|---|---|
| `infrastructure` | `arc-org` | `validate.yml` — kubeconform + `kubectl kustomize`, both from the runner image |
| `eden` | `arc-org` | needs dind for the k3d-based gates |
| `workspaces` | `arc-org` | |
| `hardware` | `arc-org` | Needs KiCad 10, supplied by `ghcr.io/gophersys/hardware-ci` (built from `ci/Dockerfile` in that repo) instead of a custom runner image. Made private specifically to use these runners — see the public-repo section |

### KiCad / EDA workloads

`hardware` runs `kicad-cli` for ERC, DRC, netlist export and Gerber generation.
KiCad is not on the runner image, and you cannot install it with apt without
sudo. That repo therefore builds `ghcr.io/gophersys/hardware-ci` (Ubuntu 24.04
plus the `ppa:kicad/kicad-10.0-releases` PPA) and runs its test suite inside that
image with `docker run`. A future EDA repo should reuse that image instead of a
new KiCad install.

If a separate group without dind ever gets public-repo access (option 2 above),
that image becomes the **runner** image, and the `docker run` step is no longer
necessary.

## Changing the scale set

Edit `platform/services/gitops/registry/app-arc-runners-org.yaml` and let ArgoCD
sync (`selfHeal: true`, `prune: true`). Do not run `kubectl edit` on the
`AutoscalingRunnerSet`. Argo reverts it.

`.github/workflows/validate.yml` runs kubeconform on that file on every PR.

[arc]: https://github.com/actions/actions-runner-controller
