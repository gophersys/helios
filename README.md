# .devcontainer

This repository holds the shared IDP (internal developer platform) images for
Eden. `gophersys/eden` uses it as a submodule at `.devcontainer/`. The
repository builds **5** container images:

- 1 base image with many tools. Most projects can use it directly.
- 2 domain-specific layers on top of the base image: flutter and zephyr.
- 1 remote development box on top of zephyr: zephyr-devbox.
- 1 cloud image, built from ubuntu directly rather than from base: the reduced
  base plus the CI fold. Every ARC runner pool runs it.

The `+ runner` layer (`base-runner`) was a 6th image and it is **retired**. The
pools run `cloud` now, so nothing pulls it and nothing builds it, and its
`runner/` directory is deleted.

Each image has 2 roles:

- **Local development environment.** Projects refer to these images with the
  standard `.devcontainer/` convention (VS Code / JetBrains Gateway / devpod /
  etc.). You do `docker pull` on the image and you do your work *inside* it.
  The default shell is zsh with oh-my-zsh. The bind-mount target is
  `/workspace`. The non-root `dev` user (uid 1000) has sudo-nopasswd.
- **CI runtime.** The GitHub Actions workflows in each project monorepo run
  `nx affected` inside these same images. Thus the local environment and the CI
  environment are identical.

This repository has **no Nx workspace of its own**. Every project monorepo uses
it as a submodule, and the parent supplies the Nx runtime. Each image obeys the
`project.json` + `ctl.sh` pattern enforced across the ecosystem. The command
`bash ./ctl.sh <cmd>` works with Nx and without Nx.

The body of each per-image verb is in `_ctl/lib.sh`, 1 time only. A per-image
`ctl.sh` sets its own data (the image name, and any build argument), then it
sources the library and sends the verb to it. Add a verb in the library, and
every image has it. See "The shared ctl library" below.

## Image inventory

| Image | Intent | `GOPHERSYS_DEVCONTAINER` |
|---|---|---|
| `ghcr.io/gophersys/base` | The general-purpose image. Ubuntu 24.04 + zsh/oh-my-zsh + Node LTS + Python 3.12 + Go stable + Rust stable + kubectl/helm/tailscale/docker-cli/docker-compose/bw/gh/k9s/nats + postgresql-client/sqlite3/redis-tools + jq/yq/httpie/rg/fd/bat + shellcheck/hadolint + Tauri/GTK/webkit desktop libs + libusb/libudev/libbluetooth/bluez USB-BLE libs. Every pin comes from `versions.env`. | `base` |
| `ghcr.io/gophersys/flutter` | Base + OpenJDK 21 + Android cmdline-tools / platform-tools / build-tools + Flutter stable SDK. The targets are Linux desktop and Android. iOS is not in the scope. | `flutter` |
| `ghcr.io/gophersys/zephyr` | Base + device-tree-compiler / ninja / ccache / dfu-util + `west` in an isolated venv + Zephyr SDK (arm-zephyr-eabi + riscv64-zephyr-elf by default) + udev rules for common dev boards (ST-Link, J-Link, DAPLink, Black Magic Probe, nRF, Espressif). | `zephyr` |
| `ghcr.io/gophersys/zephyr-devbox` | Zephyr + sshd (key-auth only, host keys on a PVC subpath at `/etc/ssh/hostkeys`) + openocd / stlink-tools / picocom / gdb-multiarch + `esptool` in an isolated venv + every Espressif Xtensa SDK toolchain (esp32, esp32s2, esp32s3) + CP210x/CH340 USB-UART udev rules + clangd and **code-server on `:8443`** (browser VS Code, with the clangd extension seeded at build time). It runs as a k8s pod, and it has 2 access paths: VS Code Remote-SSH, and the browser at `:8443`. It starts as root and it execs sshd. A login gets the `dev` user. code-server runs as `dev` and **needs a credential** — see "The zephyr-devbox entrypoint" below. | `zephyr-devbox` |
| `ghcr.io/gophersys/cloud` | The reduced base + the CI fold (the Actions runner, cictl, buildx, the harnesses), built `FROM ubuntu` directly rather than from `base`, so it is a reduction and not a layer. **Every ARC pool runs it**, and the same image is a devcontainer: the default command is zsh and a CI pod overrides it. Every pin comes from `versions.env`. | `cloud` |

## Dependency graph

```
        base            cloud
     ┌───┴───┐        (FROM ubuntu)
 flutter   zephyr
              │
        zephyr-devbox
```

Build in this order:

1. `base`, and `cloud` beside it — `cloud` depends on nothing here.
2. `flutter` and `zephyr`. Both layer on `base`.
3. `zephyr-devbox`. It layers on `zephyr`.

**That drawing is prose. `images.yaml` is the graph**, and it is the only place
the image set is declared. Each entry carries the image's parent, its build
context and Dockerfile, the paths a change to which rebuilds it, and the smoke
check groups it runs. Everything mechanical is derived from it: `BUILD_ORDER` in
both control scripts, the parent map and the input path table `.ci/affected.sh`
answers with, the check groups `.ci/smoke.sh` sends to the guest, the 5 publish
jobs, and the nightly scan matrix. `bash _ctl/generate.sh` writes the last 2 —
it is idempotent, and the workflows carry a GENERATED header saying so.

Adding an image is 1 entry in `images.yaml`, its directory, a regeneration, and
the hand-kept literals the policy tests carry on purpose (a test that reads the
value it checks agrees with any value, a wrong one included).

### The `+ runner` layer is retired and deleted

`runner/` held **1** Dockerfile, which added the GitHub Actions runner to any
parent image through `BASE_IMAGE`. It built `base-runner`, and `base-runner` was
what the ARC pools ran.

They run `cloud` now, pinned by digest — `cloud` folds the runner in itself
(gophersys/infrastructure #184). So the layer had no consumer: it left the image
set, which took it out of `BUILD_ORDER`, both copies of the publishing workflow,
the nightly scan matrix and `.ci/smoke.sh` in one edit. Retiring an image is 1
entry removed from `images.yaml` and a regeneration now; it was ~15 hand edits
when `base-runner` went.

The `ghcr.io/gophersys/base-runner` package is gone from the registry: read on
2026-08-17, the org's container list does not hold it and the packages API
answers 404 for it.

**The directory is deleted**, on 2026-08-18 under Mateo's D2 decision: the CI
fold lives in the shared parent, so a parent-plus-runner-layer directory has no
future role. Its content is `_delta/components/runner.sh` and
`_delta/components/agents.sh` in the `cloud` build — the same 2 downloads, at
the same URLs, from the same `versions.env` pins.

The deletion was a wave and not a `git rm`, because nothing BUILT the directory
and 4 mechanisms still READ it: `runner/Dockerfile` was 1 of the 5 pin homes the
Monday bump wrote into and 1 of the 6 governed download files, it carried a
`_build/download-exemptions.txt` row, and 5 test files held a `runner/` path as
a literal. Read `.claude/rules/00-identity.md` for the file-by-file record; the
general lesson is that "nothing builds it" is not "nothing reaches it".

The reason a runner image is the image of the POD, and never a workflow
`container:` image, is unchanged and now answered by `cloud`:

1. The dind daemon in the runner pod pulls a `container:` image, and the image
   is lost when the pod stops. For an image of this size the cost is 5m17s per
   job.
2. To pull a private package with `GITHUB_TOKEN` you need a grant for each
   (package, repository) pair. GitHub gives that grant only in its user
   interface. A kubelet pull has neither problem, and 1 in-cluster
   `imagePullSecret` covers every image and every repository.

The full interface is in `gophersys/infrastructure` `docs/ci-substrate.md`.

## How to use

Pull an image directly:

```sh
docker pull ghcr.io/gophersys/base:latest
docker pull ghcr.io/gophersys/cloud:latest
docker pull ghcr.io/gophersys/flutter:latest
docker pull ghcr.io/gophersys/zephyr:latest
docker pull ghcr.io/gophersys/zephyr-devbox:latest
```

### As a VS Code devcontainer

A consuming project mounts this repository at `<project>/.devcontainer/`. Each
image directory contains its own `devcontainer.json`. Run **Dev Containers:
Reopen in Container** and select `base`, `cloud`, `flutter`, `zephyr` or
`zephyr-devbox`. Each configuration bind-mounts the project to `/workspace` and
runs as the `dev` user. The configuration files are at these paths:

```
.devcontainer/base/devcontainer.json
.devcontainer/cloud/devcontainer.json
.devcontainer/flutter/devcontainer.json
.devcontainer/zephyr/devcontainer.json
.devcontainer/zephyr-devbox/devcontainer.json
```

`cloud/devcontainer.json` carries no `postCreateCommand` and `base` does. The
difference is where the harnesses come from: `cloud` bakes claude, omp and codex
into the image through `_delta/components/agents.sh` at the `versions.env` pins,
so a container start does zero network installs. `base` ships no harness, so
`base/ctl.sh post-create` installs them at create time.

### As the CI runtime

The image is the image of the **pod**, and never a workflow `container:` image.
A job names an ARC pool and no container:

```yaml
jobs:
  build:
    runs-on: arc-build
    steps:
      - uses: actions/checkout@v4
      - run: npx nx affected -t build
```

**This section used to show `runs-on: ubuntu-latest` with a `container:` key,
and both halves are forbidden here.** Two measurements say so. The dind daemon
in the runner pod pulls a `container:` image and loses it when the pod stops: at
this image size that is 5m17s per job. And a `GITHUB_TOKEN` pull of a private
package needs a grant for each (package, repository) pair, which GitHub gives
only in its user interface — while 1 in-cluster `imagePullSecret` covers every
image and every repository. Nothing in this repository runs on a GitHub-hosted
runner either; see "Every job runs on `arc-build`" below.

Which pool an image backs is declared in `gophersys/infrastructure`
`docs/ci-substrate.md`. All 3 ARC pools run `cloud`, pinned by digest.

### Detect the image at runtime

Use this code in a script or in CI:

```sh
case "${GOPHERSYS_DEVCONTAINER}" in
  base)          echo "running in the base image" ;;
  cloud)         echo "running in the cloud image" ;;
  flutter)       echo "running in the flutter layer" ;;
  zephyr)        echo "running in the zephyr layer" ;;
  zephyr-devbox) echo "running in the zephyr-devbox layer" ;;
  *)             echo "not inside a gophersys devcontainer" ;;
esac
```

**The `cloud)` arm is not optional.** Every ARC pool runs `cloud`, so a copy of
this block without that arm sends every CI job to the `*)` arm and prints "not
inside a gophersys devcontainer" from inside a gophersys devcontainer. That arm
was missing here while the same README said 45 lines higher that the pools run
`cloud`.

### The zephyr-devbox entrypoint

`zephyr-devbox/devbox-entrypoint.sh` is PID 1 of the pod. Read that file for the
full contract. sshd is the LAST thing it does, and these steps come first:

| Step | What it does | Operator knob |
|---|---|---|
| argv pass-through | Execs any argv you supply and stops there, so a local `docker run <image> zsh` behaves like the other layers. | — |
| host keys | Generates ed25519 + rsa keys into `/etc/ssh/hostkeys` (a PVC subpath), so the box keeps its SSH identity across restarts. | — |
| mountpoint ownership | Chowns and chmods `/home/dev` and `/workspace`, **non-recursively** — recursing a populated home on every boot is slow and tramples intentional ownership. | — |
| authorized_keys | Takes the keys from `DEVBOX_AUTHORIZED_KEYS`, else from a mounted `/etc/devbox/authorized_keys`, else leaves the persistent home's file alone. | `DEVBOX_AUTHORIZED_KEYS` |
| mcu slots | Recreates `/dev/mcu-slot-1..6` from `/dev/serial/by-path`. A symlink at the node's `/dev` root does not reach the pod. Slot N is guest USB port N is physical hub slot N. | — |
| code-server | Starts it as `dev` on `0.0.0.0:8443`, under a supervisor loop that logs and restarts every exit. | `DEVBOX_CODE_SERVER_HASHED_PASSWORD` **or** `DEVBOX_CODE_SERVER_AUTH=none-behind-proxy` |

**code-server auth is required by default.** Set
`DEVBOX_CODE_SERVER_HASHED_PASSWORD` to an argon2 hash (code-server's own
`HASHED_PASSWORD` contract, usually from a Secret), or set
`DEVBOX_CODE_SERVER_AUTH=none-behind-proxy` to declare that an authenticating
proxy owns the port. With neither set, code-server does NOT start and the
refusal names both knobs. The reason is measured: the account code-server runs
as holds passwordless sudo, so a reachable unauthenticated `:8443` is root on
the pod for any peer the network admits — and the network boundary is a
NetworkPolicy in another repository, which this file cannot see and must not
trust as the only wall.

**Every refusal writes `/run/devbox-degraded` and logs ERROR, not WARNING.**
sshd still runs, because code-server is supplementary and a missing credential
must not take the primary service down. A pod that reports Running while a
declared service is absent is the failure mode this entrypoint used to have, so
the marker file gives a probe or an operator machine-readable state to find.

## Sanctioned-platform policy

Every image here publishes **1** platform: `linux/amd64`. `SANCTIONED_PLATFORMS`
in `_ctl/lib.sh` declares it, and it is the only place a platform is named. A
platform outside that set fails the guard and names itself, so a future edit that
re-adds one fails loudly instead of quietly restoring an emulated build.

| Verb | Behavior |
|---|---|
| `build` | `docker build --platform "$IMAGE_PLATFORMS"`. The `--platform` is explicit: a bare `docker build` targets the HOST, which on an Apple Silicon Mac is not the platform that gets published. |
| `push` | `docker buildx build --platform "$IMAGE_PLATFORMS" --push`. The guard `require_buildx_and_platforms` runs at the start of the verb. |
| `verify-published [tag]` | Read the manifest the registry holds and assert it carries exactly the sanctioned set. |

The guard is in `_ctl/lib.sh`, 1 time only, and each per-image `push` calls it.
It fails closed in 5 conditions: a platform outside the sanctioned set, an empty
platform list, buildx absent, no buildx builder active, or the active builder
unable to build 1 of the required platforms. The list an image builds is
`IMAGE_PLATFORMS`; it defaults to the sanctioned set, and an image may declare a
measured NARROWER list but never a wider one.

The repository-root `ctl.sh` does **not** call the guard. It sends `push` to
the per-image `ctl.sh`, which calls the guard with its own list of platforms.
The root script cannot call the guard correctly, because the list is not the
same for every image.

The CI workflow `.github/workflows/build-and-push.yml` enforces the same policy
on every push to `main` and on every semver tag (`v*`), and each of its jobs runs
`verify-published` against the SHA tag it just pushed.

### Why there is no arm64 variant

Every image runs where its consumers are, and every consumer that could be
verified is amd64:

- `cloud` runs only as an ARC pod, and every node in that cluster is amd64. So
  did `base-runner`, which it replaced.
- `zephyr-devbox` runs only as a kubernetes pod. Its 3 live pods sat on
  `k3s-w-1`, `k3s-w-3` and `k3s-w-4`, and all 3 are amd64.
- `base`, `flutter` and `zephyr` published an arm64 variant until it was measured.
  The published `base` arm64 image was an amd64 Ubuntu userland carrying aarch64
  Go binaries: the `FROM` line pinned the userland to the BUILD host while buildx
  labelled the result with the TARGET platform. It was mislabelled rather than
  native, and on an Apple Silicon host Docker Desktop emulates that userland
  anyway, which is why nobody noticed. It gave none of the benefit of a native
  image and cost the larger half of a 41.7-minute build.

This command shows the architecture of each node:

```sh
kubectl get nodes -o custom-columns=NAME:.metadata.name,ARCH:.status.nodeInfo.architecture
```

The rule is: **build only the architecture that you deploy to.** No arm64
consumer can be verified for any image today, which is open in
gophersys/infrastructure `docs/debt-register.md` as D42. Widen
`SANCTIONED_PLATFORMS` on the day a consumer exists, and not before.

## How to add a tool

1. **Select the latest LTS or stable release.** Do the research with
   apt-cache, with the upstream GitHub releases, or with pypi. Never invent a
   version.
2. **Add its row to `versions.env`** with a comment, and a value-less `ARG` at
   the top of the Dockerfile that installs it:
   ```
   MY_TOOL_VERSION=1.2.3  # latest LTS as of YYYY-MM-DD
   ```
   ```dockerfile
   ARG MY_TOOL_VERSION
   ```
   `versions.env` is the ONE pin home of `base` and `cloud`. There is no second
   home and no `ARG NAME=value` in either file: the value arrives as a generated
   `--build-arg`, and a name you forget to add to the Dockerfile's pin gate is
   the 1 way to lose it silently. A tool of `flutter`, `zephyr` or
   `zephyr-devbox` still takes an `ARG MY_TOOL_VERSION=1.2.3` in that image's
   own Dockerfile — those 3 have not moved yet, and moving them is ledger #102.
3. **Add its sha256 digest row beside that version**, in the SAME home. The
   value comes from the asset you just selected, never from a second table:
   ```
   MY_TOOL_VERSION=1.2.3  # latest LTS as of YYYY-MM-DD
   MY_TOOL_SHA256_AMD64=<64 lowercase hex>  # upstream-published: <checksum file url>
   ```
   The vocabulary is `_SHA256_AMD64`, or `_SHA256_NOARCH` when 1 asset serves
   every platform. Write `# upstream-published: <url>` when the release ships a
   checksum file and the 2 values agree; write `# computed-at-pin: YYYY-MM-DD`
   when it does not. Both spellings are read by
   `_ctl/tests/download-coverage.test.sh`, which fails a digest with neither.
   The digest takes a value-less `ARG` and a pin-gate entry of its own, exactly
   like the version: an empty digest is what an unverified download looks like.
4. **Fetch it through the verified fetcher.** A bare `curl` or `wget` is
   forbidden, and `bash ./ctl.sh test` names it:
   ```sh
   /usr/local/lib/gophersys/fetch-verified.sh \
     "https://example.com/my-tool-${MY_TOOL_VERSION}-linux-${ARCH}.tar.gz" \
     /tmp/my-tool.tar.gz \
     "${MY_TOOL_SHA256_AMD64}" MY_TOOL_SHA256_AMD64
   ```
   The digest name is passed twice on purpose: once for its value, once as the
   name the failure message prints. `base` and `cloud` COPY the helper from
   `_build/`; the other 4 images inherit it through their `FROM`. When a
   download cannot carry a digest, add 1 row to `_build/download-exemptions.txt`
   naming its class and the reason. Those are the only 2 answers.
5. **Say where its next version comes from.** Add 1 row to
   `_build/upstreams.txt`, `<pin>|<datasource>|<coordinate>|<policy>`:
   ```
   MY_TOOL_VERSION|github-release|myowner/mytool|bump to the newest release github marks latest
   ```
   A pin with no row fails `bash ./ctl.sh test`, and a row for a pin that is
   gone fails it too. When no upstream can answer, the row takes the
   `no-autobump` datasource and its 4th field states WHY, in a sentence. Those
   are the only 2 answers: a pin nobody watches is a snapshot that looks
   current forever.
6. **Use the ARG in the RUN line, and name it in the pin gate.** A hardcoded
   semver in a `RUN` line is forbidden: the command `bash ./ctl.sh validate`
   searches for a semver in a `RUN` line and fails. In `base/Dockerfile` and
   `cloud/Dockerfile` add the name to the `RUN : "${PIN:?not in versions.env}"`
   chain at the top as well — a value-less ARG that nothing feeds expands to the
   empty string, and the build would otherwise reach a download URL with no
   version in it.
7. **Make every binary installation read `TARGETPLATFORM`**:
   ```sh
   case "$TARGETPLATFORM" in
     linux/amd64) ARCH=amd64 ;;
     *) echo "unsupported platform: $TARGETPLATFORM"; exit 1 ;;
   esac
   ```
   Write the amd64 arm only. `SANCTIONED_PLATFORMS` is `linux/amd64` alone, and
   an arm64 arm needs an arm64 digest that no build ever compares — a check that
   cannot fail. The `*)` arm is what makes an unsanctioned platform stop the
   build instead of installing the wrong binary. Restore both the arm and its
   `_SHA256_ARM64` row together, on the day `SANCTIONED_PLATFORMS` widens.
8. **Remove the temporary files in the same layer.** For apt, use
   `rm -rf /var/lib/apt/lists/*`.
9. **You must get approval.** A new tool and a version change need Mateo's
   approval on the pull request. They reach every image below this one in the
   graph, and the ARC pools run `cloud`.
10. Run `bash ./ctl.sh validate` and `bash ./ctl.sh test` until both report no
   error. Then run `bash ./ctl.sh build base` to make sure that the chain of
   images still builds.

## Repository layout

```
.devcontainer/
├── README.md
├── project.json                 # repo-level Nx wiring (list, validate, test)
├── ctl.sh                       # repo-wide control script
├── images.yaml                  # the ONE declaration of the image SET
├── versions.env                 # the ONE pin home of base and cloud
├── _ctl/lib.sh                  # the shared ctl library — every verb body, 1 time only,
│                                #   and the images.yaml reader every home derives from
├── _ctl/generate.sh             # images.yaml -> the publish jobs + the nightly matrix
├── _ctl/tests/                  # hermetic *.test.sh + harness + docker stub + fixtures
├── _build/                      # COPYed into base and cloud, above their first download
│   ├── fetch-verified.sh        # the ONE verifier every image download goes through
│   ├── download-exemptions.txt  # the downloads that take a stated class instead of a digest
│   ├── upstreams.txt            # where the next value of every pin comes from
│   └── resolve-upstream.sh      # the weekly resolver — 1 function per datasource
├── _delta/components/           # 1 file per folded tool group; cloud COPYs them and runs them
├── docs/                        # PROPOSALS for images that do not exist yet — see docs/README.md
├── .claude/rules/               # identity + conventions
├── .ci/                         # the CI layer — .ci/README.md lists every file
│   ├── affected.sh              # which images a commit changes — 1 home for the answer
│   ├── buildx-node.sh           # the builder every image build uses; owns the arm64 switch
│   └── mirror-buildkit.sh       # keeps ghcr.io holding the BuildKit index the builder boots from
├── base/          { devcontainer.json, Dockerfile, project.json, ctl.sh }
├── cloud/         { devcontainer.json, Dockerfile, project.json, ctl.sh }
├── flutter/       { devcontainer.json, Dockerfile, project.json, ctl.sh }
├── zephyr/        { devcontainer.json, Dockerfile, project.json, ctl.sh }
├── zephyr-devbox/ { devcontainer.json, Dockerfile, project.json, ctl.sh, devbox-entrypoint.sh }
└── .github/workflows/
    ├── build-and-push.yml    # publish the images
    ├── security-nightly.yml  # the nightly trivy scan + the base-OS currency probe
    ├── weekly-bumps.yml      # the weekly upstream resolution + the 1 bump pull request
    ├── validate.yml          # the pull request gate: ctl.sh validate + ctl.sh test + BUILD_ORDER
    └── pr-review.yml         # the review agent, shared from gophersys/cictl
```

### The shared ctl library

`_ctl/lib.sh` holds the body of every per-image verb, 1 time only. The name
follows `gophersys/libs`, which uses `go/_ctl/lib.sh` for the same purpose. The
leading underscore keeps the directory out of the set of image directories.

A per-image `ctl.sh` is a thin dispatcher. It sets its data, it sources the
library, and it sends the verb to `image_main`:

```sh
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
IMAGE_NAME="flutter"
source "$PROJECT_ROOT/../_ctl/lib.sh"
image_main "$@"
```

The library reads this data. **Set the first 6 items BEFORE the source line**,
because the library reads them while it loads. It reads the last 2 at call time,
so those may be set after:

| Name | Use |
|---|---|
| `PROJECT_ROOT` | The directory that holds the script. Required. |
| `IMAGE_NAME` | The image slug, for example `flutter`. Required for the image verbs. |
| `IMAGE_PLATFORMS` | The platforms this image builds. The default is `SANCTIONED_PLATFORMS`. Narrower is allowed with a measurement; wider is refused. |
| `IMAGE_BUILD_ARGS` | An array of extra arguments for `docker build`. `base/ctl.sh` and `cloud/ctl.sh` each fill it from `versions.env` through `versions_env_build_args` — the same 1 line, because there is 1 pin mechanism. |
| `IMAGE_BUILD_CONTEXT` | The `docker build` context. The default is `PROJECT_ROOT`. `base/ctl.sh` and `cloud/ctl.sh` both set the repository root, because they COPY `_build/` and read `versions.env` (and cloud `_delta/`), which sit 1 level above their directory. |
| `IMAGE_DOCKERFILE` | An explicit `--file`. The default is empty, which keeps docker's own `<context>/Dockerfile`. Set it whenever `IMAGE_BUILD_CONTEXT` is not the image directory. |
| `IMAGE_USAGE_HEADER` | Extra lines below the `Image:` header of the help text. |
| `IMAGE_USAGE_COMMANDS` | Extra lines below the command list of the help text. |

The last 2 rows of the first 6 are not optional in practice. A per-image script
written from an earlier version of this table — which listed 4 rows and omitted
both — would build `base` with `base/` as its context and die on
`COPY _build/`, because the fetcher is not inside the image directory.

An image that adds a verb handles that verb itself and sends every other verb
to `image_main`. `base/ctl.sh` does this for `up`, `exec`, `shell`, `down` and
`post-create`.

**8 non-image scripts source the same library**, and not for the same contract.
`ctl.sh`, `.ci/ctl.sh`, `.ci/smoke.sh`, `.ci/affected.sh` and
`.ci/notify-failure.sh` take the logging, the tool gate and the guard.
`.ci/buildx-node.sh` and `.ci/mirror-buildkit.sh` take the platform and BuildKit
declarations (`SANCTIONED_PLATFORMS`, `BUILDKIT_REF`, `BUILDKIT_UPSTREAM_REF`).
`_build/resolve-upstream.sh` takes the pin readers and the writer — `pin_value`,
`homes_of`, `digest_row_of`, `fetch_urls` and `bump_pin`. Their own verbs act on
the whole set of images, so they keep those verbs themselves.

`validate` runs `shellcheck -x -S style` over every shell script in the
repository — found by `*.sh` name **or** by a shell shebang, so a script with no
extension is not skipped. `-x` follows the source line, so each script is checked
together with the library, and a new script is linted wherever you put it. It
refuses to report OK when it finds no script at all.

`validate` lints Dockerfiles at the hadolint version `versions.env` pins in
`HADOLINT_VERSION`: the `hadolint` on PATH when its version matches,
otherwise `hadolint/hadolint:v<pin>` through docker. A gate whose verdict depends
on which hadolint the operator happened to install is not a gate.

### The tests

`_ctl/tests/` holds hermetic test files. They are hermetic in the strict sense:
a stub `docker` goes first on `PATH`, so no daemon is contacted, no socket is
opened and no registry is resolved. `bash ./ctl.sh test` runs every
`_ctl/tests/*.test.sh`, and it **fails when it finds none** — a glob that stopped
matching would otherwise report a green run that checked nothing.

**There is no EXIT trap in these scripts, and that is deliberate.** Each script
carried a `BG_PIDS` array and an `on_exit` trap that killed the listed
processes. No script ever added a process to the array. On bash 3.2, which is
the bash of macOS, `$?` is 0 when the EXIT trap starts after the shell aborts
on an unbound variable, so the trap made the script exit 0. It reported success
for a fatal abort. A script that starts a background job must clean up its own
job, and it must not add an EXIT trap that returns a status.

## Day-to-day operations

Run these commands from the repository root:

```sh
# Build for the sanctioned platform (fast dev loop).
bash ./ctl.sh build base
bash ./ctl.sh build flutter
bash ./ctl.sh build zephyr
bash ./ctl.sh build zephyr-devbox
bash ./ctl.sh build cloud

# Push (guarded).
bash ./ctl.sh push base

# Read the published manifest back and assert its platform set.
bash ./ctl.sh verify-published base
bash ./ctl.sh verify-published base e0c6bc5

# List canonical image refs.
bash ./ctl.sh list

# Lint every shell script, validate JSON, lint Dockerfiles at the pinned
# hadolint version, enforce ARG discipline.
bash ./ctl.sh validate

# Run every hermetic test under _ctl/tests/.
bash ./ctl.sh test
```

Run these commands for 1 image, from inside the image directory:

```sh
cd base
bash ./ctl.sh build
bash ./ctl.sh push
bash ./ctl.sh inspect
```

## CI

The workflow `.github/workflows/build-and-push.yml` publishes the images on a
push to `main`. It tags each image it builds with `:latest` and with the short
commit SHA. On a push of a semver tag (`v*`) it also publishes `:v<semver>`. It
builds with `--platform ${{ env.PLATFORMS }}`, then reads the manifest back with
`verify-published` at the SHA tag it just pushed. It sets up no QEMU: emulation
is what a cross-platform build needed, and there is no cross-platform build. The
workflow needs the `packages: write` permission. The permission is set in the
workflow.

**It builds only what the commit changed.** A warm rebuild of the whole set cost
~35 minutes on every push, and most pushes touch 1 image or none. Each job asks
`bash .ci/affected.sh <image>` whether the commit changes that image's inputs,
and gates its build, its smoke, its push and its manifest read on the answer.
That file is the one home of the input table, and of the parent map that makes a
child rebuild whenever its parent does. Everything builds on
`workflow_dispatch`, on a tag, and on any change to a workflow or to `.ci/`.

**An image that did not build keeps the `:latest` it already had**, and no
`:<sha>` tag exists for that commit. A SHA tag is therefore not a promise that
every image carries that SHA.

**The layer cache is `ghcr.io/gophersys/<image>-cache`**, 1 registry package per
image, written `mode=max` by the build that loads and read by the build that
pushes. The Actions cache service gives 10 GB per repository across every scope,
which 5 images at `mode=max` do not fit.

**The builder comes from `bash .ci/buildx-node.sh`** and not from
`docker/setup-buildx-action`. It makes the same `docker-container` builder — the
default `docker` driver can neither read nor write a registry cache — and it
owns the switch that appends the Mac mini as a native arm64 node the day
`SANCTIONED_PLATFORMS` names `linux/arm64`. That switch reads the library, so
widening the set is still 1 edit.

**Every job runs on `arc-build`**, the homelab ARC pool, and so do the nightly
scan and the weekly bump. Nothing in this repository runs on a GitHub-hosted
runner. No job may add a free-disk action either: it reclaims space by deleting
the preinstalled SDKs of a throwaway hosted VM, and on our nodes the same
deletion strips the NODE. `_ctl/tests/workflow-yaml.test.sh` holds both halves.

The workflow `.github/workflows/validate.yml` is the pull request gate. It runs
`bash ./ctl.sh validate`, `bash ./ctl.sh test`, and the BUILD_ORDER agreement
check. That last step is now VACUOUS and is left in place for a follow-up: both
control scripts fill `BUILD_ORDER` from `images.yaml`, so the 2 literals the
step greps are equal by construction and it can no longer fail.

The workflow `.github/workflows/security-nightly.yml` scans the published images
for CRITICAL vulnerabilities every night and reports the night ubuntu moves under
the digest `UBUNTU_BASE_REF` pins. It builds and publishes nothing. Its matrix
declares `max-parallel: 3`, because `arc-build` has 6 slots that every
repository shares and nobody is waiting for a scan at 02:00 MST.

The workflow `.github/workflows/weekly-bumps.yml` runs every Monday. It asks the
upstream named in each row of `_build/upstreams.txt` what it publishes now, and
where anything moved it writes the new version and the new sha256 into every home
of that pin and opens ONE pull request. Every sha256 is the digest of the asset
for the version the same run resolved, and it is re-proven through
`_build/fetch-verified.sh` before a line is written, so a bump cannot carry a
stale digest. It merges nothing.

**One unreadable upstream fails the whole run.** It resolves every row first,
reports every pin that moved AND every pin it could not read, writes nothing and
exits non-zero. A run that bumped the pins it happened to reach would let the
absence of the others read as "nothing moved", and a run that stopped at the
first bad row would hide the real bumps behind it. A pin that resolves nothing on
purpose takes a `no-autobump` row with a stated reason instead — 16 do today, and
each reason has to be TRUE: 3 of them were rewritten after their coordinates were
measured against the real API, with the whole suite green before and after.

**A bump pull request arrives with no checks on it.** GitHub starts no workflow
run for an event a `GITHUB_TOKEN` caused, so `validate.yml` does not fire on the
branch this workflow pushes. Close and reopen the pull request, or push to its
branch, to start the gates — and never merge it before they are green.

Both scheduled workflows report a failure through `.ci/notify-failure.sh`, which
opens or updates ONE labelled issue and closes it on the next green run. The
label is a parameter: the nightly scan uses the default `ci-nightly-red` and the
weekly bump passes `ci-weekly-red`, so a green Monday cannot retire the scan's
open issue about a CVE.

## Shared-change propagation

After a change merges to `main`, Eden keeps the previous commit. Eden gets the
change only when a person moves its submodule pointer:

```sh
# From the eden checkout:
git -C .devcontainer fetch origin
git -C .devcontainer checkout <sha>
git add .devcontainer && git commit
```

**There is no `propagate` verb and no fan-out script.** This section used to
show `bash brain/.claude/scripts/propagate.sh` and `bash ./ctl.sh propagate`.
Neither path exists: `brain` is the pre-Eden name of the parent, Eden has no
`.claude/scripts/` directory, and the verb took its own error branch at every
invocation. The pointer bump is 1 commit in 1 consumer. It needs Mateo's
approval, like any other merge.
