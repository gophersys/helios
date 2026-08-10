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

## Image inventory

| Image | Intent | `GOPHERSYS_DEVCONTAINER` |
|---|---|---|
| `ghcr.io/gophersys/base` | The general-purpose image. Ubuntu 24.04 + zsh/oh-my-zsh + Node LTS + Python 3.12 + Go stable + Rust stable + kubectl/helm/terraform/tailscale/docker-cli/docker-compose/bw/gh/k9s/nats + postgresql-client/sqlite3/redis-tools + jq/yq/httpie/rg/fd/bat + shellcheck/hadolint + Tauri/GTK/webkit desktop libs + libusb/libudev/libbluetooth/bluez USB-BLE libs. | `base` |
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

## Multi-arch-on-push policy

Publish every **devcontainer** image as a multi-arch image (linux/amd64 and
linux/arm64). Both architectures have real users: the images are opened on an
arm64 Mac and on amd64 Linux. For those images the rule is non-negotiable. You
must not change it:

| Verb | Behavior |
|---|---|
| `build` | A build for the native architecture only. Use it for a fast local development loop. |
| `build-multi-arch` | `docker buildx build --platform linux/amd64,linux/arm64 --load=false`. It verifies the multi-arch build and it does not push. |
| `push` | A multi-arch push with buildx and `--push`. This is **ENFORCED**. The guard `require_buildx_and_multi_arch` runs at the start of the push verb. There is no flag that changes the push to 1 architecture. |

The CI workflow `.github/workflows/build-and-push.yml` enforces the same policy
on every push to `main` and on every semver tag (`v*`).

### Runner images build only the arch they deploy to

`base-runner` is **amd64 only**. This is the only exception. `base-runner` is
not a devcontainer. It runs only as an ARC pod, and every node in that cluster
is amd64. This command shows the architecture of each node:

```sh
kubectl get nodes -o custom-columns=NAME:.metadata.name,ARCH:.status.nodeInfo.architecture
```

The arm64 half compiled Go under QEMU for an architecture that no node runs.
On a thin layer it measured **~13 minutes**. This was the largest cost of every
correction to the runner. The rule is: **build only the architecture that you
deploy to.** Add arm64 again on the day an arm64 pool exists, and not before.

## How to add a tool

1. **Select the latest LTS or stable release.** Do the research with
   apt-cache, with the upstream GitHub releases, or with pypi. Never invent a
   version.
2. **Add an `ARG` at the top of the Dockerfile** with a comment:
   ```dockerfile
   ARG MY_TOOL_VERSION=1.2.3  # latest LTS as of YYYY-MM-DD
   ```
3. **Use the ARG in the RUN line.** A hardcoded semver in a `RUN` line is
   forbidden. The command `bash ./ctl.sh validate` searches for a semver in a
   `RUN` line and fails.
4. **Make every binary installation read `TARGETPLATFORM`**:
   ```sh
   case "$TARGETPLATFORM" in
     linux/amd64) ARCH=amd64 ;;
     linux/arm64) ARCH=arm64 ;;
     *) echo "unsupported platform: $TARGETPLATFORM"; exit 1 ;;
   esac
   ```
5. **Remove the temporary files in the same layer.** For apt, use
   `rm -rf /var/lib/apt/lists/*`.
6. **You must get approval.** A new tool and a version change go through the
   brain-level approval gate. They have an effect on every consuming project.
7. Run `bash ./ctl.sh validate` until it reports no error. Then run
   `bash ./ctl.sh build base` to make sure that the chain of images still
   builds.

## Repository layout

```
.devcontainer/
├── README.md
├── project.json                 # repo-level Nx wiring (list, validate, propagate, release)
├── ctl.sh                       # repo-wide control script
├── .claude/rules/               # identity + conventions
├── base/          { devcontainer.json, Dockerfile, project.json, ctl.sh }
├── runner/        { Dockerfile, project.json, ctl.sh }   # + runner layer, no devcontainer.json
├── flutter/       { devcontainer.json, Dockerfile, project.json, ctl.sh }
├── zephyr/        { devcontainer.json, Dockerfile, project.json, ctl.sh }
├── zephyr-devbox/ { devcontainer.json, Dockerfile, project.json, ctl.sh, devbox-entrypoint.sh }
└── .github/workflows/build-and-push.yml
```

## Day-to-day operations

Run these commands from the repository root:

```sh
# Native single-arch build (fast dev loop).
bash ./ctl.sh build base
bash ./ctl.sh build base-runner
bash ./ctl.sh build flutter
bash ./ctl.sh build zephyr
bash ./ctl.sh build zephyr-devbox

# Verify multi-arch locally without pushing.
bash ./ctl.sh build-multi-arch base

# Push (ENFORCED multi-arch).
bash ./ctl.sh push base

# List canonical image refs.
bash ./ctl.sh list

# Lint shell scripts, validate JSON, lint Dockerfiles, enforce ARG discipline.
bash ./ctl.sh validate
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
`:v<semver>`. The workflow always sets up QEMU and buildx, and it builds with
`--platform linux/amd64,linux/arm64`. The workflow needs the `packages: write`
permission. The permission is set in the workflow.

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
