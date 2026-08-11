# CI substrate — the interface between runners and toolchains

A job declares where it runs and what it runs in. This document defines that
interface for the web, desktop, firmware, hardware and mobile domains. Not every
pool must exist yet.

- Runner capacity and sizing: `docs/ci-runners.md`.
- Dev images: `gophersys/.devcontainer` (submodule at `eden/.devcontainer`).

## The one rule

**A pool is a physical capability. An image is a software capability.**

| Question | Axis | Declared as |
| --- | --- | --- |
| What CPU architecture? Which OS kernel? Is a phone or a dev board plugged in? How much RAM and disk? | **physical** | the runner pool (`runs-on:`) |
| Which compiler, SDK, linter, CLI? | **software** | the image |

Software is anything you can install. Physical is anything you must plug in, buy,
or boot a different kernel for.

The rule gives a small number of pools and a growing number of images. A new
language or a new SDK must never need a new pool. If it does, the split is in the
wrong place.

## Why the images are the dev images

`.devcontainer` states the intent: *"Each image serves two roles: local dev
environment / CI runtime."* Its README also shows the GitHub Actions usage. This
document keeps that intent. The gain is not only fewer images to maintain. It is
also that **a workflow that passes in CI runs in the same environment that passed
on your machine**. That environment includes the ADR-0020 gate toolchain, `k3d`,
`kind` and the Zephyr SDK.

Current inventory (`ghcr.io/gophersys/*`). Every image is private, except where
the diagram says public.

```
       base ──── web, desktop, infrastructure, Go/Node/Python
     ┌──┴──┐
flutter  zephyr ──── firmware
   │        │
 Android  zephyr-devbox (public)
```

Gaps against the 5 target domains:

| Domain | Image | State |
| --- | --- | --- |
| web | `base` | exists — Node LTS, Tauri/GTK libs |
| desktop | `base` | exists |
| firmware | `zephyr` | exists — SDK, west, udev rules |
| hardware (EDA) | — | **missing.** `gophersys/hardware` builds its own `ghcr.io/gophersys/hardware-ci` (KiCad 10). Move it into `.devcontainer/kicad`, so it has one build, one policy and one propagation path. |
| mobile — Android | `flutter` | exists — JDK 17, Android SDK |
| mobile — iOS | — | **cannot be an image.** Read the section below. |

## The measured constraints

A probe workflow ran against `arc-org` on 2026-08-10 and measured every result
below. Nobody inferred them. The probe is removed; these are its results.

### 1. Job containers work on ARC, but the images are not cached

A `container:` job runs correctly on a dind runner. The runner pulls the image
**inside the pod's dind daemon**. The pod is temporary, so the layers are lost
when the job ends.

> Measured: a cold pull of `zephyr-devbox` took **5 minutes 17 seconds** before
> the first step ran.

**Every job** pays that cost. The cost is too high for images of this size. You
cannot remove it by a docker data-root shared across pods, because 2 dind daemons
on 1 data-root corrupt that data-root.

**Therefore the toolchain image should be the runner container image, not a
`container:` image.** The kubelet then pulls the image, and the kubelet caches
per node. The first job on a node pays the pull. Every later job starts
immediately.

### 2. Private images work in the cluster, and only in the cluster

A pull of a private package with `GITHUB_TOKEN` fails:

```
ghcr.io/gophersys/base:latest: 403 Forbidden
```

The login succeeds. The *package* has not granted access to the consuming
repository. That grant is per (package, repository) pair, and it is **UI-only**:
`/orgs/gophersys/packages/container/base/repositories` returns
404, so you cannot script the grant. The other method is organization-level
Actions secrets, and it needs GitHub Team. The organization stays on Free.

A kubelet pull has neither problem. One `imagePullSecret` in `arc-runners`,
supplied from Vaultwarden through ESO, covers every image and every repository.
**Private images therefore need the same design that performance needs.**

### 3. The runner supplies Node, so an image does not have to

The job container starts with `-v /home/runner/externals:/__e:ro` and the
workspace at `/__w`. GitHub runs JavaScript actions from `/__e`. An image that
carries no Node still runs `actions/checkout`. An image author owes nothing to
Actions.

## The interface

### Pools (`runs-on:`) — physical only

| Pool | Runner image | Physical capability | State |
| --- | --- | --- | --- |
| `arc-org` | `base-runner` | linux/amd64, general build | **live** |
| `arc-zephyr` | `zephyr` + runner | linux/amd64 | planned |
| `arc-kicad` | `kicad` + runner | linux/amd64 | planned |
| `arc-flutter` | `flutter` + runner | linux/amd64, Android emulator needs KVM | planned |
| `arc-usb` | `zephyr` + runner | **`k3s-w-4` only — dev boards on USB** | planned |
| `arc-arm64` | `base` + runner | **linux/arm64 native** | planned |
| `macos-mini` | native, no container | **macOS kernel; 2 phones on USB** | planned — `macbook-mini` |
| `windows` | native, no container | **Windows kernel** | planned — VM on `pve-03` |

6 of the 8 pools differ only by image. They would become 1 pool if images were
cheap to swap. They do not become 1 pool, because the kubelet cache is what makes
them fast, and the kubelet caches the image of the **pod**.

`arc-usb` and `arc-arm64` are the 2 pools that are truly physical. You cannot
install a USB device or a CPU architecture.

**The name `arc-org`.** The name states ownership, not capability. By the rule in
this document the name should be `arc-base`. The pool keeps the name `arc-org`.
`runnerScaleSetName` *is* the `runs-on` label, and a scale set has exactly 1, so
there is no alias and no overlap window. 17 workflow references in 5 repositories
point at `arc-org`. A label that no pool answers makes a job queue for ever with
no error — `ci-runners.md` documents this failure. A rename for appearance is not
worth that risk. Name every new pool for its capability from the start.

### What a runner image must supply

A pool's image is more than the dev image plus a runner binary. It must satisfy a
small contract. Each item below is here because a break in it caused a failure
that stayed invisible until a job ran.

| Requirement | Why | Where it is asserted |
| --- | --- | --- |
| The runner installed at `/home/runner` | the ARC chart mounts `work` and `dind-externals` there, so the standard layout needs no special case in the pod spec | — |
| `/home/runner` owned by the runner user | the runner writes `.runner` and `.credentials` there at registration; root ownership fails every pod | build-time `stat` assertion + `.ci/smoke.sh` |
| The user in gid **123** | the dind sidecar runs `dockerd --group=$DOCKER_GROUP_GID`; a user outside that group cannot reach the socket | build-time `id -G` assertion + `.ci/smoke.sh` |
| `init-dind-externals` uses the **same** image | it seeds `/home/runner/externals`, which is the runner's bundled Node; a pair that does not match ships the wrong Node to every JavaScript action | reviewed in the manifest |
| Any CI tool a contract names, on `PATH` | a generated workflow that calls a missing binary fails in the consuming repository, far from the image that omitted it | `.ci/smoke.sh` |

The rule: **assert each item in the image build, because the other option is to
find the fault in a different repository.** A plain `docker run` smoke test cannot
catch the docker-group case, because there is no dind socket to fail against. That
item is therefore checked by an inspection of the group membership, not by docker.

### The `+ runner` layer

One Dockerfile with a parameter, not one Dockerfile per image:

```dockerfile
ARG BASE_IMAGE                      # ghcr.io/gophersys/<image>:<sha>
FROM ${BASE_IMAGE}
# adds the actions runner binary and its entrypoint; changes nothing else
```

The build runs for each domain image and tags the result `<image>-runner`. The
dev image and the CI image therefore differ by exactly 1 layer, and that layer
holds no toolchain. A workflow cannot observe any difference between them.

### How to choose, as a workflow author

```yaml
jobs:
  gate:
    runs-on: arc-base          # physical: linux/amd64, general
  firmware:
    runs-on: arc-zephyr        # software capability, delivered as a pool for cache reasons
  hil:
    runs-on: arc-usb           # physical: a board is plugged into k3s-w-4
  ios:
    runs-on: macos-mini        # physical: Apple's toolchain requires macOS
```

A job that needs a toolchain that no pool carries can still use `container:` and
accept the cold-pull cost. That is the exception, not the default. Repeated use
of the exception is a signal to add a pool.

### Why iOS is the exception

Xcode does not run in a Linux container, and Apple does not license macOS on
hardware that Apple does not make. iOS is the one domain where the toolchain
cannot be separated from the machine, so the pool *is* the toolchain. Android
does not have this problem: `flutter` builds Android in a container, and the Mac
mini is necessary only for tests on a connected device and for release signing.

## Order of work

Each step is useful on its own and can be verified on its own.

1. ~~**Add `kubeconform` to `base`.**~~ Done 2026-08-10.
2. ~~**Build the `+ runner` layer.**~~ Done — `runner/Dockerfile` in
   `.devcontainer`, one Dockerfile per parent through `BASE_IMAGE`.
3. ~~**Add the `imagePullSecret`**~~ Done — `ghcr-pull`, ESO from
   `shared/github/pat-godmode` (debt D24).
4. ~~**Point the pool at `base-runner`**~~ Done — `arc-org` runs
   `ghcr.io/gophersys/base-runner`, and `validate.yml` has no tool-install step.
5. **Move `hardware-ci` into `.devcontainer/kicad`**, then add `arc-kicad`.
6. **Add `arc-zephyr` and `arc-usb`** (pin `arc-usb` to `k3s-w-4`).
7. **Mac mini** — macOS, iOS and Android over USB. Blocked: the phones are not
   connected.
8. **Windows VM** on `pve-03`. Blocked: the licence decision.

Steps 1 to 4 carry the load. They prove that dev and CI use the same environment,
end to end. No step after step 4 adds a new idea. Each one is 1 image and 1 pool,
and follows the same 2 files.

## The review pool

`arc-review` is the 1 pool that is not a build pool. It runs the pull request
review agent and nothing else. It has no dind sidecar, and it carries a Claude
credential in its environment.

It is separate from `arc-org` for 1 reason. The credential is an environment
variable on the pool, and an environment variable on a pool is readable by every
job that runs there. On the general pool that would give the token to every build
in the organization.

The reviewer is not a gate. It cannot block a merge, because branch protection is
not available on this plan (see debt-register D29). Its verdict is advice to the
author, and the loop is bounded at 2 rounds.

## How to add a pool

1. Add a CI job in `.devcontainer/.github/workflows/build-and-push.yml`. The job
   builds `runner/Dockerfile` with `BASE_IMAGE` set to the new parent. Also add
   the image to `BUILD_ORDER` in both `ctl.sh` files.
2. Copy `platform/services/gitops/registry/app-arc-runners-org.yaml`. Change
   `runnerScaleSetName`, the 2 image references, and any node affinity that the
   physical capability needs.
3. Name the pool for the capability, never for the owner.
4. Prove the pool with a real job before you point a repository's default at it.

## What this replaces

The earlier plan was a CI runner image built for the purpose, carrying sudo, Go,
Node and Python. That plan is dropped. It would have been a second set of images
to maintain. It would have drifted from the dev images by construction, so the
same correction would be necessary again and again. The measured pull cost and
the private-registry result both support the current plan.
