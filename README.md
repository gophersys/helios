# .devcontainer

This repository holds the shared IDP (internal developer platform) images for
every project in the brain ecosystem. The repository builds **5** container
images:

- 1 base image with many tools. Most projects can use it directly.
- 2 domain-specific layers on top of the base image: flutter and zephyr.
- 1 remote development box on top of zephyr: zephyr-devbox.
- 1 `+ runner` layer. It changes any of the other images into a GitHub Actions
  runner image. The result is base-runner.

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
| `ghcr.io/gophersys/base` | The general-purpose image. Ubuntu 24.04 + zsh/oh-my-zsh + Node LTS + Python 3.12 + Go stable + Rust stable + kubectl/helm/tailscale/docker-cli/docker-compose/bw/gh/k9s/nats + postgresql-client/sqlite3/redis-tools + jq/yq/httpie/rg/fd/bat + shellcheck/hadolint + Tauri/GTK/webkit desktop libs + libusb/libudev/libbluetooth/bluez USB-BLE libs. | `base` |
| `ghcr.io/gophersys/flutter` | Base + OpenJDK 17 + Android cmdline-tools / platform-tools / build-tools + Flutter stable SDK. The targets are Linux desktop and Android. iOS is not in the scope. | `flutter` |
| `ghcr.io/gophersys/zephyr` | Base + device-tree-compiler / ninja / ccache / dfu-util + `west` in an isolated venv + Zephyr SDK (arm-zephyr-eabi + riscv64-zephyr-elf by default) + udev rules for common dev boards (ST-Link, J-Link, DAPLink, Black Magic Probe, nRF, Espressif). | `zephyr` |
| `ghcr.io/gophersys/base-runner` | Base + the GitHub Actions runner at `/home/runner`, owned by `dev`. **This is not a devcontainer.** It has no `devcontainer.json`. An ARC pool runs this image as its runner container, so the kubelet keeps the image in the cache on each node and a job does not wait for a cold pull. The build uses `runner/Dockerfile`. That Dockerfile takes `BASE_IMAGE`, so it serves every parent image. | `base` (inherited) |
| `ghcr.io/gophersys/zephyr-devbox` | Zephyr + sshd (key-auth only, host keys on a PVC subpath at `/etc/ssh/hostkeys`) + openocd / stlink-tools / picocom / gdb-multiarch + `esptool` in an isolated venv + every Espressif Xtensa SDK toolchain (esp32, esp32s2, esp32s3) + CP210x/CH340 USB-UART udev rules. It runs as a k8s pod. You connect to it with VS Code Remote-SSH. It starts as root and it execs sshd. A login gets the `dev` user. | `zephyr-devbox` |

## Dependency graph

```
           base
    ┌────┬──┴──┐
base-   flutter  zephyr
runner              │
              zephyr-devbox
```

Build in this order:

1. `base`.
2. `base-runner`, `flutter` and `zephyr`. All 3 layer on `base`.
3. `zephyr-devbox`. It layers on `zephyr`.

### The `+ runner` layer

`runner/` holds **1** Dockerfile. It adds the GitHub Actions runner to any
parent image, and it changes nothing else. `BASE_IMAGE` selects the parent
image. Thus a future `zephyr-runner` or `kicad-runner` needs only a build
argument and a CI job. Never write a second Dockerfile to keep in step.

```sh
bash ./ctl.sh build base-runner              # parent defaults to base
RUNNER_PARENT=zephyr bash runner/ctl.sh build
```

The runner layer is a pod image and not a workflow `container:` image. There
are 2 measured reasons:

1. The dind daemon in the runner pod pulls a `container:` image, and the image
   is lost when the pod stops. For an image of this size the cost is 5m17s per
   job.
2. To pull a private package with `GITHUB_TOKEN` you need a grant for each
   (package, repository) pair. GitHub gives that grant only in its user
   interface.

The runner layer is the image of the pod itself. Thus the kubelet pulls it,
keeps it in the cache on each node, and authenticates with 1 in-cluster
`imagePullSecret`. The full interface is in `gophersys/infrastructure`
`docs/ci-substrate.md`.

## How to use

Pull an image directly:

```sh
docker pull ghcr.io/gophersys/base:latest
docker pull ghcr.io/gophersys/flutter:latest
docker pull ghcr.io/gophersys/zephyr:latest
docker pull ghcr.io/gophersys/zephyr-devbox:latest
```

### As a VS Code devcontainer

A consuming project mounts this repository at `<project>/.devcontainer/`. Each
image directory contains its own `devcontainer.json`. Run **Dev Containers:
Reopen in Container** and select `base`, `flutter`, `zephyr` or
`zephyr-devbox`. Each configuration bind-mounts the project to `/workspace` and
runs as the `dev` user. The configuration files are at these paths:

```
.devcontainer/base/devcontainer.json
.devcontainer/flutter/devcontainer.json
.devcontainer/zephyr/devcontainer.json
.devcontainer/zephyr-devbox/devcontainer.json
```

### As a GitHub Actions job container

```yaml
jobs:
  build:
    runs-on: ubuntu-latest
    container:
      image: ghcr.io/gophersys/base:latest
    steps:
      - uses: actions/checkout@v4
      - run: npx nx affected -t build
```

### Detect the image at runtime

Use this code in a script or in CI:

```sh
case "${GOPHERSYS_DEVCONTAINER}" in
  base)          echo "running in the base image" ;;
  flutter)       echo "running in the flutter layer" ;;
  zephyr)        echo "running in the zephyr layer" ;;
  zephyr-devbox) echo "running in the zephyr-devbox layer" ;;
  *)             echo "not inside a gophersys devcontainer" ;;
esac
```

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

- `base-runner` runs only as an ARC pod, and every node in that cluster is amd64.
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
2. **Add an `ARG` at the top of the Dockerfile** with a comment:
   ```dockerfile
   ARG MY_TOOL_VERSION=1.2.3  # latest LTS as of YYYY-MM-DD
   ```
3. **Add its sha256 digest row beside that version**, in the SAME home. The
   value comes from the asset you just selected, never from a second table:
   ```dockerfile
   ARG MY_TOOL_VERSION=1.2.3  # latest LTS as of YYYY-MM-DD
   ARG MY_TOOL_SHA256_AMD64=<64 lowercase hex>  # upstream-published: <checksum file url>
   ```
   The vocabulary is `_SHA256_AMD64`, or `_SHA256_NOARCH` when 1 asset serves
   every platform. Write `# upstream-published: <url>` when the release ships a
   checksum file and the 2 values agree; write `# computed-at-pin: YYYY-MM-DD`
   when it does not. Both spellings are read by
   `_ctl/tests/download-coverage.test.sh`, which fails a digest with neither.
   A tool of the cloud family puts both rows in `versions.env`, adds a
   value-less `ARG` to `cloud/Dockerfile`, and adds the name to its pin gate.
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
6. **Use the ARG in the RUN line.** A hardcoded semver in a `RUN` line is
   forbidden. The command `bash ./ctl.sh validate` searches for a semver in a
   `RUN` line and fails.
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
9. **You must get approval.** A new tool and a version change go through the
   brain-level approval gate. They have an effect on every consuming project.
10. Run `bash ./ctl.sh validate` and `bash ./ctl.sh test` until both report no
   error. Then run `bash ./ctl.sh build base` to make sure that the chain of
   images still builds.

## Repository layout

```
.devcontainer/
├── README.md
├── project.json                 # repo-level Nx wiring (list, validate, propagate, release)
├── ctl.sh                       # repo-wide control script
├── _ctl/lib.sh                  # the shared ctl library — every verb body, 1 time only
├── _ctl/tests/                  # hermetic *.test.sh + harness + docker stub + fixtures
├── _build/                      # COPYed into base and cloud, above their first download
│   ├── fetch-verified.sh        # the ONE verifier every image download goes through
│   ├── download-exemptions.txt  # the downloads that take a stated class instead of a digest
│   ├── upstreams.txt            # where the next value of every pin comes from
│   └── resolve-upstream.sh      # the weekly resolver — 1 function per datasource
├── .claude/rules/               # identity + conventions
├── base/          { devcontainer.json, Dockerfile, project.json, ctl.sh }
├── runner/        { Dockerfile, project.json, ctl.sh }   # + runner layer, no devcontainer.json
├── flutter/       { devcontainer.json, Dockerfile, project.json, ctl.sh }
├── zephyr/        { devcontainer.json, Dockerfile, project.json, ctl.sh }
├── zephyr-devbox/ { devcontainer.json, Dockerfile, project.json, ctl.sh, devbox-entrypoint.sh }
└── .github/workflows/build-and-push.yml
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

The library reads this data. Set the first 4 items before the source line:

| Name | Use |
|---|---|
| `PROJECT_ROOT` | The directory that holds the script. Required. |
| `IMAGE_NAME` | The image slug, for example `flutter`. Required for the image verbs. |
| `IMAGE_PLATFORMS` | The platforms this image builds. The default is `SANCTIONED_PLATFORMS`. Narrower is allowed with a measurement; wider is refused. |
| `IMAGE_BUILD_ARGS` | An array of extra arguments for `docker build`. `runner/ctl.sh` puts `BASE_IMAGE` here. |
| `IMAGE_USAGE_HEADER` | Extra lines below the `Image:` header of the help text. |
| `IMAGE_USAGE_COMMANDS` | Extra lines below the command list of the help text. |

An image that adds a verb handles that verb itself and sends every other verb
to `image_main`. `base/ctl.sh` does this for `up`, `exec`, `shell`, `down` and
`post-create`.

The repository-root `ctl.sh`, `.ci/ctl.sh` and `.ci/smoke.sh` source the same
library for the logging, the tool gate and the guard. Their own verbs act on
the whole set of images, so they keep those verbs themselves.

`validate` runs `shellcheck -x -S style` over every shell script in the
repository — found by `*.sh` name **or** by a shell shebang, so a script with no
extension is not skipped. `-x` follows the source line, so each script is checked
together with the library, and a new script is linted wherever you put it. It
refuses to report OK when it finds no script at all.

`validate` lints Dockerfiles at the hadolint version `base/Dockerfile` pins in
`ARG HADOLINT_VERSION`: the `hadolint` on PATH when its version matches,
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
bash ./ctl.sh build base-runner
bash ./ctl.sh build flutter
bash ./ctl.sh build zephyr
bash ./ctl.sh build zephyr-devbox

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

The workflow `.github/workflows/build-and-push.yml` builds and publishes all 5
images on every push to `main`. It tags each image with `:latest` and with the
short commit SHA. On a push of a semver tag (`v*`) it also publishes
`:v<semver>`. It sets up buildx and builds with `--platform ${{ env.PLATFORMS }}`,
then reads the manifest back with `verify-published` at the SHA tag it just
pushed. It sets up no QEMU: emulation is what a cross-platform build needed, and
there is no cross-platform build. The workflow needs the `packages: write`
permission. The permission is set in the workflow.

The workflow `.github/workflows/validate.yml` is the pull request gate. It runs
`bash ./ctl.sh validate`, `bash ./ctl.sh test`, and the BUILD_ORDER agreement
check.

The workflow `.github/workflows/security-nightly.yml` scans the published images
for CRITICAL vulnerabilities every night and reports the night ubuntu moves under
the digest `UBUNTU_BASE_REF` pins. It builds and publishes nothing.

The workflow `.github/workflows/weekly-bumps.yml` runs every Monday. It asks the
upstream named in each row of `_build/upstreams.txt` what it publishes now, and
where anything moved it writes the new version and the new sha256 into every home
of that pin and opens ONE pull request. The 2 values come from the same fetch and
the digest is re-proven through `_build/fetch-verified.sh` before a line is
written, so a bump cannot carry a stale digest. It merges nothing.

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

After a change is merged to `main`, each consuming project keeps the previous
commit. The project gets the change only when a person changes its submodule
pointer. The parent brain repository owns the propagation flow:

```sh
# From within brain:
bash brain/.claude/scripts/propagate.sh .devcontainer

# Or, equivalently, from this repo invoked through brain's submodule:
bash ./ctl.sh propagate
```

Propagation needs approval. See
`brain/.claude/rules/operations/shared-change-propagation.md`.
