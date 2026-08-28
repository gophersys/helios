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

      cloud ──── EVERY ARC POOL: the reduced base + the CI fold
                 (Actions runner, cictl, buildx, the harnesses).
                 Built from ubuntu directly, not FROM base.
```

`cloud` is what the 3 live pools run. It is not a child of `base`: it builds from
the pinned Ubuntu digest and re-adds a chosen subset, so it is a reduction rather
than a layer. `base-runner` — `base` plus the runner binary — is what it
replaced, and nothing pulls that image now.

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
| `arc-org` | `cloud` | linux/amd64, general build | **live** |
| `arc-build` | `cloud` | linux/amd64, **the three 14Gi pve-00 workers** — image builds | **live** |
| `arc-review` | `cloud` | linux/amd64, **no dind** — the review agent alone | **live** |
| `arc-zephyr` | `zephyr` + runner | linux/amd64 | planned |
| `arc-kicad` | `kicad` + runner | linux/amd64 | planned |
| `arc-flutter` | `flutter` + runner | linux/amd64, Android emulator needs KVM | planned |
| `arc-usb` | `zephyr` + runner | **`k3s-w-4` only — dev boards on USB** | planned |
| `arc-arm64` | `base` + runner | **linux/arm64 native** | planned |
| `macos-mini` | native, no container | **macOS kernel; 2 phones on USB** | planned — the host `macos-ci-runner` is enrolled, the runner is not registered |
| `windows` | native, no container | **Windows kernel** | planned — VM on `pve-03` |

6 of the 10 pools differ only by image. They would become 1 pool if images were
cheap to swap. They do not become 1 pool, because the kubelet cache is what makes
them fast, and the kubelet caches the image of the **pod**.

`arc-usb` and `arc-arm64` are the 2 pools that are truly physical. You cannot
install a USB device or a CPU architecture.

**`arc-build` and `arc-review` are the honest exceptions to the one rule**, and
naming them is better than pretending. They run the same image as `arc-org` and
differ only in what they are ALLOWED to do:

- `arc-build` is a **capacity partition with a node set**. Its ceiling of 6 is
  bounded by one thin pool on pve-00, which the three nodes it runs on share and
  no guest can see; and it is separate from `arc-org` so a build wave cannot
  starve an unrelated repository's gate. The node subset is physical — 14Gi of
  RAM against `k3s-w-3`'s 9Gi — and the ceiling is a property of a disk, so this
  is closer to the rule than it first reads.
- `arc-review` is a **credential boundary**. An environment variable on a pool is
  readable by every job on that pool.

Neither is a new software capability, and neither should be copied for one. A new
language or SDK still needs an image, not a pool.

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
4. ~~**Point the pool at `base-runner`**~~ Done, and superseded 2026-08-17: all
   3 live pools now run `ghcr.io/gophersys/cloud`, pinned by digest.
   `validate.yml` has no tool-install step.
   **`base-runner` has no consumer left.** Retiring the image — the `runner/`
   Dockerfile, its `BUILD_ORDER` entry and its publish job — is a
   `gophersys/.devcontainer` change, and it is the handoff from this one. Until
   it lands the image is still published and still scanned; it is simply not
   pulled. It also left the image warmer's opt-in list, so the layers already
   cached on the nodes are now invisible to the warmer's GC and have to be
   removed once, by hand.
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

## The native arm64 builder — the Mac mini as a buildkitd node

`arc-org` is amd64. It builds a `linux/arm64` image with QEMU emulation, and
emulation is slow. The Mac mini is arm64, so it builds the same image natively.

Measured on 2026-08-13. The same Dockerfile, the images pulled first,
`--no-cache`, and the warm-up run discarded:

| target | method | time |
| --- | --- | --- |
| `linux/arm64` | native, on the mini | 4.01s / 4.02s / 4.02s |
| `linux/amd64` | emulated | 14.05s / 13.65s / 13.74s |

That is 3.44 times faster. Measured on 2026-08-14, a native arm64 build sent
through the mini's buildkitd over mTLS took 9.3s end to end. The build context
transfers at approximately 100 MB/s, so a real context costs 1 to 2 seconds.

**The mini is a buildx NODE, not a pool.** A job keeps its own `runs-on`, and an
image build takes `arc-build`. Only the arm64 part of the build leaves the pod.
This is why the `arc-arm64` row in the table above stays "planned": you do not
need a second scale set to build arm64 natively.

### The credential

`arc-org` and `arc-build` each mount three PEM files at `/etc/buildkit-certs/` —
`ca.pem`, `cert.pem` and `key.pem` — mode 0400. `arc-review` does not: it builds
nothing. The manifests are `40-buildkit-client-certs-externalsecret.yaml` (the
vault link) and `app-arc-runners-{org,build}.yaml` (the volume). Read the
comments in both before you change either one.

**Owner-only names an owner.** A projected secret file is owned by uid 0, so 0400
is readable by uid 0 and by nobody else, and the runner container must therefore
declare `runAsUser: 0`. That used to be true by accident — `base-runner` ended as
root — and the manifest said so in a comment. `cloud` ends `USER dev`, measured
on the pinned digest as `uid=1000(dev)`, so the accident is gone and the
declaration is explicit. `bash ctl.sh verify-buildx-key` asserts the mode and the
uid together, and 0440 is not an escape hatch: tls refuses a group-readable
private key, and without `fsGroup` the group is root anyway.

**The security model — the BUILD API only, over mTLS.** The mini runs a
standalone `buildkitd` container that listens on `tcp://10.168.0.92:1234`. It
exposes the build API and never the Docker Engine API, and mTLS is enforced.
Proven on the mini on 2026-08-14:

| test | result |
| --- | --- |
| a native arm64 build through the node | exit 0, 9.3s |
| a client with no certificate | refused — mTLS enforced |
| `docker -H tcp://10.168.0.92:1234` | error — no Engine API on the port |
| `docker run --privileged --pid=host` through the port | error, NOT root — the escape is dead |
| `docker buildx build --allow security.insecure` | refused — the entitlement is not allowed |

The client can do one thing: submit a sandboxed build. This replaces an SSH key
that reached the Docker Engine API, which is root on the mini's VM (task #66). The
old vault item `shared/eden/macos-buildx-key` is deleted and the SSH key is
revoked.

**Why arc-org is acceptable now.** The certificate reaches every job on the
shared `arc-org` pool, but it grants only a build. The pool already stays closed
to public repositories (see `docs/ci-runners.md`), so a fork pull request cannot
reach the mini. The final pool placement stays Mateo's call, because every
repository on the pool then shares one builder on the mini. `arc-build` narrows
that exposure rather than widening it — it answers 3 workflows in 1 repository —
and the natural end state is the cert on `arc-build` alone.

**The admin key `~/.ssh/macos-ci-runner` is separate.** It stays unrestricted,
`verify-access` uses it, and it never enters the cluster.

`bash ctl.sh verify-buildx-key` asserts that the credential reaches the pod as a
file, and that the uid which mounts it can read it. It reads manifests only, so
CI runs it on every pull request. It reads `arc-org` today; `arc-build` carries
the identical mount and is not yet covered by that verb.

### The mini must serve builds after a reboot

The mini needs three things, and each one was proven necessary by removing it:

1. Docker Desktop `AutoStart=True`.
2. macOS auto-login. Docker Desktop is a GUI application, so it cannot start
   without a user session.
3. The LaunchAgent `com.gophersys.docker-autostart`. The settings flag never
   registered a login item, so it alone does not start Docker.

With items 1 and 2 only, Docker stayed down for 422 seconds after a reboot. With
all three, Docker answers 41 seconds after a reboot. The detail is in
`machines/services/macos-ci-runner/README.md`.

### How a workflow uses the node

**The runner image carries buildx. This dependency is CLOSED.** It was open
until 2026-08-16, and the paragraph that said "nothing installs it" outlived the
fix by a day — so the measurement is repeated here rather than asserted.
Measured on 2026-08-17 by running the digest the pools pinned THAT DAY,
`ghcr.io/gophersys/cloud@sha256:9a150cbf…`, at `--user 0`, which is the shape the
pod runs in. The pools have moved twice since (`245e3e9e` in #203, `ffdcf504` in
#204); this digest is deliberately NOT rewritten, because the buildx property is
what the reading establishes and editing the subject out from under a dated
measurement turns it into an assertion. Read the live pin from the manifests,
never from this line:

```
docker buildx version  ->  github.com/docker/buildx v0.36.1 1d8dde89b8ab…
```

The plugin arrives as a digest-pinned release binary, not as an apt package:
`DOCKER_BUILDX_VERSION` plus `DOCKER_BUILDX_SHA256_AMD64` in
`gophersys/.devcontainer`, installed by `_build/fetch-verified.sh` from
`base/Dockerfile` for the base family and from `_delta/components/buildx.sh` for
`cloud`. The earlier reading was correct at the time and about a different
image: `base-runner:e0c6bc5` really did exit 1 with `unknown command: docker
buildx`, because `base` then added only the compose plugin to
`/usr/local/lib/docker/cli-plugins`.

**Do not install buildx inside the job.** The rule at the top of this document
puts software capability in the image, and `validate.yml` has no tool-install
step for that reason. A download in the build path adds a network dependency and
an unpinned version to every job.

### The step to add

The image carries buildx, so this step is ready to use. What is still closed is
D42 — `SANCTIONED_PLATFORMS` is `linux/amd64` alone, so no workflow asks for an
arm64 build yet.

```yaml
- name: Point buildx at the native arm64 node
  run: |
    set -euo pipefail
    docker buildx create --name eden-mini --driver remote \
      --driver-opt cacert=/etc/buildkit-certs/ca.pem,cert=/etc/buildkit-certs/cert.pem,key=/etc/buildkit-certs/key.pem \
      tcp://10.168.0.92:1234
```

Then build with `--builder eden-mini --platform linux/arm64`. The `remote` driver
needs no ssh alias and no Docker context: buildx dials the mini's buildkitd over
mTLS with the three PEM files from the mount.

### Why the step is in the workflow, and not in the pod spec

The credential mount belongs in the pod spec, and it is there. The `create`
command does not, for three reasons:

1. **A builder is per-container state.** `docker buildx create` writes to
   `$HOME/.docker/buildx` in the runner container. Every job gets a new pod, so a
   builder made at pod start dies with that pod. The job must make it again.
2. **An init container writes to its own file system.** It cannot put the builder
   into the runner container. Only a shared volume crosses that boundary, and
   that volume would hide `$HOME/.docker`, which also holds the registry
   credentials.
3. **A wrapper around `run.sh` would touch every job.** `arc-org` is the pool that
   every repository shares. One stuck pod on it starved every repository for 47
   minutes on 2026-08-11. A step that only image builds need must not run before
   the runner starts.

The cost of item 1 is small. `docker buildx create` writes local metadata only.
The `remote` driver spawns no per-node BuildKit container: buildkitd already runs
on the mini as `eden-buildkitd`, it starts at boot, and it keeps its cache across
jobs. Measured on 2026-08-14: a fresh client with no local builder metadata,
which is what a new pod has, reused the running daemon and its cache.

**D42 stays open.** Do not add `linux/arm64` back to an image workflow in the same
change that adds this builder. Prove the builder in CI first.

## How to add a pool

1. Add a CI job in `.devcontainer/.github/workflows/build-and-push.yml`. The job
   builds `runner/Dockerfile` with `BASE_IMAGE` set to the new parent. Also add
   the image to `BUILD_ORDER` in both `ctl.sh` files. **Skip this step for a pool
   that needs no new software** — `arc-build` runs the same `cloud` image as
   `arc-org`, so it added no image and no CI job.
2. Copy `platform/services/gitops/registry/app-arc-runners-org.yaml`. Change
   `runnerScaleSetName`, the **3** image references (`init-dind-externals`, the
   runner, and the `podAntiAffinity` label is a 4th value that must follow the
   name), and any node affinity that the physical capability needs.
3. Name the pool for the capability, never for the owner.
4. Run `bash ctl.sh verify-runner-image <repository> <sha>` before you pin the
   image, and the `helm template … | kubectl apply --server-side
   --dry-run=server` procedure in `ci-runners.md` before you merge the manifest.
   The dry run is the one that catches a duplicate container name, which is the
   specific way this chart fails.
5. Prove the pool with a real job before you point a repository's default at it.

## What this replaces

The earlier plan was a CI runner image built for the purpose, carrying sudo, Go,
Node and Python. That plan is dropped. It would have been a second set of images
to maintain. It would have drifted from the dev images by construction, so the
same correction would be necessary again and again. The measured pull cost and
the private-registry result both support the current plan.
