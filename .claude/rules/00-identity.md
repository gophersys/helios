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
| `ghcr.io/gophersys/cloud`         | `cloud`         | The successor image of the consolidation program (ledger #94), ADDITIVE today: the reduced base (no clang/cmake/desktop/USB-BLE/Rust/terraform/AWS/ansible, Go caches removed) + delve/buf/grpcurl + the CI fold (Actions runner, cictl, claude/omp/codex at the versions.env pins). ONE image for dev and CI: the default command is zsh, and a CI pod overrides the command to `/home/runner/run.sh`. Every pin lives in `versions.env` at the repository root; the build feeds it in as generated `--build-arg`s, and `_delta/components/*.sh` install the folded tool groups. Its smoke gates publish (build → smoke → push) and enforces the ≤ 5.75 GB size budget (raised from 5.5 GB by Mateo, 2026-08-16: the measured floor after the R4 levers with every tool kept is ~5.63–5.67 GB). |

## Structure

```
.devcontainer/
├── README.md
├── project.json                 # repo-level Nx wiring
├── ctl.sh                       # repo-wide control
├── _ctl/lib.sh                  # the shared ctl library — every verb body, 1 time
├── _ctl/tests/                  # hermetic *.test.sh + harness + docker stub + fixtures
├── .claude/rules/00-identity.md # (this file)
├── base/          { devcontainer.json, Dockerfile, project.json, ctl.sh }
├── runner/        { Dockerfile, project.json, ctl.sh }   # + runner layer — no devcontainer.json
├── flutter/       { devcontainer.json, Dockerfile, project.json, ctl.sh }
├── zephyr/        { devcontainer.json, Dockerfile, project.json, ctl.sh }
├── zephyr-devbox/ { devcontainer.json, Dockerfile, project.json, ctl.sh, devbox-entrypoint.sh }
└── .github/workflows/
    ├── build-and-push.yml    # publish the images
    ├── validate.yml          # the pull request gate: ctl.sh validate + ctl.sh test + BUILD_ORDER
    └── pr-review.yml         # the review agent, shared from gophersys/cictl
```

## Conventions

1. **This repository has no Nx workspace of its own.** You must be able to run
   every operation as plain `bash ./ctl.sh <cmd>` from within this repository.
2. **Per-image file rule.** Each devcontainer image directory at the repository
   root (`base/`, `flutter/`, `zephyr/`, `zephyr-devbox/`) contains
   `devcontainer.json` + `Dockerfile` + `project.json` + `ctl.sh`. It also
   contains each script that the image COPYs in, for example an entrypoint.
   `validate` runs `shellcheck -x -S style` on every shell script in the
   repository — found by `*.sh` name **or** by a shell shebang on the first
   line, so a script with no extension is linted too. A new script is therefore
   linted wherever you put it. Do not write a README for an image. The output
   of `bash ./ctl.sh help` is the specification.

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
- **`ARG HADOLINT_VERSION` in `base/Dockerfile` also governs the gate.**
  hadolint's verdict depends on its version — 2.15.1 raises DL3064 and DL3066 on
  Dockerfiles that 2.14.0 passes — so `validate` lints at that exact pin. It uses
  the `hadolint` on PATH when the version matches, otherwise
  `hadolint/hadolint:v<pin>` through docker, and it FAILS naming the version when
  it can reach neither. The devcontainer ships the pinned version, so a developer
  and CI get the same verdict. Raising the pin is a version change like any
  other, and it may turn new findings red.

## Sanctioned-platform policy

Every image of this repository publishes **1** platform: `linux/amd64`. The
declaration is `SANCTIONED_PLATFORMS` in `_ctl/lib.sh`, and it is the only place
a platform is named. A platform outside that set fails the guard and names
itself.

**An image builds only the arch it deploys to.** Each narrowing was measured, not
assumed:

- `base-runner` runs only as an ARC pod, and every node in that cluster is amd64.
  Its arm64 half compiled Go under QEMU for an architecture that no node runs,
  and it took ~13 minutes on a thin layer.
- `zephyr-devbox` runs only as a kubernetes pod (commit `c7e8e94`). Its 3 running
  pods sat on `k3s-w-1`, `k3s-w-3` and `k3s-w-4`, and all 3 are amd64. Nobody
  opens it locally; `zephyr` is the image for that.
- `base`, `flutter` and `zephyr` were published for 2 architectures until the
  arm64 half was measured: the published `base` arm64 variant was an amd64 Ubuntu
  userland carrying aarch64 Go binaries, because the `FROM` line pinned the
  userland to the BUILD host while buildx labelled the result with the TARGET.
  So it was mislabelled rather than native, and on the only host that would
  consume it Docker Desktop emulates that userland anyway. It gave none of the
  benefit of a native image and cost the larger half of a 41.7-minute build.

**No arm64 consumer can be verified for any image today**, which is recorded in
gophersys/infrastructure `docs/debt-register.md` D42. Widen
`SANCTIONED_PLATFORMS` on the day a consumer exists, and not before.

**Widening it is not 1 edit.** Each shell path reads the list from that 1
declaration, and `.ci/smoke.sh` selects a platform out of it rather than refusing
a list of more than 1. But 3 other places STATE the same policy, and they must
move with it: `PLATFORMS` in `.github/workflows/build-and-push.yml`, the same key
in its provider copy, and the literal `SANCTIONED` in
`_ctl/tests/platform-policy.test.sh`. That literal is deliberate — a test that
reads the value it checks agrees with any value, a wrong one included. The
`build` verb also refuses a list of more than 1 entry, because `docker build`
makes 1 image, so the local loop must name the 1 platform it wants. Measured on
2026-08-13: 1 edit to `_ctl/lib.sh`, and nothing else, made 8 checks red in 4
test files — `build` 3, `guard` 1, `platform-policy` 2, `verify-published` 2. The
per-file counts are here because the first version of this sentence said 11,
which is the TOTAL check count of `guard.test.sh` read as its failure count.

Verify a published image with `bash ./ctl.sh verify-published <image> [tag]`. A
manifest declares a platform; that verb reads the manifest back out of the
registry and asserts the set is exactly the sanctioned one. An `unknown/unknown`
entry is an attestation manifest, which buildx attaches 1 of per variant, and it
is not a variant. For the deeper check — the manifest declares a platform, but
what is in the layers — `bash ctl.sh verify-image-arch <ref> [platforms]` in
gophersys/infrastructure reads the content.

| Verb | Scope | Platform |
|---|---|---|
| `build` | local dev loop | explicit `--platform`, 1 platform, no push |
| `push` | publish | **GUARDED** buildx build + push |
| `verify-published` | after a publish | reads the manifest the registry holds |

The guard `require_buildx_and_platforms` is in `_ctl/lib.sh`, 1 time only, and it
runs at the start of every per-image `push`. It fails closed in 5 conditions: a
platform outside the sanctioned set, an empty platform list, buildx absent, no
buildx builder active, or the active builder unable to build 1 of the required
platforms. The first condition is `require_sanctioned_platforms`, which `build`
also uses.

The list of platforms an image builds is `IMAGE_PLATFORMS`, which defaults to
`SANCTIONED_PLATFORMS` and stays overridable from the environment. An image may
declare a measured NARROWER list; it may not declare a wider one, because every
entry still has to be sanctioned. `IMAGE_PLATFORMS` was called
`MULTI_ARCH_PLATFORMS` until the arm64 drop, and a tripwire in the library fails
at source time if the old name is still set — both names would hold the same
string, so a missed rename would otherwise be silent.

The repository-root `ctl.sh` does **not** call the guard. It sends `push` to the
per-image `ctl.sh`, which calls the guard with its own list. The root script
cannot call the guard correctly, because the list is not the same for every
image. Do not add a call to the guard there.

The CI workflow enforces the same policy. It sets up buildx, builds with
`--platform ${{ env.PLATFORMS }} --push`, and then runs `verify-published`
against the SHA tag it just pushed. It sets up no QEMU: emulation is what a
cross-platform build needed, and there is no cross-platform build.

The `base-runner` job builds **twice**, and the order is the point. The first
build sets `push: false` + `load: true`, so the image goes into the local image
store and not to ghcr.io. The smoke test then asserts the content of that loaded
image. Only then does the second build push, from the cache the first one wrote.
A push cannot be undone and no job here rolls one back, so a check that runs
after the push reports a broken image but cannot stop one from reaching a
consumer. `_ctl/tests/publish-order.test.sh` holds that order in the pull request
gate. `load: true` takes 1 platform, so read the arm64 note at the top of that
test file before you widen `SANCTIONED_PLATFORMS`.

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
| `build` | `docker build --platform "$IMAGE_PLATFORMS"` | false |
| `push` | `docker buildx build --platform "$IMAGE_PLATFORMS" --push` (guarded) | false |
| `verify-published [tag]` | read the published manifest; it must carry exactly `SANCTIONED_PLATFORMS` | false |
| `pull` | `docker pull ghcr.io/gophersys/<name>:latest` | false |
| `inspect` | `docker image inspect ghcr.io/gophersys/<name>:latest` | false |
| `help` | Print the usage block from `ctl.sh` | n/a |

## Repo-root verb catalog

| Verb | Action |
|---|---|
| `build <image>` | Delegate to per-image `ctl.sh build` |
| `push <image>` | Delegate to per-image `ctl.sh push` (guarded) |
| `verify-published <image> [tag]` | Delegate to per-image `ctl.sh verify-published` |
| `pull <image>` | Delegate to per-image `ctl.sh pull` |
| `inspect <image>` | Delegate to per-image `ctl.sh inspect` |
| `list` | Print the managed image refs |
| `validate` | shellcheck every shell script, jq, hadolint at the pinned version, ARG-discipline checks |
| `test` | Run every `_ctl/tests/*.test.sh`; fail if it finds none |
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

`validate.yml` runs `bash ./ctl.sh validate`, then `bash ./ctl.sh test`, then
asserts that BUILD_ORDER agrees between `ctl.sh` and `.ci/ctl.sh`. `.ci/ctl.sh
validate` delegates to the root `ctl.sh`: it used to be a second copy and the 2
diverged, so it reported OK on a Dockerfile that the root script rejected.

The graph is declared in 4 places. All 4 MUST stay the same:

- `BUILD_ORDER` in `./ctl.sh` **and** in `.ci/ctl.sh`.
- `dependsOn` in each image's `project.json`.
- `needs:` in `.github/workflows/build-and-push.yml`.
- `.ci/providers/github/build-and-push.yml`. This file is the source of truth
  for the provider, and it must match the workflow byte for byte. Once it
  became an old copy that listed only 3 images, and nobody saw the difference.
  Then it drifted again in commit `d9089b2`, which added 5 `timeout-minutes: 90`
  blocks to the workflow and to neither copy of this file, while this rule went
  on calling them identical. A rule that nothing checks is a rule that drifts:
  `_ctl/tests/platform-policy.test.sh` compares the 2 files with `cmp` now, and
  `bash ./ctl.sh test` runs it in the pull request gate.

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
