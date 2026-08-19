# CI runners

Self-hosted GitHub Actions capacity for the `gophersys` org, and what a repo must
do to use it.

## What exists

Three [actions-runner-controller][arc] scale sets. All are registered at **org**
level against `https://github.com/gophersys`, all live in the homelab k3s
namespace `arc-runners` (controller in `arc-systems`), all run chart
`gha-runner-scale-set` 0.14.2, all are managed by ArgoCD from
`platform/services/gitops/registry/`, and all authenticate with the GitHub App
secret `arc-github-app` (Bitwarden: `shared/github/arc-app`).

| `runs-on:` | Capacity | dind | Placement | What it answers | Manifest |
|---|---|---|---|---|---|
| **`arc-org`** | min 1, max 4 | yes | any worker (`k3s-w-0..4`); not the control planes | every repo's `validate` and its general jobs | `app-arc-runners-org.yaml` |
| **`arc-build`** | min 0, max 6 | yes | `k3s-w-0`, `k3s-w-1`, `k3s-w-2` only | container image builds — `.devcontainer`'s build-and-push, nightly scan and weekly bump | `app-arc-runners-build.yaml` |
| **`arc-review`** | min 0, max 2 | **no** | any worker (`k3s-w-0..4`); not the control planes | the pull request review agent, and nothing else | `app-arc-runners-review.yaml` |

All three run the **same** runner image, `ghcr.io/gophersys/cloud`, pinned by
digest: one image for dev and CI, with the Actions runner folded in. See
[`ci-substrate.md`](ci-substrate.md). It replaced `base-runner` on every pool on
2026-08-17, which left `base-runner` with no consumer; retiring the image itself
is a `gophersys/.devcontainer` change, not one here.

The capacity is **partitioned, not shared**. A build wave that fills `arc-build`
cannot starve an unrelated repository's gate, and that is the whole reason
`arc-build` exists rather than a larger `arc-org`. `arc-review` was split off
earlier for a different reason of the same class — it carries a credential in its
environment, and an environment variable on a pool is readable by every job on
that pool.

`arc-build` and `arc-review` scale to zero, so a cold job there waits 30 to 60
seconds for a pod. `arc-org` keeps a floor of 1: with no floor, a single pod
stuck in `Terminating` still counts toward `currentRunnerCount`, and on
2026-08-11 one zombie from an unrelated repository starved every repository for
47 minutes.

`arc-org` is still shared by every repo, so a workflow with many parallel jobs
leaves no `arc-org` capacity for the others.

## What a runner does and does not give you

- **Sudo, and the full dev toolchain.** The runner image is the `cloud` dev
  image. A job gets Go, Node, Python, kubectl, helm, k3d, kind, kubeconform,
  shellcheck, buildx, delve, cictl and the ADR-0020 gate tools at the same
  versions an interactive session gets. The `dev` user has passwordless sudo.
  Jobs no longer download their tooling into `$HOME/bin`.
  `cloud` is a **reduction** of `base`, so a few things left with it — clang and
  cmake, the desktop/Tauri libraries, the USB and BLE libraries, Rust, ansible
  and the OCI CLI. A job that needs one of those needs a `container:` step or a
  pool of its own.
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

`arc-build` uses the same numbers, with one change: its `work` emptyDir is
20Gi rather than 10Gi, because `_work` holds a build context on that pool.
`arc-review` has no `dind` at all, so a review pod is `runner` alone — 500m,
1Gi/4Gi memory, 2Gi/8Gi ephemeral.

At `maxRunners: 4` the `arc-org` pool reserves **4 cores, 8Gi RAM and 40Gi
disk**. That is comfortable against 4 workers of 4 cores and 14Gi each. At
`maxRunners: 6` `arc-build` reserves **6 cores, 6Gi RAM and 60Gi disk** across
the 3 pve-00 workers.

**The pve-00 thin pool is the ceiling `arc-build` is sized against, and it is not
visible from inside a guest.** `k3s-w-0`, `k3s-w-1` and `k3s-w-2` are three thin
LVs on one NVMe. Each guest reports about 60GB free; the host may not have 180GB
to give, and exhausting the pool takes all three nodes at once. Measured on
pve-00 on 2026-08-17: data 816.21g at 29.15% used, about 578GB free — which is
what makes `maxRunners: 6` with a 30Gi `dind` ephemeral limit safe. Re-measure
with `ssh pve-00 'lvs -o lv_name,data_percent,lv_size'` before raising it.

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

Declare the placement; do not use a hand-applied label. On `arc-org` and
`arc-review` a `nodeAffinity` `NotIn [k3s-cp-0, k3s-cp-1, k3s-cp-2]` keeps jobs
off the etcd control planes, which no taint protects (D45). Both pools also
excluded `k3s-w-4` while it held the USB-passthrough embedded lab; that role was
retired on 2026-08-19 and the node is general capacity again. `arc-build` states
the positive form, `In [k3s-w-0, k3s-w-1, k3s-w-2]`, because it must also stay
off `k3s-w-3` **and** `k3s-w-4`: both have 9Gi of RAM and one pod of this shape
declares 12Gi of memory limits. A
preferred `podAntiAffinity` spreads concurrent runners across the workers on
every pool. The manifests use the hostnames directly, so nothing depends on a
label applied by hand outside git.

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
POOL=arc-build        # or arc-org, or arc-review
FILE=platform/services/gitops/registry/app-arc-runners-build.yaml
yq -r '.spec.source.helm.values' "$FILE" > /tmp/v.yaml
helm template "$POOL" \
  oci://ghcr.io/actions/actions-runner-controller-charts/gha-runner-scale-set \
  --version 0.14.2 -n arc-runners -f /tmp/v.yaml > /tmp/r.yaml
yq 'select(.kind=="AutoscalingRunnerSet")' /tmp/r.yaml \
  | kubectl apply --server-side --dry-run=server \
      --field-manager=argocd-controller --force-conflicts -f -
```

**The two flags are load-bearing, and they were missing here until 2026-08-17.**
Argo owns the live object under the field manager `argocd-controller`. Without
them the dry run applies as the manager `kubectl`, and every field you actually
changed comes back as `conflicts with "argocd-controller"` — a hard red that
looks exactly like a broken manifest and is only a question of ownership. It is
worse than a plain false alarm, because it is inconsistent: an object that still
carries a `last-applied-configuration` annotation takes the CSA-to-SSA migration
path and passes with a warning, while one that does not hard-fails. `arc-org`
passed and `arc-review` failed on the same change, for that reason alone. Both
flags are safe under `--dry-run=server`, which writes nothing.

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
  gate:
    runs-on: arc-org      # self-hosted (ARC) — the default choice
  image:
    runs-on: arc-build    # a job whose work is `docker build`
```

Pick `arc-build` only for a job that builds a container image. It has the wider
`_work` volume and the three-node placement, and putting a fast gate there costs
that gate a cold start while holding a build slot.

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
| `.devcontainer` | `arc-build` | build-and-push, security-nightly and weekly-bumps. The pool it builds the image that every other pool runs — a broken publish therefore costs the next pin, not the running pods, because every pool is pinned by digest |
| every repo | `arc-review` | `pr-review.yml`, shared from `gophersys/cictl` |

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

## Changing a scale set

Edit `platform/services/gitops/registry/app-arc-runners-{org,build,review}.yaml`
and let ArgoCD sync (`selfHeal: true`, `prune: true`). Do not run `kubectl edit`
on the `AutoscalingRunnerSet`. Argo reverts it.

`.github/workflows/validate.yml` runs kubeconform on those files on every PR.

### Changing the runner image

Every pool is pinned by **digest**, so the ref is immutable and a rebuild cannot
change CI without a commit. Read the new digest of the manifest LIST, never a
per-platform one:

```bash
docker buildx imagetools inspect ghcr.io/gophersys/cloud:latest \
  --format '{{.Manifest.Digest}}'
```

Then the 3 preconditions, all learned on 2026-08-10 when a pinned tag that did
not exist yet put every pod into `Init:ImagePullBackOff` and took org-wide CI
down:

1. `docker manifest inspect ghcr.io/gophersys/cloud@<digest>`
2. the `cloud` smoke job passed for that build
3. `bash ctl.sh verify-runner-image cloud <sha>` passed — it runs the image in
   the real pod shape, with the dind sidecar, and is the only check that can see
   a broken Docker socket. **Both arguments are required.** The repository used
   to be a constant, and `verify-runner-image cloud <sha>` then read `cloud` as
   the tag and reported a confident verdict about `base-runner:cloud`.

The runner container also declares `securityContext.runAsUser: 0` on every pool.
That is not decoration: `cloud` ends `USER dev`, and the buildkit client key is
projected as a root-owned 0400 file, so uid 1000 could not open it and nothing
would fail until the first arm64 build. `bash ctl.sh verify-buildx-key` asserts
the mode and the uid together.

[arc]: https://github.com/actions/actions-runner-controller
