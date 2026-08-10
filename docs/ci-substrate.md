# CI substrate — the interface between runners and toolchains

How a job says *where it runs* and *what it runs in*, across web, desktop,
firmware, hardware and mobile. This document defines the interface. It does not
require every pool to exist yet.

Runner capacity and sizing: `docs/ci-runners.md`.
Dev images: `gophersys/.devcontainer` (submodule at `eden/.devcontainer`).

## The one rule

**A pool is a physical capability. An image is a software capability.**

| Question | Axis | Declared as |
| --- | --- | --- |
| What CPU architecture? Which OS kernel? Is a phone or a dev board plugged in? How much RAM and disk? | **physical** | the runner pool (`runs-on:`) |
| Which compiler, SDK, linter, CLI? | **software** | the image |

Anything you could install is software. Anything you would have to *plug in*,
*buy*, or *boot a different kernel for* is physical.

Applied, that gives a small number of pools and a growing number of images.
Adding a new language or SDK must never require a new pool — if it does, the
split has been drawn in the wrong place.

## Why the images are the dev images

`.devcontainer` already states the intent: *"Each image serves two roles: local
dev environment / CI runtime."* Its README even shows the GitHub Actions usage.
That intent is correct and this document keeps it. The gain is not only fewer
images to maintain — it is that **a workflow which passes in CI is the same
environment that passed on your machine**, including the ADR-0020 gate toolchain,
`k3d`, `kind` and the Zephyr SDK.

Current inventory (`ghcr.io/gophersys/*`, all private except where noted):

```
       base ──── web, desktop, infrastructure, Go/Node/Python
     ┌──┴──┐
flutter  zephyr ──── firmware
   │        │
 Android  zephyr-devbox (public)
```

Gaps against the five target domains:

| Domain | Image | State |
| --- | --- | --- |
| web | `base` | exists — Node LTS, Tauri/GTK libs |
| desktop | `base` | exists |
| firmware | `zephyr` | exists — SDK, west, udev rules |
| hardware (EDA) | — | **missing.** `gophersys/hardware` builds its own `ghcr.io/gophersys/hardware-ci` (KiCad 10). Fold it in as `.devcontainer/kicad` so it follows one build, one policy, one propagation path. |
| mobile — Android | `flutter` | exists — JDK 17, Android SDK |
| mobile — iOS | — | **cannot be an image.** See below. |

## The measured constraints

Everything below was verified on 2026-08-10 by running a probe workflow against
`arc-org`, not inferred. The probe has been removed; these are its results.

### 1. Job containers work on ARC — but they are not cached

A `container:` job runs correctly on a dind runner. The runner pulls the image
**inside the pod's dind daemon**, and the pod is ephemeral, so the layers die
with the job.

> Measured: a cold pull of `zephyr-devbox` took **5 minutes 17 seconds** before
> the first step ran.

That cost is paid on **every job**. It is not acceptable for images this large,
and it cannot be fixed by sharing a docker data-root across pods — two dind
daemons on one data-root corrupt it.

**Therefore the toolchain image should be the runner container image, not a
`container:` image.** The kubelet then pulls it, and the kubelet caches per node:
the first job on a node pays the pull, every later job starts instantly.

### 2. Private images work in-cluster, and only in-cluster

Pulling a private package with `GITHUB_TOKEN` fails:

```
ghcr.io/gophersys/base:latest: 403 Forbidden
```

The login succeeds; the *package* has not granted the consuming repository
access. That grant is per (package, repository) pair and is **UI-only** —
`/orgs/gophersys/packages/container/base/repositories` returns 404, so it cannot
be scripted. Organization-level Actions secrets, the other workaround, need
GitHub Team; the org stays on Free.

A kubelet pull has neither problem: one `imagePullSecret` in `arc-runners`,
sourced from Vaultwarden through ESO, covers every image and every repo.
**Keeping the images private argues for the same design that performance does.**

### 3. The runner supplies Node, so images need not

The job container is started with `-v /home/runner/externals:/__e:ro` and the
workspace at `/__w`. GitHub runs JavaScript actions from `/__e`, so an image
carrying no Node still runs `actions/checkout`. Image authors owe nothing to
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

Six of the eight differ only by image and would collapse into one pool if images
were cheap to swap. They do not collapse, because the kubelet cache is what makes
them fast, and the kubelet caches the **pod's** image.

`arc-usb` and `arc-arm64` are the pools that are genuinely physical: a USB device
and a CPU architecture cannot be installed.

**On the name `arc-org`.** It describes ownership, not capability, so by this
document's own rule it should be `arc-base`. It is not being renamed.
`runnerScaleSetName` *is* the `runs-on` label and a scale set has exactly one, so
there is no aliasing and no overlap window. Seventeen workflow references across
five repos point at `arc-org`, and a label no pool answers makes a job queue
forever with no error — the documented failure mode in `ci-runners.md`. A
cosmetic rename is not worth that. Pools added from here are named for capability
from the start.

### The `+ runner` layer

One parameterized Dockerfile, not one per image:

```dockerfile
ARG BASE_IMAGE                      # ghcr.io/gophersys/<image>:<sha>
FROM ${BASE_IMAGE}
# adds the actions runner binary and its entrypoint; changes nothing else
```

It is built for each domain image and tagged `<image>-runner`. The dev image and
the CI image therefore differ by exactly one layer that contains no toolchain.
Nothing a workflow can observe differs between them.

### Choosing, as a workflow author

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

A job needing a toolchain that no pool carries may still use `container:`,
accepting the cold-pull cost. That is the escape hatch, not the default, and a
recurring use of it is a signal to add a pool.

### Why iOS is the exception

Xcode does not run in a Linux container and Apple does not license macOS on
non-Apple hardware. iOS is the one domain where the toolchain is inseparable from
the machine, so the pool *is* the toolchain. Android does not share this problem:
`flutter` builds it in a container, and the Mac mini is needed only for
device-attached test and release signing.

## Order of work

Each step is independently useful and independently verifiable.

1. ~~**Add `kubeconform` to `base`.**~~ Done 2026-08-10.
2. ~~**Build the `+ runner` layer.**~~ Done — `runner/Dockerfile` in
   `.devcontainer`, one Dockerfile per parent via `BASE_IMAGE`.
3. ~~**Add the `imagePullSecret`**~~ Done — `ghcr-pull`, ESO from
   `shared/github/pat-godmode` (debt D24).
4. ~~**Point the pool at `base-runner`**~~ Done — `arc-org` runs
   `ghcr.io/gophersys/base-runner`, and `validate.yml` has no tool-install step.
5. **Fold `hardware-ci` into `.devcontainer/kicad`**, then add `arc-kicad`.
6. **Add `arc-zephyr` and `arc-usb`** (`arc-usb` pinned to `k3s-w-4`).
7. **Mac mini** — macOS, iOS, and Android over USB. Blocked on the phones.
8. **Windows VM** on `pve-03`. Blocked on a licence decision.

Steps 1–4 were the load-bearing ones: they prove dev/CI parity end to end.
Nothing after step 4 introduces a new idea — each is one image and one pool,
following the same two files.

## Adding a pool

1. Add a CI job in `.devcontainer/.github/workflows/build-and-push.yml` that
   builds `runner/Dockerfile` with `BASE_IMAGE` set to the new parent, and add
   the image to `BUILD_ORDER` in both `ctl.sh` files.
2. Copy `platform/services/gitops/registry/app-arc-runners-org.yaml`, change
   `runnerScaleSetName`, the two image references, and any node affinity the
   physical capability requires.
3. Name it for the capability, never for the owner.
4. Prove it with a real job before pointing a repo's default at it.

## What this replaces

The earlier plan was a purpose-built CI runner image carrying sudo, Go, Node and
Python. It is dropped. It would have been a second image set to maintain, drifting
from the dev images by construction — a fix that must be repeated. The measured
pull cost and the private-registry result both point the other way.
