# .devcontainer

Shared IDP (internal developer platform) images for every project in the
brain ecosystem. The repo produces **four** container images: one rich
base that most projects can run directly, two domain-specific layers on
top (flutter, zephyr), and a remote dev box layered on zephyr
(zephyr-devbox).

Each image serves two roles:

- **Local dev environment.** Projects reference these via the standard
  `.devcontainer/` convention (VS Code / JetBrains Gateway / devpod / etc.).
  You `docker pull` the image and do your work *inside* it — zsh + oh-my-zsh
  is the default shell, `/workspace` is the bind-mount target, the
  non-root `dev` user (uid 1000) has sudo-nopasswd.
- **CI runtime.** The GitHub Actions workflows in each project monorepo
  run `nx affected` inside these same images, so local and CI execute in
  an identical environment.

This repo has **no Nx workspace of its own**. It is consumed as a
submodule by every project monorepo; the parent provides the Nx runtime.
Each image follows the `project.json` + `ctl.sh` pattern enforced across
the ecosystem, and `bash ./ctl.sh <cmd>` works directly with or without Nx.

## Image inventory

| Image | Intent | `GOPHERSYS_DEVCONTAINER` |
|---|---|---|
| `ghcr.io/gophersys/base` | "Pick up and work" image. Ubuntu 24.04 + zsh/oh-my-zsh + Node LTS + Python 3.12 + Go stable + Rust stable + kubectl/helm/terraform/tailscale/docker-cli/docker-compose/bw/gh/k9s/nats + postgresql-client/sqlite3/redis-tools + jq/yq/httpie/rg/fd/bat + shellcheck/hadolint + Tauri/GTK/webkit desktop libs + libusb/libudev/libbluetooth/bluez USB-BLE libs. | `base` |
| `ghcr.io/gophersys/flutter` | Base + OpenJDK 17 + Android cmdline-tools / platform-tools / build-tools + Flutter stable SDK. Linux desktop + Android targets. iOS is out of scope. | `flutter` |
| `ghcr.io/gophersys/zephyr` | Base + device-tree-compiler / ninja / ccache / dfu-util + `west` in an isolated venv + Zephyr SDK (arm-zephyr-eabi + riscv64-zephyr-elf by default) + udev rules for common dev boards (ST-Link, J-Link, DAPLink, Black Magic Probe, nRF, Espressif). | `zephyr` |
| `ghcr.io/gophersys/zephyr-devbox` | Zephyr + sshd (key-auth only, host keys on a PVC subpath at `/etc/ssh/hostkeys`) + openocd / stlink-tools / picocom / gdb-multiarch + `esptool` in an isolated venv + every Espressif Xtensa SDK toolchain (esp32, esp32s2, esp32s3) + CP210x/CH340 USB-UART udev rules. Runs as a k8s pod, targeted with VS Code Remote-SSH; starts as root and execs sshd, logins land as `dev`. | `zephyr-devbox` |

## Dependency graph

```
       base
     ┌──┴──┐
flutter  zephyr
            │
      zephyr-devbox
```

Build order: `base`, then `flutter` and `zephyr` (both layer on `base`),
then `zephyr-devbox` (layers on `zephyr`).

## How to use

Pull an image directly:

```sh
docker pull ghcr.io/gophersys/base:latest
docker pull ghcr.io/gophersys/flutter:latest
docker pull ghcr.io/gophersys/zephyr:latest
docker pull ghcr.io/gophersys/zephyr-devbox:latest
```

As a VS Code devcontainer (inside a consuming project): this repo is
mounted at `<project>/.devcontainer/`, and each image directory ships its
own `devcontainer.json`. Run **Dev Containers: Reopen in Container** and
pick `base`, `flutter`, `zephyr`, or `zephyr-devbox` — each bind-mounts
the project to `/workspace` and runs as the `dev` user. The configs live at:

```
.devcontainer/base/devcontainer.json
.devcontainer/flutter/devcontainer.json
.devcontainer/zephyr/devcontainer.json
.devcontainer/zephyr-devbox/devcontainer.json
```

As a GitHub Actions job container:

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

Detect the image at runtime (use in scripts / CI):

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

Every image is published **multi-arch** (linux/amd64 + linux/arm64). The
rule is non-negotiable:

| Verb | Behavior |
|---|---|
| `build` | Native single-arch build for a fast local dev loop. |
| `build-multi-arch` | `docker buildx build --platform linux/amd64,linux/arm64 --load=false`. Verifies multi-arch without pushing. |
| `push` | **ENFORCED** multi-arch via buildx + `--push`. A `require_buildx_and_multi_arch` guard runs at the start of the push verb; there is no flag to downgrade to single-arch. |

CI (`.github/workflows/build-and-push.yml`) enforces the same policy on
every push to `main` and on every semver tag (`v*`).

## How to add a tool

1. **Pick the latest LTS/stable**. Research via apt-cache, upstream GitHub
   releases, or pypi. Never invent a version.
2. **Add an `ARG` at the top of the Dockerfile** with a comment:
   ```dockerfile
   ARG MY_TOOL_VERSION=1.2.3  # latest LTS as of YYYY-MM-DD
   ```
3. **Reference the ARG from the RUN line**. Hardcoded semver in `RUN` is
   forbidden and `bash ./ctl.sh validate` greps for and fails on it.
4. **Every binary install is `TARGETPLATFORM`-aware**:
   ```sh
   case "$TARGETPLATFORM" in
     linux/amd64) ARCH=amd64 ;;
     linux/arm64) ARCH=arm64 ;;
     *) echo "unsupported platform: $TARGETPLATFORM"; exit 1 ;;
   esac
   ```
5. **Clean up in the same layer** (`rm -rf /var/lib/apt/lists/*` for apt).
6. **Approval required.** Tool additions and version bumps go through the
   brain-level approval gate — they affect every consuming project.
7. Run `bash ./ctl.sh validate` until clean, then
   `bash ./ctl.sh build base` to verify the chain still builds.

## Repo layout

```
.devcontainer/
├── README.md
├── project.json                 # repo-level Nx wiring (list, validate, propagate, release)
├── ctl.sh                       # repo-wide control script
├── .claude/rules/               # identity + conventions
├── base/          { devcontainer.json, Dockerfile, project.json, ctl.sh }
├── flutter/       { devcontainer.json, Dockerfile, project.json, ctl.sh }
├── zephyr/        { devcontainer.json, Dockerfile, project.json, ctl.sh }
├── zephyr-devbox/ { devcontainer.json, Dockerfile, project.json, ctl.sh, devbox-entrypoint.sh }
└── .github/workflows/build-and-push.yml
```

## Day-to-day operations

From the repo root:

```sh
# Native single-arch build (fast dev loop).
bash ./ctl.sh build base
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

Per-image, from inside the image directory:

```sh
cd base
bash ./ctl.sh build
bash ./ctl.sh push
bash ./ctl.sh inspect
```

## CI

`.github/workflows/build-and-push.yml` builds and publishes all four
images on every push to `main`, tagged with both `:latest` and the short
commit SHA. On semver tag pushes (`v*`), it additionally publishes
`:v<semver>`. The workflow always sets up QEMU + buildx and runs
`--platform linux/amd64,linux/arm64`. Requires the `packages: write`
permission (configured in the workflow).

## Shared-change propagation

After a change lands on `main`, consuming projects still pin the previous
commit until someone explicitly bumps their submodule pointer. The
propagation flow is owned by the parent brain repo:

```sh
# From within brain:
bash brain/.claude/scripts/propagate.sh .devcontainer

# Or, equivalently, from this repo invoked through brain's submodule:
bash ./ctl.sh propagate
```

Propagation is approval-gated — see
`brain/.claude/rules/operations/shared-change-propagation.md`.
