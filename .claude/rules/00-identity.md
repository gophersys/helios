# .devcontainer — identity and conventions

Every project monorepo in the brain ecosystem uses this repository
(`gophersys/.devcontainer`) as a shared submodule. Its role is to supply the
container images. The projects use the images for local development (the VS
Code devcontainer) and as the CI runtime in which GitHub Actions runs
`nx affected`.

## Purpose

- It is the single source of truth for the canonical container images that the
  brain ecosystem uses.
- It keeps the local development environment and the CI environment identical,
  byte for byte.
- It gives you 1 place to change a toolchain version. You make the change
  exactly once, and the change then goes to every project through
  shared-change propagation.

## Image model

The repository supplies 4 **devcontainer** images and the `+ runner` layer.
Every devcontainer image sets the `GOPHERSYS_DEVCONTAINER` environment marker,
so a script can detect the image that it runs inside. A runner variant
inherits the marker of its parent and adds `GOPHERSYS_DEVCONTAINER_RUNNER=true`.

| Image | `GOPHERSYS_DEVCONTAINER` | Intent |
|---|---|---|
| `ghcr.io/gophersys/base`          | `base`          | Everything that most projects need: shells (zsh+oh-my-zsh), git/gh, languages (Node LTS, Python 3.12, Go, Rust), infra CLIs (terraform/kubectl/helm/k9s/tailscale/docker-cli/docker-compose/bw/nats), desktop libs (Tauri/GTK/webkit), USB/BLE libs (libusb, libudev, libbluetooth, bluez), data clients (psql, sqlite3, redis-cli), parsing (jq, yq, httpie, rg, fd, bat), QA (shellcheck, hadolint). |
| `ghcr.io/gophersys/flutter`       | `flutter`       | Base + OpenJDK 17 + Android cmdline-tools/platform/build-tools + Flutter stable SDK. |
| `ghcr.io/gophersys/zephyr`        | `zephyr`        | Base + device-tree-compiler/ninja/ccache + west in an isolated venv + Zephyr SDK (arm-zephyr-eabi + riscv64-zephyr-elf by default) + udev rules for common dev boards. |
| `ghcr.io/gophersys/base-runner`   | `base` + `_RUNNER=true` | Base + the GitHub Actions runner at `/home/runner`, owned by `dev`. This is a **CI image, not a devcontainer**. It has no `devcontainer.json`. The build uses `runner/Dockerfile`. |
| `ghcr.io/gophersys/zephyr-devbox` | `zephyr-devbox` | Zephyr + sshd (key-auth only, persistent host keys under /etc/ssh/hostkeys) + openocd/stlink-tools/picocom/gdb-multiarch + esptool in an isolated venv + all Espressif Xtensa SDK toolchains + CP210x/CH340 udev rules. It is an embedded development box for a k8s pod, and you connect to it over SSH. |

## Structure

```
.devcontainer/
├── README.md
├── project.json                 # repo-level Nx wiring
├── ctl.sh                       # repo-wide control
├── _ctl/lib.sh                  # the shared ctl library — every verb body, 1 time
├── .claude/rules/00-identity.md # (this file)
├── base/          { devcontainer.json, Dockerfile, project.json, ctl.sh }
├── runner/        { Dockerfile, project.json, ctl.sh }   # + runner layer — no devcontainer.json
├── flutter/       { devcontainer.json, Dockerfile, project.json, ctl.sh }
├── zephyr/        { devcontainer.json, Dockerfile, project.json, ctl.sh }
├── zephyr-devbox/ { devcontainer.json, Dockerfile, project.json, ctl.sh, devbox-entrypoint.sh }
└── .github/workflows/
    ├── build-and-push.yml    # publish the images
    ├── validate.yml          # the pull request gate: ctl.sh validate + BUILD_ORDER + shellcheck -x
    └── pr-review.yml         # the review agent, shared from gophersys/cictl
```

## Conventions

1. **This repository has no Nx workspace of its own.** You must be able to run
   every operation as plain `bash ./ctl.sh <cmd>` from within this repository.
2. **Per-image file rule.** Each devcontainer image directory at the repository
   root (`base/`, `flutter/`, `zephyr/`, `zephyr-devbox/`) contains
   `devcontainer.json` + `Dockerfile` + `project.json` + `ctl.sh`. It also
   contains each script that the image COPYs in, for example an entrypoint.
   `validate` runs shellcheck on all `*.sh` files in an image directory. Do not
   write a README for an image. The output of `bash ./ctl.sh help` is the
   specification.

   **A per-image `ctl.sh` is a thin dispatcher.** The body of each verb is in
   `_ctl/lib.sh`, 1 time only. The per-image script sets its data
   (`IMAGE_NAME`, and any build argument), it sources the library, and it
   sends the verb to `image_main`. Never copy a verb body into an image
   directory. Add the verb to the library, and every image has it.
   `_ctl/` is not an image directory. The leading underscore says so, and it
   follows `gophersys/libs`, which uses `go/_ctl/lib.sh` for the same purpose.
   An image that adds a verb of its own handles that verb first, then sends
   every other verb to `image_main`. `base/ctl.sh` does this for the
   devcontainer lifecycle verbs.

   **`runner/` is the 1 exception, and this is intentional.** It is a CI image
   and nobody opens it in an editor, so it contains no `devcontainer.json`. It
   is also the only directory whose name is not its image name. 1 Dockerfile
   builds `<parent>-runner` for every parent, and `BASE_IMAGE` or the
   `RUNNER_PARENT` environment variable selects the parent. The function
   `image_dir()` in **both** `./ctl.sh` and `.ci/ctl.sh` maps `*-runner` back
   to `runner/`. The 2 functions must agree. To add `zephyr-runner`, add a
   `BUILD_ORDER` entry and a CI job. Never write a second Dockerfile.
3. **Do not add a `CLAUDE.md` file.** The conventions of this repository stay
   here, in `.claude/rules/`.
4. **A human writes the text.** Do not put an AI or LLM attribution of any kind
   in a commit, in a comment or in a document.

## ARGs-at-top + latest-LTS convention

Every Dockerfile MUST declare all tool versions as `ARG`s at the top of the
file. Each ARG line carries a `# latest LTS as of YYYY-MM-DD` comment.

- **To change a version**, edit 1 ARG line and its date comment. Change nothing
  else.
- **A hardcoded version in a RUN line is forbidden.** `ctl.sh validate`
  searches for `=\d+\.\d+\.\d+` in a RUN line and fails the build.
- To add a new tool, select its **latest LTS or stable** release. Do the
  research with apt-cache, with the upstream GitHub releases, or with pypi.
  Never invent a version.
- **You must get approval to change a version.** A change to a version ARG goes
  through the brain-level approval gate.

## Multi-arch-on-push policy

Publish every **devcontainer** image as a multi-arch image (linux/amd64 and
linux/arm64). Both architectures have real users: an arm64 Mac and amd64 Linux.
For those images the rule is non-negotiable. You must not change it.

**An image builds only the arch it deploys to.** 2 images are narrowed today, and
both narrowings were measured, not assumed:

- `base-runner` is amd64 only. It runs only as an ARC pod, and every node in that
  cluster is amd64. Its arm64 half compiled Go under QEMU for an architecture
  that no node runs, and it took ~13 minutes on a thin layer.
- `zephyr-devbox` is amd64 only (commit `c7e8e94`). It runs only as a kubernetes
  pod. Its 3 running pods sat on `k3s-w-1`, `k3s-w-3` and `k3s-w-4`, and all 3
  are amd64. Nobody opens it locally; `zephyr` is the image for that.

So the multi-arch rule above applies to `base`, `flutter` and `zephyr`. This
paragraph exists because it did not say so for a while: `zephyr-devbox` was
narrowed in a merged commit and this rule still called multi-arch non-negotiable
for all 4, so a reader who trusted the rule would have called a decision a defect.
That happened.

Add arm64 back to either image when an arm64 consumer exists. **No arm64 consumer
can be verified for any image today**, which is recorded in gophersys/
infrastructure `docs/debt-register.md` D42 as an open question for `base`,
`flutter` and `zephyr` too.

Verify a published image with `bash ctl.sh verify-image-arch <ref> [platforms]`
in gophersys/infrastructure. A manifest declares a platform; that verb reads the
content.

For devcontainer images:

| Verb | Scope | Arch |
|---|---|---|
| `build` | local dev loop | native single-arch (fast) |
| `build-multi-arch` | local verification | buildx multi-arch, `--load=false` |
| `push` | publish | **ENFORCED** buildx multi-arch, no flag to downgrade |

The guard `require_buildx_and_multi_arch` is in `_ctl/lib.sh`, 1 time only. The
guard runs at the start of every per-image `push` verb. It fails closed in 4
conditions: the platform list is empty, buildx is absent, no buildx builder is
active, or the active builder cannot emulate 1 of the required platforms.

The list of platforms is a property of the image. `MULTI_ARCH_PLATFORMS` in the
library gives the default `linux/amd64,linux/arm64`. An image narrows the list
only with a measurement, as `runner/ctl.sh` does.

The repository-root `ctl.sh` does **not** call the guard. It sends `push` to the
per-image `ctl.sh`, which calls the guard with its own list. The root script
cannot call the guard correctly, because the list is not the same for every
image. Do not add a call to the guard there.

The CI workflow enforces the same policy. It always sets up QEMU and buildx,
and it builds with `--platform linux/amd64,linux/arm64 --push`.

## Dev-in-container expectation

Use these images for **development from inside the container**. They are not
only a CI runtime. The default `CMD` is zsh. oh-my-zsh is already installed for
the `dev` user (uid 1000, sudo-nopasswd). The working directory is
`/workspace`. This agrees with the bind-mount convention of the brain-ecosystem
projects.

Every image exports `GOPHERSYS_DEVCONTAINER=<image-name>`, so a development
script and a project CI job can detect the image that they run inside.

Each image directory contains a `devcontainer.json` that pins its published
image. A consuming project mounts the file at
`.devcontainer/<image>/devcontainer.json`. The VS Code command "Reopen in
Container" then lists `base`, `flutter`, `zephyr` and `zephyr-devbox` as
configurations that you can select. Each configuration bind-mounts the project
to `/workspace` and runs as the `dev` user.

You can also deploy `zephyr-devbox` as a k8s pod and connect to it over VS Code
Remote-SSH. Its default entrypoint runs sshd as root. The entrypoint execs any
argv that you supply, so local devcontainer use behaves like the other layers.

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

`validate.yml` runs `bash ./ctl.sh validate` and asserts that BUILD_ORDER agrees
between `ctl.sh` and `.ci/ctl.sh`. `.ci/ctl.sh validate` delegates to the root
`ctl.sh`: it used to be a second copy and the 2 diverged, so it reported OK on a
Dockerfile that the root script rejected.

The graph is declared in 4 places. All 4 MUST stay the same:

- `BUILD_ORDER` in `./ctl.sh` **and** in `.ci/ctl.sh`.
- `dependsOn` in each image's `project.json`.
- `needs:` in `.github/workflows/build-and-push.yml`.
- `.ci/providers/github/build-and-push.yml`. This file is the source of truth
  for the provider, and it must match the workflow byte for byte. Once it
  became an old copy that listed only 3 images, and nobody saw the difference.
  Examine this file again each time that the workflow changes.

## Why the `+ runner` layer exists

CI runs **these images**. There is no second set of CI images. The runner layer
makes this possible. The runner layer is a pod image and not a workflow
`container:` image. There are 2 measured reasons:

1. The dind daemon in the runner pod pulls a `container:` image, and the image
   is lost when the pod stops. At this image size the cost is 5m17s per job.
2. To pull a private package with `GITHUB_TOKEN` you need a grant for each
   (package, repository) pair. GitHub gives that grant only in its user
   interface.

The runner layer is the image of the pod itself. Thus the kubelet pulls it,
keeps it in the cache on each node, and 1 in-cluster `imagePullSecret` covers
every image and every repository.

The full interface is in `gophersys/infrastructure` `docs/ci-substrate.md`. It
states which capabilities are pools and which capabilities are images.

## Shared-change propagation

Every project monorepo uses this repository as a submodule at
`<project>/.devcontainer/`. A project does not see a change here until the
project changes its submodule pointer. Run `bash ./ctl.sh propagate` from
within brain to send the change to every project. This operation needs
approval.

## Git hygiene

- Set the git identity for each repository:
  `user.name = Mateo Segura`, `user.email = mateo.segura413@gmail.com`.
- Set `commit.gpgsign = false` for each repository.
- Use Conventional Commits for every commit.
- Do not force-push to `main`.
- Do not put an AI or LLM attribution anywhere.
