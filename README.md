# .devcontainer

This repository holds the shared IDP (internal developer platform) images for
Eden. `gophersys/eden` uses it as a submodule at `.devcontainer/`. The
repository builds **6** container images:

- 1 base image with many tools. Most projects can use it directly.
- 2 domain-specific layers on top of the base image: mobile, and embedded —
  the Zephyr toolchain AND the remote development box, in 1 image whose 2
  identities are a mode of its entrypoint.
- 1 cloud image, built from ubuntu directly rather than from base: the reduced
  base plus the CI fold. Every ARC runner pool runs it.
- 2 category layers on top of cloud: hardware, which adds the KiCad ECAD
  toolchain, and ui, which adds headless Chrome.

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
| `ghcr.io/gophersys/mobile` | Base + OpenJDK 21 + Android cmdline-tools / platform-tools / build-tools + Flutter stable SDK. The targets are Linux desktop and Android. iOS is not in the scope. | `mobile` |
| `ghcr.io/gophersys/embedded` | Base + device-tree-compiler / ninja / ccache / dfu-util + `west` in an isolated venv + Zephyr SDK (arm-zephyr-eabi + riscv64-zephyr-elf by default) + every Espressif Xtensa SDK toolchain (esp32, esp32s2, esp32s3) + `esptool` in an isolated venv + the flash/debug bench (openocd / stlink-tools / picocom / gdb-multiarch / clangd) + udev rules for common dev boards (ST-Link, J-Link, DAPLink, Black Magic Probe, nRF, Espressif) and for the CP210x/CH340 USB-UART bridges. **It was 2 images**, `zephyr` and `zephyr-devbox`, and the pod half of that fold — sshd, code-server on `:8443`, the `DEVBOX_*` env contract and the `GOPHERSYS_EMBEDDED_MODE` dispatch — **is DELETED** (Mateo, 2026-08-19); see "The devbox mode is deleted" in `.claude/rules/00-identity.md`. It still ships `USER root`, and its entrypoint drops to `dev` before it execs your command — see "The embedded entrypoint" below. Size budget 8.15 GB: the first post-deletion publish (run 32231070482) measured 7,760,642,048 unpacked bytes, and the row is that + 5%. | `embedded` |
| `ghcr.io/gophersys/cloud` | The reduced base + the CI fold (the Actions runner, cictl, buildx, the harnesses), built `FROM ubuntu` directly rather than from `base`, so it is a reduction and not a layer. **Every ARC pool runs it**, and the same image is a devcontainer: the default command is zsh and a CI pod overrides it. Every pin comes from `versions.env`. | `cloud` |
| `ghcr.io/gophersys/hardware` | Cloud + the KiCad 10 ECAD toolchain from the project's own PPA (`kicad`, `kicad-symbols`, `kicad-footprints`, `kicad-packages3d`) + the python stack the consumer's suite imports and runs (`kiutils`, `sexpdata`, `pytest`, `ruff`). `kicad-cli` drives headless ERC, DRC, netlist export and Gerber generation. The consumer is `gophersys/research-hardware`. It is 1 of the 2 CHILD images whose pins come from `versions.env`: its ARGs are value-less like cloud's, and `pins: versions.env` on its manifest entry generates the build args. Size budget 10.52 GB — reset on 2026-08-19 from the 11.0 estimate to the first green build measured on the repaired gate, + 5%. See the note beside the key in `images.yaml`. | `hardware` |
| `ghcr.io/gophersys/ui` | Cloud + headless Chrome and the DejaVu fallback font. The consumer is `gophersys/research-ui`. It exposes cloud's own Node and uv at `/usr/local/bin` rather than installing a second copy of each, and its content group asserts `node`/`npm`/`uv` resolving as BOTH root and dev. It is the other CHILD whose pins come from `versions.env`. Size budget 6.33 GB — reset on 2026-08-19 from the 6.5 estimate to the first build measured on the repaired gate, + 5%. See the note beside the key in `images.yaml`. | `ui` |

**`mobile` was `flutter` until 2026-08-18**, and the rename reached the IMAGE
alone: one name per category, the last naming step of the consolidation
program. The Flutter SDK keeps its own name everywhere it appears —
`FLUTTER_VERSION`, `/opt/flutter`, the `flutter` binary, the `flutter-releases`
datasource and the `content-flutter` check group all read the same as before,
because each one names the SDK and not the image that carries it.
`ghcr.io/gophersys/flutter` stays in the registry as the rollback anchor,
frozen at its last publish; `ghcr.io/gophersys/mobile` is created by the first
publish after the merge.

## Dependency graph

```
        base                cloud
     ┌───┴────┐         (FROM ubuntu)
 mobile   embedded     ┌────┴────┐
                     hardware    ui
```

Build in this order:

1. `base`, and `cloud` beside it — `cloud` depends on nothing here.
2. `mobile` and `embedded`. Both layer on `base`.
3. `hardware` and `ui`. Both layer on `cloud`.

**That drawing is prose. `images.yaml` is the graph**, and it is the only place
the image set is declared. Each entry carries the image's parent, its build
context and Dockerfile, the paths a change to which rebuilds it, and the smoke
check groups it runs. Everything mechanical is derived from it: `BUILD_ORDER` in
both control scripts, the parent map and the input path table `.ci/affected.sh`
answers with, the check groups `.ci/smoke.sh` sends to the guest, the 6 publish
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
docker pull ghcr.io/gophersys/mobile:latest
docker pull ghcr.io/gophersys/embedded:latest
docker pull ghcr.io/gophersys/hardware:latest
docker pull ghcr.io/gophersys/ui:latest
```

### As a VS Code devcontainer

A consuming project mounts this repository at `<project>/.devcontainer/`. Each
image directory contains its own `devcontainer.json`. Run **Dev Containers:
Reopen in Container** and select `base`, `cloud`, `mobile`, `embedded`,
`hardware` or `ui`. Each configuration bind-mounts the project to `/workspace` and
runs as the `dev` user. The configuration files are at these paths:

```
.devcontainer/base/devcontainer.json
.devcontainer/cloud/devcontainer.json
.devcontainer/mobile/devcontainer.json
.devcontainer/embedded/devcontainer.json
.devcontainer/hardware/devcontainer.json
.devcontainer/ui/devcontainer.json
```

`cloud/devcontainer.json` carries no `postCreateCommand` and `base` does. The
difference is where the harnesses come from: `cloud` bakes claude, omp and codex
into the image through `_delta/components/agents.sh` at the `versions.env` pins,
so a container start does zero network installs. `base` ships no harness, so
`base/ctl.sh post-create` installs them at create time.

### The local/CI 1:1 workflow

**One image, two consumers.** A developer opens
`ghcr.io/gophersys/<image>:latest` on the Apple Silicon Mac. A CI job runs
`ghcr.io/gophersys/<image>:latest` on the ARC pool. The 2 refs are equal, because
they are the same string: 1 publish writes 1 manifest list, and that list holds
both variants.

- **The amd64 leg runs CI.** Every ARC node is amd64, so a job pulls that
  variant.
- **The arm64 leg is what the Mac opens.** The devcontainer CLI pulls the variant
  of the host, and the Mac mini builds that leg natively.

Nothing here selects a platform. Each `devcontainer.json` names the tag alone,
and the docker client takes the variant of the host out of the manifest list. So
a developer and a CI job get the same pins, the same tools and the same
`GOPHERSYS_DEVCONTAINER` value.

`ctl.sh validate` enforces the workflow, and it does so as a SET. The image set
of `images.yaml` and the set of `*/devcontainer.json` files are one set, in both
directions: an image with no such file is an image nobody can open locally, and
a file in a directory no image declares points at a ref nothing here builds. Each
file must also open the image of its own directory. A `ui/devcontainer.json` that
names cloud's ref matches the shape rule exactly, and it gives the developer a
container that no CI job of `ui/` has ever run.

**`mobile` is the exception, and it is the only one.** That image publishes
`linux/amd64` alone, because Flutter publishes no linux-arm64 SDK.

**The ref is younger than this section, so read it in that order.**
`ghcr.io/gophersys/flutter` holds the frozen rollback anchor, and the first
publish after the rename merge CREATES `ghcr.io/gophersys/mobile` — the image
inventory above says the same. A pull of that ref fails until then, and it fails
for both architectures. ONCE the package exists, an arm64 host emulates the
amd64 variant, or it does not use `mobile` locally. The developer's `uname -m`
then disagrees with every CI job of that image. Read "Why mobile is the
exception" below for the measurement.
`_ctl/tests/platform-policy.test.sh` holds this paragraph to the manifest: an
image that loses its arm64 variant, and takes no name here, turns that file red.

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
  mobile)       echo "running in the mobile layer" ;;
  embedded)      echo "running in the embedded layer" ;;
  hardware)      echo "running in the hardware layer" ;;
  ui)            echo "running in the ui layer" ;;
  *)             echo "not inside a gophersys devcontainer" ;;
esac
```

**The `cloud)` arm is not optional.** Every ARC pool runs `cloud`, so a copy of
this block without that arm sends every CI job to the `*)` arm and prints "not
inside a gophersys devcontainer" from inside a gophersys devcontainer. That arm
was missing here while the same README said 45 lines higher that the pools run
`cloud`.

### The embedded entrypoint

`embedded/embedded-entrypoint.sh` is PID 1 of the image, and it does ONE thing:

| Step | What it does | Operator knob |
|---|---|---|
| dev drop | Execs the argv docker hands it — the image `CMD` when you named none — as `dev`. At euid 0 that is `runuser -u dev --`; at any other euid (`docker run --user dev`, which `.ci/smoke.sh` does) it execs plainly, because `runuser` REFUSES below root and would turn a working invocation into an error. **An EMPTY argv exits 2** naming the cause: the image declares `CMD`, so reaching it means a caller replaced `CMD` with nothing, and `exec` with no argument is a no-op that would hand you a container which started nothing and exited 0. | — |

That table had **7 rows**, and the other 6 were the pod: SSH host keys into
`/etc/ssh/hostkeys`, mountpoint ownership, `authorized_keys` from
`DEVBOX_AUTHORIZED_KEYS`, the `/dev/mcu-slot-N` links, code-server on `:8443`
behind `DEVBOX_CODE_SERVER_HASHED_PASSWORD`, and `exec sshd`. **All 6 are
deleted** — Mateo, 2026-08-19 — along with `GOPHERSYS_EMBEDDED_MODE`, the
`/run/devbox-degraded` marker and the `EXPOSE 22` / `EXPOSE 8443` lines. The
decision and its evidence are in `.claude/rules/00-identity.md`, "The devbox
mode is deleted".

**The image still ships `USER root`**, and this script is what puts `dev` back,
so `docker run embedded id` answers `dev` exactly as the pre-fold `USER dev`
line made it. Nothing in the image needs root any more; collapsing the pair into
a plain `USER dev` is open work stated at the top of the entrypoint, because it
also removes `.ci/smoke.sh`'s embedded-only `--user dev` arm.

## Sanctioned-platform policy

The sanctioned set is **2** platforms: `linux/amd64` and `linux/arm64`.
`SANCTIONED_PLATFORMS` in `_ctl/lib.sh` declares them, and it is the only place a
platform is named. A platform outside that set fails the guard and names itself,
so an edit that adds a third fails loudly instead of quietly restoring an
emulated build.

5 of the 6 images publish both. **`mobile` alone narrows**, to `linux/amd64`, and
that exception is DATA: a `platforms` key on its entry in `images.yaml`, with the
measurement beside it. An image with no such key takes the sanctioned set, and a
key that named a platform outside the set is refused — narrower is an exception
WITHIN the policy, wider would replace it.

| Verb | Behavior |
|---|---|
| `build` | `docker build --platform "$IMAGE_PLATFORMS"`. The `--platform` is explicit: a bare `docker build` targets the HOST, which on an Apple Silicon Mac is not the platform that gets published. It takes 1 platform, so with 2 sanctioned the local loop names the one it wants: `IMAGE_PLATFORMS=linux/arm64 bash ./ctl.sh build base`. |
| `push` | `docker buildx build --platform "$IMAGE_PLATFORMS" --push`. The guard `require_buildx_and_platforms` runs at the start of the verb. |
| `verify-published [tag]` | Read the manifest the registry holds and assert it carries exactly `$IMAGE_PLATFORMS` — the image's OWN set, which is the sanctioned set unless `images.yaml` narrows it. A platform the image does not publish is refused too, so the rule is equality and not "at least". |

The guard is in `_ctl/lib.sh`, 1 time only, and each per-image `push` calls it.
It fails closed in 5 conditions: a platform outside the sanctioned set, an empty
platform list, buildx absent, no buildx builder active, or the active builder
unable to build 1 of the required platforms. The list an image builds is
`IMAGE_PLATFORMS`, resolved from 3 sources in falling precedence: the
environment, the image's `platforms` key in `images.yaml`, and the sanctioned
set. An image may declare a measured NARROWER list but never a wider one.

`verify-published` asserts the set the IMAGE publishes, not the sanctioned set.
Against the sanctioned set, mobile's correct amd64-only manifest would read as
a broken publish on every run.

The repository-root `ctl.sh` does **not** call the guard. It sends `push` to
the per-image `ctl.sh`, which calls the guard with its own list of platforms.
The root script cannot call the guard correctly, because the list is not the
same for every image.

The CI workflow `.github/workflows/build-and-push.yml` enforces the same policy
on every push to `main` and on every semver tag (`v*`), and each of its jobs runs
`verify-published` against the SHA tag it just pushed.

Each job builds **twice**, and the 2 builds name different platform lists:

- the **gate** build takes `SMOKE_PLATFORM` (`linux/amd64`), sets
  `push: false` + `load: true`, and `.ci/smoke.sh` asserts the content of the
  image it loaded. `load: true` takes 1 platform, because buildx writes a
  manifest LIST for 2 and the docker image store holds a single image.
- the **publish** build takes the whole `PLATFORMS`. Its amd64 layers come from
  the cache the gate wrote; the arm64 leg is built here, on the mini.

**The arm64 content is therefore not smoke-gated at publish time.** The amd64
smoke gates the publish for both variants, the digest comparison on every
download covers the arm64 bytes, and `verify-published` asserts the manifest
carries both. Smoking arm64 out of the registry after the push is the recorded
follow-up.

### Rehearsal mode

Dispatch the workflow with `mode=rehearsal` to run everything except the ship:

```sh
gh workflow run build-and-push.yml --ref <branch> -f mode=rehearsal
```

Every job builds its gate image and smokes it exactly as in publish mode, then
runs the publish-shaped build — same context, same build-args, same per-image
`PLATFORMS`, same builders including the arm64 node — with `push: false`. The
manifest read-back is skipped, because nothing was pushed and reading the
previous `:<sha>` would report a verdict about another run's build.

It exists because the arm64 leg is built only by the publish step, so without it
the only way to exercise a branch's real multi-platform build was to publish it.
`mode` defaults to `publish`, and a `push` event carries no input at all, so
publish behaviour is unchanged.

### Why there IS an arm64 variant

Every image runs where its consumers are. The rule is **build only the
architecture that you deploy to**, and it is the rule that removed arm64 in
July and the rule that brought it back:

- the arm64 consumer is real now. Local development on Apple Silicon runs these
  images through the devcontainer CLI, so `base`, `cloud` and `embedded` are
  opened on an arm64 host daily. D42 in gophersys/infrastructure
  `docs/debt-register.md` — "no arm64 consumer can be verified" — is answered.
- it is built NATIVELY, which the old one was not. The Mac mini runs a
  standalone buildkitd and buildx appends it as an arm64 node
  (`.ci/buildx-node.sh`); a native build there measured 3.44x faster than the
  same build emulated on an amd64 node. No job installs QEMU.
- the old arm64 variant was mislabelled rather than native: the published `base`
  arm64 image was an amd64 Ubuntu userland carrying aarch64 Go binaries, because
  the `FROM` line pinned the userland to the BUILD host while buildx labelled
  the result with the TARGET platform. On an Apple Silicon host Docker Desktop
  emulates that userland anyway, which is why nobody noticed. No Dockerfile here
  writes `FROM --platform=` now, and `_ctl/tests/platform-policy.test.sh` fails
  one that does.

### Why mobile is the exception

**Flutter publishes no linux-arm64 SDK, at any version.** Read on 2026-08-17,
`https://storage.googleapis.com/flutter_infra_release/releases/releases_linux.json`
(264191 bytes) lists every Linux release ever published and
`[.releases[].dart_sdk_arch] | unique` returns `[null,"x64"]` over 730 releases:
431 predate the key, 299 say `x64`, and the count that decides it —
`[.releases[] | select(.dart_sdk_arch != null and .dart_sdk_arch != "x64")]
| length` — is **0**. The pinned 3.47.0 stable carries 1 archive, and its
filename holds no architecture, so an HTTP probe of it returns 200 and proves
nothing. **Read the JSON, never the 200.**

No bump reaches an asset upstream does not publish, so this does not expire on
its own. `mobile/Dockerfile` keeps amd64-only `case` arms and they are correct,
not incomplete. On the day Flutter ships an arm64 Linux SDK, delete the
`platforms` key from `images.yaml` and add the arm64 arms and their
`_SHA256_ARM64` rows in the same change.

The amd64 half of every measurement stands unchanged: the ARC nodes are amd64,
and this command shows the architecture of each node.

```sh
kubectl get nodes -o custom-columns=NAME:.metadata.name,ARCH:.status.nodeInfo.architecture
```

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
   the 1 way to lose it silently. A tool of `mobile` or `embedded` still takes
   an `ARG MY_TOOL_VERSION=1.2.3` in that image's
   own Dockerfile — those 2 have not moved yet, and moving them is ledger #102.
3. **Add a sha256 digest row per sanctioned platform beside that version**, in
   the SAME home. Each value comes from the asset you just selected, never from
   a second table:
   ```
   MY_TOOL_VERSION=1.2.3  # latest LTS as of YYYY-MM-DD
   MY_TOOL_SHA256_AMD64=<64 lowercase hex>  # upstream-published: <checksum file url>
   MY_TOOL_SHA256_ARM64=<64 lowercase hex>  # upstream-published: <checksum file url>
   ```
   The vocabulary is `_SHA256_AMD64` and `_SHA256_ARM64`, or `_SHA256_NOARCH`
   when 1 asset serves every platform — a sanctioned platform with no row is an
   empty digest reaching that leg of the build. Write
   `# upstream-published: <url>` when the release ships a
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
     "${SHA256}" "${SHA256_PIN}"
   ```
   Both locals come from the `case` arm in step 7: the digest is passed once for
   its value and once as the name the failure message prints, and with 2
   platforms the arm is what chooses which row is in play. `base` and `cloud` COPY the helper from
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
7. **Make every binary installation read `TARGETPLATFORM`**, 1 arm per
   sanctioned platform, each arm on 1 line:
   ```sh
   case "$TARGETPLATFORM" in
     linux/amd64) ARCH=amd64; SHA256="${MY_TOOL_SHA256_AMD64}"; SHA256_PIN=MY_TOOL_SHA256_AMD64 ;;
     linux/arm64) ARCH=arm64; SHA256="${MY_TOOL_SHA256_ARM64}"; SHA256_PIN=MY_TOOL_SHA256_ARM64 ;;
     *) echo "unsupported platform: $TARGETPLATFORM"; exit 1 ;;
   esac
   ```
   The arm carries the ASSET spelling (`x64`, `x86_64`, `aarch64` — whatever
   upstream names it) and the digest ROW of its own platform; the fetch then
   reads `"${SHA256}" "${SHA256_PIN}"`. Both rows are verified before the edit:
   the arm64 asset must exist AT THE PINNED VERSION, and a pin where it does not
   is a blocker to report rather than a bump to improvise. The `*)` arm is what
   makes an unsanctioned platform stop the build instead of installing the wrong
   binary.

   2 traps, both measured: an arm broken across lines reads as an arm that
   assigns nothing (`fetch_urls` in `_ctl/lib.sh` reads to the `;;` on the same
   logical line), and a pin-name local spelled `MY_TOOL_SHA256_PIN` reads as a
   digest ROW to every reader of the vocabulary. Keep `SHA256_PIN` bare, or use
   `MY_TOOL_PIN` where 1 arm feeds 2 fetches.
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
├── versions.env                 # the ONE pin home of base, cloud and hardware
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
├── docs/                        # PROPOSALS — part of one has LANDED; see docs/README.md
├── .claude/rules/               # identity + conventions
├── .ci/                         # the CI layer — .ci/README.md lists every file
│   ├── affected.sh              # which images a commit changes — 1 home for the answer
│   ├── buildx-node.sh           # the builder every image build uses; owns the arm64 switch
│   └── mirror-buildkit.sh       # keeps ghcr.io holding the BuildKit index the builder boots from
├── base/          { devcontainer.json, Dockerfile, project.json, ctl.sh }
├── cloud/         { devcontainer.json, Dockerfile, project.json, ctl.sh }
├── mobile/       { devcontainer.json, Dockerfile, project.json, ctl.sh }
├── embedded/      { devcontainer.json, Dockerfile, project.json, ctl.sh, embedded-entrypoint.sh }
├── hardware/      { devcontainer.json, Dockerfile, project.json, ctl.sh }
├── ui/            { devcontainer.json, Dockerfile, project.json, ctl.sh }
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
IMAGE_NAME="mobile"
source "$PROJECT_ROOT/../_ctl/lib.sh"
image_main "$@"
```

The library reads this data. **Set the first 6 items BEFORE the source line**,
because the library reads them while it loads. It reads the last 2 at call time,
so those may be set after:

| Name | Use |
|---|---|
| `PROJECT_ROOT` | The directory that holds the script. Required. |
| `IMAGE_NAME` | The image slug, for example `mobile`. Required for the image verbs. |
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
`homes_of`, `digest_rows_of`, `fetch_urls` and `bump_pin`. Their own verbs act on
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
bash ./ctl.sh build mobile
bash ./ctl.sh build embedded
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
which 6 images at `mode=max` do not fit.

**The builder comes from `bash .ci/buildx-node.sh`** and not from
`docker/setup-buildx-action`. It owns the switch that appends the Mac mini as a
native arm64 node when `SANCTIONED_PLATFORMS` names `linux/arm64`. That switch
reads the library, so it needed no edit when the set widened, and it is LIVE:
the first dual-arch build is the mini's first real work, and an unreachable mini
or an expired client PEM fails at the `--bootstrap` that step ends with.

**The builder has one driver, `remote`, for both of its nodes.** buildx refuses
a builder whose nodes disagree — a `docker-container` builder rejects a
`--driver remote` append with `mismatched driver`, and a rehearsal run died
exactly there. So the local node is a buildkitd container the script starts
itself from the ghcr-mirrored `BUILDKIT_REF`, in the pod's network namespace,
on `tcp://127.0.0.1:18234`, pinned to `linux/amd64`. It keeps everything the
`docker-container` driver gave: a registry cache the plain `docker` driver
cannot read or write, `load: true` for the gate build, the pod's netns and the
`--oci-worker-net=host` worker flag. The endpoint is plaintext because only the
pod can route to it; the mini keeps mTLS because it is on the tailnet. Re-running
the step removes and recreates — `buildx create` on an existing name fails even
when the driver matches.

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

**A bump moves every `_SHA256_` row of a pin, or it moves none of it.** A pin has
one digest row per platform its download has a case arm for, so `fetch_urls`
reads every arm, `digest_rows_of` reports the whole set, and the resolver fetches
one asset per arm — buf spells its arm64 asset `aarch64` where grpcurl spells the
same platform `arm64`, and each arm carries the spelling its own asset uses. The
durable half is the writer: `bump_pin` refuses a call that leaves a declared row
unnamed, and says which row. A row left on the old digest is invisible in the
diff and fails the build on the leg it answers for. A row named by two arms that
build two different asset URLs is refused too, naming both: a digest row attests
one asset, so that shape is a defect and not a bump.

Because the arms are read as WRITTEN and never against `SANCTIONED_PLATFORMS`,
a download with one arm and a download with no arm each take exactly one row with
no special case for either. `mobile/Dockerfile` holds one of each, and the
pairing is the opposite of the intuitive one: the Android cmdline-tools download
sits under a `linux/amd64) : ;;` guard and carries a `_NOARCH` row, while
flutter's own SDK download sits in a RUN with no case at all and carries the
`_AMD64` row — nothing in that RUN names a platform, and the `exit 1` in the
guard above is what makes the image amd64-only.

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
