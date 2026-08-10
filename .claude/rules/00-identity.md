# .devcontainer — identity and conventions

This repo (`gophersys/.devcontainer`) is a shared submodule consumed by
every project monorepo in the brain ecosystem. Its role is to provide the
container images used both for local development (VS Code devcontainer)
and as the CI runtime that GitHub Actions invokes `nx affected` inside.

## Purpose

- Single source of truth for the canonical container images the brain
  ecosystem depends on.
- Keeps local dev and CI execution environments byte-for-byte identical.
- Provides a place to bump a toolchain version exactly once and have the
  change flow to every project via shared-change propagation.

## Image model

The repo exposes four **devcontainer** images plus the `+ runner` layer.
Every devcontainer image sets the `GOPHERSYS_DEVCONTAINER` env marker so
scripts can detect which image they are running inside; a runner variant
inherits its parent's marker and adds `GOPHERSYS_DEVCONTAINER_RUNNER=true`.

| Image | `GOPHERSYS_DEVCONTAINER` | Intent |
|---|---|---|
| `ghcr.io/gophersys/base`          | `base`          | Everything most projects need: shells (zsh+oh-my-zsh), git/gh, languages (Node LTS, Python 3.12, Go, Rust), infra CLIs (terraform/kubectl/helm/k9s/tailscale/docker-cli/docker-compose/bw/nats), desktop libs (Tauri/GTK/webkit), USB/BLE libs (libusb, libudev, libbluetooth, bluez), data clients (psql, sqlite3, redis-cli), parsing (jq, yq, httpie, rg, fd, bat), QA (shellcheck, hadolint). |
| `ghcr.io/gophersys/flutter`       | `flutter`       | Base + OpenJDK 17 + Android cmdline-tools/platform/build-tools + Flutter stable SDK. |
| `ghcr.io/gophersys/zephyr`        | `zephyr`        | Base + device-tree-compiler/ninja/ccache + west in an isolated venv + Zephyr SDK (arm-zephyr-eabi + riscv64-zephyr-elf by default) + udev rules for common dev boards. |
| `ghcr.io/gophersys/base-runner`   | `base` + `_RUNNER=true` | Base + the GitHub Actions runner at `/home/runner`, owned by `dev`. A **CI image, not a devcontainer** — no `devcontainer.json`. Built from `runner/Dockerfile`. |
| `ghcr.io/gophersys/zephyr-devbox` | `zephyr-devbox` | Zephyr + sshd (key-auth only, persistent host keys under /etc/ssh/hostkeys) + openocd/stlink-tools/picocom/gdb-multiarch + esptool in an isolated venv + all Espressif Xtensa SDK toolchains + CP210x/CH340 udev rules. Remote SSH-able embedded dev box for k8s pods. |

## Structure

```
.devcontainer/
├── README.md
├── project.json                 # repo-level Nx wiring
├── ctl.sh                       # repo-wide control
├── .claude/rules/00-identity.md # (this file)
├── base/          { devcontainer.json, Dockerfile, project.json, ctl.sh }
├── runner/        { Dockerfile, project.json, ctl.sh }   # + runner layer — no devcontainer.json
├── flutter/       { devcontainer.json, Dockerfile, project.json, ctl.sh }
├── zephyr/        { devcontainer.json, Dockerfile, project.json, ctl.sh }
├── zephyr-devbox/ { devcontainer.json, Dockerfile, project.json, ctl.sh, devbox-entrypoint.sh }
└── .github/workflows/build-and-push.yml
```

## Conventions

1. **No Nx workspace of its own.** Every operation must be runnable as plain
   `bash ./ctl.sh <cmd>` from within this repo.
2. **Per-image file rule.** Every devcontainer image directory at the repo
   root (`base/`, `flutter/`, `zephyr/`, `zephyr-devbox/`) contains
   `devcontainer.json` + `Dockerfile` + `project.json` + `ctl.sh`
   (plus any scripts the image COPYs in, e.g. an entrypoint — all
   `*.sh` in an image dir are shellchecked by `validate`). No per-image
   READMEs; `ctl.sh usage()` is the spec.

   **`runner/` is the one exception**, and deliberately so. It is a CI image,
   never opened in an editor, so it ships no `devcontainer.json`. It is also
   the only directory whose name is not its image name: one Dockerfile builds
   `<parent>-runner` for every parent, selected by `BASE_IMAGE` / the
   `RUNNER_PARENT` env var. `image_dir()` in **both** `./ctl.sh` and
   `.ci/ctl.sh` maps `*-runner` back to `runner/`; the two resolvers must
   agree. Adding `zephyr-runner` is a `BUILD_ORDER` entry and a CI job — never
   a second Dockerfile.
3. **No `CLAUDE.md` files.** Repo-specific conventions live here in
   `.claude/rules/`.
4. **Human-authored voice.** Commits, comments, and docs contain no AI/LLM
   attribution of any kind.

## ARGs-at-top + latest-LTS convention

Every Dockerfile MUST declare all tool versions as `ARG`s at the top of the
file. Each ARG line carries a `# latest LTS as of YYYY-MM-DD` comment.

- **Bumping a version** = edit one ARG line + its date comment, nothing else.
- **Hardcoding a version in a RUN line is forbidden.** `ctl.sh validate`
  greps for `=\d+\.\d+\.\d+` inside RUN lines and fails the build.
- Adding a new tool requires picking its **latest LTS/stable** release
  (research via apt-cache / upstream GitHub releases / pypi) — never
  invent a version.
- Approval required for bumps: changes to version ARGs go through the
  brain-level approval gate.

## Multi-arch-on-push policy

Every **devcontainer** image is published multi-arch (linux/amd64 +
linux/arm64) — both are real consumers, an arm64 Mac and amd64 Linux. For
those the rule is non-negotiable.

**Runner images build only the arch they deploy to.** `base-runner` is amd64
only: it runs solely as an ARC pod and every node in that cluster is amd64, so
its arm64 half was Go compiled under QEMU for an architecture nothing runs
(~13 minutes on a thin layer). Add arm64 back when an arm64 pool exists.

For devcontainer images:

| Verb | Scope | Arch |
|---|---|---|
| `build` | local dev loop | native single-arch (fast) |
| `build-multi-arch` | local verification | buildx multi-arch, `--load=false` |
| `push` | publish | **ENFORCED** buildx multi-arch, no flag to downgrade |

Both the repo-root and per-image `ctl.sh` expose
`require_buildx_and_multi_arch` as a guard that runs at the start of every
`push` verb. It fails closed if buildx is missing, if no buildx builder is
active, or if the active builder cannot emulate both required platforms.

The CI workflow enforces the same policy: it always sets up QEMU +
buildx and builds with `--platform linux/amd64,linux/arm64 --push`.

## Dev-in-container expectation

These images are intended for **development from inside the container**,
not just CI runtime. The default `CMD` is zsh; oh-my-zsh is preinstalled
for the `dev` user (uid 1000, sudo-nopasswd). Workdir is `/workspace`,
matching the bind-mount convention used by brain-ecosystem projects.

Every image exports `GOPHERSYS_DEVCONTAINER=<image-name>` so dev scripts
and project CI can detect which image they are running inside.

Each image directory ships a `devcontainer.json` pinned to its published
image. Mounted inside a consuming project at
`.devcontainer/<image>/devcontainer.json`, VS Code's "Reopen in Container"
lists `base`, `flutter`, `zephyr`, and `zephyr-devbox` as selectable
configurations — each bind-mounts the project to `/workspace` and runs as
the `dev` user. `zephyr-devbox` is additionally deployable as a k8s pod
targeted over VS Code Remote-SSH: it defaults to a root-run sshd
entrypoint, and its entrypoint execs any provided argv so local
devcontainer use behaves like the other layers.

## Per-image verb catalog

| Verb | Action | Cache |
|---|---|---|
| `build` | native single-arch `docker build` | false |
| `build-multi-arch` | `docker buildx build --platform linux/amd64,linux/arm64 --load=false` | false |
| `push` | `docker buildx build --platform linux/amd64,linux/arm64 --push` (guarded) | false |
| `pull` | `docker pull ghcr.io/gophersys/<name>:latest` | false |
| `inspect` | `docker image inspect ghcr.io/gophersys/<name>:latest` | false |
| `help` | Print the usage block from `ctl.sh` | n/a |

## Repo-root verb catalog

| Verb | Action |
|---|---|
| `build <image>` | Delegate to per-image `ctl.sh build` |
| `build-multi-arch <image>` | Delegate to per-image `ctl.sh build-multi-arch` |
| `push <image>` | Delegate to per-image `ctl.sh push` (multi-arch enforced) |
| `pull <image>` | Delegate to per-image `ctl.sh pull` |
| `inspect <image>` | Delegate to per-image `ctl.sh inspect` |
| `list` | Print the managed image refs |
| `validate` | shellcheck, jq, hadolint, ARG-discipline checks |
| `propagate` | Fan out submodule pointer bumps (delegates to brain) |
| `release` | Cut a release (delegates to brain) |
| `help` | Usage |

## Dependency graph

```
           base
    ┌────┬──┴──┐
base-   flutter  zephyr
runner              │
              zephyr-devbox
```

Declared in four places that MUST stay in sync:

- `BUILD_ORDER` in `./ctl.sh` **and** in `.ci/ctl.sh`.
- `dependsOn` in each image's `project.json`.
- `needs:` in `.github/workflows/build-and-push.yml`.
- `.ci/providers/github/build-and-push.yml`, the provider source of truth —
  it must match the workflow byte for byte. It silently drifted to a stale
  three-image copy once; re-check it whenever the workflow changes.

## Why the `+ runner` layer exists

CI runs **these images**, not a parallel CI image set. The runner layer is what
makes that possible, and it is a pod image rather than a workflow `container:`
image for two measured reasons: a `container:` image is pulled inside the runner
pod's dind daemon and dies with the pod (5m17s per job at this image size), and
pulling a private package with `GITHUB_TOKEN` needs a per-(package, repository)
grant that GitHub exposes only in its UI. As the pod's own image the kubelet
pulls it, caches it per node, and one in-cluster `imagePullSecret` covers every
image and every repo.

The full interface — which capabilities are pools and which are images — is
`gophersys/infrastructure` `docs/ci-substrate.md`.

## Shared-change propagation

This repo is consumed as a submodule by every project monorepo under
`<project>/.devcontainer/`. Changes here are not visible to projects until
each project bumps its submodule pointer. Run `bash ./ctl.sh propagate`
from within brain to fan out the bump — approval-gated.

## Git hygiene

- Git identity is set per-repo:
  `user.name = Mateo Segura`, `user.email = mateo.segura413@gmail.com`.
- `commit.gpgsign = false` per-repo.
- Conventional Commits for every commit.
- No force-pushes to `main`.
- No AI/LLM attribution anywhere.
